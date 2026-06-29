# Execution log — Workspace

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
