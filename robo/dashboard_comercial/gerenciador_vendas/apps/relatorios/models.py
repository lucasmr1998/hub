"""
Models do sistema de relatorios self-service (estilo Hubspot).

Dashboard = container que agrupa widgets, com layout em grid + filtros globais.
Widget    = uma visualizacao (numero, barra, linha, pizza, tabela, funil)
            configurada via Data Source + Metrica + Agrupamento + Filtros.

Multi-tenant via TenantMixin. Permissoes em apps/sistema/seed_funcionalidades.py:
- relatorios.ver_dashboards
- relatorios.criar_dashboard
- relatorios.compartilhar_dashboard
"""
from django.conf import settings
from django.db import models

from apps.sistema.mixins import TenantMixin


VISUALIZACAO_CHOICES = [
    ('numero', 'Numero grande'),
    ('barra',  'Barra'),
    ('linha',  'Linha (serie temporal)'),
    ('pizza',  'Pizza'),
    ('tabela', 'Tabela'),
    ('funil',  'Funil'),
]


class Dashboard(TenantMixin):
    """
    Dashboard = container que reune varios widgets num layout em grid.
    Pessoal (criado_por) ou compartilhado (todos do tenant veem).
    """
    nome = models.CharField(max_length=120, verbose_name='Nome')
    descricao = models.TextField(blank=True, default='', verbose_name='Descricao')
    icone = models.CharField(
        max_length=50, default='bi-bar-chart',
        verbose_name='Icone (Bootstrap Icons)',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='dashboards_criados',
        verbose_name='Criado por',
    )
    compartilhado = models.BooleanField(
        default=False,
        verbose_name='Compartilhado',
        help_text='Se True, todos os usuarios do tenant veem (so admin pode marcar).',
    )
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')
    config = models.JSONField(
        default=dict, blank=True,
        verbose_name='Config (filtros globais, layout grid)',
        help_text='JSON com filtros padrao + layout do GridStack.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'relatorios_dashboard'
        verbose_name = 'Dashboard'
        verbose_name_plural = 'Dashboards'
        ordering = ['ordem', 'nome']
        unique_together = [('tenant', 'criado_por', 'nome')]
        indexes = [
            models.Index(fields=['tenant', 'compartilhado']),
            models.Index(fields=['tenant', 'criado_por']),
        ]

    def __str__(self):
        return f'{self.nome} ({self.tenant.slug if self.tenant else "?"})'


class Widget(models.Model):
    """
    Widget = 1 visualizacao (numero/barra/etc) dentro de um Dashboard.
    Config declarativa: data_source + metrica + agrupamento + filtros + visualizacao.

    Engine resolve a query via `apps.relatorios.query_builder.WidgetQueryBuilder`.
    """
    dashboard = models.ForeignKey(
        Dashboard, on_delete=models.CASCADE,
        related_name='widgets',
        verbose_name='Dashboard',
    )
    titulo = models.CharField(max_length=120, verbose_name='Titulo')
    descricao = models.CharField(max_length=255, blank=True, default='')
    data_source = models.CharField(
        max_length=50,
        verbose_name='Data Source',
        help_text='Chave do registry em apps.relatorios.data_sources (ex: "oportunidade", "lead").',
    )
    metrica = models.JSONField(
        default=dict,
        verbose_name='Metrica',
        help_text='Ex: {"tipo": "count"} ou {"tipo": "sum", "campo": "valor_estimado"}.',
    )
    agrupamento = models.JSONField(
        default=dict, blank=True,
        verbose_name='Agrupamento',
        help_text='Ex: {"dimensao": "estagio.nome"} ou {"dimensao": "data_criacao", "granularidade": "mes"}.',
    )
    filtros = models.JSONField(
        default=list, blank=True,
        verbose_name='Filtros',
        help_text='Lista: [{"campo": X, "operador": "igual|diferente|maior|menor|entre|contem", "valor": Y}].',
    )
    visualizacao = models.CharField(
        max_length=30, choices=VISUALIZACAO_CHOICES,
        default='numero',
        verbose_name='Tipo de visualizacao',
    )
    layout = models.JSONField(
        default=dict, blank=True,
        verbose_name='Layout no grid',
        help_text='Posicao no GridStack: {x, y, w, h}.',
    )
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')
    config_extra = models.JSONField(
        default=dict, blank=True,
        verbose_name='Config extra',
        help_text='Ex: {"cor_serie": "#2563eb", "limite_top": 10}.',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'relatorios_widget'
        verbose_name = 'Widget'
        verbose_name_plural = 'Widgets'
        ordering = ['dashboard', 'ordem', 'id']

    def __str__(self):
        return f'{self.titulo} ({self.visualizacao})'
