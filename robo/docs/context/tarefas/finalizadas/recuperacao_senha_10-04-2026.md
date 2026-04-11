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
**Status:** ✅ Concluido

---

## Descricao

Usuarios nao tinham como recuperar a senha caso esquecessem. Implementado fluxo completo com dois metodos: email (link de reset) e WhatsApp (codigo de 6 digitos).

---

## Tarefas

- [x] Tela de "Esqueci minha senha" com campo de email/username
- [x] Envio de email com link de reset (SMTP customizavel)
- [x] Envio de codigo via WhatsApp (Uazapi)
- [x] Tela de verificacao de codigo (WhatsApp)
- [x] Tela de redefinicao de senha
- [x] Painel de configuracao no aurora-admin
- [x] Link na tela de login
- [x] Models: ConfiguracaoRecuperacaoSenha e CodigoRecuperacaoSenha
- [x] Migration 0007

---

## Contexto e referencias

- Views: `apps/sistema/views.py` (esqueci_senha_view, verificar_codigo_view, nova_senha_view)
- Models: `apps/sistema/models.py` (ConfiguracaoRecuperacaoSenha, CodigoRecuperacaoSenha)
- Templates: `sistema/esqueci_senha.html`, `sistema/verificar_codigo.html`, `sistema/nova_senha.html`
- Admin: `apps/admin_aurora/views.py` (config_recuperacao_senha_view)
- URLs: `apps/sistema/urls.py`, `apps/admin_aurora/urls.py`

---

## Resultado

Usuario consegue redefinir senha via email (link) ou WhatsApp (codigo de 6 digitos), configuravel pelo aurora-admin.
