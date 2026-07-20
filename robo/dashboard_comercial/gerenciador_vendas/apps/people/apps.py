from django.apps import AppConfig


class PeopleConfig(AppConfig):
    """
    People — gestao de pessoas (RH) por tenant.

    Cobre o ciclo de vida do colaborador, de cadastro a desligamento. Portado
    da spec do modulo People da Visio (ver robo/docs/PRODUTO/modulos/people/).

    Duas regras estruturais que valem pro modulo inteiro e que codigo novo
    NAO pode violar:

    1. `Colaborador` e FONTE UNICA de cadastro de pessoa. Toda Tool que for
       criar colaborador (feedback, recrutamento, treinamento) precisa passar
       por `apps.people.services.registrar_colaborador`, que tem o dedup
       embutido. Ninguem escreve na tabela direto, e ninguem cria cadastro
       paralelo pra sua propria Tool.

    2. Colaborador NAO se apaga, se desliga. A desativacao e soft delete via
       `situacao='desligado'`, e e isso que viabiliza readmissao e o
       reaproveitamento como freelancer. FK vinda de outro app deve ser
       PROTECT, nunca CASCADE.

    Multi-tenant, com escopo adicional por Unidade (loja ou filial).
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.people'
    label = 'people'
    verbose_name = 'People (gestao de pessoas)'

    def ready(self):
        import apps.people.signals  # noqa: F401
