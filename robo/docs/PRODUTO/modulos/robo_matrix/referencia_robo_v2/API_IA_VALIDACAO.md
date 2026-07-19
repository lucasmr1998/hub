# API de IA de Validação — Referência Detalhada

> Serviço **FastAPI** (`ia_validacao/src/app.py`) que o Matrix consulta a cada turno
> do fluxo de vendas/atendimento. É o **flow determinístico**: a decisão vem de um
> `extractor` por tipo (CPF, CEP, opção, confirmação…) configurado por regra no
> Django (`RegraValidacao`) — **não** de LLM. A única exceção que usa IA de fato é
> `/validar-imagem` (OpenAI Vision).
>
> Versão da API: `2.0.0` · Título: *Megalink IA Validação*

---

## Índice

1. [Arquitetura](#1-arquitetura)
2. [Convenções gerais](#2-convenções-gerais)
3. [`POST /validar`](#3-post-validar--validação-de-uma-resposta) — o coração
4. [`POST /proximo-passo`](#4-post-proximo-passo--roteador-inicial)
5. [`POST /validar-imagem`](#5-post-validar-imagem)
5b. [`POST /recontato`](#5b-post-recontato--reengajamento-no-tempo-de-espera) — reengajamento no tempo de espera
6. [Endpoints auxiliares e legados](#6-endpoints-auxiliares-e-legados)
7. [Referência: extractors](#7-referência-extractors)
8. [Referência: sequência de coleta (mapa do fluxo)](#8-referência-sequência-de-coleta-mapa-do-fluxo)
9. [Referência: status_api do lead](#9-referência-status_api-do-lead)
10. [Logging de interações](#10-logging-de-interações)

---

## 1. Arquitetura

```
        ┌─────────────┐   /proximo-passo    ┌────────────────────┐
        │   Matrix    │ ──────────────────▶ │  API IA Validação  │
        │ (chatbot)   │   /validar          │     (FastAPI)      │
        │             │ ◀────────────────── │                    │
        └─────────────┘   JSON estruturado  └─────────┬──────────┘
                                                       │ HTTP
                                          regras + ações│ + log
                                                       ▼
                                            ┌────────────────────┐
                                            │   Django (Robô)    │
                                            │ RegraValidacao,    │
                                            │ LeadProspecto,     │
                                            │ LogInteracaoIA     │
                                            └────────────────────┘
```

- **`/proximo-passo`** é chamado **uma vez** quando o cliente entra: decide *para onde* mandar o cliente (qual nó do Matrix / qual pergunta).
- **`/validar`** é chamado a **cada resposta**: valida, extrai o dado, salva no lead e devolve a decisão do próximo passo implícito.
- As regras ficam em cache em memória (TTL configurável); o Django avisa mudanças via `POST /admin/invalidar-cache/`.

---

## 2. Convenções gerais

| Item | Comportamento |
|---|---|
| **Sucesso** | Sempre `HTTP 200` com corpo JSON. "Resposta inválida do cliente" **não** é erro HTTP — vem `200` com `valido: false`. |
| **Erro interno** | `HTTP 500` com `{"detail": "<mensagem>"}` (exceção não tratada). |
| **Erro de schema** | `HTTP 422` (validação do Pydantic — campo obrigatório ausente/tipo errado). |
| **`mensagem_inicial` vs `_safe`** | `mensagem_inicial` mantém `\n` (renderiza bonito no WhatsApp). `mensagem_inicial_safe` remove quebras de linha (uso seguro dentro de body JSON de outras APIs). |
| **Emojis** | Vêm como placeholders `##1f680##` (codepoint) — o Matrix converte. |
| **Compat legado** | `/validar` devolve, além do schema V2, um bloco de campos legados em **string** (`"true"`/`"false"`) para o flow Matrix antigo. |
| **Side-effects** | `/validar` salva o campo principal de forma **síncrona** e dispara status/tags/histórico em **background** (thread). O log é sempre assíncrono e nunca derruba a resposta. |

---

## 3. `POST /validar` — validação de uma resposta

Endpoint principal. Recebe a pergunta feita + a resposta do cliente, identifica a
regra, aplica o extractor, salva o dado e devolve a decisão.

### 3.1 Request — `ValidarV2Request`

| Campo | Tipo | Obrigatório | Descrição |
|---|---|:---:|---|
| `question` | `str` | ✅ | Texto da pergunta feita ao cliente |
| `answer` | `str` | ✅ | Resposta do cliente (texto **ou** URL/nome de imagem) |
| `cellphone` | `str` | ✅ | Telefone do contato |
| `lead_id` | `int \| null` | ❌ | ID do lead no Django (se já existe) |
| `question_id` | `str` | ❌ | Identificador da regra. Se vier, lookup direto; senão, infere pela `question` |

```json
{
  "question": "Pra começar, pode me informar seu CPF?",
  "answer": "111.444.777-35",
  "cellphone": "5564999998888",
  "lead_id": 1234,
  "question_id": "coleta_cpf"
}
```

### 3.2 Response — `ValidarV2Response`

**Bloco V2 (novo):**

| Campo | Tipo | Descrição |
|---|---|---|
| `valido` | `bool` | A resposta passou no extractor |
| `extracted_data` | `dict` | Dados extraídos (varia por extractor — ver §7) |
| `message` | `str` | Mensagem composta pro cliente (vazia em coletas simples) |
| `motivo_invalido` | `str` | Código do erro quando `valido=false` (ex: `cpf_invalido`) |
| `intent` | `str` | Intent detectada (geralmente vazio em `/validar`) |
| `transbordo` | `bool` | Deve cair para atendente humano |
| `fim_fluxo` | `bool` | Fluxo encerrado |
| `actions_executed` | `list` | Ações disparadas (ex: `[{"tipo":"agendado_background","ok":true}]`) |
| `regra_aplicada` | `str` | `question_id` usado (`_sem_regra` se nenhuma casou) |
| `tentativas` | `int` | Nº de tentativas dessa questão |
| `usou_ia` | `bool` | Sempre `false` no caminho determinístico |
| `confianca` | `float` | `1.0` se válido, `0.0` se inválido, `0.3` se sem regra |

**Bloco legado (compat Matrix antigo)** — todos `str`:

| Campo | Valor |
|---|---|
| `answerIsCorrect` / `resposta_correta` | `"true"`/`"false"` (= `valido`) |
| `resposta_sem_erro_api` | `"true"`/`"false"` |
| `errorMessage` / `retorno_erro_api` | `message` quando inválido; senão `""` |
| `mensagem_resposta` | mensagem rica (só em cenários transbordo/menu/agendamento) |
| `isAClient` | `"true"` se CPF identificou cliente Hubsoft |
| `hasCancelledService` / `cancelado` | `"false"` (reservados) |
| `needsReception` | `"true"` se `transbordo` |
| `time_instalacao` | `""` (reservado) |
| `viabilidade_cep` | `"true"` se extractor `cep` válido |
| `givesServiceToCity` | `"true"` (reservado) |
| `api_cep` | `message` quando extractor `cep` |
| `ret_cep` / `ret_estado` / `ret_cidade` / `ret_bairro` / `ret_rua` | preenchidos só no extractor `cep` |

### 3.3 Variações de retorno conforme a entrada

#### A) Resposta **válida** (coleta simples — ex: CPF)

```json
{
  "valido": true,
  "extracted_data": { "cpf_cnpj": "11144477735" },
  "message": "",
  "motivo_invalido": "",
  "intent": "",
  "transbordo": false,
  "fim_fluxo": false,
  "actions_executed": [{ "tipo": "agendado_background", "ok": true }],
  "regra_aplicada": "coleta_cpf",
  "tentativas": 1,
  "usou_ia": false,
  "confianca": 1.0,

  "answerIsCorrect": "true",
  "resposta_correta": "true",
  "resposta_sem_erro_api": "true",
  "errorMessage": "",
  "retorno_erro_api": "",
  "mensagem_resposta": "",
  "isAClient": "false",
  "hasCancelledService": "false",
  "cancelado": "false",
  "needsReception": "false",
  "time_instalacao": "",
  "viabilidade_cep": "false",
  "givesServiceToCity": "true",
  "api_cep": "",
  "ret_cep": "", "ret_estado": "", "ret_cidade": "", "ret_bairro": "", "ret_rua": ""
}
```

#### B) Resposta **inválida** (ex: CPF com dígito errado)

```json
{
  "valido": false,
  "extracted_data": {},
  "message": "CPF inválido, pode conferir e mandar de novo?",
  "motivo_invalido": "cpf_invalido",
  "intent": "",
  "transbordo": false,
  "fim_fluxo": false,
  "actions_executed": [],
  "regra_aplicada": "coleta_cpf",
  "tentativas": 2,
  "usou_ia": false,
  "confianca": 0.0,

  "answerIsCorrect": "false",
  "resposta_correta": "false",
  "resposta_sem_erro_api": "false",
  "errorMessage": "CPF inválido, pode conferir e mandar de novo?",
  "retorno_erro_api": "CPF inválido, pode conferir e mandar de novo?",
  "mensagem_resposta": "",
  "isAClient": "false",
  "needsReception": "false",
  "viabilidade_cep": "false",
  "api_cep": "", "ret_cep": "", "ret_estado": "", "ret_cidade": "", "ret_bairro": "", "ret_rua": ""
}
```

> `message`/`motivo_invalido` mudam por extractor — ver tabela em §7.

#### C) Extractor **CEP** válido (preenche endereço via ViaCEP)

```json
{
  "valido": true,
  "extracted_data": {
    "cep": "64000000", "rua": "Praça Marechal Deodoro",
    "bairro": "Centro", "cidade": "Teresina", "estado": "PI"
  },
  "message": "",
  "regra_aplicada": "coleta_cep",
  "transbordo": false, "fim_fluxo": false, "confianca": 1.0,

  "viabilidade_cep": "true",
  "api_cep": "",
  "ret_cep": "64000000",
  "ret_estado": "PI",
  "ret_cidade": "Teresina",
  "ret_bairro": "Centro",
  "ret_rua": "Praça Marechal Deodoro"
}
```

#### D) CPF identifica **cliente Hubsoft existente** → transbordo p/ menu

```json
{
  "valido": true,
  "extracted_data": {
    "cpf_cnpj": "11144477735",
    "eh_cliente_existente": true,
    "nome_cliente_hubsoft": "MARIA SOUZA"
  },
  "message": "Achei seu cadastro, Maria! Como posso te ajudar hoje?",
  "regra_aplicada": "coleta_cpf",
  "transbordo": true,
  "isAClient": "true",
  "needsReception": "true",
  "mensagem_resposta": "Achei seu cadastro, Maria! Como posso te ajudar hoje?"
}
```

#### E) `tipo_imovel = empresa` → transbordo (bot só atende residencial)

```json
{
  "valido": true,
  "extracted_data": { "opcao": "empresa" },
  "message": "Pra planos empresariais vou te passar pra um especialista...",
  "regra_aplicada": "tipo_imovel",
  "transbordo": true,
  "needsReception": "true",
  "mensagem_resposta": "Pra planos empresariais vou te passar pra um especialista..."
}
```

#### F) **Nenhuma regra** aplicável (aceita "livre" pra não travar o flow)

```json
{
  "valido": true,
  "extracted_data": { "valor": "qualquer coisa que o cliente mandou" },
  "message": "Anotei!",
  "regra_aplicada": "_sem_regra",
  "confianca": 0.3,
  "transbordo": false, "fim_fluxo": false,
  "answerIsCorrect": "true"
}
```

#### G) `escolha_data` opção `1/2/3` → mapeia para data ISO real

```json
{
  "valido": true,
  "extracted_data": {
    "opcao": "1",
    "data_instalacao": "2026-06-05",
    "data_instalacao_label": "05/06/2026"
  },
  "regra_aplicada": "escolha_data",
  "fim_fluxo": false
}
```

> Se a consulta de datas falhar, mantém `valido=true` e `data_instalacao` vazio
> (não pune o cliente — um atendente resolve). Se a abertura de OS der erro real,
> volta `transbordo=true` com `message` de transferência.

---

## 4. `POST /proximo-passo` — roteador inicial

Chamado **uma vez** quando o cliente entra. Olha `status_api` do lead + campos já
preenchidos e devolve o nó do Matrix para o "jump" dinâmico.

### 4.1 Request — `ProximoPassoRequest`

| Campo | Tipo | Obrigatório | Descrição |
|---|---|:---:|---|
| `cellphone` | `str` | ✅ | Telefone do contato |
| `lead_id` | `int \| null` | ❌ | ID do lead (busca pelo telefone se ausente) |
| `ultima_mensagem` | `str` | ❌ | Última mensagem do cliente (ajuda a detectar intent) |

```json
{ "cellphone": "5564999998888", "lead_id": null, "ultima_mensagem": "oi, quero internet" }
```

### 4.2 Response — `ProximoPassoResponse`

| Campo | Tipo | Descrição |
|---|---|---|
| `lead_id` | `int \| null` | ID final usado (criado se necessário) |
| `status_lead` | `str` | `status_api` atual (ou estado interno: `lead_novo`, `erro`…) |
| `proximo_passo` | `str` | **Identifier do nó Matrix** (ex: `msg_sol_cpf`) — usado no jump |
| `proxima_pergunta_id` | `str` | `question_id` da próxima pergunta (ex: `coleta_cpf`) |
| `deve_perguntar` | `bool` | Continuar coletando |
| `deve_transbordar` | `bool` | Transferir para humano |
| `motivo` | `str` | Explicação humana da decisão |
| `mensagem_inicial` | `str` | Mensagem sugerida (com `\n`) |
| `mensagem_inicial_safe` | `str` | Mesma mensagem sem `\n` |
| `intent_detectado` | `str` | `contratar`/`suporte`/`cancelar`/`financeiro`/`cumprimento`/`""` |
| `dados_ja_coletados` | `dict` | Campos do lead já preenchidos (chaves de `SEQUENCIA_COLETA`) |
| `ura` | `dict \| null` | **URA estruturada (aditivo)** — `null` em pergunta aberta; objeto quando a mensagem oferece opções numeradas (ver 4.2b) |

### 4.2b Campo `ura` — URA de opções estruturada

Quando a pergunta é uma **URA de opções** (mensagem com `*1)* … *2)* …`), o engine
devolve, além da mensagem pronta, a estrutura parseada — para o Matrix montar a URA
sem precisar interpretar texto:

```json
"ura": {
  "tipo": "opcoes",
  "titulo": "confirmacao_endereco",
  "pergunta": "##1f4cd## *Confira o endereço que encontrei:*\n\n##1f3f7## *CEP:* 64020-340\n##1f6e3## *Rua:* Quadra Saci\n\nEstá tudo certo?",
  "pergunta_safe": "##1f4cd## *Confira o endereço que encontrei:* ##1f3f7## *CEP:* 64020-340 ... Está tudo certo?",
  "opcoes": [
    { "numero": "1", "texto": "Sim, está correto", "texto_completo": "Sim, está correto" },
    { "numero": "2", "texto": "Não, corrigir",     "texto_completo": "Não, preciso corrigir" }
  ],
  "total_opcoes": 2,
  "respostas_validas": ["1", "2"]
}
```

- `pergunta` vem **estilizada pro WhatsApp**: quebras de linha, `*negrito*` e os
  **tokens de emoji `##hex##` preservados** (padrão do canal — o Matrix converte
  no envio; emoji unicode direto quebra a renderização). Use no **body** da URA
  interativa. `pergunta_safe` é a versão em linha única (para bodies JSON).
- `opcoes[].texto` tem **no máximo 20 caracteres** (limite de botão do WhatsApp) —
  rótulos curados para as opções conhecidas ("Upgrade de plano", "1 Giga + Ponto"…)
  e abreviação automática nas dinâmicas (remove preço/parênteses, corta em 20).
  `opcoes[].texto_completo` traz o texto integral (bom para a *description* das
  linhas de lista, limite 72).

- `titulo` = `question_id` da pergunta (ex.: `tipo_imovel`, `dia_vencimento`).
- `pergunta`/`opcoes[].texto` vêm **limpos** (sem tokens de emoji `##hex##` nem markdown);
  a linha de instrução ("Responda apenas com…") fica de fora.
- Funciona para URAs **fixas e dinâmicas** (menu do cliente, planos com preço —
  "Plano 620 Mega — R$ 99,90/mês" —, datas de instalação, retomada, CPF atual/novo),
  pois é parseado da própria mensagem — inclusive refletindo edições feitas na aba
  **Mensagens do Robô**.
- Pergunta aberta (CPF, nome, e-mail…) → `"ura": null`.

### 4.3 Variações de retorno conforme o estado do lead

#### A) Cliente **totalmente novo** (sem lead) → cria lead e pede CPF

```json
{
  "lead_id": 1234,
  "status_lead": "lead_novo",
  "proximo_passo": "msg_sol_cpf",
  "proxima_pergunta_id": "coleta_cpf",
  "deve_perguntar": true,
  "deve_transbordar": false,
  "motivo": "Lead novo criado — começar pelo CPF",
  "mensagem_inicial": "Oi! Que bom ter você aqui na *Megalink* ##1f680##\n\nPra começar, pode me informar seu *CPF*? ##1f194##\n\n_Exemplo: 999.999.999-99_\n\nVou usar pra verificar se você já tem cadastro com a gente.",
  "mensagem_inicial_safe": "Oi! Que bom ter você aqui na *Megalink* ##1f680##  Pra começar, pode me informar seu *CPF*? ##1f194##  _Exemplo: 999.999.999-99_  Vou usar pra verificar se você já tem cadastro com a gente.",
  "intent_detectado": "contratar",
  "dados_ja_coletados": {}
}
```

#### B) Lead com **dados parciais** → retoma da próxima pergunta faltante

```json
{
  "lead_id": 1234,
  "status_lead": "lead_novo",
  "proximo_passo": "msg_pergunta",
  "proxima_pergunta_id": "coleta_email",
  "deve_perguntar": true,
  "deve_transbordar": false,
  "motivo": "Retomando: próxima pergunta coleta_email",
  "mensagem_inicial": "...pergunta de e-mail...",
  "intent_detectado": "",
  "dados_ja_coletados": {
    "cpf_cnpj": "11144477735",
    "nome_razaosocial": "Maria Souza",
    "data_nascimento": "1990-05-10",
    "email": ""
  }
}
```

#### C) **Cliente ativo / instalação agendada** → mostra menu

```json
{
  "lead_id": 1234,
  "status_lead": "cliente_ativo",
  "proximo_passo": "msg_menu_cliente",
  "proxima_pergunta_id": "menu_cliente_existente",
  "deve_perguntar": true,
  "deve_transbordar": false,
  "motivo": "Cliente Hubsoft — exibindo menu",
  "mensagem_inicial": "Oi de novo! O que você precisa hoje?\n1) Contratar novo serviço\n2) Upgrade de plano\n3) Acompanhar instalação\n4) Falar com atendente",
  "intent_detectado": "",
  "dados_ja_coletados": { "cpf_cnpj": "11144477735", "nome_razaosocial": "Maria Souza" }
}
```

#### D) Status que força **transbordo** (ex: `cancelado` → retenção)

```json
{
  "lead_id": 1234,
  "status_lead": "cancelado",
  "proximo_passo": "transbordo_retencao",
  "proxima_pergunta_id": "",
  "deve_perguntar": false,
  "deve_transbordar": true,
  "motivo": "Cliente cancelado — retenção",
  "mensagem_inicial": "Vou te transferir pra nossa equipe...",
  "intent_detectado": "",
  "dados_ja_coletados": {}
}
```

#### E) **Falha ao criar lead** → transbordo de erro

```json
{
  "lead_id": null,
  "status_lead": "erro",
  "proximo_passo": "ser_5",
  "proxima_pergunta_id": "",
  "deve_perguntar": false,
  "deve_transbordar": true,
  "motivo": "Não foi possível criar lead — transbordando",
  "mensagem_inicial": "Vou te transferir pra um atendente.",
  "intent_detectado": "",
  "dados_ja_coletados": {}
}
```

#### F) **Falha transitória** ao consultar lead (ex: 503) → pede retry

```json
{
  "lead_id": 1234,
  "status_lead": "erro_consulta_transitorio",
  "proximo_passo": "msg_pergunta",
  "proxima_pergunta_id": "",
  "deve_perguntar": true,
  "deve_transbordar": false,
  "motivo": "Falha transitória ao consultar lead — solicita retry",
  "mensagem_inicial": "Tive uma instabilidade aqui agora ##1f615##\n\nPode mandar sua última mensagem de novo? ##1f64f##",
  "intent_detectado": "",
  "dados_ja_coletados": {}
}
```

> Mapeamento status → nó em `STATUS_ROTAS`: `aguardando_assinatura` → `aguardar_assinatura`/`msg_aguardando_assinatura`; `cancelado` → `transbordo_retencao`/`msg_1`; `transbordo_atendente` → `transbordo_comercial`/`msg_1`.
> O fluxo de **Novo Serviço** (`status=em_fluxo_new_service`) usa uma sequência própria (`SEQUENCIA_NEW_SERVICE`) lendo do `NewService` em vez do lead; cumprimento no meio é tratado como abandono e volta ao menu.

---

## 5. `POST /validar-imagem`

Valida **uma única imagem** via OpenAI Vision. Único endpoint que usa IA de fato.
Usado pelo formulário do site `/cadastro/` (feedback em ~3s) e reutilizado pelo WhatsApp.

### 5.1 Request — `ValidarImagemRequest`

| Campo | Tipo | Obrigatório | Descrição |
|---|---|:---:|---|
| `url` | `str` | ✅ | URL pública da imagem (http/https) |
| `descricao` | `str` | ✅ | `selfie_com_doc` \| `frente_doc` \| `verso_doc` |

```json
{ "url": "https://exemplo.com/uploads/selfie.jpg", "descricao": "selfie_com_doc" }
```

### 5.2 Response — `ValidarImagemResponse`

| Campo | Tipo | Descrição |
|---|---|---|
| `aprovado` | `bool` | Imagem passou |
| `motivo_codigo` | `str` | Código (ex: `ok`, `documento_ilegivel`, `sem_rosto`) |
| `motivo_humano` | `str` | Explicação legível |
| `msg_refoto` | `str` | Mensagem amigável para pedir nova foto (quando rejeitado) |

**Aprovado:**
```json
{ "aprovado": true, "motivo_codigo": "ok", "motivo_humano": "Selfie com documento legível", "msg_refoto": "" }
```

**Rejeitado:**
```json
{
  "aprovado": false,
  "motivo_codigo": "documento_ilegivel",
  "motivo_humano": "Não consegui ler os dados do documento",
  "msg_refoto": "A foto ficou um pouco embaçada 😅 Pode tirar de novo num lugar mais iluminado?"
}
```

---

## 5b. `POST /recontato` — reengajamento no tempo de espera

Chamado pelo Matrix no ramo **"tempo de espera"** (cliente não respondeu). Em vez de
encerrar, devolve uma mensagem de reengajamento **escalonada** (diferente a cada
silêncio consecutivo, personalizada com o 1º nome). Após `max_tentativas` (3), devolve
`acao='encerrar'` com a despedida **uma única vez** e, dos próximos silêncios em diante,
`acao='encerrar'` com `mensagem` **vazia** (pausa silenciosa). O contador zera sozinho
quando o cliente responde (reset no `/validar`).

**Request** (`RecontatoRequest`):

```json
{ "cellphone": "5586999998888", "lead_id": 74, "pergunta_id": "coleta_cpf" }
```

`lead_id` e `pergunta_id` são opcionais — só `cellphone` já basta para escalar.

**Response** (`RecontatoResponse`):

```json
{
  "acao": "recontatar",        // ou "encerrar"
  "tentativa": 1,
  "max_tentativas": 3,
  "mensagem": "Oi, Maria! Vi que você parou por aqui. Ainda consigo te ajudar? ...",
  "mensagem_safe": "…sem quebras de linha…",
  "reperguntar": false,        // true só na última tentativa (opcional)
  "pergunta_id": "coleta_cpf",
  "deve_transbordar": false
}
```

**Wiring Matrix:** no ramo *tempo de espera* → `POST /recontato`. Se
`acao == "recontatar"` → envia `mensagem` e **volta a aguardar a resposta da pergunta
pendente** (para a resposta cair no `/validar` e ser aproveitada). Se
`acao == "encerrar"` → nó de encerramento/pausa (envie `mensagem` só se não-vazia).
Os textos são configuráveis na aba **Mensagens do Robô** (`recontato_1..3`,
`recontato_despedida`).

---

## 6. Endpoints auxiliares e legados

| Método | Rota | Uso | Retorno |
|---|---|---|---|
| `GET` | `/` | Health check | `{status, versao, persona, modelo_ia, erros_config, regras_stats, fluxos_yaml_legados}` |
| `POST` | `/admin/invalidar-cache/` | Callback do Django ao editar regra **ou mensagem** (recarrega regras E mensagens do robô) | `{"ok": true}` |
| `GET` | `/ia_validador/api/mensagens-robo/` (Django) | Mensagens configuráveis (chave→texto) que o engine lê e cacheia | `{mensagens:[{chave, texto, ativo}], total}` |
| `GET` | `/regras` | Debug: dump do cache de regras | `{stats, regras:[{question_id, extractor, campo, pergunta}]}` |
| `POST` | `/validar/matrix` | Legado N8N `{question, answer, telefone}` | Remapeado p/ `/validar` (mesmo schema da §3.2) |
| `POST` | `/validar/etapa` | Legado YAML (deprecated) | Formato do validador antigo |
| `POST` | `/conversar` | Legado modelo dinâmico (deprecated) | — |
| `GET` | `/contexto/{telefone}` | Debug do contexto em memória | `{telefone, etapa_atual, dados_extraidos, historico_count, tentativas, lead_id}` |
| `DELETE` | `/contexto/{telefone}` | Reset do contexto | `{"ok": true}` |
| `GET` | `/fluxos` | Lista fluxos YAML legados | `{fluxos:[...]}` |
| `GET` | `/fluxos/{nome}` | Obtém fluxo YAML | objeto do fluxo ou `404` |

**Exemplo `GET /`:**
```json
{
  "status": "ok",
  "versao": "2.0.0",
  "persona": "Mel",
  "modelo_ia": "gpt-4o-mini",
  "erros_config": [],
  "regras_stats": {
    "regras_em_cache": 27,
    "inferencias_em_cache": 4,
    "ultima_carga_h_atras": 0.12,
    "ttl_segundos": 300
  },
  "fluxos_yaml_legados": ["vendas_megalink"]
}
```

---

## 7. Referência: extractors

Cada regra define um `extractor_tipo`. O extractor decide `valido`,
`extracted_data` e `motivo_invalido`. (`ia_validacao/src/regras/engine.py`)

| `extractor_tipo` | Válido → `extracted_data` | Inválido → `motivo_invalido` |
|---|---|---|
| `cpf` | `{cpf_cnpj}` (regex + dígito verificador) | `cpf_nao_identificado`, `cpf_invalido` |
| `cep` | `{cep, rua, bairro, cidade, estado}` (ViaCEP) | `cep_nao_identificado`, `cep_nao_existe` |
| `nome` | `{nome_razaosocial}` | `nome_invalido` |
| `telefone` | `{telefone}` | `telefone_invalido` |
| `data_nascimento` | `{data_nascimento}` (valida ≥ 18 anos) | `data_invalida` |
| `email` | `{email}` (lowercase) | `email_vazio`, `email_invalido` |
| `numero` | `{numero_residencia}` (aceita `S/N`) | `numero_vazio`, `numero_invalido` |
| `opcao` | `{opcao: <valor>}` (match em `extractor_config.opcoes`) | `opcao_nao_reconhecida` |
| `confirmacao` | `{confirmacao: true\|false}` | `confirmacao_ambigua` |
| `imagem` | `{url_imagem}` (URL direta ou filename → URL Matrix) | `imagem_nao_recebida` |
| `texto_livre` | `{valor}` | `resposta_vazia` |
| `livre` | `{valor}` (sempre válido, mesmo vazio) | — (nunca falha) |

**Detalhes de matching:**
- `opcao`: aliases curtos (≤3 chars, ex `"1"`, `"sim"`) exigem match **exato**
  (evita `"1"` casar dentro de `"64011-852"`); aliases longos (`"casa"`, `"manha"`)
  aceitam substring na resposta. Config: `{"opcoes": {"manha": ["1","manhã"], "tarde": ["2","tarde"]}}`.
- `confirmacao`: trata `1/s/sim/ok/yes` = `true`; `2/n/não/nao/no` = `false`;
  detecta negação por palavras (`corrigir`, `errado`, `trocar`…) **antes** de
  afirmação (para `"não está correto"` não cair em "correto").
- `imagem`: aceita URL `http(s)` direta, ou filename com extensão de imagem
  (`.jpg/.png/.webp/...`) que vira URL do Matrix.

---

## 8. Referência: sequência de coleta (mapa do fluxo)

Ordem em que `/proximo-passo` pede os campos do **fluxo de vendas residencial**
(`SEQUENCIA_COLETA`). Cada item = `(campo_lead, question_id, identifier_no_matrix)`.

| # | Campo do lead | `question_id` | Observação |
|---|---|---|---|
| 1 | `cpf_cnpj` | `coleta_cpf` | Primeiro — detecta cliente Hubsoft existente |
| 2 | `nome_razaosocial` | `coleta_nome` | Nome genérico/1 palavra é tratado como "não coletado" |
| 3 | `data_nascimento` | `coleta_data_nascimento` | Valida ≥ 18 |
| 4 | `email` | `coleta_email` | |
| 5 | `tipo_imovel` | `tipo_imovel` | `empresa` → transbordo |
| 6 | `cep` | `coleta_cep` | ViaCEP preenche cidade/rua/bairro |
| 7 | `endereco_confirmado` | `confirmacao_endereco` | Confirma dados do ViaCEP |
| 8–10 | `cidade` / `bairro` / `rua` | `coleta_cidade/bairro/rua` | Só se **não** confirmou o ViaCEP |
| 11 | `numero_residencia` | `coleta_numero` | |
| 12 | `tipo_residencia` | `coleta_tipo_residencia` | Só se `tipo_imovel=casa` |
| 13 | `ponto_referencia` | `coleta_ponto_referencia` | |
| 14 | `id_plano_rp` | `escolha_plano` | |
| 15 | `plano_confirmado` | `confirmacao_plano` | Negar limpa o plano e repergunta |
| 16 | `id_dia_vencimento` | `dia_vencimento` | |
| 17 | `dados_confirmados` | `confirmacao_dados` | Revisão final antes dos documentos |
| 18 | `doc_selfie_recebida` | `documentacao_selfie` | → usa `/validar-imagem` |
| 19 | `doc_frente_recebida` | `documentacao_frente_doc` | |
| 20 | `doc_verso_recebida` | `documentacao_verso_doc` | |
| 21 | `turno_instalacao` | `escolha_turno` | |
| 22 | `data_instalacao` | `escolha_data` | Dispara abertura de atendimento + OS |

> Há ainda `SEQUENCIA_NEW_SERVICE` (clientes Hubsoft que escolhem "contratar novo
> serviço" no menu), com lógica equivalente lendo do `NewService`.

---

## 9. Referência: status_api do lead

Valores de `status_api` que `/proximo-passo` interpreta:

| `status_api` | Comportamento |
|---|---|
| *(vazio)* / lead novo | `lead_novo` → inicia coleta pelo CPF |
| `pendente` | Estado transitório (signal do Django cadastra prospecto) |
| `cliente_ativo` | Menu de cliente existente |
| `instalacao_agendada` | Menu de cliente existente |
| `em_fluxo_new_service` | Fluxo de Novo Serviço (sequência própria) |
| `aguardando_assinatura` | Nó `aguardar_assinatura` (sem OS ainda) |
| `aguardando_finalizacao` | Próxima volta pergunta finalizar/voltar |
| `atendimento_concluido` | Cliente voltou → reverte status conforme dados |
| `cancelado` | Transbordo de retenção |
| `transbordo_atendente` | Transbordo comercial |

---

## 10. Logging de interações

Toda chamada a `/validar`, `/proximo-passo` e `/validar-imagem` dispara, em
**background** (thread daemon, sem impactar latência), um `POST` para o Django:

```
POST /api/ia/log-interacao/
```

Body enviado (campos opcionais — o que vier é gravado):

```json
{
  "endpoint": "validar",
  "cellphone": "5564999998888",
  "lead_id": 1234,
  "question_id": "coleta_cpf",
  "answer": "111.444.777-35",
  "mensagem_resposta": "",
  "payload_in":  { "...request completo..." },
  "payload_out": { "...response completo..." },
  "duracao_ms": 87,
  "valido": true,
  "transbordou": false,
  "motivo": ""
}
```

Resposta do Django: `{"ok": true, "id": 9876}` (ou `{"ok": false, "erro": "..."}`
com `200` — o log **nunca** derruba o caller). Persistido em `LogInteracaoIA`
(`endpoint` ∈ `validar` | `proximo-passo` | `validar-imagem` | `new_service` | `conv-turno`).

---

*Gerado a partir de `ia_validacao/src/app.py`, `ia_validacao/src/regras/engine.py`,
`ia_validacao/src/onboarding.py` e `dashboard_comercial/.../ia_validador/`.*
