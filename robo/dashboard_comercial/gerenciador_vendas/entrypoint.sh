#!/bin/bash
set -e

echo "=== Hubtrix Deploy ==="

# 1. Rodar migrations
echo "[1/4] Aplicando migrations..."
python manage.py migrate --noinput

# 2. Rodar seeds (idempotentes — || true para nao derrubar o deploy se falhar)
echo "[2/4] Verificando seeds..."
python manage.py seed_funcionalidades || true
python manage.py seed_perfis_padrao || true
python manage.py seed_tipos_notificacao || true
python manage.py seed_fluxo_assistente || true
python manage.py seed_demo_vendas || true

# 3. Coletar arquivos estáticos
echo "[3/4] Coletando static files..."
python manage.py collectstatic --noinput || true

# 4. Iniciar nginx como proxy reverso (porta 8000 → Daphne 8001)
echo "[4/4] Iniciando servidores..."
nginx

echo "=== Deploy concluido ==="

# Iniciar Daphne (ASGI — HTTP + WebSocket) na porta interna 8001
exec daphne -b 127.0.0.1 -p 8001 --proxy-headers gerenciador_vendas.asgi:application
