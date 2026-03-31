---
name: "Admin Aurora — Verificação de Tenant por Objeto"
description: "O painel Admin Aurora usa `@staff_required` (verifica `is_staff`) mas não valida se o objeto acessado pertence ao tenant"
prioridade: "🟡 Média"
responsavel: "Dev / Segurança (AppSec)"
---

# Admin Aurora — Verificação de Tenant por Objeto — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

O painel Admin Aurora usa `@staff_required` (verifica `is_staff`) mas não valida se o objeto acessado pertence ao tenant do usuário. Um staff de Tenant A pode acessar detalhes de Tenant B via URL direta.

---

## Tarefas

- [ ] Adicionar verificação de tenant em todas as views que recebem ID por URL
- [ ] Restringir `tenant_detalhe` para superusers ou verificar que o staff pertence ao tenant
- [ ] Revisar permissões: staff vê apenas seu tenant, superuser vê todos
- [ ] Testar com staff de Tenant A acessando URL de Tenant B (esperar 403)

---

## Contexto e referências

- Views: `apps/admin_aurora/views.py`, linhas 21-279
- Decorator: `staff_required` verifica apenas `is_staff`
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Staff users só acessam dados do seu tenant. Superusers acessam todos. Acesso indevido retorna 403.
