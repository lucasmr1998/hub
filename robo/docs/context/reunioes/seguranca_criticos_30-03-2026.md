# Correção de Vulnerabilidades Críticas de Segurança — 30/03/2026

**Data:** 30/03/2026
**Participantes:** Dev, Segurança (AppSec)
**Tipo:** Implementação técnica

---

## Contexto

Scan de segurança completo identificou 5 vulnerabilidades críticas, 9 altas e 8 médias. As 5 críticas foram corrigidas nesta sessão.

---

## Correções realizadas

### 1. Credencial HubSoft hardcoded — ✅ Corrigido
**Arquivo:** `apps/cs/clube/management/commands/testar_pontuacoes.py`
**O que tinha:** Senha do banco HubSoft em texto plano no código.
**O que foi feito:** Substituído por `os.environ['HUBSOFT_DB_*']`. Adicionado ao `.env.example`.
**Ação pendente:** Rotacionar a senha exposta no HubSoft (responsável: admin do provedor).

### 2. Admin exibe senhas (render_value=True) — ✅ Corrigido
**Arquivo:** `apps/integracoes/admin.py`
**O que tinha:** `PasswordInput(render_value=True)` mostrava senha e client_secret em texto plano no HTML.
**O que foi feito:** Removido `render_value=True`. Campos ficam vazios ao editar. Adicionado `clean_password()` e `clean_client_secret()` para manter valor existente se campo vazio.

### 3. Webhook sem validação de token — ✅ Corrigido
**Arquivos:** `apps/comercial/crm/views.py`, `crm/views.py`
**O que tinha:** `webhook_hubsoft_contrato()` aceitava qualquer POST, permitindo forjar confirmações de contrato.
**O que foi feito:**
- Criado `apps/sistema/decorators.py` com `@webhook_token_required` e `@api_token_required`
- Decorator valida `Authorization: Bearer <token>` no header
- Aplicado no webhook do CRM
- Tokens configuráveis via `WEBHOOK_SECRET_TOKEN` e `N8N_API_TOKEN` no `.env`
- Tentativas inválidas são logadas

### 4. CRM sem TenantMixin (9 models) — ✅ Corrigido
**Arquivo:** `apps/comercial/crm/models.py`
**O que tinha:** 13 models sem FK tenant. Qualquer tenant via dados de outro.
**O que foi feito:**
- Adicionado `TenantMixin` em todos os 13 models (PipelineEstagio, EquipeVendas, PerfilVendedor, TagCRM, OportunidadeVenda, HistoricoPipelineEstagio, TarefaCRM, NotaInterna, MetaVendas, SegmentoCRM, MembroSegmento, AlertaRetencao, ConfiguracaoCRM)
- Migration `0004` gerada e aplicada (SQLite local)
- Campo tenant nullable para compatibilidade com dados existentes
- TenantManager (auto-filtro) ativo em todos os models

### 5. 48+ endpoints sem autenticação — ✅ Corrigido
**Arquivos:** `vendas_web/views.py`, `vendas_web/views_api_atendimento.py`
**O que tinha:** Todos os endpoints de API usavam `@csrf_exempt` sem autenticação.
**O que foi feito:**
- **27 endpoints N8N/externos:** adicionado `@api_token_required` (valida `Authorization: Bearer <N8N_API_TOKEN>`)
- **21 endpoints do painel:** removido `@csrf_exempt`, adicionado `@login_required`
- **3 endpoints públicos:** mantidos sem auth (cadastro cliente, upload documento, consulta CEP)

---

## Validação

- `manage.py check` — 0 erros
- 16 testes de isolamento tenant — todos passando
- Migration CRM aplicada com sucesso (SQLite local)

---

## Pendências pós-correção

- [ ] Rotacionar senha HubSoft exposta no código (admin do provedor)
- [ ] Configurar `WEBHOOK_SECRET_TOKEN` e `N8N_API_TOKEN` no `.env` de produção
- [ ] Atualizar workflows do N8N para enviar `Authorization: Bearer <token>` no header
- [ ] Deploy das correções em produção
- [ ] Data migration para popular tenant nos registros existentes do CRM

---

## Arquivos criados/modificados

| Arquivo | Ação |
|---------|------|
| `apps/sistema/decorators.py` | **Criado** — decorators webhook_token_required e api_token_required |
| `apps/sistema/middleware.py` | Atualizado — LoginRequiredMiddleware movido para cá |
| `apps/sistema/context_processors.py` | **Criado** — empresa_context movido de vendas_web |
| `apps/integracoes/admin.py` | Corrigido — render_value removido |
| `apps/comercial/crm/models.py` | Corrigido — TenantMixin em 13 models |
| `apps/comercial/crm/views.py` | Corrigido — webhook_token_required no webhook |
| `apps/cs/clube/management/commands/testar_pontuacoes.py` | Corrigido — credenciais via env |
| `vendas_web/views.py` | Corrigido — auth em 24 endpoints |
| `vendas_web/views_api_atendimento.py` | Corrigido — auth em 24 endpoints |
| `.env.example` | Atualizado — HUBSOFT_DB_*, WEBHOOK_SECRET_TOKEN, N8N_API_TOKEN |
