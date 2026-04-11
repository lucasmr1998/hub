from django.urls import path
from . import views

app_name = 'notificacoes'

urlpatterns = [
    # Paginas de configuracao de notificacoes
    path('configuracoes/notificacoes/', views.configuracoes_notificacoes_view, name='configuracoes_notificacoes'),
    path('configuracoes/notificacoes/tipo/<int:tipo_id>/', views.tipo_notificacao_detalhes_view, name='tipo_notificacao_detalhes'),

    # APIs de notificacoes
    path('api/notificacoes/enviar/', views.api_notificacao_enviar, name='api_notificacao_enviar'),
    path('api/notificacoes/listar/', views.api_notificacoes_listar, name='api_notificacoes_listar'),
    path('api/notificacoes/<int:notificacao_id>/', views.api_notificacao_detalhes, name='api_notificacao_detalhes'),
    path('api/notificacoes/preferencias/', views.api_notificacoes_preferencias, name='api_notificacoes_preferencias'),
    path('api/notificacoes/teste/', views.api_notificacoes_teste, name='api_notificacoes_teste'),
    path('api/notificacoes/estatisticas/', views.api_notificacoes_estatisticas, name='api_notificacoes_estatisticas'),

    # APIs de templates de notificacoes
    path('api/templates-notificacoes/', views.api_templates_notificacoes, name='api_templates_notificacoes'),
    path('api/templates-notificacoes/<int:template_id>/', views.api_templates_notificacoes, name='api_templates_notificacoes_detail'),

    # APIs de tipos de notificacao
    path('api/tipos-notificacao/', views.api_tipos_notificacao, name='api_tipos_notificacao'),
    path('api/tipos-notificacao/<int:tipo_id>/', views.api_tipos_notificacao, name='api_tipos_notificacao_detail'),

    # APIs de canais de notificacao
    path('api/canais-notificacao/', views.api_canais_notificacao, name='api_canais_notificacao'),
    path('api/canais-notificacao/<int:canal_id>/', views.api_canais_notificacao, name='api_canais_notificacao_detail'),

    # APIs de gerenciamento de preferencias de usuarios
    path('api/notificacoes/canais/', views.api_canais_notificacao, name='api_canais'),
    path('api/notificacoes/preferencias/criar/', views.api_preferencias_criar, name='api_preferencias_criar'),
    path('api/notificacoes/preferencias/editar/', views.api_preferencias_editar, name='api_preferencias_editar'),
    path('api/notificacoes/preferencias/<int:preferencia_id>/dados/', views.api_preferencias_dados, name='api_preferencias_dados'),
    path('api/notificacoes/preferencias/<int:preferencia_id>/pausar/', views.api_preferencias_pausar, name='api_preferencias_pausar'),
    path('api/notificacoes/preferencias/<int:preferencia_id>/ativar/', views.api_preferencias_ativar, name='api_preferencias_ativar'),
    path('api/notificacoes/preferencias/<int:preferencia_id>/', views.api_preferencias_remover, name='api_preferencias_remover'),

    # APIs de configuracao do WhatsApp
    path('api/notificacoes/whatsapp/config/', views.api_whatsapp_config, name='api_whatsapp_config'),
    path('api/notificacoes/whatsapp/config/salvar/', views.api_whatsapp_config_salvar, name='api_whatsapp_config_salvar'),
    path('api/notificacoes/whatsapp/test/', views.api_whatsapp_test, name='api_whatsapp_test'),

    # API para alternar status de canais
    path('api/notificacoes/canais/<int:canal_id>/toggle/', views.api_canal_toggle, name='api_canal_toggle'),

    # APIs de leitura
    path('api/notificacoes/<int:notificacao_id>/lida/', views.api_notificacao_marcar_lida, name='api_notificacao_marcar_lida'),
    path('api/notificacoes/marcar-todas-lidas/', views.api_notificacoes_marcar_todas_lidas, name='api_notificacoes_marcar_todas_lidas'),
    path('api/notificacoes/nao-lidas/', views.api_notificacoes_nao_lidas, name='api_notificacoes_nao_lidas'),
]
