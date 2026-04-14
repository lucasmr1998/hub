---
name: "Refatorar Assistente CRM para usar Inbox (Opcao C)"
description: "Migrar assistente CRM do engine separado para o fluxo de atendimento do Inbox com tipo de conversa 'assistente'"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Refatorar Assistente CRM para Inbox — 14/04/2026

**Data:** 14/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando

---

## Descricao

O assistente CRM atualmente roda em engine separado (apps/assistente/engine.py) sem visibilidade no sistema. Migrar para usar o fluxo de atendimento do Inbox (Opcao C), com tipo de conversa 'assistente' filtrado separadamente.

---

## Decisoes tomadas

- Fluxo do assistente fica no **tenant Aurora HQ** (conta da Hubtrix)
- Tools CRM operam no **tenant do usuario** (nao da Aurora)
- Conversas aparecem no Inbox com `modo_atendimento='assistente'`
- Filtro no Inbox para separar conversas de assistente das de clientes
- Usa o engine existente (`_chamar_llm_com_tools`) com as tools de CRM
- Fluxo com 1 no ia_agente (system prompt + 15 tools)

---

## Tarefas

### Fase 1: Model e Webhook
- [ ] Adicionar 'assistente' nas choices de Conversa.modo_atendimento
- [ ] Webhook do assistente: criar/reutilizar Conversa no Inbox (modo_atendimento='assistente')
- [ ] Mensagens vao para inbox.Mensagem (nao mais MensagemAssistente)
- [ ] Manter identificacao por telefone (PerfilUsuario)

### Fase 2: Tools no Engine
- [ ] Registrar as 15 tools como tools do sistema no engine.py
- [ ] Adicionar checkboxes no editor de fluxos
- [ ] Adaptar tools para receber contexto do tenant do usuario (nao do atendimento)

### Fase 3: Fluxo
- [ ] Criar fluxo "Assistente CRM" no tenant Aurora HQ
- [ ] 1 no ia_agente com system prompt e tools habilitadas
- [ ] Vincular ao canal do assistente

### Fase 4: Inbox
- [ ] Filtro/aba separada para conversas modo_atendimento='assistente'
- [ ] Nao misturar com conversas de clientes

### Fase 5: Limpeza
- [ ] Deprecar apps/assistente/engine.py
- [ ] Deprecar ConversaAssistente e MensagemAssistente
- [ ] Manter ConfiguracaoAssistenteGlobal e ConfiguracaoAssistenteTenant

---

## Contexto

- Engine atual: `apps/assistente/engine.py` (separado)
- Tools: `apps/assistente/tools.py` (15 tools)
- Webhook: `apps/assistente/views.py`
- Engine fluxo: `apps/comercial/atendimento/engine.py`
- Inbox: `apps/inbox/`
- Config: `ConfiguracaoAssistenteGlobal`, `ConfiguracaoAssistenteTenant`

---

## Resultado esperado

Assistente CRM roda no fluxo de atendimento do Inbox, com visibilidade total (logs, editor, sessoes). Conversas separadas das de clientes. Tools operam no tenant do vendedor.
