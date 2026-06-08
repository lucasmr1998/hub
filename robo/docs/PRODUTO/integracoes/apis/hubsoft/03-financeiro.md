# HubSoft API — Financeiro

> A premissa antiga de que "API HubSoft nao expoe pagamento" **nao e mais verdade**. Desde H3 (paridade), Hubtrix consome 4 endpoints financeiros via `HubsoftService`. O Clube ainda acessa via banco direto por motivo historico — migracao avaliada caso a caso.

## Listar faturas do cliente

`GET /api/v1/integracao/cliente/financeiro?id_cliente=<id>` (ou `id_cliente_servico` / `cpf_cnpj`)

Retorna faturas do cliente: abertas, pagas, atrasadas, com link de boleto/Pix.

### Query params

| Param | Descricao |
|---|---|
| `id_cliente` | Filtra por cliente |
| `id_cliente_servico` | Filtra por servico |
| `cpf_cnpj` | Alternativa pra busca |
| `status` | `aberto`, `pago`, `atrasado` (opcional) |
| `data_inicio`, `data_fim` | Periodo |

### Resposta resumida

```json
{
  "status": "success",
  "faturas": [
    {
      "id_fatura": 88888,
      "id_cliente_servico": 57515,
      "valor": 99.90,
      "data_vencimento": "2026-06-10",
      "data_pagamento": null,
      "status": "aberto",
      "linha_digitavel": "...",
      "url_pdf": "https://...",
      "url_pix": "https://...",
      "qr_code_pix": "00020126..."
    }
  ]
}
```

### Service

`HubsoftService.listar_faturas_cliente(id_cliente=None, id_cliente_servico=None, cpf_cnpj=None, status=None, ...)`.

---

## Renegociacao — listar opcoes

`GET /api/v1/integracao/financeiro/renegociacao?id_fatura=<id>` (ou `id_cliente`)

Retorna opcoes de renegociacao disponiveis pra uma fatura ou cliente: parcelas, juros, descontos.

### Resposta

```json
{
  "status": "success",
  "renegociacoes": [
    {
      "id_renegociacao_opcao": 12,
      "descricao": "12x com 10% desconto",
      "parcelas": 12,
      "valor_total": 1078.92,
      "valor_parcela": 89.91,
      "desconto": 10
    }
  ]
}
```

### Service

`HubsoftService.listar_renegociacoes(id_fatura=None, id_cliente=None)`.

---

## Renegociacao — simular

`POST /api/v1/integracao/financeiro/renegociacao/simular`

Calcula valor final de uma renegociacao especifica antes de efetivar.

### Body

```json
{
  "id_fatura": 88888,
  "id_renegociacao_opcao": 12,
  "data_primeira_parcela": "2026-07-10"
}
```

### Resposta

```json
{
  "status": "success",
  "simulacao": {
    "parcelas": [
      { "numero": 1, "valor": 89.91, "vencimento": "2026-07-10" },
      { "numero": 2, "valor": 89.91, "vencimento": "2026-08-10" }
    ],
    "valor_total": 1078.92,
    "valor_economia": 119.88
  }
}
```

### Service

`HubsoftService.simular_renegociacao(id_fatura, id_renegociacao_opcao, data_primeira_parcela=None)`.

---

## Renegociacao — efetivar

`POST /api/v1/integracao/financeiro/renegociacao/efetivar`

Aplica a renegociacao. **Acao destrutiva** — gera novas faturas, cancela a antiga. Precisa confirmacao na UI antes.

### Body

```json
{
  "id_fatura": 88888,
  "id_renegociacao_opcao": 12,
  "data_primeira_parcela": "2026-07-10",
  "id_meio_pagamento": 3
}
```

### Resposta

```json
{
  "status": "success",
  "renegociacao": {
    "id_renegociacao": 555,
    "faturas_geradas": [88891, 88892, 88893]
  }
}
```

### Service

`HubsoftService.efetivar_renegociacao(id_fatura, id_renegociacao_opcao, data_primeira_parcela, id_meio_pagamento)`.

---

## Sandbox (UI)

Em `/configuracoes/integracoes/<pk>/` aba **Sandbox** o admin pode testar essas 4 chamadas sem efeito colateral (exceto `efetivar` que tem `confirm()` JS antes de disparar). Util pra validar credenciais sem precisar de cliente real abrir um caso.

---

## Por que o Clube usa banco direto e nao a API

A API REST agora cobre faturas + renegociacao (H3), mas o Clube de Beneficios da Megalink ja estava implementado contra o banco PostgreSQL HubSoft antes. Migracao pendente — ver "Debitos tecnicos" em [../../01-HUBSOFT.md](../../01-HUBSOFT.md#debitos-tecnicos).
