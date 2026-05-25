FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
# REBUILD-2026-05-24: fixed package names for Debian 13 (Trixie) + WeasyPrint deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev nginx \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf-xlib-2.0-0 libgdk-pixbuf2.0-bin \
    libffi-dev shared-mime-info \
    libglib2.0-0 libharfbuzz0b fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# WeasyPrint runtime libs (new layer to bypass build cache)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libcairo2 libgdk-pixbuf-xlib-2.0-0 libgdk-pixbuf2.0-bin \
    libglib2.0-0 libharfbuzz0b fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

# Copy project
COPY . .

# Configurar nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/sites-enabled/default

# Tornar entrypoint executavel
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
