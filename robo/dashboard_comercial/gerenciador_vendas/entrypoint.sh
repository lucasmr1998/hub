#!/bin/bash
set -e

echo "=== Hubtrix Deploy ==="

# 0. Garantir libs do WeasyPrint (necessario enquanto EasyPanel usa cache de image)
if ! python -c "import weasyprint" 2>/dev/null; then
    echo "[0/4] Instalando dependencias WeasyPrint..."
    apt-get update -qq && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
        libcairo2 libgdk-pixbuf-xlib-2.0-0 libgdk-pixbuf2.0-bin \
        libglib2.0-0 libharfbuzz0b fonts-dejavu-core \
        && rm -rf /var/lib/apt/lists/*
fi

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
echo "[4/5] Iniciando servidores..."
nginx

# 5. Dispatcher de cron jobs em background (apps/cron — ver dispatcher-cron.md)
# Loop que dispara dispatcher_cron a cada 60s. Pra desligar, basta matar o
# processo (ou desabilitar individualmente cada CronJob em /aurora-admin/cron/).
echo "[5/5] Iniciando dispatcher de cron jobs em background..."
python manage.py dispatcher_loop --intervalo 60 &

echo "=== Deploy concluido ==="

# Iniciar Daphne (ASGI — HTTP + WebSocket) na porta interna 8001
exec daphne -b 127.0.0.1 -p 8001 --proxy-headers gerenciador_vendas.asgi:application
