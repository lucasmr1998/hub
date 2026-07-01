"""
Camada de domínio compartilhada pelos nós de WhatsApp.

REUSA o serviço Uazapi que já existe (`apps.integracoes.services.uazapi.UazapiService`)
e resolve as credenciais por tenant via `IntegracaoAPI` (tipo='uazapi'). Nenhum nó
fala com a Uazapi direto — todos passam por aqui (executor de domínio único).
"""
import re


def chave_telefone(tel):
    """Normaliza um telefone pra usar como âncora de retoma (só dígitos)."""
    return re.sub(r'\D', '', str(tel or ''))


def uazapi_do_tenant(tenant, integracao_id=None):
    """Devolve um UazapiService do tenant, ou None se não há Uazapi ativa nele.

    `integracao_id` (opcional) escolhe a conta/credencial — o "credential" do n8n.
    Vazio/inválido cai pra primeira Uazapi ativa do tenant (back-compat)."""
    if tenant is None or getattr(tenant, 'pk', None) is None:
        return None
    from apps.integracoes.models import IntegracaoAPI
    from apps.integracoes.services.uazapi import UazapiService
    qs = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='uazapi', ativa=True)
    integ = qs.filter(pk=integracao_id).first() if integracao_id else None
    if integ is None:
        integ = qs.first()
    if integ is None:
        return None
    try:
        return UazapiService(integracao=integ)
    except Exception:
        return None


def enviar_venda(tenant, *, oportunidade, telefone, integ_id=None):
    """Manda o resumo da venda + documentos por WhatsApp (uazapi). Idempotente
    (flag `venda_whatsapp_enviada` no lead, gerida pelo service de domínio).

    Devolve `(enviou: bool, resultado: dict)`. `enviou`=False quando pulou por
    idempotência ("ja enviado") ou o service não efetivou. Portado de
    `crm.services.automacao_pipeline._acao_enviar_venda_whatsapp` (motor novo
    autossuficiente — reusa o service de domínio de leads, não importa do antigo)."""
    from apps.comercial.leads.services_whatsapp_venda import enviar_venda_whatsapp
    lead = getattr(oportunidade, 'lead', None) if oportunidade is not None else None
    if lead is None:
        raise ValueError('Sem lead na oportunidade.')
    telefone = (telefone or '').strip()
    if not telefone:
        raise ValueError('telefone vazio.')
    resultado = enviar_venda_whatsapp(lead, telefone, oportunidade=oportunidade, integ_id=integ_id)
    enviou = bool(resultado.get('ok')) and not (resultado.get('motivo') or '').startswith('ja enviado')
    return enviou, resultado
