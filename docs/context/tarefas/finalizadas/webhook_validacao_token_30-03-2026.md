---
name: "Validação de Token nos Webhooks"
description: "O webhook `webhook_hubsoft_contrato()` aceita qualquer POST sem validar a origem. Um atacante pode forjar confirmações d"
prioridade: "🔴 Alta"
responsavel: "Dev / Segurança (AppSec)"
---

# Validação de Token nos Webhooks — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

O webhook `webhook_hubsoft_contrato()` aceita qualquer POST sem validar a origem. Um atacante pode forjar confirmações de contrato e mover oportunidades para "Cliente Ativo", causando fraude de receita. Outros webhooks do N8N têm o mesmo problema.

---

## Tarefas

- [ ] Criar variável de ambiente `WEBHOOK_SECRET_TOKEN` no `.env`
- [ ] Implementar validação de token no header `X-Webhook-Token` no `webhook_hubsoft_contrato()` (CRM)
- [ ] Implementar a mesma validação nos webhooks de `vendas_web/views.py` (ex: `registrar_lead_api`)
- [ ] Configurar o token no N8N (header de autenticação nos workflows)
- [ ] Retornar 401 Unauthorized se token inválido ou ausente
- [ ] Adicionar log de tentativas inválidas para monitoramento
- [ ] Documentar o processo de configuração do token para novos webhooks

---

## Contexto e referências

- Webhook CRM: `apps/comercial/crm/views.py`, `webhook_hubsoft_contrato()`
- Webhook vendas_web: `vendas_web/views.py`, múltiplos endpoints com `@csrf_exempt`
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Todos os webhooks validam um token secreto no header antes de processar. Requisições sem token válido são rejeitadas com 401. Tentativas inválidas são logadas.
