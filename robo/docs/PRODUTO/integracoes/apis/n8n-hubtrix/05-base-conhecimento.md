# Hubtrix N8N API — Base de conhecimento (RAG)

Endpoints pra **agentes LLM externos** (Matrix, N8N) consultarem e alimentarem a base de conhecimento do tenant. RAG via pgvector + OpenAI embeddings.

## Stack

- **pgvector** (extension Postgres) — armazena embeddings 1536-dim
- **OpenAI text-embedding-3-small** — modelo de embedding ($0.0001/pergunta)
- **HNSW** (m=16, ef_construction=64) — indice de similaridade
- Distancia: cosseno via operador `<=>`

### Credenciais OpenAI

Cada tenant pode ter sua `IntegracaoAPI tipo=openai` ativa. Se nao tiver, usa a chave da Aurora HQ como fallback. **Sem nenhuma credencial:** endpoint retorna `artigos=[]` sem erro (bot trata como "base nao configurada").

---

## `POST /api/public/n8n/conhecimento/buscar/` — Busca semantica

Cliente pergunta `"voces tem plano de 1 giga?"` e o endpoint acha o artigo "Tabela de planos residenciais" mesmo sem string "1 giga" literal.

### Body

```json
{
  "pergunta": "qual o valor do plano 500MB?",
  "k": 5,
  "distancia_max": 0.5
}
```

| Campo | Default | Descricao |
|---|---|---|
| `pergunta` | obrig. | Texto da pergunta (>=3 chars) |
| `k` | 5 | Quantos artigos retornar (max 20) |
| `distancia_max` | 0.5 | Cutoff de similaridade (0=identico, 2=oposto) |

### Resposta

```json
{
  "status": "success",
  "encontrou": true,
  "artigos": [
    {
      "id": 12,
      "titulo": "Tabela de planos residenciais",
      "resumo": "Planos a partir de R$ 89/mes ...",
      "conteudo": "...",
      "tags": ["planos", "preco"],
      "url": "/suporte/conhecimento/artigo/tabela-planos/",
      "distancia": 0.18
    }
  ]
}
```

### Sem match

```json
{ "status": "success", "encontrou": false, "artigos": [] }
```

Ai o agente sabe que e duvida "fora da base" — deve chamar `/registrar-pergunta/` (proximo endpoint).

### Performance

<50ms p99 ate ~10k artigos por tenant. Index HNSW em `suporte_artigos_conhecimento.embedding` filtrado por `tenant_id` antes do `<=>`.

---

## `POST /api/public/n8n/conhecimento/registrar-pergunta/` — Curadoria

Quando o bot **nao consegue responder**, registra a duvida pra alimentar curadoria. As perguntas viram `PerguntaSemResposta` (tabela `suporte_perguntas_sem_resposta`). Depois um humano transforma em artigo via `/suporte/conhecimento/perguntas/`.

### Body

```json
{
  "pergunta": "qual o valor do plano 500MB?",
  "lead_id": 462,
  "conversa_id": 312
}
```

`lead_id` e `conversa_id` sao opcionais — vinculam a pergunta a um lead/conversa especifico.

### Resposta

```json
{
  "status": "success",
  "criada": true,
  "pergunta_id": 28,
  "ocorrencias": 3
}
```

### Deduplicacao

O endpoint **nao cria duplicata**: extrai o **primeiro termo significativo** (>=3 chars, fora das stop-words PT) da pergunta e busca `PerguntaSemResposta` pendente do mesmo tenant cujo texto contenha esse termo.

- Acha similar -> incrementa `ocorrencias`, retorna `criada=false`
- Nao acha -> cria nova, retorna `criada=true`

Lead/conversa sao atualizados na existente se ela ainda nao tinha.

> **Limite v1:** dedup primitivo. "quanto custa X" e "qual valor Y" nao sao detectados como similares. Em v2 (com embeddings) substituimos por similaridade semantica — mas isso e proxima iteracao.

### Erros

- `400` — `pergunta` ausente / menor que 3 chars / tenant nao resolvido
- `401` — token invalido

---

## Backfill / regeracao de embeddings

Signal `post_save` em `ArtigoConhecimento` regera embedding quando `titulo`/`conteudo`/`tags`/`resumo` mudam. Pra povoamento inicial:

```bash
python manage.py backfill_embeddings_artigos --tenant <slug>
```

---

## Fluxo do agente LLM (Vero / futuro Nuvyon)

```
1. Cliente faz pergunta na conversa
2. Bot LLM extrai a pergunta do contexto
3. POST /conhecimento/buscar/  (k=3, distancia_max=0.5)
4. Se encontrou:
     -> bot responde citando o artigo
     -> bot pode incluir link pro artigo na resposta
   Se nao encontrou:
     -> bot responde "vou consultar um especialista, ja te respondo"
     -> POST /conhecimento/registrar-pergunta/ (com lead_id + conversa_id)
     -> bot transfere pra humano OU agenda followup
```

---

## Por que pgvector e nao Pinecone/Qdrant

- Postgres ja roda
- `CREATE EXTENSION vector;` resolve
- Backup, multi-tenant, RBAC ja existem
- Volume da Nuvyon/FATEPI (~milhares de artigos por tenant) e trivial
- Migrar pra servico dedicado e trivial depois se virar gargalo

---

## Custos

- Embedding de busca: $0.0001/pergunta (text-embedding-3-small)
- Embedding de escrita (1x por artigo, no signal post_save): mesmo custo
- Total estimado pra tenant medio: < $1/mes em embeddings

LLM (gpt-4o-mini/gpt-4o) custa mais — mas isso entra no fluxo do agente, nao desses endpoints especificos.
