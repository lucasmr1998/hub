# Marketing

**Status:** Em desenvolvimento
**App:** `apps/marketing/`

Motor de automacao e inteligencia do hub. Cobre campanhas de trafego pago com deteccao automatica por palavra-chave, segmentacao dinamica de leads e automacoes visuais com editor de fluxo (Drawflow). Composto por 3 sub-apps que se integram via signals, services e o engine de execucao.

```
Lead chega (WhatsApp/Site/Instagram)
    │
    ▼
┌────────────┐     ┌────────────┐     ┌────────────────┐
│ CAMPANHAS  │────▶│ SEGMENTOS  │────▶│  AUTOMACOES    │
│ Deteccao   │     │ Agrupamento│     │  Editor Visual │
│ Atribuicao │     │ Regras     │     │  Engine BFS    │
│ ROI        │     │ Preview    │     │  Acoes + Delay │
└────────────┘     └────────────┘     └────────────────┘
       │                  │                    │
       ▼                  ▼                    ▼
   N8N / API        Disparo massa        WhatsApp, Email,
   Deteccao         Avaliacao auto       CRM, Pontos, Webhook
```

---

## Indice

| Arquivo | Sub-app | Descricao |
|---------|---------|-----------|
| [campanhas.md](campanhas.md) | `campanhas/` | Campanhas de trafego + deteccao automatica por palavra-chave |
| [segmentos.md](segmentos.md) | (`crm/` + URLs `marketing/`) | Agrupamento dinamico de leads |
| [automacoes/](automacoes/) | `automacoes/` | Engine completo de automacoes + editor visual |

---

## Integracoes entre submodulos

```
Campanhas ──deteccao──▶ Leads (campanha_origem FK)
Campanhas ──N8N API──▶ N8N (mensagem recebida → detecta campanha)
Segmentos ──signal──▶ Automacoes (lead_entrou_segmento)
Segmentos ──service──▶ Leads (filtrar, avaliar, atualizar membros)
Automacoes ──signal──▶ Leads (lead_criado, lead_qualificado)
Automacoes ──signal──▶ CRM (oportunidade_movida, tarefa_vencida)
Automacoes ──signal──▶ CS (indicacao_convertida)
Automacoes ──acao──▶ WhatsApp (via N8N webhook)
Automacoes ──acao──▶ CRM (criar_tarefa, mover_estagio)
Automacoes ──acao──▶ CS/Clube (dar_pontos)
Automacoes ──cron──▶ ExecucaoPendente (delays, temporal events)
Automacoes ──timeline──▶ CRM/Lead (api_lead_timeline)
```

---

## Dependencias externas

| Servico | Uso | Integracao |
|---------|-----|------------|
| **N8N** | Envio de WhatsApp e e-mail, deteccao de campanha | Webhook POST |
| **Drawflow.js** | Editor visual de fluxo | CDN v0.0.59 |
| **Chart.js** | Grafico de execucoes no dashboard | CDN |

---

## Estatisticas

| Metrica | Valor |
|---------|-------|
| Sub-apps | 3 (campanhas, automacoes, segmentos) |
| Models | 11 (2 campanhas + 7 automacoes + 2 segmentos) |
| Views | 22 funcoes |
| Templates | 9 |
| APIs | 22 endpoints |
| Signals | 6 |
| Testes | 60+ (test_automacoes.py) |

---

## Stack

TenantMixin (multi-tenancy), Django 5.2, DRF, PostgreSQL, Drawflow.js.
