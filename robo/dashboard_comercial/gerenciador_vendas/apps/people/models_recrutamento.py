"""
Models de Recrutamento e Selecao.

Arquivo separado de `models.py` porque o modulo ja passa de 900 linhas e
Recrutamento e um subdominio inteiro, no padrao de split de
`apps/sistema/models.py`. O re-export em `models.py` mantem
`from apps.people.models import X` funcionando pra quem importa.

Passo 1 do plano (`robo/docs/PRODUTO/modulos/people/RECRUTAMENTO-PLANO.md`):
so a EtapaPipeline. Vaga, LinkCandidatura e Candidato vem nos passos seguintes.
"""
from django.db import models

from apps.sistema.mixins import TenantMixin
from apps.people import estados_recrutamento as estados_rs


class EtapaPipeline(TenantMixin):
    """
    Uma etapa do processo seletivo, configuravel por unidade.

    E a metade "dado" da divisao explicada em `estados_recrutamento.py`: etapa
    intermediaria e configuracao do cliente, saida terminal e regra de dominio
    em codigo. Aqui nao ha comportamento, so nome, ordem e prazo.

    ESCOPO. `unidade` nula significa "vale pro tenant inteiro", que e o default
    entregue pronto. Uma unidade que precise de fluxo proprio ganha as etapas
    dela e passa a ignorar as do tenant. Mesma forma do `config_efetiva()` do
    DP: global com override por unidade, e nao uma tabela de override separada.
    Ver `do_escopo()`.

    DESATIVAR NAO APAGA. A spec de origem e explicita sobre o comportamento
    observado no produto real: "esse botao ele fica, ele nao some, ele fica
    invisivel". Apagar a etapa deixaria orfao todo candidato parado nela, e o
    historico apontaria pra uma linha que nao existe mais. Por isso `ativa` e
    booleano e nao ha delete no fluxo normal.
    """

    unidade = models.ForeignKey(
        'people.Unidade', on_delete=models.CASCADE,
        null=True, blank=True, related_name='etapas_pipeline',
        verbose_name="Unidade",
        help_text="Em branco significa que a etapa vale pro tenant inteiro.",
    )
    nome = models.CharField(max_length=80, verbose_name="Nome da etapa")
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")
    ativa = models.BooleanField(
        default=True, verbose_name="Ativa",
        help_text="Etapa desativada some do board pra novos candidatos, porem "
                  "quem ja esta nela continua visivel.",
    )
    sla_dias = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Prazo máximo (dias)",
        help_text="Depois disso o candidato aparece como atrasado nesta etapa.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_etapa_pipeline'
        verbose_name = 'Etapa do pipeline'
        verbose_name_plural = 'Etapas do pipeline'
        ordering = ['ordem', 'id']
        indexes = [
            models.Index(fields=['tenant', 'unidade', 'ordem'],
                         name='people_etapa_escopo_idx'),
            models.Index(fields=['tenant', 'ativa'],
                         name='people_etapa_ativa_idx'),
        ]
        constraints = [
            # `nulls_distinct=False` e o ponto desta constraint, e nao um
            # detalhe. Sem ele o Postgres trata cada `unidade IS NULL` como
            # valor distinto, entao o tenant conseguiria acumular varias
            # "Triagem" globais e o seed viraria duplicata a cada execucao.
            # Precisa de PG 15+, e prod e dev rodam PG 17.
            models.UniqueConstraint(
                fields=['tenant', 'unidade', 'nome'],
                name='people_etapa_nome_unico_por_escopo',
                nulls_distinct=False,
            ),
        ]

    def __str__(self):
        escopo = self.unidade.nome if self.unidade_id else 'todas as unidades'
        return f'{self.nome} ({escopo})'

    @classmethod
    def do_escopo(cls, tenant, unidade=None, *, somente_ativas=True):
        """
        As etapas que valem pra esta unidade.

        Resolve o override: se a unidade tem etapas proprias, sao elas; senao,
        as do tenant. Nao mistura os dois niveis de proposito. Misturar
        produziria um pipeline que ninguem configurou, montado a partir de dois
        lugares, e o cliente nao teria como prever o resultado ao criar a
        primeira etapa da unidade.
        """
        base = cls.all_tenants.filter(tenant=tenant)
        if somente_ativas:
            base = base.filter(ativa=True)

        if unidade is not None:
            proprias = base.filter(unidade=unidade)
            if proprias.exists():
                return proprias

        return base.filter(unidade__isnull=True)

    @classmethod
    def semear_padrao(cls, tenant, unidade=None):
        """
        Cria o pipeline default se o escopo ainda nao tiver etapa nenhuma.

        Idempotente: roda de novo sem duplicar. Devolve a lista do que criou,
        vazia quando ja havia etapa. Usado no provisionamento do modulo e no
        seed de demo.
        """
        ja_tem = cls.all_tenants.filter(tenant=tenant, unidade=unidade).exists()
        if ja_tem:
            return []

        return cls.all_tenants.bulk_create([
            cls(tenant=tenant, unidade=unidade, nome=etapa['nome'],
                ordem=etapa['ordem'], sla_dias=etapa['sla_dias'])
            for etapa in estados_rs.ETAPAS_PADRAO
        ])
