# CRM — Retencao

## AlertaRetencao

**Tabela:** `crm_alertas_retencao`

Alertas automaticos de risco de churn, baseados em dados do HubSoft.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `cliente_hubsoft` | FK ClienteHubsoft | Cliente |
| `lead` / `oportunidade` | FK | Contexto |
| `tipo_alerta` | CharField | contrato_expirando / inadimplencia / plano_downgradado / sem_uso / reclamacao / upgrade_disponivel / aniversario_contrato |
| `nivel_risco` | CharField | baixo / medio / alto / critico |
| `score_churn` | Integer(0-100) | Score de risco |
| `status` | CharField | novo / em_tratamento / resolvido / perdido |

---

## Scanner automatico

Analisa contratos do HubSoft, cria alertas baseado em dias restantes do contrato:

| Dias restantes | Nivel | Score |
|----------------|-------|-------|
| ≤ 30 | **critico** | 90 |
| ≤ 60 | **alto** | 70 |
| ≤ 90 | **medio** | 50 |

Disparado via `api_scanner_retencao` (botao na tela `retencao.html`) ou cron periodico.

---

## Tratamento do alerta

1. Vendedor recebe notificacao
2. Abre alerta em `retencao.html` (agrupado por nivel)
3. Pode **Tratar** (`api_tratar_alerta`) — marca como em_tratamento, vincula acao
4. Resolve com **Resolver** (`api_resolver_alerta`) — marca como resolvido (cliente retido) ou perdido (churn confirmado)

---

## Tela

`retencao.html` — Alertas agrupados por nivel de risco, com filtros por tipo e status.
