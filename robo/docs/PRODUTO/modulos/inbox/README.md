# Inbox

**Status:** Em producao
**App:** `apps/inbox/`
**Localizacao no painel:** Menu `Suporte` → Sidebar `ATENDIMENTO`

Modulo de conversas em tempo real estilo Chatwoot/Intercom. Permite que agentes conversem com leads e clientes via WhatsApp (webhook) e Chat Widget (embeddable), com interface three-panel unificada, equipes, filas de atendimento, distribuicao automatica, FAQ, metricas e integracao com automacoes.

**Dois canais:**

- **WhatsApp** — mensagens chegam/saem via webhook (pronto para N8N)
- **Chat Widget** — JS embeddable para sites de provedores, com FAQ e 3 abas

---

## Indice

| Arquivo | Conteudo |
|---------|----------|
| [models.md](models.md) | 17 models + campos importantes de Conversa + indices |
| [services.md](services.md) | services.py + modo atendimento (bot vs humano) + signals |
| [distribuicao.md](distribuicao.md) | Engine de distribuicao + horarios por fila |
| [apis.md](apis.md) | Webhook N8N + APIs internas + APIs publicas do widget |
| [websocket.md](websocket.md) | InboxConsumer + groups + actions em tempo real |
| [widget-chat.md](widget-chat.md) | Chat widget embeddable (3 abas + FAQ) |
| [interface.md](interface.md) | Dashboard + configuracoes + sidebar + management commands |

---

## Relacoes com outros modulos

```
                    ┌──────────────┐
                    │ LeadProspecto│
                    │  (leads)    │
                    └──────┬──────┘
                           │ FK lead
┌──────────┐        ┌──────▼──────┐        ┌──────────────┐
│EquipeInbox│───FK──▶│  Conversa   │────FK──▶│    Ticket     │
│FilaInbox  │       │  (inbox)    │        │  (suporte)   │
└──────────┘        └──────┬──────┘        └──────────────┘
                           │ FK oportunidade
                    ┌──────▼──────┐
                    │Oportunidade │
                    │  Venda (crm)│
                    └─────────────┘
```

---

## Estrutura de arquivos

```
apps/inbox/
├── apps.py                    # AppConfig com ready() → importa signals
├── models.py                  # 17 models
├── services.py                # Logica: receber, enviar, transferir
├── distribution.py            # Engine de distribuicao (fila, round-robin, menor carga)
├── serializers.py             # DRF serializers
├── widget_auth.py             # Decorator @widget_token_required + CORS
├── views.py                   # View principal + APIs internas + config + dashboard
├── views_n8n.py               # 2 endpoints webhook (mensagem recebida, status)
├── views_public.py            # 7 endpoints publicos do widget (sem login)
├── urls.py / urls_public.py   # Rotas
├── signals.py                 # 3 signals → engine de automacoes
├── consumers.py               # WebSocket consumer (InboxConsumer)
├── routing.py                 # WebSocket URL routing
├── admin.py                   # Admin para todos os 17 models
├── migrations/                # 0001 (core) + 0002 (equipes/filas) + 0003 (FAQ/widget)
├── management/commands/
│   └── seed_inbox.py
├── templates/inbox/
│   ├── inbox.html             # Three-panel chat
│   ├── configuracoes_inbox.html  # 9 abas de configuracao
│   └── dashboard_inbox.html      # Dashboard com Chart.js
└── static/inbox/
    ├── css/inbox.css
    ├── js/inbox.js
    └── widget/aurora-chat.js  # Widget embeddable (vanilla JS, ~15KB)
```

---

## Limitacoes conhecidas

1. **Sem Celery:** envio de webhook e sincrono (background thread)
2. **InMemoryChannelLayer em dev:** WebSocket funciona so em processo unico. Producao precisa Redis
3. **Sem upload de arquivos:** campo `arquivo_url` espera URL externa
4. **Widget sem WebSocket:** usa polling 5s. WebSocket para visitantes e enhancement futuro
5. **Sem CSAT:** pesquisa de satisfacao pos-conversa nao implementada

---

## Deploy em producao (checklist)

1. **Redis:** configurar `CHANNEL_LAYERS` com `RedisChannelLayer`
2. **Daphne:** adicionar `'daphne'` ao INSTALLED_APPS
3. **Nginx:** proxy `/ws/` → Daphne, resto → Gunicorn
4. **N8N:** workflow WhatsApp → POST `/api/v1/n8n/inbox/mensagem-recebida/`
5. **CanalInbox:** criar canal WhatsApp no admin com `webhook_envio_url`
6. **Token:** `N8N_API_TOKEN` no `.env`
7. **Widget:** configurar dominios permitidos em `/inbox/configuracoes/` aba Widget
8. **Migrate:** `python manage.py migrate inbox`
