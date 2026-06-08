# Matrix API — Atendimento e mensagens

Endpoints que **operam dentro de um atendimento existente** (criar, enviar msg, transferir, agendar, finalizar). Pra **iniciar conversa do zero**, ver [02-disparos.md](02-disparos.md).

## Gerar novo atendimento

`POST /rest/v1/atendimento` ou `POST /rest/v2/atendimento`

Cria um atendimento (receptivo ou ativo) pra um contato identificado por CPF, telefone ou email. Direciona pra um servico/fila ou flow.

### Body principal

| Campo | Tipo | Obrig. | Descricao |
|---|---|---|---|
| `cod_integracao` | int | sim | Canal (1=WhatsApp, 9=SMS, 18=API, 25=Instagram, etc) |
| `cod_conta` | int | sim | ID da conta (Sistema > Contas) |
| `identificador` | string | sim | `num_cpf`, `num_telefone` ou `nom_email` |
| `val_identificador` | string | sim | Valor (ex.: telefone DDI+DDD+numero) |
| `mensagem` | string | nao | Texto da primeira mensagem |
| `ativo` | int | nao | 1=ativo, 0=receptivo (padrao) |
| `url_pesquisa` | int | nao | 1 retorna URL da pesquisa pos-atendimento |
| `contato` | obj | nao | Dados complementares (nome, cpf, email, endereco) |
| `historico` | array | nao | Mensagens passadas pra incluir no atendimento |
| `tipo_destino` | string | nao | `servico` ou `flow` |
| `id_destino` | int | cond | ID do servico ou flow (obrig. se `tipo_destino` setado) |
| `flow_variaveis` | obj | nao | Variaveis do flow (se destino for flow) |
| `num_externo` | string | nao | ID externo (ex.: ID do CRM) — util pra correlacionar |

### Exemplo (v2)

```bash
curl -X POST 'https://nuvyon.matrixdobrasil.ai/rest/v2/atendimento' \
  -H 'Authorization: Bearer <jwt>' \
  -H 'Content-Type: application/json' \
  -d '{
    "cod_integracao": 18,
    "cod_conta": 1,
    "identificador": "num_telefone",
    "val_identificador": "5511999999999",
    "mensagem": "Ola, atendimento iniciado via API",
    "ativo": 0,
    "tipo_destino": "flow",
    "id_destino": 123,
    "contato": {
      "nome": "Joao Silva",
      "cpfCnpj": "12345678900",
      "email": "joao@email.com",
      "telefone": "5511999999999"
    }
  }'
```

### Resposta

```json
{ "cod_error": 0, "msg": "atendimento gerado com sucesso", "cod_atendimento": 3 }
```

### Observacao

Pra WhatsApp oficial (Meta), **nao use** este endpoint pra **iniciar** conversa. Use `sendHsm` (ver [02-disparos.md](02-disparos.md)). Este endpoint vale pra continuar conversa em janela aberta ou pra canais nao-WhatsApp.

---

## Consultar dados de um atendimento

`GET /rest/v1/atendimento?codigo_atendimento=N` ou `GET /rest/v2/atendimento?codigo_atendimento=N`

Retorna dados completos do atendimento + lista de mensagens + dados do contato.

```bash
curl 'https://nuvyon.matrixdobrasil.ai/rest/v2/atendimento?codigo_atendimento=1' \
  -H 'Authorization: Bearer <jwt>'
```

Resposta resumida:

```json
[{
  "id_atendimento": 1,
  "protocolo": "123456789987654321",
  "data_entrada": "2020-04-20 15:00:00",
  "id_status_atendimento": "3",
  "status": "Finalizado",
  "id_conta": "20",
  "id_servico": "39",
  "servico": "Teste",
  "mensagens": [
    { "data_msg": "...", "boleano_entrante": "1", "tip_msg": "TEXTO",
      "descricao_msg": "Teste", "autor": "admin" }
  ],
  "contato": { "contato": "Luke Skywalker", "telefone": "...", "cpf": "..." }
}]
```

---

## Obter atendimentos de um contato

`GET /rest/v2/getAtendimentoContato?cod_contato=N&limit=N&page=N`

Lista paginada dos ultimos atendimentos de um contato.

---

## Obter dados do ultimo atendimento

`GET /rest/v2/getDadosUltimoAtendimento`

Busca o ultimo atendimento por varios filtros possiveis: `codigo_contato`, `telefone`, `cpf_cnpj`, `email`, `codigo_conta`, `codigo_canal`, `codigo_servico`, `codigo_agente`, `codigo_status`, `codigo_classificacao`, `atendimento_ativo=1`.

Util pra: "este telefone tem atendimento aberto hoje?".

---

## Enviar mensagem em atendimento existente

`POST /rest/v1/mensagem` ou `POST /rest/v2/mensagem`

**Endpoint principal pra enviar msg em atendimento ja aberto.** Envia texto ou arquivo (base64 ou URL).

### Body

| Campo | Descricao |
|---|---|
| `cod` | ID do atendimento |
| `mensagem` | Texto |
| `entrante` | 0=saindo (do agente/sistema), 1=entrando (do cliente) |
| `bolFlow` | true se a msg deve ser processada pelo flow |
| `validar_hsm` | Forca validacao de janela 24h do WhatsApp |
| `url_arquivo` | URL publica do arquivo |
| `base64_arquivo` | Conteudo base64 do arquivo |
| `nome_arquivo`, `mime_type` | Metadados do arquivo |
| `ura_opcoes` | Botoes/opcoes interativas (Whatsapp) |
| `forcar_botoes` | Forca renderizar como botoes |
| `bol_mascarar` | Mascara dado sensivel no historico |
| `id_mensagem_resposta` | Marca esta msg como resposta a outra (reply) |

### Exemplo

```bash
curl -X POST 'https://nuvyon.matrixdobrasil.ai/rest/v2/mensagem' \
  -H 'Authorization: Bearer <jwt>' \
  -H 'Content-Type: application/json' \
  -d '{
    "cod": 18,
    "mensagem": "Oi, tudo bem?",
    "entrante": 0
  }'
```

### Resposta

```json
{ "cod_error": 0, "msg": "mensagem inserida com sucesso", "cod_msg": "242483", "cod_atendimento": 18 }
```

### Variantes deprecadas (descontinuadas em 2023-12-31)

- `POST /rest/v1/mensagemAlt` / `/rest/v2/mensagemAlt` — formato de payload com `from`, `to`, `contents[]`. Nao usar em codigo novo.
- `POST /rest/v1/mensagemInteg` / `/rest/v2/mensagemInteg` — variante antiga.

---

## Callback flow (msg em atendimento existente do flow)

`POST /rest/v1/callbackFlowMsg` ou `POST /rest/v2/callbackFlowMsg`

Variante especifica pra atendimentos rodando dentro de um flow. Body: `cod_atendimento`, `sendMsg`, `msg_usuario`, `entrante`.

---

## Transferir atendimento automatico pra humano

`POST /rest/v1/transferirHumano` ou `POST /rest/v2/transferirHumano`

Tira o atendimento do flow/bot e poe na fila de um servico humano.

| Campo | Descricao |
|---|---|
| `cod` | ID do atendimento |
| `cod_servico` | Servico/fila destino |
| `cod_prioridade` | Prioridade na fila |
| `msgTransferencia` | Se envia mensagem de transferencia padrao ao cliente |

---

## Transferir pra flow (v2)

`POST /rest/v2/transferirFlow`

Move atendimento(s) pra outro flow. Body e array:

```json
[{ "cod_atendimento": "68403", "cod_flow": "3" }]
```

Resposta inclui `cod_novo_atendimento` (a Matrix gera um novo atendimento ao transferir entre flows).

---

## Finalizar atendimento

`POST /rest/v2/finalizaAtendimento`

| Campo | Descricao |
|---|---|
| `cod` | ID do atendimento |
| `cod_categorizacao` | Categoria (tabulacao) |
| `cod_pesquisa` | Pesquisa pos-atendimento a disparar |
| `lista_status` | Array de IDs de status a marcar (multiplos) |

---

## Agendar atendimento

`POST /rest/v1/agendamentoContato` ou `POST /rest/v2/agendamentoContato`

Agenda envio de mensagem/atendimento pra data/hora especifica.

| Campo | Descricao |
|---|---|
| `id_contato` | ID do contato |
| `id_atendimento` | Opcional, se vinculado a atendimento existente |
| `has_historico` | 1 inclui historico no agendamento |
| `data_agendamento` | `DD-MM-YYYY` |
| `hora_agendamento` | `HH:MM` |
| `id_grupo_horario` | Grupo de horario util |
| `tipo_destino` | `servico` ou `flow` |
| `id_destino` | ID do servico/flow |
| `flow_variaveis` | Variaveis se for flow |
| `hsm` | ID do template HSM a enviar |
| `hsm_variaveis` | Variaveis do HSM |
| `botoes` | Botoes dinamicos |
| `url_file`, `filename` | Anexo |
| `auth_code` | Codigo de autenticacao (HSM categoria auth, v2) |
| `hsm_parametros` | Parametros adicionais HSM (v2) |

Util pra: enviar lembrete agendado, follow-up de venda.

---

## Checar ultimo atendimento (quantos dias desde)

`POST /rest/v1/checaUltimoLogin` ou `POST /rest/v2/checaUltimoLogin`

Body: `{ "telefone": "5534999999999" }`. Retorna `{ "dias": 5 }` — uteis pra decidir se manda HSM ou pode usar janela aberta.

---

## Exportacao de atendimentos (webhook)

A Matrix dispara webhook pra URL configurada com dados completos do atendimento + mensagens. Schema documentado na collection (item "Exportacao de atendimentos").

Util pra: copia local de atendimentos no nosso DW.

---

## Como o Hubtrix deveria consumir esses endpoints

Hoje **nao consumimos** esses endpoints diretamente (a Matrix Nuvyon e quem cuida do atendimento dela). Cenarios futuros onde faria sentido:

- **Visualizar atendimento Matrix dentro do Hubtrix** (read-only): chamar `GET /rest/v2/atendimento` por protocolo
- **Forcar transferencia de atendimento pra humano** a partir de uma acao no CRM: `POST /transferirHumano`
- **Finalizar atendimento Matrix** quando o lead vira `ganho` no nosso CRM: `POST /finalizaAtendimento`

Quando implementar: criar wrapper em `apps/integracoes/services/matrix.py` (ja existe esqueleto em `prod/dashboard_comercial/.../integracoes/services/matrix.py`) seguindo o padrao do `HubsoftService`.
