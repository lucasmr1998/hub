"""Resolvedor + executores do HubSoft por tenant pra engine de automação.

Espelha `services/whatsapp.py` e `services/matrix.py`: o nó nunca fala com a API
direto. `sincronizar_prospecto` reusa o helper de domínio que o motor de marketing
já usa (`hubsoft_prospecto_rascunho.sincronizar_prospecto_hubsoft`) — sem 2ª cópia.

Seletor de credencial (como o uazapi): todas as funções aceitam `integ_id` opcional
(pk da `IntegracaoAPI`). Vazio = a primeira integração HubSoft ativa do tenant
(retrocompatível — comportamento de antes do picker).
"""


def hubsoft_do_tenant(tenant, integ_id=None):
    """Devolve um `HubsoftService` do tenant, ou None se não houver integração ativa.

    `integ_id` (pk) escolhe qual conta HubSoft usar; vazio = a primeira ativa."""
    from apps.integracoes.models import IntegracaoAPI
    from apps.integracoes.services.hubsoft import HubsoftService
    integ = _integracao_hubsoft(tenant, integ_id)
    return HubsoftService(integ) if integ else None


def _integracao_hubsoft(tenant, integ_id=None):
    """Resolve a `IntegracaoAPI` HubSoft ativa do tenant (a `integ_id`, ou a 1ª ativa)."""
    from apps.integracoes.models import IntegracaoAPI
    qs = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='hubsoft', ativa=True)
    if integ_id:
        return qs.filter(pk=integ_id).first()
    return qs.first()


def sincronizar_prospecto(lead, integ_id=None):
    """Cria (rascunho) ou atualiza o prospecto do lead no HubSoft — decide pelo
    `lead.id_hubsoft`. Devolve `ResultadoSincProspecto` (nunca levanta).

    `integ_id` escolhe a conta HubSoft; vazio = a 1ª ativa do tenant (o helper já
    resolve sozinho se `integracao=None`)."""
    from apps.integracoes.services.hubsoft_prospecto_rascunho import (
        sincronizar_prospecto_hubsoft,
    )
    integracao = _integracao_hubsoft(getattr(lead, 'tenant', None), integ_id) if integ_id else None
    return sincronizar_prospecto_hubsoft(lead, integracao=integracao)


def consultar_cliente(tenant, cpf_cnpj, *, incluir_contrato=False, integ_id=None):
    """Consulta um cliente no HubSoft por CPF/CNPJ. Devolve o dict da API.

    Levanta ValueError se o tenant não tem integração HubSoft ativa.
    """
    svc = hubsoft_do_tenant(tenant, integ_id)
    if svc is None:
        raise ValueError('tenant sem integração HubSoft ativa')
    return svc.consultar_cliente(cpf_cnpj, incluir_contrato=incluir_contrato)


def listar_faturas(tenant, cpf_cnpj, *, apenas_pendente=False, integ_id=None):
    """Lista faturas (boletos) do cliente por CPF/CNPJ. Devolve list[dict]."""
    svc = hubsoft_do_tenant(tenant, integ_id)
    if svc is None:
        raise ValueError('tenant sem integração HubSoft ativa')
    return svc.listar_faturas_cliente(cpf_cnpj=cpf_cnpj, apenas_pendente=apenas_pendente)


def listar_planos_por_cep(tenant, cep, integ_id=None):
    """Lista os planos disponíveis pra um CEP (viabilidade comercial). Devolve list."""
    svc = hubsoft_do_tenant(tenant, integ_id)
    if svc is None:
        raise ValueError('tenant sem integração HubSoft ativa')
    return svc.listar_planos_por_cep(cep)
