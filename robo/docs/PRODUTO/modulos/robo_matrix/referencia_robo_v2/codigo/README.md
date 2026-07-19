# Rob-Vendas — Plataforma Comercial Megalink

Sistema de vendas via WhatsApp da Megalink Telecom. Um bot na plataforma **Matrix**
conduz o cliente por um fluxo de cadastro/venda, apoiado por duas aplicações deste
repositório que validam dados, decidem o próximo passo e integram com HubSoft ERP.

> 📚 Documentação detalhada em **[docs/](docs/)** — comece por
> [docs/ARQUITETURA.md](docs/ARQUITETURA.md) e [docs/ESTRUTURA.md](docs/ESTRUTURA.md).

---

## Os dois serviços

| Serviço | O que é | Roda como | Pasta |
|---|---|---|---|
| **Django (CRM + API de dados)** | Cadastro de leads, clientes HubSoft, validação de documentos, painel de vendas, **config das regras de validação** (`RegraValidacao`) e logs. | gunicorn + nginx | [`dashboard_comercial/gerenciador_vendas/`](dashboard_comercial/gerenciador_vendas/) |
| **FastAPI (IA Validação)** | Camada de IA que valida respostas, decide o próximo passo do fluxo e conversa com o cliente. | uvicorn `:8090` | [`ia_validacao/`](ia_validacao/) |

### Como se conectam

```
WhatsApp ──▶ Matrix (bot)
                │  chama os endpoints HTTP
                ▼
            nginx  ──  /ia/*  ─▶  FastAPI  (127.0.0.1:8090)   [ia_validacao/]
                │                    │
                │                    │ cliente HTTP (robovendas)
                ▼                    ▼
            Django (gunicorn)  ◀─────┘   [dashboard_comercial/gerenciador_vendas/]
                │
                ├─ PostgreSQL (leads, regras, logs)
                └─ HubSoft ERP / API Matrix
```

- O **nginx** faz proxy de `/ia/*` → `http://127.0.0.1:8090/*` (tira o prefixo `/ia/`).
  Ex.: `/ia/conv/turno` → FastAPI `/conv/turno`.
- A **FastAPI** lê/escreve dados no Django via HTTP (cliente `robovendas`), usando as
  `RegraValidacao` cadastradas no Django como configuração por pergunta.

---

## Os dois fluxos de atendimento

1. **Determinístico** (estável, em produção): `POST /ia/validar` (valida a resposta) +
   `POST /ia/proximo-passo` (decide a próxima pergunta).
2. **Conversacional** (IA por cima, mais natural): `POST /ia/conv/turno`, com dois modos
   detectados pelo corpo da requisição — **rotear** (próxima pergunta) e **validar**
   (valida a resposta). Isolado do determinístico.

Detalhes e a tabela de contrato em [docs/ARQUITETURA.md](docs/ARQUITETURA.md) e
[ia_validacao/docs/](ia_validacao/docs/).

---

## Como rodar (dev)

### FastAPI — IA Validação
```bash
cd ia_validacao
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edite as credenciais (OPENAI_API_KEY, ROBOVENDAS_API_URL...)
uvicorn src.app:app --host 0.0.0.0 --port 8090 --reload
# health: curl http://127.0.0.1:8090/conv/health
# testes (offline, sem rede): PYTHONPATH=. .venv/bin/python3 tests/test_conv_simulacao.py
```

### Django — CRM + API de dados
```bash
cd dashboard_comercial/gerenciador_vendas
python3 -m venv n_env && source n_env/bin/activate     # (o servidor usa n_env)
pip install -r requirements.txt
cp .env.example .env          # edite DB_*, credenciais HubSoft/Matrix...
python manage.py migrate
python manage.py runserver     # http://localhost:8000  (admin em /admin)
```

---

## Mapa do repositório (resumo)

```
new_robo/
├── README.md                      # este arquivo
├── docs/                          # documentação a nível de REPO (índice + arquitetura)
├── ia_validacao/                  # ── SERVIÇO FastAPI (IA) ──
│   ├── src/                        #   código (app, regras, onboarding, conversacional/)
│   ├── tests/                      #   suíte offline
│   ├── tools/                      #   utilitários de migração de flow (dev)
│   ├── fluxos/                     #   exports de flow do Matrix (.json) + yaml
│   └── docs/                       #   docs específicas da API IA
└── dashboard_comercial/
    └── gerenciador_vendas/         # ── SERVIÇO Django (CRM) ──
        ├── crm/  ia_validador/  integracoes/  vendas_web/   # apps Django
        ├── manage.py  db.sqlite3  templates/  static/
        └── README.md               # docs específicas do Django
```

Árvore anotada completa em **[docs/ESTRUTURA.md](docs/ESTRUTURA.md)**.

---

## Stack

| Camada | Tecnologia |
|---|---|
| IA Validação | FastAPI, Pydantic v2, OpenAI (gpt-4o / gpt-4o-mini), uvicorn |
| CRM / API dados | Django 4.x, PostgreSQL, gunicorn + nginx, WeasyPrint |
| Integrações | HubSoft ERP, API Matrix, ViaCEP |

## Licença
Uso interno — Megalink Telecom © 2026
