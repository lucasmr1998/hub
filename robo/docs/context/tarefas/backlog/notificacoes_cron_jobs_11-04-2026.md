---
name: "Cron jobs de notificacoes (tarefa vencendo, SLA, mencao)"
description: "Implementar management commands periodicos para notificacoes que dependem de verificacao temporal"
prioridade: "🟢 Baixa"
responsavel: "Tech Lead"
---

# Cron Jobs de Notificacoes — 11/04/2026

**Data:** 11/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🟢 Baixa
**Status:** ⏳ Aguardando

---

## Descricao

3 tipos de notificacao que nao podem ser disparados por signals porque dependem de verificacao temporal periodica. Precisam de management commands rodando via cron/celery.

---

## Tarefas

- [ ] `tarefa_vencendo`: command que busca TarefaCRM com data_vencimento nas proximas 24h e status pendente/em_andamento
- [ ] `sla_estourando`: command que busca Tickets abertos com SLA proximo do limite (ex: 80% do tempo)
- [ ] `mencao_nota`: detectar @username em notas internas do CRM e notificar o mencionado
- [ ] Registrar commands em `apps/notificacoes/management/commands/`
- [ ] Documentar frequencia recomendada (ex: a cada 15min para SLA, 1x/dia para tarefas)

---

## Contexto e referencias

- Services: `apps/notificacoes/services/notificacao_service.py`
- TarefaCRM: `apps/comercial/crm/models.py` (campo data_vencimento, notificacao_enviada)
- Ticket: `apps/suporte/models.py` (SLA por plano)
- Doc modulo: `docs/PRODUTO/16-NOTIFICACOES.md`

---

## Resultado esperado

Agentes recebem alerta antes de tarefas vencerem e antes do SLA estourar. Usuarios mencionados em notas sao notificados.
