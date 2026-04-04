---
name: "Segmentos: Mover redirect para Marketing"
description: "Ao criar/salvar segmento, redirecionar para Marketing em vez do CRM"
prioridade: "🟡 Média"
responsavel: "Dev"
---

# Segmentos: Redirect para Marketing — 03/04/2026

**Data:** 03/04/2026
**Responsável:** Dev
**Prioridade:** 🟡 Média
**Status:** 🔧 Em andamento

---

## Descrição

A view de segmentos (`api_segmento_salvar`) redireciona para o CRM após salvar. Como segmentos agora pertence ao Marketing, o redirect deve ir para a lista de segmentos no Marketing.

---

## Tarefas

- [ ] Verificar redirect na view api_segmento_salvar
- [ ] Corrigir para redirecionar para segmentos_lista
- [ ] Garantir que a sidebar de Marketing aparece nas páginas de segmentos

---

## Resultado esperado

Ao criar/editar segmento, o usuário permanece no contexto de Marketing.
