---
name: "Filtrar User por Tenant em Views"
description: "Views do CRM e outros módulos fazem `User.objects.filter(is_active=True)` sem filtrar por tenant. Dropdowns de atribuiçã"
prioridade: "🟠 Alta"
responsavel: "Dev / Segurança (AppSec)"
---

# Filtrar User por Tenant em Views — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟠 Alta
**Status:** ⏳ Aguardando

---

## Descrição

Views do CRM e outros módulos fazem `User.objects.filter(is_active=True)` sem filtrar por tenant. Dropdowns de atribuição de responsável mostram usuários de todos os tenants. O model User do Django não tem tenant, mas PerfilUsuario faz a ponte.

---

## Tarefas

- [ ] Criar helper `get_tenant_users(tenant)` que retorna users via PerfilUsuario
- [ ] Substituir `User.objects.filter(is_active=True)` por `get_tenant_users()` nas views do CRM
- [ ] Verificar outros locais que listam usuários (dashboard, admin, notificações)
- [ ] Testar que dropdowns só mostram usuários do tenant correto

---

## Contexto e referências

- CRM views: `apps/comercial/crm/views.py`, linhas 79, 297, 642, 682
- PerfilUsuario: `apps/sistema/models.py` (FK tenant)
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Nenhum dropdown ou listagem exibe usuários de outros tenants. Filtragem via PerfilUsuario.tenant.
