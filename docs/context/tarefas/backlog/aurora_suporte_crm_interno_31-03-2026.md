---
name: "Aurora como primeiro cliente: Suporte + CRM interno"
description: "Estruturar a AuroraISP como primeira cliente do próprio sistema. CRM para pipeline de provedores e sistema de suporte."
prioridade: "🔴 Alta"
responsavel: "CEO / PM / Tech Lead"
---

# Aurora como Primeiro Cliente: Suporte + CRM Interno — 31/03/2026

**Data:** 31/03/2026
**Responsável:** CEO / PM / Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

A AuroraISP será a primeira cliente do próprio sistema. O módulo Comercial será usado para gerenciar o pipeline de vendas de provedores, e um novo módulo de Suporte será criado para atender os clientes pós-venda.

---

## Tarefas

### CRM Interno (pipeline de provedores)
- [ ] Criar tenant "Aurora HQ" com configuração interna
- [ ] Definir estágios do pipeline: Lead Identificado > Contato > Qualificado > Demo Agendada > Em Trial > Negociação > Cliente Ativo > Churn
- [ ] Configurar CRM Kanban com os estágios
- [ ] Definir campos customizados para provedores (base de clientes, ERP, cidade, vendedores)
- [ ] Criar métricas: MRR, churn rate, LTV, CAC
- [ ] Integrar acompanhamento de trials (14 dias)
- [ ] Dashboard interno com pipeline e métricas

### Sistema de Suporte (tickets)
- [ ] Definir tipos de ticket: bug, dúvida, solicitação, incidente
- [ ] Definir prioridades: baixa, normal, alta, urgente
- [ ] Definir SLA por plano (Starter: 24h, Start: 8h, Pro: 4h)
- [ ] Criar models: Ticket, ComentarioTicket, CategoriaTicket
- [ ] Criar views: lista de tickets, detalhe, criar, responder
- [ ] Notificação ao abrir/responder ticket (WhatsApp/email)
- [ ] Dashboard de suporte (tickets abertos, SLA, tempo médio)
- [ ] Base de conhecimento / FAQ

### Fluxos de Atendimento
- [ ] Fluxo de onboarding do provedor (passo a passo)
- [ ] Fluxo de suporte técnico (triagem > resolução)
- [ ] Fluxo de churn prevention (alertas > ação > retenção)

---

## Contexto e referências

- Reunião: docs/context/reunioes/aurora_primeiro_cliente_31-03-2026.md
- CRM existente: apps/comercial/crm/ (13 models, pipeline Kanban)
- Suporte será novo app: apps/suporte/
- CS existente: apps/cs/ (clube, parceiros, indicações, carteirinha, NPS, retenção)

---

## Resultado esperado

Aurora opera usando o próprio sistema para vender e dar suporte. Pipeline de provedores gerenciado no CRM. Tickets de suporte com SLA. Métricas de negócio visíveis no dashboard.
