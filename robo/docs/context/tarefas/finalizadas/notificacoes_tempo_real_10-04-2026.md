---
name: "Notificacoes em tempo real"
description: "Verificar e implementar sistema de notificacoes para agentes (som/push)"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Notificacoes em Tempo Real — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descricao

Verificar o estado atual do sistema de notificacoes. Agentes precisam ser notificados em tempo real quando: nova conversa chega, conversa transferida para eles, SLA prestes a estourar. Avaliar se o sistema atual funciona e o que falta.

---

## Tarefas

- [ ] Auditar sistema de notificacoes atual (models, views, templates)
- [ ] Verificar se o botao de sino no topbar funciona
- [ ] Implementar notificacao ao receber nova conversa
- [ ] Implementar notificacao ao ser atribuido a conversa
- [ ] Som de notificacao (audio HTML5)
- [ ] Badge com contador no sino
- [ ] Push notification (browser Notification API) — opcional

---

## Contexto e referencias

- Botao sino: `apps/sistema/templates/sistema/base.html` (topbar)
- Model: verificar se existe `Notificacao` em `apps/notificacoes/`
- Polling atual: inbox.js usa POLL_INTERVAL = 5000ms

---

## Resultado esperado

Agente recebe notificacao visual e sonora quando nova conversa chega ou e atribuida a ele.
