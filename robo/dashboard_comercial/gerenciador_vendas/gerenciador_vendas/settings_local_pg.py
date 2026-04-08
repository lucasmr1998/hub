"""
Settings para desenvolvimento local com PostgreSQL.
Usa banco aurora_dev no localhost.

Uso: python manage.py runserver --settings=gerenciador_vendas.settings_local_pg
"""
import os

# Tokens para APIs externas (ANTES de importar settings)
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
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
