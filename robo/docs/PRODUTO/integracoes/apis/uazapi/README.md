# uazapi — API

Provedor WhatsApp **nao-oficial** (Baileys-based) usado por aurora-hq e fatepifaespi.

## Tenants ativos

- `aurora-hq` (consulteplus.uazapi.com)
- `fatepifaespi` (instancia propria)

## Base URL

Por tenant — vem de `IntegracaoAPI.base_url`. Padrao: `https://<instancia>.uazapi.com`.

## Auth

Header `token` (nao `Authorization`). Valor: API key do tenant.

## Endpoints principais usados

| Endpoint | Uso no Hubtrix |
|---|---|
| `POST /send/text` | Enviar texto (`apps/inbox/services/uazapi_sender.py`) |
| `POST /send/media` | Enviar midia (imagem, audio, pdf, video) |
| `POST /sender/queue` | Disparo em lote / com delay |
| `POST /sender/edit-msg` | Editar mensagem ja enviada (limitado) |
| `POST /message/delete` | Apagar mensagem |
| `POST /chats/find` | Buscar conversa por telefone |
| `POST /message/find` | Buscar mensagens (paginadas) |
| `GET /status` | Status da instancia (conectado/desconectado/QR) |

Detalhes do disparo + parser (campo `messageid` retornado e nao `key.id`): ver commits recentes do bug `extrair_msg_id` (commit `6c41a2d`).

## Webhook in (entrada de mensagem)

A uazapi POSTa em endpoint Hubtrix com payload `{ event, instance, data, ... }`. Handler em [apps/inbox/views/webhook_uazapi.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/inbox/views/webhook_uazapi.py).

## TODO desta pasta

- `01-envio.md` — text/media/queue, formato base64 vs URL
- `02-recebimento.md` — webhook in, formato de eventos, midias e Fernet storage
- `03-instancia.md` — status, QR, reconexao
- `04-mensagens.md` — find, delete, edit
- `uazapi-API.postman_collection.json` — collection bruta
