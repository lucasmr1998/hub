---
name: "Forçar HTTPS e Cookies Seguros"
description: "O `settings.py` base não define `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` nem `SECURE_SSL_REDIRECT`. Em produção, co"
prioridade: "🟠 Alta"
responsavel: "DevOps / Segurança (AppSec)"
---

# Forçar HTTPS e Cookies Seguros — 30/03/2026

**Data:** 30/03/2026
**Responsável:** DevOps / Segurança (AppSec)
**Prioridade:** 🟠 Alta
**Status:** ⏳ Aguardando

---

## Descrição

O `settings.py` base não define `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` nem `SECURE_SSL_REDIRECT`. Em produção, cookies podem ser transmitidos via HTTP, permitindo ataques man-in-the-middle.

---

## Tarefas

- [ ] Adicionar ao settings.py (com fallback via env var):
  - `SECURE_SSL_REDIRECT`
  - `SESSION_COOKIE_SECURE`
  - `CSRF_COOKIE_SECURE`
  - `SECURE_HSTS_SECONDS` (já existe no production, garantir no base)
- [ ] Verificar que settings_production.py tem todas as flags ativas
- [ ] Testar que settings_local.py não quebra com HTTP (valores False para dev)
- [ ] Verificar configuração SSL do Nginx no servidor

---

## Contexto e referências

- Settings base: `gerenciador_vendas/settings.py`
- Settings prod: `gerenciador_vendas/settings_production.py` (já tem HSTS)
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Cookies de sessão e CSRF marcados como Secure em produção. HTTPS forçado. HSTS ativo.
