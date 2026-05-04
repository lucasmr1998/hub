# CLAUDE.md

## Abordagem de Trabalho

**OBRIGATORIO:** Antes de implementar qualquer funcionalidade, correcao ou alteracao:
1. **Ler a documentacao do modulo PRIMEIRO.** Antes de qualquer alteracao, **sempre** ler `robo/docs/PRODUTO/` do modulo correspondente (ex: mexer em notificacoes -> ler `robo/docs/PRODUTO/ops/03-NOTIFICACOES.md`; mexer em integracao -> `robo/docs/PRODUTO/integracoes/`; modulo funcional -> `robo/docs/PRODUTO/modulos/<modulo>/`). A doc tem o desenho original, decisoes ja tomadas e armadilhas conhecidas. **Nao implementar sem ler a doc.** Se a doc nao existir, criar antes — nao confiar so no que o codigo aparenta fazer.
2. **Discutir antes de fazer.** Apresentar o problema/tarefa, sugerir abordagens e perguntar como o usuario quer proceder.
3. **Trazer opcoes.** Sempre que houver mais de uma forma de resolver, apresentar as opcoes com pros e contras.
4. **Nunca implementar sem alinhamento.** Mesmo que a solucao pareca obvia, perguntar antes. O usuario decide a direcao.
5. **Confirmar escopo.** Antes de comecar, resumir o que vai ser feito e pedir confirmacao.

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

**Desenvolvimento padrao:** sempre usar `--settings=gerenciador_vendas.settings_local` pra rodar codigo, testes, `runserver`, etc. No ambiente atual, `settings_local` e `settings_local_pg` apontam para o mesmo Postgres local (`aurora_dev` em `localhost:5432`). A alternativa SQLite nao esta configurada.

**Consultas read-only em producao:** permitidas quando necessarias pra investigacao/analise, com as seguintes regras.

**Permitido em producao:**
- `SELECT` via `manage.py shell`, `manage.py dbshell` ou scripts
- Queries do Django ORM com `.filter()`, `.values()`, `.annotate()`, `.aggregate()`
- Exports pontuais (CSV/JSON) pra analise offline
- Management commands marcados explicitamente como read-only

**Proibido em producao (sem autorizacao explicita do usuario por tarefa):**
- `migrate`, `makemigrations` — migrations sobem via CI/CD ou manualmente pelo dono
- `createsuperuser`, `flush`, `loaddata`, `dumpdata` — mudam estado
- Qualquer `.create()`, `.save()`, `.update()`, `.delete()`, `.bulk_*()` no ORM
- `UPDATE`, `INSERT`, `DELETE`, `TRUNCATE`, `ALTER` em SQL cru
- Rodar codigo que dispare signals que escrevam (ex: instanciar model com `save=True`)

**Obrigatorio em qualquer consulta de producao:**
1. **Avisar no chat** antes de conectar (ex: "vou rodar uma query em producao pra investigar X")
2. **Filtrar por tenant** sempre que o model herdar `TenantMixin`, mesmo em leitura
3. **Respeitar LGPD:** conversas, dados pessoais e PII precisam ser tratados como confidenciais. Nunca copiar/exibir dados de clientes em chat/docs sem necessidade clara
4. **Nunca compartilhar credenciais** ou dumps de producao em arquivos versionados ou canais externos
5. **Em caso de duvida, perguntar ao usuario** antes de rodar

**Se o comando que quero rodar cair na zona cinza** (ex: "atualizar 1 campo num lead"), **SEMPRE confirmar com o usuario antes de executar**, mesmo que pareça trivial.

**Credenciais de acesso ao servidor de producao:** ver arquivo local `.env.prod_readonly` (gitignored). Contem `PROD_DB_*` (Postgres) e eventualmente SSH do VPS Hostinger (EasyPanel). **NUNCA** colar credenciais no chat ou em arquivos versionados. Servidor roda no IP `103.199.187.4`; Postgres na porta 5433; console do EasyPanel (UI) ja roda dentro do container do app Django — comandos `python manage.py X` funcionam direto sem `docker exec`.

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

Ao mexer em `apps/comercial/atendimento/`, `apps/inbox/`, `apps/comercial/crm/`, `apps/suporte/`, `apps/marketing/`, `apps/cs/`, `apps/integracoes/` ou `apps/assistente/`, atualizar tambem a doc correspondente em `robo/docs/PRODUTO/modulos/<modulo>/`.

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

**A partir de 04/05/2026, fonte da verdade do backlog é o módulo Workspace** (não mais markdown).

- **Onde:** `https://app.hubtrix.com.br/workspace/` — tenant Aurora HQ (id 3)
- **Tabela DB:** `workspace_tarefa`
- **Consulta read-only via SQL:** ver `robo/docs/context/tarefas/README.md`

Toda implementação deve estar vinculada a uma tarefa no Workspace. Se nao existir, **criar antes de implementar** — pela UI, não via markdown.

A pasta `robo/docs/context/tarefas/backlog/` e `finalizadas/` ficam **deprecadas** (preservadas como histórico). Não criar arquivos `.md` novos lá. O `TEMPLATE.md` segue como referência de campos pra preencher na UI do Workspace.

### Documentos de produto existentes

Estrutura hierarquica em `robo/docs/PRODUTO/`:

**core/** — transversais
- `core/00-STATUS.md` — Estado atual de cada modulo
- `core/01-ROADMAP.md` — Roadmap
- `core/02-TESTES.md` — Estrategia de testes
- `core/03-PERMISSOES.md` — Permissoes granulares

**integracoes/**
- `integracoes/01-HUBSOFT.md` — HubSoft
- `integracoes/02-INTEGRACOES.md` — Demais integracoes
- `integracoes/03-APIS_N8N.md` — APIs consumidas pelo N8N

**ops/**
- `ops/01-DEPLOY.md` — Deploy
- `ops/02-CRON.md` — Cron jobs
- `ops/03-NOTIFICACOES.md` — Motor de notificacoes

**modulos/** — um diretorio por modulo funcional, cada um com `README.md` + arquivos por funcionalidade
- `modulos/atendimento/` — Engine, sessoes, recontato
- `modulos/comercial/` — Leads, cadastro, viabilidade, CRM (pipeline/oportunidades/metas)
- `modulos/inbox/` — Chat multicanal, distribuicao, widget, websocket
- `modulos/fluxos/` — Editor visual, nodos, integracao IA
- `modulos/assistente-crm/` — Assistente via WhatsApp cross-tenant
- `modulos/marketing/` — Campanhas, segmentos, automacoes (regras e motor)
- `modulos/suporte/` — Tickets e SLA
- `modulos/cs/` — Clube, parceiros, indicacoes, carteirinha, NPS, retencao

Indice completo em `robo/docs/PRODUTO/README.md`.

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
│   ├── docs/                    ← documentacao (GTM, PRODUTO, BRAND, AGENTES, OPERACIONAL, context)
│   │   └── OPERACIONAL/         ← contratos + implementacao + materiais (templates, propostas, deck)
│   ├── exports/                 ← saidas geradas (hub.html, backlog.html)
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
| **Dev PostgreSQL (padrao)** | `settings_local` ou `settings_local_pg` | `aurora_dev` (localhost:5432, user: postgres, pass: admin123) | Desenvolvimento e validacao. Ambos os settings apontam para o mesmo Postgres local. |
| **Producao** | `settings` | PostgreSQL remoto (variaveis .env) | **NUNCA usar no desenvolvimento** |

> Historico: originalmente `settings_local` apontava para SQLite (`db_local.sqlite3`) e `settings_local_pg` para Postgres. Hoje ambos foram unificados no Postgres local para garantir paridade com producao. Se precisar de SQLite isolado pra um teste, crie um settings dedicado em vez de assumir que `settings_local` e SQLite.

### Como rodar

```bash
cd robo/dashboard_comercial/gerenciador_vendas

# Desenvolvimento padrao (Postgres local aurora_dev)
python manage.py runserver 8001 --settings=gerenciador_vendas.settings_local
```

### Commands essenciais

```bash
# Migrations (Postgres local aurora_dev)
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

## Design System e Templates

Estrutura unificada de templates em `robo/dashboard_comercial/gerenciador_vendas/templates/`. Pagina de showcase em `/design-system/preview/` (layout) e `/design-system/componentes/` (biblioteca).

### Onde fica o que

- **Tokens CSS:** `templates/layouts/base.html` — cores, tipografia, espacamentos, radii, sombras, layout sizes. Fonte unica de variaveis.
- **Layout base pra paginas logadas:** `templates/layouts/layout_app.html` — ja traz topbar + sidebar + flyout + toast container + JS base (modal/toast/tabs/flyout de hover). **Toda pagina logada deve extender este layout.**
- **Partials reutilizaveis:** `templates/partials/{topbar,sidebar,sidebar_subnav}.html` — mexer aqui propaga pra todas as paginas.
- **Biblioteca de componentes:** `templates/components/*.html` — botao, input, badge, stat_card, modal, breadcrumbs, tabs. Cada arquivo e um partial reutilizavel documentado no inicio do proprio arquivo.

### Regra de ouro

- Toda pagina logada **deve extender** `layouts/layout_app.html`. **Nunca duplicar** topbar/sidebar no template da pagina.
- Mudancas visuais globais vao nos partials/tokens, nunca em CSS inline da pagina.
- Ao criar elemento de UI que ja exista como componente, **usar o componente**. Nao reinventar botao/input/badge inline.
- **Se o elemento nao existe ainda no DS, criar o componente primeiro** em `templates/components/` e adicionar ao showcase (`/design-system/componentes/`). So depois usar. Isso evita o DS voltar a drift de inline CSS/one-offs durante a migracao.
- **Se o padrao visual ja existe num preview/showcase, COPIAR a estrutura HTML/CSS dele — nao reinventar.** Os previews em `/design-system/preview/` e `/design-system/componentes/` sao a fonte da verdade de como cada padrao se comporta (colapsar, flyout, dropdown, toast, etc.). Quando migrar pra server-side, mantem a mesma marcacao e so troca o conteudo dinamico. Nao adicionar variantes novas (tipo "botao flutuante absoluto") quando o preview ja tem o padrao certo. Se o preview esta errado, conserta o preview primeiro e replica.

### Como criar pagina nova

```django
{% extends "layouts/layout_app.html" %}
{% block title %}Minha pagina — Hubtrix{% endblock %}

{% block subnav %}{# opcional — incluir partial de subnav ou HTML custom #}{% endblock %}
{% block main_mod %} has-subnav{% endblock %}{# so se tiver subnav #}

{% block content %}
  <h1>Minha pagina</h1>
  {% include "components/button.html" with variant="primary" label="Salvar" icon="bi-check" %}
{% endblock %}
```

### Como usar componentes

```django
{% include "components/button.html" with variant="primary" label="Salvar" %}
{% include "components/input.html" with name="email" label="Email" type="email" required=True %}
{% include "components/badge.html" with variant="success" label="Ativo" dot=True %}
{% include "components/stat_card.html" with label="Leads" value="248" delta="+12%" delta_trend="up" icon="bi-person-plus" %}
{% include "components/modal.html" with id="meu-modal" title="..." confirm_label="Salvar" %}
{% include "components/tabs.html" with items=tabs_list %}
{% include "components/breadcrumbs.html" with items=crumbs %}
```

JS globais disponiveis em qualquer pagina que use o layout: `abrirModal(id)`, `fecharModal(id)`, `toast(titulo, msg, 'success'|'warning'|'danger'|'info')`.

### Backlog de migracao

Paginas legadas (CRM, Inbox, aurora-admin, etc.) ainda NAO usam o design system. A migracao e gradual — cada vez que uma pagina for tocada por outro motivo, migrar tambem pro DS.

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

**SEMPRE iniciar a resposta** identificando o agente na primeira linha:

> `Agente: [Nome]`

### Regra de classificacao (obrigatoria antes de responder)

Antes de cada resposta, fazer esta pergunta: **"o que o usuario esta pedindo?"** — e mapear para o agente conforme a tabela abaixo. NAO defaultar em Tech Lead quando o tema e de produto, conteudo, vendas ou processo.

| Tema | Agente | Exemplos |
|------|--------|----------|
| Codigo, arquitetura, stack, scripts, migrations, debug | **Tech Lead** | refatorar engine.py, quebrar script, fix de bug, performance, Django |
| Funcionalidade, fluxo de usuario, escopo de feature, priorizacao | **PM** | "como deveria funcionar X", decidir cortes de escopo, definir MVP |
| Posicionamento, mensagem de mercado, canais, entregas para cliente | **PMM** | deck, one-pager, como descrever produto, comparacao com concorrente |
| Precificacao, margens, ROI, unit economics | **CFO** | precos, margens, CAC, LTV, pricing de plano |
| Vendas, objecoes, parceiros, discovery | **Head de Vendas** | script de venda, resposta a objecao, treinamento de parceiro |
| Texto comercial: emails, WhatsApp, social, copy | **Copywriter** | escrever mensagem, ajustar tom, template de email |
| Automacoes, segmentacao, reguas de relacionamento | **CRM e Automacao** | regra de trigger, segmento, jornada |
| Seguranca, LGPD, auth, permissoes | **Seguranca** | vulnerabilidade, politica de senha, escopo de permissao |
| Testes, qualidade, QA | **QA** | casos de teste, estrategia de teste, regressao |
| Organizacao de arquivos/pastas do projeto (quando NAO e codigo) | **PM** | como organizar docs, hierarquia de pastas de conteudo |
| Conversa geral, pergunta direta, favor pontual | **Assistente** | "que horas sao", "me explica X" |

### Casos de fronteira (NAO default em Tech Lead)

- **Reorganizar docs/materiais/pastas de conteudo:** PM (organizacao de informacao), NAO Tech Lead
- **Decidir o que vai pro cliente vs fica interno:** PMM
- **Definir o que e "entrega" vs "operacional":** PM ou PMM conforme o foco
- **Escrever sobre o produto para publico externo:** PMM ou Copywriter
- **Script ou automacao que publica/envia algo:** Copywriter (texto) + Tech Lead (implementacao) — escolher o lado dominante do pedido

### Multi-tema

Se o pedido legitimamente cobre dois agentes (ex: "organize os templates E ajuste o script"), escolher o agente do **lado dominante** da pergunta. Se for 50/50, declarar que e misto na resposta.

Definicoes completas em `robo/docs/AGENTES/`.
