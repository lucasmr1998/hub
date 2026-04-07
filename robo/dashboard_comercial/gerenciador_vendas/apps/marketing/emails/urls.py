from django.urls import path
from . import views

app_name = 'marketing_emails'

urlpatterns = [
    # Páginas
    path('', views.lista_emails, name='lista'),
    path('criar/', views.criar_email, name='criar'),
    path('<int:pk>/editor/', views.editor_email, name='editor'),
    path('<int:pk>/preview/', views.preview_email, name='preview'),

    # API
    path('<int:pk>/salvar/', views.salvar_email, name='salvar'),
    path('<int:pk>/duplicar/', views.duplicar_email, name='duplicar'),
    path('<int:pk>/excluir/', views.excluir_email, name='excluir'),
    path('api/preview/', views.preview_live, name='preview_live'),
    path('api/templates/', views.api_templates, name='api_templates'),
]
