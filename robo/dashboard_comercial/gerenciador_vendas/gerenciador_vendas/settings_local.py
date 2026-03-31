"""
Settings para desenvolvimento local.
Usa SQLite para não depender do PostgreSQL de produção.

Uso: python manage.py runserver --settings=gerenciador_vendas.settings_local
"""

from .settings import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = 'dev-local-insecure-key-only-for-testing'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_local.sqlite3',
    }
}

# Herda INSTALLED_APPS do settings.py (já inclui todos os apps modulares)
# Não precisa redefinir — settings.py é a fonte da verdade
