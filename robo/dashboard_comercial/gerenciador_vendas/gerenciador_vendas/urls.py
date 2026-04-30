"""
URL configuration for gerenciador_vendas project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView, RedirectView


class DesignSystemComponentsView(TemplateView):
    """Showcase dos componentes do DS. Context com dados dummy pros exemplos."""
    template_name = 'design_system_components.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tabs_line'] = [
            {'id': 'aba-dados', 'label': 'Dados', 'icon': 'bi-info-circle', 'active': True},
            {'id': 'aba-modulos', 'label': 'Modulos', 'icon': 'bi-grid', 'badge': '4'},
            {'id': 'aba-usuarios', 'label': 'Usuarios', 'icon': 'bi-people', 'badge': '12'},
            {'id': 'aba-integracoes', 'label': 'Integracoes', 'icon': 'bi-plug'},
        ]
        ctx['tabs_pills'] = [
            {'id': 'p1', 'label': 'Todos', 'active': True},
            {'id': 'p2', 'label': 'Ativos', 'badge': '8'},
            {'id': 'p3', 'label': 'Inativos', 'badge': '2'},
            {'id': 'p4', 'label': 'Arquivados'},
        ]
        ctx['crumbs'] = [
            {'label': 'Hubtrix Admin', 'href': '/aurora-admin/'},
            {'label': 'Tenants', 'href': '/aurora-admin/tenants/'},
            {'label': 'Megalink'},
        ]
        ctx['accordion_items'] = [
            {'id': 'sec-1', 'title': 'O que esta no escopo', 'icon': 'bi-check-circle',
             'body': '<p style="margin:0;">Conteudo expansivel. Clica pra abrir, clica de novo pra fechar.</p>',
             'open': True},
            {'id': 'sec-2', 'title': 'Requisitos tecnicos', 'icon': 'bi-gear',
             'body': '<p style="margin:0;">Django 5.2, PostgreSQL, Redis. <strong>Obrigatorio.</strong></p>'},
            {'id': 'sec-3', 'title': 'Perguntas frequentes', 'icon': 'bi-question-circle',
             'body': '<p style="margin:0;">Body pode conter HTML arbitrario — listas, tabelas, botoes, etc.</p>'},
        ]
        ctx['filter_tabs_demo'] = [
            {'label': 'Todos', 'url': '#', 'active': True, 'count': 24},
            {'label': 'Ativos', 'url': '#', 'count': 18},
            {'label': 'Rascunhos', 'url': '#', 'count': 4},
            {'label': 'Arquivados', 'url': '#', 'count': 2},
        ]
        ctx['filter_fields_demo'] = [
            {'type': 'select', 'label': 'Status', 'name': 'status', 'value': 'ativo',
             'options': [('', 'Todos'), ('ativo', 'Ativo'), ('pausado', 'Pausado'), ('arquivado', 'Arquivado')]},
            {'type': 'select', 'label': 'Origem', 'name': 'origem', 'value': '',
             'options': [('', 'Todas'), ('google', 'Google Ads'), ('facebook', 'Facebook'), ('organico', 'Organico')]},
            {'type': 'select', 'label': 'Responsavel', 'name': 'resp', 'value': '',
             'options': [('', 'Todos'), ('1', 'Lucas Rocha'), ('2', 'Maria Silva'), ('3', 'Joao Souza')]},
            {'type': 'date', 'label': 'A partir de', 'name': 'data_inicio', 'value': ''},
        ]
        return ctx

urlpatterns = [
    path('admin/', admin.site.urls),

    # === Design system preview (temporario — remover quando o DS estiver adotado) ===
    path('design-system/preview/', TemplateView.as_view(template_name='design_system_preview.html'), name='design_system_preview'),
    path('design-system/componentes/', DesignSystemComponentsView.as_view(), name='design_system_components'),
    path('design-system/brand/', TemplateView.as_view(template_name='design_system_brand.html'), name='design_system_brand'),
    path('design-system/brand/logo/', TemplateView.as_view(template_name='design_system_brand_logo.html'), name='design_system_brand_logo'),
    path('design-system/brand/cores/', TemplateView.as_view(template_name='design_system_brand_cores.html'), name='design_system_brand_cores'),
    path('design-system/brand/tipografia/', TemplateView.as_view(template_name='design_system_brand_tipografia.html'), name='design_system_brand_tipografia'),
    path('design-system/brand/voz-e-tom/', TemplateView.as_view(template_name='design_system_brand_voz_tom.html'), name='design_system_brand_voz_tom'),
    path('design-system/brand/marginalia/', TemplateView.as_view(template_name='design_system_brand_marginalia.html'), name='design_system_brand_marginalia'),
    path('design-system/brand/aplicacoes/', TemplateView.as_view(template_name='design_system_brand_aplicacoes.html'), name='design_system_brand_aplicacoes'),
    path('design-system/brand/instagram/', TemplateView.as_view(template_name='design_system_brand_instagram.html'), name='design_system_brand_instagram'),
    path('design-system/brand/assinatura-email/', TemplateView.as_view(template_name='design_system_brand_assinatura.html'), name='design_system_brand_assinatura'),

    # === API REST (DRF + OpenAPI) ===
    path('api/', include('apps.api.urls')),

    # === Apps modulares ===
    path('', include('apps.sistema.urls')),
    path('', include('apps.comercial.leads.urls')),
    path('', include('apps.comercial.atendimento.urls')),
    path('', include('apps.comercial.cadastro.urls')),
    path('', include('apps.comercial.viabilidade.urls')),
    path('', include('apps.notificacoes.urls')),
    path('', include('apps.marketing.campanhas.urls')),
    path('', include('apps.dashboard.urls')),

    # === Apps com prefixo proprio ===
    path('aurora-admin/', include('apps.admin_aurora.urls')),
    path('configuracoes/integracoes/', include('apps.integracoes.urls')),
    # Redirect legado: /integracoes/* -> /configuracoes/integracoes/*
    path('integracoes/<path:resto>', RedirectView.as_view(url='/configuracoes/integracoes/%(resto)s', permanent=False, query_string=True)),
    path('integracoes/', RedirectView.as_view(url='/configuracoes/integracoes/', permanent=False, query_string=True)),
    path('crm/',          include('apps.comercial.crm.urls')),
    path('marketing/automacoes/', include('apps.marketing.automacoes.urls')),
    path('marketing/emails/',     include('apps.marketing.emails.urls')),
    path('marketing/segmentos/', include('apps.marketing.segmentos_urls')),

    # === Modulo CS ===
    path('cs/clube/',       include('apps.cs.clube.urls')),
    path('cs/parceiros/',   include('apps.cs.parceiros.urls')),
    path('cs/indicacoes/',  include('apps.cs.indicacoes.urls')),
    path('cs/carteirinha/', include('apps.cs.carteirinha.urls')),

    # === Suporte ===
    path('suporte/', include('apps.suporte.urls')),

    # === Inbox ===
    path('inbox/', include('apps.inbox.urls')),

    # === Widget público (sem login) ===
    path('api/public/widget/', include('apps.inbox.urls_public')),

    # Webhook publico do Resend (validado por assinatura HMAC)
    path('api/public/resend/', include('apps.marketing.emails.urls_public')),

    # === Assistente CRM (webhook WhatsApp) ===
    path('assistente/', include('apps.assistente.urls')),

    # === Workspace (projetos, tarefas, documentos) ===
    path('workspace/', include('apps.workspace.urls')),

] + (static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) if settings.DEBUG else [])
