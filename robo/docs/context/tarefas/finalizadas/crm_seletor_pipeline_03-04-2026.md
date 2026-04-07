---
name: "CRM: Seletor de pipeline no Kanban"
description: "Permitir trocar entre pipelines criados na página do CRM Kanban"
prioridade: "🔴 Alta"
responsavel: "Dev"
---

# CRM: Seletor de pipeline no Kanban — 03/04/2026

**Data:** 03/04/2026
**Responsável:** Dev
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

A página do Pipeline CRM foi criada antes do sistema suportar múltiplos pipelines por tenant. Hoje o tenant pode ter vários pipelines (ex: Vendas B2B, Vendas B2C, Onboarding), mas o Kanban não permite trocar entre eles.

---

## Tarefas

- [ ] Adicionar seletor de pipeline (tabs ou dropdown) no topo do Kanban
- [ ] Enviar pipeline_id na chamada da API api_pipeline_dados
- [ ] Manter pipeline selecionado via query param (?pipeline=ID)
- [ ] Atualizar estágios e oportunidades ao trocar pipeline

---

## Resultado esperado

Usuário consegue trocar entre pipelines no Kanban sem sair da página.
