"""URLs de segmentos no contexto de Marketing (reutiliza views do CRM)."""
from django.urls import path
from apps.comercial.crm import views

app_name = 'marketing_segmentos'

urlpatterns = [
    path('', views.segmentos_lista, name='segmentos_lista'),
    path('criar/', views.segmento_criar, name='segmento_criar'),
    path('<int:pk>/', views.segmento_detalhe, name='segmento_detalhe'),
    path('<int:pk>/editar/', views.segmento_editar, name='segmento_editar'),
    path('salvar/', views.api_segmento_salvar, name='api_segmento_salvar'),
    path('preview/', views.api_preview_regras, name='api_preview_regras'),
    path('<int:pk>/buscar-leads/', views.api_segmento_buscar_leads, name='api_segmento_buscar_leads'),
    path('<int:pk>/adicionar-lead/', views.api_segmento_adicionar_lead, name='api_segmento_adicionar_lead'),
    path('<int:pk>/remover-membro/', views.api_segmento_remover_membro, name='api_segmento_remover_membro'),
    path('<int:pk>/disparar-campanha/', views.api_segmento_disparar_campanha, name='api_segmento_disparar_campanha'),
]
