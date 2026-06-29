# Marketing

**Status:** Em desenvolvimento
**App:** `apps/marketing/`

Cobre campanhas de trafego pago com deteccao automatica por palavra-chave, segmentacao dinamica de leads e envio outbound (email/WhatsApp). A automacao por regras saiu do escopo do modulo: o motor antigo `apps/marketing/automacoes/` (editor Drawflow) foi **aposentado em 29/06/2026** e substituido pela engine unificada estilo n8n em [../automacao/README.md](../automacao/README.md). Os sub-apps remanescentes se integram via signals, services e disparo de eventos pra engine unificada.

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
| [marketing-suite.md](marketing-suite.md) | — | **Visao integrada** de todos os sub-apps (capta → nutri → converte → atribui) |
| [campanhas.md](campanhas.md) | `campanhas/` | Campanhas de trafego + deteccao automatica por palavra-chave |
| [segmentos.md](segmentos.md) | (`crm/` + URLs `marketing/`) | Agrupamento dinamico de leads |
| ~~automacoes/~~ | ~~`automacoes/`~~ | ❌ **APOSENTADO (29/06/2026)**. Substituido pela engine unificada, ver [../automacao/README.md](../automacao/README.md) |
| [emails-dominios-remetentes.md](emails-dominios-remetentes.md) | `emails/` | Dominios de envio (DNS Resend SPF/DKIM/DMARC), remetentes, webhook |
| [emails-templates-renderer.md](emails-templates-renderer.md) | `emails/` | Editor visual de blocos + renderer JSON→HTML (12 tipos de bloco) |
| [landing-pages.md](landing-pages.md) | `landing_pages/` (futuro) | 📋 Discovery — plano de implementacao de LP por tenant |

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
| ~~**Drawflow.js**~~ | ~~Editor visual de fluxo~~ (❌ aposentado 29/06/2026; editor migrou pra engine unificada, React Flow) | (n/a) |
| **Chart.js** | Grafico de execucoes no dashboard | CDN |

---

## Estatisticas

| Metrica | Valor |
|---------|-------|
| Sub-apps | 3 (campanhas, segmentos, emails) + 1 planejado (landing_pages); automacoes aposentado 29/06/2026 |
| Models | 9 (2 campanhas + 2 segmentos + 5 emails); +7 de automacoes dropados 29/06/2026 |
| Views | 22 funcoes |
| Templates | 9 |
| APIs | 22 endpoints |
| Signals | 6 |
| Testes | campanhas + emails + segmentos (test_automacoes.py aposentado 29/06/2026) |

---

## Stack

TenantMixin (multi-tenancy), Django 5.2, DRF, PostgreSQL, Drawflow.js.
