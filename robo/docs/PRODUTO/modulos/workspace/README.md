---
modulo: Workspace
status: 🟢 Operacional
fase_atual: 1 — Fundação (projetos + tarefas + documentos) + Drive multi-formato
ultima_atualizacao: 30/05/2026
ativacao: por tenant via aurora-admin
---

# Workspace — projetos, tarefas e documentos

Espaço de trabalho colaborativo dentro do Hubtrix. Cada tenant que tiver o módulo ligado pode criar **projetos** com **etapas** e **tarefas**, escrever **notas**, e organizar **documentos** em **pastas** (Drive) com markdown sanitizado, HTML, imagens, PDFs, links e anexos (inclusive imagens geradas por IA).

## Onde fica

- **App Django:** `apps/workspace/`
- **URL raiz:** `/workspace/`
- **Modelo:** multi-tenant (todos os models herdam `TenantMixin`)
- **Ativação:** `Tenant.modulo_workspace` (toggle no aurora-admin)

## O que existe

### 7 models

| Model | Propósito |
|-------|-----------|
| `Projeto` | Iniciativa estratégica com objetivo, critérios, riscos, datas, orçamento |
| `Etapa` | Fase dentro de um projeto (ordem, datas) |
| `Tarefa` | Unidade de trabalho com status/prioridade/responsável; campos preparados pra IA |
| `Nota` | Comentário em tarefa, com autor |
| `Documento` | Conteúdo multi-formato (markdown/html/imagem/pdf/link), categorizado, em pastas opcionais. Campos: `formato`, `conteudo`, `arquivo` (FileField), `url_externa` |
| `PastaDocumento` | Hierarquia de pastas (FK self pra subpastas), com cor e ícone Bootstrap Icons |
| `AnexoDocumento` | Arquivo anexado a um documento (imagem/arquivo): `arquivo`, `tipo`, `mime_type`, `tamanho_bytes` + metadados de IA (`gerado_por_ia`, `prompt_ia`, `modelo_ia`) |

### Formatos de documento

`Documento.formato` define como o detalhe renderiza:

| Formato | Render | Onde fica o conteúdo |
|---------|--------|----------------------|
| `markdown` | Markdown sanitizado (tipografia editorial) | `conteudo` (TEXT no banco) |
| `html` | HTML sanitizado (sem passar por markdown) | `conteudo` |
| `imagem` | Hero de imagem | `arquivo` ou primeiro anexo de imagem |
| `pdf` | Iframe embed + botão de download | `arquivo` (media volume) |
| `link` | CTA pra link externo (ou download do `arquivo`) | `url_externa` / `arquivo` |

### Telas

| URL | O que faz |
|-----|-----------|
| `/workspace/` | Home — KPIs + projetos ativos + tarefas urgentes + docs recentes |
| `/workspace/projetos/` | Lista com filtros (status/busca/arquivados) |
| `/workspace/projetos/<id>/` | Detalhe — overview, etapas, tarefas recentes, sidebar com objetivo/critérios/riscos |
| `/workspace/projetos/<id>/kanban/` | Kanban com 4 colunas (pendente/andamento/concluida/bloqueada), **drag-and-drop nativo** |
| `/workspace/projetos/<id>/editar/` | Form em 3 seções + bloco IA recolhível |
| `/workspace/tarefas/` | Visão "minhas tarefas" cross-projeto, agrupada por prazo (atrasadas/hoje/próximas/futuras/sem prazo) |
| `/workspace/tarefas/<id>/` | Detalhe — descrição + briefing executivo + sidebar + thread de notas |
| `/workspace/documentos/` | **Drive** — vista unificada: subpastas + documentos da raiz, com busca cross-pasta e filtro por categoria |
| `/workspace/documentos/pasta/<slug>/` | Drive dentro de uma pasta (breadcrumb hierárquico) |
| `/workspace/documentos/<id>/` | Render por formato (markdown/html/imagem/pdf/link) + anexos |

### APIs AJAX

| Endpoint | Verbo | Uso |
|----------|-------|-----|
| `/workspace/api/kanban/mover/` | POST JSON | Move tarefa entre colunas (`tarefa_id`, `novo_status`, `ordem`) |
| `/workspace/api/tarefa/<id>/status/` | POST | Quick action de mudar status (auto-marca `data_conclusao`) |
| `/workspace/documentos/<id>/anexos/upload/` | POST | Upload de imagem/arquivo pra um documento (retorna URL + snippet markdown) |
| `/workspace/documentos/<id>/anexos/gerar-ia/` | POST | Gera imagem por IA (Gemini) e anexa ao documento |
| `/workspace/anexos/<id>/excluir/` | POST | Remove anexo (arquivo + registro) |

> Geração de imagem por IA: `apps/workspace/services/imagem_ia_service.py` usa Google Gemini (`gemini-3-pro-image-preview` com fallback `gemini-2.5-flash-image`), chave em `GOOGLE_AI_API_KEY`.

## Permissões

Granulares via `Funcionalidade` (modulo='workspace'):

| Código | Descrição |
|--------|-----------|
| `workspace.ver` | Acessar qualquer tela do Workspace |
| `workspace.criar_projeto` | Criar projeto |
| `workspace.editar_proprios` | Editar projetos/tarefas/docs próprios |
| `workspace.editar_todos` | Editar de qualquer um (também é exigida pra excluir projeto/pasta) |

**Defaults nos perfis (seed `seed_workspace_funcionalidades`):**

| Perfil | ver | criar | editar_proprios | editar_todos |
|--------|-----|-------|-----------------|--------------|
| Admin | ✓ | ✓ | ✓ | ✓ |
| Supervisor Comercial | ✓ | ✓ | ✓ | ✗ |
| Supervisor Marketing | ✓ | ✓ | ✓ | ✗ |
| Supervisor CS | ✓ | ✓ | ✓ | ✗ |
| Supervisor Suporte | ✓ | ✗ | ✓ | ✗ |
| Vendedor / Atendente | ✗ | ✗ | ✗ | ✗ |

## Markdown e sanitização

`apps/workspace/markdown_utils.py` — wrapper sobre `markdown` + `bleach`:
- `render_markdown(texto)` — converte markdown em HTML sanitizado
- `sanitizar_input(texto)` — sanitização defensiva antes de salvar
- Whitelist: tags básicas (h1-h6, p, listas, tabelas, código, blockquote, links, imagens), atributos `class/id/href/src/alt`, protocolos `http/https/mailto`

## Auditoria

Todas as ações destrutivas + de mudança chamam `registrar_acao('workspace', acao, entidade, ...)`. Categorias usadas: `criar`, `editar`, `excluir`, `mover_kanban`, `mudar_status`. Visível em `/configuracoes/logs-auditoria/`.

## Comandos de management

| Comando | O que faz |
|---------|-----------|
| `seed_workspace_funcionalidades` | Cadastra as 4 funcionalidades + aplica defaults nos perfis padrão de TODOS os tenants. Idempotente. |
| `importar_docs_drive` | Importa `robo/docs/` como Drive da empresa (ver abaixo). Idempotente. |
| `criar_tarefas_de_backlog` | Transforma docs da pasta "10. Tarefas/Backlog" em `Tarefa` no projeto Hubtrix Desenvolvimento. |
| `importar_emails_paper` | Importa e-mails (JSX→HTML) + PNGs como documentos `formato=html` + anexos. |

### `importar_docs_drive` — Drive da empresa + sync

Importa os arquivos de `robo/docs/` pro Workspace (tenant Aurora HQ por padrão), organizados **por time** em 11 pastas raiz (não espelha o filesystem). Idempotente via `(tenant, slug)`.

- **Formatos:** `.md` (conteúdo no banco), `.pdf` (`formato=pdf`, arquivo no media volume), `.pptx` (`formato=link`, download), `.json`/`.sql` (`formato=markdown`, conteúdo como bloco de código).
- **Flags:** `--tenant`, `--clear`, `--dry-run`, `--root`, `--apenas-md`, `--apenas-binarios`, `--base-url`, `--no-manifest`.
- **Idempotência de binários:** o arquivo só é (re)gravado se ausente ou se o tamanho mudar (evita duplicar no media).

```bash
python manage.py importar_docs_drive --dry-run        # revisar roteamento (0 IGNORADO esperado)
python manage.py importar_docs_drive                  # md + binarios
python manage.py importar_docs_drive --apenas-md      # so markdown (dispensa media volume)
```

### Manifesto de sync (nuvem ↔ local)

Ao final, o command gera em `robo/docs/`:
- `_SYNC_NUVEM.md` — tabela legível: cada arquivo local, status (`sincronizado`/`local-apenas`) e link na nuvem.
- `.sync_nuvem.json` — versão para máquina; o `hub.html` lê e mostra um badge nuvem/local por documento.

> A pasta `robo/docs/` continua sendo a fonte versionada; a nuvem (Workspace) é a cópia viva colaborativa. Link de produção: `https://app.hubtrix.com.br/workspace/documentos/<id>/`.

## Multi-tenancy + módulo ativável

Workspace segue o padrão dos outros módulos (Comercial/Marketing/CS):

1. **Aurora-admin liga via toggle** em `/aurora-admin/tenant/<id>/`:
   - Checkbox "Workspace ativo" → `tenant.modulo_workspace`
   - Select de plano (Starter/Start/Pro) → `tenant.plano_workspace`

2. **Sidebar condicional** em `templates/partials/sidebar.html`:
   ```django
   {% if modulo_workspace and (is_superuser or perm.acesso_workspace) %}
     <a href="/workspace/">...</a>
   {% endif %}
   ```

3. **Middleware bloqueia acesso direto** (`apps/sistema/middleware.py`):
   - Se usuário sem `acesso_workspace` tentar `/workspace/...` → 403

4. **Defesa em camadas:**
   - View entry: `if not user_tem_funcionalidade(request, 'workspace.ver'): return 403`
   - Edição: `_pode_editar()` checa `editar_todos` OU `editar_proprios + ownership`

### Regras de edição (detalhe)

- **Projeto:** dono = `projeto.responsavel` **OU** responsável de qualquer tarefa do projeto. Com `editar_proprios` o dono edita; `editar_todos` edita qualquer um.
- **Pasta (`PastaDocumento`):** não tem dono (sem `criado_por`), então criar/editar/excluir pasta exige `workspace.editar_todos`.
- **"Minhas tarefas" `?escopo=todas`:** expõe tarefas de todos os usuários do tenant, então exige `editar_todos` (ou superuser). Sem permissão, degrada pra `escopo=minhas` com aviso.

## Campos preparados pra IA (dormentes na fase 1)

Models já têm campos que serão usados na fase 3 quando ressuscitarmos a camada de agentes do `apps/comando/`:

- `Projeto.contexto_agentes` — briefing pra agentes lerem
- `Tarefa.objetivo`, `contexto`, `passos`, `entregavel`, `criterios_aceite`, `log_execucao` — briefing executivo
- `Tarefa.nivel_delegacao` — 0=humano, 1-2=agente IA
- `Tarefa.criado_por_agente` (FK `comando.Agente`) — agente que criou
- `Tarefa.documento_processo` (FK `Documento`) — SOP da tarefa
- `Documento.visivel_agentes` — bool
- `Documento.agente_origem` (FK `comando.Agente`) — agente autor

## O que NÃO está incluído (fica fase 2/3)

- Dashboard CEO completo cruzando dados de outros apps (Leads, Vendas, Churn) — fase 2
- Camada de agentes IA — fase 3 (já vem em schema dormente em `apps/comando/`)
- Reuniões multi-agente — fase 3
- Automações + Alertas + Propostas — fase 3
- FAQ gerada por IA — fase 3

## Histórico de migrações

| Migração | O que faz |
|----------|-----------|
| `workspace.0001_initial` | Cria 6 models + indexes + unique_together |
| `workspace.0002_anexodocumento` | Adiciona o model `AnexoDocumento` |
| `workspace.0003_documento_formato_documento_url_externa_and_more` | Adiciona `formato`, `arquivo`, `url_externa`, `descricao` em `Documento` |
| `sistema.0010_tenant_modulo_workspace_*` | Adiciona `modulo_workspace`, `plano_workspace`, `plano_workspace_ref` em Tenant + atualiza enums |

## Notas técnicas

- **Bleach 6.1.0** adicionado ao `requirements.txt`
- **Slug único por tenant** (`unique_together = [['tenant', 'slug']]`) — não usar `unique=True` solo
- **Upload path** dos documentos: `workspace/docs/<tenant_id>/<slug>/<filename>` (isolamento entre tenants); anexos em `workspace/anexos/<tenant_id>/<doc_slug>/<filename>`
- **Storage de arquivos** (pdf/pptx/anexos): `FileSystemStorage` no media volume (`/app/media` em prod). Markdown vai pro banco (campo TEXT) e não depende do filesystem.
- **Bootstrap Icons** substitui FontAwesome do gestão legado
- **Cor default** das pastas: paleta v2 (`#252020` tinta)

## Testes

`tests/test_views_workspace.py` (15 testes): permissões (`_pode_editar` de projeto/tarefa/doc), os 3 fixes de permissão (projeto por tarefa, `pasta_editar`, `?escopo=todas`), isolamento de tenant, CRUD e API do kanban. Factories em `tests/factories.py`.

```bash
pytest tests/test_views_workspace.py -v
```
