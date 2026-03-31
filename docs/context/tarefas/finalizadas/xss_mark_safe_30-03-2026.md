---
name: "Corrigir XSS — mark_safe e format_html"
description: "Template tags de parceiros usam `mark_safe(json.dumps(data))` com dados de usuário (título, descrição de cupom). O `admi"
prioridade: "🟡 Média"
responsavel: "Dev / Segurança (AppSec)"
---

# Corrigir XSS — mark_safe e format_html — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

Template tags de parceiros usam `mark_safe(json.dumps(data))` com dados de usuário (título, descrição de cupom). O `admin_config.py` usa `format_html()` com conteúdo não escapado. Ambos são vetores de XSS armazenado se os dados contiverem JavaScript.

---

## Tarefas

- [ ] Substituir `mark_safe(json.dumps(...))` por `json_script` filter do Django em `parceiros/templatetags/parceiros_tags.py`
- [ ] Corrigir `format_html()` em `vendas_web/admin_config.py` para escapar conteúdo
- [ ] Auditar outros usos de `mark_safe` e `|safe` nos templates
- [ ] Testar com payloads XSS (ex: `<script>alert(1)</script>` como título de cupom)

---

## Contexto e referências

- `apps/cs/parceiros/templatetags/parceiros_tags.py`, linha 27
- `vendas_web/admin_config.py`, linhas 20-53
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Zero uso de `mark_safe` com dados de usuário. Conteúdo dinâmico sempre escapado.
