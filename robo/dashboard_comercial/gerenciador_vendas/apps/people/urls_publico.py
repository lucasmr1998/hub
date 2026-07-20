"""
Rotas publicas do People. Sem login.

Montadas fora do `people/urls.py` de proposito: aquele esta atras do
`PermissaoMiddleware` via `_MODULO_MAP`, e estas precisam ficar de fora. A
isencao de login vive em `_EXEMPT_PATTERNS` no middleware do sistema.
"""
from django.urls import path

from apps.people.views import publico

app_name = 'people_publico'

urlpatterns = [
    path('<str:token>/', publico.formulario, name='formulario'),
    path('<str:token>/enviar/', publico.enviar, name='enviar'),
]
