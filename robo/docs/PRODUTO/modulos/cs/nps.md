# CS — NPS (stub)

**App:** `apps/cs/nps/`
**Status:** Stub — models criados, views/URLs pendentes

Pesquisa de satisfacao Net Promoter Score.

---

## Models (2)

### ConfiguracaoNPS (Singleton)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `periodicidade_dias` | Integer(90) | Intervalo entre pesquisas |
| `canal_envio` | CharField | whatsapp / email / ambos |
| `mensagem_template` | TextField | Template da mensagem |
| `ativo` | Boolean | Status |

### PesquisaNPS

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `cliente` | FK ClienteHubsoft | Cliente |
| `membro` | FK MembroClube | Membro (se aplicavel) |
| `nota` | Integer(0-10) | Nota NPS |
| `comentario` | TextField | Comentario livre |
| `categoria` | CharField | promotor (9-10) / neutro (7-8) / detrator (0-6) — auto-calculada |
| `canal_resposta` | CharField | whatsapp (default) |
| `data_envio` / `data_resposta` | DateTime | Timestamps |
| `respondida` | Boolean | Se respondeu |

---

## Status atual

Models registrados no admin. Views, URLs e service de envio vazios (TODO).

**Proximos passos:**

1. Service `NPSService` com metodos `enviar_pesquisa(cliente)` e `registrar_resposta(nota, comentario)`
2. Cron periodico que dispara pesquisas com base em `periodicidade_dias`
3. Views de dashboard com NPS calculado + lista de detratores
4. Integracao com [marketing/automacoes/](../marketing/automacoes/) — dispara evento `nps_respondido` ou `detrator_identificado`
