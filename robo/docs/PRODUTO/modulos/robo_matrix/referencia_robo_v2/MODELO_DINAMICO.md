# 🌊 Modelo Dinâmico — `/conversar`

Em vez de um flow.json com **538 nós** representando cada etapa, o Matrix vira **mínimo** (6 nós): só recebe mensagem, manda pra API, e exibe a resposta. **A API IA Validação controla 100% do fluxo** lendo o YAML.

## Comparação

| | Modelo antigo (N8N) | Modelo `/validar` | Modelo `/conversar` (este) |
|---|---|---|---|
| Nós no flow.json | 538 | 538 | ~6 |
| Onde fica a lógica | flow.json | YAML + flow.json | YAML + Python |
| Alterar pergunta de uma etapa | Editar flow.json + reimportar | Editar YAML (hot-reload) | Editar YAML (hot-reload) |
| Adicionar etapa nova | Criar 5+ nodes, conectar | Adicionar bloco no YAML | Adicionar bloco no YAML |
| Mudar persona / tom | Editar mensagens hardcoded | Editar prompts.py | Editar prompts.py |
| Custo OpenAI | — | Mesmo | Mesmo |
| Robustez a falha de etapa | Baixa (fluxo trava) | Média | Alta (API decide) |

## Endpoint

```http
POST https://robovendas.megalinkpiaui.com.br/ia/conversar
Content-Type: application/json

{
  "telefone": "5586999999999",
  "mensagem": "oi quero internet"
}
```

Resposta:

```json
{
  "mensagem_bot": "Que bom que você quer contratar! Em qual cidade você mora?",
  "proxima_etapa": "coleta_cidade",
  "etapa_anterior": "cumprimento",
  "fim_fluxo": false,
  "transbordo_humano": false,
  "intencao": "contratar",
  "dados_extraidos": {},
  "tentativas": 0,
  "usou_ia": true
}
```

A API:
1. Lê a `etapa_atual` do telefone (do contexto persistido).
2. Valida a `mensagem` na etapa atual (extractor local → OpenAI fallback).
3. Anexa a pergunta da próxima etapa na `mensagem_bot` pra fluir natural.
4. Persiste a nova etapa pra próxima chamada.
5. Sincroniza dados extraídos com o Django em background.

## Fluxo Matrix mínimo (6 nós)

```
┌─────────┐   ┌──────────┐   ┌────────────────────┐   ┌──────┐
│ início  │ → │ sol_loop │ → │ api: POST /conversar│ → │ dec  │
└─────────┘   │ aguarda  │   │ body: {telefone,    │   └──┬───┘
              │ mensagem │   │   mensagem}         │      │
              │ do user  │   │ store: $.*          │      │
              └──────────┘   └─────────────────────┘      │
                  ↑                                       │
                  │     ┌────────────────────────────┐    │
                  └─────│ msg: {#mensagem_bot}       │←───┤ default
                        └────────────────────────────┘    │
                                                          │
                  ┌────────────────────────────┐          │
                  │ msg: {#mensagem_bot} + fin │←─────────┤ fim_fluxo = true
                  └────────────────────────────┘          │
                                                          │
                  ┌────────────────────────────┐          │
                  │ msg: {#mensagem_bot} + ser │←─────────┘ transbordo_humano = true
                  └────────────────────────────┘
```

## Variáveis Matrix que o nó API precisa

Configure no nó **api** o `store/filter=1` com:

| Variável Matrix (criar) | JSONPath retornado |
|---|---|
| `{#mensagem_bot}` | `$.mensagem_bot` |
| `{#fim_fluxo}` | `$.fim_fluxo` |
| `{#transbordo}` | `$.transbordo_humano` |
| `{#intencao}` | `$.intencao` |

## Como montar no editor Matrix

1. **Crie um fluxo novo** (não modifica o atual).
2. **Node 1 — set var** `var_endpoint`:
   - `url_ia` = `https://robovendas.megalinkpiaui.com.br/ia/conversar`
3. **Node 2 — sol** `sol_loop`:
   - `update_db` = 0
   - timeout = `{#tempo_de_inatividade}`
   - **Conectado a si mesmo no fim** (loop)
4. **Node 3 — api** `api_conversar`:
   - URL: `{#url_ia}`
   - método: POST
   - timeout: 30s
   - headers: `Content-Type: application/json`
   - body:
     ```json
     {
       "telefone": "{#CONTATO.TELEFONE}",
       "mensagem": "{#MENSAGEM}"
     }
     ```
   - store/filter: 1
     - var `mensagem_bot` ← `mensagem_bot`
     - var `fim_fluxo` ← `fim_fluxo`
     - var `transbordo` ← `transbordo_humano`
5. **Node 4 — msg** `msg_bot`:
   - texto: `{#mensagem_bot}`
6. **Node 5 — dec** `dec_destino`:
   - condição 1 (`fim_fluxo == "true"`) → **fin**
   - condição 2 (`transbordo == "true"`) → **ser** (transbordo humano)
   - default → volta pro `sol_loop`

Pronto. 5-6 nós, ~30 minutos de trabalho no editor visual.

## Vantagens operacionais

- **Tempo pra adicionar uma pergunta nova**: 30 segundos (editar [fluxos/vendas_megalink.yaml](../fluxos/vendas_megalink.yaml) + hot-reload).
- **Tempo pra mudar tom da Aurora**: 1 minuto (editar [src/ia/prompts.py](../src/ia/prompts.py) + `systemctl restart`).
- **Tempo pra criar fluxo novo** (ex: suporte, retenção): copiar YAML, editar etapas, sem mexer no Matrix.
- **A/B testing de prompts**: troca `PERSONA_SYSTEM` por feature flag → 2 variantes da Aurora rodando em paralelo.

## Fallback

Caso o endpoint `/conversar` esteja fora do ar, basta o fluxo Matrix antigo continuar respondendo pelos webhooks já configurados em [flow_megalink_v2.json](../fluxos/flow_megalink_v2.json) — a API IA Validação suporta os 3 modos:
- `/validar` (com `etapa` explícita)
- `/validar/matrix` (compatibilidade N8N)
- `/conversar` (dinâmico — recomendado)
