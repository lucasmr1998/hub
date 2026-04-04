"""
Settings para desenvolvimento local com PostgreSQL.
Usa banco aurora_dev no localhost.

Uso: python manage.py runserver --settings=gerenciador_vendas.settings_local_pg
"""

from .settings import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = 'dev-local-insecure-key-only-for-testing'

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
