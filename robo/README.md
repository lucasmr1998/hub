# Hub de Tecnologia para Provedores de Internet

SaaS multi-tenant que centraliza Comercial, Marketing e Customer Success para provedores de internet. Integracao nativa com HubSoft, WhatsApp (N8N/Uazapi), e providers de IA.

## Modulos

| Modulo | O que faz |
|--------|-----------|
| **Comercial** | Leads, CRM Kanban, fluxos de atendimento (bot), cadastro, viabilidade |
| **Marketing** | Automacoes visuais (Drawflow), campanhas de trafego, segmentos dinamicos |
| **CS** | Clube de beneficios, parceiros, indicacoes, carteirinha digital |
| **Inbox** | Chat multicanal (WhatsApp, Email, Widget) com bot e agente |
| **Suporte** | Tickets, base de conhecimento |

## Stack

| Tecnologia | Uso |
|-----------|-----|
| Python 3.11 | Backend |
| Django 5.2 | Framework web |
| Django REST Framework | API REST |
| PostgreSQL | Banco de dados (producao) |
| SQLite | Banco local (desenvolvimento) |
| Gunicorn + Nginx | Servidor de producao |
| Drawflow.js | Editor visual de fluxos |
| N8N | Automacao e integracao WhatsApp |
| WeasyPrint | Geracao de PDF |

## Como rodar

```bash
cd dashboard_comercial/gerenciador_vendas
python manage.py migrate --settings=gerenciador_vendas.settings_local
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local
```

Acesse em http://127.0.0.1:8001/

## Estrutura

```
robo/
├── docs/                        # Documentacao (GTM, PRODUTO, BRAND, AGENTES)
├── exports/                     # Hub visual, drafts, deck
└── dashboard_comercial/gerenciador_vendas/
    ├── apps/                    # 18 apps modulares
    │   ├── sistema/             # Tenant, auth, configs, logging, permissoes
    │   ├── comercial/           # leads, atendimento, cadastro, viabilidade, crm
    │   ├── marketing/           # campanhas, automacoes, emails
    │   ├── cs/                  # clube, parceiros, indicacoes, carteirinha
    │   ├── inbox/               # chat multicanal
    │   ├── suporte/             # tickets, base de conhecimento
    │   ├── integracoes/         # HubSoft, providers IA
    │   ├── notificacoes/        # motor de comunicacao
    │   ├── dashboard/           # relatorios
    │   └── admin_aurora/        # painel SaaS (/aurora-admin/)
    ├── tests/                   # testes automatizados
    └── gerenciador_vendas/      # settings, urls, wsgi
```

## Documentacao

Toda a documentacao de produto fica em `docs/PRODUTO/`. Consultar antes de implementar.

Para detalhes completos, ver `CLAUDE.md` na raiz do workspace.
