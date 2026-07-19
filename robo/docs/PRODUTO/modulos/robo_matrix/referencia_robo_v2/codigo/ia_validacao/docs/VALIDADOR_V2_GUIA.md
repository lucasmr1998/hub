# 📘 Validador V2 — Guia operacional

## Como funciona

```
┌────────────┐       POST /ia/validar         ┌──────────────────┐
│  Matrix    │ ───────────────────────────▶   │   API IA         │
│ (flow.json)│   {question, answer,           │   (FastAPI)      │
│            │    cellphone, lead_id,         │                  │
│            │    question_id?}               │                  │
│            │                                │                  │
│            │ ◀───────────────────────────   │                  │
└────────────┘    {valido, extracted_data,    └────────┬─────────┘
                   message, transbordo, …}             │
                                                        │ (background)
                                                        ▼
                                            ┌────────────────────────┐
                                            │ Django:                │
                                            │  • /api/leads/atualizar/│
                                            │  • /api/leads/status/  │
                                            │  • /api/leads/tags/    │
                                            │  • /api/historicos/    │
                                            │  • /api/leads/imagens/ │
                                            └────────────────────────┘
```

## O `RegraValidacao` (Django admin)

Cada pergunta do fluxo tem uma linha nesta tabela. Acesse em:

**https://robovendas.megalinkpiaui.com.br/admin/ia_validador/regravalidacao/**

Campos principais:

| Campo | Descrição |
|-------|-----------|
| `question_id` | Identificador único (slug). Ex: `coleta_cpf`. O Matrix envia esse valor no payload. |
| `pergunta_padrao` | Texto da pergunta no Matrix (referência + fallback de matching) |
| `extractor_tipo` | Como validar: `cpf`, `cep`, `nome`, `email`, `data_nascimento`, `opcao`, `imagem`, `confirmacao`, `texto_livre`, `numero` |
| `extractor_config` | JSON com config extra. Ex: `{"opcoes": {"casa": ["casa","residencial"], "empresa": ["empresa"]}}` |
| `campo_lead_atualizar` | Nome do campo do `LeadProspecto` a atualizar (ex: `cpf_cnpj`) |
| `status_api_apos_sucesso` | Se preenchido, dispara mudança de `status_api` no Lead após validar |
| `tags_adicionar` | Lista JSON: `["Comercial", "Endereço"]` — adicionado via `/api/leads/tags/` |
| `historico_status_apos_sucesso` | Se preenchido, registra `HistoricoContato` com esse status |
| `descricao_imagem` | Para `extractor_tipo=imagem`: ex `selfie_com_doc`, `frente_doc`, `verso_doc` |
| `msg_sucesso` / `msg_erro` / `msg_max_tentativas` | Mensagens enviadas ao cliente |
| `max_tentativas` | Quantas tentativas falhas antes de transbordar |
| `forcar_transbordo_apos_max` | Se `True`, ao exceder tentativas marca `transbordo=true` no response |

### Como cadastrar uma pergunta nova

1. Entre no admin Django, clique **Adicionar Regra de Validação**
2. Preencha `question_id` (algo curto e descritivo: `coleta_estado_civil`)
3. Escreva o `pergunta_padrao` (texto exato no Matrix)
4. Escolha o `extractor_tipo` adequado
5. Configure ações:
   - Vai gravar em algum campo do lead? → `campo_lead_atualizar = nome_do_campo`
   - Tem tag a adicionar? → `tags_adicionar = ["NomeDaTag"]`
   - Muda status? → `status_api_apos_sucesso = "novo_status"`
6. **Salve.** Pronto — a API IA recebe a notificação automaticamente e invalida o cache.

No flow.json do Matrix, basta antes do `sol_*` correspondente:
- Setar `question_id_atual = "coleta_estado_civil"`

## Endpoint principal

### POST `/ia/validar`

**Request:**
```json
{
  "question": "Qual seu CPF?",
  "answer": "529.982.247-25",
  "cellphone": "5586999999999",
  "lead_id": 2057,
  "question_id": "coleta_cpf"
}
```

**Response:**
```json
{
  "valido": true,
  "extracted_data": {"cpf_cnpj": "52998224725"},
  "message": "Anotei!",
  "motivo_invalido": "",
  "intent": "",
  "transbordo": false,
  "fim_fluxo": false,
  "actions_executed": [{"tipo": "agendado_background", "ok": true}],
  "regra_aplicada": "coleta_cpf",
  "tentativas": 0,
  "usou_ia": false,
  "confianca": 1.0
}
```

### Outros endpoints

| Endpoint | Função |
|----------|--------|
| `GET /` | Health check + stats |
| `GET /regras` | Debug — lista regras em cache |
| `POST /admin/invalidar-cache/` | Callback do Django (interno) |
| `POST /validar/matrix` | Legado — compat antigo `{question, answer, telefone}` |
| `POST /validar/etapa` | Legado — modelo por etapa do YAML |
| `POST /conversar` | Legado — modo dinâmico |
| `GET /contexto/{telefone}` | Debug — estado da conversa |
| `DELETE /contexto/{telefone}` | Reset (testes) |

## Configuração do flow.json do Matrix

### Para cada `sol_*` (pergunta) no Matrix:

1. **Antes** do `sol_*`, adicione um nó `set var` que defina `{#question_id_atual}` = o `question_id` da regra correspondente.

   Exemplo antes de `sol_cpf`:
   ```
   set: question_id_atual = "coleta_cpf"
   ```

2. **Depois** do `sol_*`, o nó `api` (validador) chama o endpoint:

   ```
   URL: https://robovendas.megalinkpiaui.com.br/ia/validar
   método: POST
   body: {
     "question": "{#pergunta_cliente}",
     "answer": "{#resposta_cliente}",
     "cellphone": "{#CONTATO.TELEFONE}",
     "lead_id": {#id_lead},
     "question_id": "{#question_id_atual}"
   }
   store filter=1:
     $.valido → resp_valido
     $.message → resp_message
     $.transbordo → resp_transbordo
     $.intent → resp_intent
     $.regra_aplicada → resp_regra
   ```

3. **Decisão pós-API**:
   - Se `resp_transbordo == true` → encaminha para `ser_humano`
   - Se `resp_valido == false` → repete a mesma pergunta usando `resp_message` como mensagem de erro
   - Senão → segue pra próxima pergunta do fluxo

## Variáveis Matrix que precisam existir

| Nome | Função |
|------|--------|
| `question_id_atual` | ID da regra (setado antes de cada sol) |
| `id_lead` | ID do lead no Django (preenchido após `/api/leads/registrar/`) |
| `pergunta_cliente` | Texto da pergunta feita ao cliente |
| `resposta_cliente` | `{#MENSAGEM}` — resposta do cliente |
| `resp_valido` | Captura `$.valido` |
| `resp_message` | Captura `$.message` (mensagem pro cliente) |
| `resp_transbordo` | Captura `$.transbordo` |
| `resp_intent` | Captura `$.intent` |
| `resp_regra` | Captura `$.regra_aplicada` (debug) |

## Como adicionar uma ação nova (avançado)

Hoje suportamos: `atualizar_lead`, `atualizar_status`, `adicionar_tags`, `registrar_historico`, `registrar_imagem`.

Para adicionar uma nova ação (ex: `enviar_email`):

1. Adicione um campo no `RegraValidacao` (ex: `enviar_email_para`)
2. Crie migration
3. No `src/regras/engine.py:_aplicar_acoes_background`, adicione o branch que executa a ação
4. Adicione o método correspondente em `src/integracoes/robovendas.py`
5. Reinicie a API (`sudo systemctl restart ia-validacao`)

## Debug

```bash
# Logs em tempo real
sudo journalctl -u ia-validacao -f

# Ver regras em cache
curl http://localhost:8090/regras | python3 -m json.tool

# Forçar refresh do cache
curl -X POST http://localhost:8090/admin/invalidar-cache/

# Estado de uma conversa
curl http://localhost:8090/contexto/5586999999999

# Reset
curl -X DELETE http://localhost:8090/contexto/5586999999999
```

## Rate limit

O nginx tem rate limit `30r/min` na zone `api`. Em uso real (1 cliente respondendo a cada 5-10s) isso não é problema. Em testes rápidos, sim — o client httpx faz retry com backoff 0.5/1/2s pra absorver picos. Se virar gargalo em produção, aumentar `rate=300r/m` na conf nginx.
