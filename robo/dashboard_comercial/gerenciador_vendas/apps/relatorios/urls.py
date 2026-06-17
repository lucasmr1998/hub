from django.urls import path

from . import views

app_name = 'relatorios'

urlpatterns = [
    # UI
    path('', views.lista_view, name='lista'),
    path('setor/<slug:setor>/', views.lista_view, name='lista_setor'),
    path('<int:pk>/', views.dashboard_detalhe_view, name='detalhe'),
    path('<int:pk>/editar/', views.dashboard_editar_view, name='editar'),
    path('criar/', views.dashboard_criar_view, name='criar'),
    path('<int:pk>/excluir/', views.dashboard_excluir_view, name='excluir'),

    # APIs
    path('api/data-sources/', views.api_data_sources, name='api_data_sources'),
    path('api/data-source/<str:slug>/', views.api_data_source_detalhe, name='api_data_source_detalhe'),
    path('api/preview/', views.api_preview, name='api_preview'),
    path('api/widget/<int:pk>/dados/', views.api_widget_dados, name='api_widget_dados'),
    path('api/widget/<int:pk>/config/', views.api_widget_config, name='api_widget_config'),
    path('api/widget/salvar/', views.api_widget_salvar, name='api_widget_salvar'),
    path('api/widget/<int:pk>/excluir/', views.api_widget_excluir, name='api_widget_excluir'),
    path('api/dashboard/<int:pk>/layout/', views.api_dashboard_layout, name='api_dashboard_layout'),
]
