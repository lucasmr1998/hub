# Hubtrix

SaaS multi-tenant para provedores de internet. Centraliza Comercial, Marketing e Customer Success numa única plataforma, com integração nativa ao HubSoft, WhatsApp (Uazapi/Evolution) e providers de IA (OpenAI, Anthropic, Groq, Google AI).

**Tagline:** Vende mais. Perde menos. Fideliza sempre.

---

## Módulos

| Módulo | O que faz | Planos |
|--------|-----------|--------|
| **Comercial** | Leads, CRM Kanban, oportunidades, fluxos de atendimento (bot), cadastro, viabilidade, Assistente CRM via WhatsApp | Starter · Pro · Advanced |
| **Marketing** | Automações visuais (Drawflow), campanhas com detecção UTM, segmentos dinâmicos, réguas | Starter · Pro · Advanced |
| **CS** | Clube de Benefícios (gamificação), parceiros, indicações, carteirinha digital, NPS, retenção | Starter · Pro · Advanced |
| **Inbox** | Chat multicanal (WhatsApp, Email, Widget) com bot, agente e fila de distribuição | Incluso no Comercial |
| **Suporte** | Tickets, SLA por plano | Incluso no plano |
| **Assistente CRM** | Operar o CRM via WhatsApp natural (15 tools) | Incluso no Advanced |

---

## Stack

| Tecnologia | Uso |
|------------|-----|
| Python 3.11 | Backend |
| Django 5.2 + DRF | Framework web + API REST |
| PostgreSQL | Banco de produção |
| SQLite | Banco local (desenvolvimento) |
| Channels + Daphne + Redis | WebSocket para Inbox em tempo real |
| Gunicorn + Nginx | Servidor de produção |
| Drawflow.js | Editor visual de fluxos e automações |
| N8N (opcional) | Workflows customizados |
| Fernet (cryptography) | Encriptação de API keys e credenciais |

---

## Como rodar local

```bash
cd robo/dashboard_comercial/gerenciador_vendas

# Primeira vez
python manage.py migrate --settings=gerenciador_vendas.settings_local

# Rodar
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local
```

Acesse em http://127.0.0.1:8001

### Settings disponíveis

| Ambiente | Settings | Banco |
|----------|----------|-------|
| Dev SQLite (padrão) | `settings_local` | `db_local.sqlite3` |
| Dev PostgreSQL | `settings_local_pg` | `aurora_dev` (localhost:5432) |
| Produção | `settings` | PostgreSQL remoto (.env) |

---

## Estrutura do repositório

```
hub/
├── README.md                    ← este arquivo
├── CLAUDE.md                    ← convenções, agentes, regras do projeto
├── Dockerfile                   ← build da imagem (produção)
├── scripts/
│   ├── gerar_hub.py             ← gerador do visualizador de docs (hub.html)
│   └── verificar_docs.py        ← checker de consistência docs ↔ código
├── robo/                        ← projeto principal
│   ├── docs/                    ← toda a documentação
│   │   ├── PRODUTO/             ← spec técnica (core, integrações, ops, módulos)
│   │   ├── GTM/                 ← ICP, concorrentes, posicionamento, precificação, JTBDs
│   │   ├── BRAND/               ← identidade visual
│   │   ├── AGENTES/             ← perfis de agentes (Tech Lead, PM, PMM, etc.)
│   │   ├── OPERACIONAL/         ← contratos, materiais, templates, cases
│   │   └── context/             ← reuniões, tarefas (backlog/finalizadas), clientes
│   ├── exports/                 ← saídas geradas (hub.html, backlog.html)
│   └── dashboard_comercial/gerenciador_vendas/
│       ├── apps/                ← 15+ apps modulares
│       │   ├── sistema/         ← Tenant, auth, configs, logging, permissões
│       │   ├── comercial/       ← leads, atendimento, cadastro, viabilidade, crm
│       │   ├── marketing/       ← campanhas, automações
│       │   ├── cs/              ← clube, parceiros, indicações, carteirinha
│       │   ├── inbox/           ← chat multicanal
│       │   ├── suporte/         ← tickets
│       │   ├── integracoes/     ← HubSoft, providers IA
│       │   ├── assistente/      ← Assistente CRM via WhatsApp
│       │   ├── notificacoes/    ← motor de comunicação
│       │   ├── dashboard/       ← relatórios
│       │   └── admin_aurora/    ← painel SaaS (/aurora-admin/)
│       ├── tests/               ← testes automatizados
│       └── gerenciador_vendas/  ← settings, urls, wsgi, asgi
└── megaroleta/                  ← legacy (read-only, não editar)
```

---

## Multi-tenancy

Todos os dados são isolados por **tenant** (ISP cliente). Invariante do sistema:

- Models com `TenantMixin` filtram automaticamente via `TenantManager`
- Nenhum dado vaza entre tenants
- Auditoria (`LogSistema`) por tenant + categoria

Ver `CLAUDE.md` seção **Multi-Tenancy (CRÍTICO)** para regras completas.

---

## Documentação

A documentação é extensa e organizada por área. Duas formas de navegar:

### Visualizador web (recomendado)

O arquivo `robo/exports/hub.html` é gerado a partir dos markdowns e tem busca, árvore de navegação e renderização com accordions:

```bash
python scripts/gerar_hub.py  # gera/atualiza
```

Em produção, também está disponível em `/aurora-admin/docs/` (requer login staff).

### Docs principais

| Onde | O que tem |
|------|-----------|
| [`robo/docs/PRODUTO/`](robo/docs/PRODUTO/) | Spec técnica por módulo (`modulos/<nome>/`) + core + integrações + ops |
| [`robo/docs/PRODUTO/VISAO.md`](robo/docs/PRODUTO/VISAO.md) | Visão do produto (jornadas, modelo mental, princípios) |
| [`robo/docs/GTM/`](robo/docs/GTM/) | ICP, concorrentes, posicionamento, precificação |
| [`robo/docs/GTM/posicionamento/`](robo/docs/GTM/posicionamento/) | 3 Jobs-to-be-Done com pitches e objeções |
| [`robo/docs/GTM/cases/`](robo/docs/GTM/cases/) | Cases reais anonimizados |
| [`robo/docs/OPERACIONAL/`](robo/docs/OPERACIONAL/) | Contratos, implementações, materiais comerciais |
| [`robo/docs/context/clientes/`](robo/docs/context/clientes/) | Contexto por cliente ativo |
| [`CLAUDE.md`](CLAUDE.md) | Convenções, agentes, regras do projeto |

---

## Convenções de desenvolvimento

Antes de contribuir, ler [`CLAUDE.md`](CLAUDE.md). Resumo:

- **Nunca rodar comandos que afetem o banco de produção** — sempre `--settings=gerenciador_vendas.settings_local`
- **Toda query deve filtrar por tenant** — invariante multi-tenancy
- **Atualizar docs** em `robo/docs/PRODUTO/modulos/<modulo>/` ao mexer em código do módulo correspondente
- **Sem secrets hardcoded** — todas as credenciais em variáveis de ambiente
- **Não editar `megaroleta/`** — projeto legado, read-only

---

## Status do produto

| Módulo | Status |
|--------|--------|
| Comercial (leads + CRM + atendimento) | ✅ Em produção |
| Marketing (automações + segmentos) | ✅ Em produção |
| CS (Clube + parceiros + indicações) | ✅ Em produção |
| Inbox multicanal | ✅ Em produção |
| Suporte (tickets) | ✅ Em produção |
| Assistente CRM via WhatsApp | ✅ Em produção |
| NPS automatizado | ⚠️ Stub (models prontos, execução pendente) |
| CS/Retenção avançada | ⚠️ Stub (complementa AlertaRetencao do CRM) |

Clientes em produção: Megalink (30k assinantes), Fatepi (faculdade), Nuvyon (28k, em setup).

---

## Licença

Código proprietário. Todos os direitos reservados.
