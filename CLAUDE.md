# CLAUDE.md

## Regras Fundamentais

### Banco de Dados
- **NUNCA rodar comandos que afetem o banco de producao.** Sempre usar `--settings=gerenciador_vendas.settings_local` (SQLite local).
- Isso inclui: `migrate`, `makemigrations`, `createsuperuser`, `flush`, `loaddata`, `dumpdata`, `dbshell`, ou qualquer script que conecte ao PostgreSQL de producao.

### Escopo de Edicao
- **`robo/` liberado para edicao.** Estrutura modular em `apps/` e a fonte da verdade.
- **NAO editar** o projeto `megaroleta/`. Apenas leitura.
- **`vendas_web` esta morto.** Removido do INSTALLED_APPS. Nao referenciar.
- **Secrets em variaveis de ambiente.** Nenhuma credencial hardcoded.

### Escrita
- **Nao usar traco/hifen** como elemento de pontuacao em frases e textos de marketing. Usar ponto, virgula ou reescrever.

---

## Documentacao

### Regra principal
**Manter a documentacao sempre atualizada.** Ao implementar, modificar ou remover funcionalidades, atualizar os documentos correspondentes em `robo/docs/PRODUTO/`. Se nao existir documento para o modulo alterado, criar.

### Consultar antes de implementar
Antes de implementar qualquer funcionalidade, **consultar os documentos existentes** para entender o contexto, decisoes anteriores e estado atual:
- `robo/docs/PRODUTO/` — especificacoes de cada modulo
- `robo/docs/context/reunioes/` — decisoes tomadas em sessoes anteriores
- `robo/docs/context/tarefas/` — backlog e tarefas concluidas

### Hub de documentos
O arquivo `robo/exports/hub.html` e o gestor visual unificado. **Rodar automaticamente** sempre que um `.md` for criado ou modificado:

```
python scripts/gerar_hub.py
```

### Reunioes
Ao final de conversas relevantes, salvar resumo em:
```
robo/docs/context/reunioes/assunto_DD-MM-AAAA.md
```
Template em `robo/docs/context/reunioes/TEMPLATE.md`.

### Tarefas
Registrar tarefas em:
```
robo/docs/context/tarefas/assunto_DD-MM-AAAA.md
```
- Pendentes: `robo/docs/context/tarefas/backlog/`
- Concluidas: `robo/docs/context/tarefas/finalizadas/`
- Template: `robo/docs/context/tarefas/TEMPLATE.md`
- Toda implementacao deve estar vinculada a uma tarefa. Se nao existir, **criar antes de implementar**.

### Documentos de produto existentes

| Doc | Modulo |
|-----|--------|
| `01-REGUAS_PADRAO.md` | Reguas de automacao |
| `02-ROADMAP_PRODUTO.md` | Roadmap |
| `03-INTEGRACOES_HUBSOFT.md` | HubSoft |
| `04-TESTES.md` | Testes |
| `05-AUTOMACOES.md` | Motor de automacoes (detalhado) |
| `06-INBOX.md` | Inbox / Chat |
| `07-MODULO_COMERCIAL.md` | Comercial |
| `08-MODULO_MARKETING.md` | Marketing (campanhas + segmentos + automacoes) |
| `09-MODULO_CS.md` | Customer Success |
| `10-INTEGRACOES.md` | Integracoes |
| `11-PERMISSOES.md` | Permissoes granulares |
| `12-MODULO_SUPORTE.md` | Suporte |
| `13-MODULO_FLUXOS.md` | Fluxos visuais (node-based) |
| `14-MODULO_ATENDIMENTO.md` | Atendimento (engine, sessoes, N8N) |
| `15-SERVICOS_CRON.md` | Cron jobs e servicos periodicos |

---

## Projeto

### Stack
Python 3.11, Django 5.2, DRF, PostgreSQL, Gunicorn, Nginx, Drawflow.js, N8N

### Estrutura

```
hub/
├── CLAUDE.md                    ← este arquivo
├── scripts/gerar_hub.py         ← gerador do hub
├── robo/                        ← projeto principal
│   ├── docs/                    ← documentacao (GTM, PRODUTO, BRAND, AGENTES, context)
│   ├── exports/                 ← hub.html, drafts, deck
│   └── dashboard_comercial/gerenciador_vendas/   ← projeto Django
│       ├── apps/                ← 18 apps modulares
│       │   ├── sistema/         ← Tenant, auth, configs, logging, permissoes
│       │   ├── comercial/       ← leads, atendimento, cadastro, viabilidade, crm
│       │   ├── marketing/       ← campanhas, automacoes, emails
│       │   ├── cs/              ← clube, parceiros, indicacoes, carteirinha
│       │   ├── inbox/           ← chat multicanal
│       │   ├── suporte/         ← tickets, base de conhecimento
│       │   ├── integracoes/     ← HubSoft, providers IA
│       │   ├── notificacoes/    ← motor de comunicacao
│       │   ├── dashboard/       ← relatorios
│       │   └── admin_aurora/    ← painel SaaS (/aurora-admin/)
│       ├── tests/               ← testes
│       └── gerenciador_vendas/  ← settings, urls, wsgi
└── megaroleta/                  ← legacy (read-only)
```

### Como rodar

```bash
cd robo/dashboard_comercial/gerenciador_vendas
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local
```

### Commands essenciais

```bash
# Migrations locais
python manage.py makemigrations --settings=gerenciador_vendas.settings_local
python manage.py migrate --settings=gerenciador_vendas.settings_local

# Testes
python manage.py test tests/ --settings=gerenciador_vendas.settings_local

# Testes de automacoes (E2E)
python manage.py testar_automacoes --settings=gerenciador_vendas.settings_local

# Check
python manage.py check --settings=gerenciador_vendas.settings_local

# Hub
python scripts/gerar_hub.py
```

---

## Logging e Auditoria

Toda acao de usuario no sistema deve gerar log de auditoria. Usar:

```python
# Para views simples (decorator automatico)
from apps.sistema.utils import auditar

@auditar('categoria', 'acao', 'entidade')
def minha_view(request): ...

# Para logica custom
from apps.sistema.utils import registrar_acao

registrar_acao('categoria', 'acao', 'entidade', entidade_id, 'mensagem', request=request)
```

**Categorias:** auth, leads, crm, inbox, suporte, cs, marketing, config, admin, integracao, sistema

---

## Agentes

O assistente deve adotar a perspectiva do agente mais adequado ao tema da conversa. Identificar na primeira linha:

> `Agente: [Nome]`

| Tema | Agente |
|------|--------|
| Codigo, arquitetura, stack | Tech Lead |
| Produto, funcionalidades, fluxos | PM |
| Posicionamento, mensagens, canais | PMM |
| Precificacao, margens, ROI | CFO |
| Vendas, objecoes, parceiros | Head de Vendas |
| Textos, emails, WhatsApp | Copywriter |
| Automacoes, segmentacao, reguas | CRM e Automacao |
| Seguranca, LGPD, auth | Seguranca |
| Testes, qualidade | QA |
| Perguntas gerais, tarefas tecnicas | Assistente |

Definicoes completas em `robo/docs/AGENTES/`.
