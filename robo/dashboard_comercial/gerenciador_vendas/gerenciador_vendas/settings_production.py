"""
Django settings for gerenciador_vendas project - PRODUÇÃO
Configurações otimizadas para ambiente de produção
"""

from .settings import *
import os

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Validar que SECRET_KEY está definida em produção
if not SECRET_KEY:
    raise ValueError("SECRET_KEY não definida. Configure a variável de ambiente SECRET_KEY.")

# Hosts permitidos em produção
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'aurora.consulteplus.com,www.aurora.consulteplus.com').split(',')

# Configurações de segurança
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Configurações SSL/HTTPS
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Configurações de sessão
SESSION_COOKIE_AGE = 3600  # 1 hora
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# Configurações de cache para produção
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# Configurações de logging para produção
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/gerenciador_vendas.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'gerenciador_vendas': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Configurações de email para produção
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@aurora.consulteplus.com')

# Configurações de arquivos estáticos otimizadas
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Banco de dados vem do settings.py base (variáveis de ambiente, sem fallback)

# Configurações de performance
CONN_MAX_AGE = 600

# Configurações de upload
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Configurações de middleware adicionais para produção
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.sistema.middleware.LoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Configurações de timezone
USE_TZ = True
TIME_ZONE = 'America/Sao_Paulo'

# Configurações de internacionalização
LANGUAGE_CODE = 'pt-br'
USE_I18N = True
USE_L10N = True

# Configurações de arquivos de mídia
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Configurações de admin
ADMIN_URL = 'admin/'

# Configurações de API
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Configurações de monitoramento
SILENCED_SYSTEM_CHECKS = [
    'security.W019',  # SECURE_SSL_REDIRECT
]

# Configurações de backup
BACKUP_DIR = '/var/backups/gerenciador_vendas'
