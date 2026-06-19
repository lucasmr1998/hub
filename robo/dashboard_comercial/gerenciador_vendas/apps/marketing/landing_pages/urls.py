"""URLs publicas da Landing Page. Montadas em /p/ no urls.py raiz."""
from django.urls import path

from . import views

app_name = 'landing_pages'

urlpatterns = [
    path('<slug:tenant_slug>/<slug:landing_slug>/', views.landing_publica, name='publica'),
]
