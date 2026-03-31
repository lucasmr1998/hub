---
name: "Limpar ALLOWED_HOSTS de Produção"
description: "O `settings_production.py` contém IP hardcoded e `localhost`/`127.0.0.1` no ALLOWED_HOSTS. Isso aumenta a superfície de "
prioridade: "🟡 Média"
responsavel: "DevOps"
---

# Limpar ALLOWED_HOSTS de Produção — 30/03/2026

**Data:** 30/03/2026
**Responsável:** DevOps
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

O `settings_production.py` contém IP hardcoded e `localhost`/`127.0.0.1` no ALLOWED_HOSTS. Isso aumenta a superfície de ataque e expõe o IP do servidor no código.

---

## Tarefas

- [ ] Remover `localhost` e `127.0.0.1` do ALLOWED_HOSTS de produção
- [ ] Remover IP hardcoded (`31.97.243.247`), usar apenas domínios
- [ ] Migrar ALLOWED_HOSTS para variável de ambiente
- [ ] Validar que SECRET_KEY falha explicitamente se vazio em produção

---

## Contexto e referências

- Settings: `gerenciador_vendas/settings_production.py`, linhas 17-23
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

ALLOWED_HOSTS contém apenas domínios. Sem IPs nem localhost em produção.
