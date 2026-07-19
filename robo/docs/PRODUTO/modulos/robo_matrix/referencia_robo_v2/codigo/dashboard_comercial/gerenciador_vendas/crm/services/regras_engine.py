"""
Motor de regras configuráveis para movimentação automática de oportunidades
no pipeline CRM.

Lógica:
  - Condições dentro da mesma regra: AND (todas devem bater)
  - Regras dentro do mesmo estágio: OR (qualquer uma basta)
  - Estágios avaliados na ordem (campo `ordem`): primeiro match ganha
  - Estágios finais (is_final_ganho / is_final_perdido) não são reavaliados
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def processar_lead(lead_id):
    """
    Ponto de entrada chamado pelos signals.
    Avalia regras e move a oportunidade se necessário.
    """
    from crm.models import OportunidadeVenda

    # Só a oportunidade de AQUISIÇÃO é movida por estas regras. As de
    # pós-venda (novo serviço/upgrade) têm pipeline próprio, movido pelos
    # signals de NewService/UpgradePlano (crm/services/posvenda_sync.py).
    oportunidade = OportunidadeVenda.objects.select_related(
        'estagio', 'lead',
    ).filter(lead_id=lead_id, tipo='aquisicao', ativo=True).first()
    if not oportunidade:
        return

    # Não reavaliar oportunidades em estágio final
    if oportunidade.estagio.is_final_ganho or oportunidade.estagio.is_final_perdido:
        return

    resultado = avaliar_regras_para_lead(oportunidade)
    if resultado is None:
        return

    estagio_destino, regra_nome, condicoes = resultado

    if oportunidade.estagio_id == estagio_destino.pk:
        return

    mover_oportunidade_por_regra(oportunidade, estagio_destino, regra_nome, condicoes)


def avaliar_regras_para_lead(oportunidade):
    """
    Avalia todas as regras ativas contra o estado atual do lead.
    Retorna (estagio_destino, regra_nome) ou None se nenhuma regra bateu.
    """
    from crm.models import PipelineEstagio, RegraPipelineEstagio

    lead = oportunidade.lead
    if not lead:
        return None

    # Pré-carregar contexto (minimizar queries)
    contexto = _construir_contexto(lead, oportunidade)

    # Carregar estágios com regras ativas, do mais avançado para o menos
    # (ordem decrescente: Cliente Ativo antes de Em Qualificação)
    # Isso garante que um lead com serviço habilitado vá para Cliente Ativo
    # e não seja capturado por uma regra genérica de Em Qualificação.
    # Só estágios do pipeline de AQUISIÇÃO — as regras não movem pra
    # estágios pós-venda (esses são geridos pelos signals).
    estagios_com_regras = (
        PipelineEstagio.objects
        .filter(ativo=True, pipeline_tipo='aquisicao', regras__ativo=True)
        .distinct()
        .order_by('-ordem')
        .prefetch_related('regras')
    )

    for estagio in estagios_com_regras:
        regras = estagio.regras.filter(ativo=True).order_by('prioridade')
        for regra in regras:
            if _avaliar_regra(regra, contexto):
                return (estagio, regra.nome, regra.condicoes)

    return None


def _construir_contexto(lead, oportunidade):
    """
    Pré-carrega todos os dados necessários para avaliação de regras.
    """
    from vendas_web.models import HistoricoContato, ImagemLeadProspecto
    from integracoes.models import ServicoClienteHubsoft

    # Status de todos os históricos do lead
    historico_statuses = set(
        HistoricoContato.objects
        .filter(lead_id=lead.pk)
        .values_list('status', flat=True)
    )

    # Verificar se tem conversão de venda
    tem_conversao_venda = HistoricoContato.objects.filter(
        lead_id=lead.pk,
        converteu_venda=True,
    ).exists()

    # Status de serviços Hubsoft via ClienteHubsoft
    servico_statuses = set(
        ServicoClienteHubsoft.objects
        .filter(cliente__lead_id=lead.pk)
        .values_list('status_prefixo', flat=True)
    )

    # Tags da oportunidade
    tags = set(
        oportunidade.tags.values_list('nome', flat=True)
    )

    # Status das imagens/documentos do lead
    imagens_statuses = list(
        ImagemLeadProspecto.objects
        .filter(lead_id=lead.pk)
        .values_list('status_validacao', flat=True)
    )

    return {
        'historico_statuses': historico_statuses,
        'lead': lead,
        'servico_statuses': servico_statuses,
        'tags': tags,
        'tem_conversao_venda': tem_conversao_venda,
        'imagens_statuses': imagens_statuses,
    }


def _avaliar_regra(regra, contexto):
    """
    Avalia uma regra: TODAS as condições devem ser verdadeiras (AND).
    """
    condicoes = regra.condicoes
    if not condicoes:
        return False

    return all(_avaliar_condicao(c, contexto) for c in condicoes)


def _avaliar_condicao(condicao, contexto):
    """
    Avalia uma condição individual contra o contexto pré-carregado.
    """
    tipo = condicao.get('tipo', '')
    operador = condicao.get('operador', 'igual')
    valor = condicao.get('valor')
    campo = condicao.get('campo', '')

    if tipo == 'historico_status':
        return _comparar_conjunto(contexto['historico_statuses'], operador, valor)

    elif tipo == 'lead_status_api':
        status_atual = getattr(contexto['lead'], 'status_api', '') or ''
        return _comparar_valor(status_atual, operador, valor)

    elif tipo == 'lead_campo':
        valor_campo = getattr(contexto['lead'], campo, None)
        if isinstance(valor_campo, bool) or isinstance(valor, bool):
            return _comparar_bool(valor_campo, operador, valor)
        return _comparar_valor(valor_campo, operador, valor)

    elif tipo == 'servico_status':
        return _comparar_conjunto(contexto['servico_statuses'], operador, valor)

    elif tipo == 'tag':
        return _comparar_conjunto(contexto['tags'], operador, valor)

    elif tipo == 'converteu_venda':
        tem = contexto['tem_conversao_venda']
        if operador in ('igual', 'existe'):
            return tem == bool(valor)
        elif operador in ('diferente', 'nao_existe'):
            return tem != bool(valor)

    elif tipo == 'imagem_status':
        # valor pode ser: 'pendente', 'documentos_validos', 'documentos_rejeitados'
        imagens = contexto.get('imagens_statuses', [])
        if operador == 'igual':
            # Existe pelo menos uma imagem com esse status
            return valor in imagens
        elif operador == 'diferente':
            return valor not in imagens
        elif operador == 'todas_iguais':
            # TODAS as imagens têm esse status (e existe pelo menos uma)
            return len(imagens) > 0 and all(s == valor for s in imagens)
        elif operador == 'nenhuma_com':
            # Nenhuma imagem tem esse status
            return valor not in imagens
        elif operador == 'existe':
            return len(imagens) > 0
        elif operador == 'nao_existe':
            return len(imagens) == 0

    logger.warning(f"[CRM Engine] Tipo de condição desconhecido: {tipo}")
    return False


def _comparar_conjunto(conjunto, operador, valor):
    """Compara se um valor está ou não em um conjunto."""
    if operador == 'igual':
        return valor in conjunto
    elif operador == 'diferente':
        return valor not in conjunto
    elif operador == 'existe':
        return len(conjunto) > 0
    elif operador == 'nao_existe':
        return len(conjunto) == 0
    return False


def _comparar_valor(valor_atual, operador, valor_esperado):
    """Compara um valor escalar."""
    if operador == 'igual':
        return str(valor_atual).strip() == str(valor_esperado).strip()
    elif operador == 'diferente':
        return str(valor_atual).strip() != str(valor_esperado).strip()
    elif operador == 'existe':
        return bool(valor_atual)
    elif operador == 'nao_existe':
        return not bool(valor_atual)
    return False


def _comparar_bool(valor_campo, operador, valor_esperado):
    """Compara valores booleanos."""
    campo_bool = bool(valor_campo)
    esperado_bool = bool(valor_esperado)
    if operador in ('igual', 'existe'):
        return campo_bool == esperado_bool
    elif operador in ('diferente', 'nao_existe'):
        return campo_bool != esperado_bool
    return False


def _calcular_data_entrada(lead_id, condicoes):
    """
    Calcula quando o lead realmente passou a atender as condições da regra.
    Retorna a data mais recente entre todas as condições (AND = a última a ser satisfeita).
    """
    from vendas_web.models import HistoricoContato
    from integracoes.models import ServicoClienteHubsoft
    from vendas_web.models import LeadProspecto

    datas = []

    for cond in condicoes:
        tipo = cond.get('tipo', '')
        valor = cond.get('valor')
        campo = cond.get('campo', '')

        if tipo == 'historico_status':
            # Data do primeiro histórico com esse status
            h = (HistoricoContato.objects
                 .filter(lead_id=lead_id, status=valor)
                 .order_by('data_hora_contato')
                 .values_list('data_hora_contato', flat=True)
                 .first())
            if h:
                datas.append(h)

        elif tipo == 'lead_status_api':
            # Usa data_atualizacao do lead (melhor aproximação)
            try:
                lead = LeadProspecto.objects.get(pk=lead_id)
                datas.append(lead.data_atualizacao or lead.data_cadastro)
            except LeadProspecto.DoesNotExist:
                pass

        elif tipo == 'lead_campo':
            # Campos booleanos têm datas correspondentes
            mapa_datas = {
                'documentacao_validada': 'data_documentacao_validada',
                'documentacao_completa': 'data_documentacao_completa',
                'contrato_aceito': 'data_aceite_contrato',
            }
            try:
                lead = LeadProspecto.objects.get(pk=lead_id)
                campo_data = mapa_datas.get(campo)
                if campo_data:
                    dt = getattr(lead, campo_data, None)
                    if dt:
                        datas.append(dt)
                    else:
                        datas.append(lead.data_atualizacao or lead.data_cadastro)
            except LeadProspecto.DoesNotExist:
                pass

        elif tipo == 'servico_status':
            # Data real do serviço: preferir data_habilitacao, senão data_cadastro_servico, senão data_sync
            s = (ServicoClienteHubsoft.objects
                 .filter(cliente__lead_id=lead_id, status_prefixo=valor)
                 .order_by('data_sync')
                 .first())
            if s:
                dt = s.data_habilitacao or s.data_sync
                if dt:
                    datas.append(dt)

        elif tipo == 'converteu_venda':
            h = (HistoricoContato.objects
                 .filter(lead_id=lead_id, converteu_venda=True)
                 .order_by('data_hora_contato')
                 .values_list('data_hora_contato', flat=True)
                 .first())
            if h:
                datas.append(h)

    if not datas:
        return None

    # AND: todas as condições devem ser verdadeiras.
    # A data de entrada é quando a ÚLTIMA condição foi satisfeita.
    return max(datas)


def mover_oportunidade_por_regra(oportunidade, estagio_destino, regra_nome, condicoes=None):
    """
    Move oportunidade para novo estágio com registro no histórico.
    Calcula a data de entrada real com base em quando as condições foram atendidas.
    """
    from crm.models import HistoricoPipelineEstagio

    agora = timezone.now()
    horas = (agora - oportunidade.data_entrada_estagio).total_seconds() / 3600

    # Calcular data real de entrada no estágio
    data_entrada = agora
    if condicoes:
        data_calculada = _calcular_data_entrada(oportunidade.lead_id, condicoes)
        if data_calculada and data_calculada < agora:
            data_entrada = data_calculada

    HistoricoPipelineEstagio.objects.create(
        oportunidade=oportunidade,
        estagio_anterior=oportunidade.estagio,
        estagio_novo=estagio_destino,
        motivo=f'Regra automática: {regra_nome}',
        tempo_no_estagio_horas=round(horas, 2),
    )

    campos_update = ['estagio', 'data_entrada_estagio', 'data_atualizacao']

    oportunidade.estagio = estagio_destino
    oportunidade.data_entrada_estagio = data_entrada
    oportunidade.probabilidade = estagio_destino.probabilidade_padrao

    if estagio_destino.is_final_ganho and not oportunidade.data_fechamento_real:
        oportunidade.data_fechamento_real = agora
        campos_update.append('data_fechamento_real')

    campos_update.append('probabilidade')

    # Flag para evitar loop infinito nos signals
    oportunidade._skip_rules_evaluation = True
    oportunidade.save(update_fields=campos_update)

    logger.info(
        f"[CRM Engine] Oportunidade {oportunidade.pk} movida para "
        f"'{estagio_destino.nome}' — Regra: {regra_nome}"
    )

    # Disparar webhook N8N se configurado
    _disparar_webhook_mudanca_estagio(oportunidade, estagio_destino, regra_nome)


def _disparar_webhook_mudanca_estagio(oportunidade, estagio_destino, regra_nome):
    """Dispara webhook N8N de mudança de estágio, se configurado."""
    try:
        from crm.models import ConfiguracaoCRM
        config = ConfiguracaoCRM.get_config()
        url = config.webhook_n8n_mudanca_estagio
        if not url:
            return

        import requests
        payload = {
            'oportunidade_id': oportunidade.pk,
            'lead_nome': oportunidade.lead.nome_razaosocial if oportunidade.lead else '',
            'lead_telefone': oportunidade.lead.telefone if oportunidade.lead else '',
            'estagio_novo': estagio_destino.nome,
            'regra': regra_nome,
            'responsavel': oportunidade.responsavel.get_full_name() if oportunidade.responsavel else '',
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"[CRM Engine] Erro ao disparar webhook: {e}")
