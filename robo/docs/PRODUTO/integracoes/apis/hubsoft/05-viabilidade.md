# HubSoft API — Viabilidade

Consulta se ha cobertura de rede para um endereco. Usado pelo bot Vero (TR Carrion) e por leads vindo do site/WhatsApp pra **filtrar leads fora da area de atendimento antes mesmo de mandar pra fila**.

## Consultar por endereco

`POST /api/v1/integracao/mapeamento/viabilidade/consultar`

### Body

```json
{
  "cep": "64000000",
  "logradouro": "Av. Frei Serafim",
  "numero": "1234",
  "bairro": "Centro",
  "cidade": "Teresina",
  "uf": "PI"
}
```

### Resposta

```json
{
  "status": "success",
  "viabilidade": {
    "atende": true,
    "tipo_atendimento": "fibra",
    "planos_disponiveis": [
      { "id_plano": 12, "nome": "500MB", "valor": 99.90 },
      { "id_plano": 13, "nome": "1GB", "valor": 149.90 }
    ],
    "obs": "Atendimento disponivel imediato"
  }
}
```

### Resposta sem cobertura

```json
{
  "status": "success",
  "viabilidade": {
    "atende": false,
    "motivo": "Endereco fora da area de cobertura"
  }
}
```

### Service

`HubsoftService.consultar_viabilidade_endereco(cep, logradouro, numero, bairro, cidade, uf)`.

---

## Consultar por coordenadas (lat/lng)

`POST /api/v1/integracao/mapeamento/viabilidade/consultar`

Mesmo endpoint, mas body com `lat`/`lng` em vez de endereco. Util quando o lead compartilha localizacao no WhatsApp.

```json
{
  "lat": -5.0892,
  "lng": -42.8016
}
```

### Service

`HubsoftService.consultar_viabilidade_coords(lat, lng)`.

---

## Wrapper Hubtrix pro N8N

`POST /api/public/n8n/viabilidade/` (ver [../n8n-hubtrix/05-base-conhecimento.md](../n8n-hubtrix/) e doc legada [../../03-APIS_N8N.md](../../03-APIS_N8N.md))

Usado pelo Vero (TR Carrion) — quando lead informa CEP + numero, o bot chama esse endpoint antes de prosseguir com qualificacao.

---

## Fluxo de uso no Vero

```
1. Cliente -> "quero internet"
2. Bot -> "qual seu CEP e numero?"
3. Cliente -> "64000000, 1234"
4. Bot -> POST /viabilidade/  (Hubtrix -> HubSoft)
5. Atende=true -> bot lista planos disponiveis
   Atende=false -> bot envia "infelizmente nao atendemos sua regiao, mas posso te avisar quando expandir?"
```

Diferente do envio de prospecto: a viabilidade e **consulta read-only** que **nao gera lead no HubSoft** — so confirma se vale a pena coletar dados do lead.

---

## Performance

A consulta passa por mapa de cobertura do HubSoft (geo-spatial query). Latencia tipica: 500ms-2s. Cachear no Hubtrix por hash do endereco (24h) e razoavel pra reduzir custo em retentativas.

> **Cache nao implementado ainda.** Pode virar otimizacao quando volume aumentar.
