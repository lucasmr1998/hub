---
name: "Automações: Refatoração completa com fluxograma visual"
description: "Implementar fluxos condicionais, editor drag & drop, delays reais, segmentos, timeline, controles"
prioridade: "🔴 Alta"
responsavel: "Dev"
---

# Automações: Refatoração Completa — 03/04/2026

**Data:** 03/04/2026
**Responsável:** Dev
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

Refatorar o módulo de Automações para suportar fluxos condicionais visuais (drag & drop), delays reais, integração com segmentos, timeline por lead e controles robustos.

---

## Tarefas

- [ ] Phase 1: Models (NodoFluxo, ConexaoNodo, ExecucaoPendente, ControleExecucao) + migrations
- [ ] Phase 2: Engine dual-mode (legacy + grafo) + controles
- [ ] Phase 3: Management command cron (pendentes, lead_sem_contato, tarefa_vencida, segmentos)
- [ ] Phase 4: Frontend editor visual (Drawflow)
- [ ] Phase 5: Dashboard central + Timeline no lead
- [ ] Phase 6: Integração com Segmentos
- [ ] Phase 7: Testes completos

---

## Contexto e referências

Plano detalhado em: `.claude/plans/typed-nibbling-stallman.md`

---

## Resultado esperado

Cliente cria automações visuais com fluxos condicionais, delays e ações encadeadas. Logs claros por lead e por regra. Controles de execução robustos.
