"""
Models do modulo People (gestao de pessoas).

Unidade           = loja ou filial dentro do tenant. Quase tudo em People e
                    escopado por unidade: prazo de experiencia, checklist de
                    admissao e link de auto cadastro variam por loja.
ConfiguracaoPeople= os defaults do tenant. A Unidade sobrescreve o que quiser
                    deixando o campo nulo pra herdar. Resolver sempre por
                    `apps.people.services.config_efetiva(unidade)`, nunca lendo
                    os campos direto.

Multi-tenant via TenantMixin. Permissoes em
apps/people/management/commands/seed_people_funcionalidades.py:
- people.ver
- people.gerir_unidades
- people.criar_colaborador
- people.mover_colaborador
- people.gerir_links
"""
import re
import threading
from contextlib import contextmanager

from django.conf import settings
from django.db import models

from apps.people import estados
from apps.people.excecoes import PeopleError, TransicaoNaoAutorizada
from apps.sistema.mixins import TenantMixin


# ── Guarda da situacao ───────────────────────────────────────────────────────
#
# `situacao` so muda por `apps.people.services.mover_situacao()`, porque toda
# mudanca precisa gerar historico e telemetria. A guarda abaixo transforma isso
# de convencao em garantia: um `save()` que mexeu na situacao sem autorizacao
# levanta excecao em vez de gravar calado.
#
# Ela nao cobre `queryset.update(situacao=...)`, que nao passa por save(). Esse
# buraco e fechado por varredura de codigo em tests/test_people_contrato.py.

_guarda = threading.local()


@contextmanager
def sem_guarda_de_situacao():
    """
    Desliga a guarda no bloco. Use so em data migration, seed e importacao,
    onde nao ha transicao de dominio acontecendo, so carga de dado.

    Fora desses casos, se voce precisou disto, o certo e mover_situacao().
    """
    anterior = getattr(_guarda, 'desligada', False)
    _guarda.desligada = True
    try:
        yield
    finally:
        _guarda.desligada = anterior


def _guarda_ativa():
    return not getattr(_guarda, 'desligada', False)


class ConfiguracaoPeople(TenantMixin):
    """Defaults do modulo por tenant. Um registro por tenant."""

    dias_experiencia_padrao = models.PositiveSmallIntegerField(
        default=90, verbose_name="Dias de experiencia (total)",
        help_text="Duracao total do periodo de experiencia, em dias corridos.",
    )
    dias_primeiro_periodo_experiencia = models.PositiveSmallIntegerField(
        default=45, verbose_name="Dias do primeiro periodo",
        help_text="Primeiro trecho da experiencia. Ex: 45 em um 45 mais 45.",
    )
    exige_cpf_no_autocadastro = models.BooleanField(
        default=True, verbose_name="Exigir CPF no auto cadastro",
        help_text="CPF e o que garante o dedup. Afrouxar so quando a operacao exigir.",
    )
    texto_consentimento_lgpd = models.TextField(
        blank=True, default='', verbose_name="Texto do consentimento LGPD",
        help_text="Exibido no formulario publico. O colaborador precisa aceitar.",
    )
    versao_consentimento_lgpd = models.CharField(
        max_length=20, default='1.0', verbose_name="Versao do consentimento",
        help_text="Gravada junto do aceite. Mudou o texto, suba a versao.",
    )
    link_expira_em_dias = models.PositiveSmallIntegerField(
        default=0, verbose_name="Validade do link de cadastro (dias)",
        help_text="0 significa que o link nao expira sozinho.",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_configuracao'
        verbose_name = 'Configuracao do People'
        verbose_name_plural = 'Configuracoes do People'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant'], name='people_configuracao_unica_por_tenant',
            ),
        ]

    def __str__(self):
        return f'Configuracao People ({self.tenant})'

    @classmethod
    def get_config(cls, tenant):
        """Retorna a configuracao do tenant, criando com os defaults se faltar."""
        config, _ = cls.all_tenants.get_or_create(tenant=tenant)
        return config


class Unidade(TenantMixin):
    """
    Loja ou filial. O colaborador pertence a uma unidade, e o acesso do gestor
    e recortado por ela.

    Os campos de configuracao nulos herdam do tenant. Ler sempre via
    `config_efetiva(unidade)`, que faz o merge.
    """

    nome = models.CharField(max_length=120, verbose_name="Nome")
    codigo = models.SlugField(
        max_length=40, verbose_name="Codigo",
        help_text="Identificador curto e estavel. Ex: loja-centro.",
    )
    cnpj = models.CharField(max_length=18, blank=True, default='', verbose_name="CNPJ")

    cep = models.CharField(max_length=9, blank=True, default='', verbose_name="CEP")
    rua = models.CharField(max_length=200, blank=True, default='', verbose_name="Rua")
    numero = models.CharField(max_length=20, blank=True, default='', verbose_name="Numero")
    complemento = models.CharField(max_length=100, blank=True, default='', verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, default='', verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, default='', verbose_name="Cidade")
    estado = models.CharField(max_length=2, blank=True, default='', verbose_name="Estado")
    telefone = models.CharField(max_length=20, blank=True, default='', verbose_name="Telefone")

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='people_unidades_geridas', verbose_name="Responsavel",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativa")

    # Overrides da ConfiguracaoPeople. Nulo significa herdar do tenant.
    dias_experiencia_padrao = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Dias de experiencia (override)",
    )
    dias_primeiro_periodo_experiencia = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name="Dias do primeiro periodo (override)",
    )
    exige_cpf_no_autocadastro = models.BooleanField(
        null=True, blank=True, verbose_name="Exigir CPF no auto cadastro (override)",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_unidade'
        verbose_name = 'Unidade'
        verbose_name_plural = 'Unidades'
        ordering = ['nome']
        indexes = [
            models.Index(fields=['tenant', 'ativo'], name='people_und_tenant_ativo_idx'),
            models.Index(fields=['tenant', 'nome'], name='people_und_tenant_nome_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'codigo'], name='people_unidade_codigo_unico_por_tenant',
            ),
        ]

    def __str__(self):
        return self.nome


TIPO_CHAVE_PIX_CHOICES = [
    ('cpf',       'CPF'),
    ('celular',   'Celular'),
    ('email',     'Email'),
    ('aleatoria', 'Chave aleatoria'),
]

REGIME_CONTRATACAO_CHOICES = [
    ('clt',        'CLT'),
    ('pj',         'PJ'),
    ('estagio',    'Estagio'),
    ('aprendiz',   'Jovem aprendiz'),
    ('temporario', 'Temporario'),
    ('freelancer', 'Freelancer'),
]

ORIGEM_CADASTRO_CHOICES = [
    ('rh',           'RH'),
    ('link_publico', 'Link publico'),
    ('importacao',   'Importacao'),
    ('api',          'API'),
]

ORIGEM_TRANSICAO_CHOICES = [
    ('painel',       'Painel'),
    ('link_publico', 'Link publico'),
    ('automacao',    'Automacao'),
    ('cron',         'Cron'),
    ('importacao',   'Importacao'),
]


class Colaborador(TenantMixin):
    """
    Cadastro mestre de pessoa. FONTE UNICA do modulo People.

    Toda Tool que precisar criar colaborador (feedback, recrutamento,
    treinamento) passa por `apps.people.services.registrar_colaborador`, que
    pesquisa antes de criar e reutiliza quem ja existe. Ninguem instancia esta
    classe direto fora de `apps/people/services/`.

    Duas particularidades que parecem descuido e nao sao:

    1. NAO existe campo `ativo`. Desativar e gravar `situacao='desligado'`, o
       que preserva a linha e viabiliza readmissao. Dois campos seriam duas
       fontes da verdade e um dia divergiriam. Use `esta_ativo`.

    2. `cpf` e o unico campo do app com `null=True` em vez de `default=''`.
       Deliberado: a unique de CPF por tenant e o que sustenta o dedup, e com
       string vazia a segunda pessoa sem CPF colidiria com a primeira. Em NULL,
       o Postgres trata cada ausencia como distinta.
    """

    # ── Identidade e dedup ───────────────────────────────────────────────
    cpf = models.CharField(
        max_length=11, null=True, blank=True, default=None, verbose_name="CPF",
        help_text="So digitos. Nulo quando ausente, nunca string vazia.",
    )
    cpf_valido = models.BooleanField(
        default=False, verbose_name="CPF com digito verificador valido",
        help_text="CPF invalido nao bloqueia o cadastro, cai na fila de revisao.",
    )
    rg = models.CharField(max_length=20, blank=True, default='', verbose_name="RG")
    pis = models.CharField(max_length=11, blank=True, default='', verbose_name="PIS")

    # ── Contato ──────────────────────────────────────────────────────────
    telefone = models.CharField(
        max_length=20, blank=True, default='', verbose_name="Telefone",
        help_text="E.164 sem o mais. Ex: 5586999998888.",
    )
    email = models.EmailField(blank=True, default='', verbose_name="Email")

    # ── Pessoa ───────────────────────────────────────────────────────────
    nome_completo = models.CharField(max_length=200, verbose_name="Nome completo")
    primeiro_nome = models.CharField(
        max_length=60, blank=True, default='', verbose_name="Primeiro nome",
        help_text="Derivado do nome completo quando vazio.",
    )
    data_nascimento = models.DateField(null=True, blank=True, verbose_name="Data de nascimento")

    cep = models.CharField(max_length=9, blank=True, default='', verbose_name="CEP")
    rua = models.CharField(max_length=200, blank=True, default='', verbose_name="Rua")
    numero = models.CharField(max_length=20, blank=True, default='', verbose_name="Numero")
    complemento = models.CharField(max_length=100, blank=True, default='', verbose_name="Complemento")
    bairro = models.CharField(max_length=100, blank=True, default='', verbose_name="Bairro")
    cidade = models.CharField(max_length=100, blank=True, default='', verbose_name="Cidade")
    estado = models.CharField(max_length=2, blank=True, default='', verbose_name="Estado")

    tipo_chave_pix = models.CharField(
        max_length=20, choices=TIPO_CHAVE_PIX_CHOICES, blank=True, default='',
        verbose_name="Tipo de chave Pix",
    )
    chave_pix = models.CharField(max_length=140, blank=True, default='', verbose_name="Chave Pix")

    # ── Vinculo e ciclo de vida ──────────────────────────────────────────
    unidade = models.ForeignKey(
        Unidade, on_delete=models.PROTECT, related_name='colaboradores',
        verbose_name="Unidade",
        help_text="PROTECT de proposito: apagar loja nao pode orfanar pessoa. "
                  "Pra tirar de circulacao, desative a unidade.",
    )
    situacao = models.CharField(
        max_length=20, choices=estados.SITUACOES, default=estados.SITUACAO_CADASTRO,
        db_index=True, verbose_name="Situacao",
        help_text="So muda por mover_situacao(). Ver apps/people/estados.py.",
    )
    ponto_entrada = models.CharField(
        max_length=20, choices=estados.PONTOS_ENTRADA_CHOICES,
        default=estados.ENTRADA_SO_CADASTRO, verbose_name="Ponto de entrada",
        help_text="Por qual porta a pessoa entrou no ciclo. Nao muda depois.",
    )
    origem_cadastro = models.CharField(
        max_length=20, choices=ORIGEM_CADASTRO_CHOICES, default='rh',
        verbose_name="Origem do cadastro",
    )
    pendente_revisao = models.BooleanField(
        default=False, verbose_name="Pendente de revisao do RH",
        help_text="Marcado quando falta CPF, o CPF e invalido, ou houve suspeita "
                  "de duplicata nao resolvida.",
    )

    # ── Consentimento LGPD ───────────────────────────────────────────────
    consentimento_lgpd = models.BooleanField(default=False, verbose_name="Consentimento LGPD")
    consentimento_lgpd_em = models.DateTimeField(null=True, blank=True, verbose_name="Consentimento em")
    consentimento_lgpd_ip = models.CharField(max_length=64, blank=True, default='', verbose_name="IP do consentimento")
    consentimento_lgpd_versao = models.CharField(max_length=20, blank=True, default='', verbose_name="Versao do texto aceito")
    consentimento_lgpd_user_agent = models.CharField(max_length=300, blank=True, default='', verbose_name="User agent do consentimento")

    # ── Vinculo trabalhista ──────────────────────────────────────────────
    # Preenchidos pelas fases seguintes (admissao, experiencia, desligamento),
    # mas criados agora porque a maquina de estados ja depende deles: entrar em
    # experiencia exige data_admissao, e o dedup precisa saber se a pessoa
    # desligada pode voltar.
    cargo = models.CharField(
        max_length=120, blank=True, default='', verbose_name="Cargo",
        help_text="Texto livre por enquanto. Vira FK quando Recrutamento chegar.",
    )
    regime_contratacao = models.CharField(
        max_length=20, choices=REGIME_CONTRATACAO_CHOICES, blank=True, default='',
        verbose_name="Regime de contratacao",
    )
    data_admissao = models.DateField(null=True, blank=True, verbose_name="Data de admissao")
    data_fim_experiencia = models.DateField(null=True, blank=True, verbose_name="Fim da experiencia")
    prorrogacoes_experiencia = models.PositiveSmallIntegerField(
        default=0, verbose_name="Prorrogacoes da experiencia",
    )
    data_desligamento = models.DateField(null=True, blank=True, verbose_name="Data de desligamento")
    motivo_desligamento = models.CharField(max_length=40, blank=True, default='', verbose_name="Motivo do desligamento")
    elegivel_recontratacao = models.BooleanField(
        default=True, verbose_name="Elegivel a recontratacao",
        help_text="False impede o dedup de reativar a pessoa numa readmissao.",
    )

    # ── Auditoria ────────────────────────────────────────────────────────
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='people_colaboradores_criados', verbose_name="Criado por",
    )
    observacoes = models.TextField(blank=True, default='', verbose_name="Observacoes")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_colaborador'
        verbose_name = 'Colaborador'
        verbose_name_plural = 'Colaboradores'
        ordering = ['nome_completo']
        indexes = [
            models.Index(fields=['tenant', 'situacao'], name='people_col_tenant_sit_idx'),
            models.Index(fields=['tenant', 'unidade', 'situacao'], name='people_col_tenant_und_idx'),
            models.Index(fields=['tenant', 'cpf'], name='people_col_tenant_cpf_idx'),
            models.Index(fields=['tenant', 'telefone'], name='people_col_tenant_fone_idx'),
            models.Index(fields=['tenant', 'pendente_revisao', '-criado_em'],
                         name='people_col_tenant_rev_idx'),
        ]
        constraints = [
            # O dedup da regra de fonte unica. Ausente e NULL (varias pessoas
            # podem estar sem CPF), presente e unico dentro do tenant.
            models.UniqueConstraint(
                fields=['tenant', 'cpf'], name='people_colaborador_cpf_unico_por_tenant',
            ),
            # Nao e decorativa: e ela que impede alguem de gravar '' ou CPF
            # mascarado e detonar a unique acima com erro incompreensivel.
            models.CheckConstraint(
                condition=models.Q(cpf__isnull=True) | models.Q(cpf__regex=r'^\d{11}$'),
                name='people_colaborador_cpf_formato',
            ),
            models.CheckConstraint(
                condition=models.Q(situacao__in=estados.VALORES_SITUACAO),
                name='people_colaborador_situacao_valida',
            ),
        ]

    def __str__(self):
        return self.nome_completo

    # ── Guarda da situacao ───────────────────────────────────────────────

    @classmethod
    def from_db(cls, db, field_names, values):
        """Memoriza a situacao que veio do banco, pra guarda do save() comparar.

        Custo zero de query. O `in field_names` cobre `.only()` e `.defer()`,
        que trazem a instancia sem o campo.
        """
        instancia = super().from_db(db, field_names, values)
        if 'situacao' in field_names:
            instancia._situacao_carregada = instancia.situacao
        return instancia

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._situacao_carregada = self.situacao

    def save(self, *args, **kwargs):
        anterior = getattr(self, '_situacao_carregada', None)
        mudou = (
            self.pk
            and anterior is not None
            and anterior != self.situacao
        )
        if mudou and _guarda_ativa() and not getattr(self, '_transicao_autorizada', False):
            raise TransicaoNaoAutorizada(
                f'Tentativa de mudar situacao de "{anterior}" para "{self.situacao}" '
                f'sem passar por mover_situacao(). Toda transicao precisa gerar '
                f'historico e telemetria.'
            )

        # CPF sempre normalizado: so digitos, e None quando nao da 11. E isto
        # que faz a unique e a check constraint funcionarem.
        digitos = re.sub(r'\D', '', self.cpf or '')
        self.cpf = digitos if len(digitos) == 11 else None

        if not self.primeiro_nome and self.nome_completo:
            self.primeiro_nome = self.nome_completo.strip().split(' ')[0][:60]

        super().save(*args, **kwargs)
        self._situacao_carregada = self.situacao
        self._transicao_autorizada = False

    def delete(self, *args, **kwargs):
        """
        Colaborador nao se apaga, se desliga.

        Apagar destroi historico de feedback, de admissao e a propria
        possibilidade de readmissao. Se voce precisa remover do board, a
        transicao e pra `desligado`.
        """
        if not getattr(self, '_apagar_de_verdade', False):
            raise PeopleError(
                'Colaborador nao se apaga, se desliga. Use mover_situacao(col, '
                '"desligado"). Pra remocao real (LGPD, direito ao esquecimento), '
                'marque _apagar_de_verdade=True explicitamente.'
            )
        return super().delete(*args, **kwargs)

    # ── Consultas de instancia ───────────────────────────────────────────

    @property
    def esta_ativo(self):
        """Gente da casa. Desligado e freelancer ficam de fora."""
        return self.situacao in estados.SITUACOES_ATIVAS

    @property
    def cpf_mascarado(self):
        """CPF pra log e telemetria, sem expor o documento inteiro."""
        if not self.cpf:
            return ''
        return f'***.***.**{self.cpf[-3:-2]}-{self.cpf[-2:]}'

    @property
    def situacao_rotulo(self):
        return estados.rotulo(self.situacao)


class HistoricoSituacao(TenantMixin):
    """
    Trilha de toda transicao de fase do colaborador.

    E a aba "Historico" da ficha e, ao mesmo tempo, a fonte primaria de
    telemetria do modulo: "tempo medio de cadastro ate efetivado" e um group by
    aqui, sem depender de ferramenta externa. A spec de origem nao tinha nenhum
    evento instrumentado, e essa lacuna nasce fechada.
    """

    colaborador = models.ForeignKey(
        Colaborador, on_delete=models.CASCADE, related_name='historico_situacao',
        verbose_name="Colaborador",
    )
    de = models.CharField(
        max_length=20, blank=True, default='', verbose_name="Situacao anterior",
        help_text="Vazio quando e a entrada na maquina de estados.",
    )
    para = models.CharField(max_length=20, verbose_name="Situacao nova")
    motivo = models.CharField(max_length=200, blank=True, default='', verbose_name="Motivo")
    dados = models.JSONField(
        default=dict, blank=True, verbose_name="Snapshot da transicao",
        help_text="O que a transicao mexeu, inclusive o que foi limpo.",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='people_transicoes', verbose_name="Usuario",
    )
    origem = models.CharField(
        max_length=20, choices=ORIGEM_TRANSICAO_CHOICES, default='painel',
        verbose_name="Origem",
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'people'
        db_table = 'people_historico_situacao'
        verbose_name = 'Historico de situacao'
        verbose_name_plural = 'Historico de situacoes'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['tenant', 'colaborador', '-criado_em'],
                         name='people_hist_col_idx'),
            models.Index(fields=['tenant', 'para', '-criado_em'],
                         name='people_hist_para_idx'),
        ]

    def __str__(self):
        origem = estados.rotulo(self.de) if self.de else 'entrada'
        return f'{self.colaborador_id}: {origem} para {estados.rotulo(self.para)}'
