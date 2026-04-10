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

# Coletar arquivos estaticos
RUN python manage.py collectstatic --noinput --settings=gerenciador_vendas.settings || true

# Porta
EXPOSE 8000

# Comando de inicializacao
CMD ["sh", "-c", "python manage.py migrate --noinput --settings=gerenciador_vendas.settings && gunicorn gerenciador_vendas.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
