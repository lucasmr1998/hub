---
name: "Segmentos: Signal para atualizar membros automaticamente"
description: "Quando lead é criado/atualizado, verificar segmentos dinâmicos e adicionar/remover"
prioridade: "🔴 Alta"
responsavel: "Dev"
---

# Segmentos: Signal automático — 03/04/2026

**Data:** 03/04/2026
**Responsável:** Dev
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

Implementar signal post_save no LeadProspecto que avalia segmentos dinâmicos do tenant e adiciona/remove o lead automaticamente.

---

## Tarefas

- [ ] Signal post_save em LeadProspecto para avaliar segmentos dinâmicos
- [ ] Respeitar _skip_segmento para importação em massa
- [ ] Atualizar total_leads do segmento

---

## Resultado esperado

Lead novo que atende regra "Origem = WhatsApp AND Score >= 7" aparece automaticamente no segmento.
