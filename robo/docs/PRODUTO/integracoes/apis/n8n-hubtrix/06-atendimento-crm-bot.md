# Hubtrix N8N API — Telemetria de atendimento e CRM (bot)

Endpoints pra **agentes/bots externos** registrarem fricao de atendimento e classificar resultado de oportunidade.

## `POST /api/public/n8n/atendimento/registrar-erro-resposta/`

Captura **fricao no fluxo da maquina de estados do bot** — bot perguntou X, cliente respondeu Y errado. Alimenta calibracao do fluxo (copy, validacao, exemplos).

Distinto de `/conhecimento/registrar-pergunta/` (que captura **duvida livre** do cliente, lacuna na base de conhecimento). Aqui e **resposta errada num node especifico**.

### Modelo

`MotivoErroResposta` em `apps.comercial.atendimento`. Substitui o INSERT direto na tabela externa `motivo-erro` (Postgres `atendimento-ai`) que os flows antigos do Matrix usam. Migrar pra ca centraliza no Hubtrix (multi-tenant, painel, metricas).

### Body

```json
{
  "pergunta_bot": "qual seu CPF?",
  "resposta_cliente": "12345",
  "no_fluxo": "ColetaCPF",
  "canal": "whatsapp",
  "lead_id": 462,
  "conversa_id": 312
}
```

| Campo | Obrig. | Descricao |
|---|---|---|
| `pergunta_bot` | sim | Pergunta que o bot fez |
| `resposta_cliente` | sim | O que o cliente respondeu (errado) |
| `no_fluxo` | nao | Nome/slug do node do bot (ex.: `ColetaCPF`, `EscolheCidade`) |
| `canal` | nao | `whatsapp`, `sms`, etc — origem |
| `lead_id` | nao | Vincular a lead |
| `conversa_id` | nao | Vincular a conversa |

### Resposta

```json
{
  "status": "success",
  "criada": true,
  "erro_id": 17,
  "ocorrencias": 1
}
```

### Deduplicacao

Combinacao **exata** (case-insensitive, whitespace trimado) de `(pergunta_bot, resposta_cliente, no_fluxo?)` no mesmo tenant, com `resolvido=False`. Mesma combinacao volta -> incrementa `ocorrencias`. Como as strings sao curtas e estruturadas (pergunta vem do bot, resposta e curta), match exato e o criterio certo aqui.

### Erros

- `400` — `pergunta_bot` ou `resposta_cliente` ausentes/vazios
- `401` — token invalido

### Uso no Vero

Sempre que `ValidarImagemRGFrente/Verso/Outro` retorna `valido=false` ou que um node de coleta nao consegue parsear a resposta:

```
Node ColetaCPF -> recebe "12345"
1. POST /atendimento/registrar-erro-resposta/ com pergunta="qual seu CPF?", resposta="12345", no_fluxo="ColetaCPF"
2. Bot responde "Hmm, isso nao parece um CPF. Pode mandar denovo com 11 digitos?"
```

### Onde ver os erros

Painel `/atendimento/erros-resposta/` (a construir) — lista agrupada por `(pergunta_bot, no_fluxo)` ordenada por `ocorrencias desc`. Permite copy editor refinar perguntas com mais friccao.

---

## Encerrar oportunidade com motivo classificado

Documentado em [02-crm.md#encerrar-oportunidade-com-motivo-botautomacao](02-crm.md#encerrar-oportunidade-com-motivo-botautomacao). Mesmo endpoint serve a esse contexto (bot LLM detectando perda e classificando motivo).

Resumo: `POST /api/public/n8n/crm/oportunidade/<pk>/encerrar-com-motivo/` recebe `ultima_mensagem_cliente`, classifica via gpt-4o-mini contra `MotivoPerda` ativos do tenant, move oportunidade pra estagio `is_final_perdido`.

---

## Quando usar cada um

| Sinal | Endpoint |
|---|---|
| Bot perguntou algo no fluxo, cliente respondeu errado | `/atendimento/registrar-erro-resposta/` |
| Cliente fez uma pergunta livre que o bot nao soube responder | `/conhecimento/registrar-pergunta/` |
| Conversa terminou e cliente nao fechou (motivos: preco, sem cobertura, mudou de ideia) | `/crm/oportunidade/<pk>/encerrar-com-motivo/` |
| Cliente passou de estagio com sucesso | `PUT /api/v1/n8n/crm/oportunidades/<id>/` com novo `estagio_slug` |

---

## Visao consolidada: o que o bot externo precisa saber

```
ANTES de responder:
1. /conhecimento/buscar/  -> tem artigo? usa
2. /leads/buscar/?telefone=...  -> tem lead? recupera
3. /crm/oportunidades/buscar/?lead_id=...  -> tem oportunidade?

DURANTE a conversa:
1. POST /inbox/mensagem-recebida/  (cliente mandou)
2. POST /inbox/enviar/             (bot vai responder)
3. PUT /leads/<id>/                (IA extraiu campos)
4. PUT /crm/oportunidades/<id>/    (mover estagio)
5. /conhecimento/registrar-pergunta/  (se nao soube responder)
6. /atendimento/registrar-erro-resposta/  (se cliente respondeu errado num node)

FIM:
1. /crm/oportunidade/<pk>/encerrar-com-motivo/  (perdeu)
   OU
   PUT /crm/oportunidades/<id>/ com estagio is_final_ganho  (ganhou)
```
