---
name: "Correção CSRF e Segurança de Endpoints"
description: "O roadmap de produto identifica 50+ endpoints com `@csrf_exempt` e APIs sem autenticação adequada. Com o sistema multi-t"
prioridade: "🔴 Alta"
responsavel: "Segurança (AppSec)"
---

# Correção CSRF e Segurança de Endpoints — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Segurança (AppSec)
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descrição

O roadmap de produto identifica 50+ endpoints com `@csrf_exempt` e APIs sem autenticação adequada. Com o sistema multi-tenant em produção, endpoints inseguros representam risco de acesso cruzado entre tenants e ataques CSRF.

---

## Tarefas

- [ ] Auditar todos os endpoints com `@csrf_exempt` no projeto
- [ ] Classificar por risco (alto: dados de tenant, médio: funcional, baixo: público)
- [ ] Remover `@csrf_exempt` onde possível, usar AJAX com CSRF token
- [ ] Implementar autenticação em endpoints de API (Token ou Session)
- [ ] Adicionar verificação de tenant em endpoints críticos
- [ ] Validar que webhooks N8N usam autenticação (API key ou HMAC)
- [ ] Testar cenários de acesso cruzado entre tenants via API
- [ ] Documentar endpoints públicos vs. autenticados

---

## Contexto e referências

- Dívida técnica: `docs/PRODUTO/02-ROADMAP_PRODUTO.md` (CSRF vulnerabilities, 50+ endpoints)
- Agente: `docs/AGENTES/tech/appsec.md`

---

## Resultado esperado

Zero endpoints com `@csrf_exempt` desnecessário. Todas as APIs autenticadas. Isolamento de tenant validado em endpoints críticos.
