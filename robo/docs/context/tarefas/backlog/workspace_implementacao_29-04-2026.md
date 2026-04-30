---
name: "Workspace + Comando — migração total do megaroleta gestão"
description: "Criar `apps/workspace/` (multi-tenant, ATIVO) e `apps/comando/` (mono-tenant, DORMENTE). Migra TUDO do megaroleta gestão pra desligá-lo de vez."
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Workspace + Comando — Implementação Fase 1 — 29/04/2026

**Data:** 29/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** 🔄 Em andamento — PRs 1/2/3/4/5 entregues (30/04)

---

## Descrição

Trazer pro robo **toda a camada de gestão** do `megaroleta/gestao/`, com objetivo final de **deletar o megaroleta**. Migração em 2 apps com finalidades distintas:

### App 1 — `apps/workspace/` (ATIVO na fase 1)

Feature de produto pra clientes. Multi-tenant, com UI, sidebar, módulo ativável no aurora-admin.

**Inclui:**
- 6 models (Projeto, Etapa, Tarefa, Nota, Documento, PastaDocumento)
- CRUD completo + Kanban + editor markdown
- Visão "minhas tarefas" cross-projeto
- Permissões granulares (4 funcionalidades)
- Validação interna pelo tenant Hubtrix antes de virar feature comercial

### App 2 — `apps/comando/` (DORMENTE na fase 1)

Operação interna do Hubtrix. Mono-tenant (igual aurora-admin), sem UI, só schema + dados importados pra preservar histórico.

**Inclui:**
- 11 models (Agente, ToolAgente, LogTool, MensagemChat, Reuniao, MensagemReuniao, Automacao, Alerta, Proposta, FAQCategoria, FAQItem)
- Migration completa criando schema
- Management command importando TODOS os dados do megaroleta (incluindo histórico)
- **Sem views, sem URLs, sem templates, sem sidebar**
- Models acessíveis apenas via Django admin + shell (e fase 2/3 quando ressuscitar)

### Resultado final da fase 1

- Workspace funcionando como feature do produto Hubtrix
- Comando com schema + dados preservados
- **Megaroleta deletado do disco** (após fase 1 validada)

---

## Decisões já fechadas

| # | Decisão | Resposta |
|---|---------|----------|
| 1 | Tenant scope (workspace) | C — híbrido (multi-tenant desde já, validação interna primeiro) |
| 2 | Local workspace | App novo `apps/workspace/` |
| 3 | Mapeamento sobreposição | Feito — sem conflitos sérios, reusa LogSistema/Notificacao/Funcionalidade |
| 4 | Markdown | Puro com sanitização Bleach |
| 5 | Escopo | Paridade completa fase 1, sem cortes |
| 6 | Campos IA | Mantidos preparados desde já. **FK Agente JÁ ATIVAS** (Comando traz Agente no schema desde fase 1) |
| 7 | Sanitização | Adicionar `bleach` no requirements |
| 8 | Permissões workspace | 4 funcionalidades granulares + defaults A (Supervisores ganham `ver+criar+editar_proprios`) |
| 9 | URLs workspace | `/workspace/...` prefixado |
| 10 | Estratégia "resto do gestão" | Trazer junto, dormente em `apps/comando/` |
| 11 | Local comando | App novo `apps/comando/` (mono-tenant, sem TenantMixin) |
| 12 | Migração de dados | C — migra TUDO incluindo histórico. User limpa depois. |
| 13 | Quando deletar megaroleta | Após fase 1 inteira validada |
| 14 | Paralelismo | B — paralelizar PR 2+3 e PR 4+5 |

---

## Estrutura do app

```
apps/workspace/
├── __init__.py
├── apps.py
├── admin.py                       # Django admin (Projeto, Tarefa, Documento)
├── models.py                      # 6 models
├── views/
│   ├── __init__.py
│   ├── dashboard.py               # /workspace/ (home)
│   ├── projetos.py                # CRUD projeto + kanban
│   ├── tarefas.py                 # CRUD tarefa + visão "minhas"
│   ├── documentos.py              # CRUD documento + pastas
│   └── api.py                     # AJAX (kanban move, notas, etc.)
├── urls.py                        # Roteamento
├── forms.py                       # ModelForms
├── permissions.py                 # Helpers de permissão
├── markdown_utils.py              # render + sanitização Bleach
├── signals.py                     # Auditoria pós-save (opcional)
├── migrations/
│   └── 0001_initial.py
├── management/commands/
│   └── seed_workspace_funcionalidades.py    # Cadastra 4 funcionalidades
├── templates/workspace/
│   ├── home.html                  # Dashboard
│   ├── projetos/
│   │   ├── lista.html
│   │   ├── editar.html
│   │   └── kanban.html
│   ├── tarefas/
│   │   ├── lista.html             # "Minhas tarefas"
│   │   ├── detalhe.html
│   │   └── editar.html
│   └── documentos/
│       ├── lista.html
│       ├── detalhe.html
│       └── editar.html
└── static/workspace/
    ├── css/workspace.css
    └── js/
        ├── kanban.js              # Drag-and-drop
        └── editor.js              # Markdown live preview (opcional)
```

---

## Models — detalhamento

Todos herdam `TenantMixin` e usam `TenantManager`. Campo `tenant` é FK obrigatório.

### Projeto

```
- id (PK)
- tenant (FK Tenant, obrigatório)               [TenantMixin]
- nome (CharField 200)
- descricao (TextField, blank)
- status (CharField, choices: PLANEJAMENTO, EM_ANDAMENTO, PAUSADO, CONCLUIDO, CANCELADO)
- prioridade (CharField, choices: BAIXA, MEDIA, ALTA, CRITICA)
- objetivo (TextField, blank)
- publico_alvo (TextField, blank)
- criterios_sucesso (TextField, blank)
- riscos (TextField, blank)
- premissas (TextField, blank)
- responsavel (FK User, nullable)
- stakeholders (TextField, blank)               # texto livre por enquanto
- data_inicio (DateField, nullable)
- data_fim_prevista (DateField, nullable)
- contexto_agentes (TextField, blank)           # PREPARADO PRA IA
- orcamento (DecimalField, nullable)
- ativo (BooleanField, default=True)
- criado_em (DateTimeField, auto_now_add)
- atualizado_em (DateTimeField, auto_now)

Métodos:
- progresso() → % calculado das tarefas filhas
- ativas_count(), concluidas_count() → conveniência
```

### Etapa

```
- id (PK)
- tenant (FK)                                   [TenantMixin]
- projeto (FK Projeto, related_name='etapas')
- nome (CharField 200)
- descricao (TextField, blank)
- ordem (IntegerField, default=0)
- data_inicio (DateField, nullable)
- data_fim (DateField, nullable)
- criado_em, atualizado_em

Ordering: ('ordem', 'id')
```

### Tarefa

```
- id (PK)
- tenant (FK)                                   [TenantMixin]
- projeto (FK Projeto, related_name='tarefas')
- etapa (FK Etapa, nullable, related_name='tarefas')
- titulo (CharField 200)
- descricao (TextField, blank)
- responsavel (FK User, nullable)
- status (CharField, choices: RASCUNHO, PENDENTE, EM_ANDAMENTO, CONCLUIDA, BLOQUEADA)
- prioridade (CharField, choices: BAIXA, MEDIA, ALTA, CRITICA)
- data_limite (DateField, nullable)
- data_conclusao (DateTimeField, nullable)
- ordem (IntegerField, default=0)               # pra kanban drag-drop
# Campos IA — PREPARADOS, ainda não usados em fase 1:
- objetivo (TextField, blank)
- contexto (TextField, blank)
- passos (TextField, blank)
- entregavel (TextField, blank)
- criterios_aceite (TextField, blank)
- log_execucao (TextField, blank)
- nivel_delegacao (IntegerField, default=0)     # 0=humano, 1-2=agente
- documento_processo (FK Documento, nullable)   # SOP da tarefa
- criado_por_agente (FK comando.Agente, nullable)  # ATIVA — Agente vem em apps/comando/ na mesma fase
- criado_em, atualizado_em
```

**✅ FK Agente fica ativa desde já.** Como `apps/comando/` traz o model Agente na fase 1 (mesmo que dormente), o campo `criado_por_agente = FK('comando.Agente', null=True, related_name='tarefas_criadas')` fica funcional desde a primeira migration. Mesmo aplicado pra `Documento.agente_origem`.

### Nota

```
- id (PK)
- tenant (FK)                                   [TenantMixin]
- tarefa (FK Tarefa, related_name='notas')
- texto (TextField)
- autor (FK User, nullable)
- criado_em
```

### Documento

```
- id (PK)
- tenant (FK)                                   [TenantMixin]
- titulo (CharField 200)
- slug (SlugField, único POR TENANT, max 220)   # unique_together com tenant
- categoria (CharField, choices: ESTRATEGIA, REGRAS, ROADMAP, DECISOES, ENTREGA, SESSAO, CONTEXTO, RELATORIO, EMAIL, PROCESSO, IMAGEM, OUTRO)
- conteudo (TextField, blank)                   # markdown puro
- arquivo (FileField, upload_to='workspace/docs/<tenant_id>/', nullable)
- resumo (TextField, blank)
- descricao (TextField, blank)
- visivel_agentes (BooleanField, default=True)  # PREPARADO PRA IA
- pasta (FK PastaDocumento, nullable, related_name='documentos')
- agente_origem (FK comando.Agente, nullable)   # ATIVA — Agente traz schema na fase 1 via apps/comando/
- ordem (IntegerField, default=0)
- criado_por (FK User, nullable)
- criado_em, atualizado_em

Métodos:
- conteudo_html() → markdown sanitizado
- save() → gera slug auto se vazio
```

### PastaDocumento

```
- id (PK)
- tenant (FK)                                   [TenantMixin]
- nome (CharField 100)
- slug (SlugField, único POR TENANT)
- icone (CharField 50, default='bi-folder')     # Bootstrap Icons (não FontAwesome — alinhar com DS Hubtrix)
- cor (CharField 7, default='#252020')          # hex da paleta v2
- ordem (IntegerField, default=0)
- pai (FK self, nullable, related_name='subpastas')
- criado_em

Ordering: ('ordem', 'nome')
```

---

## Migrações de bibliotecas

**`requirements.txt`:**
```
+ bleach==6.1.0
+ markdown==3.5.1                    # se ainda não estiver
```

**`markdown_utils.py`:**
- `render_markdown(texto: str) → str` (HTML sanitizado)
- `sanitizar_input(texto: str) → str` (sanitização antes de salvar)
- Whitelist de tags/atributos baseada no helper do megaroleta

---

## Permissões — funcionalidades novas

Cadastrar via management command `seed_workspace_funcionalidades`:

```
workspace.ver                        # Ver Workspace (qualquer tela)
workspace.criar_projeto              # Criar projeto
workspace.editar_proprios            # Editar projetos/tarefas/docs próprios
workspace.editar_todos               # Editar projetos/tarefas/docs de qualquer um
```

**Defaults nos perfis padrão:**

| Perfil | ver | criar_projeto | editar_proprios | editar_todos |
|--------|-----|---------------|-----------------|--------------|
| Admin | ✅ | ✅ | ✅ | ✅ |
| Supervisor Comercial | ✅ | ✅ | ✅ | ❌ |
| Supervisor Marketing | ✅ | ✅ | ✅ | ❌ |
| Supervisor CS | ✅ | ✅ | ✅ | ❌ |
| Supervisor Suporte | ✅ | ❌ | ✅ | ❌ |
| Vendedor / Atendente | ❌ | ❌ | ❌ | ❌ |

**Padrão de uso nas views:**
```python
@login_required
def lista_projetos(request):
    if not user_tem_funcionalidade(request, 'workspace.ver'):
        return HttpResponseForbidden()
    ...
```

---

## URLs

```python
urlpatterns = [
    path('', views.home, name='workspace_home'),

    # Projetos
    path('projetos/', views.projetos_lista, name='projetos_lista'),
    path('projetos/criar/', views.projeto_criar, name='projeto_criar'),
    path('projetos/<int:pk>/', views.projeto_detalhe, name='projeto_detalhe'),
    path('projetos/<int:pk>/editar/', views.projeto_editar, name='projeto_editar'),
    path('projetos/<int:pk>/excluir/', views.projeto_excluir, name='projeto_excluir'),
    path('projetos/<int:pk>/kanban/', views.projeto_kanban, name='projeto_kanban'),

    # Etapas (sob projeto)
    path('projetos/<int:projeto_pk>/etapas/criar/', views.etapa_criar, name='etapa_criar'),
    path('etapas/<int:pk>/editar/', views.etapa_editar, name='etapa_editar'),
    path('etapas/<int:pk>/excluir/', views.etapa_excluir, name='etapa_excluir'),

    # Tarefas
    path('tarefas/', views.minhas_tarefas, name='minhas_tarefas'),
    path('tarefas/<int:pk>/', views.tarefa_detalhe, name='tarefa_detalhe'),
    path('tarefas/<int:pk>/editar/', views.tarefa_editar, name='tarefa_editar'),
    path('tarefas/<int:pk>/excluir/', views.tarefa_excluir, name='tarefa_excluir'),
    path('projetos/<int:projeto_pk>/tarefas/criar/', views.tarefa_criar, name='tarefa_criar'),

    # Notas em tarefa
    path('tarefas/<int:tarefa_pk>/notas/criar/', views.nota_criar, name='nota_criar'),
    path('notas/<int:pk>/excluir/', views.nota_excluir, name='nota_excluir'),

    # Documentos
    path('documentos/', views.documentos_lista, name='documentos_lista'),
    path('documentos/criar/', views.documento_criar, name='documento_criar'),
    path('documentos/<int:pk>/', views.documento_detalhe, name='documento_detalhe'),
    path('documentos/<int:pk>/editar/', views.documento_editar, name='documento_editar'),
    path('documentos/<int:pk>/excluir/', views.documento_excluir, name='documento_excluir'),

    # Pastas
    path('pastas/', views.pastas_lista, name='pastas_lista'),
    path('pastas/criar/', views.pasta_criar, name='pasta_criar'),
    path('pastas/<slug:slug>/', views.pasta_detalhe, name='pasta_detalhe'),
    path('pastas/<int:pk>/editar/', views.pasta_editar, name='pasta_editar'),
    path('pastas/<int:pk>/excluir/', views.pasta_excluir, name='pasta_excluir'),

    # APIs AJAX
    path('api/kanban/mover/', views.api_kanban_mover, name='api_kanban_mover'),
    path('api/tarefa/<int:pk>/status/', views.api_tarefa_status, name='api_tarefa_status'),
]
```

Registrar em `gerenciador_vendas/urls.py`:
```python
path('workspace/', include('apps.workspace.urls')),
```

---

## Integração com sistema de módulos (ativável por tenant)

Workspace segue o padrão dos outros módulos do robo (Comercial/Marketing/CS): **flag por tenant + plano + permissão de usuário**. Super-admin liga/desliga via aurora-admin.

### Arquivos a editar (mapa exato — 8 pontos)

| # | Arquivo | Mudança |
|---|---------|---------|
| 1 | `apps/sistema/models.py` (Tenant) | + `modulo_workspace = BooleanField(default=False)` |
| 2 | `apps/sistema/models.py` (Tenant) | + `plano_workspace = CharField(choices=PLANO_CHOICES, default='starter')` |
| 3 | `apps/sistema/models.py` (Tenant) | + `plano_workspace_ref = FK(Plano, nullable)` |
| 4 | `apps/sistema/models.py` (Plano.MODULO_CHOICES) | + `('workspace', 'Workspace')` |
| 5 | `apps/sistema/models.py` (PermissaoUsuario) | + `@property def acesso_workspace` |
| 6 | `apps/sistema/context_processors.py` | + `ctx['modulo_workspace'] = tenant.modulo_workspace` |
| 7 | `apps/sistema/middleware.py` (`_MODULO_MAP`) | + `('/workspace/', 'acesso_workspace')` |
| 8 | `apps/admin_aurora/views.py` (`tenant_detalhe_view`) | Estender bloco `atualizar_modulos` pra incluir workspace |
| 9 | `apps/admin_aurora/templates/admin_aurora/tenant_detalhe.html` | + card de toggle workspace (igual aos outros) |
| 10 | `templates/partials/sidebar.html` | + bloco `{% if modulo_workspace and (is_superuser or perm.acesso_workspace) %}` |
| 11 | `templates/partials/sidebar_subnav.html` | + subnav workspace (Início, Projetos, Minhas tarefas, Documentos, Pastas) |

### Comportamento esperado

- **Tenant sem o módulo ligado:** Workspace não aparece na sidebar. Tentativa de acessar `/workspace/` → middleware retorna 403.
- **Tenant com módulo ligado + usuário sem permissão:** Workspace não aparece na sidebar. Tentativa de acessar → 403 (middleware via `acesso_workspace=False`).
- **Tenant com módulo ligado + usuário com permissão `acesso_workspace`:** sidebar mostra Workspace, links funcionam, e dentro a granularidade fica nas funcionalidades (`workspace.criar_projeto`, etc.).

### Plano (tier) do Workspace

Mesmo padrão dos outros módulos: `starter`, `start`, `pro`. Default `starter` — diferenciação de tier fica pra fase futura (não impacta features na fase 1).

### Item de menu

- **Raiz:** "Workspace" com ícone `bi-kanban-fill`
- **Subnav:**
  - Início (`workspace_home`)
  - Projetos (`projetos_lista`)
  - Minhas tarefas (`minhas_tarefas`)
  - Documentos (`documentos_lista`)
  - Pastas (`pastas_lista`)

---

## Auditoria (LogSistema)

Padrão pra cada operação destrutiva ou de mudança:

```python
@auditar('workspace', 'criar', 'projeto')
def projeto_criar(request):
    ...

# OU pra logica custom:
registrar_acao('workspace', 'mover_tarefa', 'tarefa', tarefa.id,
               f'Tarefa "{tarefa.titulo}" movida de {old} para {new}',
               request=request)
```

**Categorias usadas:** `workspace` (nova categoria — adicionar ao enum em `apps/sistema/models.py:LogSistema.CATEGORIAS` se for choices field, ou só usar string livre se for CharField sem choices — verificar).

---

## Ordem de implementação (PRs)

Cada PR é testável de forma isolada. Ordem garante green build em cada commit.

### Sequencial — backbone

| PR | Conteúdo | Status |
|----|----------|--------|
| **1** | **`apps/workspace/` + `apps/comando/` skeletons** — 6 models workspace + 11 models comando + migrations + admin (ambos) + `bleach` + `markdown_utils` + seed funcionalidades + integração tenant | ✅ Entregue |
| **2** | Views/URLs de **Documentos + PastaDocumento** + templates + render markdown + upload anexos + geração IA + fix media serving | ✅ Entregue (30/04) |
| **3** | Views/URLs de **Projeto + Etapa** + templates + fix form validation (ordem) + N+1 progresso() | ✅ Entregue (30/04) |
| **4** | Views/URLs de **Tarefa + Nota** + visão "minhas tarefas" + fix form validation | ✅ Entregue (30/04) |
| **5** | Kanban interativo (HTML + JS drag-drop + API) | ✅ Entregue (30/04) |
| **6** | **Aurora-admin** (toggle workspace) + sidebar/subnav + permissões aplicadas + auditoria | ⏳ Pendente |
| **7** | **Importação de dados** do megaroleta → `apps/comando/` (management command + dry-run + execução) | ⏳ Pendente |
| **8** | Doc do módulo workspace em `robo/docs/PRODUTO/modulos/workspace/` + doc do comando + atualizar memória | ⏳ Pendente |
| **9** | **Deletar megaroleta** — apaga diretório, atualiza CLAUDE.md, atualiza docs, verifica imports | ⏳ Pendente |

**Extra entregue (30/04):** 6 posts Instagram importados do Paper MCP como Documentos workspace (formato=imagem, AnexoDocumento). Media serving configurado (MEDIA_URL=/media/, MEDIA_ROOT=hub root) em settings_local e settings_local_pg.

### Paralelos workspace UI — após PR 1

**Frente A:**
- **PR 2** — Views/URLs de **Documentos + PastaDocumento** + templates + render markdown
- **PR 3** — Views/URLs de **Projeto + Etapa** + templates

**Frente B:**
- **PR 4** — Views/URLs de **Tarefa + Nota** + visão "minhas tarefas"
- **PR 5** — Kanban interativo (HTML + JS drag-drop + API)

**Mitigação de dependência:** Frente A faz Documentos primeiro (standalone). Frente B avança Kanban JS com mock, integração final no fim.

**Total estimado revisado:** 6-8 dias úteis com paralelismo (workspace + comando + import + delete megaroleta).

---

## Riscos e cuidados

1. **Slug único por tenant** — `unique_together = ('tenant', 'slug')` em Documento e PastaDocumento. Não usar `unique=True` simples.
2. **Filtro de tenant manual em FKs** — `responsavel`, `criado_por` usam User que não tem TenantMixin. Em forms, filtrar choices por usuários do tenant atual: `User.objects.filter(permissaousuario__tenant=request.tenant)`.
3. **Bleach config** — replicar whitelist exata do `_sanitizar_markdown` do megaroleta. Tags permitidas: `p, h1-h6, strong, em, ul, ol, li, blockquote, code, pre, a, img, table, thead, tbody, tr, td, th, br, hr`. Atributos: `href, src, alt, title, class, id` (whitelisted). Protocolos: `http, https, mailto`.
4. **Upload de arquivos** — `Documento.arquivo` deve usar path com tenant id pra evitar colisão: `upload_to='workspace/docs/<tenant_id>/<slug>/'`. Função custom `_get_upload_path`.
5. **Migration zero-downtime** — App novo, primeira migration cria tudo. Não há risco de schema legacy.
6. **Bootstrap Icons em vez de FontAwesome** — o gestão usa FA, alinhar com DS Hubtrix (BS Icons).
7. **Cor default em PastaDocumento** — usar paleta v2 (`#252020` tinta como default, sienna `#E76F51` como acento opcional).
8. **Performance kanban** — em projetos com 100+ tarefas, usar `select_related('responsavel', 'etapa')` e `prefetch_related('notas')`.

---

## App `apps/comando/` (DORMENTE)

App separado pra abrigar a camada de IA do gestão **sem ativá-la**. Objetivo: trazer schema + dados pra que o megaroleta possa morrer.

### Características distintivas

- **Mono-tenant.** Models NÃO usam TenantMixin. Documentar no header de cada model: `# Mono-tenant: operação interna do Hubtrix. Não usar TenantMixin.`
- **Sem UI.** Sem views, URLs, templates, sidebar entry. Só admin Django.
- **Sem middleware de bloqueio.** `/comando/` não existe como URL na fase 1.
- **Acessível só via:** Django admin + `python manage.py shell`. Pra debug e import inicial.

### 11 models (paridade com megaroleta gestão, ajustes mínimos)

```
apps/comando/models.py:

class Agente(models.Model):
    slug = models.SlugField(unique=True)
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    icone = models.CharField(max_length=50, default='bi-robot')  # BS Icons
    cor = models.CharField(max_length=7, default='#252020')
    time = models.CharField(max_length=50, choices=...)  # executivo/marketing/sucesso/parcerias/tech
    prompt = models.TextField()
    prompt_autonomo = models.TextField(blank=True)
    modelo = models.CharField(max_length=50, default='gpt-4o-mini')
    ativo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)
    # criado_em, atualizado_em

class ToolAgente(models.Model):
    slug = models.SlugField(unique=True)
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    icone = models.CharField(max_length=50, default='bi-tools')
    tipo = models.CharField(max_length=20, choices=[('executavel','Executável'),('conhecimento','Conhecimento')])
    prompt = models.TextField(blank=True)
    exemplo = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    ordem = models.IntegerField(default=0)

class LogTool(models.Model):
    tool = models.ForeignKey(ToolAgente, null=True, on_delete=models.SET_NULL)
    agente = models.ForeignKey(Agente, null=True, on_delete=models.SET_NULL)
    tool_slug = models.CharField(max_length=100)
    resultado = models.TextField(blank=True)
    sucesso = models.BooleanField(default=True)
    tempo_ms = models.IntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

class MensagemChat(models.Model):
    agente = models.ForeignKey(Agente, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=[('user','User'),('assistant','Assistant')])
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

class Reuniao(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    agentes = models.TextField(blank=True)  # CSV de IDs (manter exato como megaroleta)
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

class MensagemReuniao(models.Model):
    reuniao = models.ForeignKey(Reuniao, related_name='mensagens', on_delete=models.CASCADE)
    tipo = models.CharField(max_length=20, choices=[('ceo','CEO'),('agente','Agente'),('moderador','Moderador')])
    agente_id = models.IntegerField(null=True)  # solto, pode ser SET_NULL FK depois
    agente_nome = models.CharField(max_length=200, blank=True)
    conteudo = models.TextField()
    criado_em = models.DateTimeField(auto_now_add=True)

class Automacao(models.Model):
    modo = models.CharField(max_length=20, choices=[('tool','Tool'),('agente','Agente')])
    tool = models.ForeignKey(ToolAgente, null=True, on_delete=models.SET_NULL)
    agente = models.ForeignKey(Agente, null=True, related_name='automacoes', on_delete=models.SET_NULL)
    encaminhar_para = models.ForeignKey(Agente, null=True, related_name='automacoes_recebidas', on_delete=models.SET_NULL)
    intervalo_horas = models.IntegerField(default=24)
    status = models.CharField(max_length=20, default='pausado')
    ultima_execucao = models.DateTimeField(null=True)
    ultimo_resultado = models.TextField(blank=True)
    ultima_analise = models.TextField(blank=True)
    total_execucoes = models.IntegerField(default=0)
    total_erros = models.IntegerField(default=0)
    ativo = models.BooleanField(default=False)  # Default FALSE — não roda na fase 1

class Alerta(models.Model):
    tipo = models.CharField(max_length=50)
    severidade = models.CharField(max_length=20, choices=[('info','Info'),('aviso','Aviso'),('critico','Crítico')])
    titulo = models.CharField(max_length=300)
    descricao = models.TextField(blank=True)
    dados_json = models.JSONField(default=dict)
    agente = models.ForeignKey(Agente, null=True, on_delete=models.SET_NULL)
    tool = models.ForeignKey(ToolAgente, null=True, on_delete=models.SET_NULL)
    lido = models.BooleanField(default=False)
    resolvido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

class Proposta(models.Model):
    agente = models.ForeignKey(Agente, on_delete=models.CASCADE)
    tool = models.ForeignKey(ToolAgente, null=True, on_delete=models.SET_NULL)
    alerta = models.ForeignKey(Alerta, null=True, on_delete=models.SET_NULL)
    reuniao = models.ForeignKey(Reuniao, null=True, on_delete=models.SET_NULL)
    titulo = models.CharField(max_length=300)
    descricao = models.TextField()
    prioridade = models.CharField(max_length=20)
    status = models.CharField(max_length=20, default='pendente')
    dados_execucao = models.JSONField(default=dict)
    motivo_rejeicao = models.TextField(blank=True)
    resultado_execucao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    data_decisao = models.DateTimeField(null=True)
    data_execucao = models.DateTimeField(null=True)

class FAQCategoria(models.Model):
    nome = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    icone = models.CharField(max_length=50, default='bi-question-circle')
    cor = models.CharField(max_length=7, default='#252020')
    ordem = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)

class FAQItem(models.Model):
    categoria = models.ForeignKey(FAQCategoria, related_name='itens', on_delete=models.CASCADE)
    pergunta = models.TextField()
    resposta = models.TextField()
    ordem = models.IntegerField(default=0)
    ativo = models.BooleanField(default=True)
    gerado_por_ia = models.BooleanField(default=False)
    hash_dados_fonte = models.CharField(max_length=64, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
```

### Estrutura mínima do app

```
apps/comando/
├── __init__.py
├── apps.py
├── admin.py                    # Registra os 11 models no admin (read-only por enquanto)
├── models.py                   # 11 models acima
├── migrations/
│   └── 0001_initial.py
└── management/commands/
    └── importar_megaroleta_gestao.py  # Importa dados do megaroleta
```

**Não terá:** views.py, urls.py, templates/, static/, forms.py, signals.py, services/.

### Management command de importação

`apps/comando/management/commands/importar_megaroleta_gestao.py`

**Como vai funcionar:**

1. Conecta no banco do megaroleta (Postgres direto via psycopg2 ou via Django multi-DB) — config separada
2. Lê cada tabela do gestão na ordem correta de dependências:
   - Sem dependência: Agente, ToolAgente, FAQCategoria, Reuniao
   - Com dependência: LogTool → MensagemChat → MensagemReuniao → Automacao → Alerta → Proposta → FAQItem
3. Pra cada registro: cria equivalente no robo, mantendo IDs originais (pra preservar FKs)
4. Reporta totais e erros

**Estratégia de execução:**
- Roda 1x: `python manage.py importar_megaroleta_gestao --dry-run` → mostra quantidade que vai migrar
- Roda real: `python manage.py importar_megaroleta_gestao` → executa
- Reproduzível: se rodar 2x, segunda vez não duplica (verifica por ID antes de inserir)

**Caminho do banco megaroleta:** ler de variável de ambiente ou parâmetro do comando, **nunca hardcoded**.

### Workspace → Comando: links via FK

```python
# apps/workspace/models.py:
class Tarefa(TenantMixin, models.Model):
    ...
    criado_por_agente = models.ForeignKey('comando.Agente', null=True, ...)
    documento_processo = models.ForeignKey('workspace.Documento', null=True, ...)

class Documento(TenantMixin, models.Model):
    ...
    agente_origem = models.ForeignKey('comando.Agente', null=True, ...)
```

Isso funciona porque comando entra na primeira migration junto com workspace.

---

## Plano de deletar o megaroleta

Após fase 1 inteira validada, criar PR final que:

1. Confirma com `python manage.py importar_megaroleta_gestao --check` que dados estão consistentes
2. Apaga o diretório `megaroleta/` do disco
3. Atualiza `CLAUDE.md`:
   - Remove menção ao megaroleta
   - Atualiza seção "Escopo de Edição" (vendas_web tava morto, megaroleta sai junto)
4. Atualiza `robo/docs/PRODUTO/` se houver referência
5. Atualiza memória `project_modulo_gestao_nao_migrado.md` → arquivar como "obsoleta — migração concluída em DD/MM/2026"
6. Atualiza `.gitignore` se tiver entrada específica do megaroleta
7. Verifica que nada no robo importa de `megaroleta/` (busca `from megaroleta` no codebase)

**Importante:** o user pode auditar/limpar dados em `apps/comando/` antes desse PR — não bloquear esperando, mas permitir caso ele queira.

---

## Resultado esperado

Quando concluído:

- ✅ Tenant Hubtrix consegue criar projetos, dividir em etapas, atribuir tarefas, mover no kanban, escrever notas, criar documentos em markdown organizados em pastas
- ✅ Tudo isolado por tenant (validar com 2 tenants distintos)
- ✅ Permissões granulares funcionando em 4 perfis diferentes
- ✅ Auditoria registra cada operação em LogSistema
- ✅ Visual alinhado com DS Hubtrix v2 (paleta tinta + sienna + branco)
- ✅ Doc em `robo/docs/PRODUTO/modulos/workspace/` atualizada
- ✅ Hub regenerado

---

## Contexto e referências

- Inventário do gestão: feito em chat 28-29/04/2026
- Mapeamento de sobreposição: feito 29/04/2026
- Memória `project_modulo_gestao_nao_migrado.md`: **atualizar** após esta entrega
- Plano antigo de migração ao DS: `C:\Users\lucas\.claude\plans\jazzy-giggling-wolf.md` (referência histórica)
