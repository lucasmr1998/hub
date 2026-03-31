from django.urls import path
from . import views

app_name = 'sistema'

urlpatterns = [
    path('setup/', views.setup_inicial_view, name='setup_inicial'),
]
