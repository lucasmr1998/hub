---
name: "Fluxo de recuperacao de senha"
description: "Implementar fluxo de recuperacao de senha para usuarios do sistema"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Fluxo de Recuperacao de Senha — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descricao

Usuarios nao tem como recuperar a senha caso esquecam. Implementar fluxo completo: tela "Esqueci minha senha" → email com link de reset → tela de nova senha.

---

## Tarefas

- [ ] Tela de "Esqueci minha senha" com campo de email
- [ ] Envio de email com token/link de reset (usar Django PasswordResetView ou custom)
- [ ] Tela de redefinicao de senha
- [ ] Configurar envio de email (SMTP ou provedor)
- [ ] Link na tela de login
- [ ] Testar fluxo completo

---

## Contexto e referencias

- Login: `apps/sistema/views.py`
- Template login: `apps/sistema/templates/sistema/login.html`
- Django tem `PasswordResetView`, `PasswordResetConfirmView` built-in

---

## Resultado esperado

Usuario consegue redefinir senha via email sem precisar de admin.
