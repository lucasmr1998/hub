# CS — Retencao (stub)

**App:** `apps/cs/retencao/`
**Status:** Stub — models criados, views/URLs pendentes

Prevencao de churn com score de saude do cliente e alertas automaticos.

> **Nota:** o CRM ja possui `AlertaRetencao` e scanner de contratos HubSoft (ver [comercial/crm/retencao.md](../comercial/crm/retencao.md)). Este modulo complementara com score de saude e acoes de retencao dedicadas.

---

## Models (3)

### ScoreCliente

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `cliente` | FK ClienteHubsoft | Cliente |
| `score` | Integer(0-100, default 50) | Score de saude |
| `fatores` | JSONField | Fatores que compoem o score |
| `ultima_atualizacao` | DateTime (auto) | Ultimo calculo |

### AlertaChurn

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `cliente` | FK ClienteHubsoft | Cliente |
| `tipo` | CharField | inadimplencia / sem_uso / reclamacao / contrato_expirando |
| `severidade` | CharField | baixa / media / alta / critica |
| `descricao` | TextField | Detalhes |
| `resolvido` | Boolean | Status |
| `data_criacao` / `data_resolucao` | DateTime | Timestamps |

### AcaoRetencao

Acao tomada para reter um cliente em risco (oferta, contato, negociacao).

---

## Status atual

Models registrados. Views, URLs e service de calculo de score vazios (TODO).

**Proximos passos:**

1. `ScoreService.calcular_score(cliente)` — agrega fatores (inadimplencia, tempo sem uso, reclamacoes abertas, NPS)
2. Cron que atualiza `ScoreCliente` de todos os clientes ativos
3. Gera `AlertaChurn` quando score cai abaixo de limiares
4. Integracao com `AlertaRetencao` do CRM (evitar duplicacao, complementar fatores)
