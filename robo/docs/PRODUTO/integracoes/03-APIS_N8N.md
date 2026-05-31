# 16. APIs para Agentes e N8N

**Ultima atualizacao:** 31/05/2026
**Status:** ✅ Em producao

---

## Autenticacao

Todas as APIs usam token Bearer no header:

```
Authorization: Bearer qB0L0dkBULVQd6KlMlg24HV1hGxxQqIoFUrzZVN6yEU
```

Base URL: `http://127.0.0.1:8001` (dev) ou `https://app.dominio.com.br` (producao)

---

## APIs disponiveis

### Leads

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | `/api/v1/n8n/leads/` | Criar lead |
| PUT | `/api/v1/n8n/leads/<id>/` | Atualizar lead |
| GET | `/api/v1/n8n/leads/buscar/?telefone=5586999` | Buscar lead por telefone |

**Criar lead:**
```json
POST /api/v1/n8n/leads/
{
    "nome_razaosocial": "Joao Silva",
    "telefone": "5586999001234",
    "email": "joao@email.com",
    "origem": "whatsapp"
}
```

**Atualizar lead:**
```json
PUT /api/v1/n8n/leads/61/
{
    "nome_razaosocial": "Joao Silva Santos",
    "cidade": "Teresina",
    "estado": "PI",
    "score_qualificacao": 8
}
```

---

### CRM — Pipelines e Estagios

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/api/v1/n8n/crm/pipelines/` | Listar pipelines com estagios |
| GET | `/api/v1/n8n/crm/estagios/?pipeline_slug=matriculas` | Listar estagios (filtro opcional) |

---

### CRM — Oportunidades

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | `/api/v1/n8n/crm/oportunidades/` | Criar oportunidade |
| PUT | `/api/v1/n8n/crm/oportunidades/<id>/` | Atualizar (mover estagio, atribuir) |
| GET | `/api/v1/n8n/crm/oportunidades/buscar/?lead_id=61` | Buscar por lead |
| GET | `/api/v1/n8n/crm/oportunidades/buscar/?telefone=5586999` | Buscar por telefone |

**Criar oportunidade:**
```json
POST /api/v1/n8n/crm/oportunidades/
{
    "lead_id": 61,
    "pipeline_slug": "matriculas",
    "estagio_slug": "novo",
    "titulo": "Joao - Direito"
}
```
Nota: se a oportunidade ja existe para o lead, retorna a existente sem duplicar.

**Mover estagio:**
```json
PUT /api/v1/n8n/crm/oportunidades/58/
{
    "estagio_slug": "qualificado"
}
```

**Atribuir responsavel:**
```json
PUT /api/v1/n8n/crm/oportunidades/58/
{
    "responsavel_username": "aurora"
}
```

---

### CRM — Tarefas

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | `/api/v1/n8n/crm/tarefas/` | Criar tarefa |
| PUT | `/api/v1/n8n/crm/tarefas/<id>/` | Atualizar/concluir tarefa |

**Criar tarefa:**
```json
POST /api/v1/n8n/crm/tarefas/
{
    "lead_id": 61,
    "titulo": "Ligar para Joao sobre Direito",
    "tipo": "ligacao",
    "prioridade": "alta"
}
```
Tipos: ligacao, whatsapp, email, visita, followup, proposta, instalacao, suporte, outro
Prioridades: baixa, normal, alta, urgente

**Concluir tarefa:**
```json
PUT /api/v1/n8n/crm/tarefas/77/
{
    "status": "concluida",
    "resultado": "Lead interessado em Direito noturno"
}
```

---

### Inbox — Mensagens

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| POST | `/api/v1/n8n/inbox/mensagem-recebida/` | Registrar mensagem recebida do contato |
| POST | `/api/v1/n8n/inbox/enviar/` | Enviar mensagem como bot |

**Registrar mensagem recebida (do WhatsApp para nosso sistema):**
```json
POST /api/v1/n8n/inbox/mensagem-recebida/
{
    "telefone": "5586999001234",
    "nome": "Joao Silva",
    "conteudo": "Ola, quero saber sobre o curso de Direito",
    "canal_tipo": "whatsapp"
}
```

**Enviar mensagem como bot (do nosso sistema para o WhatsApp via N8N):**
```json
POST /api/v1/n8n/inbox/enviar/
{
    "telefone": "5586999001234",
    "conteudo": "Ola Joao! O curso de Direito funciona das 18h30 as 21h40. Qual forma de ingresso te interessa?",
    "remetente_nome": "Pedro"
}
```

---

## Fluxo N8N recomendado para a faculdade

```
1. Webhook Uazapi (WhatsApp mensagem recebida)
        |
2. POST /api/v1/n8n/inbox/mensagem-recebida/    ← registra no nosso Inbox
        |
3. POST /api/v1/n8n/leads/                       ← cria/busca lead
        |
4. POST /api/v1/n8n/crm/oportunidades/           ← cria oportunidade (nao duplica)
        |
5. Agente IA (OpenAI) processa a mensagem
        |
6. Se agente decide salvar dados:
   PUT /api/v1/n8n/leads/<id>/                    ← atualiza nome, curso, etc.
   PUT /api/v1/n8n/crm/oportunidades/<id>/        ← move estagio
        |
7. POST /api/v1/n8n/inbox/enviar/                ← registra resposta no nosso Inbox
        |
8. Uazapi envia resposta no WhatsApp
```

---

## Matrix — Agendamento e abertura de OS (clientes Nuvyon, FATEPI, etc.)

Endpoints consumidos pelo **bot Matrix** (n8n externo) para substituir a camada
`apimatrix.<provedor>` que ficava fora do Hubtrix. A logica de orquestracao
(agenda, atendimento, OS) agora vive aqui, falando direto com o HubSoft do
tenant.

**Base path:** `/api/public/n8n/matrix/`
**Auth:** Bearer token da `IntegracaoAPI` tipo `n8n` ativa do tenant
(o decorator `api_token_required` resolve `request.tenant` a partir do token).

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/matrix/datas-sem-domingo/` | Proximas N datas de instalacao pulando domingos (logica pura, sem HubSoft) |
| GET | `/matrix/consultar-agenda/` | Horarios disponiveis numa agenda HubSoft para uma data/turno |
| POST | `/matrix/abrir-atendimento/` | Abre atendimento no HubSoft (sem OS) |
| POST | `/matrix/abrir-os/` | Abre OS a partir do atendimento + slot escolhido |

**Configuracao por tenant.** Cada tenant que usa Matrix precisa ter sua
`IntegracaoAPI` HubSoft com o bloco `os_matrix` em `configuracoes_extras`:

```json
{
  "os_matrix": {
    "id_agenda_ordem_servico": 46,
    "id_tipo_atendimento": 281,
    "id_status_atendimento": 1,
    "id_tipo_os": 4,
    "status_os": "pendente",
    "id_usuario_responsavel": null
  }
}
```

Os IDs vem do painel HubSoft do cliente (agenda, tipos de atendimento, etc.).

### Detalhes dos endpoints

**`GET /matrix/datas-sem-domingo/?data_referencia=DD/MM/YYYY&qtd=5&offset_dias=1`**
Retorna as proximas `qtd` datas a partir de `data_referencia + offset_dias`,
pulando domingos. Default: `qtd=5`, `offset_dias=1`. Logica pura, nao chama
HubSoft. O Matrix le `datas[0]/[1]/[2]` pra `data_instalacao_1/2/3`.

```json
{"status": "success", "datas": ["02/06/2026", "03/06/2026", "04/06/2026", "05/06/2026", "06/06/2026"]}
```

**`GET /matrix/consultar-agenda/?data_referencia=DD/MM/YYYY&turno=manha|tarde|noite`**
Horarios disponiveis na agenda configurada (`id_agenda_ordem_servico`) pra
data/turno. Faixas de turno: manha (0-12h), tarde (12-18h), noite (18-24h).

```json
{"status": "success", "dados": {
  "id_agenda_ordem_servico": 46,
  "disponibilidade_turno": [
    {"horario": "07:00:00", "tecnicos": [{"id": 258}, {"id": 132}]},
    {"horario": "08:00:00", "tecnicos": [{"id": 144}]}
  ]
}}
```

**`POST /matrix/abrir-atendimento/`** — body JSON:
```json
{
  "id_cliente_servico": 12345,
  "nome": "Joao Silva",
  "telefone": "34999990000",
  "descricao": "Solicitacao via Matrix",
  "email": "joao@example.com"
}
```
Tipos/status/responsavel vem do `os_matrix` config. Resposta:
`{"status": "success", "atendimento": {"id_atendimento": N, ...}}`.

**`POST /matrix/abrir-os/`** — body JSON:
```json
{
  "id_atendimento": 9876,
  "data_inicio_programado": "2026-06-05",
  "data_termino_programado": "2026-06-05",
  "hora_inicio_programado": "08:00:00",
  "hora_termino_programado": "09:00:00",
  "tecnicos": [258],
  "disponibilidade": ["manha"]
}
```
`id_tipo_ordem_servico`, `status` e `id_agenda_ordem_servico` vem do
`os_matrix` config (com override pelo body). Resposta:
`{"status": "success", "ordem_servico": {...}}`.

### Coercao de tipos (normalizacao defensiva)

`tecnicos` e `disponibilidade` aceitam **lista, string ou int** — o view
embrulha em lista antes de chamar o `HubsoftService` via `_coerce_lista()`.
Sem isso, `enumerate('manha')` explodia a string char-por-char e o HubSoft
recebia `{"0":"m","1":"a","2":"n","3":"h","4":"a"}` no payload. Aceita:

```json
"tecnicos": [258]      // OK (default)
"tecnicos": 258         // OK (coercao -> [258])
"disponibilidade": ["manha"]   // OK (default)
"disponibilidade": "manha"     // OK (coercao -> ["manha"])
```

### Codigos de erro

- **400** — erro de validacao local (`id_atendimento obrigatorio`,
  `Integracao HubSoft nao configurada`) OU erro do HubSoft repassado
  (permissao, payload invalido).
- **401** — token ausente/invalido.

> **Por que 4xx mesmo pra erro HubSoft.** O proxy do **EasyPanel** intercepta
> qualquer resposta 5xx do backend e substitui o body pela sua propria pagina
> HTML "Service is not reachable". Como o cliente (Matrix) espera JSON, todos
> os catches de `HubsoftServiceError` retornam **400** com `{"status":"error","msg":...}`
> em vez de 502 — assim o body chega intacto.

### Permissoes HubSoft requeridas

A credencial HubSoft do tenant precisa ter as permissoes abaixo liberadas no
**painel de Usuarios da API** do HubSoft:

- Consultar agenda de ordem de servico
- **Criar atendimento** (necessaria pra `/abrir-atendimento/`)
- **Abrir ordem de servico** (necessaria pra `/abrir-os/`)

Se faltar permissao, o HubSoft retorna `403` com `"O Usuário não possui a permissão desejada!"`
e o endpoint nosso responde 400 com essa mensagem no `msg`.

### Logs

Cada chamada ao HubSoft gera 1 registro em `logs_integracao` com payload
enviado e resposta crua — util pra debugar erros de permissao/payload.
Filtrar por tenant + endpoint (`/api/v1/integracao/atendimento`, etc.).

---

## Base de conhecimento — registro de duvidas (Matrix / agentes LLM)

Quando um bot externo (Matrix, N8N agente LLM) recebe uma pergunta que nao
consegue responder, deve **registrar a duvida** pra alimentar a curadoria da
base de conhecimento. As perguntas viram registros em `PerguntaSemResposta`
(tabela `suporte_perguntas_sem_resposta`) — depois um humano transforma em
artigo via `/suporte/conhecimento/perguntas/`.

**`POST /api/public/n8n/conhecimento/registrar-pergunta/`**

Body JSON:
```json
{
  "pergunta": "qual o valor do plano 500MB?",
  "lead_id": 462,         // opcional — vincula a um lead
  "conversa_id": 312      // opcional — vincula a uma conversa do Inbox
}
```

Resposta `200`:
```json
{
  "status": "success",
  "criada": true,         // true = nova; false = incrementou ocorrencias de uma similar
  "pergunta_id": 28,
  "ocorrencias": 3
}
```

**Deduplicacao.** O endpoint nao cria duplicata: extrai o **primeiro termo
significativo** (>=3 chars, fora das stop-words PT) da pergunta e busca
`PerguntaSemResposta` pendente do mesmo tenant cujo texto contenha esse
termo. Se acha, incrementa `ocorrencias`; senao, cria nova. Lead/conversa
sao atualizados na existente se ela ainda nao tinha.

> **Limite v1:** dedup por "primeiro termo significativo" e primitivo —
> "quanto custa X" e "qual valor Y" nao sao detectados como similares. Em v2
> (com embeddings) substituimos por similaridade semantica.

Erros:
- `400` — `pergunta` ausente / menor que 3 chars / tenant nao resolvido.
- `401` — token ausente/invalido.

---

## Atendimento — telemetria de erros de resposta no fluxo do bot

Distinto de `/conhecimento/registrar-pergunta/`: la captura **duvida livre do
cliente** (lacuna na base de conhecimento). Aqui captura **fricao no fluxo
da maquina de estados** — bot perguntou X, cliente respondeu Y errado.
Alimenta calibracao do fluxo (copy, validacao, exemplos).

**Modelo:** `MotivoErroResposta` em `apps.comercial.atendimento`. Substitui o
INSERT direto na tabela externa `motivo-erro` (Postgres `atendimento-ai`)
que os flows antigos do Matrix usam. Migrar pra ca centraliza no Hubtrix
(multi-tenant, painel, metricas).

**`POST /api/public/n8n/atendimento/registrar-erro-resposta/`**

Body JSON:
```json
{
  "pergunta_bot": "qual seu CPF?",
  "resposta_cliente": "12345",
  "no_fluxo": "ColetaCPF",     // opcional — nome/slug do node do bot
  "canal": "whatsapp",          // opcional — origem
  "lead_id": 462,               // opcional
  "conversa_id": 312            // opcional
}
```

Resposta `200`:
```json
{
  "status": "success",
  "criada": true,
  "erro_id": 17,
  "ocorrencias": 1
}
```

**Deduplicacao:** combinacao **exata** (case-insensitive, whitespace trimado)
de `(pergunta_bot, resposta_cliente, no_fluxo?)` no mesmo tenant, com
`resolvido=False`. Mesma combinacao volta → incrementa `ocorrencias`. Como
as duas strings sao curtas e estruturadas (pergunta vem do bot, resposta
e curta), match exato e o criterio certo aqui.

Erros:
- `400` — `pergunta_bot` ou `resposta_cliente` ausentes/vazios.
- `401` — token ausente/invalido.

---

## Orquestrador Vero (TR Carrion) — coleta de documentos

O fluxo `[Vero] Orquestrador Atendimento` coleta RG/CNH frente e verso no
cadastro. A validacao (`ValidarImagemRGFrente/Verso`) aceita **foto (imagem)
OU arquivo PDF** — a CNH digital (e-CNH) e PDF nato, exigir foto fisica era
friccao desnecessaria.

O node `Entrada` extrai `conteudo_inbox` (label limpo) e `tipo_midia` a partir
do payload Uazapi, e nunca repassa o objeto de midia cru. O `RegistrarMsgCliente`
envia esse label + `tipo_conteudo` + `arquivo_nome` pro
`POST /api/public/n8n/inbox/mensagem/`, evitando JSON cru no balao do Inbox.

---

## Respostas

Todas as APIs retornam JSON com `success: true/false`. Em caso de erro:

```json
{
    "success": false,
    "error": "Descricao do erro"
}
```

Ou para erros de validacao:

```json
{
    "success": false,
    "errors": {
        "campo": ["mensagem de erro"]
    }
}
```
