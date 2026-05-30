"""URLs do painel admin de Cron Jobs (montado em /aurora-admin/cron/)."""
from django.urls import path

from . import views

app_name = 'cron'

urlpatterns = [
    path('', views.lista_view, name='lista'),
    path('<int:pk>/', views.detalhe_view, name='detalhe'),
    path('<int:pk>/toggle/', views.toggle_view, name='toggle'),
    path('<int:pk>/run-now/', views.run_now_view, name='run_now'),
    path('<int:pk>/editar/', views.editar_view, name='editar'),
]
