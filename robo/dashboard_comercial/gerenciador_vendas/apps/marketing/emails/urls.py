from django.urls import path
from . import views, views_remetentes

app_name = 'marketing_emails'

urlpatterns = [
    # Páginas — templates de email
    path('', views.lista_emails, name='lista'),
    path('criar/', views.criar_email, name='criar'),
    path('<int:pk>/editor/', views.editor_email, name='editor'),
    path('<int:pk>/preview/', views.preview_email, name='preview'),

    # API templates
    path('<int:pk>/salvar/', views.salvar_email, name='salvar'),
    path('<int:pk>/duplicar/', views.duplicar_email, name='duplicar'),
    path('<int:pk>/excluir/', views.excluir_email, name='excluir'),
    path('api/preview/', views.preview_live, name='preview_live'),
    path('api/templates/', views.api_templates, name='api_templates'),

    # Dominios de remetente
    path('dominios/', views_remetentes.dominios_lista, name='dominios_lista'),
    path('dominios/criar/', views_remetentes.dominio_criar, name='dominio_criar'),
    path('dominios/<int:pk>/', views_remetentes.dominio_detalhe, name='dominio_detalhe'),
    path('dominios/<int:pk>/verificar/', views_remetentes.dominio_verificar, name='dominio_verificar'),
    path('dominios/<int:pk>/excluir/', views_remetentes.dominio_excluir, name='dominio_excluir'),
    path('dominios/<int:pk>/flags/', views_remetentes.dominio_toggle_flag, name='dominio_toggle_flag'),

    # Remetentes (dentro de um dominio)
    path('dominios/<int:dominio_pk>/remetentes/criar/', views_remetentes.remetente_criar, name='remetente_criar'),
    path('remetentes/<int:pk>/excluir/', views_remetentes.remetente_excluir, name='remetente_excluir'),
    path('remetentes/<int:pk>/padrao/', views_remetentes.remetente_set_padrao, name='remetente_set_padrao'),

    # Webhook publico do Resend vive em apps/marketing/emails/urls_public.py
    # montado em /api/public/resend/webhook/
]
