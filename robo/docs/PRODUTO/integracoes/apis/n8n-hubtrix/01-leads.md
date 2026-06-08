# Hubtrix N8N API — Leads

## Criar lead

`POST /api/v1/n8n/leads/`

Cria `LeadProspecto` no Hubtrix. Idempotente por telefone (se ja existe, retorna o existente sem duplicar).

### Body

```json
{
  "nome_razaosocial": "Joao Silva",
  "telefone": "5586999001234",
  "email": "joao@email.com",
  "origem": "whatsapp"
}
```

| Campo | Obrig. | Descricao |
|---|---|---|
| `nome_razaosocial` | sim | Nome do lead |
| `telefone` | sim | DDI+DDD+numero (deduplicacao por aqui) |
| `email` | nao | Email |
| `origem` | nao | `whatsapp`, `site`, `indicacao`, etc. Default: `whatsapp` |
| `cidade`, `estado` | nao | Localizacao |
| `score_qualificacao` | nao | 0-10 (preenchido depois) |

### Resposta

```json
{ "success": true, "lead_id": 61, "criado": true }
```

`criado=false` indica que ja existia (retorna o ID do existente).

---

## Atualizar lead

`PUT /api/v1/n8n/leads/<id>/`

Atualiza campos. Aceita parcial (so manda o que muda).

```json
{
  "nome_razaosocial": "Joao Silva Santos",
  "cidade": "Teresina",
  "estado": "PI",
  "score_qualificacao": 8
}
```

### Resposta

```json
{ "success": true }
```

---

## Buscar por telefone

`GET /api/v1/n8n/leads/buscar/?telefone=5586999001234`

Retorna lead se existir no tenant.

```json
{
  "success": true,
  "lead": {
    "id": 61,
    "nome_razaosocial": "Joao Silva",
    "telefone": "5586999001234",
    "email": "joao@email.com",
    "cidade": "Teresina",
    "estado": "PI",
    "score_qualificacao": 8,
    "id_hubsoft": 12345,
    "status_api": "processado"
  }
}
```

Sem resultado:
```json
{ "success": true, "lead": null }
```

---

## Uso no Vero (TR Carrion)

```
1. Webhook Uazapi -> mensagem recebida
2. POST /api/v1/n8n/inbox/mensagem-recebida/   (registra mensagem)
3. GET /api/v1/n8n/leads/buscar/?telefone=...   (existe?)
   |
   |-- nao existe:
   |     POST /api/v1/n8n/leads/  -> cria
   |-- existe:
         (segue com lead_id)
4. POST /api/v1/n8n/crm/oportunidades/         (cria/recupera oportunidade)
5. AI Agent processa msg
6. PUT /api/v1/n8n/leads/<id>/                  (se IA extraiu nome/curso/etc)
```

## Triggers internos no Hubtrix ao criar/atualizar lead

- Signal `post_save` em `LeadProspecto`:
  - Se `status_api='pendente'`: agenda envio pro HubSoft via `processar_pendentes`
  - Se `tenant` tem `enviar_lead=automatico`: dispara `cadastrar_prospecto` direto
  - Log em `LogIntegracao` se houver chamada HubSoft

Bot externo nao precisa se preocupar com isso — `POST /leads/` retorna na mesma hora; o sync HubSoft acontece async.
