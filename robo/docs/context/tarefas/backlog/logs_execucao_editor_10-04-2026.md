---
name: "Logs de execucao no editor"
description: "Visualizar por onde o fluxo passou em cada atendimento, direto no editor"
prioridade: "🟡 Media"
responsavel: "Tech Lead"
---

# Logs de Execucao no Editor — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🟡 Media
**Status:** ⏳ Aguardando

---

## Descricao

No editor de fluxos, poder selecionar um atendimento e ver visualmente por quais nos passou: nos executados em verde, no atual pulsando, nos pendentes em cinza. Como o N8N mostra durante execucao.

---

## Tarefas

- [ ] Botao "Ver Execucoes" no editor
- [ ] Sidebar com lista de atendimentos recentes
- [ ] Ao selecionar, aplicar CSS nos nos baseado nos logs
- [ ] Mostrar dados de cada no ao clicar (input/output/tempo)

---

## Contexto e referencias

- Plano original: P10 (Execucao Visual) e P11 (Historico por No)
- Logs: `LogFluxoAtendimento` ja registra execucao de cada nodo
- Editor: `apps/comercial/atendimento/templates/.../editor_fluxo.html`

---

## Resultado esperado

Gestor consegue debugar visualmente o caminho que cada atendimento percorreu no fluxo.
