#!/bin/bash
set -e

echo "=== Hubtrix Deploy ==="

# 1. Rodar migrations
echo "[1/3] Aplicando migrations..."
python manage.py migrate --noinput

# 2. Rodar seeds (idempotentes — só cria o que não existe)
echo "[2/4] Verificando seeds..."
python manage.py seed_funcionalidades
python manage.py seed_perfis_padrao
python manage.py seed_tipos_notificacao
python manage.py seed_fluxo_assistente
python manage.py seed_demo_vendas

# 3. Coletar arquivos estáticos
echo "[3/4] Coletando static files..."
python manage.py collectstatic --noinput || true

echo "=== Deploy concluido ==="

# Iniciar Gunicorn
exec gunicorn gerenciador_vendas.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
