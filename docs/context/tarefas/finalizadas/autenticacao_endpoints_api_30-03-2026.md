# Autenticação nos 48+ Endpoints de API — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

48+ endpoints de API usam `@csrf_exempt` sem nenhuma autenticação. Qualquer pessoa na internet consegue criar leads, aprovar/rejeitar vendas, deletar imagens e acessar dashboards. Inclui endpoints com impacto financeiro direto (`aprovar_venda_api`, `rejeitar_venda_api`).

---

## Tarefas

### Categorização dos endpoints
- [ ] Mapear todos os endpoints com `@csrf_exempt` e classificar em:
  - **Webhook/N8N** (chamados por sistemas externos) → autenticação por API Key
  - **Painel** (chamados pelo frontend) → remover `@csrf_exempt`, usar `@login_required` + CSRF token
  - **Público** (cadastro de cliente) → manter público mas com rate limiting

### Implementação — APIs do painel
- [ ] Remover `@csrf_exempt` dos endpoints do painel (dashboard_data, aprovar_venda, etc.)
- [ ] Adicionar `@login_required` nos endpoints que exigem autenticação
- [ ] Garantir que o frontend envia o CSRF token via header `X-CSRFToken`

### Implementação — Webhooks/N8N
- [ ] Criar decorator `@webhook_auth_required` que valida `Authorization: Bearer <token>`
- [ ] Criar variável de ambiente `N8N_API_TOKEN`
- [ ] Aplicar nos endpoints chamados pelo N8N (registrar_lead, registrar_prospecto, etc.)
- [ ] Atualizar os workflows do N8N para enviar o token no header

### Implementação — Endpoints públicos
- [ ] Manter `api_cadastro_cliente` e `api_consulta_cep` públicos
- [ ] Adicionar rate limiting (ex: 10 req/min por IP)

### Validação
- [ ] Testar que endpoints do painel rejeitam requests sem CSRF/login
- [ ] Testar que webhooks rejeitam requests sem token
- [ ] Testar que endpoints públicos funcionam sem auth mas com rate limit
- [ ] Atualizar a isenção do LoginRequiredMiddleware (`^api/` é muito amplo)

---

## Contexto e referências

- Endpoints: `vendas_web/views.py` e `vendas_web/views_api_atendimento.py`
- LoginRequiredMiddleware: `apps/sistema/middleware.py` (isenta `^api/`)
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Zero endpoints de API sem autenticação (exceto os explicitamente públicos com rate limiting). Webhooks protegidos por token. Frontend usando CSRF token corretamente.
