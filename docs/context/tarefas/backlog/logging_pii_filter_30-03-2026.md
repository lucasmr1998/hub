# Filtro de PII no Logging — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev / Segurança (AppSec)
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

A configuração de logging em produção não possui filtros para mascarar dados pessoais. Se um desenvolvedor logar um objeto ou request com CPF, email ou telefone, esses dados ficam nos logs sem proteção.

---

## Tarefas

- [ ] Criar classe `PIIFilter(logging.Filter)` que mascara padrões de CPF, email e telefone
- [ ] Adicionar filtro a todos os handlers no settings de logging
- [ ] Testar que logs de integração (HubSoft) não expõem dados pessoais
- [ ] Documentar regra: nunca logar dados pessoais diretamente

---

## Contexto e referências

- Logging: `gerenciador_vendas/settings_production.py`, linhas 57-99
- Scan de segurança realizado em 30/03/2026

---

## Resultado esperado

Filtro de PII ativo em produção. CPFs mascarados como `XXX.XXX.XXX-XX`, emails como `[email]`.
