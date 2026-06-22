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


def uazapi_do_tenant(tenant):
    """Devolve um UazapiService do tenant, ou None se não há Uazapi ativa nele."""
    if tenant is None or getattr(tenant, 'pk', None) is None:
        return None
    from apps.integracoes.models import IntegracaoAPI
    from apps.integracoes.services.uazapi import UazapiService
    integ = IntegracaoAPI.all_tenants.filter(
        tenant=tenant, tipo='uazapi', ativa=True,
    ).first()
    if integ is None:
        return None
    try:
        return UazapiService(integracao=integ)
    except Exception:
        return None
