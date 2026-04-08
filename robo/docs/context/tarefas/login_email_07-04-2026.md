---
name: "Login por email em vez de username"
description: "Mudar autenticacao para email unico, permitir usernames duplicados entre tenants"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Login por Email — 07/04/2026

**Data:** 07/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descricao

Hoje o login e por username (Django padrao). Em multi-tenant, dois tenants podem querer criar usuario "admin" ou "vendedor1", causando conflito. Mudar para login por email resolve isso.

---

## Tarefas

- [ ] Criar backend de autenticacao customizado (EmailBackend)
- [ ] Alterar view de login para aceitar email
- [ ] Alterar template de login
- [ ] Alterar criacao de usuario (gerar username automatico ou usar email)
- [ ] Garantir que email e unico globalmente
- [ ] Migrar usuarios existentes (verificar emails duplicados)
- [ ] Atualizar CLAUDE.md e docs

---

## Contexto

Multi-tenant com usernames duplicados entre tenants e um problema real. Email como identificador unico resolve.
