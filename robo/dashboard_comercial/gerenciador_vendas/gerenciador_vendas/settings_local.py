"""
Settings para desenvolvimento local.
Usa PostgreSQL local (aurora_dev).

Uso: python manage.py runserver --settings=gerenciador_vendas.settings_local
"""

from .settings import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = 'dev-local-insecure-key-only-for-testing'
ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'aurora_dev',
        'USER': 'postgres',
        'PASSWORD': 'admin123',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}

# Herda INSTALLED_APPS do settings.py (já inclui todos os apps modulares)
# Não precisa redefinir — settings.py é a fonte da verdade
