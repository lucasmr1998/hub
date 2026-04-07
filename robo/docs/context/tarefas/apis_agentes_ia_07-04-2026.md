---
name: "APIs para Agentes IA (Tools)"
description: "Criar endpoints DRF em /api/v1/n8n/crm/ para agentes externos (N8N) interagirem com o CRM"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# APIs para Agentes IA (Tools) — 07/04/2026

**Data:** 07/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descricao

Criar APIs DRF padronizadas para que agentes externos (N8N, futuramente nosso no Agente IA) possam interagir com o CRM, leads e inbox do sistema. Primeira fase do plano de Agente IA.

---

## Tarefas

- [ ] Serializers DRF para OportunidadeVenda, TarefaCRM, Pipeline, PipelineEstagio
- [ ] POST /api/v1/n8n/crm/oportunidades/ (criar)
- [ ] PUT /api/v1/n8n/crm/oportunidades/<pk>/ (atualizar/mover estagio)
- [ ] GET /api/v1/n8n/crm/oportunidades/buscar/ (buscar por lead)
- [ ] POST /api/v1/n8n/crm/tarefas/ (criar)
- [ ] PUT /api/v1/n8n/crm/tarefas/<pk>/ (atualizar/concluir)
- [ ] GET /api/v1/n8n/crm/pipelines/ (listar com estagios)
- [ ] GET /api/v1/n8n/crm/estagios/ (listar, filtrar por pipeline)
- [ ] POST /api/v1/n8n/inbox/enviar/ (enviar mensagem como bot)
- [ ] Documentar APIs
- [ ] Testar com curl

---

## Contexto e referencias

Plano completo em `.claude/plans/breezy-frolicking-thompson.md`.
Analise do fluxo N8N em `robo/docs/context/reunioes/analise_fluxo_n8n_consultoria_06-04-2026.md`.
APIs existentes em `/api/v1/n8n/leads/`, `/api/v1/n8n/atendimentos/`.

---

## Resultado esperado

N8N pode chamar nossas APIs para criar oportunidades, tarefas, mover estagios e enviar mensagens. Mesmas APIs serao reutilizadas internamente pelo futuro no Agente IA.
