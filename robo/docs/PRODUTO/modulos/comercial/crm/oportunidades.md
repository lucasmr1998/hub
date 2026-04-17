# CRM — Oportunidades

## OportunidadeVenda

**Tabela:** `crm_oportunidades`

Entidade central do CRM. Cada lead qualificado tem uma oportunidade (1:1).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `pipeline` | FK Pipeline | Pipeline |
| `lead` | OneToOne LeadProspecto | Lead (1:1) |
| `estagio` | FK PipelineEstagio | Estagio atual |
| `responsavel` | FK User | Vendedor responsavel |
| `titulo` | CharField(255) | Titulo da oportunidade |
| `valor_estimado` | Decimal(12,2) | Valor estimado |
| `probabilidade` | Integer(50) | % de probabilidade |
| `prioridade` | CharField | baixa / normal / alta / urgente |
| `tags` | M2M TagCRM | Tags visuais |
| `plano_interesse` | FK PlanoInternet | Plano de interesse (legado, usar itens) |
| `origem_crm` | CharField | automatico / manual / importacao |
| `data_entrada_estagio` | DateTime | Para calculo de SLA |
| `motivo_perda` / `concorrente_perdido` | Text / Char | Se perdeu |
| `contrato_hubsoft_id` | CharField(100) | ID do contrato no HubSoft |
| `churn_risk_score` | Integer(0-100) | Score de risco de churn |

**Propriedades:** `dias_no_estagio`, `sla_vencido`, `valor_total_itens`
**Metodos:** `recalcular_valor()` — atualiza `valor_estimado` com soma dos itens

**Indices:** `(estagio, ativo)`, `(responsavel, estagio)`, `(data_fechamento_previsto)`, `(churn_risk_score)`

---

## ItemOportunidade

**Tabela:** `crm_itens_oportunidade`

Vincula produtos a oportunidades (N:N com quantidade e valor).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `oportunidade` | FK OportunidadeVenda | Oportunidade |
| `produto` | FK ProdutoServico | Produto/Servico |
| `quantidade` | PositiveInteger | Quantidade |
| `valor_unitario` | Decimal(10,2) | Valor unitario |
| `desconto` | Decimal(10,2) | Desconto |
| `observacao` | CharField(255) | Observacao |

**Propriedade:** `subtotal = (quantidade * valor_unitario) - desconto`

---

## Ciclo de vida

```
Lead criado (score >= 7)
    ↓
  signal auto-cria OportunidadeVenda no pipeline_padrao/estagio_inicial
    ↓
  Vendedor atribui responsavel, adiciona itens, move entre estagios
    ↓
  Chega em estagio com is_final_ganho=True
    ↓
  Envia webhook para N8N → HubSoft cria contrato
    ↓
  webhook_hubsoft_contrato retorna → preenche contrato_hubsoft_id
```

Ver [oportunidade_detalhe.html](oportunidade_detalhe) e [pipeline.html](pipeline) para as telas correspondentes.
