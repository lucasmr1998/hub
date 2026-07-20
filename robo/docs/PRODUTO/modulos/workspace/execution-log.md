# Execution log — Workspace

---

## 2026-06-29 — Paginas Ferramentas + Fluxos + fix ticket_detalhe

- **Ferramentas** (`/workspace/ferramentas/`, `01af391`): catalogo UI das tools (le o registry da
  engine) por categoria + tipo (consulta/acao) + uso por agente. A versao tela do `TOOLS.md`.
- **Fluxos** (`/workspace/fluxos/`, `01af391`): lista os flows da engine `automacao` (nome/gatilho/
  nos/status/atualizado) + link pro editor. A engine so tinha editor + `api/fluxos`, sem pagina de lista.
- Ambas na sidebar Inteligencia: Dashboard CEO | Agentes | Ferramentas | Fluxos | Propostas.
- **fix** (`783728e`): `suporte/ticket_detalhe` quebrava (500) quando solicitante/atendente/autor/
  usuario era nulo — `{{ obj.get_full_name|default:obj.username }}` resolvia `username` num None
  (o arg do filtro `default` propaga `VariableDoesNotExist`). Guardado com `{% if obj %}` nos 5
  acessos. Validado: ticket 15 volta a 200.
- Status: completed.

---

## 2026-06-29 — Empresa de agentes: Peca 1 (campos + organizacao por time + editor)

Continuacao da camada de agentes (traz do gestao a organizacao por time + o editor pro
workspace, casa unica). Consolidado na **main** via merge da `feat/agentes-workspace`
(`428fd4c`, 3 conflitos de CRM/sidebar resolvidos), sem push. Tarefa Workspace #142.

- **Schema** (`6c0b3c8`): 6 campos no `automacao.Agente` (`equipe`, `cor`, `icone`,
  `prompt_autonomo`, `descricao`, `ordem`) + migration `0009`. `ordering = equipe/ordem/nome`.
- **Seed** (`24d371a`): `seed_agentes_workspace` deriva `equipe` da subpasta do `AGENTES/` +
  cor/icone por time. 23 agentes ganharam time (executivo 5, marketing 5, tech 5, comercial 3,
  produto 3, operacoes 2); monitor + 7 bots ficam "sem time" (editor permite ajustar).
- **Roster por time** (`cffa5e9`): `/workspace/agentes/` agrupa por departamento (cor + icone),
  estilo gestao. Validado no browser (31 agentes, chat com dado real via `status_pipeline`).
- **Editor** (`6b69558`): CRUD completo no workspace (`/workspace/agentes/novo`,
  `/<pk>/editar/`) reusando o model + `tools_disponiveis`, sob `workspace.editar_todos`. Form
  com todos os campos + chat de teste. Roster ganhou "Novo agente" + lapis. Validado (form
  popula, save 200).
- **Redirect** (`90ebe43`): `/automacao/agentes/` -> workspace, preservando o pk no editar.
  Porta unica. Validado.
- **Orfaos (follow-up):** `automacao.agente_salvar/excluir/simular_api/resumo_api` + templates
  `automacao/agentes.html`/`agente_editar.html` ficaram sem uso pela UI. Cleanup futuro (nao
  removidos agora pra nao arriscar refs).
- **Achado nao relacionado:** drift pre-existente em `notificacoes` (modelo vs migration),
  fora de escopo, nao mexido.
- Status: completed (Peca 1). Proximo: Peca 2 (tools de acao + FAQ como tool), Peca 3 (dashboard
  CEO), Peca 4 (rotinas autonomas + secao 4 + alertas).

---

## 2026-06-29 — Empresa de agentes: Peca 2 (sistema de tools + tools de acao)

Os agentes passam a AGIR no workspace, com um sistema de tools de primeira classe. Main, sem push.

- **Sistema de tools** (`930ce7d`): `@_tool` ganha `tipo` (conhecimento/executavel) + `categoria`;
  tools classificadas. Comando `gerar_catalogo_tools` gera `TOOLS.md` do registry (fonte da verdade =
  codigo, doc derivado). Editor agrupa por categoria + badge de tipo. Skill `criar-tool` (passo 0 =
  procurar no catalogo, anti-duplicacao).
- **Naming** (`9fbf051`): `criar_tarefa` -> `criar_tarefa_workspace` pra nao confundir com a
  `TarefaCRM` (que tem um NO `criar_tarefa`, registry separado). Regra "nao misturar Workspace e CRM".
- **CRUD de workspace** (`930ce7d`, `4e9b6e1`): criar/atualizar/consultar projeto, tarefa, etapa,
  documento (tenant-safe, agente como origem). Habilitadas no seed.
- **explorar_codigo** (`d132fac`): leitura read-only do projeto, **so pro time tech**. Travas: raiz em
  `robo/` (exclui `.env`), bloqueia escape/`.env`/secrets, allowlist de extensao, redige credenciais.
  Validado (escape bloqueado, token nao vaza).
- **gerar_imagem** (`264545f`): Gemini -> anexa em doc novo/existente, **so pro time marketing**.
  Falha graciosa sem a key + cleanup do doc.
- **faq_ia: descartada** (redundante — o agente ja faz com `consultar_base_conhecimento` +
  `salvar_documento`).
- 23 tools no catalogo. Per-time via `TOOLS_EXTRA_POR_EQUIPE` (tech/marketing). Status: completed
  (Peca 2). Proximo: Peca 3 (Dashboard CEO).

---

## 2026-06-29 — Empresa de agentes: Peca 3 (Dashboard CEO, cockpit + IA)

Cockpit executivo em `/workspace/ceo/` (`cb51618`), tenant-safe, cruzando os 3 mundos:
- **KPIs**: pipeline, leads (+novos 30d), vendas 30d, churn, tickets, propostas pendentes.
- **Briefing IA** (a peca "com IA"): botao chama o agente CEO via `chat_api`; ele usa as tools de
  dados (puxou 5 no teste) e devolve a leitura executiva + recomendacao; tem follow-up por chat.
- Negocio (pipeline por estagio com barras), Workspace (tarefas por status / projetos / propostas),
  agentes por time. Link na sidebar Inteligencia. Tarefa Workspace #146.
- Validado no browser (Playwright): 6 KPIs com dado real, briefing chamou status_pipeline +
  resumo_leads + vendas_periodo + churn_clientes + tickets_abertos.
- Status: completed (Peca 3). Proximo: Peca 4 (rotinas autonomas + secao 4 + alertas).

---

## 2026-06-29 — Camada de agentes IA (Fase 1 + 2a + 3)

Branch `feat/agentes-workspace` (NAO pushada, prod intacto). Dar vida a camada de agentes do
gestao (megaroleta) expressa **sobre a engine `apps/automacao`** (casa=workspace, motor reusado,
fonte unica do agente = `automacao.Agente`, multi-tenant-ready). Plano em `.claude/plans/`.

- **Fase 1** (`6cc24e5`): 5 tools de dados read-only tenant-scoped em `automacao/services/ia_tools.py`
  (`status_pipeline`, `resumo_leads`, `vendas_periodo`, `churn_clientes`, `tickets_abertos`; reusam
  os models do registry `apps/relatorios`). `seed_agentes_workspace` (le `docs/AGENTES/*.md`, cria 24
  personas no aurora-hq). `views/agentes.py` + template + chat em `/workspace/agentes/`. Status: completed.
- **Fix migration** (`58a9191`): dependencia faltante no `automacoes/0007` (build fresh quebrava com
  "Related model automacoes.regraautomacao cannot be resolved"). Status: completed.
- **Fase 2a** (`f0258b7`): model `Proposta` (TenantMixin, migration `0004`) + tool `solicitar_aprovacao`
  (agente propoe em vez de agir) + fila `/workspace/propostas/` (aprovar/rejeitar, gate
  `workspace.editar_todos`) + `tests/test_workspace_propostas.py` (7 testes). Status: completed.
- **Fase 3** (`a4ab444`): FKs `Tarefa.criado_por_agente` e `Documento.agente_origem` re-apontadas de
  `comando.Agente` -> `automacao.Agente` (migration `0005`, 0 dados nas FKs). Status: completed.
- **Validacao:** 45 pytest verdes (build fresh com pgvector) + E2E no browser via Playwright **10/10**
  (login, roster com 31 agentes, CEO chamando `status_pipeline` com dado real "25 oportunidades",
  `solicitar_aprovacao` criando proposta, aprovacao na fila). Status: completed.
- **Deferido (frontier):** Fase 2b (cron autonomo, falta decisao de design "agente responsavel" na
  `Tarefa` + guards anti-loop); execucao diferida da Proposta (v1 e advisory); aposentar `comando`.
  Status: pending.
- **Ambiente:** dev migrado pro Docker `pgvector/pgvector:pg17` (5433), pois o PG 18 nativo nao tem
  pgvector. Ver `context/reunioes/agentes_workspace_fase1_29-06-2026.md` e a memoria de referencia.

## 2026-07-20 — Tela de acompanhamento das respostas do checklist

- **Acao:** nova tela `/workspace/checklists/<pk>/respostas/` (view
  `checklists.respostas_page`, rota `workspace:checklist_respostas`), com link
  a partir da listagem de checklists e do editor.
- **Motivacao:** o bot de venda por WhatsApp (tarefa 204) ja gravava resposta
  de checklist em producao, mas nao havia nenhuma forma de ver isso pela
  interface. Dado coletado que ninguem consegue ler nao serve pra decisao.
- **O que mostra:** uma linha por entidade que comecou a responder, com
  identificacao (nome e telefone quando e lead), progresso (respondidos sobre
  total, com barra), item onde parou e data da ultima resposta. Ordenado pela
  ultima resposta, 25 por pagina, com link pro detalhe do lead.
- **Decisao de produto:** a leitura por checklist responde "como o bot esta
  indo" (onde o roteiro perde gente), diferente da leitura por lead, que
  responde "o que ja sei desse cliente" e vive no detalhe do lead (ver
  execution-log do modulo comercial). As duas foram entregues juntas.
- **Desempenho:** listar N entidades chamando `progresso()` por entidade daria
  N+1. O servico `apps/automacao/services/checklist.py` foi partido em duas
  camadas: funcoes `*_de` (`itens_elegiveis_de`, `progresso_de`,
  `proximo_item_de`) recebem itens e respostas ja carregados e concentram a
  regra; as funcoes antigas viraram wrappers que so buscam e delegam. Assim a
  tela carrega tudo em bulk (`respostas_por_entidade`) sem duplicar a regra de
  progresso. Assinaturas publicas antigas inalteradas.
- **Design system:** componente novo `templates/components/progress_bar.html`
  criado ANTES do uso e adicionado ao showcase. O bloco de barra que ja existia
  (`breakdown_row`) carrega label e stats, que nao cabem em celula de tabela.
- **Testes:** 16 novos em `tests/test_workspace_checklist_respostas.py`
  (isolamento entre tenants, progresso batendo com o servico, ordem dos itens,
  lead apagado nao quebrando a tela). Suite de checklist: 84 verdes.
- **Status:** completed
