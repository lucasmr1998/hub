---
name: "Mensagens com botao na Uazapi"
description: "Implementar envio de mensagens interativas com botoes via Uazapi (WhatsApp)"
prioridade: "🟡 Media"
responsavel: "Tech Lead"
---

# Mensagens com Botao na Uazapi — 10/04/2026

**Data:** 10/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🟡 Media
**Status:** ⏳ Aguardando

---

## Descricao

Implementar suporte a mensagens interativas do WhatsApp via Uazapi: botoes de resposta rapida (reply buttons) e listas de opcoes. Hoje as opcoes de select sao enviadas como texto numerado ("1. Opcao A, 2. Opcao B"). Com botoes nativos, a experiencia fica melhor.

---

## Tarefas

- [ ] Verificar API Uazapi para envio de botoes (send/buttons, send/list)
- [ ] Adaptar o provider Uazapi para enviar botoes quando o nodo e do tipo select
- [ ] Adaptar o signal para montar payload de botoes em vez de texto
- [ ] Tratar resposta de botao (callback) no webhook
- [ ] Testar com WhatsApp real

---

## Contexto e referencias

- Provider: `apps/inbox/providers/uazapi.py`
- Service: `apps/integracoes/services/uazapi.py` (ja tem `enviar_menu`)
- Signal: `apps/inbox/signals.py`
- Documentacao Uazapi: https://uazapi.com/docs

---

## Resultado esperado

Perguntas do tipo select no fluxo enviam botoes nativos do WhatsApp em vez de texto numerado.
