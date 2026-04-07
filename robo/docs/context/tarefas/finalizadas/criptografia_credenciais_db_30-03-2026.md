---
name: "Criptografar Credenciais API no Banco"
description: "Os models `IntegracaoAPI` armazenam `client_secret`, `password` e `access_token` em texto plano no banco. Se o banco for"
prioridade: "🟠 Alta"
responsavel: "Dev / Segurança (AppSec)"
---

# Criptografar Credenciais API no Banco — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟠 Alta
**Status:** ⏳ Aguardando

---

## Descrição

Os models `IntegracaoAPI` armazenam `client_secret`, `password` e `access_token` em texto plano no banco. Se o banco for comprometido (dump, backup vazado, acesso indevido), todas as credenciais de integração ficam expostas.

---

## Tarefas

- [ ] Avaliar django-cryptography ou django-fernet-fields para criptografia de campo
- [ ] Instalar e configurar a biblioteca escolhida
- [ ] Migrar campos `client_secret`, `password` e `access_token` para campos criptografados
- [ ] Gerar migration (dados existentes serão re-criptografados)
- [ ] Testar que leitura/escrita das credenciais continua funcionando (HubSoft, N8N)
- [ ] Adicionar chave de criptografia ao `.env` (`FIELD_ENCRYPTION_KEY`)

---

## Contexto e referências

- Model: `apps/integracoes/models.py`, campos client_secret, password, access_token
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Credenciais de API criptografadas em repouso no banco. Dump do banco não expõe senhas.
