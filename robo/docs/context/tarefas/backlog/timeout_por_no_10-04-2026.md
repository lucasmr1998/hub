---
name: "Timeout por no no fluxo"
description: "Se lead nao responde uma pergunta em X min, seguir por caminho alternativo"
prioridade: "🟢 Baixa"
responsavel: "Tech Lead"
---

# Timeout por No no Fluxo — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🟢 Baixa
**Status:** ⏳ Aguardando

---

## Descricao

Hoje o recontato e por fluxo (global). Seria util ter timeout por no individual: "se nao responder esta pergunta em 5min, seguir pelo branch false". Complementa o recontato.

---

## Tarefas

- [ ] Campo `timeout_minutos` na config do nodo questao
- [ ] Cron verifica nodos com timeout e executa branch alternativo
- [ ] UI no modal de config da questao (tab Avancado)

---

## Resultado esperado

Perguntas individuais podem ter timeout configuravel com caminho alternativo.
