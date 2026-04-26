# Mapa de Integrações — AuroraISP

**Última atualização:** 05/04/2026
**Responsável:** Tech Lead / CTO

---

## Visão Geral

O Aurora precisa de duas integrações externas para funcionar: uma com o **ERP do provedor** (gestão de clientes, planos, contratos) e outra com a **plataforma de atendimento** (WhatsApp, chat). Hoje o sistema roda com HubSoft + Matrix, mas a arquitetura deve suportar outros ERPs e plataformas.

Este documento mapeia **o que** precisa ser integrado, independente da ferramenta.

---

## 1. Integração com ERP

O ERP é a fonte da verdade sobre clientes, planos, contratos e financeiro do provedor.

### 1.1 O que o Aurora consome do ERP

| # | Dado | Onde é usado | Criticidade | Frequência |
|---|------|-------------|-------------|------------|
| 1 | **Consultar cliente por CPF** | Verificação de membro no Clube (CS), cadastro de lead | Alta | A cada cadastro/verificação |
| 2 | **Dados do cliente** (nome, e-mail, telefone, endereço) | Preencher MembroClube, vincular lead | Alta | A cada consulta |
| 3 | **ID do cliente no ERP** | FK para rastreabilidade (id_cliente_hubsoft, id_prospecto_hubsoft) | Alta | Uma vez por cliente |
| 4 | **Planos disponíveis** (nome, velocidade, preço) | Página de cadastro público, seleção de plano | Média | Seed inicial ou sync periódico |
| 5 | **Status do contrato** (ativo, suspenso, cancelado, dias restantes) | Alertas de retenção, score de churn | Média | Scanner periódico (cron) |
| 6 | **Situação financeira** (inadimplência, pagamento adiantado, recorrência) | Pontuação extra no Clube, alertas de churn | Baixa | A cada validação OTP |
| 7 | **Uso do app do provedor** | Pontuação extra no Clube | Baixa | A cada validação OTP |
| 8 | **Clientes por cidade** | Relatórios, distribuição de prêmios por região | Baixa | Cache 1h |

### 1.2 O que o Aurora envia para o ERP

| # | Dado | Quando | Criticidade |
|---|------|--------|-------------|
| 1 | **Novo prospecto/lead** | Lead qualificado pelo bot ou cadastro público | Alta |
| 2 | **Documentos do lead** (selfie, RG frente/verso) | Upload durante cadastro | Alta |
| 3 | **Contrato aceito** (IP, timestamp, dados) | Aceite no cadastro público | Alta |
| 4 | **Status do processamento** (aprovado/rejeitado) | Webhook de confirmação | Média |

### 1.3 Como cada integração funciona hoje (HubSoft)

#### Via API REST OAuth2 (`apps/integracoes/services/hubsoft.py`)

| # | Operação | Endpoint HubSoft | Método | Arquivo |
|---|----------|------------------|--------|---------|
| 1 | **Obter token OAuth** | `/oauth/token` | POST | `hubsoft.py:42` |
| 2 | **Cadastrar prospecto** (lead → ERP) | `/api/v1/integracao/prospecto` | POST | `hubsoft.py:115` |
| 3 | **Consultar cliente** por CPF/CNPJ | `/api/v1/integracao/cliente` | GET | `hubsoft.py:184` |
| 4 | **Sincronizar cliente** (cria/atualiza ClienteHubsoft local) | `/api/v1/integracao/cliente` | GET | `hubsoft.py:251` |
| 5 | **Sincronizar serviços** (planos ativos do cliente) | Dentro da resposta do cliente | — | `hubsoft.py:378` |

Credenciais armazenadas em `IntegracaoAPI` (campos sensíveis criptografados). Token OAuth cacheado com expiração. Todas as chamadas logadas em `LogIntegracao` com tempo de resposta.

#### Via Webhook N8N (`apps/cs/clube/services/hubsoft_service.py`)

| # | Operação | Webhook N8N | Método | Arquivo |
|---|----------|-------------|--------|---------|
| 6 | **Consultar cliente** (Clube CS) | `/webhook/roletaconsultarcliente` | POST | `hubsoft_service.py:28` |

O N8N recebe o CPF e faz a consulta no HubSoft, retornando os dados. Usado na verificação de membro do Clube.

#### Via conexão direta ao banco PostgreSQL (`apps/cs/clube/services/hubsoft_service.py`)

| # | Operação | Query SQL | Arquivo |
|---|----------|-----------|---------|
| 7 | **Checar pontos extras** (recorrência, adiantamento, app) | SELECT em cliente, cobranca, cliente_cartao, cliente_acesso_central | `hubsoft_service.py:60` |
| 8 | **Consultar cidade** do cliente (endereço de instalação) | SELECT em cliente_servico_endereco + cidade | `hubsoft_service.py:139` |
| 9 | **Clientes por cidade** (relatórios) | SELECT COUNT GROUP BY cidade | `hubsoft_service.py:189` |

Conexão psycopg2 direta, read-only (`mega_leitura`). Env vars: `HUBSOFT_DB_USER`, `HUBSPOT_DB_PASSWORD`, `HUBSOFT_DB_HOST`, `HUBSOFT_DB_PORT`, `HUBSOFT_DB_NAME`.

#### Via serviço de contrato (`apps/comercial/cadastro/services/contrato_service.py`)

| # | Operação | Endpoint HubSoft | Método | Arquivo |
|---|----------|------------------|--------|---------|
| 10 | **Buscar contrato** do cliente | API HubSoft | GET | `contrato_service.py:40` |
| 11 | **Criar contrato** | API HubSoft | POST | `contrato_service.py:164` |
| 12 | **Atualizar contrato** | API HubSoft | PUT | `contrato_service.py:256` |
| 13 | **Download contrato PDF** | API HubSoft | GET | `contrato_service.py:314` |

**Resumo: 13 pontos de integração com o ERP.**

| Método | Quantidade | Pontos |
|--------|-----------|--------|
| API REST OAuth2 | 8 | #1-5, #10-13 |
| Webhook N8N | 1 | #6 |
| Banco direto (psycopg2) | 3 | #7, #8, #9 |
| **Total** | **13** | |

**Recomendação:** migrar os 3 acessos diretos ao banco (#7, #8, #9) para API REST. A conexão direta depende de IP, schema e credenciais de banco, e não funciona com outros ERPs.

### 1.4 Dados mínimos que o ERP precisa expor

Para integrar qualquer ERP, precisamos de no mínimo:

```
GET  /clientes?cpf={cpf}          → {id, nome, email, telefone, endereco, cidade, status}
GET  /clientes/{id}/contratos     → [{id, plano, status, data_inicio, data_fim, valor}]
GET  /clientes/{id}/financeiro    → {inadimplente, recorrencia, adiantado}
GET  /planos                      → [{id, nome, velocidade_down, velocidade_up, valor}]
POST /prospectos                  → Criar prospecto com dados do lead
POST /prospectos/{id}/documentos  → Enviar documentos
```

### 1.5 Credenciais necessárias

| Item | Descrição |
|------|-----------|
| URL base da API | Ex: https://api.erp.com.br/v1 |
| Método de autenticação | OAuth2 (client_credentials ou password), API Key, ou Bearer Token |
| Client ID / Secret | Se OAuth |
| Username / Password | Se auth por usuário |
| IDs de mapeamento | id_origem (de onde vem o lead), id_vendedor_padrao, id_servico |

---

## 2. Integração com Plataforma de Atendimento

A plataforma de atendimento é o canal de comunicação com o cliente (WhatsApp, chat web, SMS).

### 2.1 O que o Aurora consome da plataforma

| # | Dado | Onde é usado | Criticidade |
|---|------|-------------|-------------|
| 1 | **Mensagens recebidas** (texto, remetente, timestamp) | Inbox, detecção de campanha, bot de atendimento | Alta |
| 2 | **Status de entrega/leitura** | Indicadores no chat (✓, ✓✓, azul) | Baixa |
| 3 | **Histórico de conversa** | Ficha do lead, CRM, PDF da conversa | Média |

### 2.2 O que o Aurora envia para a plataforma

| # | Dado | Quando | Criticidade |
|---|------|--------|-------------|
| 1 | **Mensagens do agente** | Resposta no Inbox | Alta |
| 2 | **Mensagens automáticas** (automações: boas-vindas, follow-up) | Engine de automações dispara | Alta |
| 3 | **OTP de verificação** | Cadastro no Clube (CS) | Alta |
| 4 | **Notificações** (tarefa vencida, nova oportunidade) | Automações + webhooks CRM | Média |

### 2.3 Como cada integração funciona hoje

#### Plataforma de atendimento (Matrix)

| # | Operação | Direção | Método | Arquivo |
|---|----------|---------|--------|---------|
| 1 | **Buscar histórico de conversa** por código | Aurora → Matrix | GET `/rest/v1/atendimento` | `atendimento_service.py:48` |
| 2 | **Enviar mensagem do agente** (Inbox) | Aurora → Plataforma | POST webhook configurado por canal | `inbox/services.py:303` |
| 3 | **Receber mensagem do cliente** | Plataforma → Aurora | POST `/inbox/api/n8n/mensagem-recebida/` | `inbox/views_n8n.py` |
| 4 | **Status de entrega/leitura** | Plataforma → Aurora | POST `/inbox/api/n8n/status-mensagem/` | `inbox/views_n8n.py` |

Credenciais: `MATRIX_API_URL`, `MATRIX_API_TOKEN` (env vars).

#### N8N (orquestrador de webhooks)

| # | Operação | Direção | Webhook | Arquivo |
|---|----------|---------|---------|---------|
| 5 | **Enviar OTP via WhatsApp** | Aurora → N8N → WhatsApp | `/webhook/roletacodconfirmacao` | `otp_service.py:25` |
| 6 | **Enviar WhatsApp (automações)** | Aurora → N8N → WhatsApp | Webhook hardcoded no engine | `engine.py:442` |
| 7 | **Enviar e-mail (automações)** | Aurora → N8N | Webhook hardcoded no engine | `engine.py:475` |
| 8 | **Validação IA de questão (bot)** | Aurora → N8N | URL configurada por questão | `atendimento/models.py:739` |
| 9 | **Pós-resposta de questão (bot)** | Aurora → N8N | URL configurada por questão | `atendimento/models.py:931` |
| 10 | **Notificação CRM: nova oportunidade** | Aurora → N8N | URL em ConfiguracaoCRM | `crm/views.py:33` |
| 11 | **Notificação CRM: mudança estágio** | Aurora → N8N | URL em ConfiguracaoCRM | `crm/views.py:33` |
| 12 | **Notificação CRM: tarefa vencida** | Aurora → N8N | URL em ConfiguracaoCRM | `crm/views.py:33` |
| 13 | **Push notification** | Aurora → N8N | URL em settings | `notificacoes/views.py:1172` |

#### APIs do Aurora que sistemas externos consomem

| # | Endpoint | Método | Auth | Quem chama |
|---|----------|--------|------|------------|
| 14 | `/api/v1/leads/registrar/` | POST | Token | N8N (bot) |
| 15 | `/api/v1/leads/atualizar/` | PUT | Token | N8N (bot) |
| 16 | `/api/v1/leads/imagens/registrar/` | POST | Token | N8N (docs) |
| 17 | `/api/v1/atendimento/n8n/*` (14 endpoints) | GET/POST | Token | N8N (bot) |
| 18 | `/marketing/api/campanhas/detectar/` | POST | Token | N8N (campanha) |
| 19 | `/inbox/api/n8n/mensagem-recebida/` | POST | Token | Plataforma/N8N |
| 20 | `/api/v1/venda/aprovar/` | POST | Token | N8N/ERP |
| 21 | `/api/v1/venda/rejeitar/` | POST | Token | N8N/ERP |

#### Consulta de CEP (multi-source)

| # | Operação | Fonte | Arquivo |
|---|----------|-------|---------|
| 22 | **Buscar endereço por CEP** | ViaCEP → CepAPI → BrasilAPI → Postmon → OpenCEP | `cadastro/views.py:604` |

**Resumo: 22 pontos de integração com atendimento/N8N/externos.**

| Método | Quantidade |
|--------|-----------|
| Aurora → Plataforma (webhook envio) | 2 |
| Plataforma → Aurora (webhook recebimento) | 2 |
| Aurora → N8N (webhook) | 9 |
| N8N/externo → Aurora (API REST) | 8 |
| Aurora → APIs de CEP | 1 |
| **Total** | **22** |

### 2.4 Endpoints mínimos que a plataforma precisa expor

```
POST /enviar-mensagem  → {telefone, mensagem, tipo}  (texto, imagem, documento)
POST /enviar-otp       → {telefone, codigo}
GET  /conversa/{id}    → Histórico de mensagens
```

E a plataforma precisa enviar para o Aurora via webhook:

```
POST /inbox/api/n8n/mensagem-recebida/  → {telefone, mensagem, canal, timestamp}
POST /inbox/api/n8n/status-mensagem/    → {mensagem_id, status} (entregue/lido)
```

### 2.5 Credenciais necessárias

| Item | Descrição |
|------|-----------|
| URL do webhook de envio | Para onde o Aurora manda mensagens |
| Token de autenticação | API Key ou Bearer Token da plataforma |
| URL do webhook de recebimento | URL do Aurora que a plataforma vai chamar |
| Token do Aurora | Token DRF gerado para a plataforma autenticar no Aurora |

---

## 3. Integração com N8N (Orquestrador)

O N8N funciona como middleware entre o Aurora e os sistemas externos. Não é obrigatório (as integrações podem ser diretas), mas simplifica o setup.

### 3.1 Fluxos N8N necessários

| # | Fluxo | Trigger | O que faz |
|---|-------|---------|-----------|
| 1 | **Bot de atendimento** | Mensagem recebida no WhatsApp | Consulta fluxo de questões na API do Aurora, envia resposta ao cliente, avança etapas |
| 2 | **Detecção de campanha** | Mensagem recebida no WhatsApp | Envia mensagem para API `/marketing/api/campanhas/detectar/`, atribui lead à campanha |
| 3 | **Envio de OTP** | Webhook do Aurora | Recebe CPF + telefone + código, envia via WhatsApp |
| 4 | **Consulta cliente ERP** | Webhook do Aurora | Recebe CPF, consulta no ERP, retorna dados do cliente |
| 5 | **Envio de WhatsApp (automações)** | Webhook do Aurora | Recebe telefone + mensagem, envia via plataforma de atendimento |
| 6 | **Notificações CRM** | Webhook do Aurora | Nova oportunidade, mudança de estágio, tarefa vencida |

### 3.2 Webhooks configurados no Aurora

| Webhook | Onde configurar | Quem chama |
|---------|----------------|------------|
| `webhook_n8n_nova_oportunidade` | ConfiguracaoCRM | Signal do CRM (auto) |
| `webhook_n8n_mudanca_estagio` | ConfiguracaoCRM | Signal do CRM (auto) |
| `webhook_n8n_tarefa_vencida` | ConfiguracaoCRM | Cron (auto) |
| Webhook de envio por canal | Configurações do Inbox > Canais | Agente responde no Inbox |

### 3.3 APIs do Aurora que o N8N consome

| API | Método | Auth | Descrição |
|-----|--------|------|-----------|
| `/api/v1/leads/registrar/` | POST | Token | Criar lead |
| `/api/v1/leads/atualizar/` | PUT | Token | Atualizar lead |
| `/api/v1/leads/imagens/registrar/` | POST | Token | Enviar documentos |
| `/api/v1/atendimento/n8n/*` | GET/POST | Token | 14 endpoints do bot |
| `/marketing/api/campanhas/detectar/` | POST | Token | Detectar campanha |
| `/inbox/api/n8n/mensagem-recebida/` | POST | Token | Receber mensagem |

---

## 4. Checklist de Integração por Cliente

### ERP (obrigatório)

```
[ ] Identificar qual ERP o provedor usa
[ ] Obter credenciais de API (URL, auth method, tokens)
[ ] Mapear IDs: id_origem, id_vendedor, id_servico
[ ] Testar consulta de cliente por CPF
[ ] Testar criação de prospecto
[ ] Configurar IntegracaoAPI no Aurora
[ ] Validar conexão no Admin Aurora > Monitoramento
```

### Plataforma de Atendimento (obrigatório para Inbox/Bot)

```
[ ] Identificar qual plataforma o provedor usa (WhatsApp Business API, etc.)
[ ] Obter webhook de envio (URL para onde Aurora manda mensagens)
[ ] Configurar webhook de recebimento (URL do Aurora na plataforma)
[ ] Gerar token DRF para a plataforma autenticar
[ ] Configurar canal no Inbox > Configurações > Canais
[ ] Testar envio e recebimento de mensagem
```

### N8N (recomendado)

```
[ ] Instância N8N disponível (self-hosted ou cloud)
[ ] Duplicar/criar fluxos necessários (bot, campanha, OTP, notificações)
[ ] Configurar credenciais do ERP no N8N
[ ] Configurar credenciais da plataforma de atendimento no N8N
[ ] Configurar token do Aurora no N8N
[ ] Testar fluxo completo: mensagem → bot → lead → CRM
```

---

## 5. ERPs conhecidos no mercado ISP

| ERP | API REST | Observações |
|-----|----------|-------------|
| **HubSoft** | Sim (OAuth2) | Integração nativa e profunda. Caso de produção. |
| **MK Solutions** | Sim | Popular em provedores médios. API documentada. |
| **IXCSoft** | Sim | Grande base instalada. API REST disponível. |
| **SGP (inSystem)** | Sim (`app+token`) | **Integrado em prod desde 04/26 (Gigamax como piloto).** 7/7 endpoints minimos cobertos + bonus (verificar acesso, 2via fatura). Detalhes em [05-SGP.md](05-SGP.md). |
| **Controllr** | Sim | API REST. Crescendo no mercado. |
| **Topapp** | Sim | Focado em provedores menores. |

### Plataformas de atendimento

| Plataforma | Tipo | Observações |
|------------|------|-------------|
| **Matrix do Brasil** | WhatsApp Business API | Integração atual da Megalink. |
| **Evolution API** | WhatsApp (não oficial) | Open source, self-hosted. Popular. |
| **Z-API** | WhatsApp Business API | API simples, boa documentação. |
| **Twilio** | WhatsApp + SMS + Voz | Enterprise, mais caro. |
| **Baileys/WPPConnect** | WhatsApp (não oficial) | Open source, instável. |
| **Chatwoot** | Omnichannel | Open source, multi-canal. |

---

## 6. Mapa Consolidado — Todos os 35 Pontos de Integração

| # | Operação | Sistema | Método | Direção |
|---|----------|---------|--------|---------|
| **ERP** | | | | |
| 1 | Obter token OAuth | HubSoft API | REST POST | Aurora → ERP |
| 2 | Cadastrar prospecto | HubSoft API | REST POST | Aurora → ERP |
| 3 | Consultar cliente por CPF | HubSoft API | REST GET | Aurora → ERP |
| 4 | Sincronizar cliente (local) | HubSoft API | REST GET | Aurora → ERP |
| 5 | Sincronizar serviços | HubSoft API | Dentro de #4 | Aurora → ERP |
| 6 | Consultar cliente (Clube) | N8N webhook | POST | Aurora → N8N → ERP |
| 7 | Checar pontos extras | HubSoft DB | SQL direto | Aurora → DB ERP |
| 8 | Consultar cidade | HubSoft DB | SQL direto | Aurora → DB ERP |
| 9 | Clientes por cidade | HubSoft DB | SQL direto | Aurora → DB ERP |
| 10 | Buscar contrato | HubSoft API | REST GET | Aurora → ERP |
| 11 | Criar contrato | HubSoft API | REST POST | Aurora → ERP |
| 12 | Atualizar contrato | HubSoft API | REST PUT | Aurora → ERP |
| 13 | Download contrato PDF | HubSoft API | REST GET | Aurora → ERP |
| **Atendimento** | | | | |
| 14 | Buscar histórico conversa | Matrix API | REST GET | Aurora → Plataforma |
| 15 | Enviar mensagem (Inbox) | Webhook canal | POST | Aurora → Plataforma |
| 16 | Receber mensagem cliente | API Aurora | POST | Plataforma → Aurora |
| 17 | Status entrega/leitura | API Aurora | POST | Plataforma → Aurora |
| **N8N / Webhooks** | | | | |
| 18 | Enviar OTP WhatsApp | N8N webhook | POST | Aurora → N8N |
| 19 | Enviar WhatsApp (automação) | N8N webhook | POST | Aurora → N8N |
| 20 | Enviar e-mail (automação) | N8N webhook | POST | Aurora → N8N |
| 21 | Validação IA questão (bot) | N8N webhook | POST | Aurora → N8N |
| 22 | Pós-resposta questão (bot) | N8N webhook | POST | Aurora → N8N |
| 23 | Notificação: nova oportunidade | N8N webhook | POST | Aurora → N8N |
| 24 | Notificação: mudança estágio | N8N webhook | POST | Aurora → N8N |
| 25 | Notificação: tarefa vencida | N8N webhook | POST | Aurora → N8N |
| 26 | Push notification | N8N webhook | POST | Aurora → N8N |
| **APIs consumidas por externos** | | | | |
| 27 | Registrar lead | API Aurora | POST | N8N → Aurora |
| 28 | Atualizar lead | API Aurora | PUT | N8N → Aurora |
| 29 | Enviar documentos | API Aurora | POST | N8N → Aurora |
| 30 | Bot atendimento (14 endpoints) | API Aurora | GET/POST | N8N → Aurora |
| 31 | Detectar campanha | API Aurora | POST | N8N → Aurora |
| 32 | Aprovar venda | API Aurora | POST | ERP/N8N → Aurora |
| 33 | Rejeitar venda | API Aurora | POST | ERP/N8N → Aurora |
| **Outros** | | | | |
| 34 | Consultar CEP | ViaCEP + fallbacks | REST GET | Aurora → APIs públicas |
| 35 | IA (OpenAI/Gemini) | APIs IA | REST POST | Aurora → OpenAI/Google |

---

## 7. Resumo: O que perguntar ao provedor

Ao iniciar a implementação de um novo cliente:

1. **Qual ERP vocês usam?** (HubSoft, MK, IXC, SGP, Controllr, outro)
2. **Vocês têm acesso à API do ERP?** (credenciais, documentação)
3. **Qual plataforma de WhatsApp usam?** (Matrix, Evolution, Z-API, outro)
4. **Já têm N8N ou ferramenta de automação?** (self-hosted, cloud)
5. **Quais IDs preciso mapear?** (vendedor padrão, origem do lead, serviço)
6. **Quem é o contato técnico para integrações?** (para resolver credenciais e testes)
