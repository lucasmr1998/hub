from django.urls import path
from . import views

app_name = 'ia_validador'

urlpatterns = [
    # Página explicativa (UI)
    path('dashboard/', views.dashboard_validador, name='dashboard'),

    # APIs (consumidas pela API IA externa)
    path('api/regras-validacao/', views.listar_regras, name='listar_regras'),
    path('api/mensagens-robo/', views.listar_mensagens, name='listar_mensagens'),
    path('api/regras-validacao/<slug:question_id>/', views.obter_regra, name='obter_regra'),
    path('api/regras-validacao/_invalidar-cache/', views.invalidar_cache, name='invalidar_cache'),
    path('api/ia/log-interacao/', views.api_log_interacao, name='api_log_interacao'),
]
