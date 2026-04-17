# 16. Deploy — Guia Completo

**Status:** Em producao
**Ultima atualizacao:** 10/04/2026
**Plataforma:** Easypanel (Hostinger VPS)

---

## Arquitetura de Producao

```
GitHub (push main)
    |
    v
Easypanel (build Docker)
    |
    ├── Container App (Django + Gunicorn + WhiteNoise)
    │   └── Porta 8000
    |
    ├── Container PostgreSQL (hubbanco)
    │   └── Porta 5432 (rede interna)
    |
    └── Proxy Reverso (Traefik/Easypanel)
        └── HTTPS → Porta 8000
```

---

## Configuracao Atual

| Item | Valor |
|------|-------|
| **URL producao** | https://projetos-hub.v4riem.easypanel.host/ |
| **Repositorio** | github.com/lucasmr1998/hub (privado) |
| **Branch** | main |
| **Build** | Dockerfile na raiz |
| **Banco** | PostgreSQL no Easypanel (hubbanco) |
| **Arquivos estaticos** | WhiteNoise (servidos pelo Django) |

---

## Como funciona o deploy automatico

1. Voce faz `git push origin main`
2. O Easypanel detecta o push (via webhook do Git)
3. Puxa o codigo do GitHub
4. Builda a imagem Docker usando o `Dockerfile`
5. Roda `migrate` automaticamente
6. Inicia o Gunicorn com 3 workers
7. O proxy redireciona HTTPS para o container

---

## Variaveis de Ambiente (Easypanel)

Configuradas na secao "Variaveis de Ambiente" do servico hub:

```
SECRET_KEY=<chave-secreta-segura>
DEBUG=False
ALLOWED_HOSTS=*
DB_NAME=hub
DB_USER=admin_hub
DB_PASSWORD=Hub@2026
DB_HOST=hubbanco
DB_PORT=5432
CSRF_TRUSTED_ORIGINS=https://projetos-hub.v4riem.easypanel.host
```

### Variaveis opcionais

```
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SITE_URL=https://projetos-hub.v4riem.easypanel.host
N8N_WEBHOOK_URL=<url-do-n8n>
N8N_API_KEY=<chave-n8n>
```

---

## Dockerfile

Localizado na raiz do repositorio (`/Dockerfile`):

```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY robo/dashboard_comercial/gerenciador_vendas/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY robo/dashboard_comercial/gerenciador_vendas/ .

RUN python manage.py collectstatic --noinput --settings=gerenciador_vendas.settings || true

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput --settings=gerenciador_vendas.settings && gunicorn gerenciador_vendas.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
```

---

## Como Replicar (novo servidor)

### Passo 1: Criar projeto no Easypanel

1. Acesse o painel do Easypanel
2. Crie um novo projeto (ex: "hubtrix")

### Passo 2: Criar banco PostgreSQL

1. No projeto, clique em **"+ Servico"**
2. Selecione **"Postgres"**
3. Preencha:
   - Nome do Servico: `hubbanco`
   - Nome do Banco: `hub`
   - Usuario: `admin_hub`
   - Senha: (defina uma senha segura)
4. Clique em **"Criar"**

### Passo 3: Criar servico da App

1. Clique em **"+ Servico"** → **"App"**
2. Na aba **"Git"**:
   - URL: `git@github.com:lucasmr1998/hub.git`
   - Ramo: `main`
   - Caminho de Build: `/`
3. Se o repo for privado:
   - Clique em **"Gerar Chave SSH"**
   - Copie a chave publica
   - No GitHub: Settings → Deploy Keys → Add deploy key → cole a chave
4. Na construcao, selecione **"Dockerfile"**
5. Arquivo: `Dockerfile`
6. Salve

### Passo 4: Configurar variaveis de ambiente

Na secao "Variaveis de Ambiente" do servico da app, adicione:

```
SECRET_KEY=<gere-uma-nova-com: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
ALLOWED_HOSTS=*
DB_NAME=hub
DB_USER=admin_hub
DB_PASSWORD=<senha-do-banco>
DB_HOST=hubbanco
DB_PORT=5432
CSRF_TRUSTED_ORIGINS=https://<seu-dominio>
```

Salve e faca deploy.

### Passo 5: Configurar dominio

1. Na secao "Dominios" do servico
2. Edite o dominio gerado
3. Mude a porta de destino para **8000** (em vez de 80)
4. Ou adicione seu dominio proprio

### Passo 6: Criar superusuario

No terminal do servico (Console do Servico → Bash):

```bash
python manage.py createsuperuser --settings=gerenciador_vendas.settings
```

### Passo 7 (opcional): Importar banco existente

Se precisa importar dados de outro ambiente:

1. No ambiente de origem, exporte:
```bash
pg_dump -h localhost -U postgres -d aurora_dev --no-owner --no-acl -F p -f backup.sql
```

2. Suba o arquivo para um local acessivel (ou coloque temporariamente no repo)

3. No terminal do Easypanel:
```bash
apt-get update && apt-get install -y postgresql-client
```

4. Se o banco ja tem tabelas, drope e recrie:
```bash
PGPASSWORD=<senha> psql -h hubbanco -U admin_hub -d postgres -c "DROP DATABASE hub;"
PGPASSWORD=<senha> psql -h hubbanco -U admin_hub -d postgres -c "CREATE DATABASE hub OWNER admin_hub;"
```

5. Importe:
```bash
PGPASSWORD=<senha> psql -h hubbanco -U admin_hub -d hub < /tmp/backup.sql
```

---

## Como fazer deploy manual

Se o deploy automatico nao disparar:

1. No Easypanel, va ao servico da app
2. Clique em **"Deploy"** ou **"Rebuild"**
3. Aguarde o build + migrate + start

---

## Troubleshooting

### Erro CSRF 403 ao fazer login
- Verificar se `CSRF_TRUSTED_ORIGINS` tem o dominio correto com `https://`
- Verificar se `SECURE_PROXY_SSL_HEADER` esta no settings

### CSS/JS nao carregam (pagina sem estilo)
- Verificar se `whitenoise.middleware.WhiteNoiseMiddleware` esta no MIDDLEWARE
- Verificar se `collectstatic` rodou no build (ver logs)

### Erro de conexao com banco
- Verificar se as variaveis DB_HOST, DB_NAME, DB_USER, DB_PASSWORD estao corretas
- DB_HOST deve ser o nome do servico do banco no Easypanel (ex: `hubbanco`)

### ModuleNotFoundError
- Adicionar o pacote faltante no `requirements.txt`
- Fazer push e redeploy

### Erro "No such user" no Gunicorn
- Verificar se `gunicorn.conf.py` nao tem `user = "..."` hardcoded
- O conf atual usa variaveis de ambiente

---

## Checklist de Deploy

- [ ] Repositorio no GitHub atualizado (`git push origin main`)
- [ ] Repositorio privado (nao publico)
- [ ] Variaveis de ambiente configuradas no Easypanel
- [ ] Dominio configurado com porta 8000
- [ ] CSRF_TRUSTED_ORIGINS com dominio correto
- [ ] Banco PostgreSQL criado e acessivel
- [ ] Superusuario criado
- [ ] Login funcionando
- [ ] CSS/JS carregando
- [ ] Seed de dados inicial rodado (tenants, perfis, funcionalidades)
