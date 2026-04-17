# CRM — Segmentos

## SegmentoCRM

**Tabela:** `crm_segmentos`

Segmentacao de leads/clientes com 3 modos: dinamico, manual, hibrido.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` | CharField(100) | Nome do segmento |
| `tipo` | CharField | dinamico / manual / hibrido |
| `regras_filtro` | JSONField | Regras de filtragem para segmentos dinamicos |
| `leads` | M2M via MembroSegmento | Leads do segmento |
| `cor_hex` / `icone_fa` | Char | Visual |
| `total_leads` | PositiveInteger | Cache do total |

### Regras de filtro (JSON)

```json
[
    {"campo": "origem", "operador": "igual", "valor": "whatsapp"},
    {"campo": "score_qualificacao", "operador": "maior", "valor": "7"},
    {"campo": "cidade", "operador": "contem", "valor": "Teresina"}
]
```

**Campos disponiveis:** origem, score_qualificacao, cidade, estado, bairro, valor, status_api, dias_cadastro

**Operadores:** igual, diferente, contem, maior, menor, maior_igual, menor_igual

---

## MembroSegmento

**Tabela:** `crm_membros_segmento`

Through table:

- `segmento` FK
- `lead` FK
- `adicionado_manualmente` BooleanField
- `adicionado_por` FK User

---

## Services

Arquivo: `apps/comercial/crm/services/segmentos.py`

| Funcao | O que faz |
|--------|-----------|
| `filtrar_leads_por_regras(regras, queryset)` | Aplica regras de filtro dinamico ao queryset de leads |
| `lead_atende_regras(lead, regras)` | Verifica se um lead especifico atende todas as regras (sem query) |
| `atualizar_membros_segmento(segmento)` | Sync completo: remove quem nao atende, adiciona quem atende |
| `avaliar_lead_em_segmentos(lead)` | Avalia lead em TODOS os segmentos dinamicos/hibridos do tenant |

---

## Integracao com automacoes

O signal `avaliar_segmentos_dinamicos` (post_save LeadProspecto) dispara o evento `lead_entrou_segmento` quando um lead passa a atender as regras de um segmento dinamico. Esse evento e captado por [marketing/automacoes/](../../marketing/automacoes/) para disparar campanhas.

---

## Telas

- `segmentos_lista.html` — Grid de segmentos
- `segmento_criar.html` — Criar/editar com rule builder
- `segmento_detalhe.html` — Membros + regras + opcao de disparar campanha
