# Módulo Inbox de Atendimento/Suporte — 03/04/2026

**Data:** 03/04/2026
**Participantes:** Lucas (Dev), Claude (Tech Lead / PM)
**Duração:** Sessão intensiva (~4h)

---

## Contexto

O sistema da AuroraISP já tinha um motor de fluxos automatizados (`apps/comercial/atendimento/`) e um sistema de tickets (`apps/suporte/`), mas não tinha um inbox de conversas em tempo real para os agentes atenderem leads/clientes. A tarefa do backlog "Módulo Atendimento/Suporte estilo Chatwoot" estava aguardando planejamento.

---

## Principais pontos discutidos

- Diferença entre o módulo de fluxos existente (bot) e o inbox necessário (conversas humanas)
- Arquitetura: novo app `apps/inbox/` top-level (cross-cutting, não aninhado)
- Posicionamento na navegação: dentro do menu Suporte (não como módulo separado na topbar)
- Dois canais: WhatsApp (via webhook/N8N) e Chat Widget (embeddable JS)
- Equipes, filas e distribuição automática (round-robin, menor carga)
- FAQ/Base de conhecimento para o widget
- Migração de SQLite para PostgreSQL local (aurora_dev)

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| App `inbox/` como top-level | Cross-cutting: conecta leads, tickets, CRM, automações |
| Inbox dentro do menu Suporte | Faz parte do mesmo fluxo de atendimento, não justifica módulo separado na topbar |
| WebSocket com fallback polling | Channels para real-time, polling 5s como fallback robusto |
| InMemoryChannelLayer em dev | Evita dependência de Redis em dev. Produção usa Redis |
| Daphne removido do INSTALLED_APPS em dev | Bugs de logging no Windows. Adicionado só em produção |
| Widget sem iframe | Injeta DOM direto na página, evita problemas de X_FRAME_OPTIONS e CSP |
| API pública sem login | Auth via token público UUID no query param + validação de Origin |
| FAQ novo (não reutilizar megaroleta) | megaroleta é legacy e read-only conforme CLAUDE.md |
| PostgreSQL local (aurora_dev) | SQLite tem limitações. Banco `aurora_dev` com user `postgres` já existia |
| Agentes em múltiplas equipes | Diferente do CRM (1:1), inbox usa M2M via MembroEquipeInbox |

---

## O que foi implementado

### Sessão 1: Inbox Base (5 phases)
1. **Phase 1:** 6 models core (CanalInbox, Conversa, Mensagem, RespostaRapida, EtiquetaConversa, NotaInternaConversa) + admin + migrations
2. **Phase 2:** API webhook genérica (receber/enviar mensagens, status de entrega) + services
3. **Phase 3:** Inbox UI three-panel (lista conversas, chat, contexto do lead) + 13 APIs internas AJAX
4. **Phase 4:** WebSocket com Django Channels + InMemoryChannelLayer + Daphne
5. **Phase 5:** Integração com automações (3 novos eventos: mensagem_recebida, conversa_aberta, conversa_resolvida)

### Sessão 2: Equipes, Filas, Distribuição (5 phases)
1. **Phase 1:** 8 models novos (EquipeInbox, MembroEquipeInbox, PerfilAgenteInbox, FilaInbox, RegraRoteamento, HistoricoTransferencia, HorarioAtendimento, ConfiguracaoInbox) + 2 FKs na Conversa
2. **Phase 2:** Engine de distribuição automática (round-robin, menor carga, manual) + verificação de horário + status do agente
3. **Phase 3:** Página de configurações com 7 abas (equipes, filas, respostas, etiquetas, canais, horário, geral)
4. **Phase 4:** Transferência de conversas (para agente/equipe/fila + modal no chat)
5. **Phase 5:** Dashboard de métricas (5 KPIs, gráfico Chart.js 30 dias, ranking agentes)

### Sessão 3: Widget + FAQ (4 phases)
1. **Phase 1-2:** 3 models (CategoriaFAQ, ArtigoFAQ, WidgetConfig) + abas FAQ e Widget na config
2. **Phase 3:** API pública (7 endpoints sem login, auth via token, CORS manual) + `receber_mensagem_widget()`
3. **Phase 4:** Widget JS (`aurora-chat.js`, ~15KB, vanilla, 3 abas: Início/Mensagens/Ajuda)
4. Widget adicionado ao `base.html` do sistema para testes

---

## Resultado final

- **17 models** no app inbox
- **26+ endpoints** (internos, N8N, públicos)
- **3 migrations** aplicadas no PostgreSQL
- **9 abas** na página de configurações
- **Dashboard** com métricas e gráfico
- **Widget JS** embeddable com FAQ
- **Distribuição automática** com equipes e filas
- **Integração** com automações, tickets, CRM e leads
- **60 testes** existentes passando

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Configurar N8N com workflow WhatsApp | Dev/Ops |
| Instalar Redis para produção (WebSocket) | DevOps |
| Configurar Daphne + Nginx para WebSocket | DevOps |
| Criar FAQ real com artigos do provedor | CS |
| Testar widget em site externo do provedor | Dev |
| Implementar CSAT (pesquisa de satisfação) | Dev (futuro) |

---

## Próximos passos

- [ ] Configurar N8N para WhatsApp → webhook inbox
- [ ] Testar o widget embeddado em um site real de provedor
- [ ] Criar conteúdo de FAQ para o primeiro cliente
- [ ] Deploy com Redis + Daphne para WebSocket em produção
- [ ] Refinar UI do inbox baseado em feedback dos atendentes
