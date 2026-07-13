"""
Models do editor de Deck (apresentacoes).

Deck  = colecao ordenada de slides, montada a partir dos widgets do modulo de
        relatorios (apps.relatorios). Multi-tenant via TenantMixin.
Slide = um canvas 16:9 com blocos posicionados numa grade (GridStack).
SlideBloco = um bloco no slide: widget (grafico/KPI de um dashboard), texto,
        KPI avulso, imagem ou titulo de secao.

Snapshot: ao "congelar" o deck, cada bloco tipo=widget guarda em `dados_snapshot`
o resultado do WidgetQueryBuilder daquele momento, pra apresentacao/PDF nao
mudar depois. Reuso total da engine de relatorios (nada de grafico reinventado).
"""
from django.conf import settings
from django.db import models

from apps.sistema.mixins import TenantMixin


class Deck(TenantMixin):
    """Apresentacao = colecao ordenada de slides."""
    nome = models.CharField(max_length=120, verbose_name='Nome')
    descricao = models.TextField(blank=True, default='', verbose_name='Descricao')
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='decks_criados', verbose_name='Criado por',
    )
    compartilhado = models.BooleanField(
        default=False, verbose_name='Compartilhado',
        help_text='Se True, todos do tenant veem (so admin marca).',
    )
    tema = models.JSONField(
        default=dict, blank=True, verbose_name='Tema',
        help_text='JSON: {cor_fundo, cor_texto, fonte, cor_primaria, logo_url}.',
    )
    config = models.JSONField(
        default=dict, blank=True, verbose_name='Config',
        help_text='JSON: {canvas:{w,h,cols,rows}} e afins.',
    )
    snapshot_em = models.DateTimeField(
        null=True, blank=True, verbose_name='Snapshot congelado em',
        help_text='Momento do ultimo "Congelar" (dados dos blocos widget).',
    )
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'decks_deck'
        verbose_name = 'Deck'
        verbose_name_plural = 'Decks'
        ordering = ['ordem', 'nome']
        indexes = [
            models.Index(fields=['tenant', 'compartilhado']),
            models.Index(fields=['tenant', 'criado_por']),
        ]

    def __str__(self):
        return f'{self.nome} ({self.tenant.slug if self.tenant else "?"})'


class Slide(models.Model):
    """Um slide do deck. Tenant vem via deck (padrao Widget)."""
    deck = models.ForeignKey(
        Deck, on_delete=models.CASCADE, related_name='slides', verbose_name='Deck',
    )
    ordem = models.PositiveSmallIntegerField(default=0, db_index=True, verbose_name='Ordem')
    titulo = models.CharField(max_length=120, blank=True, default='', verbose_name='Titulo')
    fundo = models.JSONField(
        default=dict, blank=True, verbose_name='Fundo',
        help_text='Override por slide: {cor, imagem_url}.',
    )
    notas = models.TextField(blank=True, default='', verbose_name='Notas do apresentador')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'decks_slide'
        verbose_name = 'Slide'
        verbose_name_plural = 'Slides'
        ordering = ['deck', 'ordem', 'id']

    def __str__(self):
        return f'Slide {self.ordem} de {self.deck_id}'


class SlideBloco(models.Model):
    """Um bloco posicionado num slide."""
    TIPO_CHOICES = [
        ('widget', 'Widget (grafico/KPI)'),
        ('texto', 'Texto'),
        ('kpi', 'KPI em destaque'),
        ('imagem', 'Imagem'),
        ('titulo_secao', 'Titulo de secao'),
    ]

    slide = models.ForeignKey(
        Slide, on_delete=models.CASCADE, related_name='blocos', verbose_name='Slide',
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='texto', verbose_name='Tipo')
    widget = models.ForeignKey(
        'relatorios.Widget', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='blocos_deck', verbose_name='Widget',
        help_text='So pra tipo=widget. SET_NULL: se o widget for excluido, o bloco '
                  'sobrevive e ainda renderiza o dados_snapshot.',
    )
    dados_snapshot = models.JSONField(
        default=dict, blank=True, verbose_name='Dados congelados',
        help_text='{labels, series, total, meta} do builder no momento do congelar.',
    )
    conteudo = models.JSONField(
        default=dict, blank=True, verbose_name='Conteudo',
        help_text='Por tipo: texto={html,align}, kpi={label,valor,...}, imagem={url,fit}, '
                  'titulo_secao={texto,subtitulo}, widget={titulo_override,viz_override,dias,fonte}.',
    )
    layout = models.JSONField(
        default=dict, blank=True, verbose_name='Layout',
        help_text='Posicao na grade do slide: {x,y,w,h} (mesma forma de Widget.layout).',
    )
    estilo = models.JSONField(
        default=dict, blank=True, verbose_name='Estilo',
        help_text='{cor_fundo, cor_texto, radius, sombra, align}.',
    )
    ordem = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'decks_slidebloco'
        verbose_name = 'Bloco de slide'
        verbose_name_plural = 'Blocos de slide'
        ordering = ['slide', 'ordem', 'id']

    def __str__(self):
        return f'{self.get_tipo_display()} (slide {self.slide_id})'
