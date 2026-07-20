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
from django.conf import settings
from django.db import models

from apps.sistema.mixins import TenantMixin


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
