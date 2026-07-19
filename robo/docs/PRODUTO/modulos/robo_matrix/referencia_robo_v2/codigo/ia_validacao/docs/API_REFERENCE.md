  # 📡 API IA Validação — Referência completa

  > Documentação técnica da API que valida respostas do cliente no fluxo Matrix e dispara
  > ações em background no Django (atualizar lead, adicionar tags, registrar histórico, etc).

  ---

  ## 🌐 URLs

  | Ambiente   | URL base                                            |
  |------------|-----------------------------------------------------|
  | Produção   | `https://robovendas.megalinkpiaui.com.br/ia`        |
  | Local dev  | `http://localhost:8090`                             |

  > O **nginx** faz reverse proxy de `/ia/*` → `http://localhost:8090/*` no servidor de produção.

  ---

  ## 🗂 Endpoints disponíveis

  | Método | Caminho                          | Função                                          |
  |--------|----------------------------------|-------------------------------------------------|
  | GET    | `/`                              | Health check + stats                            |
  | POST   | `/proximo-passo`                 | **Roteador inicial** — decide pra onde mandar o cliente |
  | POST   | `/validar`                       | **Endpoint principal** — valida resposta        |
  | POST   | `/validar/matrix`                | Legado N8N (`{question, answer, telefone}`)     |
  | POST   | `/validar/etapa`                 | Legado fluxo YAML (deprecated)                  |
  | POST   | `/conversar`                     | Legado modelo dinâmico (deprecated)             |
  | POST   | `/admin/invalidar-cache/`        | Callback do Django ao editar regra              |
  | GET    | `/regras`                        | Debug — lista regras em cache                   |
  | GET    | `/contexto/{telefone}`           | Debug — estado da conversa                      |
  | DELETE | `/contexto/{telefone}`           | Reset estado (limpa tentativas)                 |
  | GET    | `/fluxos`                        | Legado — lista YAMLs                            |
  | GET    | `/fluxos/{nome}`                 | Legado — obtém YAML                             |

  ---

  ## 🚦 Endpoint de roteamento — `POST /proximo-passo`

  > Chamado **uma vez** quando o cliente entra no fluxo. Decide pra onde o Matrix
  > deve direcioná-lo: começar venda, retomar de onde parou, transbordar, etc.

  ### Request

  ```http
  POST /ia/proximo-passo HTTP/1.1
  Content-Type: application/json
  ```

  | Campo            | Tipo        | Obrigatório | Descrição                                                  |
  |------------------|-------------|-------------|------------------------------------------------------------|
  | `cellphone`      | string      | ✅           | Telefone do contato                                        |
  | `lead_id`        | int \| null | ❌           | ID do lead Django (se já vier do api_8/api_14)             |
  | `ultima_mensagem`| string      | ❌           | Última mensagem do cliente (detecta intent)                |

  **Exemplo:**
  ```json
  {
    "cellphone": "5586999999999",
    "lead_id": 2057,
    "ultima_mensagem": "Quero contratar internet"
  }
  ```

  ### Response

  | Campo                  | Tipo    | Descrição                                                          |
  |------------------------|---------|--------------------------------------------------------------------|
  | `lead_id`              | int     | ID final do lead (criado se não existia)                           |
  | `status_lead`          | string  | `lead_novo`, `em_andamento`, `aguardando_assinatura`, `cancelado`, etc |
  | `proximo_passo`        | string  | **Identifier do nó Matrix** pra onde pular (ex: `msg_cep`, `ser_5`) |
  | `proxima_pergunta_id`  | string  | `question_id` da regra (pra setar `question_id_atual`)             |
  | `deve_perguntar`       | boolean | `true` = continuar coletando, `false` = só notificar/transbordar   |
  | `deve_transbordar`     | boolean | `true` = transferir pra humano                                     |
  | `motivo`               | string  | Explicação humana da decisão                                       |
  | `mensagem_inicial`     | string  | Texto sugerido pra começar (ex: "Oi João! Vamos continuar...")     |
  | `intent_detectado`     | string  | `contratar`, `suporte`, `cancelar`, `financeiro`, `cumprimento`, `` |
  | `dados_ja_coletados`   | object  | Campos do lead já preenchidos (resumo do que tem)                  |

  ### Cenários possíveis (output)

  **1. Cliente totalmente NOVO:**
  ```json
  {
    "lead_id": 3001,
    "status_lead": "lead_novo",
    "proximo_passo": "msg_60",
    "proxima_pergunta_id": "coleta_nome",
    "deve_perguntar": true,
    "deve_transbordar": false,
    "motivo": "Lead novo criado — começar do início",
    "mensagem_inicial": "Oi! Que bom ter você aqui. Pra começar, qual seu nome?",
    "intent_detectado": "contratar",
    "dados_ja_coletados": {}
  }
  ```

  **2. Cliente que VOLTOU (já tem nome + CPF, falta CEP):**
  ```json
  {
    "lead_id": 2057,
    "status_lead": "em_andamento",
    "proximo_passo": "msg_cep",
    "proxima_pergunta_id": "coleta_cep",
    "deve_perguntar": true,
    "deve_transbordar": false,
    "motivo": "Continuar de onde parou — falta: cep",
    "mensagem_inicial": "Oi João! Vamos continuar de onde paramos. Pode me passar o CEP da sua residência?",
    "intent_detectado": "cumprimento",
    "dados_ja_coletados": {
      "nome_razaosocial": "João Silva",
      "cpf_cnpj": "12345678900",
      "cep": "",
      "numero_residencia": "",
      "email": "..."
    }
  }
  ```

  **3. Cliente já é ATIVO no Hubsoft — transbordar:**
  ```json
  {
    "lead_id": 1850,
    "status_lead": "cliente_ativo",
    "proximo_passo": "ser_5",
    "proxima_pergunta_id": "",
    "deve_perguntar": false,
    "deve_transbordar": true,
    "motivo": "Já é cliente ativo",
    "mensagem_inicial": "",
    "intent_detectado": "suporte",
    "dados_ja_coletados": {...}
  }
  ```

  **4. Cliente com instalação JÁ AGENDADA:**
  ```json
  {
    "lead_id": 2057,
    "status_lead": "instalacao_agendada",
    "proximo_passo": "msg_38",
    "proxima_pergunta_id": "",
    "deve_perguntar": false,
    "deve_transbordar": false,
    "motivo": "Instalação já agendada",
    "mensagem_inicial": "",
    "intent_detectado": "",
    "dados_ja_coletados": {...}
  }
  ```

  ### Como usar no Matrix

  1. Coloque o nó API `/ia/proximo-passo` **logo após** `api_14`+`api_8` (criação/garantia do lead).
  2. Armazene `proximo_passo` em uma variável (ex: `{#proximo_passo}`).
  3. Logo após, coloque uma **decisão multi-branch**:
     - `deve_transbordar=true` → transbordo (`ser_5`/`hor_1`)
     - `status_lead=lead_novo` → ir pro **msg_60** (início do fluxo de vendas)
     - `status_lead=instalacao_agendada` → mensagem informativa
     - `status_lead=aguardando_assinatura` → mensagem de "estamos analisando"
     - **Padrão** → red type=2 com `component_identifier="{#proximo_passo}"` (pula pra onde a API mandou)
  4. Antes do jump dinâmico, sete `question_id_atual = {#proxima_pergunta_id}` pra próxima chamada `/ia/validar` saber qual regra usar.

  > 📄 Veja [`fluxos/flow_dinamico_inicio.json`](../fluxos/flow_dinamico_inicio.json)
  > com o template pronto pra colar no Matrix.

  ### Sequência de roteamento por status_api

  | `status_api` do lead         | `proximo_passo` retornado | Ação esperada                              |
  |------------------------------|---------------------------|--------------------------------------------|
  | (vazio / `processamento_manual`) | primeiro campo faltante na sequência (`msg_60`, `msg_cep`, etc) | Continua coleta |
  | `aguardando_assinatura`      | `msg_aguarde`             | "Cadastro em análise"                      |
  | `pendente`                   | `msg_aguarde`             | "Processamento em andamento"               |
  | `instalacao_agendada`        | `msg_38`                  | "Instalação já agendada para {data}"       |
  | `cliente_ativo`              | `ser_5`                   | Transbordo pro suporte                     |
  | `cancelado`                  | `ser_5`                   | Transbordo pra retenção                    |

  **Sequência canônica de coleta** (campos verificados em ordem):
  ```
  nome_razaosocial → cep → numero_residencia → ponto_referencia →
  cpf_cnpj → email → data_nascimento → id_dia_vencimento → (docs)
  ```

  O primeiro campo VAZIO determina o `proximo_passo`.

  ---

  ## 🎯 Endpoint principal — `POST /validar`

  ### Request

  ```http
  POST /ia/validar HTTP/1.1
  Content-Type: application/json
  ```

  **Schema:**

  | Campo         | Tipo            | Obrigatório | Descrição                                                         |
  |---------------|-----------------|-------------|-------------------------------------------------------------------|
  | `question`    | string          | ✅           | Texto da pergunta feita ao cliente                                |
  | `answer`      | string          | ✅           | Resposta do cliente (texto ou URL de imagem)                      |
  | `cellphone`   | string          | ✅           | Telefone do contato (qualquer formato, será normalizado)          |
  | `lead_id`     | int \| null     | ❌           | ID do lead Django. Se não vier, a API cria/busca automaticamente  |
  | `question_id` | string          | ❌           | Slug da regra (ex: `coleta_cpf`). Se vier, lookup direto e rápido |

  **Exemplo:**
  ```json
  {
    "question": "Pode me informar seu CPF?",
    "answer": "529.982.247-25",
    "cellphone": "5586999999999",
    "lead_id": 2057,
    "question_id": "coleta_cpf"
  }
  ```

  > ✅ Sempre envie o mesmo schema. O que varia é o **valor** dos campos.
  > Se você não souber o `question_id`, omita — a API tenta inferir pela `question`.

  ### Response

  **Schema:**

  ```typescript
  {
    // ── Schema V2 (novo) ─────────────────────────────────────────
    valido: boolean,                       // true se passou na validação
    extracted_data: object,                // dados extraídos (varia por extractor)
    message: string,                       // mensagem pra mostrar ao cliente
    motivo_invalido: string,               // código do motivo (ex: "cpf_invalido")
    intent: string,                        // intent detectado (raro — só cumprimento)
    transbordo: boolean,                   // true se deve transferir pra humano
    fim_fluxo: boolean,                    // true se este foi o último passo
    actions_executed: object[],            // log das ações disparadas (informativo)
    regra_aplicada: string,                // question_id da regra usada
    tentativas: integer,                   // quantas tentativas falhas neste passo
    usou_ia: boolean,                      // se caiu no fallback OpenAI
    confianca: float,                      // 0.0 a 1.0

    // ── Schema LEGADO (compat flow Matrix antigo) ────────────────
    answerIsCorrect: "true"|"false",
    resposta_correta: "true"|"false",
    resposta_sem_erro_api: "true"|"false",
    errorMessage: string,
    retorno_erro_api: string,
    isAClient: "true"|"false",
    hasCancelledService: "true"|"false",
    cancelado: "true"|"false",
    needsReception: "true"|"false",
    time_instalacao: string,
    viabilidade_cep: "true"|"false",
    givesServiceToCity: "true"|"false",
    api_cep: string,
    ret_cep: string,
    ret_estado: string,
    ret_cidade: string,
    ret_bairro: string,
    ret_rua: string,
  }
  ```

  > ⚠️ **Sempre retorna o mesmo schema.** O que muda são os valores.
  > Os 18 campos legados existem pra manter compatibilidade com o flow Matrix original
  > (decisões `dec_3`, `dec_4`, `dec_5` ainda leem essas variáveis).

  **Exemplo de resposta — CPF válido:**
  ```json
  {
    "valido": true,
    "extracted_data": { "cpf_cnpj": "52998224725" },
    "message": "CPF validado! ##263A##",
    "motivo_invalido": "",
    "intent": "",
    "transbordo": false,
    "fim_fluxo": false,
    "actions_executed": [{ "tipo": "agendado_background", "ok": true }],
    "regra_aplicada": "coleta_cpf",
    "tentativas": 0,
    "usou_ia": false,
    "confianca": 1.0,

    "answerIsCorrect": "true",
    "resposta_correta": "true",
    "resposta_sem_erro_api": "true",
    "errorMessage": "",
    "retorno_erro_api": "",
    "isAClient": "false",
    "hasCancelledService": "false",
    "cancelado": "false",
    "needsReception": "false",
    "time_instalacao": "",
    "viabilidade_cep": "false",
    "givesServiceToCity": "true",
    "api_cep": "",
    "ret_cep": "",
    "ret_estado": "",
    "ret_cidade": "",
    "ret_bairro": "",
    "ret_rua": ""
  }
  ```

  **Exemplo de resposta — CPF inválido (2ª tentativa):**
  ```json
  {
    "valido": false,
    "extracted_data": {},
    "message": "CPF inválido. Pode conferir? (Exemplo: 999.999.999-99)",
    "motivo_invalido": "cpf_invalido",
    "transbordo": false,
    "regra_aplicada": "coleta_cpf",
    "tentativas": 2,
    "resposta_correta": "false",
    "resposta_sem_erro_api": "false",
    "retorno_erro_api": "CPF inválido. Pode conferir? (Exemplo: 999.999.999-99)",
    ...
  }
  ```

  **Exemplo de resposta — CEP válido (ViaCEP encontrou):**
  ```json
  {
    "valido": true,
    "extracted_data": {
      "cep": "64020-340",
      "rua": "Rua Areolino de Abreu",
      "bairro": "Centro",
      "cidade": "Teresina",
      "estado": "PI"
    },
    "message": "Endereço encontrado! ##263A##",
    "regra_aplicada": "coleta_cep",
    "viabilidade_cep": "true",
    "ret_cep": "64020-340",
    "ret_rua": "Rua Areolino de Abreu",
    "ret_bairro": "Centro",
    "ret_cidade": "Teresina",
    "ret_estado": "PI",
    ...
  }
  ```

  ---

  ## ⚙️ Processamento interno — o que acontece quando você chama `/validar`

  ```
  1. REQUEST CHEGA
    │
    ▼
  2. IDENTIFICA A REGRA  (3 estratégias em cascata)
    │   ├─ a) question_id veio? → lookup direto no cache (1 µs)
    │   ├─ b) keywords-based: bate texto da pergunta contra ~30 regras
    │   ├─ c) match exato com pergunta_padrao
    │   ├─ d) substring match (primeiros 40 chars)
    │   └─ e) fallback OpenAI (se configurado)
    │
    ▼
  3. APLICA O EXTRACTOR  (de acordo com regra.extractor_tipo)
    │   └─ Cada extractor retorna (valido: bool, extracted: dict, motivo: str)
    │
    ▼
  4. CONTA TENTATIVAS  (por cellphone+question_id, em memória)
    │   ├─ Válido → reset contador
    │   └─ Inválido → incrementa, decide transbordo se >= max_tentativas
    │                  e regra tem forcar_transbordo_apos_max=true
    │
    ▼
  5. MONTA MENSAGEM PRO CLIENTE
    │   ├─ Válido → msg_sucesso da regra (ou "Anotei!")
    │   ├─ Transbordo → msg_max_tentativas
    │   └─ Erro → msg_erro
    │
    ▼
  6. DISPARA AÇÕES EM BACKGROUND (thread daemon — não bloqueia)
    │   ├─ Atualizar campo do lead (campo_lead_atualizar)
    │   ├─ Mudar status_api (status_api_apos_sucesso)
    │   ├─ Adicionar/remover tags (tags_adicionar/remover)
    │   ├─ Registrar histórico (historico_status_apos_sucesso)
    │   └─ Salvar imagem (se extractor_tipo=imagem)
    │
    ▼
  7. RESPOSTA HTTP RETORNADA  (~50-300ms total)
  ```

  > ⚠️ As ações em background **não bloqueiam** a resposta. A API retorna imediatamente
  > após o extractor decidir. Se uma ação falhar (ex: Django offline), o log fica em
  > `actions_executed` mas o cliente já recebeu a resposta.

  ---

  ## 🧪 Extractors disponíveis (11 tipos)

  Cada `RegraValidacao` no Django define qual extractor usar. A regra `extractor_tipo`
  determina como `answer` será processado.

  ### 1. `cpf` — CPF brasileiro com dígito verificador

  ```python
  # Aceita: "529.982.247-25", "52998224725", "meu cpf é 529982247-25"
  # Rejeita: "111.111.111-11" (DV inválido), "12345"
  extracted_data: {"cpf_cnpj": "52998224725"}  # sem máscara
  ```

  Motivos de erro: `cpf_nao_identificado`, `cpf_invalido`

  ### 2. `cep` — CEP + ViaCEP

  ```python
  # Aceita: "64000-000", "64000000", "meu cep é 64020-340"
  # Faz chamada ao ViaCEP. Se não existe → falha.
  extracted_data: {
    "cep": "64020-340",
    "rua": "Rua Areolino de Abreu",
    "bairro": "Centro",
    "cidade": "Teresina",
    "estado": "PI"
  }
  ```

  > ⚠️ Só pra CEP, a API **também** preenche os campos `ret_cep`, `ret_rua`, `ret_bairro`,
  > `ret_cidade`, `ret_estado` na resposta top-level (compat com flow Matrix antigo).

  Motivos de erro: `cep_nao_identificado`, `cep_nao_existe`

  ### 3. `nome` — Nome completo

  ```python
  # Aceita: "João Silva", "Maria José Santos"
  # Rejeita: nome só (sem sobrenome), nomes de 1 letra
  extracted_data: {"nome_razaosocial": "João Silva"}
  ```

  Motivos: `nome_incompleto`, `nome_invalido`

  ### 4. `telefone` — Número de telefone

  ```python
  extracted_data: {"telefone": "5586999999999"}
  ```

  ### 5. `data_nascimento` — Data com validação de maioridade

  ```python
  # Aceita: "01/01/2000", "01-01-2000", "1 de janeiro de 2000"
  # Rejeita: menores de 18 anos, datas futuras
  extracted_data: {"data_nascimento": "2000-01-01"}  # formato ISO
  ```

  Motivos: `data_invalida`, `menor_de_idade`

  ### 6. `email` — Validação simples por regex

  ```python
  extracted_data: {"email": "nome@exemplo.com"}
  ```

  Motivos: `email_vazio`, `email_invalido`

  ### 7. `numero` — Número de residência

  ```python
  # Aceita: "123", "S/N", "sem número"
  extracted_data: {"numero_residencia": "123"}
  # OU
  extracted_data: {"numero_residencia": "S/N"}
  ```

  ### 8. `opcao` — Escolha de menu (URA)

  ```python
  # Config esperada na regra:
  extractor_config: {
    "opcoes": {
      "manha": ["1", "manhã", "manha", "AM"],
      "tarde": ["2", "tarde", "PM"]
    }
  }
  # Cliente diz "tarde" → match
  extracted_data: {"opcao": "tarde"}
  ```

  Motivos: `opcao_nao_reconhecida`

  ### 9. `confirmacao` — Sim/Não

  ```python
  # Aceita: "sim", "s", "claro", "pode", "ok" → True
  #         "não", "n", "depois", "não quero" → False
  extracted_data: {"confirmacao": true}  // ou false
  ```

  ### 10. `imagem` — URL de imagem

  ```python
  # Espera que o Matrix tenha enviado uma URL (ex: do WhatsApp)
  extracted_data: {"url_imagem": "https://..."}
  ```

  ### 11. `texto_livre` / `livre` — Texto qualquer

  ```python
  # Sempre aceita (a não ser que `texto_livre` chame OpenAI pra validar contexto)
  extracted_data: {"valor": "texto qualquer"}
  ```

  ---

  ## 🎬 Ações disparadas em background

  Quando `valido = true`, a API IA executa estas ações **em paralelo** (sem bloquear
  a resposta). Cada ação depende dos campos da regra estarem preenchidos.

  | Ação                   | Endpoint Django                                | Condição na regra                          |
  |------------------------|-----------------------------------------------|---------------------------------------------|
  | **Atualizar lead**     | `POST /api/leads/atualizar/`                  | `campo_lead_atualizar` preenchido           |
  | **Mudar status_api**   | `POST /api/leads/atualizar/`                  | `status_api_apos_sucesso` preenchido        |
  | **Adicionar tags**     | `POST /api/leads/tags/`                       | `tags_adicionar` lista com itens            |
  | **Remover tags**       | `POST /api/leads/tags/`                       | `tags_remover` lista com itens              |
  | **Registrar histórico**| `POST /api/historicos/registrar/`             | `historico_status_apos_sucesso` preenchido  |
  | **Salvar imagem**      | `POST /api/leads/imagens/`                    | `extractor_tipo=imagem` + `descricao_imagem`|

  ### Caso especial: CEP

  Quando `extractor_tipo=cep` e a validação dá certo, **TODOS** os campos extraídos
  (cep, rua, bairro, cidade, estado) são salvos no lead, mesmo que `campo_lead_atualizar`
  esteja vazio. Isso é hardcoded no engine pra simplificar o uso.

  ### Caso especial: Plano

  Quando `extractor_tipo=opcao` e `campo_lead_atualizar=id_plano_rp`, a API também
  grava `valor` (preço do plano) automaticamente, consultando o dict `PLANOS` em
  `src/integracoes/robovendas.py`.

  ---

  ## 📥 Endpoint `GET /` — Health check

  ```bash
  curl https://robovendas.megalinkpiaui.com.br/ia/
  ```

  ```json
  {
    "status": "ok",
    "versao": "2.0.0",
    "persona": "Aurora",
    "modelo_ia": "gpt-4o-mini",
    "erros_config": [],
    "regras_stats": {
      "regras_em_cache": 27,
      "inferencias_em_cache": 12,
      "ultima_carga_h_atras": 0.5,
      "ttl_segundos": 3600
    },
    "fluxos_yaml_legados": []
  }
  ```

  ---

  ## 📥 Endpoint `GET /regras` — Listar regras em cache

  ```bash
  curl https://robovendas.megalinkpiaui.com.br/ia/regras
  ```

  ```json
  {
    "stats": {
      "regras_em_cache": 27,
      "inferencias_em_cache": 12,
      "ultima_carga_h_atras": 0.5,
      "ttl_segundos": 3600
    },
    "regras": [
      {
        "question_id": "coleta_cpf",
        "extractor": "cpf",
        "campo": "cpf_cnpj",
        "pergunta": "Pode me informar seu CPF? (Exemplo: 999.99..."
      },
      ...
    ]
  }
  ```

  ---

  ## 📥 Endpoint `POST /admin/invalidar-cache/`

  Chamado automaticamente pelo Django via signal (`post_save`/`post_delete` em `RegraValidacao`).
  Você só chama manualmente se editar o banco direto (sem passar pelo admin).

  ```bash
  curl -X POST https://robovendas.megalinkpiaui.com.br/ia/admin/invalidar-cache/
  # → {"ok": true}
  ```

  ---

  ## 📥 Endpoints de DEBUG

  ### `GET /contexto/{telefone}` — Estado da conversa

  ```bash
  curl https://robovendas.megalinkpiaui.com.br/ia/contexto/5586999999999
  ```

  ```json
  {
    "telefone": "5586999999999",
    "etapa_atual": "",
    "dados_extraidos": {"cpf_cnpj": "52998224725", "cep": "64020-340"},
    "historico_count": 8,
    "tentativas": {"regra:coleta_cpf": 0, "regra:coleta_cep": 2},
    "lead_id": 2057
  }
  ```

  ### `DELETE /contexto/{telefone}` — Reset

  Limpa as tentativas, lead_id em cache e histórico. Útil pra refazer um teste.

  ```bash
  curl -X DELETE https://robovendas.megalinkpiaui.com.br/ia/contexto/5586999999999
  # → {"ok": true}
  ```

  ---

  ## 🔁 O que SEMPRE varia vs o que SEMPRE é igual

  ### ✅ Sempre IGUAL (você não muda):

  - **URL** — `https://robovendas.megalinkpiaui.com.br/ia/validar`
  - **Método** — POST
  - **Headers** — `Content-Type: application/json`
  - **Schema do request** — sempre os 5 campos (`question`, `answer`, `cellphone`, `lead_id`, `question_id`)
  - **Schema do response** — sempre os mesmos ~30 campos (V2 + legados)

  ### 🔀 Sempre VARIA (você muda por pergunta):

  - **Valores** dos 5 campos do request
  - **Valores** dos campos do response (alguns vazios pra perguntas que não envolvem CEP, etc)
  - **`extracted_data`** — estrutura interna varia por `extractor_tipo`

  ### Por exemplo, no mesmo endpoint:

  | Pergunta sendo validada | Campos `extracted_data`                              | Campos `ret_*` populados? |
  |-------------------------|------------------------------------------------------|---------------------------|
  | CPF                     | `{cpf_cnpj}`                                         | Não                       |
  | CEP                     | `{cep, rua, bairro, cidade, estado}`                 | Sim (todos os 5)          |
  | Nome                    | `{nome_razaosocial}`                                 | Não                       |
  | E-mail                  | `{email}`                                            | Não                       |
  | Imagem                  | `{url_imagem}`                                       | Não                       |
  | Opção (turno)           | `{opcao: "manha"}`                                   | Não                       |

  ---

  ## 🚨 Códigos de erro (`motivo_invalido`)

  | Código                  | Significado                                       |
  |-------------------------|---------------------------------------------------|
  | `cpf_nao_identificado`  | Texto não tem 11 dígitos                          |
  | `cpf_invalido`          | DV inválido                                       |
  | `cep_nao_identificado`  | Texto não tem 8 dígitos                           |
  | `cep_nao_existe`        | ViaCEP retornou 404                               |
  | `nome_invalido`         | Só uma palavra ou caracteres estranhos            |
  | `nome_incompleto`       | Cliente forneceu só primeiro nome                 |
  | `email_vazio`           | Resposta vazia                                    |
  | `email_invalido`        | Não bate com regex de e-mail                      |
  | `data_invalida`         | Data não parseável                                |
  | `menor_de_idade`        | Idade calculada < 18                              |
  | `opcao_nao_reconhecida` | Resposta não bate com nenhuma opção da config     |
  | `imagem_nao_recebida`   | URL ausente ou não parece com URL                 |
  | `telefone_invalido`     | Não bate com formato BR                           |
  | `numero_vazio`          | Resposta vazia pra campo numérico                 |
  | `confirmacao_ambigua`   | Resposta não é claramente sim/não                 |
  | `resposta_vazia`        | answer vazia ou só whitespace                     |

  ---

  ## ⏱ Comportamento de tentativas e transbordo

  - A API mantém um **contador em memória** por (`cellphone`, `question_id`).
  - Cada validação **inválida** incrementa o contador.
  - Cada validação **válida** zera.
  - Se `tentativas >= regra.max_tentativas` E `regra.forcar_transbordo_apos_max=true`:
    - `transbordo: true` na resposta
    - `needsReception: "true"` (compat legado)
    - `message`: usa `msg_max_tentativas` da regra
  - O Matrix lê `transbordo` (ou `needsReception`) e roteia pra `hor_1` → atendente humano.

  > 📌 O contador **NÃO** persiste em banco. Se a API IA reiniciar, contadores zeram.
  > Pra zerar manualmente: `DELETE /contexto/{telefone}`.

  ---

  ## 🔐 Autenticação

  Atualmente **não tem autenticação** — a API confia que só o Matrix e o Django chamam.
  O nginx faz rate limit de **30 req/min** por IP na zone `api`.

  > Se quiser proteger, adicione um middleware FastAPI que valide um `X-API-Key`.

  ---

  ## 📊 Performance esperada

  | Cenário              | Latência típica |
  |----------------------|-----------------|
  | CPF / Nome / Email   | 30-80 ms        |
  | CEP (com ViaCEP)     | 200-600 ms      |
  | Imagem               | 30-80 ms        |
  | Texto livre + OpenAI | 800-2500 ms     |
  | Cache hit (qualquer) | < 50 ms         |

  A chamada da API IA não bloqueia ações em background — você recebe a resposta
  e o Django é atualizado em paralelo (~50-200ms depois).

  ---

  ## 🐛 Como testar manualmente

  ```bash
  # CPF válido
  curl -X POST https://robovendas.megalinkpiaui.com.br/ia/validar \
    -H "Content-Type: application/json" \
    -d '{
      "question": "Qual seu CPF?",
      "answer": "529.982.247-25",
      "cellphone": "5586999999999",
      "question_id": "coleta_cpf"
    }' | python3 -m json.tool

  # CEP válido
  curl -X POST https://robovendas.megalinkpiaui.com.br/ia/validar \
    -H "Content-Type: application/json" \
    -d '{
      "question": "Qual seu CEP?",
      "answer": "64020-340",
      "cellphone": "5586999999999",
      "question_id": "coleta_cep"
    }' | python3 -m json.tool

  # Resposta inválida (vai contar tentativa)
  curl -X POST https://robovendas.megalinkpiaui.com.br/ia/validar \
    -H "Content-Type: application/json" \
    -d '{
      "question": "Qual seu CPF?",
      "answer": "11111111111",
      "cellphone": "5586999999999",
      "question_id": "coleta_cpf"
    }' | python3 -m json.tool

  # Limpa estado pra refazer o teste
  curl -X DELETE https://robovendas.megalinkpiaui.com.br/ia/contexto/5586999999999
  ```

  ---

  ## 🔗 Endpoints Django que a API IA dispara em background

  Esses são chamados internamente — você **não** precisa chamar do Matrix.

  | Endpoint                                       | Método | Quando                                |
  |-----------------------------------------------|--------|---------------------------------------|
  | `/api/consultar/leads/?search=...`            | GET    | Garantir que existe lead              |
  | `/api/leads/registrar/`                       | POST   | Criar lead se não existe              |
  | `/api/leads/atualizar/`                       | POST   | Atualizar campos do lead              |
  | `/api/leads/tags/`                            | POST   | Adicionar/remover tags                |
  | `/api/historicos/registrar/`                  | POST   | Registrar histórico de interação      |
  | `/api/leads/imagens/`                         | POST   | Salvar imagem do documento            |

  ---

  ## 📁 Arquivos relacionados

  | Arquivo                                  | Função                                   |
  |------------------------------------------|------------------------------------------|
  | `src/app.py`                             | Endpoints FastAPI                        |
  | `src/regras/engine.py`                   | Lógica de validação + ações              |
  | `src/regras/client.py`                   | Cliente HTTP do Django + cache + inferência |
  | `src/extractors/*.py`                    | Implementação dos extractors              |
  | `src/integracoes/robovendas.py`          | Chamadas pros endpoints Django           |
  | `src/contexto/conversa.py`               | Gerenciador de tentativas em memória     |
  | `src/config.py`                          | Config via env vars                      |

  ---

  ## 🎚 Variáveis de ambiente

  Setadas em `/etc/systemd/system/ia-validacao.service`:

  | Var                       | Default                                       | Descrição                       |
  |---------------------------|-----------------------------------------------|----------------------------------|
  | `ROBOVENDAS_API_URL`      | `https://robovendas.megalinkpiaui.com.br`     | URL base do Django               |
  | `OPENAI_API_KEY`          | (secreto)                                     | Para fallback de inferência      |
  | `OPENAI_MODEL`            | `gpt-4o-mini`                                 | Modelo OpenAI                    |
  | `PERSONA_NOME`            | `Aurora`                                      | Nome da persona da IA            |
  | `USAR_CACHE_INFERENCIA`   | `true`                                        | Habilita fallback OpenAI         |
  | `LOG_LEVEL`               | `INFO`                                        |                                  |
  | `PORT`                    | `8090`                                        |                                  |

  ---

  ## 🆘 Troubleshooting

  ### "Bot ficou em silêncio após resposta"
  - Verifica logs: `sudo journalctl -u ia-validacao -f --since "5 min ago"`
  - Vê se a regra existe no cache: `curl /ia/regras | grep "coleta_xxx"`
  - Verifica se a API tá no ar: `curl /ia/`

  ### "Sempre cai em erro mesmo com resposta válida"
  - Verifica se `question_id` no Matrix bate com o cadastrado no Django
  - Forçar reload do cache: `curl -X POST /ia/admin/invalidar-cache/`
  - Teste o endpoint direto com curl (acima)

  ### "Lead não está sendo atualizado"
  - Verifica `actions_executed` na resposta — log das ações disparadas
  - Checa se `campo_lead_atualizar` da regra bate com o nome do campo no model Django
  - Logs: `sudo journalctl -u ia-validacao | grep "atualizar_lead"`

  ### "Cliente atingiu max tentativas mas não transbordou"
  - Confirma que `forcar_transbordo_apos_max=true` na regra
  - Lembra que o contador é **em memória** — se restartou o service, zerou
