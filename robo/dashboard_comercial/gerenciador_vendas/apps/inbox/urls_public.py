from django.urls import path
from . import views_public

app_name = 'inbox_public'

urlpatterns = [
    path('config/', views_public.widget_config, name='widget_config'),
    path('faq/', views_public.widget_faq, name='widget_faq'),
    path('faq/buscar/', views_public.widget_faq_buscar, name='widget_faq_buscar'),
    path('conversa/iniciar/', views_public.widget_conversa_iniciar, name='widget_conversa_iniciar'),
    path('conversa/<int:conversa_id>/mensagens/', views_public.widget_mensagens, name='widget_mensagens'),
    path('conversa/<int:conversa_id>/enviar/', views_public.widget_enviar, name='widget_enviar'),
    path('conversas/', views_public.widget_conversas, name='widget_conversas'),
]
