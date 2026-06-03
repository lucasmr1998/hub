FROM python:3.11-slim

# Chromium + driver oficial do Debian (mais leve que google-chrome-stable).
# Se o HubSoft UI tiver problema, dá pra trocar pra google-chrome-stable.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-liberation \
    libnss3 \
    libxss1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cria pasta pra screenshots de debug (volume opcional em prod)
RUN mkdir -p /app/screenshots /app/dom_capturado

# Loop infinito que pega prospects pendentes da Nuvyon e converte via Selenium
CMD ["python", "-u", "bot_runner.py"]
