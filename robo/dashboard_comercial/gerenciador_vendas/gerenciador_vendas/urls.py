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

urlpatterns = [
    path('admin/', admin.site.urls),

    # === API REST (DRF + OpenAPI) ===
    path('api/', include('apps.api.urls')),

    # === App legado (views e URLs ainda aqui, migração incremental) ===
    path('', include('vendas_web.urls')),

    # === Apps modulares ===
    path('',              include('apps.sistema.urls')),
    path('aurora-admin/', include('apps.admin_aurora.urls')),
    path('integracoes/',  include('apps.integracoes.urls')),
    path('crm/',          include('apps.comercial.crm.urls')),

    # === Módulo CS ===
    path('cs/clube/',       include('apps.cs.clube.urls')),
    path('cs/parceiros/',   include('apps.cs.parceiros.urls')),
    path('cs/indicacoes/',  include('apps.cs.indicacoes.urls')),
    path('cs/carteirinha/', include('apps.cs.carteirinha.urls')),
]
