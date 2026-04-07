"""
Settings para desenvolvimento local.
Usa PostgreSQL local (aurora_dev).

Uso: python manage.py runserver --settings=gerenciador_vendas.settings_local
"""
import os

# Tokens para APIs externas
os.environ['N8N_API_TOKEN'] = 'qB0L0dkBULVQd6KlMlg24HV1hGxxQqIoFUrzZVN6yEU'
os.environ['WEBHOOK_SECRET_TOKEN'] = 'webhook-dev-token-local'

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
