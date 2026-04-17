# Marketing — Segmentos

**URLs em:** `apps/marketing/segmentos_urls.py`
**Model e services em:** `apps/comercial/crm/`

Agrupa leads por criterios dinamicos, manuais ou hibridos. Os segmentos sao a ponte entre o CRM e as automacoes: permitem disparo em massa, preview em tempo real das regras, e avaliacao automatica quando um lead muda. Segmentos ficam no contexto de Marketing (URLs `/marketing/segmentos/`) mas o model vive no CRM.

Detalhes do model `SegmentoCRM`, `MembroSegmento` e services estao em [comercial/crm/segmentos.md](../comercial/crm/segmentos.md) — este arquivo documenta o **contexto Marketing** (URLs, rule builder, disparo em massa).

---

## Formato das regras de filtro (JSON)

```json
{
    "regras": [
        {"campo": "origem", "operador": "igual", "valor": "whatsapp"},
        {"campo": "score_qualificacao", "operador": "maior", "valor": "7"},
        {"campo": "cidade", "operador": "contem", "valor": "Teresina"},
        {"campo": "dias_cadastro", "operador": "menor", "valor": "30"}
    ]
}
```

**Campos disponiveis:** origem, score_qualificacao, cidade, estado, bairro, valor, status_api, dias_cadastro
**Operadores:** igual, diferente, contem, maior, menor, maior_igual, menor_igual

---

## APIs (7 endpoints)

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/marketing/segmentos/` | GET | Lista de segmentos (grid de cards) |
| `/marketing/segmentos/criar/` | GET | Pagina de criacao com rule builder |
| `/marketing/segmentos/<pk>/` | GET | Detalhe com membros |
| `/marketing/segmentos/<pk>/editar/` | GET | Edicao com regras |
| `/marketing/segmentos/salvar/` | POST | Salvar segmento (API JSON) |
| `/marketing/segmentos/preview/` | POST | Preview em tempo real (retorna count + amostra) |
| `/marketing/segmentos/<pk>/buscar-leads/` | GET | Buscar leads para adicionar manualmente |
| `/marketing/segmentos/<pk>/adicionar-lead/` | POST | Adicionar lead manualmente |
| `/marketing/segmentos/<pk>/remover-membro/` | POST | Remover membro |
| `/marketing/segmentos/<pk>/disparar-campanha/` | POST | Disparo em massa para leads do segmento |

---

## Signal

**`avaliar_segmentos_dinamicos`** (post_save LeadProspecto):

- Chama `avaliar_lead_em_segmentos()` a cada save de lead
- Para cada segmento que o lead entrou: dispara evento `lead_entrou_segmento` para o engine de automacoes
- Contexto inclui: lead, lead_nome, telefone, segmento, segmento_nome

---

## Templates (3)

| Template | Descricao |
|----------|-----------|
| `segmentos_lista.html` | Grid de cards (nome, tipo badge, total_leads, icone, cor) |
| `segmento_criar.html` | Formulario com builder de regras dinamicas (campo + operador + valor) e preview em tempo real |
| `segmento_detalhe.html` | Lista de membros com acoes (adicionar, remover, disparar campanha) |

---

## Disparo em massa

Ao clicar "Disparar Campanha" na tela do segmento:

1. Lista leads ativos do segmento
2. Chama `engine.disparar_evento('disparo_segmento', contexto_por_lead, tenant)` para cada um
3. O engine processa cada lead na automacao vinculada (se houver)

Ver [automacoes/](automacoes/) para como configurar a regra que consome esse evento.
