"""
Models de Recrutamento e Selecao.

Arquivo separado de `models.py` porque o modulo ja passa de 900 linhas e
Recrutamento e um subdominio inteiro, no padrao de split de
`apps/sistema/models.py`. O re-export em `models.py` mantem
`from apps.people.models import X` funcionando pra quem importa.

Passo 1 do plano (`robo/docs/PRODUTO/modulos/people/RECRUTAMENTO-PLANO.md`):
so a EtapaPipeline. Vaga, LinkCandidatura e Candidato vem nos passos seguintes.
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sistema.mixins import TenantMixin
from apps.people import estados_recrutamento as estados_rs


# Turno esperado. Vocabulario proprio porque o DP nao tem equivalente: la o
# colaborador ja tem escala, aqui e expectativa declarada no anuncio.
TURNO_CHOICES = [
    ('manha',    'Manhã'),
    ('tarde',    'Tarde'),
    ('noite',    'Noite'),
    ('integral', 'Integral'),
    ('escala',   'Escala'),
]

JUSTIFICATIVA_AUMENTO = 'aumento_quadro'
JUSTIFICATIVA_SUBSTITUICAO = 'substituicao'

JUSTIFICATIVA_CHOICES = [
    (JUSTIFICATIVA_AUMENTO,      'Aumento de quadro'),
    (JUSTIFICATIVA_SUBSTITUICAO, 'Substituição'),
]


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


class Vaga(TenantMixin):
    """
    Uma posicao aberta numa unidade.

    A VAGA E A FONTE DA VERDADE DA DIVULGACAO. Este e o defeito de UX mais
    citado pela criadora do produto de origem, duas vezes em duas conversas
    diferentes: la, criar a vaga e criar o link de divulgacao sao fluxos
    separados, e ela mesma diz que nao deveriam ser. Requisito, cargo, horario e
    criterio vivem AQUI; arte, link, QR e texto de rede social sao derivados.

    Por isso o LinkCandidatura (passo 3) vai apontar pra ca, e nao o contrario, e
    por isso os requisitos sao filhos da vaga em vez de campos do link.
    """

    unidade = models.ForeignKey(
        'people.Unidade', on_delete=models.PROTECT, related_name='vagas',
        verbose_name="Unidade",
    )
    cargo = models.ForeignKey(
        'people.Cargo', on_delete=models.PROTECT, related_name='vagas',
        verbose_name="Cargo",
    )
    titulo = models.CharField(
        max_length=140, blank=True, default='', verbose_name="Título da vaga",
        help_text="Em branco usa o nome do cargo. Preencha quando a mesma "
                  "função tiver recortes diferentes, tipo Atendente noturno.",
    )
    tipo_contratacao = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name="Tipo de contratação",
    )
    turno = models.CharField(
        max_length=20, choices=TURNO_CHOICES, blank=True, default='',
        verbose_name="Turno esperado",
    )
    justificativa = models.CharField(
        max_length=20, choices=JUSTIFICATIVA_CHOICES,
        verbose_name="Justificativa",
    )
    colaborador_substituido = models.ForeignKey(
        'people.Colaborador', on_delete=models.PROTECT,
        null=True, blank=True, related_name='vagas_de_substituicao',
        verbose_name="Colaborador substituído",
        help_text="So faz sentido quando a justificativa e substituição.",
    )
    observacoes = models.TextField(blank=True, default='',
                                   verbose_name="Observações")
    limite_aprovados = models.PositiveSmallIntegerField(
        default=50, validators=[MinValueValidator(1)],
        verbose_name="Limite de aprovados",
        help_text="Ao atingir, a triagem para. A captação continua.",
    )
    status = models.CharField(
        max_length=20, choices=estados_rs.STATUS_VAGA,
        default=estados_rs.STATUS_VAGA_RASCUNHO, db_index=True,
        verbose_name="Status",
    )
    publicada_em = models.DateTimeField(null=True, blank=True)
    encerrada_em = models.DateTimeField(null=True, blank=True)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='vagas_criadas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_vaga'
        verbose_name = 'Vaga'
        verbose_name_plural = 'Vagas'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tenant', 'status', '-criado_em'],
                         name='people_vaga_status_idx'),
            models.Index(fields=['tenant', 'unidade', 'status'],
                         name='people_vaga_unidade_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(limite_aprovados__gte=1),
                name='people_vaga_limite_aprovados_minimo',
            ),
            # Substituido so pode existir quando a justificativa e substituicao.
            # Sem isto, trocar a justificativa depois deixa pendurada a
            # referencia a uma pessoa que ninguem esta substituindo, e o alerta
            # de pendencia no DP (ponte confirmada na spec) passa a apontar pro
            # nada.
            models.CheckConstraint(
                condition=(models.Q(justificativa=JUSTIFICATIVA_SUBSTITUICAO)
                           | models.Q(colaborador_substituido__isnull=True)),
                name='people_vaga_substituido_exige_justificativa',
            ),
        ]

    def __str__(self):
        return f'{self.nome_exibido} em {self.unidade.nome}'

    @property
    def nome_exibido(self):
        """Titulo quando ha, nome do cargo quando nao."""
        return self.titulo or self.cargo.nome

    @property
    def aceita_candidatura(self):
        """So vaga publicada recebe candidato novo. Ver estados_recrutamento."""
        return self.status in estados_rs.STATUS_VAGA_ACEITA_CANDIDATURA

    def requisitos_do_anuncio(self):
        """O que vai pro texto publicado."""
        return self.requisitos.filter(aparece_no_anuncio=True)

    def requisitos_de_triagem(self):
        """
        O que vira criterio de filtro.

        Separado de `requisitos_do_anuncio` de proposito: um requisito pode ser
        os dois, ou so um, e os dois conjuntos nao sao complementares. Ver o
        docstring de RequisitoVaga.
        """
        return self.requisitos.filter(usar_na_triagem=True)

    def mudar_status(self, novo_status):
        """
        Aplica a mudanca de status, validando contra a maquina.

        O metodo so aplica e carimba data. Historico e telemetria ficam pro
        servico do passo 5, quando houver candidato pra contar: emitir evento
        de vaga antes de existir funil seria registrar numero que ninguem le.

        Existe no model, e nao solto na view, pra que o carimbo de
        `publicada_em` e `encerrada_em` nao dependa de quem chamou lembrar.
        """
        estados_rs.validar_transicao_vaga(self.status, novo_status)

        campos = ['status', 'atualizado_em']
        self.status = novo_status

        if novo_status == estados_rs.STATUS_VAGA_PUBLICADA and not self.publicada_em:
            # `or` na primeira publicacao apenas: republicar depois de pausar
            # nao pode reescrever a data, senao o tempo de captacao encolhe
            # sozinho no relatorio.
            self.publicada_em = timezone.now()
            campos.append('publicada_em')

        if novo_status == estados_rs.STATUS_VAGA_ENCERRADA:
            self.encerrada_em = timezone.now()
            campos.append('encerrada_em')

        self.save(update_fields=campos)


class RequisitoVaga(TenantMixin):
    """
    Um requisito da vaga, com os DOIS usos separados.

    Esta e a regra 4.3 da spec de origem, e ela avisa explicitamente pra nao
    colapsar:

        "Cada requisito da vaga e texto de anuncio ou criterio de filtro da IA
        (ou ambos), controlado por um toggle. E o mecanismo que permite filtrar
        por coisas que nao convem publicar. Preserve a distincao, nao colapse os
        dois usos num campo so."

    Por isso sao dois booleanos e nao um enum de tres valores. O enum parece mais
    enxuto e destroi justamente o caso do meio, que e o mais comum: requisito que
    aparece no anuncio E filtra.

    O caso concreto que motiva a separacao: "disponibilidade pra trabalhar aos
    domingos" convem publicar; "experiencia minima de 6 meses" o RH prefere
    filtrar sem anunciar, pra nao afastar quem se candidataria mesmo assim.
    """

    vaga = models.ForeignKey(
        Vaga, on_delete=models.CASCADE, related_name='requisitos',
        verbose_name="Vaga",
    )
    texto = models.CharField(max_length=200, verbose_name="Requisito")
    obrigatorio = models.BooleanField(
        default=True, verbose_name="Obrigatório",
        help_text="Obrigatório ou desejável.",
    )
    aparece_no_anuncio = models.BooleanField(
        default=True, verbose_name="Aparece no anúncio",
    )
    usar_na_triagem = models.BooleanField(
        default=False, verbose_name="Usar como critério de triagem",
    )
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_requisito_vaga'
        verbose_name = 'Requisito da vaga'
        verbose_name_plural = 'Requisitos da vaga'
        ordering = ['ordem', 'id']
        indexes = [
            models.Index(fields=['tenant', 'vaga', 'ordem'],
                         name='people_requisito_vaga_idx'),
        ]
        constraints = [
            # Requisito que nao publica nem filtra nao faz nada. E dado morto que
            # o usuario digitou achando que servia, e o unico jeito de descobrir
            # seria estranhar o anuncio depois de publicado.
            models.CheckConstraint(
                condition=(models.Q(aparece_no_anuncio=True)
                           | models.Q(usar_na_triagem=True)),
                name='people_requisito_precisa_de_um_uso',
            ),
        ]

    def __str__(self):
        return self.texto
