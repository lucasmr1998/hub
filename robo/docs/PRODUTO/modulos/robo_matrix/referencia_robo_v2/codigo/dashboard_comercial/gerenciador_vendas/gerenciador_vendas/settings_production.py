"""
Production settings for Robo V2 — deployed at https://techub.megalinkpiaui.com.br/robo-v2/
Herda tudo de settings.py (inclusive PortalSSOMiddleware) e sobrescreve o que precisa.
Banco isolado: robovendas_v2 (paralelo ao robovendas de producao).
"""
from .settings import *  # noqa: F401,F403
import os

DEBUG = False

ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS',
    'techub.megalinkpiaui.com.br,127.0.0.1,localhost'
).split(',')

# Subpath deployment
FORCE_SCRIPT_NAME = '/robo-v2'
STATIC_URL = '/robo-v2/static/'
MEDIA_URL = '/robo-v2/media/'
STATIC_ROOT = BASE_DIR / 'staticfiles_collected'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = 'https://techub.megalinkpiaui.com.br/login/'
LOGIN_REDIRECT_URL = '/robo-v2/novo-dashboard/'
LOGOUT_REDIRECT_URL = 'https://techub.megalinkpiaui.com.br/'

# APPEND_SLASH remains False (api endpoints)

# Proxy / HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = False  # nginx handles redirect

CSRF_TRUSTED_ORIGINS = ['https://techub.megalinkpiaui.com.br']

# Security
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Cookies (distintos por app, dominio compartilhado — nao colidem com /robo/)
SESSION_COOKIE_NAME = 'robo_v2_sessionid'
CSRF_COOKIE_NAME = 'robo_v2_csrftoken'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_DOMAIN = 'techub.megalinkpiaui.com.br'
CSRF_COOKIE_DOMAIN = 'techub.megalinkpiaui.com.br'
SESSION_COOKIE_PATH = '/robo-v2/'
CSRF_COOKIE_PATH = '/robo-v2/'
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'robo-v2-cache',
        'TIMEOUT': 300,
        'OPTIONS': {'MAX_ENTRIES': 1000},
    }
}

# Logging (console only — captured by systemd journal)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '[{asctime}] {levelname} {module} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'mail.megalinkinternet.com.br')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'techub@megalinkinternet.com.br')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL', 'Megalink Portal <techub@megalinkinternet.com.br>'
)

STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Portal SSO
# PORTAL_URL = chamada server-to-server (interno, nao passa por Cloudflare)
# PORTAL_URL_PUBLICA = link para o browser (HTTPS publico)
PORTAL_URL = os.environ.get('PORTAL_URL', 'http://127.0.0.1:8100')
PORTAL_URL_PUBLICA = os.environ.get('PORTAL_URL_PUBLICA', 'https://techub.megalinkpiaui.com.br')
PORTAL_SECRET_KEY = os.environ.get('PORTAL_SECRET_KEY', '')

# Clube — conversão automática de indicação (server-to-server, porta 8101, sem prefixo /clube)
CLUBE_WEBHOOK_URL = os.environ.get(
    'CLUBE_WEBHOOK_URL',
    'http://127.0.0.1:8101/roleta/api/indicacoes/conversao/',
).rstrip('/') + '/'
# Mesmo segredo do COMERCIAL_WEBHOOK_SECRET no Clube (canal Clube ↔ Comercial)
CLUBE_WEBHOOK_SECRET = (
    os.environ.get('CLUBE_WEBHOOK_SECRET', '').strip()
    or os.environ.get('COMERCIAL_WEBHOOK_SECRET', '').strip()
)

SITE_URL = os.environ.get('SITE_URL', 'https://techub.megalinkpiaui.com.br/robo-v2')

# Perf
CONN_MAX_AGE = 600

# Silenced checks (not redirecting ssl, using SAMEORIGIN)
SILENCED_SYSTEM_CHECKS = ['security.W019']
