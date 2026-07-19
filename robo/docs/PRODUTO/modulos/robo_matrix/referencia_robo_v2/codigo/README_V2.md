# Robô de Vendas V2 — módulo TecHub (/robo-v2/)

Versão repaginada do robô de vendas rodando **dentro do portal TecHub**, em
paralelo com a v1 (`/robo/`) e com a produção antiga
(`robovendas.megalinkpiaui.com.br`). **Banco isolado: `robovendas_v2`** —
nada aqui toca o banco `robovendas` de produção.

## Arquitetura no TecHub

```
nginx (techub.megalinkpiaui.com.br)
  ├─ /robo-v2/         → gunicorn 127.0.0.1:8104  (Django, settings_production)
  ├─ /robo-v2/ia/*     → uvicorn  127.0.0.1:8091  (FastAPI ia_validacao, prefixo removido)
  ├─ /robo-v2/static/  → staticfiles_collected/ (servido direto)
  └─ /robo-v2/media/   → media/
```

- **SSO**: card "Comercial → Robô de Vendas V2" no portal → POST `portal_token`
  → `gerenciador_vendas/portal_sso.py` valida em `/api/validar-token/` do portal.
  Registro do módulo: `manage.py setup_robo_v2_modulo` (no portal).
- **Banco**: `robovendas_v2` @ 187.62.153.52 (criado vazio; migrations já
  populam as 33 `RegraValidacao`). Config em `dashboard_comercial/.env.production`.
- **FastAPI → Django**: `ia_validacao/.env` → `ROBOVENDAS_API_URL=http://127.0.0.1:8104`.

## Rotas de API (bot Matrix / N8N)

| Antiga (robovendas)                                  | Nova (techub)                                                        |
|------------------------------------------------------|----------------------------------------------------------------------|
| `https://robovendas.megalinkpiaui.com.br/ia/validar` | `https://techub.megalinkpiaui.com.br/robo-v2/ia/validar`             |
| `…/ia/proximo-passo`                                 | `…/robo-v2/ia/proximo-passo`                                          |
| `…/ia/conv/turno`                                    | `…/robo-v2/ia/conv/turno`                                             |
| `…/ia/validar-imagem`                                | `…/robo-v2/ia/validar-imagem`                                         |
| `…/api/...` (Django: leads, n8n, dashboards)         | `…/robo-v2/api/...`                                                   |
| `…/ia_validador/api/regras-validacao/`               | `…/robo-v2/ia_validador/api/regras-validacao/`                        |

## Deploy / operação

```bash
# ativar tudo (systemd + nginx):
sudo bash /home/darlan/projetos_django/projeto_techub/deploy/apply-robo-v2.sh

# serviços:
sudo systemctl restart techub-robo-v2   # Django  :8104
sudo systemctl restart techub-ia-v2     # FastAPI :8091

# migrations / static:
cd dashboard_comercial/gerenciador_vendas
DJANGO_ENV=production DJANGO_SETTINGS_MODULE=gerenciador_vendas.settings_production \
  ../myenv/bin/python manage.py migrate
DJANGO_ENV=production DJANGO_SETTINGS_MODULE=gerenciador_vendas.settings_production \
  ../myenv/bin/python manage.py collectstatic --noinput
```

## Padrão visual

O shell (`vendas_web/templates/vendas_web/base.html`) usa os tokens do
**TecHub DS** (`techub/static/css/techub-ds.css`): navy `#000b4a`, azul
`#0022fa`, laranja `#ff6b00`, Inter/Poppins. O `<head>` do base injeta um
patch global de `fetch`/XHR que prefixa chamadas absolutas com o
`SCRIPT_NAME` (`/robo-v2`) e corrige o header `X-CSRFToken` (o cookie em
produção chama `robo_v2_csrftoken`).

## Clonar dados da produção (opcional, decisão manual)

Para começar a v2 com os dados atuais do robovendas (leitura apenas na origem):

```bash
PGPASSWORD='***' pg_dump  -h 187.62.153.52 -U admin -Fc robovendas -f /tmp/robovendas.dump
PGPASSWORD='***' pg_restore -h 187.62.153.52 -U admin -d robovendas_v2 --clean --if-exists /tmp/robovendas.dump
```
