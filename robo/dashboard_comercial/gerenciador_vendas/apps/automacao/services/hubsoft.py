"""Resolvedor + executores do HubSoft por tenant pra engine de automação.

Espelha `services/whatsapp.py` e `services/matrix.py`: o nó nunca fala com a API
direto. `sincronizar_prospecto` reusa o helper de domínio que o motor de marketing
já usa (`hubsoft_prospecto_rascunho.sincronizar_prospecto_hubsoft`) — sem 2ª cópia.
"""


def hubsoft_do_tenant(tenant):
    """Devolve um `HubsoftService` do tenant, ou None se não houver integração ativa."""
    from apps.integracoes.models import IntegracaoAPI
    from apps.integracoes.services.hubsoft import HubsoftService
    integ = IntegracaoAPI.all_tenants.filter(
        tenant=tenant, tipo='hubsoft', ativa=True,
    ).first()
    return HubsoftService(integ) if integ else None


def sincronizar_prospecto(lead):
    """Cria (rascunho) ou atualiza o prospecto do lead no HubSoft — decide pelo
    `lead.id_hubsoft`. Devolve `ResultadoSincProspecto` (nunca levanta)."""
    from apps.integracoes.services.hubsoft_prospecto_rascunho import (
        sincronizar_prospecto_hubsoft,
    )
    return sincronizar_prospecto_hubsoft(lead)


def consultar_cliente(tenant, cpf_cnpj, *, incluir_contrato=False):
    """Consulta um cliente no HubSoft por CPF/CNPJ. Devolve o dict da API.

    Levanta ValueError se o tenant não tem integração HubSoft ativa.
    """
    svc = hubsoft_do_tenant(tenant)
    if svc is None:
        raise ValueError('tenant sem integração HubSoft ativa')
    return svc.consultar_cliente(cpf_cnpj, incluir_contrato=incluir_contrato)


def listar_faturas(tenant, cpf_cnpj, *, apenas_pendente=False):
    """Lista faturas (boletos) do cliente por CPF/CNPJ. Devolve list[dict]."""
    svc = hubsoft_do_tenant(tenant)
    if svc is None:
        raise ValueError('tenant sem integração HubSoft ativa')
    return svc.listar_faturas_cliente(cpf_cnpj=cpf_cnpj, apenas_pendente=apenas_pendente)


def listar_planos_por_cep(tenant, cep):
    """Lista os planos disponíveis pra um CEP (viabilidade comercial). Devolve list."""
    svc = hubsoft_do_tenant(tenant)
    if svc is None:
        raise ValueError('tenant sem integração HubSoft ativa')
    return svc.listar_planos_por_cep(cep)
