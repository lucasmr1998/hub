# Documentacao do Fluxo Comercial WhatsApp — v5

> Arquivo: `flow_221_new_flow_comercial_-_v5_.json`
> Plataforma: Matrix (bot WhatsApp)
> Data: 30/03/2026

---

## Sumario

1. [Visao Geral](#1-visao-geral)
2. [Componentes e Tipos de No](#2-componentes-e-tipos-de-no)
3. [Variaveis do Fluxo](#3-variaveis-do-fluxo)
4. [Chamadas de API](#4-chamadas-de-api)
5. [Fluxo Principal — Passo a Passo](#5-fluxo-principal--passo-a-passo)
6. [Ramificacoes e Decisoes](#6-ramificacoes-e-decisoes)
7. [Mensagens Enviadas ao Lead](#7-mensagens-enviadas-ao-lead)
8. [Menus Interativos (URA)](#8-menus-interativos-ura)
9. [Coleta de Dados (Inputs)](#9-coleta-de-dados-inputs)
10. [Integracao com Webhook Aurora / N8N](#10-integracao-com-webhook-aurora--n8n)
11. [Finalizacoes Possiveis](#11-finalizacoes-possiveis)
12. [Mapa de Conexoes Simplificado](#12-mapa-de-conexoes-simplificado)

---

## 1. Visao Geral

O fluxo e um bot de atendimento comercial via WhatsApp que:

1. **Recebe** a mensagem inicial do lead
2. **Consulta** se ele ja existe na aplicacao (por telefone)
3. **Registra ou atualiza** o lead na base com todos os dados coletados
4. **Conduz** o prospect pelo processo de contratacao:
   - Coleta de endereco (via CEP automatico ou manual)
   - Verificacao de viabilidade da area
   - Apresentacao e selecao de planos
   - Coleta de dados pessoais (nome, CPF, email, RG, nascimento)
   - Coleta de documentos (3 fotos)
   - Selecao de data de vencimento da fatura
   - Agendamento de instalacao
5. **Abre** atendimento e Ordem de Servico (OS) no sistema Matrix/Hubsoft
6. **Registra** o historico de cada etapa na aplicacao Django

**Totais do fluxo:**
- 501 nos no total
- 39 nos de mensagem
- 25 chamadas de API
- 21 nos de coleta de input
- 11 menus interativos (URA)
- 20 nos de decisao
- 118 nos de roteamento/redirect
- 13 nos de variavel

**URL base da aplicacao:** `https://robovendas.megalinkpiaui.com.br` (variavel `url_api`)

---

## 2. Componentes e Tipos de No

| Cod | Tipo | Quantidade | Funcao |
|-----|------|-----------|--------|
| 1 | Mensagem | 39 | Envia mensagem de texto ao lead |
| 2 | Input/Coleta | 21 | Aguarda resposta do lead e armazena em variavel |
| 4 | Finalizacao | 2 | Encerra o atendimento no bot |
| 7 | Servico/Fila | 4 | Transfere para atendimento humano |
| 8 | Decisao | 20 | Ramificacao condicional (IF) |
| 9 | Chamada API | 25 | Requisicoes HTTP para APIs externas |
| 10 | URA/Menu | 11 | Menu interativo com botoes |
| 13 | Variavel | 13 | Seta/calcula valores de variaveis |
| 14 | Horario | 1 | Verifica horario de atendimento |
| 17 | Redirect | 118 | Conecta nos |
| 18 | Container | 23 | Agrupador de nos (sub-fluxos) |
| 26 | Espera | 2 | Aguarda N segundos (20s cada) |

---

## 3. Variaveis do Fluxo

### 3.1 Configuracao do servidor (setadas no no 5004)

| ID | Nome | Valor |
|----|------|-------|
| 1280025 | url_api | `https://robovendas.megalinkpiaui.com.br` |
| 3620089 | webhook_aurora | `https://automation-n8n.v4riem.easypanel.host/webhook/atendimento-v2` |
| 3620098 | url_api_matrix | `https://apimatrix.megalinkpiaui.com.br` |

### 3.2 Configuracao da empresa (setadas no no 5551)

| ID | Nome | Valor |
|----|------|-------|
| 3620044 | id_tipo_atendimento_semacesso | 1 |
| 3620046 | id_status_atendimento | 1 |
| 3620039 | id_user_responsavel | 1 |
| 3620028 | nome_empresa_api | "Megalink" |
| 1008 | nome_empresa | "*Megalink*" |
| 1039 | msg_boas_vindas | (configuravel) |

### 3.3 Mensagens do sistema (setadas no no 241)

| ID | Nome | Mensagem |
|----|------|---------|
| 1045 | msg_transferir_atendimento | "Aguarde um momento que vou te transferir para um de nossos atendentes 👥" |
| 1081 | msg_fora_do_horario | "No momento não temos agentes disponíveis, mas não se preocupe, vou fazer um registro da sua solicitação e daremos um retorno o mais breve possível." |
| 1280004 | msg_ajudo_em_algo_mais | "Eu posso te ajudar em algo mais 😊?" |
| 1280001 | msg_informar_cpf | "Informe por gentileza o CPF ou CNPJ do titular do contrato." |
| 1046 | msg_cpf_invalido | "CPF ou CNPJ informado inválido. Digite novamente!" |
| 1280005 | msg_cpf_nao_encontrado | "CPF ou CNPJ não localizado. Digite novamente!" |
| 1280003 | msg_finalizacao_cpf_invalido | "CPF ou CNPJ informado inválido!" |
| 1280002 | msg_finalizacao_cpf_nao_localizado | "CPF ou CNPJ informado não localizado!" |
| 1040 | msg_finalizacao_geral | "A {#nome_empresa} agradece o seu contato! Se precisar de algo mais estaremos à sua disposição, é sempre um prazer atendê-lo!" |
| 1180001 | msg_finalizacao_tentativas | "Seu atendimento foi finalizado por tentar escolher opções invalidas varias vezes. Peço que entre em contato novamente." |
| 1042 | msg_pesquisa_satisfacao | "Participe da nossa pesquisa de satisfação!" |
| 1280015 | msg_opcao_invalida | "Escolha uma opção válida" |
| 1034 | msg_inatividade | "Seu atendimento foi finalizado por inatividade. Peço que entre em contato novamente." |
| 3470002 | tempo_de_inatividade | **10** (segundos — timeout padrao) |
| 3470003 | qtd_max_tentativas_invalidas | **3** (tentativas antes de encerrar) |

### 3.4 Dados do lead / prospecto

| ID | Nome | Descricao |
|----|------|-----------|
| 3620083 | id_lead | ID do lead na aplicacao Django |
| 3620087 | result_get_leads | Resposta bruta do GET de consulta |
| 3620060 | prospecto_nome_completo | Nome completo |
| 3620055 | prospecto_cpf | CPF (com validacao tipo 1) |
| 3620056 | prospecto_rg | RG (validacao tipo 5 - regex numeros) |
| 3620057 | prospecto_nascimento | Data de nascimento |
| 3620079 | prospecto_email | E-mail |
| 3620051 | prospecto_cep | CEP |
| 3620052 | prospecto_bairro | Bairro |
| 3620053 | prospecto_rua | Rua |
| 3620054 | prospecto_n_resisdencia | Numero da residencia |
| 3620090 | prospecto_ponto_referencia | Ponto de referencia |
| 3620061 | prospecto_cidade | Cidade |
| 3620058 | id_plano_prospecto | ID do plano selecionado |
| 3620059 | valor_plano_prospecto | Valor do plano selecionado |
| 3620063 | prospecto_titulo_plano | Nome/titulo do plano |
| 3620050 | id_vencimento_prospect | ID do dia de vencimento escolhido |
| 3620062 | prospecto_dia_exato_vencimento | Dia exato do vencimento |

### 3.5 Endereco (retorno da API de CEP)

| ID | Nome | Descricao |
|----|------|-----------|
| 3620069 | ret_cep | CEP retornado |
| 3620070 | ret_bairro | Bairro retornado |
| 3620071 | ret_cidade | Cidade retornada |
| 3620072 | ret_estado | Estado retornado (UF) |
| 3620073 | ret_rua | Rua retornada |
| 3620066 | api_cep | Mensagem de retorno da API de CEP |
| 3620094 | viabilidade_cep | Se o CEP tem cobertura |

### 3.6 Documentos

| ID | Nome | Descricao |
|----|------|-----------|
| 3620084 | img_doc1 | Selfie com documento |
| 3620085 | img_doc2 | Frente do documento |
| 3620086 | img_doc3 | Verso do documento |
| 3620116 | documentacao_validada | Se docs foram validados |
| 3620117 | total_doc_rejeitado | Contador de docs rejeitados |

### 3.7 Agendamento de instalacao

| ID | Nome | Descricao |
|----|------|-----------|
| 3620097 | turno_instalacao | Turno escolhido (manha/tarde) |
| 3620115 | cliente_data_insta | Data de instalacao escolhida |
| 3620099 | dados_agenda | Resposta da consulta de agenda |
| 3620100 | opt1_horario | Horario opcao 1 |
| 3620101 | opt2_horario | Horario opcao 2 |
| 3620088 | time_instalacao | Horario final da instalacao |
| 3620111 | id_agenda_os | ID da agenda retornada |
| 3620112 | data_instalacao_1 | Data opcao 1 |
| 3620113 | data_instalacao_2 | Data opcao 2 |
| 3620114 | data_instalacao_3 | Data opcao 3 |

### 3.8 Atendimento / OS (Matrix/Hubsoft)

| ID | Nome | Descricao |
|----|------|-----------|
| 3620025 | id_atendimento_api | ID do atendimento aberto |
| 3620106 | id_atendimento_abrir_os | ID do atendimento para a OS |
| 3620105 | id_tipo_atendimento_instalacao | Tipo de atendimento |
| 3620107 | id_tipo_os | Tipo de OS |
| 3620108 | primeiro_tec_disponivel | Tecnico disponivel |
| 3620109 | status_os_api | Status da OS |
| 3620110 | duracao | Duracao estimada |
| 3620104 | body_descricao | Descricao do atendimento |
| 3620095 | is_a_client_hubsoft | Se ja e cliente no Hubsoft |
| 3620096 | contador_verifica_status_cliente | Contador de tentativas de verificacao |

### 3.9 Controle de fluxo

| ID | Nome | Descricao |
|----|------|-----------|
| 3620064 | qtd_invalidas | Contador de respostas invalidas |
| 3620065 | dinamica_invalida | Logica de invalidas |
| 3620015 | qtd_tempo_espera | Contador de timeouts |
| 3620016 | dinamica_tempo_espera | Logica de timeouts |
| 3620080 | needsReception | Precisa de atendimento humano |
| 3620081 | isAClient | Se e cliente (fluxo pos-venda) |

---

## 4. Chamadas de API

### 4.1 GET — Consultar lead por telefone

```
GET {url_api}/api/consultar/leads/?search={CONTATO.TELEFONE}&origem=whatsapp&ativo=true&page=1
```
- **Quando:** logo no inicio do fluxo, ao receber a mensagem
- **Objetivo:** verificar se o numero ja esta cadastrado como lead
- **Resultado:** armazenado em `result_get_leads` (3620087)
- **Proximo passo:** extrai o ID do primeiro resultado e salva em `id_lead` (3620083)

---

### 4.2 POST — Registrar historico de inicio

```
POST {url_api}/api/historicos/registrar/
```
**Body:**
```json
{
  "telefone": "{CONTATO.TELEFONE}",
  "nome_contato": "{CONTATO.NOME}",
  "origem_contato": "whatsapp",
  "status": "fluxo_inicializado",
  "observacoes": "fluxo inicializado",
  "lead_id": {id_lead},
  "numero_conta": "{NOME_CONTA}",
  "protocolo_atendimento": "{PROTOCOLO}",
  "id_conta": {CODIGO_CONTA},
  "ultima_mensagem": "{MENSAGEM}",
  "codigo_atendimento": "{CODIGO_ATENDIMENTO}"
}
```
- **Quando:** logo apos consulta do lead (nos 5750 e 5972)
- **Objetivo:** registrar que o fluxo comecou

---

### 4.3 POST — Registrar novo lead

```
POST {url_api}/api/leads/registrar/
```
**Body:**
```json
{
  "nome_razaosocial": "{CONTATO.NOME}",
  "telefone": "{CONTATO.TELEFONE}",
  "origem": "whatsapp",
  "canal_entrada": "whatsapp",
  "tipo_entrada": "contato_whatsapp",
  "status_api": "processamento_manual",
  "id_vendedor_rp": 1618,
  "id_origem": "106",
  "id_origem_servico": "74"
}
```
- **Quando:** lead nao encontrado na consulta inicial (novo contato)
- **Objetivo:** criar o registro do lead na aplicacao Django

---

### 4.4 POST — Atualizar lead (plano)

```
POST {url_api}/api/leads/atualizar/
```
**Body:**
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "id_plano_rp": {id_plano_prospecto},
  "valor": {valor_plano_prospecto}
}
```
- **Quando:** apos selecao do plano

---

### 4.5 POST — Atualizar lead (endereco)

```
POST {url_api}/api/leads/atualizar/
```
**Body:**
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "bairro": "{ret_bairro}",
  "cidade": "{ret_cidade}",
  "rua": "{ret_rua}",
  "cep": "{prospecto_cep}",
  "cpf_cnpj": "{prospecto_cpf}",
  "estado": "{ret_estado}",
  "endereco": "{ret_rua}, {ret_numero} - {ret_bairro}, {ret_cidade} - {ret_estado}, CEP: {prospecto_cep}"
}
```
- **Quando:** apos confirmacao de endereco

---

### 4.6 POST — Atualizar lead (dados pessoais)

```
POST {url_api}/api/leads/atualizar/
```
**Body:**
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "numero_residencia": "{prospecto_n_resisdencia}",
  "nome_razaosocial": "{prospecto_nome_completo}",
  "ponto_referencia": "{prospecto_ponto_referencia}",
  "rg": "{prospecto_rg}"
}
```

---

### 4.7 POST — Atualizar lead (email, nascimento, vencimento)

```
POST {url_api}/api/leads/atualizar/
```
**Body:**
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "email": "{prospecto_email}",
  "data_nascimento": "{prospecto_nascimento}",
  "id_dia_vencimento": "{id_vencimento_prospect}"
}
```

---

### 4.8 POST — Finalizar lead (status pendente)

```
POST {url_api}/api/leads/atualizar/
```
**Body:**
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "empresa": "{nome_empresa_api}",
  "status_api": "pendente",
  "observacoes": "Finalizado"
}
```
- **Quando:** apos todos os dados coletados e validados
- **Efeito:** aciona o signal Django que enviara o lead ao Hubsoft

---

### 4.9 POST — Registrar imagem do documento (3 chamadas)

```
POST {url_api}/api/leads/imagens/registrar/
```
**Chamada 1 — Selfie com documento:**
```json
{
  "lead_id": {id_lead},
  "link_url": "{img_doc1}",
  "descricao": "selfie_com_doc"
}
```
**Chamada 2 — Frente do documento:**
```json
{
  "lead_id": {id_lead},
  "link_url": "{img_doc2}",
  "descricao": "frente_doc"
}
```
**Chamada 3 — Verso do documento:**
```json
{
  "lead_id": {id_lead},
  "link_url": "{img_doc3}",
  "descricao": "verso_doc"
}
```
- **Quando:** apos recepcao das 3 fotos pelo WhatsApp

---

### 4.10 GET — Verificar status Hubsoft do lead

```
GET {url_api}/integracoes/api/lead/hubsoft-status/?lead_id={id_lead}
```
- **Quando:** apos finalizar o lead (`status_api=pendente`) — loop de verificacao
- **Objetivo:** verificar se o Hubsoft ja processou o lead (se virou cliente)
- **Controle:** variavel `contador_verifica_status_cliente` conta as tentativas
- **Espera:** no de espera de 20 segundos entre tentativas (comp 26)

---

### 4.11 POST — Consultar CEP via webhook Aurora

```
POST {webhook_aurora}
```
**Body:**
```json
{
  "question": "Você pode me passar o CEP do local?",
  "answer": "{prospecto_cep}",
  "cellphone": "{CONTATO.TELEFONE}"
}
```
- **Quando:** lead informa o CEP
- **Objetivo:** buscar endereco e verificar viabilidade da area
- **Retorno:** popula variaveis `ret_cep`, `ret_bairro`, `ret_cidade`, `ret_estado`, `ret_rua`, `api_cep`, `viabilidade_cep`

---

### 4.12 POST — Validar resposta dinamica via webhook Aurora

```
POST {webhook_aurora}
```
**Body:**
```json
{
  "question": "{pergunta_cliente}",
  "answer": "{resposta_cliente}",
  "cellphone": "{CONTATO.TELEFONE}"
}
```
- **Quando:** em pontos de validacao dinamica de resposta

---

### 4.13 POST — Validar resposta via N8N DynamicValidator

```
POST https://automation-n8n.v4riem.easypanel.host/webhook/ade59082-6e57-4fda-b689-0844fdf66edbDynamicValidator
```
**Body:**
```json
{
  "question": "{pergunta_cliente}",
  "answer": "{resposta_cliente}",
  "telefone": "{CONTATO.TELEFONE}"
}
```

---

### 4.14 POST — Ping webhook Matrix

```
POST https://automation-n8n.v4riem.easypanel.host/webhook/matrix
```
**Body:**
```json
{
  "atendimento_id": "1",
  "answer": "oi",
  "telefone": "{CONTATO.TELEFONE}"
}
```

---

### 4.15 GET — Consultar datas de instalacao (sem domingo)

```
GET https://apimatrix.megalinkpiaui.com.br/consultar_datas_sem_domingo?data_referencia={DATE(d/m/Y)}
```
- **Quando:** inicio do agendamento de instalacao
- **Objetivo:** listar datas disponiveis para instalacao (excluindo domingos)
- **Retorna:** `data_instalacao_1`, `data_instalacao_2`, `data_instalacao_3`

---

### 4.16 GET — Consultar agenda de instalacao

```
GET {url_api_matrix}/consultar_agenda?cidade={ret_cidade}&data_referencia={cliente_data_insta}&turno={turno_instalacao}&qtd_vagas=1
```
- **Quando:** lead escolhe data e turno
- **Objetivo:** verificar disponibilidade e obter `id_agenda_os`

---

### 4.17 POST — Abrir atendimento no Matrix

```
POST {url_api_matrix}/abrir_atendimento
```
**Body:**
```json
{
  "id_cliente_servico": {id_cliente_servico_api},
  "nome": "ClienteVenda",
  "telefone": "{CONTATO.TELEFONE}",
  "descricao": "{body_descricao}",
  "id_tipo_atendimento": {id_tipo_atendimento_instalacao},
  "id_atendimento_status": {id_status_atendimento},
  "id_usuario_responsavel": {id_user_responsavel},
  "empresa": "{nome_empresa_api}"
}
```
- **body_descricao inclui:** nome completo, CPF, nascimento, endereco completo, plano, valor, data instalacao

---

### 4.18 POST — Abrir OS no Matrix

```
POST {url_api_matrix}/abrir_os
```
**Body:**
```json
{
  "id_atendimento": {id_atendimento_abrir_os},
  "id_tipo_ordem_servico": {id_tipo_os},
  "id_agenda_ordem_servico": {id_agenda_os},
  "data_inicio_programado": "{cliente_data_insta}",
  "data_termino_programado": "{cliente_data_insta}",
  "hora_inicio_programado": "{opt1_horario}",
  "duracao": "{duracao}",
  "status": "{status_os_api}",
  ...
}
```

---

### 4.19 POST — Registrar historico (varios momentos)

```
POST {url_api}/api/historicos/registrar/
```
Chamado com diferentes `status`:
- `fluxo_inicializado` — inicio do fluxo
- `fluxo_finalizado` com `sucesso: True` — conclusao bem-sucedida
- `transferido_humano` — quando transfere para atendente
- `resposta` — quando registra resposta do lead em pergunta

---

## 5. Fluxo Principal — Passo a Passo

```
MENSAGEM RECEBIDA
       |
       v
[INIT] Inicializa variaveis
  - var_mensagens (no 241): mensagens, timeouts, tentativas
  - var_servidor (no 5004): urls das APIs
  - var_11 (no 5551): IDs empresa, nome, msg boas-vindas
       |
       v
[API] GET leads por telefone (api_14)
  URL: {url_api}/api/consultar/leads/?search={telefone}
       |
       v
[VAR] Extrai id_lead do resultado (var_6, no 6032)
       |
       +----[Lead encontrado?]----+
       |                         |
      SIM                       NAO
       |                         |
[API] Registra historico    [API] Registra historico
  status=fluxo_inicializado    status=fluxo_inicializado
  com id_lead preenchido       sem id_lead
       |                         |
       |                    [FLUXO NOVO LEAD]
       |                    (ver secao 5.1)
       |
[VERIFICACAO] Lead e cliente ativo? (dec_1)
  Checa is_a_client_hubsoft / isAClient
       |
       +-- E CLIENTE -------> [Fluxo pos-venda / suporte]
       |
       +-- NAO E CLIENTE ---> [FLUXO PROSPECTO]
                              (ver secao 5.2)
```

---

### 5.1 Fluxo Novo Lead (lead nao existe na base)

```
[API] Cria lead (api_8)
  POST /api/leads/registrar/
  status_api = processamento_manual
       |
       v
[MENSAGEM] Boas-vindas
  "Oi! Que bom ter você aqui na {nome_empresa} Internet 🚀
  Para começarmos, qual é o seu nome?"
       |
       v
[INPUT] Aguarda nome (armazenado no CONTATO.NOME)
       |
       v
[Continua em 5.2 — FLUXO PROSPECTO]
```

---

### 5.2 Fluxo Prospecto (novo ou existente sem ser cliente)

```
ETAPA 1: ENDERECO
══════════════════════════════════════════
[MENSAGEM] "Digite o seu CEP. 🏠
           (Exemplo: XXXXX-XXX)"
       |
       v
[INPUT] sol_7 — coleta CEP → var prospecto_cep (3620051)
       timeout: {tempo_de_inatividade}
       |
       v
[API] Consulta CEP via webhook Aurora (api_consulta_cep)
  POST {webhook_aurora}
  body: { question, answer: CEP, cellphone }
       |
       v
[DEC dec_3] Resposta da API de CEP ok?
  |               |
  OK          ERRO/SEM COBERTURA
  |               |
  |         [MODO MANUAL]
  |         Perguntas individuais:
  |           - "Qual é o nome da sua rua?" → prospecto_rua
  |           - "Qual é o bairro?" → prospecto_bairro
  |           - "Para qual cidade?" → prospecto_cidade
  |           - "Digite o seu CEP" → prospecto_cep (novamente)
  |         Se sem estado: "Informe a UF (ex: PI, MA, CE)"
  |
  v
[URA ura_7] Confirma endereco automatico
  "Confirme seu endereço:
  CEP: {ret_cep}
  Estado: {ret_estado}
  Cidade: {ret_cidade}
  Bairro: {ret_bairro}
  Rua: {ret_rua}
  Posso seguir com esses dados?"
  Opcoes: [Sim] [Não, corrigir]
       |
       +--[NAO]---> Modo manual (acima)
       |
       v
[MENSAGEM] "Só mais um passo 😀
           Vou verificar quais planos estão disponíveis
           na sua região."
       |
       v
═══════════════════════════════════════════
ETAPA 2: PLANO
═══════════════════════════════════════════
[URA ura_14] Uso residencial ou empresarial?
  "A internet será para sua casa ou para sua empresa?
  Assim já te indico o melhor plano 😀"
  Opcoes: [Casa] [Empresa]
       |
       v
[URA ura_plano] Plano destaque (620MB)
  "🎺 Ótima notícia, {CONTATO.NOME}!
  Temos uma promoção exclusiva da Megalink...
  📶 620 Mega — R$ 99,90/mês
  (valor com desconto de pontualidade)
  🚀 Ideal para filmes, jogos, home office"
  Opcoes: [Quero esse plano!] [Ver outros planos] [Falar com atendente]
       |
       +--[VER OUTROS]---> [URA ura_plano_2]
       |                   Lista de planos alternativos com mais velocidade
       |
       +--[ATENDENTE]----> [Transfere para humano]
       |
       +--[QUERO]--------> Salva id_plano / valor
                           [API] Atualiza lead com plano (api_9)
       |
       v
═══════════════════════════════════════════
ETAPA 3: DADOS PESSOAIS
═══════════════════════════════════════════
[MENSAGEM] "Perfeito, {CONTATO.NOME}! ✏️"
       |
       v
[MENSAGEM] "Para darmos sequência ao seu cadastro,
           pode me informar seu nome completo?"
[INPUT] → prospecto_nome_completo (3620060)
       |
       v
[MENSAGEM] "{CONTATO.NOME}, é bem rapidinho ✏️
           Para dar continuidade, pode me informar seu CPF?
           (Exemplo: 999.999.999-99)"
[INPUT] → prospecto_cpf (3620055) — validacao tipo 1 (CPF/CNPJ)
       |
       v
[MENSAGEM] "Agora, digite o número do seu RG."
[INPUT] → prospecto_rg (3620056) — validacao tipo 5 (regex: so numeros)
  Se invalido: "Resposta Inválida. Digite somente os numeros do seu RG."
       |
       v
[MENSAGEM] "Pode me informar seu e-mail? ✏️
           (Exemplo: exemplo@email.com)"
[INPUT] → prospecto_email (3620079)
       |
       v
[MENSAGEM] "Informe sua data de nascimento.
           (No formato: 01/01/2000)"
[INPUT] → prospecto_nascimento (3620057)
       |
       v
[MENSAGEM] "Certo! Agora digite apenas o número do endereço,
           sem o complemento: (Exemplo: N° 99)
           Se for sem número, envie s/n."
[INPUT] → prospecto_n_resisdencia (3620054)
       |
       v
[MENSAGEM] "Só pra ajudar nosso time na instalação ✏️
           Tem algum ponto de referência perto da sua casa?"
[INPUT] → prospecto_ponto_referencia (3620090)
       |
       v
[API] Atualiza lead com dados pessoais (api_10, api_11)
       |
       v
═══════════════════════════════════════════
ETAPA 4: DOCUMENTOS
═══════════════════════════════════════════
[MENSAGEM] "Já estamos quase finalizando, {CONTATO.NOME} ✏️
           Para garantir a segurança da sua contratação,
           preciso que você envie 3 fotos.
           Pode começar enviando uma selfie segurando
           seu documento de identidade ao lado do rosto."
[INPUT sol_16] → img_doc1 (3620084) — timeout: 20s
       |
       v
[VAR] Formata URL: megalink.matrixdobrasil.ai/.../img_doc1
[API] Registra imagem selfie_com_doc (api_18)
       |
       v
[MENSAGEM] "Em seguida, precisamos da foto da frente do
           documento, garantindo que as informações
           estejam legíveis."
[INPUT sol_17] → img_doc2 (3620085) — timeout: 20s
[VAR] Formata URL
[API] Registra imagem frente_doc (api_19)
       |
       v
[MENSAGEM] "Última etapa: precisamos da foto da
           parte de trás do seu RG/CNH"
[INPUT sol_18] → img_doc3 (3620086) — timeout: 20s
[VAR] Formata URL
[API] Registra imagem verso_doc (api_20)
       |
       v
═══════════════════════════════════════════
ETAPA 5: VENCIMENTO DA FATURA
═══════════════════════════════════════════
[URA ura_12 / ura_9 / ura_6]
  "Agora, só preciso que me informe qual a melhor data
  para vencimento da sua fatura. Lembre-se de escolher
  uma data próxima ao recebimento do seu salário."
  → Opcoes de datas de vencimento
  → Salva id_vencimento_prospect e prospecto_dia_exato_vencimento
       |
       v
[API] Atualiza lead com email/nascimento/vencimento (api_email_nas_ven)
       |
       v
═══════════════════════════════════════════
ETAPA 6: CONFIRMACAO FINAL
═══════════════════════════════════════════
[URA ura_13] Exibe resumo completo:
  "*Confirme seus dados, por favor:*
  Plano: {prospecto_titulo_plano}
  Valor: R$ {valor_plano_prospecto}
  Vencimento: Dia {prospecto_dia_exato_vencimento}
  Nome: {prospecto_nome_completo}
  CPF: {prospecto_cpf}
  Telefone: {CONTATO.TELEFONE}
  Data de Nascimento: {prospecto_nascimento}
  CEP: {prospecto_cep}
  Endereço: {prospecto_rua}, Nº {prospecto_n_resisdencia}
  Bairro: {prospecto_bairro} | Cidade: {prospecto_cidade}"
  Opcoes: [Confirmar] [Corrigir dados]
       |
       +--[CORRIGIR]---> Retorna para campos faltantes (dec campos_faltantes)
       |
       v
[MENSAGEM] "📍 Sobre a cobrança
           Como o plano será ativado antes da data de vencimento,
           o valor da primeira fatura será proporcional."
       |
       v
═══════════════════════════════════════════
ETAPA 7: FINALIZACAO E AGENDAMENTO
═══════════════════════════════════════════
[URA ura_8] Prefere contratar pelo site ou WhatsApp?
  "Ótimo, {CONTATO.NOME}!
  A contratação é rápida e 100% segura.
  Prefere contratar pelo site ou continuar com nosso time aqui no WhatsApp?"
  Opcoes: [Site] [WhatsApp]
       |
       +--[SITE]---> Envia link do cadastro online
       |             "Você pode concluir sua contratação agora mesmo pelo
       |             nosso site... https://cadastro.megalinkpiaui.com.br"
       |             → Finaliza
       |
       +--[WHATSAPP]-> [Finaliza lead no Django: status_api = pendente]
                       → Signal Django envia para Hubsoft
                       |
                       v
                [GET] Verifica status Hubsoft (loop)
                  Aguarda 20s, tenta novamente
                  max: contador_verifica_status_cliente tentativas
                       |
                       v
                [API] Consulta datas de instalacao
                  GET .../consultar_datas_sem_domingo
                       |
                       v
                [URA ura_10] Escolhe turno
                  "Perfeito! Para a instalação, qual é o melhor período?
                  O prazo é de até 48 horas."
                  Opcoes: [Manhã] [Tarde]
                       |
                       v
                [URA ura_11] Escolhe data
                  "Escolha a melhor data para você:"
                  Opcoes: {data_1} | {data_2} | {data_3}
                       |
                       v
                [API] Consulta agenda (api_22)
                  Verifica vaga na data/turno escolhidos
                       |
                       v
                [API] Abre atendimento no Matrix (api_23)
                [API] Abre OS no Matrix (api_24)
                       |
                       v
                [MENSAGEM] Confirmacao de agendamento
                  "Perfeito!
                  Sua instalação foi agendada com sucesso
                  para a data {cliente_data_insta} no turno {turno_instalacao}.
                  Nossa equipe técnica irá até o local dentro do turno
                  e data escolhida."
                       |
                       v
                [MENSAGEM msg_73] Encerramento
                  "Certinho, {prospecto_nome_completo}
                  Finalizamos sua contratação com sucesso.
                  Em instantes, nosso time de atendimento vai falar
                  com você para concluir a contratação, enviar o termo
                  de adesão e passar todas as orientações certinhas.
                  Seja muito bem-vindo(a) à Megalink Internet 🚀"
                       |
                       v
                [API] Registra historico status=fluxo_finalizado
                [FIN] Encerra atendimento no bot
```

---

## 6. Ramificacoes e Decisoes

| No | Identificador | O que verifica | Saida SIM | Saida NAO |
|----|--------------|----------------|-----------|-----------|
| 5719 | dec_1 | Se lead e cliente ativo (isAClient) | Fluxo cliente | Fluxo prospecto |
| 5777 | campos_faltantes | Quais campos ainda faltam preencher | Campo especifico | Proximo passo |
| 5786 | dec_3 | Resposta da API de CEP ok | Exibe URA de confirmacao | Modo manual |
| 5899 | dec_4 | Tem atendimento aberto? | Encaminha para humano | Continua fluxo |
| 5914 | dec_5 | Validacao de resposta de input | Input valido | Invalido (contador) |
| 5970 | dec_6 | Status da resposta dinamica | Segue | Transfere humano |
| 6006 | dec_7 | Resultado da API de status Hubsoft | Hubsoft ok | Aguarda novamente |
| 6038 | dec_8 | Timeout de resposta do input de doc | Imagem recebida | Timeout |
| 6058 | dec_9 | Status do agendamento de instalacao | Agenda ok | Sem vaga |
| 6102 | dec_10 | Contador de invalidas >= 3 | Encerra por tentativas | Volta para input |
| 6108 | dec_11 | Contador de timeouts >= limite | Encerra por inatividade | Volta para input |
| 6111 | dec_12 | Viabilidade do CEP | Tem cobertura | Sem cobertura na area |
| 6115 | dec_13 | Opcao escolhida pelo lead na URA | Roteia por opcao | Invalido |
| 6122 | dec_14 | Selecao de plano | Plano 1 / outros | -- |
| 6131 | dec_15 | Confirmacao de dados (ura_13) | Confirma | Corrige |
| 6164 | dec_16 | contador_verifica_status_cliente | Continua esperando | Desiste |
| 6173 | dec_17 | Status da abertura de OS | OS aberta | Erro |
| 6228 | dec_18 | Preferencia de contratacao | Site | WhatsApp |
| 6230 | dec_19 | Turno escolhido | Manha | Tarde |
| 6235 | dec_20 | Data de instalacao disponivel | Agenda disponivel | Indisponivel |

### Logica de contador de invalidas

A cada resposta invalida, executa o no `var_4` (no 5722):
```
qtd_invalidas = CALC(qtd_invalidas + 1)
```
Ao atingir **3 tentativas** (dec_10): encerra com `msg_finalizacao_tentativas`.

### Logica de timeout

A cada timeout, executa o no `var_5` (no 6013):
```
qtd_tempo_espera = CALC(qtd_tempo_espera + 1)
```
Ao atingir o limite (dec_11): encerra com `msg_inatividade`.

---

## 7. Mensagens Enviadas ao Lead

| No | Identificador | Mensagem |
|----|--------------|---------|
| 5571 | msg_60 | "Oi! Que bom ter você aqui na {nome_empresa} Internet 🚀\nPara começarmos, qual é o seu nome?" |
| 5576 | msg_cidade | "Para qual a cidade que solicita atendimento?" |
| 5579 | msg_rua | "Qual é o nome da sua rua?" |
| 5583 | msg_bairro | "Qual é o bairro?" |
| 5585 | msg_cep | "Para seguirmos com o atendimento de forma adequada..." |
| 5608 | msg_n_residencia | "Certo! Agora digite apenas o número do endereço, sem o complemento: (Exemplo: N° 99)\nSe for uma residência sem número, envie s/n." |
| 5611 | msg_ponto_referencia | "Só pra ajudar nosso time na instalação ✏️\nTem algum ponto de referência perto da sua casa?" |
| 5614 | msg_Nome_completo | "Para darmos sequência ao seu cadastro, pode me informar seu nome completo, por favor?" |
| 5617 | msg_sol_cpf | "{CONTATO.NOME}, é bem rapidinho ✏️\nPara dar continuidade ao atendimento, pode me informar seu CPF?\n(Exemplo: 999.999.999-99)" |
| 5618 | msg_sol_rg | "Pode me informar seu e-mail, por favor? ✏️\n(Exemplo: exemplo@email.com)" |
| 5619 | msg_sol_nascimento | "Informe sua data de nascimento.\n(No formato: 01/01/2000)" |
| 5646 | msg_72 | "📍 Sobre a cobrança\nImportante! Sobre a primeira mensalidade: Como o plano será ativado antes da data de vencimento, o valor da primeira fatura será proporcional aos dias utilizados..." |
| 5658 | msg_73 | "Certinho, {prospecto_nome_completo}\nFinalizamos sua contratação com sucesso.\nEm instantes, nosso time de atendimento vai falar com você para concluir a contratação, enviar o termo de adesão e passar todas as orientações certinhas.\nSeja muito bem-vindo(a) à Megalink Internet 🚀" |
| 5709 | msg_finaliza | "Em breve, um de nossos especialistas entrará em contato para agendar a instalação do seu plano e garantir que você aproveite ao máximo sua nova conexão." |
| 5748 | msg_15 | "Resposta Invalida! por favor responda de acordo com o esperado!" |
| 5803 | msg_16 | "{retorno_erro_api}" (erro da API de CEP) |
| 5822 | msg_manual_rua | "Qual é o nome da sua rua?" |
| 5832 | msg_manual_bairro | "Qual é o bairro?" |
| 5840 | msg_manual_cidade | "Para qual a cidade que solicita atendimento?" |
| 5848 | msg_manual_cep | "Digite o seu CEP. 🏠\n(Exemplo: XXXXX-XXX)" |
| 5856 | msg_21 | "{api_cep}" (retorno da API de CEP) |
| 5858 | msg_22 | "Só mais um passo 😀\nVou verificar quais planos estão disponíveis na sua região." |
| 5869 | msg_23 | "Perfeito, {CONTATO.NOME}! ✏️" |
| 5879 | msg_24 | "Perfeito! Você pode concluir sua contratação agora mesmo pelo nosso site.\nÉ rápido, seguro e leva menos de 2 minutos.\nClique no link abaixo: https://cadastro.megalinkpiaui.com.br" |
| 5895 | msg_25 | "Aguarde um momento que vou te transferir para um de nossos atendentes 👥" |
| 5902 | msg_26 | "Aguarde um momento que vou te transferir para um de nossos atendentes 👥" |
| 5903 | msg_27 | "Aguarde um momento que vou te transferir para um de nossos atendentes 👥" |
| 5920 | msg_28 | "Já estamos quase finalizando, {CONTATO.NOME} ✏️\nPara garantir a segurança da sua contratação, preciso que você envie 3 fotos.\nPode começar enviando uma selfie segurando seu documento de identidade ao lado do rosto." |
| 5922 | msg_29 | "Em seguida, precisamos da foto da frente do documento, garantindo que todas as informações estejam legíveis." |
| 5923 | msg_30 | "Última etapa: precisamos da foto da parte de trás do seu RG/CNH" |
| 5936 | msg_31 | "Pode começar enviando uma selfie segurando seu documento de identidade ao lado do rosto." |
| 5952 | msg_33 | "Digite o seu CEP. 🏠\n(Exemplo: XXXXX-XXX)" |
| 6016 | msg_33 | "Ainda não recebi sua resposta!\nEstou retomando sua contratação para darmos sequência ao processo. 😊" |
| 6084 | msg_35 | "Agora, digite o número do seu RG." |
| 6090 | msg_36 | "Resposta Inválida.\nDigite somente os numeros do seu RG." |
| 6144 | msg_estado_manual | "Olá! Poderia me informar qual é a UF (sigla do estado) onde você reside?\nExemplo: PI, MA, CE." |
| 6226 | msg_38 | "Perfeito!\nSua instalação foi agendada com sucesso para a data {cliente_data_insta} no turno {turno_instalacao}.\nNossa equipe técnica irá até o local dentro do turno e data escolhida. Caso precise de algo ou tenha alguma dúvida, estamos à disposição!" |

---

## 8. Menus Interativos (URA)

### URA ura_14 — Uso da internet
**Mensagem:** "Perfeito! ✏️\nA internet será para sua casa ou para sua empresa? Assim já te indico o melhor plano 😀"
**Botoes:** [Casa] [Empresa]

### URA ura_plano — Plano destaque 620MB
**Cabecalho:** imagem `620MB (2).png`
**Mensagem:** Apresenta plano de 620MB por R$ 99,90/mes com beneficios
**Botoes:** [Quero esse plano!] [Ver outros planos] [Falar com atendente]

### URA ura_plano_2 — Mais planos
**Mensagem:** "Ótimo, pois temos os seguintes planos disponíveis com mais velocidade e ainda mais benefícios para você."
**Tipo:** lista (bol_botoes_ura=2)

### URA ura_7 — Confirmacao de endereco (CEP automatico)
**Mensagem:**
```
Confirme seu endereço:
CEP: {ret_cep}
Estado: {ret_estado}
Cidade: {ret_cidade}
Bairro: {ret_bairro}
Rua: {ret_rua}
Posso seguir com esses dados?
```
**Botoes:** [Sim] [Não, corrigir]

### URA ura_8 — Canal de contratacao
**Mensagem:** "Ótimo, {CONTATO.NOME}!\nA contratação é rápida e 100% segura.\nPrefere contratar pelo site ou continuar com nosso time aqui no WhatsApp?"
**Botoes:** [Site] [WhatsApp]

### URA ura_12 — Vencimento da fatura (versao longa)
**Mensagem:** "Agora, só preciso que me informe qual a melhor data para vencimento da sua fatura. Lembre-se de escolher uma data próxima ao recebimento do seu salário para facilitar a lembrança:"
**Botoes:** dias do mes

### URA ura_9 — Vencimento da fatura (versao simplificada)
**Mensagem:** "Informe qual a melhor data para vencimento da sua fatura."

### URA ura_13 — Confirmacao final de dados
**Mensagem:** Exibe resumo completo (plano + dados pessoais + endereco)
**Botoes:** [Confirmar] [Corrigir dados]

### URA ura_10 — Turno de instalacao
**Mensagem:** "Perfeito! Para a instalação, qual é o melhor período para você?\nO prazo para instalação é de até 48 horas, podendo ser realizado antes disso. Qual sua preferência?"
**Botoes:** [Manhã] [Tarde]

### URA ura_11 — Data de instalacao
**Mensagem:** "Escolha a melhor data para você:"
**Botoes:** {data_instalacao_1} | {data_instalacao_2} | {data_instalacao_3}

---

## 9. Coleta de Dados (Inputs)

| No | Identificador | Variavel Destino | Validacao | Timeout |
|----|--------------|-----------------|-----------|---------|
| 5570 | sol_2 | — | 0 (nenhuma) | {tempo_de_inatividade} |
| 5577 | sol_cidade | prospecto_cidade (3620061) | 0 | {tempo_de_inatividade} |
| 5580 | sol_rua | prospecto_rua (3620053) | 0 | {tempo_de_inatividade} |
| 5582 | sol_bairro | prospecto_bairro (3620052) | 0 | {tempo_de_inatividade} |
| 5586 | sol_7 | prospecto_cep (3620051) | 0 | {tempo_de_inatividade} |
| 5593 | sol_13 | prospecto_n_resisdencia (3620054) | 0 | {tempo_de_inatividade} |
| 5596 | sol_13 | prospecto_ponto_referencia (3620090) | 0 | {tempo_de_inatividade} |
| 5598 | sol_13 | prospecto_nome_completo (3620060) | 0 | {tempo_de_inatividade} |
| 5600 | sol_13 | prospecto_nascimento (3620057) | 0 | {tempo_de_inatividade} |
| 5601 | sol_13 | prospecto_email (3620079) | 0 | {tempo_de_inatividade} |
| 5604 | sol_13 | prospecto_cpf (3620055) | **1** (CPF/CNPJ) | {tempo_de_inatividade} |
| 5823 | sol_12 | prospecto_rua (3620053) | 0 | {tempo_de_inatividade} |
| 5835 | sol_bairro | prospecto_bairro (3620052) | 0 | {tempo_de_inatividade} |
| 5843 | sol_cidade | prospecto_cidade (3620061) | 0 | {tempo_de_inatividade} |
| 5851 | sol_cep | prospecto_cep (3620051) | 0 | {tempo_de_inatividade} |
| 5919 | sol_16 | img_doc1 (3620084) | 0 | **20s** |
| 5921 | sol_17 | img_doc2 (3620085) | 0 | **20s** |
| 5924 | sol_18 | img_doc3 (3620086) | 0 | **20s** |
| 6040 | sol_19 | — | 0 | **5s** |
| 6083 | sol_20 | prospecto_rg (3620056) | **5** (regex) | {tempo_de_inatividade} |
| 6145 | sol_21 | ret_estado (3620072) | 0 | **5s** |

**Tipos de validacao:**
- `0` — sem validacao (qualquer texto aceito)
- `1` — CPF ou CNPJ (formato e digitos verificadores)
- `5` — Regex (apenas numeros para RG)

---

## 10. Integracao com Webhook Aurora / N8N

O fluxo usa dois endpoints externos de IA para validacao dinamica:

### Webhook Aurora — `{webhook_aurora}`
URL: `https://automation-n8n.v4riem.easypanel.host/webhook/atendimento-v2`

Usado para:
1. **Consulta de CEP** — recebe CEP, retorna dados do endereco e viabilidade
2. **Validacao de resposta** — valida resposta livre do cliente a uma pergunta

Parametros sempre enviados:
```json
{
  "question": "pergunta feita ao lead",
  "answer": "resposta do lead",
  "cellphone": "{CONTATO.TELEFONE}"
}
```

**Codigos de resposta (campo `resposta_correta`):**
- `1` — Resposta valida e coerente
- `2` — Resposta do tipo e-mail (validacao especifica)
- `3` — Invalido ou timeout
- `5` — Formato regex incorreto

### DynamicValidator — N8N
URL: `https://automation-n8n.v4riem.easypanel.host/webhook/...DynamicValidator`

Usado para validacoes complementares com o mesmo contrato de parametros.

---

## 11. Finalizacoes Possiveis

| Situacao | Mensagem | Tipo |
|----------|---------|------|
| Lead optou pelo site | Link do cadastro online | Saida voluntaria |
| Contratacao concluida via WhatsApp | "Finalizamos sua contratação com sucesso..." | Sucesso com OS aberta |
| Transferencia para humano | "Aguarde um momento que vou te transferir..." | Transferencia (servico 4 ou 5) |
| 3 respostas invalidas | "Seu atendimento foi finalizado por tentar escolher opções invalidas varias vezes." | Encerramento automatico |
| Inatividade | "Seu atendimento foi finalizado por inatividade." | Encerramento automatico |
| Fora do horario | "No momento não temos agentes disponíveis..." | Horario indisponivel |

---

## 12. Mapa de Conexoes Simplificado

```
ENTRADA (comp 15, no 2)
    |
    v
INIT (comp 18, no 1250)
  ├─ var_mensagens (no 241)
  ├─ var_servidor (no 5004)
  ├─ var_empresa (no 5551)
  ├─ api_historico_inicio (no 5750)
  ├─ api_registra_lead (no 5939)
  ├─ api_get_leads (no 5975) ─────────────> result_get_leads
  └─ var_id_lead (no 6032)                    ↓ id_lead
    |
    v
FLUXO CEP / ENDERECO (comp 18, no 5755)
  ├─ msg_cep → input_cep
  ├─ api_consulta_cep → dec_3 ─[ok]──> ura_7 (confirma)
  │                           └[erro]─> modo manual (rua/bairro/cidade/cep)
  └─ dec_12 (viabilidade) ─[ok]──> FLUXO PLANO
                           └[sem]─> transfere

FLUXO PLANO (no 5569)
  ├─ ura_14 (casa/empresa)
  ├─ ura_plano → [quero] ─> salva plano → api_9
  │            → [outros] ─> ura_plano_2
  │            → [atendente] ─> transfere
  └─ ura_plano_2

FLUXO DADOS PESSOAIS (no 5908)
  ├─ msg_nome_completo → input
  ├─ msg_cpf → input (validacao=1)
  ├─ msg_rg → input (validacao=5)
  ├─ msg_email → input
  ├─ msg_nascimento → input
  ├─ msg_numero → input
  ├─ msg_ponto_ref → input
  └─ api_10, api_11 (atualiza lead)

FLUXO DOCUMENTOS (no 5712 / 5708)
  ├─ msg_28 → input_selfie (timeout=20s) → api_18
  ├─ msg_29 → input_frente (timeout=20s) → api_19
  └─ msg_30 → input_verso  (timeout=20s) → api_20

FLUXO VENCIMENTO (ura_12 / ura_9)
  └─ api_email_nas_ven (atualiza lead)

FLUXO CONFIRMACAO (ura_13)
  ├─ [confirmar] ─> FLUXO FINALIZACAO
  └─ [corrigir]  ─> dec_campos_faltantes

FLUXO FINALIZACAO (no 5708)
  ├─ ura_8 (site ou whatsapp)
  │   ├─ [site] ─> msg_24 (link) ─> fin_1
  │   └─ [whats] ─> api_finaliza_lead (status=pendente)
  │                  └─> loop verifica hubsoft
  │                       └─> api_datas_instalacao
  │                           └─> ura_10 (turno) ─> ura_11 (data)
  │                                └─> api_22 (consulta agenda)
  │                                    └─> api_23 (abre atendimento)
  │                                        └─> api_24 (abre OS)
  │                                            └─> msg_38 (agendado!)
  │                                                └─> msg_73 (sucesso)
  │                                                    └─> api_historico_finalizado
  │                                                        └─> fin_2
  └─ msg_73 → fin_2 (fallback)

SAIDAS DE ERRO
  ├─ 3x invalidas ─> msg_1180001 ─> fin
  ├─ timeout ──────> msg_1034 ───> fin
  ├─ fora horario ─> msg_1081 ───> fin
  └─ transferencia ─> ser_1 / ser_2 (filas de atendimento humano)
```
