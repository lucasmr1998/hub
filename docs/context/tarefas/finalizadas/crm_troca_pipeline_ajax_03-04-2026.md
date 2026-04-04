---
name: "CRM: Troca de pipeline via AJAX sem reload"
description: "Trocar pipeline sem recarregar página, usando fetch para atualizar apenas o kanban"
prioridade: "🔴 Alta"
responsavel: "Dev"
---

# CRM: Troca de pipeline via AJAX — 03/04/2026

**Data:** 03/04/2026
**Responsável:** Dev
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

Ao trocar de pipeline no dropdown, o sistema recarrega a página inteira com `?pipeline=ID`. Deveria trocar via AJAX, atualizando apenas o kanban. A URL deve ficar limpa ou usar slug amigável.

---

## Tarefas

- [ ] Trocar links `<a href="?pipeline=ID">` por onclick JS
- [ ] Ao clicar, chamar `carregarPipeline(pipelineId)` via fetch
- [ ] Recriar as colunas do kanban dinamicamente com os novos estágios
- [ ] Atualizar título do dropdown com o nome do pipeline selecionado
- [ ] Não recarregar a página

---

## Resultado esperado

Troca de pipeline é instantânea, sem reload. URL permanece `/crm/`.
