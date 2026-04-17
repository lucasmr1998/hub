# Suporte

**Status:** Em producao
**App:** `apps/suporte/`

Tickets de suporte com SLA configuravel por plano. Integrado ao Inbox — cada conversa pode virar ticket.

---

## Indice

| Arquivo | Conteudo |
|---------|----------|
| [tickets.md](tickets.md) | 4 models + views + fluxo de vida do ticket |

---

## Integracao com Inbox

```
Conversa (Inbox) ──FK──▶ Ticket (Suporte)
    │
    └── api_criar_ticket: cria ticket com ultimas 10 mensagens como descricao
        herda prioridade da conversa
        cria mensagem de sistema "Ticket #N criado"
```

Detalhes do lado Inbox em [inbox/services.md](../inbox/services.md#funcoes-principais).

---

## Fluxos completos

### Mensagem WhatsApp → Inbox → Ticket

```
1. Cliente envia WhatsApp
2. Uazapi recebe → POST webhook
3. Inbox services.receber_mensagem() cria Conversa
4. Agente abre conversa e cria Ticket (api_criar_ticket)
5. Timeline do ticket herda as 10 ultimas mensagens
```

### Widget → Inbox → Ticket

```
1. Visitante usa widget no site do provedor
2. Conversa aparece no Inbox do agente
3. Se agente classifica como suporte, cria Ticket
```

Detalhes dos fluxos Inbox em [inbox/apis.md](../inbox/apis.md) e [inbox/widget-chat.md](../inbox/widget-chat.md).

---

## Estatisticas

| Metrica | Valor |
|---------|-------|
| Models | 4 (CategoriaTicket, SLAConfig, Ticket, ComentarioTicket) |
| Views | 4 (dashboard, lista, criar, detalhe) |
| Templates | 4 |

Para detalhes completos, ver [tickets.md](tickets.md).
