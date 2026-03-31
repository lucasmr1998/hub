from django.urls import path

app_name = 'carteirinha'

from . import views

urlpatterns = [
    # Dashboard Admin
    path('dashboard/carteirinha/', views.dashboard_carteirinha, name='dashboard_carteirinha'),
    path('dashboard/carteirinha/modelos/', views.dashboard_modelos, name='dashboard_modelos_carteirinha'),
    path('dashboard/carteirinha/modelos/criar/', views.dashboard_modelo_criar, name='dashboard_modelo_criar'),
    path('dashboard/carteirinha/modelos/<int:modelo_id>/editar/', views.dashboard_modelo_editar, name='dashboard_modelo_editar'),
    path('dashboard/carteirinha/regras/', views.dashboard_regras, name='dashboard_regras_carteirinha'),
    path('dashboard/carteirinha/preview/<int:modelo_id>/', views.dashboard_preview, name='dashboard_preview_carteirinha'),

    # Area do Membro
    path('membro/carteirinha/', views.membro_carteirinha, name='membro_carteirinha'),
]
