"""Orquestrações de contrato HubSoft pra engine de automação (Fase 1 da migração
do funil). Portadas de `crm.services.automacao_pipeline._acao_gerar_contrato_hubsoft`
e `_acao_assinar_contrato_hubsoft` — o motor novo é **autossuficiente**: reusa os
helpers de domínio de `cadastro`/`integracoes` (que NÃO são o motor antigo), mas não
importa nada de `automacao_pipeline`.

⚠️ Outbound REAL no ERP (cria/aceita contrato). Seletor de credencial: `integ_id`
escolhe a conta HubSoft (vazio = 1ª ativa). Tudo dormente até a Fase 3.
"""
from django.utils import timezone


def _extrair_id_contrato(resp, id_cliente_servico):
    """Extrai id_cliente_servico_contrato da resposta de consultar_cliente
    (incluir_contrato=True), casando pelo id_cliente_servico do serviço.
    Fallback: primeiro contrato de qualquer serviço do cliente."""
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


def gerar_contrato(tenant, *, oportunidade, id_contrato_modelo=None, id_empresa=None, integ_id=None):
    """Gera contrato no HubSoft (criar → anexar arquivos → aceitar), com tracking.
    Idempotente (pula se já aceito + anexado). Devolve `(feito: bool, info: dict)`:
    - feito=True quando criou/anexou/aceitou algo; info={'motivo','id_contrato','arquivos'}
    - feito=False + info={'motivo': <skip>} pros pulos ('sem_lead','score_nao_aprovado',
      'ja_feito','sem_cliente_hubsoft','sem_servico','sem_config').
    Levanta `HubsoftServiceError` se criar/aceitar falhar (o nó → saída erro).

    `id_contrato_modelo`/`id_empresa` vazios caem pro `configuracoes_extras['hubsoft']`
    da integração (id_contrato_modelo / id_empresa_padrao)."""
    from apps.comercial.cadastro.services.contrato_service import _coletar_arquivos_lead
    from apps.integracoes.services.hubsoft import HubsoftServiceError
    from apps.integracoes.services.contrato_tracking import (
        iniciar_tentativa, marcar_sucesso, marcar_falha,
    )
    from .hubsoft import hubsoft_do_tenant

    if oportunidade is None:
        raise ValueError('Sem oportunidade.')
    lead = oportunidade.lead
    if not lead:
        return False, {'motivo': 'sem_lead'}
    if getattr(lead, 'score_status', 'nao_consultado') != 'aprovado':
        return False, {'motivo': 'score_nao_aprovado'}
    if getattr(lead, 'contrato_aceito', False) and getattr(lead, 'anexos_contrato_enviados', False):
        return False, {'motivo': 'ja_feito'}
    cliente_hubsoft = lead.clientes_hubsoft.first()
    if not cliente_hubsoft:
        return False, {'motivo': 'sem_cliente_hubsoft'}
    servico = cliente_hubsoft.servicos.first()
    if not servico:
        return False, {'motivo': 'sem_servico'}

    hubsoft_service = hubsoft_do_tenant(tenant, integ_id)
    if hubsoft_service is None:
        raise ValueError('tenant sem integração HubSoft ativa')

    extras = (hubsoft_service.integracao.configuracoes_extras or {}).get('hubsoft', {})
    id_contrato_modelo = id_contrato_modelo or extras.get('id_contrato_modelo')
    id_empresa = id_empresa or extras.get('id_empresa_padrao')
    if not id_contrato_modelo or not id_empresa:
        return False, {'motivo': 'sem_config'}

    tentativa, _t0 = iniciar_tentativa(oportunidade, 'gerar', hubsoft_service, origem='automacao_engine')

    # 1) criar contrato (se ainda não tem)
    id_contrato = servico.id_cliente_servico_contrato
    if not id_contrato:
        try:
            resp = hubsoft_service.criar_contrato(
                id_cliente_servico=servico.id_cliente_servico,
                id_contrato_modelo=int(id_contrato_modelo),
                id_empresa=int(id_empresa),
                autorizacao_nome=lead.nome_razaosocial or '',
                autorizacao_cpf=lead.cpf_cnpj or '',
                informacao_adicional='Contrato gerado via automacao Hubtrix (engine).',
                lead=lead,
            )
            id_contrato = (
                (resp.get('data') or {}).get('id_cliente_servico_contrato')
                or resp.get('id_cliente_servico_contrato')
                or (resp.get('contrato') or {}).get('id_cliente_servico_contrato')
            )
            if not id_contrato:
                exc = HubsoftServiceError('HubSoft criou mas nao retornou id_contrato')
                marcar_falha(tentativa, _t0, exc, etapa='criar')
                raise exc
            servico.id_cliente_servico_contrato = int(id_contrato)
            servico.save(update_fields=['id_cliente_servico_contrato'])
        except HubsoftServiceError as exc:
            marcar_falha(tentativa, _t0, exc, etapa='criar')
            raise

    # 2) anexar arquivos
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
                    {'nome': a[0], 'tamanho_bytes': len(a[1]) if a[1] else 0,
                     'mime': a[2] if len(a) > 2 else ''}
                    for a in arquivos
                ]
        except HubsoftServiceError as exc:
            erro_anexar = exc  # não para — ainda tenta aceitar

    # 3) aceitar contrato
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
        except HubsoftServiceError as exc:
            erro_aceitar = exc

    tentativa.anexos_enviados = arquivos_anexados
    if erro_aceitar:
        marcar_falha(tentativa, _t0, erro_aceitar, etapa='aceitar')
        raise erro_aceitar
    if erro_anexar:
        # aceitou mas o anexo falhou — sucesso parcial (tracking marca falha no anexo)
        marcar_falha(tentativa, _t0, erro_anexar, etapa='anexar')
        return True, {'motivo': 'aceito_anexo_falhou', 'id_contrato': id_contrato,
                      'arquivos': arquivos_anexados}
    marcar_sucesso(tentativa, _t0, resposta={'id_cliente_servico_contrato': id_contrato},
                   etapa='completo', id_contrato=id_contrato)
    return True, {'motivo': 'ok', 'id_contrato': id_contrato, 'arquivos': arquivos_anexados}


def assinar_contrato(tenant, *, oportunidade, ativar_servico_apos_aceite=False, integ_id=None):
    """Assina (aceita) o contrato JÁ EXISTENTE do lead no HubSoft. NÃO cria (no Nuvyon
    o contrato é auto-criado com o cliente/serviço). Resolve o id via
    consultar_cliente(incluir_contrato=True) e chama aceitar_contrato. Idempotente
    (pula se já aceito). Devolve `(feito: bool, info: dict)`:
    - feito=True → info={'motivo':'ok','id_contrato'}
    - feito=False + info={'motivo': <skip>} ('sem_lead','score_nao_aprovado','ja_aceito',
      'sem_cliente_hubsoft','sem_servico').
    Levanta `HubsoftServiceError` se a consulta/aceite falhar (nó → erro).

    `ativar_servico_apos_aceite`: após o aceite, chama ativar_servico (o aceite sozinho
    pode não mover o status do serviço)."""
    from apps.integracoes.services.hubsoft import HubsoftServiceError
    from apps.integracoes.services.contrato_tracking import (
        iniciar_tentativa, marcar_sucesso, marcar_falha,
    )
    from .hubsoft import hubsoft_do_tenant

    if oportunidade is None:
        raise ValueError('Sem oportunidade.')
    lead = oportunidade.lead
    if not lead:
        return False, {'motivo': 'sem_lead'}
    if getattr(lead, 'score_status', 'nao_consultado') != 'aprovado':
        return False, {'motivo': 'score_nao_aprovado'}
    if getattr(lead, 'contrato_aceito', False):
        return False, {'motivo': 'ja_aceito'}
    cliente_hubsoft = lead.clientes_hubsoft.first()
    if not cliente_hubsoft:
        return False, {'motivo': 'sem_cliente_hubsoft'}
    servico = cliente_hubsoft.servicos.first()
    if not servico:
        return False, {'motivo': 'sem_servico'}

    hubsoft_service = hubsoft_do_tenant(tenant, integ_id)
    if hubsoft_service is None:
        raise ValueError('tenant sem integração HubSoft ativa')

    tentativa, _t0 = iniciar_tentativa(oportunidade, 'assinar', hubsoft_service, origem='automacao_engine')

    # 1) resolve o id do contrato (já salvo, ou via consulta com incluir_contrato)
    id_contrato = servico.id_cliente_servico_contrato
    if not id_contrato:
        try:
            resp = hubsoft_service.consultar_cliente(lead.cpf_cnpj, lead=lead, incluir_contrato=True)
        except HubsoftServiceError as exc:
            marcar_falha(tentativa, _t0, exc, etapa='criar')  # consulta antes de aceitar
            raise
        id_contrato = _extrair_id_contrato(resp, servico.id_cliente_servico)
        if id_contrato:
            servico.id_cliente_servico_contrato = int(id_contrato)
            servico.save(update_fields=['id_cliente_servico_contrato'])
    if not id_contrato:
        exc = HubsoftServiceError('Contrato nao encontrado na consulta HubSoft')
        marcar_falha(tentativa, _t0, exc, etapa='criar')
        raise exc

    # 2) aceita o contrato
    try:
        hubsoft_service.aceitar_contrato(
            int(id_contrato),
            observacao='Contrato aceito automaticamente apos validacao de documentos.',
            lead=lead,
        )
    except HubsoftServiceError as exc:
        marcar_falha(tentativa, _t0, exc, etapa='aceitar')
        raise

    lead.contrato_aceito = True
    lead.data_aceite_contrato = timezone.now()
    lead.save(update_fields=['contrato_aceito', 'data_aceite_contrato'])
    marcar_sucesso(tentativa, _t0, resposta={'id_cliente_servico_contrato': id_contrato},
                   etapa='aceitar', id_contrato=id_contrato)

    # 3) opcional: ativar serviço (aceite sozinho pode não mover o status)
    ativado = None
    if ativar_servico_apos_aceite:
        try:
            hubsoft_service.ativar_servico(int(servico.id_cliente_servico))
            ativado = True
        except HubsoftServiceError:
            ativado = False  # não derruba o aceite (já persistido)

    return True, {'motivo': 'ok', 'id_contrato': id_contrato, 'servico_ativado': ativado}
