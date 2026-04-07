# Gunicorn configuration file for MegaLink Robo Vendas
# robovendas.megalinkpiaui.com.br

import multiprocessing
import os

# Server socket
bind = "127.0.0.1:8003"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests, to help prevent memory leaks
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "/var/log/gunicorn/robovendas/access.log"
errorlog = "/var/log/gunicorn/robovendas/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "robovendas_megalink"

# Server mechanics
daemon = False
pidfile = "/var/run/gunicorn/robovendas.pid"
user = "darlan"
group = "darlan"
tmp_upload_dir = None

# SSL (se necessário)
# keyfile = "/etc/ssl/private/robovendas.megalinkpiaui.com.br.key"
# certfile = "/etc/ssl/certs/robovendas.megalinkpiaui.com.br.crt"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Application
wsgi_module = "gerenciador_vendas.wsgi:application"
pythonpath = "/home/darlan/projetos_django/new_robo/dashboard_comercial/gerenciador_vendas"

# Environment variables
raw_env = [
    "DJANGO_SETTINGS_MODULE=gerenciador_vendas.settings",
    "PYTHONPATH=/home/darlan/projetos_django/new_robo/dashboard_comercial/gerenciador_vendas",
]

# Preload application for better performance
preload_app = True

# Enable automatic worker restarts
reload = False

# Worker timeout
graceful_timeout = 30
