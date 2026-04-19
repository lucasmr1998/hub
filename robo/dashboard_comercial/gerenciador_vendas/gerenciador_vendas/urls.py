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
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView


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
        return ctx

urlpatterns = [
    path('admin/', admin.site.urls),

    # === Design system preview (temporario — remover quando o DS estiver adotado) ===
    path('design-system/preview/', TemplateView.as_view(template_name='design_system_preview.html'), name='design_system_preview'),
    path('design-system/componentes/', DesignSystemComponentsView.as_view(), name='design_system_components'),

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
    path('integracoes/',  include('apps.integracoes.urls')),
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

    # === Assistente CRM (webhook WhatsApp) ===
    path('assistente/', include('apps.assistente.urls')),

]
