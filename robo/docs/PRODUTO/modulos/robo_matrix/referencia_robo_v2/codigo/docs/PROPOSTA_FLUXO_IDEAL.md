# Proposta: Fluxo Ideal de Atendimento e Alimentacao do Sistema

> Documento de redesenho — 30/03/2026
> Base: DOCUMENTACAO_CRM.md + DOCUMENTACAO_FLOW_COMERCIAL.md

---

## Objetivo

Este documento define **exatamente quando e como** o fluxo de atendimento WhatsApp deve alimentar o sistema Django (LeadProspecto, CRM, Historico, Hubsoft) a cada passo. O foco e garantir que:

1. O CRM reflita em tempo real o progresso de cada lead
2. O historico registre cada evento significativo
3. As tags sejam atualizadas conforme dados sao preenchidos
4. Os estagios do pipeline avancem automaticamente
5. Nenhum dado se perca em caso de abandono ou transferencia

---

## Problemas do Fluxo Atual

| Problema | Impacto |
|----------|---------|
| Lead criado com `status_api=processamento_manual` — nao aciona signal do CRM (score < 7) | Oportunidade NAO e criada automaticamente |
| Historico so registrado no inicio e no fim | Sem visibilidade do progresso durante atendimento |
| CRM nao atualizado durante o fluxo | Kanban nao reflete a realidade do lead |
| Tags nao atualizadas em tempo real | Visao de completude no CRM esta defasada |
| Dados enviados em 5 chamadas separadas sem ordem garantida | Risco de parcialidade |
| Se lead abandona no meio, nenhum registro intermediario no CRM | Lead fica "fantasma" na qualificacao |
| Transferencia para humano nao registra motivo no CRM | Sem rastreabilidade |
| `status_api=pendente` so e setado no final — tudo antes disso e invisivel para signals | CRM cego para 90% do fluxo |

---

## Principios do Redesenho

1. **Uma chamada de API por acao concreta** — nao por formulario completo
2. **Historico a cada etapa** — nao so inicio/fim
3. **CRM atualizado em tempo real** via endpoints dedicados
4. **Fail-safe** — se o lead abandona em qualquer ponto, o sistema tem o maximo de dados possivel
5. **Lead criado JA qualificado** — para que o signal do CRM crie a oportunidade

---

## Fluxo Ideal — Passo a Passo

### FASE 0: Inicializacao

```
MENSAGEM RECEBIDA NO WHATSAPP
              |
              v
```

#### Passo 0.1 — Consultar lead existente

```
GET /api/consultar/leads/?search={TELEFONE}&origem=whatsapp&ativo=true&page=1
```

| Resultado | Acao |
|-----------|------|
| Lead encontrado | Armazena `id_lead`, segue para Passo 0.2 |
| Lead NAO encontrado | Vai para Passo 0.3 (criar lead) |

#### Passo 0.2 — Lead existente: registrar historico de retorno

```
POST /api/historicos/registrar/
```
```json
{
  "telefone": "{TELEFONE}",
  "nome_contato": "{NOME}",
  "origem_contato": "whatsapp",
  "status": "fluxo_inicializado",
  "observacoes": "Lead retornou ao fluxo comercial",
  "lead_id": {id_lead}
}
```
**Resultado no sistema:**
- HistoricoContato criado
- Se lead ja tem OportunidadeVenda, o CRM ja tem visibilidade

**Proximo:** Verificar se e cliente ativo. Se sim, redirecionar para suporte. Se nao, ir para Fase 1.

#### Passo 0.3 — Lead novo: criar com score que aciona o CRM

```
POST /api/leads/registrar/
```
```json
{
  "nome_razaosocial": "{NOME}",
  "telefone": "{TELEFONE}",
  "origem": "whatsapp",
  "canal_entrada": "whatsapp",
  "tipo_entrada": "contato_whatsapp",
  "status_api": "sucesso",
  "score_qualificacao": 10,
  "id_vendedor_rp": 1618,
  "id_origem": "106",
  "id_origem_servico": "74"
}
```

**MUDANCA CRITICA:** `status_api = "sucesso"` em vez de `"processamento_manual"`.

**O que acontece no backend (automatico via signals):**
1. `LeadProspecto` e salvo
2. Signal `criar_oportunidade_automatica` detecta `status_api == 'sucesso'`
3. `OportunidadeVenda` e criada automaticamente no estagio **"Novo Lead"**
4. CRM ja tem o card no Kanban

**Depois:** registrar historico igual ao Passo 0.2.

---

### FASE 1: Coleta de Endereco

```
[Mensagem] "Oi! Que bom ter voce aqui..."
[Mensagem] "Digite o seu CEP"
[Input] → CEP coletado
              |
              v
```

#### Passo 1.1 — Consulta CEP (via Aurora/N8N)

```
POST {webhook_aurora}
```
```json
{
  "question": "Voce pode me passar o CEP do local?",
  "answer": "{CEP}",
  "cellphone": "{TELEFONE}"
}
```

| Resultado | Acao |
|-----------|------|
| CEP valido + com cobertura | Exibe URA de confirmacao de endereco |
| CEP valido + sem cobertura | Registra historico "sem_cobertura", transfere ou finaliza |
| CEP invalido | Modo manual (rua, bairro, cidade, UF) |

#### Passo 1.2 — Endereco confirmado: salvar no lead

```
POST /api/leads/atualizar/
```
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "cep": "{CEP}",
  "rua": "{RUA}",
  "bairro": "{BAIRRO}",
  "cidade": "{CIDADE}",
  "estado": "{ESTADO}",
  "endereco": "{RUA}, {NUMERO} - {BAIRRO}, {CIDADE} - {ESTADO}, CEP: {CEP}"
}
```

#### Passo 1.3 — Registrar historico de progresso

```
POST /api/historicos/registrar/
```
```json
{
  "telefone": "{TELEFONE}",
  "nome_contato": "{NOME}",
  "origem_contato": "whatsapp",
  "status": "endereco_coletado",
  "observacoes": "Endereco confirmado: {RUA}, {BAIRRO}, {CIDADE}-{ESTADO}",
  "lead_id": {id_lead}
}
```

**O que acontece no backend:**
- Campos `rua`, `bairro`, `cep` preenchidos
- Tag **Endereco** passa a ser aplicavel pelo `taguear_leads`

**NOVA API SUGERIDA — Mover estagio do CRM:**

```
POST /api/crm/mover-por-lead/
```
```json
{
  "lead_id": {id_lead},
  "estagio_slug": "qualificacao",
  "motivo": "Endereco coletado via fluxo WhatsApp"
}
```

**Resultado:** OportunidadeVenda sai de "Novo Lead" e vai para **"Em Qualificacao"**.

---

### FASE 2: Selecao de Plano

```
[URA] "Casa ou empresa?"
[URA] Apresenta plano 620MB / lista de planos
[Lead seleciona]
              |
              v
```

#### Passo 2.1 — Plano selecionado: salvar no lead

```
POST /api/leads/atualizar/
```
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "id_plano_rp": {ID_PLANO},
  "valor": {VALOR_PLANO}
}
```

#### Passo 2.2 — Registrar historico

```
POST /api/historicos/registrar/
```
```json
{
  "telefone": "{TELEFONE}",
  "nome_contato": "{NOME}",
  "origem_contato": "whatsapp",
  "status": "plano_selecionado",
  "observacoes": "Plano: {NOME_PLANO} - R$ {VALOR}",
  "lead_id": {id_lead}
}
```

**O que acontece:**
- Tag **Comercial** aplicavel
- OportunidadeVenda.valor_estimado pode ser atualizado

---

### FASE 3: Dados Pessoais

```
[Coleta sequencial]
  1. Nome completo
  2. CPF (validacao)
  3. E-mail
  4. Data de nascimento
  5. Numero da residencia
  6. Ponto de referencia
              |
              v
```

#### Passo 3.1 — Salvar dados pessoais (uma chamada consolidada)

Apos coletar TODOS os campos acima, uma unica chamada:

```
POST /api/leads/atualizar/
```
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "nome_razaosocial": "{NOME_COMPLETO}",
  "cpf_cnpj": "{CPF}",
  "email": "{EMAIL}",
  "data_nascimento": "{NASCIMENTO}",
  "numero_residencia": "{NUMERO}",
  "ponto_referencia": "{PONTO_REF}"
}
```

#### Passo 3.2 — Registrar historico

```
POST /api/historicos/registrar/
```
```json
{
  "telefone": "{TELEFONE}",
  "nome_contato": "{NOME}",
  "origem_contato": "whatsapp",
  "status": "dados_pessoais_coletados",
  "observacoes": "Nome: {NOME}, CPF: {CPF}, Email: {EMAIL}",
  "lead_id": {id_lead}
}
```

**O que acontece:**
- Tag **Documental** aplicavel (cpf_cnpj preenchido)
- Lead agora tem dados pessoais completos

#### Passo 3.3 — Mover CRM para Negociacao

```
POST /api/crm/mover-por-lead/
```
```json
{
  "lead_id": {id_lead},
  "estagio_slug": "proposta",
  "motivo": "Dados pessoais completos via fluxo WhatsApp"
}
```

**Resultado:** OportunidadeVenda vai para **"Proposta Enviada"**.

---

### FASE 4: Documentos (3 fotos)

```
[Mensagem] "Envie uma selfie com documento..."
[Input] → foto 1
[Mensagem] "Agora a frente do documento..."
[Input] → foto 2
[Mensagem] "Agora o verso..."
[Input] → foto 3
              |
              v
```

#### Passo 4.1 — Registrar cada imagem (3 chamadas)

```
POST /api/leads/imagens/registrar/
```
```json
{ "lead_id": {id_lead}, "link_url": "{URL_IMG}", "descricao": "selfie_com_doc" }
```
```json
{ "lead_id": {id_lead}, "link_url": "{URL_IMG}", "descricao": "frente_doc" }
```
```json
{ "lead_id": {id_lead}, "link_url": "{URL_IMG}", "descricao": "verso_doc" }
```

#### Passo 4.2 — Registrar historico

```
POST /api/historicos/registrar/
```
```json
{
  "telefone": "{TELEFONE}",
  "nome_contato": "{NOME}",
  "origem_contato": "whatsapp",
  "status": "documentos_enviados",
  "observacoes": "3 documentos recebidos: selfie, frente, verso",
  "lead_id": {id_lead}
}
```

---

### FASE 5: Vencimento da Fatura

```
[URA] "Qual o melhor dia de vencimento?"
[Lead seleciona]
              |
              v
```

#### Passo 5.1 — Salvar vencimento

```
POST /api/leads/atualizar/
```
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "id_dia_vencimento": "{ID_VENCIMENTO}"
}
```

---

### FASE 6: Confirmacao e Finalizacao

```
[URA] Exibe resumo completo dos dados
[Lead confirma]
[URA] "Pelo site ou pelo WhatsApp?"
              |
     +--------+--------+
     |                  |
  [SITE]           [WHATSAPP]
     |                  |
     v                  v
```

#### Caminho A — Pelo Site

##### Passo 6A.1 — Registrar escolha e encaminhar

```
POST /api/historicos/registrar/
```
```json
{
  "status": "encaminhado_site",
  "observacoes": "Lead optou por finalizar pelo site. Link enviado.",
  "lead_id": {id_lead}
}
```

Envia mensagem com link. Fluxo bot encerra.
Lead continua com `status_api=sucesso` no estagio "Proposta Enviada" ate concluir no site.

---

#### Caminho B — Pelo WhatsApp (fluxo completo)

##### Passo 6B.1 — Finalizar lead para envio ao Hubsoft

```
POST /api/leads/atualizar/
```
```json
{
  "termo_busca": "id",
  "busca": {id_lead},
  "status_api": "pendente",
  "observacoes": "Finalizado via fluxo WhatsApp"
}
```

**O que acontece no backend (cadeia de signals):**
1. `LeadProspecto.status_api = 'pendente'` → salvo
2. Signal `enviar_lead_pendente_para_hubsoft` dispara:
   - Envia para Hubsoft API como prospecto
   - Atualiza `status_api = 'processado'` e `id_hubsoft = id_prospecto`
   - Sincroniza `ClienteHubsoft` e `ServicoClienteHubsoft`
3. Signal `validar_estagio_aguardando_instalacao` pode disparar:
   - Se Hubsoft criou servico com `aguardando_instalacao` E `documentacao_validada=True`:
     - OportunidadeVenda vai para **"Aguardando Instalacao"**

##### Passo 6B.2 — Loop de verificacao do status Hubsoft

```
# Repete a cada 20 segundos, max N tentativas
GET /integracoes/api/lead/hubsoft-status/?lead_id={id_lead}
```

| Status retornado | Acao |
|------------------|------|
| `aguardando_instalacao` | Prossegue para agendamento (Fase 7) |
| `servico_habilitado` | Lead ja virou cliente — pula para encerramento |
| Sem status / erro | Aguarda 20s e tenta novamente |
| Max tentativas excedidas | Registra historico e transfere para humano |

##### Passo 6B.3 — Registrar historico

```
POST /api/historicos/registrar/
```
```json
{
  "status": "enviado_hubsoft",
  "observacoes": "Lead enviado ao Hubsoft. Status: {STATUS_RETORNADO}",
  "lead_id": {id_lead}
}
```

---

### FASE 7: Agendamento de Instalacao (so via WhatsApp)

```
[API] Consulta datas disponiveis
[URA] "Manha ou tarde?"
[URA] "Escolha a data"
[API] Consulta agenda
[API] Abre atendimento
[API] Abre OS
              |
              v
```

#### Passo 7.1 — Consultar datas

```
GET {url_api_matrix}/consultar_datas_sem_domingo?data_referencia={DATA_HOJE}
```

#### Passo 7.2 — Lead escolhe turno e data

Armazena: `turno_instalacao`, `cliente_data_insta`

#### Passo 7.3 — Consultar agenda

```
GET {url_api_matrix}/consultar_agenda?cidade={CIDADE}&data_referencia={DATA}&turno={TURNO}&qtd_vagas=1
```

#### Passo 7.4 — Abrir atendimento no Matrix

```
POST {url_api_matrix}/abrir_atendimento
```
```json
{
  "id_cliente_servico": {ID_CLIENTE_SERVICO},
  "nome": "ClienteVenda",
  "telefone": "{TELEFONE}",
  "descricao": "*Instalacao* Cliente: {NOME} CPF: {CPF} ...",
  "id_tipo_atendimento": {ID_TIPO},
  "id_atendimento_status": {ID_STATUS},
  "id_usuario_responsavel": {ID_RESPONSAVEL},
  "empresa": "{EMPRESA}"
}
```

#### Passo 7.5 — Abrir OS no Matrix

```
POST {url_api_matrix}/abrir_os
```
```json
{
  "id_atendimento": {ID_ATENDIMENTO},
  "id_tipo_ordem_servico": {ID_TIPO_OS},
  "id_agenda_ordem_servico": {ID_AGENDA},
  "data_inicio_programado": "{DATA}",
  "hora_inicio_programado": "{HORA}",
  "duracao": "{DURACAO}",
  "status": "{STATUS_OS}"
}
```

#### Passo 7.6 — Registrar historico de agendamento

```
POST /api/historicos/registrar/
```
```json
{
  "status": "instalacao_agendada",
  "observacoes": "Instalacao agendada para {DATA} turno {TURNO}. OS aberta.",
  "lead_id": {id_lead}
}
```

#### Passo 7.7 — Mensagens finais e encerramento

```
[Mensagem] "Sua instalacao foi agendada com sucesso para {DATA} no turno {TURNO}."
[Mensagem] "Finalizamos sua contratacao com sucesso. Seja bem-vindo(a) a Megalink!"
```

#### Passo 7.8 — Registrar historico de encerramento

```
POST /api/historicos/registrar/
```
```json
{
  "status": "fluxo_finalizado",
  "sucesso": "True",
  "observacoes": "Fluxo comercial concluido com sucesso. OS aberta.",
  "lead_id": {id_lead}
}
```

**Fluxo encerra no bot.**

---

## Saidas Alternativas (em qualquer fase)

### Transferencia para Atendente Humano

Pode ocorrer em qualquer ponto. Sempre executar:

#### Passo T.1 — Registrar historico de transferencia

```
POST /api/historicos/registrar/
```
```json
{
  "status": "transferido_humano",
  "observacoes": "Motivo: {MOTIVO}. Ultima etapa: {FASE_ATUAL}. Pergunta: {PERGUNTA}. Resposta: {RESPOSTA}",
  "lead_id": {id_lead}
}
```

**Resultado:** O HistoricoContato registra o ponto exato de transferencia.

### Encerramento por Inatividade

```
POST /api/historicos/registrar/
```
```json
{
  "status": "fluxo_abandonado",
  "observacoes": "Inatividade na fase: {FASE_ATUAL}. Ultimo dado coletado: {ULTIMO_CAMPO}",
  "lead_id": {id_lead}
}
```

### Encerramento por Tentativas Invalidas

```
POST /api/historicos/registrar/
```
```json
{
  "status": "fluxo_abandonado",
  "observacoes": "Excedeu tentativas invalidas na fase: {FASE_ATUAL}",
  "lead_id": {id_lead}
}
```

---

## Mapa de Status do Historico

Todos os valores de `status` usados nas chamadas a `/api/historicos/registrar/`:

| Status | Quando | Fase |
|--------|--------|------|
| `fluxo_inicializado` | Lead inicia conversa | 0 |
| `endereco_coletado` | Endereco confirmado (CEP ou manual) | 1 |
| `sem_cobertura` | CEP sem viabilidade | 1 |
| `plano_selecionado` | Lead escolheu plano | 2 |
| `dados_pessoais_coletados` | Nome, CPF, email, nascimento preenchidos | 3 |
| `documentos_enviados` | 3 fotos recebidas | 4 |
| `encaminhado_site` | Lead preferiu finalizar pelo site | 6A |
| `enviado_hubsoft` | Lead enviado ao Hubsoft (status_api=pendente) | 6B |
| `instalacao_agendada` | OS aberta, data confirmada | 7 |
| `fluxo_finalizado` | Concluido com sucesso | 7 |
| `transferido_humano` | Transferido para atendente | qualquer |
| `fluxo_abandonado` | Inatividade ou tentativas invalidas | qualquer |

---

## Mapa de Estagio CRM por Fase

| Fase Concluida | Estagio CRM | Tipo | Como Chega |
|----------------|-------------|------|------------|
| 0. Lead criado/encontrado | **Novo Lead** | novo | Signal automatico (status_api=sucesso) |
| 1. Endereco coletado | **Em Qualificacao** | qualificacao | API /crm/mover-por-lead/ |
| 3. Dados pessoais completos | **Proposta Enviada** | negociacao | API /crm/mover-por-lead/ |
| 6B. Enviado ao Hubsoft | **Aguardando Instalacao** | fechamento | Signal automatico (servico + doc validada) |
| 7. Instalacao concluida | **Cliente Ativo** | cliente | Signal automatico (servico habilitado) |
| Abandono > 48h em qualificacao | **Perdido** | perdido | Command mover_perdidos |

---

## Mapa de Tags por Fase

| Fase | Tag Aplicavel | Criterio |
|------|--------------|----------|
| 2. Plano selecionado | **Comercial** | id_plano_rp preenchido |
| 1. Endereco coletado | **Endereco** | rua + numero + bairro + cep preenchidos |
| 3. CPF informado | **Documental** | cpf_cnpj preenchido |

---

## APIs Novas Necessarias

### 1. Mover estagio por lead_id

O fluxo atual so permite mover por `oportunidade_id`. Para o bot, que conhece apenas o `lead_id`, precisamos de:

```
POST /api/crm/mover-por-lead/
```
```json
{
  "lead_id": 123,
  "estagio_slug": "qualificacao",
  "motivo": "Endereco coletado via fluxo WhatsApp"
}
```

**Logica interna:**
1. Buscar `OportunidadeVenda` onde `lead_id = lead_id` e `ativo = True`
2. Buscar `PipelineEstagio` onde `slug = estagio_slug` e `ativo = True`
3. Aplicar mesma logica de `api_mover_oportunidade` (historico, validacoes, webhook)

### 2. Atualizar tags por lead_id

Para aplicar tags em tempo real conforme dados sao preenchidos:

```
POST /api/crm/taguear-lead/
```
```json
{
  "lead_id": 123
}
```

**Logica interna:** executa a mesma logica do `taguear_leads` mas para um unico lead.

---

## Diagrama Completo

```
WHATSAPP                          DJANGO                           CRM                    HUBSOFT
   |                                |                               |                        |
   | ── GET /consultar/leads ─────> |                               |                        |
   | <── id_lead ou "nao existe" ── |                               |                        |
   |                                |                               |                        |
   | ── POST /leads/registrar ────> |                               |                        |
   |    status_api=sucesso          | ── signal ──────────────────> |                        |
   |                                |    criar_oportunidade_auto    | [Novo Lead]            |
   |                                |                               |                        |
   | ── POST /historicos/ ────────> |                               |                        |
   |    status=fluxo_inicializado   |                               |                        |
   |                                |                               |                        |
   |   [COLETA CEP + ENDERECO]      |                               |                        |
   |                                |                               |                        |
   | ── POST /leads/atualizar ───> |                               |                        |
   |    cep, rua, bairro, cidade    |                               |                        |
   | ── POST /historicos/ ────────> |                               |                        |
   |    status=endereco_coletado    |                               |                        |
   | ── POST /crm/mover-por-lead > |  ─────────────────────────>   | [Em Qualificacao]      |
   |                                |                               |                        |
   |   [SELECAO DE PLANO]           |                               |                        |
   |                                |                               |                        |
   | ── POST /leads/atualizar ───> |                               |                        |
   |    id_plano_rp, valor          |                               |                        |
   | ── POST /historicos/ ────────> |                               |                        |
   |    status=plano_selecionado    |                               |                        |
   |                                |                               |                        |
   |   [DADOS PESSOAIS]             |                               |                        |
   |                                |                               |                        |
   | ── POST /leads/atualizar ───> |                               |                        |
   |    nome, cpf, email, nasc      |                               |                        |
   | ── POST /historicos/ ────────> |                               |                        |
   |    status=dados_pessoais       |                               |                        |
   | ── POST /crm/mover-por-lead > |  ─────────────────────────>   | [Proposta Enviada]     |
   |                                |                               |                        |
   |   [DOCUMENTOS: 3 FOTOS]        |                               |                        |
   |                                |                               |                        |
   | ── POST /leads/imagens x3 ──> |                               |                        |
   | ── POST /historicos/ ────────> |                               |                        |
   |    status=documentos_enviados  |                               |                        |
   |                                |                               |                        |
   |   [VENCIMENTO]                  |                               |                        |
   |                                |                               |                        |
   | ── POST /leads/atualizar ───> |                               |                        |
   |    id_dia_vencimento           |                               |                        |
   |                                |                               |                        |
   |   [CONFIRMACAO + WHATSAPP]      |                               |                        |
   |                                |                               |                        |
   | ── POST /leads/atualizar ───> |                               |                        |
   |    status_api=pendente         | ── signal ──────────────────────────────────────────> |
   |                                |    enviar_lead_para_hubsoft                    CADASTRA |
   |                                | <── signal ─────────────────────────────────── RETORNA |
   |                                |    sincroniza ClienteHubsoft                          |
   |                                |    cria ServicoClienteHubsoft                         |
   |                                | ── signal ──────────────────> |                        |
   |                                |    validar_estagio            | [Aguardando            |
   |                                |    (servico+doc_validada)     |  Instalacao]           |
   |                                |                               |                        |
   |   [LOOP VERIFICACAO STATUS]     |                               |                        |
   |                                |                               |                        |
   | ── GET /hubsoft-status ──────> |                               |                        |
   | <── status_prefixo ──────────  |                               |                        |
   |                                |                               |                        |
   |   [AGENDAMENTO INSTALACAO]      |                               |                        |
   |                                |                               |                        |
   | ── GET consultar_datas ──────> |  (Matrix API)                 |                        |
   | ── GET consultar_agenda ─────> |  (Matrix API)                 |                        |
   | ── POST abrir_atendimento ──> |  (Matrix API)                 |                        |
   | ── POST abrir_os ────────────> |  (Matrix API)                 |                        |
   |                                |                               |                        |
   | ── POST /historicos/ ────────> |                               |                        |
   |    status=instalacao_agendada  |                               |                        |
   |                                |                               |                        |
   |   [ENCERRAMENTO]               |                               |                        |
   |                                |                               |                        |
   | ── POST /historicos/ ────────> |                               |                        |
   |    status=fluxo_finalizado     |                               |                        |
   |                                |                               |                        |
   |   ...instalacao concluida...   |                               |                        |
   |                                | <── hubsoft webhook ──────────────────── HABILITADO    |
   |                                | ── signal ──────────────────> | [Cliente Ativo]        |
   |                                |    servico_habilitado         |  is_final_ganho=True   |
   |                                |                               |  MetaVendas atualizada |
```

---

## Checklist de Implementacao

### Backend (Django)

- [ ] Criar endpoint `POST /api/crm/mover-por-lead/` que aceite `lead_id` e `estagio_slug`
- [ ] Criar endpoint `POST /api/crm/taguear-lead/` que aplique tags para um lead
- [ ] Garantir que `/api/leads/registrar/` aceite `score_qualificacao` no body
- [ ] Ajustar signal `criar_oportunidade_automatica` para aceitar `status_api='sucesso'` vindo do bot
- [ ] Garantir que `/api/historicos/registrar/` aceite todos os novos valores de `status`

### Fluxo WhatsApp (Matrix/N8N)

- [ ] Alterar criacao de lead: `status_api=sucesso` + `score_qualificacao=10`
- [ ] Adicionar chamada a `/crm/mover-por-lead/` apos endereco coletado (Fase 1)
- [ ] Adicionar chamada a `/crm/mover-por-lead/` apos dados pessoais (Fase 3)
- [ ] Adicionar registro de historico a cada fase (12 pontos de registro)
- [ ] Consolidar atualizacao de dados pessoais em uma unica chamada (Fase 3)
- [ ] Registrar historico com fase e motivo em todas as saidas (transferencia, abandono, inatividade)

### Cron Jobs

- [ ] `mover_perdidos` — execucao a cada hora (leads em qualificacao > 48h)
- [ ] `validar_aguardando_instalacao` — execucao a cada 30 min
- [ ] `taguear_leads` — execucao a cada hora (backup, pois o ideal e tag em tempo real)
