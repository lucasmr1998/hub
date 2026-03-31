---
name: "Autenticação e Tenant no Módulo Clube"
description: "As APIs do Clube de Benefícios usam session-based auth (`request.session.get('auth_membro_id')`) sem verificar se o memb"
prioridade: "🟠 Alta"
responsavel: "Dev / Segurança (AppSec)"
---

# Autenticação e Tenant no Módulo Clube — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟠 Alta
**Status:** ⏳ Aguardando

---

## Descrição

As APIs do Clube de Benefícios usam session-based auth (`request.session.get('auth_membro_id')`) sem verificar se o membro pertence ao tenant atual. Um membro de um provedor poderia acessar dados de outro provedor se a sessão for comprometida.

---

## Tarefas

- [ ] Adicionar verificação de tenant nas APIs do clube (`apps/cs/clube/views/api_views.py`)
- [ ] Garantir que `MembroClube.objects.get(id=auth_membro_id)` filtra por tenant
- [ ] Revisar login do membro para incluir tenant na sessão
- [ ] Testar que membro de Tenant A não acessa dados de Tenant B

---

## Contexto e referências

- Views: `apps/cs/clube/views/api_views.py`, linhas 21-50, 191-300
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Todas as operações do clube validam que o membro pertence ao tenant do request.
