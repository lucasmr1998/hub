from django.urls import path

from apps.people.views import inicio, unidades

app_name = 'people'

urlpatterns = [
    path('', inicio.home, name='home'),
    path('unidades/', unidades.lista, name='unidades_lista'),
]
