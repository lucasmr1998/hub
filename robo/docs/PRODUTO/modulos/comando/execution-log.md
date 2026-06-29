# Execution log — Comando (camada de agentes IA herdada do gestao)

---

## 2026-06-29 — Fase 0 (analise) + orfanamento

- **Fase 0 (analise):** como expressar a "empresa de agentes" do gestao (megaroleta) na engine nova.
  Output: `docs/PRODUTO/modulos/comando/analise-agentes-vs-engine-nova.md`. Decisao: NAO ressuscitar
  o motor velho de IA (regex em texto + `ai_service`/`agent_actions`); expressar **sobre o
  `apps/automacao`** (function-calling real). Roster vem de `docs/AGENTES/` (NAO importar 1:1 do
  megaroleta, que e contexto Megalink/roleta). Status: completed.
- **Orfanamento (workspace Fase 3, commit `a4ab444`):** as FKs `workspace.Tarefa.criado_por_agente` e
  `workspace.Documento.agente_origem` que apontavam pro `comando.Agente` foram re-apontadas pro
  `automacao.Agente` (fonte unica). `comando` ficou **orfao e vazio** (0 rows nas 11 tabelas; nunca
  foi populado). Status: completed.
- **Pendente:** aposentar o app (husk + DeleteModel, mesma tecnica do marketing). Como esta vazio e
  sem referencias, o drop e limpo, mas em prod e gated por deploy. Status: pending.
