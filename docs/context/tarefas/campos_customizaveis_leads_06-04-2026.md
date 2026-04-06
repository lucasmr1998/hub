---
name: "Campos customizaveis nos Leads"
description: "Permitir que cada tenant defina campos extras nos leads via JSONField"
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Campos Customizaveis nos Leads — 06/04/2026

**Data:** 06/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🟡 Media
**Status:** 🔧 Em andamento

---

## Descricao

Permitir que cada provedor (tenant) crie campos personalizados nos leads, sem necessidade de alterar o schema do banco. Abordagem: model CampoCustomizado por tenant + JSONField no LeadProspecto.

---

## Tarefas

- [ ] Model CampoCustomizado (nome, slug, tipo, opcoes, obrigatorio, ordem)
- [ ] Adicionar campo dados_custom (JSONField) no LeadProspecto
- [ ] Migration local
- [ ] Tela de configuracao para gerenciar campos custom
- [ ] Renderizar campos custom no detalhe do lead
- [ ] Suportar campos custom na API

---

## Contexto e referencias

Decisao: JSONField escolhido por flexibilidade e bom suporte no Django 5.2 + PostgreSQL (indexes GIN).
Alternativas descartadas: EAV (complexidade) e toggle de visibilidade (sem campos novos).

---

## Resultado esperado

Cada tenant pode criar, editar e ordenar campos extras para seus leads. Os campos aparecem no detalhe do lead e na API. Sem necessidade de migrations para novos campos.
