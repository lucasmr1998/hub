# Atendimento — Sessoes e telas de acompanhamento

Telas do painel para visualizar sessoes de atendimento em andamento e historicas.

---

## Lista de sessoes

**URL:** `/configuracoes/sessoes/`

- Lista todas as sessoes com status, progresso, nodo atual
- Filtros por status (em andamento, completado, etc.) e por fluxo
- Botao "Ativos" nos cards de fluxo filtra sessoes ativas

---

## Detalhe da sessao

**URL:** `/configuracoes/sessoes/<id>/`

- Info: fluxo, canal, inicio, duracao, score, progresso
- Nodo atual (onde o lead esta)
- Respostas do lead
- **Log de execucao** passo a passo: cada nodo com status, mensagem e timestamp

Util para diagnosticar por que um lead abandonou, validar que IA tomou a decisao certa, ou auditar execucao.

---

## Fluxo ao vivo

**URL:** `/configuracoes/sessoes/<id>/fluxo/`

- Editor Drawflow em modo **read-only**
- Nodos executados com **borda verde**
- Nodo atual com **borda azul pulsando**
- Sidebar com legenda, dados da sessao e respostas

Visualizacao ideal para acompanhar em tempo real um lead "vivo" no fluxo.

---

## Painel de logs no editor

**Acesso:** botao "Logs" no toolbar do editor de fluxos.

- Lista todos os atendimentos do fluxo (lead, status, duracao)
- Click no atendimento → timeline de execucao de cada nodo
- Util para debug de prompts e condicoes ao iterar um fluxo
