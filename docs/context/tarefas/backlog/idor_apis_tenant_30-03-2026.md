---
name: "Corrigir IDOR nas APIs — Verificação de Tenant"
description: "Múltiplas APIs aceitam IDs via parâmetro (lead_id, imagem_id, fluxo_id) sem verificar se o objeto pertence ao tenant do "
prioridade: "🟠 Alta"
responsavel: "Dev / Segurança (AppSec)"
---

# Corrigir IDOR nas APIs — Verificação de Tenant — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟠 Alta
**Status:** ⏳ Aguardando

---

## Descrição

Múltiplas APIs aceitam IDs via parâmetro (lead_id, imagem_id, fluxo_id) sem verificar se o objeto pertence ao tenant do usuário. Um atacante pode acessar, modificar ou deletar dados de outro tenant apenas trocando o ID na requisição.

---

## Tarefas

- [ ] Auditar todos os `.objects.get(pk=X)` e `get_object_or_404(Model, id=X)` sem filtro de tenant
- [ ] Criar helper `get_tenant_object_or_404(Model, tenant, **kwargs)` para uso padronizado
- [ ] Corrigir `deletar_imagem_lead_api()` — adicionar filtro de tenant
- [ ] Corrigir `validar_imagem_api()` — adicionar filtro de tenant
- [ ] Corrigir `imagens_por_cliente_api()` — adicionar filtro de tenant
- [ ] Corrigir `iniciar_atendimento_n8n()` — verificar tenant do lead e fluxo
- [ ] Corrigir `api_lead_hubsoft_status()` em `apps/integracoes/views.py` — verificar tenant
- [ ] Corrigir `get_object_or_404(ModeloCarteirinha, id=X)` em `apps/cs/carteirinha/views.py`
- [ ] Criar testes de IDOR (tentar acessar objeto de outro tenant, esperar 404)

---

## Contexto e referências

- Endpoints afetados: `vendas_web/views.py`, `apps/integracoes/views.py`, `apps/cs/carteirinha/views.py`
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Todas as consultas por ID validam tenant antes de retornar. Requisições para objetos de outro tenant retornam 404.
