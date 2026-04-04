---
name: "Módulo Automações: Backend completo"
description: "Implementar models, engine de execução e APIs do módulo de automações em Marketing"
prioridade: "🔴 Alta"
responsavel: "Dev"
---

# Módulo Automações — Backend — 01/04/2026

**Data:** 01/04/2026
**Responsável:** Dev
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

Implementar o backend do módulo de automações que permite ao cliente criar regras do tipo "Quando X acontecer, se Y, então faça Z". O frontend (lista + builder) já está pronto em `apps/marketing/automacoes/`.

---

## Tarefas

- [x] Frontend: lista de automações com toggle, KPIs, filtros
- [x] Frontend: builder visual (Quando/Se/Então)
- [x] URLs e views placeholder
- [ ] Models: RegraAutomacao, CondicaoRegra, AcaoRegra, LogExecucao
- [ ] Admin registration
- [ ] Views: CRUD de regras via POST do formulário
- [ ] Engine: dispatcher que escuta signals e executa regras ativas
- [ ] Ações: enviar_whatsapp, criar_tarefa, mover_estagio, notificacao_sistema, dar_pontos, webhook
- [ ] Condições: avaliador dinâmico de campo/operador/valor
- [ ] Delay: suporte a ações com atraso (minutos/horas/dias)
- [ ] Log de execuções por regra
- [ ] Testes

---

## Contexto e referências

- Frontend: `apps/marketing/automacoes/templates/automacoes/lista.html` e `criar.html`
- Signals existentes: `apps/integracoes/signals.py`, `apps/comercial/cadastro/signals.py`
- Sistema de notificações: `apps/notificacoes/` (desativado, será conectado)

---

## Resultado esperado

Cliente consegue criar, ativar/desativar e monitorar regras de automação pelo painel. Exemplo: "Quando novo lead chegar via WhatsApp com score >= 7, criar tarefa no CRM e enviar WhatsApp de boas vindas."
