# 📡 Fluxograma técnico — APIs do fluxo de venda Megalink

> **Como ler:** cada bloco abaixo é um ponto onde você posiciona um nó **API** no Matrix.
> Variáveis Matrix usam o padrão `{#nome_variavel}`.
> A IA `/ia/validar` faz validação **e dispara ações em background** (atualizar lead, adicionar tags, registrar histórico, salvar imagens) — você não precisa chamar essas APIs manualmente, basta cadastrar a regra correta em `RegraValidacao` no Django Admin.

---

## 🗺 Visão geral do fluxo

```
┌──────────────────────────────────────────────────────────────────┐
│  INICIO                                                          │
│  1. api_14 (GET)  — consultar se já existe lead com esse telefone│
│  2. api_8  (POST) — registrar lead se não existir                │
└─────┬────────────────────────────────────────────────────────────┘
      ▼
┌──────────────────────────────────────────────────────────────────┐
│  COLETA DE DADOS (loop para cada pergunta)                       │
│  Antes do sol → set_var question_id_atual = "coleta_xxx"         │
│  Depois do sol → /ia/validar (faz tudo: valida + ações bg)       │
└─────┬────────────────────────────────────────────────────────────┘
      ▼
┌──────────────────────────────────────────────────────────────────┐
│  ESCOLHA DO PLANO (URAs com botões — sem IA)                     │
│  Apenas set_var de id_plano_rp, valor, titulo                    │
└─────┬────────────────────────────────────────────────────────────┘
      ▼
┌──────────────────────────────────────────────────────────────────┐
│  COLETA DE CEP                                                   │
│  /ia/validar com question_id="coleta_cep" — retorna ret_cep/etc  │
└─────┬────────────────────────────────────────────────────────────┘
      ▼
┌──────────────────────────────────────────────────────────────────┐
│  DOCUMENTOS (3 imagens)                                          │
│  /ia/validar com question_id="documentacao_selfie"/frente/verso  │
└─────┬────────────────────────────────────────────────────────────┘
      ▼
┌──────────────────────────────────────────────────────────────────┐
│  CONFIRMAÇÃO + FINALIZAÇÃO                                       │
│  api_email_nas_ven (POST) — status_api=aguardando_assinatura     │
│  api_finaliza_lead (POST) — status_api=pendente                  │
│  api_fluxo_finalizado (POST) — registra historico                │
└─────┬────────────────────────────────────────────────────────────┘
      ▼
┌──────────────────────────────────────────────────────────────────┐
│  INSTALAÇÃO (Hubsoft)                                            │
│  Polling api_21 (até is_a_client_hubsoft=true)                   │
│  api_22 (consultar agenda) → api_23 (atendimento) → api_24 (OS)  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ Bloco INÍCIO — identificar/registrar lead

### 📌 Antes de qualquer pergunta

**Variáveis pra setar (set_var):**
- `{#url_api}` = `https://robovendas.megalinkpiaui.com.br`
- `{#webhook_aurora}` = `https://robovendas.megalinkpiaui.com.br/ia/validar`

### ➡️ Chamada 1: `api_14` — Consultar lead existente

```
URL:    GET {#url_api}/api/consultar/leads/?search={#CONTATO.TELEFONE}&origem=whatsapp&ativo=true&page=1
Método: GET
Body:   (vazio)
```

**Armazenar:**
| Variável Matrix | Caminho do retorno |
|----------------|-------------------|
| `result_get_leads` (3620087) | `results.0.id` |

### 🔀 Decisão `dec_6` — lead existe?

- Se `result_get_leads != ""` → set `id_lead = {#result_get_leads}` → pular pro fluxo principal
- Se `result_get_leads == ""` → chamar **api_8**

### ➡️ Chamada 2: `api_8` — Registrar novo lead

```
URL:    POST {#url_api}/api/leads/registrar/
Método: POST
Headers: Content-Type: application/json
Body:
{
  "nome_razaosocial": "{#CONTATO.NOME}",
  "telefone": "{#CONTATO.TELEFONE}",
  "origem": "whatsapp",
  "canal_entrada": "whatsapp",
  "tipo_entrada": "contato_whatsapp",
  "status_api": "processamento_manual",
  "id_vendedor_rp": 1618,
  "id_origem": "106",
  "id_origem_servico": "74"
}
```

**Armazenar:**
| Variável Matrix | Caminho do retorno |
|----------------|-------------------|
| `id_lead` (3620083) | `id` |

> ✅ A partir daqui `{#id_lead}` está populado e será usado em TODAS as próximas chamadas.

---

## 2️⃣ Bloco COLETA DE DADOS — padrão reutilizável

> **Esse padrão se repete para cada pergunta**: nome, número, ponto referência, nome completo, e-mail, data nascimento, CPF, RG, CEP.

### Estrutura por pergunta:

```
┌─────────────────────────────────────┐
│  set_var question_id_atual = "coleta_cpf"│  ← MUDA por pergunta
└─────┬───────────────────────────────┘
      ▼
┌─────────────────────────────────────┐
│  msg: "Pode me informar seu CPF?"   │
└─────┬───────────────────────────────┘
      ▼
┌─────────────────────────────────────┐
│  sol_xxx (variable=prospecto_cpf)   │  ← captura input
└─────┬───────────────────────────────┘
      ▼ Validado
┌─────────────────────────────────────┐
│  set_var:                           │
│    pergunta_cliente = "...?"        │
│    resposta_cliente = {#prospecto_cpf}│  ← IMPORTANTE
└─────┬───────────────────────────────┘
      ▼
┌─────────────────────────────────────┐
│  api_valida_resposta (chama IA)     │
└─────┬───────────────────────────────┘
      ▼
   dec_3 → roteia conforme resposta
```

### ➡️ Chamada: `/ia/validar`

```
URL:    POST {#webhook_aurora}     (=  /ia/validar)
Método: POST
Headers: Content-Type: application/json
Body:
{
  "question": "{#pergunta_cliente}",
  "answer": "{#resposta_cliente}",
  "cellphone": "{#CONTATO.TELEFONE}",
  "lead_id": "{#id_lead}",
  "question_id": "{#question_id_atual}"
}
```

**Armazenar (filter=1):**

| Variável Matrix         | ID      | Caminho do retorno              | Uso                                |
|-------------------------|---------|--------------------------------|------------------------------------|
| `resposta_correta`      | 3620068 | `resposta_correta`              | dec_4 (validação semântica)         |
| `resposta_sem_erro_api` | 3620067 | `resposta_sem_erro_api`         | dec_3 (chamada não deu erro)        |
| `retorno_erro_api`      | 3620074 | `retorno_erro_api`              | mensagem de erro pro cliente        |
| `needsReception`        | 3620080 | `needsReception`                | dec_3 Avançado (transbordo)         |
| `isAClient`             | 3620081 | `isAClient`                     | dec_5 (cliente já existe no Hubsoft)|
| `cancelado`             | 3620082 | `cancelado`                     | dec_5 (serviço cancelado)           |
| `viabilidade_cep`       | 3620094 | `viabilidade_cep`               | dec_4 (CEP atendido na região)      |
| `api_cep`               | 3620066 | `api_cep`                       | dec_8 (msg de erro do CEP)          |
| `time_instalacao`       | 3620088 | `time_instalacao`               | dec_9                               |
| `ret_cep`               | 3620069 | `ret_cep`                       | confirmação de endereço             |
| `ret_bairro`            | 3620070 | `ret_bairro`                    |                                    |
| `ret_cidade`            | 3620071 | `ret_cidade`                    |                                    |
| `ret_estado`            | 3620072 | `ret_estado`                    |                                    |
| `ret_rua`               | 3620073 | `ret_rua`                       |                                    |
| `prospecto_cpf`         | 3620055 | `extracted_data.cpf_cnpj`       | CPF normalizado (sem máscara)       |
| `prospecto_nome_completo`| 3620060 | `extracted_data.nome_razaosocial`|                                    |
| `prospecto_email`       | 3620079 | `extracted_data.email`          |                                    |
| `prospecto_nascimento`  | 3620057 | `extracted_data.data_nascimento`| Formato ISO                         |
| `prospecto_n_resisdencia`| 3620054| `extracted_data.numero_residencia`|                                  |

### 🧠 O que a IA faz em background (você NÃO precisa chamar):

A IA, ao validar com sucesso, dispara automaticamente (de acordo com a regra `RegraValidacao` cadastrada no Django Admin):

1. **Atualizar campo do lead** (`/api/leads/atualizar/`) — se `campo_lead_atualizar` preenchido
2. **Adicionar tags** (`/api/leads/tags/`) — se `tags_adicionar` tem itens
3. **Mudar status_api** — se `status_api_apos_sucesso` preenchido
4. **Registrar histórico** (`/api/historicos/registrar/`) — se `historico_status_apos_sucesso` preenchido
5. **Salvar imagem do documento** (`/api/leads/imagens/`) — se `descricao_imagem` preenchido (selfie/frente/verso)

### 🔀 Decisões após `/ia/validar`:

```
                    api_valida_resposta
                          │
                          ▼
                      ╔═══════╗
                      ║ dec_3 ║
                      ╚═══╤═══╝
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
  needsReception     resposta_sem_erro     Padrão
     = true              _api=true         (erro)
       │                  │                  │
       ▼                  ▼                  ▼
  → transbordo        ╔═══════╗         msg_16 mostra
   (ser_5/hor_1)      ║ dec_5 ║         {#retorno_erro_api}
                      ╚═══╤═══╝         → loop p/ sol
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
   isAClient=true    cancelado=true       Padrão
       │                  │                  │
       ▼                  ▼                  ▼
   → transbordo      → transbordo       red_41:
   (já é cliente)    (serviço            jump pro próximo
                     cancelado)          passo do fluxo
                                         (= {#dinamica_prox_pass})
```

### 🔑 Variáveis de controle do fluxo (você seta em RED nodes antes da chamada):

| Variável                 | Função                                              | Exemplo                   |
|-------------------------|-----------------------------------------------------|---------------------------|
| `pergunta_cliente`      | Pergunta atual (vai no body da API)                 | "Qual seu CPF?"           |
| `resposta_cliente`      | Resposta do usuário (vai no body da API)            | `{#prospecto_cpf}`        |
| `question_id_atual`     | Lookup direto da regra no Django                    | `coleta_cpf`              |
| `dinamica_prox_pass`    | Para onde pular se validar com sucesso              | `msg_22`                  |
| `dinamica_pass_atual`   | Para onde voltar se erro (re-perguntar)             | `msg_sol_cpf`             |

---

## 3️⃣ Padrão dec_5 → "next step" (red_41)

Após dec_5 Padrão, o `red_41` (type=2) faz **jump por identifier dinâmico**:

```
component_identifier: "{#dinamica_prox_pass}"
```

Isso faz o Matrix pular para o nó cujo `data.identifier` é igual ao valor da variável.

**⚠️ Importante:** o identifier alvo precisa ser **único** no flow.

---

## 4️⃣ Bloco CEP (especial)

O CEP tem dois caminhos:
- **Sucesso ViaCEP**: ret_cep/bairro/cidade/estado/rua preenchidos → confirmação via URA
- **CEP não encontrado / sem viabilidade**: pular para coleta manual (rua/bairro/cidade/estado) OU transbordo

### ➡️ `api_consulta_cep` (= `/ia/validar` com question_id=coleta_cep)

```
Body:
{
  "question": "Qual o CEP do seu endereço?",
  "answer": "{#prospecto_cep}",
  "cellphone": "{#CONTATO.TELEFONE}",
  "lead_id": "{#id_lead}",
  "question_id": "coleta_cep"
}
```

> ✅ Note que **answer usa `{#prospecto_cep}` direto** (não `{#resposta_cliente}`), porque vem direto do sol sem red intermediário.

**Armazenar:** mesmas vars do bloco genérico + `ret_*`.

### 🔀 Decisão `dec_4`:

```
dec_4:
├─ viabilidade_cep = false  →  hor_1 (transbordo, sem cobertura)
├─ resposta_correta = false →  msg_21 ({#api_cep}) → loop p/ sol_7
├─ needsReception = true    →  hor_1 (Avançado)
└─ Padrão → campos_faltantes (verifica ret_cidade, ret_bairro, ret_rua):
            ├─ ret_cidade=""  →  sol_cidade manual
            ├─ ret_bairro=""  →  sol_bairro manual
            ├─ ret_rua=""     →  sol_rua manual
            └─ Padrão → ura_7 (confirmação) → seguir fluxo
```

---

## 5️⃣ Bloco DOCUMENTOS

3 sols sequenciais (selfie / frente / verso), cada um com chamada à IA pra validar a imagem.

### Variáveis Matrix:
- `img_doc1` (3620084) — selfie
- `img_doc2` (3620085) — frente do documento
- `img_doc3` (3620086) — verso

### Padrão:

```
msg "Envie selfie segurando o documento"
        ↓
sol_16 (variable = img_doc1)
        ↓ Validado
set_var:
   pergunta_cliente = "Envie selfie..."
   resposta_cliente = {#img_doc1}
   dinamica_prox_pass = "msg_29"  ← próximo: pede frente
   dinamica_pass_atual = "msg_31" ← se erro, repete
        ↓
api_valida_resposta (com question_id="documentacao_selfie")
```

**Question IDs:**
- `documentacao_selfie` → grava em `img_doc_selfie`
- `documentacao_frente_doc` → grava em `img_doc_frente`
- `documentacao_verso_doc` → grava em `img_doc_verso`

> A IA grava a imagem no Django via `/api/leads/imagens/` automaticamente.

---

## 6️⃣ Bloco FINALIZAÇÃO (não usa /ia/validar)

São chamadas explícitas pra mudar status do lead.

### ➡️ `api_email_nas_ven` — após confirmação URA, antes do checkout

```
URL:    POST {#url_api}/api/leads/atualizar/
Body:
{
  "termo_busca": "id",
  "busca": {#id_lead},
  "email": "{#prospecto_email}",
  "data_nascimento": "{#prospecto_nascimento}",
  "id_dia_vencimento": "{#id_vencimento_prospect}",
  "status_api": "aguardando_assinatura"
}
```

### ➡️ `api_finaliza_lead` — após cliente confirmar tudo

```
URL:    POST {#url_api}/api/leads/atualizar/
Body:
{
  "termo_busca": "id",
  "busca": {#id_lead},
  "empresa": "{#nome_empresa_api}",
  "status_api": "pendente",
  "observacoes": "Finalizado"
}
```

### ➡️ `api_fluxo_finalizado` — registra historico de sucesso

```
URL:    POST {#url_api}/api/historicos/registrar/
Body:
{
  "telefone": "{#CONTATO.TELEFONE}",
  "nome_contato": "{#CONTATO.NOME}",
  "origem_contato": "whatsapp",
  "lead_id": {#id_lead},
  "status": "fluxo_finalizado",
  "sucesso": "True"
}
```

---

## 7️⃣ Bloco INSTALAÇÃO (Hubsoft) — opcional

> Só executa se o lead deve ir pro Hubsoft (após assinatura).

### ➡️ `api_21` — polling status no Hubsoft

```
URL:    GET {#url_api}/integracoes/api/lead/hubsoft-status/?lead_id={#id_lead}
Método: GET
```

**Armazenar:**
| Variável                  | Caminho                                |
|---------------------------|----------------------------------------|
| `is_a_client_hubsoft`     | `eh_cliente_hubsoft`                   |
| `id_cliente_servico_api`  | `servicos.0.id_cliente_servico`        |
| `nome_lead_api`           | `lead.nome_razaosocial`                |
| `documentacao_validada`   | `lead.documentacao_validada`           |
| `total_doc_rejeitado`     | `cliente_hubsoft.lead.docs.rejeitados` |

### 🔄 Loop com `wait` (20s):

```
api_21 → dec_16:
   ├─ is_a_client_hubsoft = true   →  wait_2 → api_22
   └─ Padrão (false) → wait_1 → incrementa contador → api_21
         (até contador > 90 → transbordo)
```

### ➡️ `api_22` — consultar agenda

```
URL: GET {#url_api_matrix}/consultar_agenda?cidade={#ret_cidade}&data_referencia={#cliente_data_insta}&turno={#turno_instalacao}&qtd_vagas=1
```

**Armazenar:**
- `dados_agenda` ← `dados`
- `opt1_horario` ← `dados.disponibilidade_turno.0.horario`
- `primeiro_tec_disponivel` ← `dados.disponibilidade_turno.0.tecnicos.0.id`
- `id_agenda_os` ← `dados.id_agenda_ordem_servico`

### ➡️ `api_23` — abrir atendimento

```
URL: POST {#url_api_matrix}/abrir_atendimento
Body:
{
  "id_cliente_servico": {#id_cliente_servico_api},
  "nome": "ClienteVenda",
  "telefone": "{#CONTATO.TELEFONE}",
  "descricao": "{#body_descricao}",
  "id_tipo_atendimento": {#id_tipo_atendimento_instalacao},
  "id_atendimento_status": {#id_status_atendimento},
  "id_usuario_responsavel": {#id_user_responsavel},
  "empresa": "{#nome_empresa_api}"
}
```

**Armazenar:** `id_atendimento_abrir_os` ← `atendimento.id_atendimento`

### ➡️ `api_24` — abrir OS

```
URL: POST {#url_api_matrix}/abrir_os
Body:
{
  "id_atendimento": {#id_atendimento_abrir_os},
  "id_tipo_ordem_servico": {#id_tipo_os},
  "id_agenda_ordem_servico": {#id_agenda_os},
  "data_inicio_programado": "{#cliente_data_insta}",
  "data_termino_programado": "{#cliente_data_insta}",
  "hora_inicio_programado": "{#opt1_horario}",
  "duracao": "{#duracao}",
  "status": "{#status_os_api}",
  "id_tecnico": {#primeiro_tec_disponivel},
  "empresa": "megalink"
}
```

### ➡️ `api_25` — datas disponíveis

```
URL: GET https://apimatrix.megalinkpiaui.com.br/consultar_datas_sem_domingo?data_referencia={$DATE(d/m/Y)}
```

**Armazenar:**
- `data_instalacao_1` ← `datas.0`
- `data_instalacao_2` ← `datas.1`
- `data_instalacao_3` ← `datas.2`

---

## 📋 Tabela RESUMO — quando chamar cada API

| Momento do fluxo                       | API                        | Tipo  | Notas                                  |
|----------------------------------------|----------------------------|-------|----------------------------------------|
| Início do atendimento                  | `api_14`                   | GET   | Verifica se lead já existe              |
| Início, se lead não existe             | `api_8`                    | POST  | Cria lead, retorna `id_lead`            |
| Após cada pergunta (texto/imagem)      | `/ia/validar`              | POST  | Faz tudo: valida + ações em background  |
| Confirmação dados + escolha venc.      | `api_email_nas_ven`        | POST  | status_api=aguardando_assinatura        |
| Finalização do checkout (confirmou)    | `api_finaliza_lead`        | POST  | status_api=pendente                     |
| Após finalização                       | `api_fluxo_finalizado`     | POST  | Historico                               |
| Após assinatura (instalação)           | `api_21` (polling)         | GET   | Loop até cliente virar Hubsoft          |
| Cliente é Hubsoft + escolheu data      | `api_25`                   | GET   | Datas disponíveis                       |
| Após escolher data                     | `api_22`                   | GET   | Consulta agenda do turno                |
| Após agenda                            | `api_23`                   | POST  | Abre atendimento                        |
| Após atendimento                       | `api_24`                   | POST  | Abre OS                                 |

---

## 🎯 Como cadastrar uma pergunta nova

No Django Admin (`/admin/ia_validador/regravalidacao/`):

1. Clique **Adicionar Regra de Validação**
2. Preencha:
   - `question_id`: slug único (ex: `coleta_estado_civil`)
   - `pergunta_padrao`: texto exato da pergunta no Matrix (para inferência fallback)
   - `extractor_tipo`: `cpf`, `cep`, `nome`, `email`, `data_nascimento`, `opcao`, `imagem`, `confirmacao`, `texto_livre`, `numero`
   - `extractor_config`: JSON com config extra (ex: opções pra `opcao`)
   - `campo_lead_atualizar`: nome do campo do `LeadProspecto` (ex: `cpf_cnpj`)
   - `tags_adicionar`: lista JSON `["Comercial", "Endereco"]`
   - `status_api_apos_sucesso`: se muda status_api
   - `historico_status_apos_sucesso`: se registra histórico
   - `descricao_imagem`: pra `extractor_tipo=imagem` (ex: `selfie`)
   - `max_tentativas`: número antes de transbordar (default 3)
   - `msg_sucesso` / `msg_erro` / `msg_max_tentativas`: mensagens ao cliente

3. **Salve.** A IA invalida o cache automaticamente via signal Django.

4. No Matrix: antes do `sol_*` correspondente, adicione um **set_var** com `question_id_atual = "coleta_estado_civil"`.

---

## 🔧 Debug

```bash
# Logs da IA em tempo real
sudo journalctl -u ia-validacao -f

# Listar regras em cache
curl https://robovendas.megalinkpiaui.com.br/ia/regras | python3 -m json.tool

# Forçar reload do cache (após editar regra no admin)
curl -X POST https://robovendas.megalinkpiaui.com.br/ia/admin/invalidar-cache/

# Testar validação direta
curl -X POST https://robovendas.megalinkpiaui.com.br/ia/validar \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Qual seu CPF?",
    "answer": "529.982.247-25",
    "cellphone": "5586999999999",
    "lead_id": 1,
    "question_id": "coleta_cpf"
  }' | python3 -m json.tool

# Resetar estado de uma conversa (limpar tentativas)
curl -X DELETE https://robovendas.megalinkpiaui.com.br/ia/contexto/5586999999999
```
