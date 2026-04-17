# CRM — Pipeline e Estagios

## Pipeline

**Tabela:** `crm_pipelines`

Configura cada funil de vendas do tenant. Um tenant pode ter varios pipelines (vendas, suporte, onboarding).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` / `slug` | CharField / Slug | Identificacao |
| `tipo` | CharField | vendas / suporte / onboarding / custom |
| `cor_hex` / `icone_fa` | Char | Visual |
| `padrao` | BooleanField | Pipeline padrao para auto-criacao |

---

## PipelineEstagio

**Tabela:** `crm_pipeline_estagios`

Cada coluna do Kanban.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `pipeline` | FK Pipeline | Pipeline pai |
| `nome` / `slug` / `ordem` | Identificacao | Ordem no Kanban |
| `tipo` | CharField | novo / qualificacao / negociacao / fechamento / cliente / retencao / perdido |
| `is_final_ganho` / `is_final_perdido` | BooleanField | Flags de encerramento |
| `probabilidade_padrao` | Integer(50) | % padrao de probabilidade |
| `sla_horas` | PositiveInteger | SLA em horas |

**SLA:** quando uma oportunidade fica no estagio por mais tempo que `sla_horas`, e marcada como vencida.

---

## HistoricoPipelineEstagio

**Tabela:** `crm_historico_estagio`

Log de cada movimentacao de estagio:

- `oportunidade` FK
- `estagio_anterior` / `estagio_novo` FK
- `movido_por` FK User
- `motivo` TextField
- `tempo_no_estagio_horas` Decimal

Usado para analise de ciclo de venda e gargalos no pipeline.
