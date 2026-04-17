# Inbox — WebSocket (tempo real)

**Consumer:** `InboxConsumer` em `apps/inbox/consumers.py`

---

## Groups

| Group | Formato | Quem entra |
|-------|---------|------------|
| Tenant | `inbox_tenant_{tenant_id}` | Todos os agentes do tenant |
| Usuario | `inbox_user_{user_id}` | Agente especifico |
| Conversa | `inbox_conversa_{conversa_id}` | Agentes com chat aberto |

---

## Actions (cliente → servidor)

| Action | O que faz |
|--------|-----------|
| `join_conversa` | Entra no group da conversa |
| `leave_conversa` | Sai do group |
| `typing` | Broadcast typing indicator |
| `set_status` | Atualiza status (online/ausente/offline) |
| `mark_read` | Marca mensagens como lidas |

---

## Comportamento

- **Auto-offline** no `disconnect()` — se o agente fecha o navegador ou perde conexao, status vira offline
- **Fallback para polling 5s** quando WebSocket nao disponivel
- **Routing:** configurado em `apps/inbox/routing.py`

---

## Producao

Em dev, usa `InMemoryChannelLayer` (funciona so em processo unico).

Para producao e obrigatorio configurar `CHANNEL_LAYERS` com `RedisChannelLayer` e servir via Daphne com proxy Nginx para `/ws/`. Ver [README.md](README.md) checklist de deploy.
