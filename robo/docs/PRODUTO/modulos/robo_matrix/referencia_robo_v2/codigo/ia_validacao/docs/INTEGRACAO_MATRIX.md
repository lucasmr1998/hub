# 🔗 Integração com Matrix

## Substituir webhook N8N

No arquivo `flow.json` do Matrix, encontre os 2 nós de API:

### `api_15` (webhook geral)
**Antes:**
```
URL: https://automation-n8n.v4riem.easypanel.host/webhook/matrix
Body: {"atendimento_id": "1", "answer": "oi", "telefone": "{#CONTATO.TELEFONE}"}
```

**Depois:**
```
URL: {#url_ia_validacao}/validar/matrix
Body: {"question": "oi", "answer": "{#resposta_cliente}", "telefone": "{#CONTATO.TELEFONE}"}
```

### `api_16` (DynamicValidator)
**Antes:**
```
URL: https://automation-n8n.v4riem.easypanel.host/webhook/...DynamicValidator
Body: {"question": "{#pergunta_cliente}", "answer": "{#resposta_cliente}", "telefone": "{#CONTATO.TELEFONE}"}
```

**Depois:**
```
URL: {#url_ia_validacao}/validar
Body: {
  "telefone": "{#CONTATO.TELEFONE}",
  "etapa": "{#etapa_atual}",
  "pergunta": "{#pergunta_cliente}",
  "resposta": "{#resposta_cliente}",
  "fluxo": "vendas_megalink"
}
```

## Configurar `store` para capturar resposta

No nó da API no Matrix, configure o **store/filter** para extrair os campos da resposta JSON:

| Variável Matrix | JSONPath |
|-----------------|----------|
| `{#resposta_valida}` | `$.valido` |
| `{#mensagem_bot}` | `$.mensagem_bot` |
| `{#proxima_etapa}` | `$.proxima_etapa` |
| `{#intencao}` | `$.intencao_detectada` |
| `{#cpf_extraido}` | `$.dados_extraidos.cpf` |
| `{#cidade_extraida}` | `$.dados_extraidos.cidade` |
| `{#tentativas}` | `$.tentativas` |

## Decisões pós-API

Após a chamada à API, use um **nó de decisão (dec)** no Matrix:

```
SE resposta_valida == true:
  → seguir para o próximo nó (ex: msg do bot com {#mensagem_bot})
SENÃO SE proxima_etapa == "transbordo_humano":
  → componente ser_1 (transbordo)
SENÃO:
  → repetir pergunta com {#mensagem_bot}
```

## Variáveis a criar no Matrix

| Nome | Tipo | Descrição |
|------|------|-----------|
| `url_ia_validacao` | URL | Ex: `https://robovendas.megalinkpiaui.com.br:8090` |
| `etapa_atual` | string | ID da etapa do fluxo (preencher em cada `sol_*`) |
| `pergunta_cliente` | string | Já existe |
| `resposta_cliente` | string | Já existe |
| `resposta_valida` | bool | Captura `$.valido` |
| `mensagem_bot` | string | Captura `$.mensagem_bot` |
| `proxima_etapa` | string | Captura `$.proxima_etapa` |
| `intencao` | string | Captura `$.intencao_detectada` |

## Fluxo recomendado de cada etapa

```
[msg do bot: "Qual seu CPF?"]
  ↓
[set: etapa_atual = "coleta_cpf"]
  ↓
[sol: aguardar resposta → resposta_cliente]
  ↓
[api: POST /validar com {etapa, resposta, telefone}]
  ↓
[dec: resposta_valida?]
  ↓ sim                    ↓ não
[msg bot: mensagem_bot]    [msg bot: mensagem_bot]
[red: proxima_etapa]       [voltar ao sol]
```

## Ambiente de teste

Para testar sem afetar produção:
1. Faça uma cópia do `flow.json` → `flow_teste_ia.json`
2. Modifique apenas os 2 webhooks
3. Importe no Matrix como fluxo separado
4. Configure um número de teste apontando para esse fluxo
5. Quando estiver estável, substitua o fluxo principal

## Rollback

Se algo der errado, basta reverter as 2 URLs para o N8N anterior. Os dados extraídos ficam no nosso banco (PostgreSQL via Robo Vendas) e não no Matrix.
