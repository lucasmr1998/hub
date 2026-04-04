---
name: "Módulo Inbox de Atendimento/Suporte Completo"
description: "Inbox Chatwoot-style: conversas, equipes, filas, distribuição, widget, FAQ, métricas"
prioridade: "🔴 Alta"
responsavel: "Dev"
---

# Módulo Inbox de Atendimento/Suporte — 03/04/2026

**Data:** 03/04/2026
**Responsável:** Dev
**Prioridade:** 🔴 Alta
**Status:** ✅ Concluída (14 phases em 3 sessões)

---

## Descrição

Módulo completo de atendimento estilo Chatwoot/Intercom. Inbox de conversas em tempo real com dois canais (WhatsApp via webhook e Chat Widget embeddable), equipes de atendimento, filas com distribuição automática (round-robin/menor carga), transferência, FAQ/base de conhecimento, dashboard de métricas e integração com automações.

---

## Tarefas

### Sessão 1: Inbox Base
- [x] Models core (CanalInbox, Conversa, Mensagem, etc.)
- [x] API webhook (receber/enviar mensagens, status)
- [x] Inbox UI three-panel (lista, chat, contexto)
- [x] WebSocket (Django Channels)
- [x] Integração automações (3 eventos)

### Sessão 2: Equipes e Distribuição
- [x] Models (EquipeInbox, FilaInbox, PerfilAgenteInbox, etc.)
- [x] Engine de distribuição automática
- [x] Página de configurações (9 abas)
- [x] Transferência de conversas
- [x] Dashboard de métricas

### Sessão 3: Widget + FAQ
- [x] Models FAQ (CategoriaFAQ, ArtigoFAQ)
- [x] Model WidgetConfig (token público, cores, domínios)
- [x] API pública (7 endpoints sem login, CORS)
- [x] Widget JS embeddable (aurora-chat.js, 3 abas)

---

## Resultado

- 17 models no app `apps/inbox/`
- 26+ endpoints (internos, N8N, públicos)
- Widget JS vanilla (~15KB, zero dependências)
- Dashboard com Chart.js
- 3 migrations no PostgreSQL
- Documentação completa em `docs/PRODUTO/06-INBOX.md`
