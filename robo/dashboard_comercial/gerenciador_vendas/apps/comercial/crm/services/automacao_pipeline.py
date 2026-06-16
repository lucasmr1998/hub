"""
Motor de Automações do Pipeline.

Avalia regras configuradas em `RegraPipelineEstagio` contra o estado atual de
uma oportunidade e move entre estágios quando uma regra bate.

Lógica:
- Condições dentro de uma regra: AND (todas devem bater)
- Regras dentro de um estágio: OR (qualquer uma basta)
- Estágios avaliados por `ordem` DESC (mais avançado primeiro)
- Estágios finais (is_final_ganho / is_final_perdido) não são reavaliados
- Multi-tenant: engine sempre resolve pela tenant da oportunidade
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def processar_oportunidade(oportunidade):
    """
    Ponto de entrada chamado pelos signals.
    Avalia regras de estágio (move oportunidade) e regras de ação (executa ações).
    """
    if oportunidade is None:
        return

    # Flag pra evitar loop de signals
    if getattr(oportunidade, '_skip_rules_evaluation', False):
        return

    estagio = oportunidade.estagio
    if estagio is None:
        return

    # Não reavaliar oportunidades em estágio final
    if estagio.is_final_ganho or estagio.is_final_perdido:
        return

    # 1. Regras com estágio destino → move oportunidade
    resultado = _avaliar_regras(oportunidade)
    if resultado is not None:
        estagio_destino, regra, _condicoes = resultado
        if oportunidade.estagio_id != estagio_destino.pk:
            _mover_por_regra(oportunidade, estagio_destino, regra)

    # 2. Regras de ação pura (sem estágio destino)
    _avaliar_e_executar_acoes(oportunidade)


def processar_lead(lead_id):
    """Wrapper pra chamar a partir de signal que só tem lead_id."""
    from apps.comercial.crm.models import OportunidadeVenda

    try:
        oportunidade = (
            OportunidadeVenda.all_tenants
            .select_related('estagio', 'lead')
            .get(lead_id=lead_id)
        )
    except OportunidadeVenda.DoesNotExist:
        return

    processar_oportunidade(oportunidade)


# ============================================================================
# AVALIAÇÃO
# ============================================================================

def _avaliar_regras(oportunidade):
    """
    Avalia todas as regras ativas do tenant da oportunidade contra o estado atual.
    Retorna (estagio_destino, regra, condicoes) ou None.
    """
    from apps.comercial.crm.models import PipelineEstagio

    tenant = oportunidade.tenant
    if tenant is None:
        return None

    contexto = _construir_contexto(oportunidade)

    # Estágios com regras ativas, do mais avançado pro menos (ordem DESC).
    # Garante que um lead que já atende ao estágio final não seja pego por regra
    # genérica de estágio anterior.
    estagios_com_regras = (
        PipelineEstagio.all_tenants
        .filter(tenant=tenant, ativo=True, regras__ativo=True)
        .distinct()
        .order_by('-ordem')
        .prefetch_related('regras')
    )

    for estagio in estagios_com_regras:
        regras = estagio.regras.filter(ativo=True).order_by('prioridade')
        for regra in regras:
            if _regra_bate(regra, contexto):
                return (estagio, regra, regra.condicoes)

    return None


def _construir_contexto(oportunidade):
    """
    Pré-carrega dados usados pelas condições chamando `coletar_contexto` de cada
    tipo registrado. Ordem minimiza queries (cada tipo popula só o que precisa).
    """
    from apps.comercial.crm.services import automacao_condicoes

    contexto = {
        'lead': oportunidade.lead,
        'oportunidade': oportunidade,
    }
    for tipo in automacao_condicoes.REGISTRY.values():
        try:
            tipo.coletar_contexto(oportunidade, contexto)
        except Exception as exc:
            logger.warning("[Automacao Pipeline] Falha ao coletar contexto de %s: %s", tipo.slug, exc)
    return contexto


def _regra_bate(regra, contexto):
    """Retorna True se TODAS as condições da regra forem satisfeitas."""
    condicoes = regra.condicoes or []
    if not condicoes:
        return False
    return all(_condicao_bate(c, contexto) for c in condicoes)


def _condicao_bate(condicao, contexto):
    """Avalia uma condição individual delegando ao tipo registrado."""
    from apps.comercial.crm.services import automacao_condicoes

    tipo_slug = condicao.get('tipo', '')
    operador = condicao.get('operador', 'igual')
    valor = condicao.get('valor')
    campo = condicao.get('campo', '')

    tipo = automacao_condicoes.tipo_por_slug(tipo_slug)
    if tipo is None:
        logger.warning("[Automacao Pipeline] Tipo de condicao desconhecido: %s", tipo_slug)
        return False

    try:
        return tipo.avaliar(operador, valor, campo, contexto)
    except Exception as exc:
        logger.warning("[Automacao Pipeline] Falha ao avaliar %s: %s", tipo_slug, exc)
        return False


# ============================================================================
# MOVIMENTAÇÃO
# ============================================================================

def _mover_por_regra(oportunidade, estagio_destino, regra):
    """
    Move a oportunidade pro estágio destino, registra histórico, atualiza métricas
    da regra e loga auditoria.

    Respeita gate de `campos_obrigatorios` do estagio destino: se faltarem
    campos, nao move e loga warning (evita lead avancar incompleto).
    """
    from apps.comercial.crm.models import HistoricoPipelineEstagio
    from apps.comercial.crm.services.requisitos_estagio import campos_faltando

    # Gate: campos obrigatorios do estagio destino
    faltantes = campos_faltando(oportunidade, estagio_destino)
    if faltantes:
        logger.info(
            "[_mover_por_regra] oport=%s nao move pra '%s' — campos faltando: %s",
            oportunidade.pk, estagio_destino.nome, [c for c, _ in faltantes]
        )
        return  # silencioso: regra pode bater de novo quando lead completar

    agora = timezone.now()
    horas = (agora - oportunidade.data_entrada_estagio).total_seconds() / 3600

    estagio_anterior = oportunidade.estagio
    regra_nome = regra.nome

    HistoricoPipelineEstagio.objects.create(
        tenant=oportunidade.tenant,
        oportunidade=oportunidade,
        estagio_anterior=estagio_anterior,
        estagio_novo=estagio_destino,
        motivo=f'Regra automática: {regra_nome}',
        tempo_no_estagio_horas=round(horas, 2),
    )

    campos_update = ['estagio', 'data_entrada_estagio', 'probabilidade', 'data_atualizacao']

    oportunidade.estagio = estagio_destino
    oportunidade.data_entrada_estagio = agora
    oportunidade.probabilidade = estagio_destino.probabilidade_padrao

    if estagio_destino.is_final_ganho and not oportunidade.data_fechamento_real:
        oportunidade.data_fechamento_real = agora
        campos_update.append('data_fechamento_real')

    # Flag pra evitar loop infinito nos signals
    oportunidade._skip_rules_evaluation = True
    oportunidade.save(update_fields=campos_update)

    # Métricas da regra
    try:
        regra.total_disparos = (regra.total_disparos or 0) + 1
        regra.ultima_execucao = agora
        regra.save(update_fields=['total_disparos', 'ultima_execucao'])
    except Exception as exc:
        logger.warning("[Automacao Pipeline] Falha ao atualizar metricas da regra %s: %s", regra.pk, exc)

    logger.info(
        "[Automacao Pipeline] Oportunidade %s movida '%s' -> '%s' (regra: %s)",
        oportunidade.pk,
        estagio_anterior.nome if estagio_anterior else '—',
        estagio_destino.nome,
        regra_nome,
    )

    try:
        from apps.sistema.utils import registrar_acao
        registrar_acao(
            'crm', 'mover_regra', 'oportunidade', oportunidade.pk,
            f"Movida para '{estagio_destino.nome}' pela regra '{regra_nome}'",
        )
    except Exception:
        pass


# ============================================================================
# AÇÕES
# ============================================================================

def _avaliar_e_executar_acoes(oportunidade):
    """Avalia regras sem estágio destino e executa suas ações se condições batem."""
    from apps.comercial.crm.models import RegraPipelineEstagio

    tenant = oportunidade.tenant
    if tenant is None:
        return

    contexto = _construir_contexto(oportunidade)

    regras_acao = (
        RegraPipelineEstagio.all_tenants
        .filter(tenant=tenant, ativo=True, estagio__isnull=True)
        .order_by('prioridade')
    )

    for regra in regras_acao:
        if not (regra.acoes or []):
            continue
        if _regra_bate(regra, contexto):
            _executar_acoes_regra(oportunidade, regra)


def _executar_acoes_regra(oportunidade, regra):
    """Executa a lista de ações de uma regra e atualiza métricas.

    Contrato das actions: retornar True se efetivou (rodou de fato), False
    se pulou por idempotência. None = compatibilidade legada (conta como efetivo).
    """
    acoes = regra.acoes or []
    houve_acao_efetiva = False
    for acao in acoes:
        tipo = acao.get('tipo')
        config = acao.get('config') or {}
        executor = _EXECUTORES_ACAO.get(tipo)
        if executor is None:
            logger.warning("[Automacao Pipeline] Tipo de ação desconhecido: %s", tipo)
            continue
        try:
            ret = executor(oportunidade, config)
            # Action retornou False => pulou idempotente; True/None => efetivou
            if ret is not False:
                houve_acao_efetiva = True
        except Exception as exc:
            logger.warning("[Automacao Pipeline] Falha ao executar ação %s: %s", tipo, exc)

    try:
        update_fields = ['total_disparos', 'ultima_execucao']
        regra.total_disparos = (regra.total_disparos or 0) + 1
        regra.ultima_execucao = timezone.now()
        if houve_acao_efetiva:
            regra.total_acoes_efetivas = (regra.total_acoes_efetivas or 0) + 1
            update_fields.append('total_acoes_efetivas')
        regra.save(update_fields=update_fields)
    except Exception as exc:
        logger.warning("[Automacao Pipeline] Falha ao atualizar métricas da regra %s: %s", regra.pk, exc)


def _acao_criar_venda(oportunidade, config):
    """Retorna True se criou Venda nova, False se ja existia (idempotente)."""
    from apps.comercial.crm.models import Venda
    tenant = oportunidade.tenant
    if Venda.all_tenants.filter(tenant=tenant, oportunidade=oportunidade).exists():
        return False
    Venda.all_tenants.create(
        tenant=tenant,
        lead=oportunidade.lead,
        oportunidade=oportunidade,
        plano=getattr(oportunidade, 'plano_interesse', None),
        valor=oportunidade.valor_estimado,
        status=Venda.STATUS_PENDENTE_ERP,
    )
    logger.info("[Automacao Pipeline] Venda criada para oportunidade %s", oportunidade.pk)
    return True


def _acao_atribuir_agente(oportunidade, config):
    """Atribui a oportunidade e a conversa vinculada a um usuario.

    Nao rouba lead de outra vendedora: se a oportunidade ja tem responsavel, pula
    (por isso a reivindicacao so acontece uma vez, no primeiro match). Quando
    reivindica, a conversa vinculada e atribuida a este usuario MESMO que a fila
    ja tenha auto-distribuido para outro agente: a regra de roteamento por cidade
    tem prioridade sobre a distribuicao automatica da fila.
    """
    from apps.comercial.crm.models import OportunidadeVenda
    from apps.inbox.models import Conversa

    user_id = config.get('user_id')
    if not user_id:
        logger.warning("[Automacao Pipeline] atribuir_agente sem user_id (oport=%s)", oportunidade.pk)
        return False

    if oportunidade.responsavel_id:
        return False  # ja tem responsavel — idempotente

    OportunidadeVenda.all_tenants.filter(pk=oportunidade.pk).update(responsavel_id=user_id)
    n_conv = Conversa.all_tenants.filter(
        tenant=oportunidade.tenant,
        oportunidade_id=oportunidade.pk,
    ).update(agente_id=user_id)

    logger.info(
        "[Automacao Pipeline] Atribuido user=%s a oport=%s (+ %s conversas)",
        user_id, oportunidade.pk, n_conv,
    )
    return True


def _acao_gerar_contrato_hubsoft(oportunidade, config):
    """Gera contrato no HubSoft + anexa documentos + aceita — atomico.

    Trigger tipico: condicao `imagem_status todas_iguais documentos_validos`.
    Reusa HubsoftService + a logica de anexar/aceitar ja em contrato_service.

    Configuracao de qual modelo/empresa usar:
    - IntegracaoAPI.configuracoes_extras['hubsoft']['id_contrato_modelo'] (default 236 = Nuvyon)
    - IntegracaoAPI.configuracoes_extras['hubsoft']['id_empresa_padrao'] (default 74 = Nuvyon matriz)

    Idempotente: se ja tem id_cliente_servico_contrato no servico, pula criacao
    e tenta direto anexar+aceitar.
    """
    from apps.comercial.cadastro.services.contrato_service import (
        _coletar_arquivos_lead, _obter_hubsoft_service,
    )
    from apps.integracoes.services.hubsoft import HubsoftServiceError
    from apps.integracoes.services.contrato_tracking import (
        iniciar_tentativa, marcar_sucesso, marcar_falha, marcar_pulado_idempotente,
    )

    lead = oportunidade.lead
    if not lead:
        logger.warning("[gerar_contrato] oport=%s sem lead vinculado", oportunidade.pk)
        return False

    # Trava defensiva: score externo precisa estar aprovado pra gerar contrato.
    # Protege fluxos que pulam a engine (retentativa manual, signals, etc).
    score = getattr(lead, 'score_status', 'nao_consultado')
    if score != 'aprovado':
        logger.info("[gerar_contrato] lead=%s bloqueado por score=%s (esperado: aprovado)", lead.pk, score)
        return False

    if getattr(lead, 'contrato_aceito', False) and getattr(lead, 'anexos_contrato_enviados', False):
        logger.info("[gerar_contrato] lead=%s ja tem contrato aceito + anexos enviados, pula", lead.pk)
        return False  # idempotente: tudo ja feito

    cliente_hubsoft = lead.clientes_hubsoft.first()
    if not cliente_hubsoft:
        logger.warning("[gerar_contrato] lead=%s ainda nao virou cliente HubSoft", lead.pk)
        return False

    servico = cliente_hubsoft.servicos.first()
    if not servico:
        logger.warning("[gerar_contrato] cliente HubSoft %s sem servicos", cliente_hubsoft.pk)
        return False

    try:
        hubsoft_service = _obter_hubsoft_service(tenant=lead.tenant)
    except Exception as exc:
        logger.error("[gerar_contrato] sem HubsoftService: %s", exc)
        return False

    # Inicia tracking da tentativa (persiste resultado no fim)
    tentativa, _t0 = iniciar_tentativa(oportunidade, 'gerar', hubsoft_service)

    extras = (hubsoft_service.integracao.configuracoes_extras or {}).get('hubsoft', {})
    id_contrato_modelo = config.get('id_contrato_modelo') or extras.get('id_contrato_modelo')
    id_empresa = config.get('id_empresa') or extras.get('id_empresa_padrao')
    if not id_contrato_modelo or not id_empresa:
        logger.error(
            "[gerar_contrato] config ausente: id_contrato_modelo=%s id_empresa=%s. "
            "Defina em IntegracaoAPI.configuracoes_extras['hubsoft'] ou na config da acao.",
            id_contrato_modelo, id_empresa,
        )
        return False

    # 1) Criar contrato (se ainda nao tem)
    id_contrato = servico.id_cliente_servico_contrato
    if not id_contrato:
        try:
            resp = hubsoft_service.criar_contrato(
                id_cliente_servico=servico.id_cliente_servico,
                id_contrato_modelo=int(id_contrato_modelo),
                id_empresa=int(id_empresa),
                autorizacao_nome=lead.nome_razaosocial or '',
                autorizacao_cpf=lead.cpf_cnpj or '',
                informacao_adicional='Contrato gerado via automacao Hubtrix (regra pipeline).',
                lead=lead,
            )
            id_contrato = (
                (resp.get('data') or {}).get('id_cliente_servico_contrato')
                or resp.get('id_cliente_servico_contrato')
                or (resp.get('contrato') or {}).get('id_cliente_servico_contrato')
            )
            if not id_contrato:
                logger.error("[gerar_contrato] HubSoft criou mas nao retornou id. Resp: %s", resp)
                marcar_falha(tentativa, _t0, Exception('HubSoft criou mas nao retornou id_contrato'), etapa='criar')
                return False
            servico.id_cliente_servico_contrato = int(id_contrato)
            servico.save(update_fields=['id_cliente_servico_contrato'])
            logger.info("[gerar_contrato] criado contrato %s pro servico %s (lead %s)",
                        id_contrato, servico.id_cliente_servico, lead.pk)
        except HubsoftServiceError as exc:
            logger.error("[gerar_contrato] criar_contrato falhou (lead=%s): %s", lead.pk, exc)
            marcar_falha(tentativa, _t0, exc, etapa='criar')
            return False

    # 2) Anexar arquivos
    arquivos_anexados = []
    erro_anexar = None
    if not lead.anexos_contrato_enviados:
        try:
            arquivos = _coletar_arquivos_lead(lead)
            if arquivos:
                hubsoft_service.anexar_arquivos_contrato(id_contrato, arquivos, lead=lead)
                lead.anexos_contrato_enviados = True
                lead.save(update_fields=['anexos_contrato_enviados'])
                arquivos_anexados = [
                    {'nome': a[0], 'tamanho_bytes': len(a[1]) if a[1] else 0, 'mime': a[2] if len(a) > 2 else ''}
                    for a in arquivos
                ]
                logger.info("[gerar_contrato] %d arquivo(s) anexado(s) ao contrato %s (lead %s)",
                            len(arquivos), id_contrato, lead.pk)
            else:
                logger.warning("[gerar_contrato] lead=%s sem arquivos pra anexar", lead.pk)
        except HubsoftServiceError as exc:
            logger.error("[gerar_contrato] anexar_arquivos_contrato falhou (lead=%s): %s", lead.pk, exc)
            erro_anexar = exc
            # nao para aqui — ainda tenta aceitar

    # 3) Aceitar contrato
    erro_aceitar = None
    if not lead.contrato_aceito:
        try:
            hubsoft_service.aceitar_contrato(
                id_contrato,
                observacao='Contrato aceito automaticamente apos validacao de documentos.',
                lead=lead,
            )
            lead.contrato_aceito = True
            lead.data_aceite_contrato = timezone.now()
            lead.save(update_fields=['contrato_aceito', 'data_aceite_contrato'])
            logger.info("[gerar_contrato] contrato %s aceito (lead %s)", id_contrato, lead.pk)
        except HubsoftServiceError as exc:
            logger.error("[gerar_contrato] aceitar_contrato falhou (lead=%s): %s", lead.pk, exc)
            erro_aceitar = exc

    # Finalizar tentativa
    tentativa.anexos_enviados = arquivos_anexados
    if erro_aceitar:
        marcar_falha(tentativa, _t0, erro_aceitar, etapa='aceitar')
    elif erro_anexar:
        # Aceitou mas o anexo falhou — sucesso parcial (categorizamos como falha pra ficar visivel)
        marcar_falha(tentativa, _t0, erro_anexar, etapa='anexar')
    else:
        marcar_sucesso(tentativa, _t0, resposta={'id_cliente_servico_contrato': id_contrato}, etapa='completo', id_contrato=id_contrato)

    # Chegou aqui: criou/anexou/aceitou algo efetivamente
    return True


def _extrair_id_contrato(resp, id_cliente_servico):
    """Extrai id_cliente_servico_contrato da resposta de consultar_cliente
    (incluir_contrato=True), casando pelo id_cliente_servico do servico.
    Fallback: primeiro contrato de qualquer servico do cliente."""
    clientes = (resp or {}).get('clientes') or []
    for cli in clientes:
        for sv in (cli.get('servicos') or []):
            if str(sv.get('id_cliente_servico')) == str(id_cliente_servico):
                for ctr in (sv.get('contratos') or []):
                    cid = ctr.get('id_cliente_servico_contrato')
                    if cid:
                        return cid
    for cli in clientes:
        for sv in (cli.get('servicos') or []):
            for ctr in (sv.get('contratos') or []):
                cid = ctr.get('id_cliente_servico_contrato')
                if cid:
                    return cid
    return None


def _acao_assinar_contrato_hubsoft(oportunidade, config):
    """Assina (aceita) o contrato JA EXISTENTE do lead no HubSoft.

    Diferente de gerar_contrato_hubsoft: NAO cria o contrato (no Nuvyon ele e
    auto-criado pelo HubSoft junto com o cliente/servico — adicionar_contrato
    devolve "ja existe"). Resolve o id via consultar_cliente(incluir_contrato=True)
    e chama aceitar_contrato.

    Trigger tipico: condicao `imagem_status todas_iguais documentos_validos`.

    config opcional:
    - ativar_servico_apos_aceite ("sim"): apos o aceite, chama ativar_servico pra
      tentar mover o servico de "aguardando assinatura" (aceitar sozinho pode nao
      mover o status do servico — ver lead 544). Use pra testar se destrava a OS.

    Idempotente: se lead.contrato_aceito ja True, pula. Retorna True se aceitou.
    """
    from apps.comercial.cadastro.services.contrato_service import _obter_hubsoft_service
    from apps.integracoes.services.hubsoft import HubsoftServiceError
    from apps.integracoes.services.contrato_tracking import (
        iniciar_tentativa, marcar_sucesso, marcar_falha,
    )

    lead = oportunidade.lead
    if not lead:
        logger.warning("[assinar_contrato] oport=%s sem lead", oportunidade.pk)
        return False

    # Trava defensiva: score externo precisa estar aprovado pra assinar.
    score = getattr(lead, 'score_status', 'nao_consultado')
    if score != 'aprovado':
        logger.info("[assinar_contrato] lead=%s bloqueado por score=%s (esperado: aprovado)", lead.pk, score)
        return False

    if getattr(lead, 'contrato_aceito', False):
        logger.info("[assinar_contrato] lead=%s ja tem contrato aceito, pula", lead.pk)
        return False

    cliente_hubsoft = lead.clientes_hubsoft.first()
    if not cliente_hubsoft:
        logger.info("[assinar_contrato] lead=%s ainda nao virou cliente HubSoft", lead.pk)
        return False
    servico = cliente_hubsoft.servicos.first()
    if not servico:
        logger.info("[assinar_contrato] cliente %s sem servicos", cliente_hubsoft.pk)
        return False

    try:
        hubsoft_service = _obter_hubsoft_service(tenant=lead.tenant)
    except Exception as exc:
        logger.error("[assinar_contrato] sem HubsoftService: %s", exc)
        return False

    tentativa, _t0 = iniciar_tentativa(oportunidade, 'assinar', hubsoft_service)

    # 1) Resolve o id do contrato (ja salvo, ou via consulta com incluir_contrato)
    id_contrato = servico.id_cliente_servico_contrato
    if not id_contrato:
        try:
            resp = hubsoft_service.consultar_cliente(
                lead.cpf_cnpj, lead=lead, incluir_contrato=True,
            )
        except HubsoftServiceError as exc:
            logger.error("[assinar_contrato] consultar_cliente falhou (lead=%s): %s", lead.pk, exc)
            marcar_falha(tentativa, _t0, exc, etapa='criar')  # consulta antes de aceitar
            return False
        id_contrato = _extrair_id_contrato(resp, servico.id_cliente_servico)
        if id_contrato:
            servico.id_cliente_servico_contrato = int(id_contrato)
            servico.save(update_fields=['id_cliente_servico_contrato'])
    if not id_contrato:
        logger.warning("[assinar_contrato] lead=%s: contrato nao encontrado na consulta", lead.pk)
        marcar_falha(tentativa, _t0, Exception('Contrato nao encontrado na consulta HubSoft'), etapa='criar')
        return False

    # 2) Aceita o contrato
    try:
        hubsoft_service.aceitar_contrato(
            int(id_contrato),
            observacao='Contrato aceito automaticamente apos validacao de documentos.',
            lead=lead,
        )
    except HubsoftServiceError as exc:
        logger.error("[assinar_contrato] aceitar_contrato falhou (lead=%s, contrato=%s): %s",
                     lead.pk, id_contrato, exc)
        marcar_falha(tentativa, _t0, exc, etapa='aceitar')
        return False

    lead.contrato_aceito = True
    lead.data_aceite_contrato = timezone.now()
    lead.save(update_fields=['contrato_aceito', 'data_aceite_contrato'])
    logger.info("[assinar_contrato] contrato %s aceito (lead %s)", id_contrato, lead.pk)

    marcar_sucesso(tentativa, _t0, resposta={'id_cliente_servico_contrato': id_contrato},
                   etapa='aceitar', id_contrato=id_contrato)

    # 3) Opcional: ativar servico (aceite sozinho pode nao mover o status — testar)
    if str((config or {}).get('ativar_servico_apos_aceite', '')).lower() in ('sim', 'true', '1', 'on'):
        try:
            hubsoft_service.ativar_servico(int(servico.id_cliente_servico))
            logger.info("[assinar_contrato] servico %s ativado (lead %s)",
                        servico.id_cliente_servico, lead.pk)
        except HubsoftServiceError as exc:
            logger.warning("[assinar_contrato] ativar_servico falhou (lead=%s): %s", lead.pk, exc)

    return True


def _acao_enviar_venda_whatsapp(oportunidade, config):
    """Manda resumo da venda + documentos por WhatsApp.

    Config:
      - telefone_destino: numero WhatsApp (formato 5553981521653, so digitos com DDI+DDD)

    Idempotente via `lead.dados_custom['venda_whatsapp_enviada']` (gerenciada no service).
    """
    from apps.comercial.leads.services_whatsapp_venda import enviar_venda_whatsapp

    lead = oportunidade.lead
    if not lead:
        logger.warning("[enviar_venda_whatsapp] sem lead (oport=%s)", oportunidade.pk)
        return False

    telefone = (config or {}).get('telefone_destino', '').strip()
    if not telefone:
        logger.warning("[enviar_venda_whatsapp] telefone_destino vazio (lead=%s)", lead.pk)
        return False

    try:
        result = enviar_venda_whatsapp(lead, telefone, oportunidade=oportunidade)
        logger.info(
            "[Automacao Pipeline] Venda WhatsApp lead=%s telefone=%s ok=%s docs=%s motivo=%s",
            lead.pk, telefone, result.get('ok'),
            result.get('docs_enviados'), result.get('motivo'),
        )
        # Idempotente: motivo comeca com 'ja enviado' => nao efetivou
        if (result.get('motivo') or '').startswith('ja enviado'):
            return False
        return bool(result.get('ok'))
    except Exception as exc:
        logger.error("[enviar_venda_whatsapp] falha (lead=%s): %s", lead.pk, exc)
        return False


_EXECUTORES_ACAO = {
    'criar_venda': _acao_criar_venda,
    'atribuir_agente': _acao_atribuir_agente,
    'gerar_contrato_hubsoft': _acao_gerar_contrato_hubsoft,
    'assinar_contrato_hubsoft': _acao_assinar_contrato_hubsoft,
    'enviar_venda_whatsapp': _acao_enviar_venda_whatsapp,
}


def processar_seguro(lead_id=None, oportunidade=None):
    """Wrapper que isola falhas do engine pra não derrubar signals."""
    try:
        if oportunidade is not None:
            processar_oportunidade(oportunidade)
        elif lead_id is not None:
            processar_lead(lead_id)
    except Exception as exc:
        logger.error("[Automacao Pipeline] Falha ao avaliar regras: %s", exc)
