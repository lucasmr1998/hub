"""URLs publicas (sem login) — webhook do Resend."""
from django.urls import path
from . import views_webhook

app_name = 'marketing_emails_public'

urlpatterns = [
    path('webhook/', views_webhook.resend_webhook, name='resend_webhook'),
]
