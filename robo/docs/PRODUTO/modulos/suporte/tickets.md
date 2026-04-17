# Suporte — Tickets

**App:** `apps/suporte/`

---

## Models (4)

### CategoriaTicket

**Tabela:** `suporte_categorias` | **Unique:** `(tenant, slug)`

Categorias de tickets com nome, slug, icone FontAwesome, ordem.

### SLAConfig

**Tabela:** `suporte_sla_config` | **Unique:** `(tenant, plano_tier)`

SLA por plano (starter/start/pro): tempo de primeira resposta e resolucao em horas.

### Ticket

**Tabela:** `suporte_tickets` | **Unique:** `(tenant, numero)`

| Grupo | Campos |
|-------|--------|
| **Identificacao** | numero (auto), titulo, descricao |
| **Classificacao** | categoria FK, prioridade, status (aberto / em_andamento / aguardando_cliente / resolvido / fechado) |
| **Pessoas** | solicitante FK User, atendente FK User |
| **SLA** | sla_horas (auto do SLAConfig), sla_cumprido (property) |
| **Timestamps** | data_abertura, data_primeira_resposta, data_resolucao, data_fechamento |
| **Provedor** | tenant_cliente FK Tenant |

### ComentarioTicket

Timeline do ticket:

- `autor` FK User
- `mensagem` TextField
- `interno` BooleanField — flag para visibilidade staff-only (comentarios internos nao aparecem para o cliente)

---

## Views (4)

| View | Rota | Descricao |
|------|------|-----------|
| `dashboard_suporte` | `/suporte/` | Dashboard KPIs (abertos, em andamento, aguardando, resolvidos, SLA breach) |
| `ticket_lista` | `/suporte/tickets/` | Lista com filtros (status, prioridade, categoria, busca) |
| `ticket_criar` | `/suporte/tickets/criar/` | Formulario de criacao |
| `ticket_detalhe` | `/suporte/tickets/<pk>/` | Detalhe com timeline, comentarios, acoes (alterar status, atribuir, comentar interno/publico) |

---

## Fluxo de vida do ticket

```
ABERTO ──atribuir──▶ EM ANDAMENTO ──resolver──▶ RESOLVIDO ──fechar──▶ FECHADO
   │                      │
   └──aguardar──▶ AGUARDANDO CLIENTE ──responder──┘
```

---

## SLA

Quando um ticket e criado, o sistema busca o `SLAConfig` para o plano do tenant do solicitante e define `sla_horas` automaticamente. A property `sla_cumprido` avalia se `data_resolucao - data_abertura <= sla_horas`.

Dashboard destaca tickets com SLA breach (em andamento ha mais tempo que o SLA permite).
