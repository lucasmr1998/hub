"""Helper dos singletons de configuracao do CS (RoletaConfig, LandingConfig,
IndicacaoConfig). Cada um herda TenantMixin: existe UM registro por tenant.

Substitui o padrao antigo `Model.objects.get_or_create(id=1)`, que forcava a
PK id=1 e colidia entre tenants: o segundo tenant nao achava a linha id=1 pelo
manager (que filtra por tenant) e tentava criar outra com a mesma PK, gerando
IntegrityError. Alem disso escrevia no banco em requests GET.
"""


def config_singleton(model_cls):
    """Retorna o registro unico de config do tenant atual, criando se faltar.

    `objects` e o TenantManager (filtra pelo tenant do request) e o `save()` do
    TenantMixin auto-preenche o tenant na criacao. Sem PK forcada: usa o
    auto-incremento normal, entao nunca colide entre tenants.
    """
    config = model_cls.objects.first()
    if config is None:
        config = model_cls.objects.create()
    return config
