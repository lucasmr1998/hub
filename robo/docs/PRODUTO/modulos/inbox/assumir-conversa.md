# Inbox — Assumir conversa (claiming)

Mecanismo que separa **ver** uma conversa de **responder** nela. Evita que
vendedora/admin digite achando que enviou e a mensagem nunca chegue no
cliente.

---

## Regra de negócio

Toda Conversa tem dois flags relevantes:

- `agente_id` — quem é o dono atribuído (pode ser null em fila)
- `assumida` — boolean, indica se o dono efetivamente "pegou" a conversa

**O input do chat só fica habilitado se `assumida == True`.**

Existem 3 estados visíveis na UI:

| Estado | Quem vê | Aparência | Pode responder? |
|--------|---------|-----------|-----------------|
| **Aberto/normal** | dono que assumiu | mensagens + input | Sim |
| **Pendente** (`agente_id != null, assumida = False`) | dono que ainda não clicou em "Assumir" | banner amarelo no lugar das mensagens, botão "Assumir conversa" | Não |
| **Visualizando** | admin/supervisor (`inbox.ver_todas`) abrindo conversa de outro | mensagens visíveis + barra cinza no rodapé "Você está visualizando" + botão "Assumir" | Não (até clicar Assumir) |

---

## Backend

### GET `/inbox/api/conversas/<id>/`
Retorna a conversa serializada. Campos relevantes:

- `assumida` — estado real do banco (booleano)
- `pode_visualizar` — true se o usuário tem permissão `inbox.ver_todas`
- `agente_id`, `agente_nome` — dono atual (pode ser null)

> **Importante:** o backend **não mente** mais o `assumida` pra admin (até
> 03/06/2026 ele setava `assumida=True` falsamente pra liberar histórico,
> mas como o input do frontend dependia desse mesmo flag, o admin enviava
> mensagens que o `enviar_mensagem` rejeitava com 403 — geravam órfãs no
> DB. Hoje o frontend usa `pode_visualizar` como flag separada).

### POST `/inbox/api/conversas/<id>/assumir/`
Marca `assumida=True`, vincula o agente ao usuário atual.

- Se a conversa **não tinha dono**: vira do usuário
- Se a conversa tinha dono = usuário atual: só seta `assumida=True`
- Se a conversa tinha **outro dono**: **transfere** + cria mensagem sistema
  na timeline (`"Conversa assumida por X (anteriormente de Y)"`) +
  reseta `data_assumida`

Resposta:
```json
{ "success": true, "assumida": true, "transferida_de": <id ou null> }
```

### POST `/inbox/api/conversas/<id>/enviar/`
Cria + envia mensagem do agente. **Antes de qualquer save no DB**, valida
que `conversa.assumida` é true (se há `agente_id`). Caso contrário, 403
com code `nao_assumida`. **Sem auto-assumir** — admin/supervisor que
visualiza precisa clicar "Assumir" antes.

---

## Frontend

Identifica o usuário atual via `data-user-id` em `#inboxApp` (template Django).

Função `_aplicarEstadoAssumida(assumida, podeVisualizar, agenteNome)`
controla os 3 estados acima. Botões "Assumir conversa" (do banner amarelo
e do viewer cinza) compartilham handler `_assumirComConfirmacao()` que:

1. Lê `state.currentConversaAgenteId`
2. Se diferente de `currentUserId`, mostra `confirm()` pedindo confirmação
   da transferência
3. POST `/assumir/` → recarrega detalhe + mensagens

---

## Casos limite e armadilhas

- **Bot Vero (N8N) grava mensagens direto** via `views_n8n_webhook.py`
  com `remetente_tipo='agente' user_id=None`. Essas **não passam pelo
  check de `assumida`** porque o N8N já manda direto pra uazapi por conta
  própria. O Hubtrix só registra retroativamente — `identificador_externo`
  fica vazio (não é bug).
- **Transferência** reseta `data_assumida`. Se o produto precisar do
  histórico do dono anterior, ler a mensagem sistema na timeline.
- **Atribuir** (`atribuir_conversa`) reseta `assumida=False` — novo
  agente precisa assumir explicitamente.

---

## Histórico

- **30/05/2026** (`c7aeb4e`): feature claiming introduzida — `Conversa.assumida`,
  endpoint `/assumir/`, banner amarelo.
- **03/06/2026** (`6c41a2d`): hotfix — `mensagem.save()` movido pra
  depois do check de `assumida` (era criado em órfão antes); fix parser
  `extrair_msg_id` do UazapiProvider (lia formato Baileys).
- **03/06/2026** (commit atual): introdução do **modo visualização**
  separado do modo assumido. Bug crítico: backend setava `assumida=True`
  falsamente pra admin, libertando UI mas backend rejeitava. Agora
  `pode_visualizar` é flag separada. Endpoint assumir aceita
  transferência com log na timeline.
