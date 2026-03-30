# Remover unsafe-inline e unsafe-eval do CSP — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟠 Alta
**Status:** ⏳ Aguardando

---

## Descrição

A Content Security Policy permite `unsafe-inline` e `unsafe-eval` nos scripts e estilos. Isso anula a proteção contra XSS, pois qualquer script inline pode ser executado. Precisa migrar scripts inline para arquivos externos e usar nonces.

---

## Tarefas

- [ ] Auditar todos os `<script>` inline nos templates
- [ ] Extrair scripts inline para arquivos .js separados
- [ ] Extrair estilos inline para arquivos .css
- [ ] Implementar sistema de nonces para scripts que precisam ser inline
- [ ] Remover `'unsafe-inline'` e `'unsafe-eval'` do `CSP_SCRIPT_SRC` no settings
- [ ] Remover `'unsafe-inline'` do `CSP_STYLE_SRC`
- [ ] Testar todas as páginas após a mudança (dashboard, CRM, CS, cadastro)

---

## Contexto e referências

- Settings: `gerenciador_vendas/settings.py`, linhas 92-115
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

CSP sem unsafe-inline e unsafe-eval. Scripts inline usando nonces. Proteção XSS efetiva.
