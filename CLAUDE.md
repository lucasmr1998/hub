# CLAUDE.md

## Abordagem de Trabalho

**OBRIGATORIO:** Antes de implementar qualquer funcionalidade, correcao ou alteracao:
1. **Discutir antes de fazer.** Apresentar o problema/tarefa, sugerir abordagens e perguntar como o usuario quer proceder.
2. **Trazer opcoes.** Sempre que houver mais de uma forma de resolver, apresentar as opcoes com pros e contras.
3. **Nunca implementar sem alinhamento.** Mesmo que a solucao pareca obvia, perguntar antes. O usuario decide a direcao.
4. **Confirmar escopo.** Antes de comecar, resumir o que vai ser feito e pedir confirmacao.

### Checklist de "feature completa"

Uma feature so e considerada **pronta** quando TODOS os itens abaixo foram cumpridos:

- [ ] Codigo funcional com teste manual/automatizado passando
- [ ] Documentacao em `robo/docs/PRODUTO/` atualizada (modulo correspondente)
- [ ] Nenhum `print`, `console.log` ou comentario de debug deixado no codigo
- [ ] Imports/variaveis nao utilizados removidos
- [ ] Deploy validado com teste real em producao (se aplicavel)
- [ ] Nenhum bug critico aberto no escopo da feature
- [ ] `python manage.py check` sem erros
- [ ] Migration aplicada nos ambientes de dev e prod (se houver)

### Regra anti-paralelismo

Nao comecar feature nova enquanto houver bug critico aberto no produto em producao. Fechar bugs primeiro, feature depois. Ritmo cai no curto prazo mas acelera no medio (menos retrabalho, menos surpresas no deploy).

---

## Regras Fundamentais

### Banco de Dados
- **NUNCA rodar comandos que afetem o banco de producao.** Sempre usar `--settings=gerenciador_vendas.settings_local` (SQLite local).
- Isso inclui: `migrate`, `makemigrations`, `createsuperuser`, `flush`, `loaddata`, `dumpdata`, `dbshell`, ou qualquer script que conecte ao PostgreSQL de producao.

### Multi-Tenancy (CRITICO)
- **TODA query deve filtrar por tenant.** Nunca usar `.objects.all()` em views sem filtro de tenant.
- Models com `TenantMixin` usam `TenantManager` que filtra automaticamente. Models sem `TenantMixin` (como `IntegracaoAPI`) devem ser filtrados manualmente: `.filter(tenant=request.tenant)`.
- **Nunca expor dados de um tenant para outro.** Isso inclui: views, APIs, templates, selects, admin.
- Ao criar qualquer view, API ou query: **sempre verificar se o tenant esta sendo filtrado**.
- Ao criar models novos: **sempre usar TenantMixin** ou adicionar FK tenant com filtro manual.

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
**OBRIGATORIO: ao finalizar qualquer implementacao, atualizar o documento do modulo correspondente em `robo/docs/PRODUTO/` antes de concluir a tarefa.** Se nao existir documento para o modulo alterado, criar. Nunca considerar uma tarefa concluida sem a documentacao atualizada.

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

### Pre-commit hook de documentacao

Ao mexer em `apps/comercial/atendimento/`, `apps/inbox/`, `apps/comercial/crm/`, `apps/suporte/`, `apps/marketing/`, `apps/cs/`, `apps/integracoes/` ou `apps/assistente/`, atualizar tambem a doc correspondente em `robo/docs/PRODUTO/`.

O hook pre-commit em `.git/hooks/pre-commit` avisa quando detecta mudanca em modulo sem mudanca correspondente na doc. Nao bloqueia o commit, so avisa.

**Instalar hook apos clonar o repo:**
```
python scripts/instalar_hooks.py
```

Script de verificacao manual: `python scripts/verificar_docs.py` (mudancas nao commitadas) ou `--staged` (mudancas staged).

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

### Bancos de dados

| Ambiente | Settings | Banco | Uso |
|----------|----------|-------|-----|
| **Dev SQLite** | `settings_local` | `db_local.sqlite3` | Desenvolvimento rapido, testes |
| **Dev PostgreSQL** | `settings_local_pg` | `aurora_dev` (localhost:5432, user: postgres, pass: admin123) | Testes com banco real, validacao |
| **Producao** | `settings` | PostgreSQL remoto (variaveis .env) | **NUNCA usar no desenvolvimento** |

### Como rodar

```bash
cd robo/dashboard_comercial/gerenciador_vendas

# SQLite (padrao para desenvolvimento)
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local

# PostgreSQL local (para testar com banco real)
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local_pg
```

### Commands essenciais

```bash
# Migrations (SQLite)
python manage.py makemigrations --settings=gerenciador_vendas.settings_local
python manage.py migrate --settings=gerenciador_vendas.settings_local

# Migrations (PostgreSQL local)
python manage.py migrate --settings=gerenciador_vendas.settings_local_pg

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

O assistente deve adotar a perspectiva do agente mais adequado ao tema da conversa. **SEMPRE iniciar a resposta** identificando o agente na primeira linha:

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
