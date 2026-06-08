# Matrix API — Disparos (iniciar conversa)

Endpoints que **iniciam mensagem do nosso lado** (broker outbound). E o que interessa pro Hubtrix quando precisamos notificar cliente fora do canal proprio (sem uazapi).

## Visao geral

| Endpoint | Canal | Tipo |
|---|---|---|
| `POST /rest/v1/sendHsm` | WhatsApp | Template HSM (categoria marketing/utilidade/auth) |
| `POST /rest/v2/dialogoWhatsapp` | WhatsApp | HSM **ou** mensagem livre (mais flexivel) |
| `POST /rest/v2/sendSms` | SMS | Texto puro |
| `POST /rest/v2/agendamentoContato` | Qualquer | Agenda disparo pra data/hora (ver [01-atendimento-mensagens.md](01-atendimento-mensagens.md)) |

## Quando usar cada um

| Cenario | Endpoint |
|---|---|
| Notificacao WhatsApp **fora de janela 24h** | `sendHsm` ou `dialogoWhatsapp` (com `hsm` setado) |
| Notificacao WhatsApp **dentro de janela 24h** (cliente respondeu nas ultimas 24h) | `dialogoWhatsapp` sem HSM, ou `mensagem` em atendimento aberto |
| Lembrete SMS | `sendSms` |
| Disparo agendado (envia depois) | `agendamentoContato` |
| Disparo em lote (uma campanha) | `dialogoWhatsapp` aceita array em `contato[]` |

---

## `POST /rest/v1/sendHsm` — Disparar template HSM

Envia template aprovado pelo WhatsApp pra um contato. Cria um atendimento novo (ou anexa ao atual se `bol_incluir_atual=1`).

### Body principal

| Campo | Tipo | Obrig. | Descricao |
|---|---|---|---|
| `cod_conta` | int | sim | ID da conta WhatsApp na Matrix |
| `hsm` | int | sim | ID do template HSM (cadastrado na Matrix) |
| `tipo_envio` | int | sim | **1**=atendimento automatico, **2**=notificacao, **3**=fila |
| `cod_flow` | int | cond | Se `tipo_envio=1`: flow destino |
| `cod_servico` | int | cond | Se `tipo_envio=3`: servico/fila destino |
| `start_flow` | int | cond | Se `tipo_envio=1`: 1 inicia o flow apos envio |
| `url_file` | string | cond | URL da midia (se HSM tem media header) |
| `auth_code` | string | cond | Se HSM e categoria autenticacao |
| `variaveis` | obj | nao | Substitui `{{1}}`, `{{2}}` etc do template |
| `botoes` | obj | nao | Botoes com valor dinamico (variavel em URL/payload) |
| `contato` | obj | sim | `nome`, `cpfCnpj`, `email`, `telefone`, `endereco` |
| `flow_variaveis` | obj | nao | Variaveis do flow se `tipo_envio=1` |
| `bol_incluir_atual` | int | nao | 1=envia mesmo que cliente tenha atendimento em andamento |

### Exemplo

```bash
curl -X POST 'https://nuvyon.matrixdobrasil.ai/rest/v1/sendHsm' \
  -H 'Authorization: <api-key-v1>' \
  -H 'Content-Type: application/json' \
  -d '{
    "cod_conta": 5,
    "hsm": 11,
    "tipo_envio": 2,
    "url_file": "https://app.hubtrix.com.br/files/contrato_lead_463.pdf",
    "variaveis": { "1": "Joao", "2": "Contrato #1234" },
    "contato": {
      "nome": "Joao da Silva",
      "cpfCnpj": "12345678900",
      "email": "joao@email.com",
      "telefone": "5511999999999"
    }
  }'
```

### Resposta

```json
{ "cod_error": 0, "msg": "atendimento gerado com sucesso", "cod_atendimento": 1 }
```

### Botoes dinamicos

Se o template HSM tem botao com variavel (ex.: URL dinamica), passar valor em `botoes`:

```json
{ "botoes": { "0": "https://hubtrix.com.br/aceitar/abc123" } }
```

---

## `POST /rest/v2/dialogoWhatsapp` — Disparar HSM ou livre (recomendado)

Versao moderna e flexivel. Envia HSM ou mensagem livre. Aceita disparar pra **um ou mais contatos** numa unica chamada (campanha simples). Suporta agendamento.

### Body principal

| Campo | Descricao |
|---|---|
| `cod_conta` | ID da conta WhatsApp |
| `hsm` | ID do template (omitir se for msg livre) |
| `mensagem` | Texto da msg livre (omitir se HSM) |
| `tipo_envio` | 1=automatico, 2=notificacao, 3=fila |
| `cod_flow` | Flow destino |
| `hsm_variaveis` | `{ "1": "x", "2": "y", ... }` |
| `botoes` | Botoes dinamicos (array de valores) |
| `url_file`, `filename` | Anexo |
| `data_agendamento` | `DD/MM/YYYY HH:MM` — se quiser agendar |
| `descricao_agendamento` | Nome amigavel do agendamento |
| `contato` | **Array** de contatos (cada um com nome, telefone etc) |
| `cod_grupo_horario` | Grupo de horario util |
| `flow_variaveis` | Variaveis do flow |
| `auth_code` | Codigo (HSM auth) |
| `hsm_parametros` | Parametros extras HSM |

### Exemplo (disparo imediato)

```bash
curl -X POST 'https://nuvyon.matrixdobrasil.ai/rest/v2/dialogoWhatsapp' \
  -H 'Authorization: Bearer <jwt>' \
  -H 'Content-Type: application/json' \
  -d '{
    "cod_conta": 1,
    "hsm": 11,
    "tipo_envio": 2,
    "hsm_variaveis": { "1": "Joao" },
    "contato": [
      { "nome": "Joao", "telefone": "5511999999999" }
    ]
  }'
```

### Resposta

```json
{ "cod_error": 0, "msg": "Agendamento API dialogoWhatsapp gerado com sucesso", "cod_agendamento": 0 }
```

---

## `POST /rest/v2/sendSms` — Disparar SMS

Envia SMS pra contato. Pode iniciar flow ou ser apenas notificacao.

### Body

| Campo | Descricao |
|---|---|
| `cod_conta` | ID da conta SMS |
| `texto` | Conteudo da msg |
| `tipo_envio` | 1=automatico, 2=notificacao, 3=fila |
| `cod_flow` | Flow destino (se `tipo_envio=1`) |
| `contato` | `{ "telefone": "5511...", "nome": "..." }` |
| `start_flow` | 1 inicia flow |
| `flow_variaveis` | Variaveis do flow |
| `id_atendimento` | Opcional, anexar a atendimento |
| `bol_incluir_atual` | 1 envia mesmo com atendimento aberto |

### Exemplo

```bash
curl -X POST 'https://nuvyon.matrixdobrasil.ai/rest/v2/sendSms' \
  -H 'Authorization: Bearer <jwt>' \
  -H 'Content-Type: application/json' \
  -d '{
    "cod_conta": 1,
    "texto": "Seu codigo: 1234",
    "tipo_envio": 2,
    "contato": { "telefone": "5511999999999", "nome": "Joao" }
  }'
```

---

## Consultar status de HSMs disparados

`GET /rest/v1/hsmEnviadas` ou `GET /rest/v2/hsmEnviadas`

| Query | Descricao |
|---|---|
| `data_inicial`, `data_final` | `DD/MM/YYYY` |
| `page` | Pagina |
| `cpf_cnpj` | Filtra por contato |
| `telefone` | Filtra por contato |

Resposta inclui `cod_status` por mensagem (enviada/entregue/lida/falhou).

---

## Consultar eventos analiticos (entrega, leitura)

`GET /rest/v2/reportEventosAnaliticoMensagens?data_inicial=...&data_final=...&bol_campanha=1&cod_campanha=N`

Retorna timestamps de envio, entrega, leitura, modificacao por mensagem. Mais granular que `hsmEnviadas`. Use pra reconciliar status no nosso lado.

---

## Janela de sessao WhatsApp

`GET /rest/v2/consultaJanelaSessao?num_telefone=5534999999999`

Retorna se o contato tem janela 24h aberta (i.e., respondeu ha menos de 24h). Util pra decidir: **se janela aberta**, usa `dialogoWhatsapp` sem HSM (mais barato + flexivel). **Se nao**, manda HSM.

---

## Opt-in

`POST /rest/v1/optin` ou `POST /rest/v2/optin`

Registra que o contato aceitou receber mensagens. Necessario antes do primeiro envio em alguns canais.

| Campo | Descricao |
|---|---|
| `cod_contato` | ID do contato |
| `num_telefone` | Telefone |
| `nom_email` | E-mail |
| `cod_conta` | Conta |
| `cod_canal_solicitacao` | Canal onde o opt-in foi solicitado |

---

## Como o Hubtrix poderia usar

### Caso 1 — Hubtrix dispara HSM pro cliente Nuvyon quando contrato fica pronto

Hoje a Nuvyon nao tem uazapi propria configurada. Fluxo possivel:

1. Engine de automacao do CRM dispara acao `notificar_contrato_pronto` quando contrato HubSoft e criado (regra #19 da Nuvyon).
2. Nova acao no engine chama `MatrixService.send_hsm(template_id, contato, variaveis)`.
3. Wrapper em `apps/integracoes/services/matrix.py` faz `POST /rest/v1/sendHsm` na Matrix Nuvyon.
4. Status do envio fica em `MatrixDisparo` (novo model) com poll via `hsmEnviadas`.

### Caso 2 — Lembrete de visita tecnica via SMS

`MatrixService.send_sms(texto, telefone)` -> `POST /rest/v2/sendSms`.

### Caso 3 — Disparo em massa de cobranca (campanha)

`dialogoWhatsapp` com `contato[]` agrupando ate N telefones por chamada.

**Decisao arquitetural pendente:** o wrapper `MatrixService` ainda nao existe no codigo atual do Hubtrix (so o esqueleto em `prod/.../integracoes/services/matrix.py`). Quando implementar, seguir padrao do `HubsoftService` (FromIntegracaoAPI + cache de JWT v2).
