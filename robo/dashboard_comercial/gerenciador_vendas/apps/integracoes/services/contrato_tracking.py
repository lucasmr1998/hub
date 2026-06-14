"""
Helpers pra registrar ContratoTentativa a partir das acoes de automacao
do CRM. Mantem `_acao_gerar_contrato_hubsoft` e `_acao_assinar_contrato_hubsoft`
enxutos: cada acao chama `iniciar_tentativa(...)` no inicio, depois
`marcar_*` conforme o resultado.
"""
import time
import uuid

from apps.integracoes.models import ContratoTentativa
from apps.integracoes.services.hubsoft_errors import categorizar_falha_contrato


def _resolver_grupo(oportunidade, acao):
    """Reusa grupo se houver tentativa anterior pro mesmo lead+acao, senao novo UUID."""
    lead_id = getattr(oportunidade, 'lead_id', None) or getattr(oportunidade.lead, 'pk', None)
    if not lead_id:
        return uuid.uuid4(), 1
    ultima = (
        ContratoTentativa.all_tenants
        .filter(lead_id=lead_id, acao=acao)
        .order_by('-tentativa_numero').first()
    )
    if ultima:
        return ultima.grupo_tentativas_id, ultima.tentativa_numero + 1
    return uuid.uuid4(), 1


def iniciar_tentativa(oportunidade, acao, hubsoft_service, regra=None, origem='automacao_pipeline'):
    """Cria registro `pendente`. Retorna (tentativa, t0_monotonic).

    Use `marcar_sucesso(tentativa, t0, resposta, etapa, id_contrato)` ou
    `marcar_falha(tentativa, t0, exc, etapa)` no fim da acao.
    """
    lead = oportunidade.lead
    cliente_hs = lead.clientes_hubsoft.first() if lead else None
    servico = cliente_hs.servicos.first() if cliente_hs else None
    integracao = hubsoft_service.integracao

    grupo_id, num = _resolver_grupo(oportunidade, acao)

    extras = (integracao.configuracoes_extras or {}).get('hubsoft', {})

    tentativa = ContratoTentativa(
        tenant=integracao.tenant,
        grupo_tentativas_id=grupo_id,
        tentativa_numero=num,
        acao=acao,
        id_cliente_servico=(servico.id_cliente_servico if servico else None),
        id_cliente_servico_contrato=(servico.id_cliente_servico_contrato if servico else None),
        id_modelo_contrato=extras.get('id_contrato_modelo'),
        id_empresa=extras.get('id_empresa_padrao'),
        lead=lead,
        cliente_hubsoft=cliente_hs,
        servico=servico,
        oportunidade=oportunidade,
        integracao=integracao,
        regra_automacao=regra,
        status='pendente',
        origem=origem,
        payload_enviado={
            'lead_id': lead.pk if lead else None,
            'oportunidade_id': oportunidade.pk,
            'id_cliente_servico': servico.id_cliente_servico if servico else None,
            'id_contrato_modelo': extras.get('id_contrato_modelo'),
            'id_empresa': extras.get('id_empresa_padrao'),
        },
    )
    # NAO salvamos ainda — vai salvar uma vez so no marcar_*
    return tentativa, time.monotonic()


def _commit(tentativa, t0):
    tentativa.duracao_ms = int((time.monotonic() - t0) * 1000)
    tentativa.save()


def marcar_sucesso(tentativa, t0, resposta=None, etapa='completo', id_contrato=None):
    tentativa.status = 'sucesso'
    tentativa.etapa = etapa
    if resposta is not None:
        tentativa.resposta_hubsoft = resposta if isinstance(resposta, dict) else {'raw': str(resposta)[:2000]}
    if id_contrato:
        try:
            tentativa.id_cliente_servico_contrato = int(id_contrato)
        except (TypeError, ValueError):
            pass
    _commit(tentativa, t0)


def marcar_falha(tentativa, t0, exc, etapa='completo'):
    msg = str(exc)
    tentativa.status = 'falha'
    tentativa.etapa = etapa
    tentativa.motivo_falha_mensagem = msg[:2000]
    tentativa.motivo_falha_categoria = categorizar_falha_contrato(msg)
    _commit(tentativa, t0)


def marcar_pulado_idempotente(tentativa, t0, motivo='ja_feito'):
    tentativa.status = 'pulado_idempotente'
    tentativa.etapa = 'completo'
    tentativa.motivo_falha_mensagem = motivo
    _commit(tentativa, t0)
