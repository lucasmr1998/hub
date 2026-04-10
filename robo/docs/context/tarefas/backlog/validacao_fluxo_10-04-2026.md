---
name: "Validacao de fluxo antes de ativar"
description: "Verificar se fluxo esta completo e correto antes de permitir ativacao"
prioridade: "🟡 Media"
responsavel: "Tech Lead"
---

# Validacao de Fluxo antes de Ativar — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🟡 Media
**Status:** ⏳ Aguardando

---

## Descricao

Hoje e possivel ativar um fluxo incompleto (sem entrada, sem finalizacao, nos desconectados). Implementar validacao automatica que verifica integridade antes de permitir ativacao.

---

## Tarefas

- [ ] Funcao `validar_fluxo(fluxo)` que verifica: tem entrada, todos nos conectados, tem finalizacao, IAs configuradas
- [ ] Chamar na API de salvar quando status muda para "ativo"
- [ ] Mostrar erros de validacao no editor (badge nos nos com problema)
- [ ] Bloquear ativacao se houver erros criticos

---

## Resultado esperado

Fluxos incompletos nao podem ser ativados. Erros mostrados visualmente no editor.
