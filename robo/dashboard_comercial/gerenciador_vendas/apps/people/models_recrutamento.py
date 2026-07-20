"""
Models de Recrutamento e Selecao.

Arquivo separado de `models.py` porque o modulo ja passa de 900 linhas e
Recrutamento e um subdominio inteiro, no padrao de split de
`apps/sistema/models.py`. O re-export em `models.py` mantem
`from apps.people.models import X` funcionando pra quem importa.

Passo 1 do plano (`robo/docs/PRODUTO/modulos/people/RECRUTAMENTO-PLANO.md`):
so a EtapaPipeline. Vaga, LinkCandidatura e Candidato vem nos passos seguintes.
"""
import re

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

# Canal de divulgacao. E choices e nao texto livre pelo mesmo motivo que Cargo
# virou entidade: "Facebook", "facebook" e "face" viram tres canais distintos e
# corrompem a atribuicao de origem, que e justamente o que o link existe pra
# medir. A lista sai do que a origem descreve em uso real.
CANAL_CHOICES = [
    ('facebook',  'Facebook'),
    ('instagram', 'Instagram'),
    ('whatsapp',  'WhatsApp'),
    ('linkedin',  'LinkedIn'),
    ('indeed',    'Indeed'),
    ('cartaz',    'Cartaz ou QR impresso'),
    ('indicacao', 'Indicação'),
    ('outro',     'Outro'),
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


class Candidato(TenantMixin):
    """
    Alguem que se candidatou. NAO e colaborador, e por isso mora em tabela
    propria.

    Se fosse mais uma `situacao` do Colaborador, toda consulta de RH (board do
    DP, analises, feedback, clima) teria que lembrar de excluir candidato, e o
    vocabulario racharia. Ja pagamos esse erro neste modulo uma vez.

    A PONTE PRO DP: `colaborador` e FK nula, preenchida so quando o candidato e
    admitido. Nao e o candidato que "vira" colaborador; e o colaborador que
    passa a referenciar de qual candidatura veio. Os dois registros coexistem,
    porque respondem perguntas diferentes: um e a pessoa da casa, outro e o
    processo seletivo que a trouxe.

    DEDUP POR WHATSAPP, e nao por CPF. O formulario publico nao coleta CPF de
    proposito: a origem testou e descartou por atrito de conversao, e a dor
    numero um do cliente e justamente "nao chega candidato". O CPF entra depois,
    na aprovacao, pelo formulario de cadastro do DP, que e onde a constraint de
    CPF ja mora.

    Motivo declarado do dedup por numero, que nao e seguranca e sim integridade
    de metrica: "fica parecendo pra gente um numero falso, parece que tem 300
    pessoas que se candidataram pra aquela vaga, mas 20 e a mesma pessoa se
    candidatando incansavelmente."

    FURO CONHECIDO E ADMITIDO: a mesma pessoa com numeros diferentes passa. A
    origem sabe e nao resolveu. Fica documentado em vez de fingido.
    """

    # ── Identidade ──
    nome_completo = models.CharField(max_length=200, verbose_name="Nome completo")
    whatsapp = models.CharField(
        max_length=15, null=True, blank=True, default=None,
        verbose_name="WhatsApp",
        help_text="So digitos, E.164 sem o mais. Ex: 5586999998888.",
    )
    email = models.EmailField(blank=True, default='', verbose_name="Email")
    data_nascimento = models.DateField(null=True, blank=True,
                                       verbose_name="Data de nascimento")

    # ── Endereco (o que a origem coleta) ──
    cidade = models.CharField(max_length=100, blank=True, default='',
                              verbose_name="Cidade")
    estado = models.CharField(max_length=2, blank=True, default='',
                              verbose_name="Estado")
    bairro = models.CharField(max_length=100, blank=True, default='',
                              verbose_name="Bairro")

    # ── Perfil ──
    experiencia_previa = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Experiência prévia",
    )
    disponibilidade_horario = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Disponibilidade de horário",
    )
    curriculo = models.FileField(
        upload_to='people/curriculos/%Y/%m/', null=True, blank=True,
        verbose_name="Currículo",
    )

    # ── Processo ──
    vaga = models.ForeignKey(
        Vaga, on_delete=models.PROTECT, null=True, blank=True,
        related_name='candidatos', verbose_name="Vaga",
        help_text="Nulo quando veio por link de banco de talentos.",
    )
    unidade = models.ForeignKey(
        'people.Unidade', on_delete=models.PROTECT, related_name='candidatos',
        verbose_name="Unidade",
    )
    link_origem = models.ForeignKey(
        'people.LinkCandidatura', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='candidatos', verbose_name="Link de origem",
        help_text="Como a atribuição de canal sobrevive à exclusão do link.",
    )
    etapa = models.ForeignKey(
        EtapaPipeline, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='candidatos', verbose_name="Etapa",
    )
    saida = models.CharField(
        max_length=20, choices=estados_rs.SAIDAS, blank=True, default='',
        db_index=True, verbose_name="Saída",
        help_text="Vazio significa que ainda esta no pipeline.",
    )
    motivo_saida = models.TextField(blank=True, default='',
                                    verbose_name="Motivo da saída")
    colaborador = models.ForeignKey(
        'people.Colaborador', on_delete=models.PROTECT, null=True, blank=True,
        related_name='candidaturas', verbose_name="Colaborador",
        help_text="Preenchido na admissão. Ver a ponte no docstring da classe.",
    )

    # ── LGPD ──
    consentimento_lgpd = models.BooleanField(default=False)
    consentimento_em = models.DateTimeField(null=True, blank=True)
    consentimento_ip = models.GenericIPAddressField(null=True, blank=True)
    consentimento_versao = models.CharField(max_length=20, blank=True, default='')
    consentimento_user_agent = models.TextField(blank=True, default='')
    retencao_ate = models.DateField(
        null=True, blank=True, verbose_name="Reter até",
        help_text="Depois desta data o cron anonimiza. Prazo declarado no "
                  "consentimento.",
    )
    anonimizado_em = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_candidato'
        verbose_name = 'Candidato'
        verbose_name_plural = 'Candidatos'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tenant', 'vaga', 'etapa'],
                         name='people_cand_pipeline_idx'),
            models.Index(fields=['tenant', 'saida'], name='people_cand_saida_idx'),
            models.Index(fields=['tenant', 'retencao_ate'],
                         name='people_cand_retencao_idx'),
        ]
        constraints = [
            # Regra 4.5 da spec. Mesma forma do CPF no Colaborador: ausente e
            # NULL (e NULLs sao distintos no Postgres, entao varios sem numero
            # convivem), presente e unico por tenant.
            models.UniqueConstraint(
                fields=['tenant', 'whatsapp'],
                name='people_candidato_whatsapp_unico_por_tenant',
            ),
            # Sem esta check, um unico ponto gravando '' faz o segundo ''
            # estourar a unique com IntegrityError incompreensivel. E a mesma
            # classe de bug que a check de CPF fecha no Colaborador.
            models.CheckConstraint(
                condition=(models.Q(whatsapp__isnull=True)
                           | models.Q(whatsapp__regex=r'^\d{10,15}$')),
                name='people_candidato_whatsapp_formato',
            ),
        ]

    def __str__(self):
        return self.nome_completo

    def save(self, *args, **kwargs):
        """
        Normaliza o WhatsApp pra so digitos, ou None.

        String vazia jamais chega ao banco: e ela que quebraria a unique.
        """
        self.whatsapp = re.sub(r'\D', '', self.whatsapp or '') or None
        super().save(*args, **kwargs)

    @property
    def esta_no_pipeline(self):
        return not self.saida

    @property
    def canal_origem(self):
        """De qual canal veio. Sobrevive a desativacao do link."""
        return self.link_origem.get_canal_display() if self.link_origem_id else ''

    def anonimizar(self):
        """
        Tira a pessoa e mantem o numero.

        Anonimizar em vez de apagar porque a analise de canal nao pode mentir
        retroativamente: se a linha sumisse, o funil de tres meses atras
        passaria a dizer que chegaram menos candidatos do que chegaram.

        O arquivo do curriculo e apagado de verdade. Ele nao entra em nenhuma
        agregacao e e o dado mais sensivel do registro.
        """
        if self.curriculo:
            self.curriculo.delete(save=False)

        self.nome_completo = 'Candidato anonimizado'
        self.whatsapp = None
        self.email = ''
        self.data_nascimento = None
        self.cidade = ''
        self.estado = ''
        self.bairro = ''
        self.experiencia_previa = ''
        self.disponibilidade_horario = ''
        self.consentimento_ip = None
        self.consentimento_user_agent = ''
        self.anonimizado_em = timezone.now()
        self.save()


class HistoricoCandidato(TenantMixin):
    """
    Cada movimento do candidato no pipeline.

    Espelho do HistoricoSituacao do DP, e pelo mesmo motivo: e a fonte primaria
    da telemetria de funil. Tempo medio por etapa e taxa de conversao por canal
    viram GROUP BY aqui, sem ferramenta externa.

    Guarda `de_etapa`/`para_etapa` como TEXTO, e nao FK, de proposito: etapa e
    configuravel e pode ser desativada ou renomeada, e o historico precisa
    continuar legivel depois disso. FK viraria "etapa apagada" na tela; o nome
    congelado no momento do movimento conta a verdade do que aconteceu.
    """

    candidato = models.ForeignKey(
        'people.Candidato', on_delete=models.CASCADE, related_name='historico',
        verbose_name="Candidato",
    )
    de_etapa = models.CharField(max_length=80, blank=True, default='',
                                verbose_name="De (etapa)")
    para_etapa = models.CharField(max_length=80, blank=True, default='',
                                  verbose_name="Para (etapa)")
    para_saida = models.CharField(
        max_length=20, choices=estados_rs.SAIDAS, blank=True, default='',
        verbose_name="Para (saída)",
    )
    motivo = models.TextField(blank=True, default='', verbose_name="Motivo")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    origem = models.CharField(max_length=20, default='painel',
                              verbose_name="Origem")
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_historico_candidato'
        verbose_name = 'Histórico do candidato'
        verbose_name_plural = 'Histórico dos candidatos'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tenant', 'candidato', '-criado_em'],
                         name='people_hist_cand_idx'),
            models.Index(fields=['tenant', 'para_saida', '-criado_em'],
                         name='people_hist_cand_saida_idx'),
        ]

    def __str__(self):
        destino = self.para_saida or self.para_etapa or 'entrada'
        return f'{self.candidato_id}: {self.de_etapa or "entrada"} para {destino}'


class LinkCandidatura(TenantMixin):
    """
    Link publico de candidatura, um por CANAL.

    Irmao do LinkCadastroUnidade do DP, e nao o mesmo model, por tres diferencas
    que nao sao cosmeticas:

    VARIOS POR VAGA, um por canal. E o mecanismo de atribuicao de origem: sem
    link por canal, o franqueado gasta em canal que nao converte sem saber. A
    spec lista isso entre as consequencias medidas do problema.

    NAO EXPIRA SOZINHO. Decisao consciente da origem, com motivo declarado:
    "hoje nao tem um prazo. Voce pode vir aqui no link e desativar ele. A gente
    fez isso porque a gente usa muito Facebook, entao as vezes as pessoas entram
    la no grupo antigo, publicacao ta la, elas se candidatam." Publicacao antiga
    em grupo continua rendendo candidato meses depois. O link do DP tem
    `expira_em`; este nao tem, de proposito.

    SEM TETO DE SUBMISSAO. A regra de parada mora na vaga (`limite_aprovados`) e
    e sobre APROVADOS, nao sobre candidaturas: ao atingir, a triagem para e a
    captacao continua. Um teto no link cortaria a captacao junto, que e o
    contrario do desenho.

    O token e unique GLOBAL, e nao por tenant, pelo mesmo motivo do DP: a URL
    publica nao carrega tenant, entao o proprio token e o mecanismo que resolve
    de quem e o link.
    """

    vaga = models.ForeignKey(
        Vaga, on_delete=models.CASCADE, null=True, blank=True,
        related_name='links', verbose_name="Vaga",
        help_text="Em branco, o link e de banco de talentos: capta sem vaga "
                  "aberta.",
    )
    unidade = models.ForeignKey(
        'people.Unidade', on_delete=models.CASCADE,
        related_name='links_candidatura', verbose_name="Unidade",
    )
    canal = models.CharField(
        max_length=20, choices=CANAL_CHOICES, verbose_name="Canal",
        help_text="Onde este link vai ser divulgado. É o que permite saber "
                  "depois qual canal trouxe candidato.",
    )
    apelido_interno = models.CharField(
        max_length=120, blank=True, default='', verbose_name="Apelido interno",
        help_text="Como o RH distingue este link dos outros. Ex: Grupo de "
                  "empregos da zona sul.",
    )
    token = models.CharField(
        max_length=64, unique=True, db_index=True, verbose_name="Token",
        help_text="secrets.token_urlsafe(32). Nao editar na mao.",
    )
    cta = models.CharField(
        max_length=140, blank=True, default='',
        verbose_name="Chamada para ação",
        help_text="Frase que abre o anúncio.",
    )
    telefone_contato = models.CharField(
        max_length=20, blank=True, default='', verbose_name="Telefone de contato",
    )
    texto_compartilhamento = models.TextField(
        blank=True, default='', verbose_name="Texto de divulgação",
        help_text="Gerado a partir da vaga e editável. A vaga continua sendo a "
                  "fonte da verdade.",
    )
    candidaturas = models.PositiveIntegerField(
        default=0, verbose_name="Candidaturas",
        help_text="Quantas chegaram por este link. É a atribuição de canal.",
    )
    ultima_candidatura_em = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    desativado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='links_candidatura_criados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_link_candidatura'
        verbose_name = 'Link de candidatura'
        verbose_name_plural = 'Links de candidatura'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tenant', 'vaga', 'ativo'],
                         name='people_link_cand_vaga_idx'),
            models.Index(fields=['tenant', 'unidade', 'canal'],
                         name='people_link_cand_canal_idx'),
        ]
        # Sem unique por (vaga, canal): dois links no mesmo canal e caso real,
        # tipo dois grupos de Facebook diferentes. Quem distingue e o apelido.

    def __str__(self):
        alvo = self.vaga.nome_exibido if self.vaga_id else 'banco de talentos'
        return f'{self.get_canal_display()} · {alvo}'

    def esta_valido(self):
        """
        Aceita candidatura? So depende de estar ativo e de a vaga aceitar.

        Sem checagem de prazo nem de teto, ao contrario do link do DP: ver o
        docstring da classe pra saber por que cada um esta fora.
        """
        if not self.ativo:
            return False
        if self.vaga_id and not self.vaga.aceita_candidatura:
            return False
        return True

    @property
    def caminho_publico(self):
        return f'/people/candidatura/{self.token}/'

    def desativar(self):
        """
        Desativa sem apagar.

        Apagar levaria junto as candidaturas que vieram por ele e destruiria a
        atribuicao de canal, que e a razao de o link existir. Efeito colateral
        conhecido e aceito: QR ja impresso para de funcionar.
        """
        self.ativo = False
        self.desativado_em = timezone.now()
        self.save(update_fields=['ativo', 'desativado_em'])

    def texto_padrao(self):
        """
        Monta o texto de divulgacao A PARTIR DA VAGA.

        E aqui que "a vaga e a fonte da verdade" deixa de ser frase e vira
        codigo: o RH nao redigita requisito no link, ele sai do que ja foi
        cadastrado. So entram os requisitos marcados pra aparecer no anuncio; o
        que e criterio de triagem calado nao vaza pro texto publicado.
        """
        if not self.vaga_id:
            return ('Deixe seu currículo com a gente. Assim que abrir uma vaga '
                    'no seu perfil, entramos em contato.')

        linhas = [self.cta or f'Vaga para {self.vaga.nome_exibido}',
                  f'Local: {self.unidade.nome}']

        if self.vaga.turno:
            linhas.append(f'Turno: {self.vaga.get_turno_display()}')

        requisitos = list(self.vaga.requisitos_do_anuncio())
        if requisitos:
            linhas.append('')
            linhas.append('O que buscamos:')
            linhas += [f'- {r.texto}' for r in requisitos]

        if self.telefone_contato:
            linhas.append('')
            linhas.append(f'Dúvidas: {self.telefone_contato}')

        return '\n'.join(linhas)
