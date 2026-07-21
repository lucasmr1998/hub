"""
Models de Recrutamento e Selecao.

Arquivo separado de `models.py` porque o modulo ja passa de 900 linhas e
Recrutamento e um subdominio inteiro, no padrao de split de
`apps/sistema/models.py`. O re-export em `models.py` mantem
`from apps.people.models import X` funcionando pra quem importa.
"""
import os
import re

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sistema.mixins import TenantMixin
from apps.people import estados_recrutamento as estados_rs


class PrivateCurriculoStorage(FileSystemStorage):
    """
    Storage privado pro curriculo do candidato.

    Curriculo e dado pessoal denso: nome, contato, historico, as vezes endereco.
    MEDIA_ROOT e servido pela rota aberta `/media/` sem autenticacao nenhuma,
    entao um curriculo la seria baixavel por qualquer um que descobrisse a URL.

    Fica em `private_media/`, que e um volume separado no deploy e NAO tem rota
    publica. Acesso so pela view auth-gated `views/candidatos.py::curriculo`.
    Mesmo padrao do PrivateMidiaStorage do Inbox, que resolveu isto antes pra
    RG e comprovante.
    """

    def __init__(self, *args, **kwargs):
        kwargs['location'] = os.path.join(
            settings.BASE_DIR, 'private_media', 'people_curriculos')
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        return ('apps.people.models_recrutamento.PrivateCurriculoStorage', [], {})

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

# Modelo de trabalho. Choices e nao texto livre porque e o tipo de coisa que o
# candidato filtra ("tem remoto?") e que o RH compara entre vagas.
MODELO_TRABALHO_CHOICES = [
    ('presencial', 'Presencial'),
    ('hibrido',    'Híbrido'),
    ('remoto',     'Remoto'),
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
    cor = models.CharField(
        max_length=20, blank=True, default='', verbose_name="Cor",
        help_text="Chave da paleta (ver CORES_ETAPA). Vazio usa a cor da ordem.",
    )
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

    @property
    def cor_hex(self):
        """Cor resolvida. Sem cor gravada, deriva da ordem."""
        return estados_rs.hex_da_cor(self.cor, self.ordem)

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
                ordem=etapa['ordem'], sla_dias=etapa['sla_dias'],
                cor=etapa.get('cor', ''))
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
    # ── Descricao publica (o que o candidato le no anuncio) ──
    # Separada de `observacoes`, que e interna (contexto pra quem tria). Confundir
    # as duas ja aconteceu: observacoes ia pro anuncio e vazava nota interna.
    descricao = models.TextField(
        blank=True, default='', verbose_name="Descrição da vaga",
        help_text="Narrativa que o candidato lê: sobre a vaga, o que vai fazer, "
                  "o que a empresa oferece.",
    )
    remuneracao = models.CharField(
        max_length=80, blank=True, default='', verbose_name="Remuneração",
        help_text="Ex: Bolsa-auxílio de R$ 700,00. Texto livre porque varia "
                  "muito (fixo, faixa, mais comissão).",
    )
    carga_horaria = models.CharField(
        max_length=80, blank=True, default='', verbose_name="Carga horária",
        help_text="Ex: 30h semanais (6h/dia).",
    )
    modelo_trabalho = models.CharField(
        max_length=20, choices=MODELO_TRABALHO_CHOICES, blank=True, default='',
        verbose_name="Modelo de trabalho",
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
    config_campos = models.JSONField(
        default=dict, blank=True, verbose_name="Campos do formulário",
        help_text="Quais campos a candidatura pede e quais sao obrigatorios. "
                  "Vazio usa o padrao. Ver apps/people/campos_candidatura.py.",
    )
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

    def campos_extras(self):
        """
        Os campos que o tenant inventou, no formato do catalogo.

        `all_tenants` com tenant explicito porque este metodo roda tambem na
        pagina publica, onde o thread local nao esta preenchido e o
        TenantManager nao filtraria nada.
        """
        return CampoCandidatura.catalogo_do_tenant(self.tenant)

    def secoes_do_formulario(self, valores=None, erros=None):
        """
        As secoes de campos que a candidatura desta vaga mostra.

        Resolve `config_campos` pelo catalogo e ja injeta valor e erro por campo,
        pra o template so exibir. Fica no model, e nao na view, porque a pagina
        publica e a de configuracao vao consumir a mesma resolucao.
        """
        from apps.people import campos_candidatura as catalogo

        valores = valores or {}
        erros = erros or {}
        campos = catalogo.campos_solicitados(self.config_campos,
                                             self.campos_extras())
        for campo in campos:
            campo['valor'] = valores.get(campo['nome'], '')
            campo['erro'] = erros.get(campo['nome'], '')
            campo['ajuda'] = campo.get('ajuda', '')
            campo['placeholder'] = campo.get('placeholder', '')
        return catalogo.agrupar_em_secoes(campos)

    @property
    def total_admitidos(self):
        """Quantos candidatos desta vaga ja sairam por admitido."""
        return self.candidatos.filter(saida=estados_rs.SAIDA_ADMITIDO).count()

    @property
    def atingiu_limite(self):
        """
        A vaga ja bateu o teto de aprovados.

        Regra 4.4 da spec: ao atingir `limite_aprovados`, a triagem para; a
        captacao continua. Nao temos triagem por IA, entao aqui isto e um AVISO,
        e nao um bloqueio: admitir o candidato 51 continua possivel, porque a
        decisao final e do RH. O que o sistema faz e deixar visivel que o teto
        foi passado, pra ser decisao e nao descuido.
        """
        return self.total_admitidos >= self.limite_aprovados

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


class CampoCandidatura(TenantMixin):
    """
    Campo que o TENANT inventa pro formulario de candidatura.

    O catalogo de `campos_candidatura.py` e fixo em codigo porque cada campo de
    la tem coluna no Candidato. Este model e a saida pro que nao tem coluna: uma
    vaga de motoboy quer CNH, uma de caixa nao, e nenhuma das duas justifica
    migration em producao.

    DIVISAO DE PAPEL, igual a dos campos de sistema: o TENANT define o campo
    (rotulo, tipo, opcoes) e a VAGA escolhe se pede e se e obrigatorio, via
    `Vaga.config_campos`. Sem isso seriam dois modelos mentais pra mesma tabela
    de configuracao, e o usuario teria que aprender qual campo se configura onde.

    O valor vai pra `Candidato.dados_custom`, e o expurgo LGPD zera esse JSON
    inteiro. Ver `Candidato.anonimizar`: e o que impede o tenant de criar um
    campo "CPF" que sobrevive a politica de retencao.
    """

    # Nao ha 'file': curriculo ja e o anexo do formulario, e um segundo upload
    # precisaria de storage privado, limite de tamanho e expurgo proprios. Se
    # aparecer demanda real, entra como trabalho proprio e nao de carona.
    TIPO_CHOICES = [
        ('text',     'Texto curto'),
        ('textarea', 'Texto longo'),
        ('number',   'Número'),
        ('date',     'Data'),
        ('select',   'Lista de opções'),
        ('bool',     'Sim ou não'),
    ]

    nome = models.CharField(
        max_length=100, verbose_name="Rótulo do campo",
        help_text="O que o candidato le. Ex: Tem CNH categoria B?",
    )
    slug = models.SlugField(
        max_length=60, verbose_name="Chave",
        help_text="Identificador em dados_custom. Nao muda depois de criado.",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='text',
                            verbose_name="Tipo")
    opcoes = models.JSONField(
        default=list, blank=True, verbose_name="Opções",
        help_text="Só para o tipo lista. Uma opção por linha.",
    )
    ajuda = models.CharField(max_length=200, blank=True, default='',
                             verbose_name="Texto de ajuda")
    secao = models.CharField(
        max_length=20, default='experiencia', verbose_name="Seção",
        help_text="Em que bloco do formulário o campo aparece.",
    )
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name="Ordem")
    ativo = models.BooleanField(
        default=True, verbose_name="Ativo",
        help_text="Desativado some do formulário, sem apagar o que já foi "
                  "respondido.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_campo_candidatura'
        verbose_name = 'Campo de candidatura'
        verbose_name_plural = 'Campos de candidatura'
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['tenant', 'ativo', 'ordem'],
                         name='people_campo_cand_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'slug'],
                name='people_campo_cand_slug_unico_por_tenant',
            ),
        ]

    def __str__(self):
        return self.nome

    @property
    def chave(self):
        """
        Nome do campo no formulario e em `config_campos`.

        PREFIXADO de proposito. Sem o prefixo, um tenant que criasse a chave
        "email" produziria um campo com o mesmo nome do campo de sistema, e o
        POST, a config da vaga e o dedup passariam a disputar a mesma chave em
        silencio. O prefixo torna a colisao impossivel por construcao, em vez de
        depender de uma lista de nomes proibidos que envelhece.
        """
        return f'custom__{self.slug}'

    def como_campo(self):
        """
        Converte pro mesmo dict que o catalogo de sistema devolve.

        E o que permite o formulario publico, a validacao do POST e a tela da
        vaga tratarem campo de sistema e campo custom pelo mesmo caminho, sem um
        `if custom` espalhado em quatro lugares.
        """
        opcoes = [str(o) for o in (self.opcoes or [])]
        return {
            'nome': self.chave,
            'tipo': self.tipo,
            'rotulo_padrao': self.nome,
            'ajuda': self.ajuda,
            'opcoes': opcoes,
            # `components/select.html` desempacota PARES. A lista crua fica pra
            # validacao do POST, que compara com o que o candidato mandou.
            'opcoes_pares': [(o, o) for o in opcoes],
            'secao': self.secao,
            'custom': True,
            'slug': self.slug,
        }

    @classmethod
    def catalogo_do_tenant(cls, tenant):
        """Os campos ativos do tenant, no formato do catalogo."""
        campos = cls.all_tenants.filter(tenant=tenant, ativo=True).order_by(
            'ordem', 'nome')
        return [campo.como_campo() for campo in campos]


class MensagemRecrutamento(TenantMixin):
    """
    Mensagem sugerida ao RH quando o candidato chega numa etapa ou numa saida.

    NADA E ENVIADO AUTOMATICAMENTE. E a mesma decisao de produto do
    `MensagemEtapa` do Departamento Pessoal, e a origem repete o motivo na
    propria tela: "Voce pode personaliza-la so para este candidato antes de
    enviar, sem alterar esse padrao".

    Quem quiser automatizar de verdade monta um fluxo na engine escutando o
    evento da transicao. Os dois caminhos convivem: este e a sugestao pro
    humano, aquele e a automacao explicita.

    ETAPA OU SAIDA, NUNCA OS DOIS. E a divisao que estrutura o modulo inteiro:
    etapa intermediaria e DADO (linha configuravel), saida terminal e CODIGO
    (constante em estados_recrutamento). A constraint no banco garante que a
    linha aponte pra exatamente um dos dois, em vez de deixar o codigo torcer.

    ABRE O WHATSAPP, nao envia por API. Copiado da origem de proposito: funciona
    pra qualquer cliente, sem integracao, sem custo por mensagem e sem risco de
    bloqueio de numero. Cliente com Uazapi pode automatizar pela engine.
    """

    etapa = models.ForeignKey(
        'people.EtapaPipeline', on_delete=models.CASCADE, null=True, blank=True,
        related_name='mensagens', verbose_name="Etapa",
        help_text="Mensagem sugerida quando o candidato chega nesta etapa.",
    )
    saida = models.CharField(
        max_length=20, choices=estados_rs.SAIDAS, blank=True, default='',
        verbose_name="Saída",
        help_text="Mensagem sugerida quando o candidato sai por este motivo.",
    )
    texto = models.TextField(
        verbose_name="Mensagem padrão",
        help_text="Aceita {{nome}}, {{primeiro_nome}}, {{vaga}}, {{unidade}} "
                  "e {{cargo}}.",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_mensagem_recrutamento'
        verbose_name = 'Mensagem de recrutamento'
        verbose_name_plural = 'Mensagens de recrutamento'
        ordering = ['saida', 'etapa__ordem']
        indexes = [
            models.Index(fields=['tenant', 'ativo'],
                         name='people_msg_recr_ativo_idx'),
        ]
        constraints = [
            # Exatamente um dos dois. Sem isto, uma linha com os dois
            # preenchidos (ou nenhum) so seria descoberta quando a tela nao
            # achasse a mensagem, e o sintoma seria "sumiu", nao "esta errado".
            models.CheckConstraint(
                condition=(
                    models.Q(etapa__isnull=False, saida='')
                    | models.Q(etapa__isnull=True) & ~models.Q(saida='')
                ),
                name='people_msg_recr_etapa_ou_saida',
            ),
            models.UniqueConstraint(
                fields=['tenant', 'etapa'], condition=models.Q(etapa__isnull=False),
                name='people_msg_recr_uma_por_etapa',
            ),
            models.UniqueConstraint(
                fields=['tenant', 'saida'], condition=~models.Q(saida=''),
                name='people_msg_recr_uma_por_saida',
            ),
        ]

    def __str__(self):
        if self.etapa_id:
            return f'Mensagem de {self.etapa.nome}'
        return f'Mensagem de {estados_rs.rotulo_saida(self.saida)}'

    def render(self, candidato):
        """
        Troca as variaveis. O RH ainda edita antes de enviar.

        Placeholder sem valor vira string vazia, e nao fica como `{{vaga}}` na
        tela: a mensagem vai pro candidato, e chave de template aparecendo pra
        ele e pior que a frase ficar mais curta.
        """
        nome = (candidato.nome_completo or '').strip()
        vaga = candidato.vaga.nome_exibido if candidato.vaga_id else ''
        cargo = (candidato.vaga.cargo.nome
                 if candidato.vaga_id and candidato.vaga.cargo_id else '')

        substituicoes = {
            '{{nome}}': nome,
            '{{primeiro_nome}}': nome.split(' ')[0] if nome else '',
            '{{vaga}}': vaga,
            '{{unidade}}': getattr(candidato.unidade, 'nome', ''),
            '{{cargo}}': cargo,
        }
        texto = self.texto
        for chave, valor in substituicoes.items():
            texto = texto.replace(chave, valor)
        return texto


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

    # ── Respostas dos campos que o tenant inventou ──
    dados_custom = models.JSONField(
        default=dict, blank=True, verbose_name="Respostas dos campos custom",
        help_text="Chave e o slug do CampoCandidatura. Vive em JSON porque o "
                  "tenant inventa o campo e nao da pra virar coluna.",
    )

    curriculo = models.FileField(
        upload_to='%Y/%m/', storage=PrivateCurriculoStorage(),
        null=True, blank=True, verbose_name="Currículo",
        help_text="Storage privado, fora de /media/. Servido só pela view "
                  "auth-gated.",
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
    etapa_desde = models.DateTimeField(
        null=True, blank=True, verbose_name="Nesta etapa desde",
        help_text="Quando entrou na etapa atual. Base do indicador de atraso.",
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
    def idade_texto(self):
        """
        Idade em anos e meses, como a tela de origem mostra.

        Anos e meses, e nao so anos, porque em vaga de primeiro emprego a
        diferenca entre 17 e 11 meses e 18 recem feitos e a diferenca entre
        poder e nao poder contratar.
        """
        if not self.data_nascimento:
            return ''

        hoje = timezone.localdate()
        anos = hoje.year - self.data_nascimento.year
        meses = hoje.month - self.data_nascimento.month
        if hoje.day < self.data_nascimento.day:
            meses -= 1
        if meses < 0:
            anos -= 1
            meses += 12

        if anos < 0:
            return ''
        if not meses:
            return f'{anos} anos'
        return f'{anos} anos e {meses} {"mês" if meses == 1 else "meses"}'

    @property
    def canal_origem(self):
        """De qual canal veio. Sobrevive a desativacao do link."""
        return self.link_origem.get_canal_display() if self.link_origem_id else ''

    @property
    def dias_na_etapa(self):
        """
        Ha quantos dias esta parado na etapa atual. None se nao se aplica.

        Sai de `etapa_desde`, e nao de `atualizado_em`: qualquer edicao do
        candidato (corrigir um telefone) bumparia o atualizado_em e zeraria a
        contagem sem ele ter andado no processo.
        """
        if not self.etapa_desde or self.saida or not self.etapa_id:
            return None
        return (timezone.now() - self.etapa_desde).days

    @property
    def esta_atrasado(self):
        """
        Passou do prazo da etapa.

        Etapa sem `sla_dias` NUNCA marca atraso: prazo em branco significa "sem
        prazo", e nao "prazo zero". Quem saiu do processo tambem nao: parado
        numa saida terminal e o estado final esperado, nao demora.
        """
        dias = self.dias_na_etapa
        if dias is None or not self.etapa.sla_dias:
            return False
        return dias > self.etapa.sla_dias

    @property
    def dias_de_atraso(self):
        """Quantos dias ALEM do prazo. Zero quando nao ha atraso."""
        if not self.esta_atrasado:
            return 0
        return self.dias_na_etapa - self.etapa.sla_dias

    def link_whatsapp(self, texto=''):
        """
        URL que ABRE o WhatsApp com a mensagem pronta.

        `wa.me` e nao API de proposito: funciona pra qualquer cliente, sem
        integracao contratada, sem custo por mensagem e sem risco de bloqueio de
        numero. Quem tem Uazapi automatiza pela engine, que e outro caminho.

        Devolve vazio quando nao ha WhatsApp: candidato anonimizado pelo expurgo
        LGPD tem o numero apagado, e um link `wa.me/` sem numero abriria uma tela
        de erro do WhatsApp em vez de nao aparecer.
        """
        from urllib.parse import quote

        if not self.whatsapp:
            return ''
        numero = ''.join(c for c in self.whatsapp if c.isdigit())
        if not numero:
            return ''
        base = f'https://wa.me/{numero}'
        return f'{base}?text={quote(texto)}' if texto else base

    def mensagem_sugerida(self):
        """
        A mensagem configurada pra onde o candidato esta AGORA, ja renderizada.

        Saida tem precedencia sobre etapa: quem saiu do processo continua
        apontando pra ultima etapa, e a mensagem certa e a da saida ("nao foi
        aprovado"), nao a da etapa em que ele parou.
        """
        modelo = None
        if self.saida:
            modelo = MensagemRecrutamento.all_tenants.filter(
                tenant_id=self.tenant_id, saida=self.saida, ativo=True).first()
        elif self.etapa_id:
            modelo = MensagemRecrutamento.all_tenants.filter(
                tenant_id=self.tenant_id, etapa_id=self.etapa_id,
                ativo=True).first()
        return modelo.render(self) if modelo else ''

    @property
    def rotulo_atraso(self):
        """
        Texto do selo de atraso.

        Fica no model, e nao no template, porque o board mostra em dois lugares
        (lista e kanban) e texto duplicado em template diverge.
        """
        dias = self.dias_de_atraso
        if not dias:
            return ''
        return f'{dias} dia atrasado' if dias == 1 else f'{dias} dias atrasado'

    def anonimizar(self):
        """
        Tira a pessoa e mantem o numero.

        Anonimizar em vez de apagar porque a analise de canal nao pode mentir
        retroativamente: se a linha sumisse, o funil de tres meses atras
        passaria a dizer que chegaram menos candidatos do que chegaram.

        O arquivo do curriculo e apagado de verdade. Ele nao entra em nenhuma
        agregacao e e o dado mais sensivel do registro.

        `dados_custom` e ZERADO INTEIRO, sem inspecionar o conteudo. O campo e
        inventado pelo tenant, entao nao ha como saber o que ele pos ali: um
        cliente cria "Nome da mae" ou "CPF" e, se a limpeza fosse por chave
        conhecida, esse dado sobreviveria ao expurgo e a promessa do
        consentimento quebraria em silencio. Zerar tudo e a unica limpeza que
        nao depende de adivinhar.
        """
        if self.curriculo:
            self.curriculo.delete(save=False)

        self.dados_custom = {}

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


class AnaliseCandidato(TenantMixin):
    """
    O que a IA achou do candidato, contra os requisitos de triagem da vaga.

    SOB DEMANDA, e nao automatica. Um botao "Analisar" na ficha, igual a origem
    faz. Nao roda na chegada da candidatura por dois motivos: o `disparar_evento`
    executa a engine em tempo de request, e uma chamada de LLM ali faria o
    candidato esperar dez segundos no celular na porta da loja; e porque assim o
    custo fica sob controle do RH, que analisa quem interessa, e nao os 76
    automaticamente.

    NUNCA MOVE O CANDIDATO. E sugestao, e a decisao continua sendo humana. A
    origem e explicita: "sempre precisa de revisao humana", e a acao so termina
    quando alguem move o card. Automatizar a recusa seria decidir contratacao
    por LLM, com risco trabalhista e sem ninguem pra responder por ela.

    GUARDA CUSTO E TOKENS de proposito. "Quanto isso custa" era discussao aberta,
    inclusive na origem, que registra o tema como pergunta de precificacao em
    aberto. Com o consumo gravado por analise, a pergunta se responde com dado
    real em uma semana em vez de continuar debate.

    HISTORICO, e nao registro unico: a vaga pode mudar de requisito e a mesma
    pessoa ser reanalisada. Guardar so a ultima apagaria a base da decisao que
    ja foi tomada.
    """

    VEREDITO_APTO = 'apto'
    VEREDITO_ATENCAO = 'atencao'
    VEREDITO_INAPTO = 'inapto'
    VEREDITO_INSUFICIENTE = 'insuficiente'

    VEREDITO_CHOICES = [
        (VEREDITO_APTO,         'Apto'),
        (VEREDITO_ATENCAO,      'Apto com ressalvas'),
        (VEREDITO_INAPTO,       'Fora dos requisitos'),
        # Nao e um julgamento do candidato, e do DADO: curriculo ilegivel ou
        # formulario vazio nao dizem nada sobre a pessoa. Misturar com "inapto"
        # faria o RH descartar quem so preencheu pouco.
        (VEREDITO_INSUFICIENTE, 'Informação insuficiente'),
    ]

    candidato = models.ForeignKey(
        'people.Candidato', on_delete=models.CASCADE, related_name='analises',
        verbose_name="Candidato",
    )
    veredito = models.CharField(
        max_length=20, choices=VEREDITO_CHOICES, verbose_name="Veredito sugerido",
    )
    resumo = models.TextField(
        blank=True, default='', verbose_name="Resumo",
        help_text="Duas ou tres linhas sobre o perfil.",
    )
    sinais_de_atencao = models.JSONField(
        default=list, blank=True, verbose_name="Sinais de atenção",
        help_text="Lista de pontos que o RH deve conferir na entrevista.",
    )
    requisitos_avaliados = models.JSONField(
        default=list, blank=True, verbose_name="Requisitos avaliados",
        help_text="Por requisito: texto, se atende e por que. É a "
                  "rastreabilidade da sugestão.",
    )

    modelo = models.CharField(max_length=60, blank=True, default='',
                              verbose_name="Modelo usado")
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_saida = models.PositiveIntegerField(default=0)
    usou_curriculo = models.BooleanField(
        default=False, verbose_name="Leu o currículo",
        help_text="Falso quando o arquivo não pôde ser lido (imagem, PDF "
                  "protegido). A análise sai só com o formulário.",
    )

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='analises_candidato',
        verbose_name="Pedida por",
    )

    class Meta:
        app_label = 'people'
        db_table = 'people_analise_candidato'
        verbose_name = 'Análise de candidato'
        verbose_name_plural = 'Análises de candidato'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tenant', 'candidato', '-criado_em'],
                         name='people_analise_cand_idx'),
        ]

    def __str__(self):
        return f'{self.get_veredito_display()} para {self.candidato}'

    @property
    def total_tokens(self):
        return self.tokens_entrada + self.tokens_saida


class QuadroUnidade(TenantMixin):
    """
    Quantas posicoes de um cargo a unidade quer ter.

    E a moldura contra a qual o recrutamento e lido: "a loja quer 8 atendentes,
    tem 6 ativos e 2 em processo" e a leitura que o franqueado faz. Sem isso,
    vaga aberta e um numero solto; com isso, vira "faltam 2".

    Os derivados (ativos, em processo) NAO sao colunas: sao consulta, calculada
    na hora. Guardar contagem em coluna e o caminho mais curto pra ela divergir
    do que realmente existe, e a divergencia so aparece quando alguem confere na
    mao. Ver `situacao()`.
    """

    unidade = models.ForeignKey(
        'people.Unidade', on_delete=models.CASCADE, related_name='quadros',
        verbose_name="Unidade",
    )
    cargo = models.ForeignKey(
        'people.Cargo', on_delete=models.CASCADE, related_name='quadros',
        verbose_name="Cargo",
    )
    quadro_definido = models.PositiveSmallIntegerField(
        default=0, verbose_name="Quadro definido",
        help_text="Quantas posições deste cargo a unidade deve ter.",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_quadro_unidade'
        verbose_name = 'Quadro da unidade'
        verbose_name_plural = 'Quadros das unidades'
        ordering = ['unidade__nome', 'cargo__nome']
        indexes = [
            models.Index(fields=['tenant', 'unidade'],
                         name='people_quadro_und_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'unidade', 'cargo'],
                name='people_quadro_unico_por_unidade_cargo',
            ),
        ]

    def __str__(self):
        return f'{self.cargo.nome} em {self.unidade.nome}: {self.quadro_definido}'

    def admitidos_ativos(self):
        """
        Colaboradores ativos deste cargo nesta unidade.

        Le do DP (Colaborador), nao do Candidato: quem ja foi admitido e virou
        gente da casa conta como ocupacao real do quadro, e nao como processo.

        `cargo` do Colaborador e FK pra Cargo, entao filtra por FK, nao por
        nome. O campo comecou como texto livre no plano e virou entidade quando
        os prints da Visio mostraram que Cargo tem CRUD.
        """
        from apps.people.models import Colaborador
        from apps.people import estados as estados_dp

        return (Colaborador.all_tenants.filter(
            tenant=self.tenant, unidade=self.unidade, cargo=self.cargo,
            situacao__in=estados_dp.SITUACOES_ATIVAS).count())

    def em_processo(self):
        """Candidatos ainda no pipeline pra vaga deste cargo nesta unidade."""
        return Candidato.all_tenants.filter(
            tenant=self.tenant, unidade=self.unidade,
            vaga__cargo=self.cargo, saida='',
            anonimizado_em__isnull=True).count()

    def situacao(self):
        """
        Foto do quadro pra tela: definido, ativos, em processo e o que falta.

        Um dict pronto, e nao os numeros soltos, pra que o template so exiba. A
        conta de 'faltam' vive aqui e nao no template, senao cada tela que
        mostrar quadro reimplementa e alguma erra.
        """
        ativos = self.admitidos_ativos()
        processo = self.em_processo()
        faltam = max(self.quadro_definido - ativos, 0)
        return {
            'definido': self.quadro_definido,
            'ativos': ativos,
            'em_processo': processo,
            'faltam': faltam,
            'cobre_a_falta': processo >= faltam,
        }


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
    visitas = models.PositiveIntegerField(
        default=0, verbose_name="Visitas",
        help_text="Visitantes unicos que ABRIRAM a pagina. Nao e clique: quem "
                  "clica e desiste antes de carregar nao conta.",
    )
    medindo_visitas_desde = models.DateTimeField(
        # `default` e nao `auto_now_add`: link criado agora ja nasce medindo, e
        # os antigos foram marcados pela migration 0018. Com auto_now_add nao
        # daria pra distinguir um do outro.
        default=timezone.now,
        null=True, blank=True, verbose_name="Medindo visitas desde",
        help_text="Link criado antes da medicao tem candidatura sem visita "
                  "correspondente, e a taxa mentiria. Guardar a data permite "
                  "dizer isso em vez de exibir um numero quebrado.",
    )
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

    @property
    def taxa_confiavel(self):
        """
        Se da pra exibir a taxa sem mentir.

        Link criado ANTES da medicao comecar ja tem candidatura sem visita
        correspondente. Exibir a divisao ali daria numero acima de 100%, ou uma
        taxa inventada, e um numero que nasce quebrado destrui a confianca na
        tela inteira. Nestes casos a tela diz "medindo desde <data>".
        """
        return bool(self.medindo_visitas_desde) and self.visitas >= self.candidaturas

    @property
    def taxa_conversao(self):
        """
        Quantos por cento dos visitantes se candidataram. None se nao da pra dizer.

        E ESTE o numero que responde "qual canal vale o dinheiro". Contagem crua
        de visita nao responde: um canal com 200 visitas e 2 candidaturas e pior
        que um com 30 e 8, e so a taxa mostra.
        """
        if not self.taxa_confiavel or not self.visitas:
            return None
        return round(self.candidaturas * 100 / self.visitas, 1)

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

        # Condicoes estruturadas: cada uma so aparece se preenchida, pra o texto
        # nao ficar com "Turno: " vazio pendurado.
        for rotulo, valor in [
            ('Turno', self.vaga.get_turno_display() if self.vaga.turno else ''),
            ('Modelo', self.vaga.get_modelo_trabalho_display() if self.vaga.modelo_trabalho else ''),
            ('Carga horária', self.vaga.carga_horaria),
            ('Remuneração', self.vaga.remuneracao),
        ]:
            if valor:
                linhas.append(f'{rotulo}: {valor}')

        requisitos = list(self.vaga.requisitos_do_anuncio())
        if requisitos:
            linhas.append('')
            linhas.append('O que buscamos:')
            linhas += [f'- {r.texto}' for r in requisitos]

        if self.telefone_contato:
            linhas.append('')
            linhas.append(f'Dúvidas: {self.telefone_contato}')

        return '\n'.join(linhas)
