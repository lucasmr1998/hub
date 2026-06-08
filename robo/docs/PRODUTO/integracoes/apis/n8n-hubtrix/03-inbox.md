# Hubtrix N8N API — Inbox (Mensagens)

Endpoints pro N8N **espelhar conversa WhatsApp dentro do Inbox** do Hubtrix. Cada mensagem (entrante do cliente ou saiando como bot) e gravada como `Mensagem` em uma `Conversa` do tenant.

## Registrar mensagem recebida (cliente -> Hubtrix)

`POST /api/v1/n8n/inbox/mensagem-recebida/`

Grava no Inbox uma mensagem **vinda do cliente** (WhatsApp via Uazapi/Matrix etc).

### Body

```json
{
  "telefone": "5586999001234",
  "nome": "Joao Silva",
  "conteudo": "Ola, quero saber sobre o curso de Direito",
  "canal_tipo": "whatsapp",
  "tipo_conteudo": "texto",
  "arquivo_nome": null,
  "arquivo_url": null
}
```

| Campo | Descricao |
|---|---|
| `telefone` | Identificador do contato (DDI+DDD+numero) |
| `nome` | Nome do contato (preenchido na criacao do contato) |
| `conteudo` | Texto da mensagem (ou label limpa pra anexos: "[Imagem]", "[Audio]") |
| `canal_tipo` | `whatsapp`, `sms`, `email`, `instagram`, etc |
| `tipo_conteudo` | `texto`, `imagem`, `audio`, `video`, `documento`, `localizacao` |
| `arquivo_nome` | Nome do arquivo (se anexo) |
| `arquivo_url` | URL do arquivo (se externo) ou data URI |

### Resposta

```json
{
  "success": true,
  "mensagem_id": 1234,
  "conversa_id": 312,
  "contato_id": 99,
  "lead_id": 61
}
```

Side-effects internos:
- Cria/recupera `Contato`
- Cria/reusa `Conversa` (ativa pra esse contato + canal)
- Cria `LeadProspecto` se nao existia
- Salva midia em `PrivateMidiaStorage` (Fernet) se `arquivo_url` for data URI

---

## Enviar mensagem como bot (Hubtrix -> cliente via N8N)

`POST /api/v1/n8n/inbox/enviar/`

Espelha no Inbox uma mensagem que o **bot N8N esta prestes a enviar**. Nao dispara WhatsApp diretamente — so registra a saida no nosso lado pra que apareca no chat do operador (continuidade visual).

### Body

```json
{
  "telefone": "5586999001234",
  "conteudo": "Ola Joao! O curso de Direito funciona das 18h30 as 21h40.",
  "remetente_nome": "Pedro"
}
```

| Campo | Descricao |
|---|---|
| `telefone` | Destinatario |
| `conteudo` | Texto da msg |
| `remetente_nome` | Nome do "agente bot" exibido no Inbox |

### Resposta

```json
{ "success": true, "mensagem_id": 1235 }
```

---

## Variante publica (v2 com mais campos)

`POST /api/public/n8n/inbox/mensagem/`

Versao mais nova usada pelo orquestrador Vero. Aceita os mesmos campos + variantes pra anexos:

```json
{
  "telefone": "...",
  "conteudo": "[Imagem]",
  "tipo_conteudo": "imagem",
  "arquivo_nome": "rg_frente.jpg",
  "entrante": true,
  "id_externo": "<uazapi-msg-id>"
}
```

`id_externo` ajuda na deduplicacao quando uazapi reenvia evento por flapping de conexao.

---

## Uazapi: campo `messageid` no retorno

Bug historico: parser `extrair_msg_id` lia `result['key']['id']` (formato Baileys); uazapi retorna `result.messageid` ou `result.id`. Corrigido no commit `6c41a2d`. Detalhe relevante quando o N8N processa retorno de envio uazapi e precisa passar o ID pro Hubtrix.

---

## Fluxo Vero (TR Carrion)

```
1. Webhook Uazapi -> N8N
2. Node "Entrada" extrai: conteudo_inbox, tipo_midia (label limpa)
3. POST /api/public/n8n/inbox/mensagem/  (registra entrada)
4. Roteador detecta tipo de fluxo
5. Bot responde via Uazapi
6. POST /api/public/n8n/inbox/mensagem/  (registra saida)
```

Diferentes etapas do fluxo nao mandam o objeto de midia cru pro Inbox — so o **label limpo** (ex.: "[Imagem]") + `tipo_conteudo` + `arquivo_nome`. Evita JSON cru no balao do Inbox.

---

## Modo Visualizar / Assumir (regra do tenant)

Quando admin/supervisor abre uma conversa que nao assumiu, o GET retorna `pode_visualizar=true` + `assumida=false`. UI bloqueia o input de envio. So apos `POST /api/v1/inbox/conversa/<id>/assumir/` o input libera.

Comportamento documentado em [../../../modulos/inbox/](../../../modulos/inbox/) (parte do produto, nao API publica N8N).

---

## Encerrar conversa por inatividade

Cron `encerrar_conversas_inativas` (ver [../../../ops/02-CRON.md](../../../ops/02-CRON.md)) fecha conversas sem msg do cliente nas ultimas N horas (configuravel por tenant). Endpoint API nao expoe esse encerramento — e logica server-side.
