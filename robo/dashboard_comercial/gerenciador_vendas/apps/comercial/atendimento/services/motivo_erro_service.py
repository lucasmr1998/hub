"""Service de telemetria de erros de resposta no fluxo do bot.

Captura quando o bot pergunta X e o cliente responde Y errado (Y nao valido pra
pergunta). Diferente de PerguntaSemResposta (suporte) que captura duvida livre
do cliente sem resposta na base.
"""
import logging

logger = logging.getLogger(__name__)


def _normaliza(s: str) -> str:
    """Lowercase + strip + colapsa whitespace. Usado pra dedup."""
    if not s:
        return ''
    return ' '.join(str(s).strip().lower().split())


def registrar_erro_resposta(
    *, tenant, pergunta_bot: str, resposta_cliente: str,
    no_fluxo: str = '', canal: str = '', lead=None, conversa=None,
):
    """Registra um MotivoErroResposta — ou incrementa ocorrencias se a mesma
    combinacao (pergunta_bot, resposta_cliente, no_fluxo) ja existe pendente.

    Args:
        tenant: Tenant (obrigatorio).
        pergunta_bot: texto da pergunta do bot (obrigatorio, min 1 char util).
        resposta_cliente: o que o cliente respondeu (obrigatorio, min 1 char util).
        no_fluxo: nome do node do bot (opcional).
        canal: canal de origem (opcional).
        lead: LeadProspecto opcional.
        conversa: Conversa opcional.

    Returns:
        (objeto MotivoErroResposta, criada: bool) ou (None, False) se invalido.
    """
    from apps.comercial.atendimento.models import MotivoErroResposta

    pb = (pergunta_bot or '').strip()
    rc = (resposta_cliente or '').strip()
    if not pb or not rc:
        return None, False

    pb_norm = _normaliza(pb)
    rc_norm = _normaliza(rc)
    nf_norm = _normaliza(no_fluxo or '')

    # Dedup: mesma combinacao normalizada, pendente, mesmo tenant.
    # iexact em vez de icontains pra precisao (pergunta_bot + resposta_cliente sao curtas
    # e estruturadas, nao queremos match parcial).
    qs = MotivoErroResposta.all_tenants.filter(
        tenant=tenant, resolvido=False,
        pergunta_bot__iexact=pb, resposta_cliente__iexact=rc,
    )
    if nf_norm:
        qs = qs.filter(no_fluxo__iexact=no_fluxo)
    existente = qs.first()

    if existente:
        existente.ocorrencias = (existente.ocorrencias or 0) + 1
        update_fields = ['ocorrencias']
        if lead and not existente.lead_id:
            existente.lead = lead
            update_fields.append('lead')
        if conversa and not existente.conversa_id:
            existente.conversa = conversa
            update_fields.append('conversa')
        if canal and not existente.canal:
            existente.canal = canal
            update_fields.append('canal')
        existente.save(update_fields=update_fields)
        return existente, False

    novo = MotivoErroResposta.objects.create(
        tenant=tenant,
        pergunta_bot=pb,
        resposta_cliente=rc,
        no_fluxo=no_fluxo or '',
        canal=canal or '',
        lead=lead, conversa=conversa,
    )
    return novo, True
