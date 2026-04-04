---
name: "Segmentos: Página dedicada com regras dinâmicas"
description: "Criar página robusta de criação/edição de segmentos com builder de regras dinâmicas"
prioridade: "🔴 Alta"
responsavel: "Dev"
---

# Segmentos: Página dedicada com regras dinâmicas — 03/04/2026

**Data:** 03/04/2026
**Responsável:** Dev
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

Substituir o modal de criação de segmentos por uma página dedicada com builder de regras dinâmicas (como o builder das Automações). O cliente define condições e o sistema filtra leads automaticamente.

---

## Tarefas

- [ ] Model: adicionar campo `regras` (JSONField) ao SegmentoCRM para regras dinâmicas
- [ ] View: criar página dedicada de criação/edição
- [ ] Template: builder visual de regras (campo + operador + valor)
- [ ] API: endpoint para preview de leads que atendem as regras
- [ ] Lógica: avaliar regras e atualizar membros automaticamente
- [ ] Migração

---

## Resultado esperado

Página `/marketing/segmentos/criar/` com builder de regras. Ao definir "Origem = WhatsApp AND Score >= 7", o sistema mostra quantos leads entram e atualiza automaticamente.
