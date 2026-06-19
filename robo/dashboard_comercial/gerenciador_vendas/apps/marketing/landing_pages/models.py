"""
Landing Pages — builder componentizado de paginas publicas.

Fase 1: LandingPage + LandingSubmissao + renderer estatico.
Fase 2 (proxima): FormularioLanding como entidade reusavel com campos componentizados.

Conceitos:
- LandingPage: 1 pagina publica, com slug por tenant, layout em blocos_json
- Blocos: cada bloco do catalogo (registry) tem JSON schema proprio.
  Cada entrada em blocos_json e um dict: {"tipo": "hero", "props": {...}}
- LandingSubmissao: cada submit do form da LP vira aqui + LeadProspecto
"""
from django.conf import settings
from django.db import models

from apps.sistema.mixins import TenantMixin


STATUS_CHOICES = [
    ('rascunho', 'Rascunho'),
    ('publicada', 'Publicada'),
    ('arquivada', 'Arquivada'),
]


class LandingPage(TenantMixin):
    """Pagina publica composta por blocos configuraveis."""

    nome = models.CharField(
        max_length=200, verbose_name='Nome interno',
        help_text='Nome para identificar a LP no painel. Nao aparece pro publico.',
    )
    slug = models.SlugField(
        max_length=80, verbose_name='Slug da URL',
        help_text='Parte final da URL publica: /p/<tenant>/<slug>/',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='rascunho',
        db_index=True, verbose_name='Status',
    )

    # Conteudo
    config_json = models.JSONField(
        default=dict, blank=True,
        verbose_name='Configuracoes globais',
        help_text='Largura max, cor de fundo, fonte. Aplicadas no <body> da LP.',
    )
    blocos_json = models.JSONField(
        default=list, blank=True,
        verbose_name='Blocos da pagina',
        help_text='Array ordenado: [{"tipo": "hero", "props": {...}}, ...]',
    )
    html_compilado = models.TextField(
        blank=True, default='',
        verbose_name='HTML compilado (cache)',
        help_text='HTML final pre-renderizado pra servir em prod sem hit no template.',
    )

    # SEO
    seo_title = models.CharField(max_length=200, blank=True, default='', verbose_name='SEO title')
    seo_description = models.CharField(max_length=300, blank=True, default='', verbose_name='SEO description')
    og_image = models.ImageField(upload_to='landing_pages/og/', null=True, blank=True, verbose_name='Imagem OpenGraph')

    # Tracking (pixels — Fase 6)
    pixels = models.JSONField(
        default=dict, blank=True,
        verbose_name='Pixels (GA4, Meta, etc.)',
        help_text='{google_analytics: "G-XXX", meta_pixel: "...", tiktok_pixel: "..."}',
    )

    # Atribuicao
    campanha_padrao = models.ForeignKey(
        'campanhas.CampanhaTrafego',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='landing_pages',
        verbose_name='Campanha padrao',
        help_text='LP sem UTM atribui essa campanha aos leads.',
    )

    # Auditoria
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='landing_pages_criadas',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    publicado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'marketing_landing_page'
        verbose_name = 'Landing Page'
        verbose_name_plural = 'Landing Pages'
        ordering = ['-atualizado_em']
        unique_together = [('tenant', 'slug')]
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'slug']),
        ]

    def __str__(self):
        return f'{self.nome} ({self.slug})'


class LandingSubmissao(TenantMixin):
    """Cada submit do form da LP vira aqui + cria LeadProspecto."""

    landing = models.ForeignKey(
        LandingPage, on_delete=models.CASCADE,
        related_name='submissoes',
        verbose_name='Landing page',
    )
    lead = models.ForeignKey(
        'leads.LeadProspecto', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='landing_submissoes',
        verbose_name='Lead criado',
    )
    dados_form = models.JSONField(
        default=dict, blank=True,
        verbose_name='Dados do form (cru)',
    )

    # UTM
    utm_source = models.CharField(max_length=100, blank=True, default='')
    utm_medium = models.CharField(max_length=100, blank=True, default='')
    utm_campaign = models.CharField(max_length=200, blank=True, default='')
    utm_content = models.CharField(max_length=200, blank=True, default='')
    utm_term = models.CharField(max_length=200, blank=True, default='')

    # Rastreio
    ip_origem = models.CharField(max_length=64, blank=True, default='')
    user_agent = models.CharField(max_length=500, blank=True, default='')
    referrer = models.TextField(blank=True, default='')

    enviado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'marketing_landing_submissao'
        verbose_name = 'Submissao de Landing Page'
        verbose_name_plural = 'Submissoes de Landing Page'
        ordering = ['-enviado_em']
        indexes = [
            models.Index(fields=['tenant', 'landing', 'enviado_em']),
            models.Index(fields=['tenant', 'enviado_em']),
        ]

    def __str__(self):
        return f'Submissao {self.pk} — {self.landing.slug}'
