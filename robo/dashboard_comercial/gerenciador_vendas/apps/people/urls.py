from django.urls import path

from apps.people.views import inicio

app_name = 'people'

urlpatterns = [
    path('', inicio.home, name='home'),
]
