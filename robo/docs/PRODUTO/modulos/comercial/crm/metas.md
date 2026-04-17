# CRM — Metas

## MetaVendas

**Tabela:** `crm_metas_vendas`

Metas individuais ou de equipe, com periodicidade configuravel.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `tipo` | CharField | individual / equipe |
| `vendedor` / `equipe` | FK | Quem tem a meta |
| `periodo` | CharField | diario / semanal / mensal / trimestral |
| `data_inicio` / `data_fim` | DateField | Periodo |
| `meta_vendas_quantidade` | Numerico | Meta de qtd de vendas |
| `meta_vendas_valor` | Decimal | Meta de valor total |
| `meta_leads_qualificados` | Integer | Meta de leads qualificados |
| `meta_contatos` | Integer | Meta de contatos |
| `realizado_vendas_quantidade` / `realizado_vendas_valor` / `realizado_leads` | Numericos | Realizado (atualizado por tasks) |

---

## Propriedades calculadas

- `percentual_quantidade` = realizado_vendas_quantidade / meta_vendas_quantidade
- `percentual_valor` = realizado_vendas_valor / meta_vendas_valor

Usadas na tela `metas.html` para barras de progresso.

---

## Views

| View | Descricao |
|------|-----------|
| `metas_view` | Lista de metas (ativas + arquivadas) |
| `api_meta_salvar` | Criar/atualizar meta |
| `api_meta_criar` | Atalho para criar |
| `api_meta_excluir` | Deletar meta |
