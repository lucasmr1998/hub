FROM python:3.11-slim

# Evitar prompts interativos
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Instalar dependencias do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Diretorio de trabalho
WORKDIR /app

# Copiar requirements e instalar dependencias Python
COPY robo/dashboard_comercial/gerenciador_vendas/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o projeto
COPY robo/dashboard_comercial/gerenciador_vendas/ .

# Copiar docs do repo (servidos em /aurora-admin/docs/)
COPY robo/docs /app/docs_repo
ENV AURORA_DOCS_PATH=/app/docs_repo

# Coletar arquivos estaticos (SECRET_KEY temporaria so para o build)
RUN SECRET_KEY=build-only-dummy-key-not-used-in-runtime-xxxxxxxxxxx \
    python manage.py collectstatic --noinput --settings=gerenciador_vendas.settings

# Porta
EXPOSE 8000

# Comando de inicializacao
CMD ["sh", "-c", "python manage.py migrate --noinput --settings=gerenciador_vendas.settings && gunicorn gerenciador_vendas.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
