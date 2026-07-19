# 🔔 Documentação Completa - Sistema de Notificações Megalink

**Versão**: 2.0.0  
**Última Atualização**: 23 de outubro de 2025  
**Autor**: Equipe Megalink

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Estrutura de Banco de Dados](#estrutura-de-banco-de-dados)
4. [APIs REST](#apis-rest)
5. [Serviço de Notificações](#serviço-de-notificações)
6. [Tipos de Notificação](#tipos-de-notificação)
7. [Canais de Comunicação](#canais-de-comunicação)
8. [Interface Web](#interface-web)
9. [Integração N8N](#integração-n8n)
10. [Exemplos de Uso](#exemplos-de-uso)
11. [Configuração e Deploy](#configuração-e-deploy)
12. [Monitoramento e Estatísticas](#monitoramento-e-estatísticas)
13. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

O Sistema de Notificações do Megalink é uma solução empresarial completa para gerenciamento e envio de notificações multi-canal, desenvolvido em Django e integrado com N8N para automação avançada.

### ✨ Principais Características

- **Multi-Canal**: WhatsApp, Email, SMS, Push Notifications, Webhooks
- **Personalização Completa**: Templates dinâmicos com variáveis
- **Preferências por Usuário**: Controle total de quando e como receber notificações
- **Agendamento Inteligente**: Envio agendado respeitando horários configurados
- **Retry Automático**: Sistema de retry com backoff exponencial
- **Estatísticas em Tempo Real**: Dashboard completo com métricas e gráficos
- **Integração N8N**: Workflows customizados e automações avançadas
- **API REST Completa**: Endpoints RESTful para todas as operações
- **Histórico Detalhado**: Rastreamento completo de todas as notificações
- **Segurança Robusta**: Autenticação, permissões e rate limiting

---

## 🏗️ Arquitetura do Sistema

### Componentes Principais

```
┌─────────────────────────────────────────────────────────────┐
│                    APLICAÇÃO DJANGO                          │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Models     │  │   Services   │  │    Views     │     │
│  │              │  │              │  │              │     │
│  │ • Notificacao│←→│ Notification │←→│ API REST     │     │
│  │ • Tipo       │  │   Service    │  │ • Enviar     │     │
│  │ • Canal      │  │              │  │ • Listar     │     │
│  │ • Preferencia│  │ • Validação  │  │ • Estatística│     │
│  │ • Template   │  │ • Processam. │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         ↓                  ↓                  ↓             │
└─────────┼──────────────────┼──────────────────┼─────────────┘
          │                  │                  │
          ↓                  ↓                  ↓
┌─────────────────────────────────────────────────────────────┐
│                     BANCO DE DADOS                           │
│                      PostgreSQL                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    INTEGRAÇÃO N8N                            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Webhook    │→ │   Router     │→ │   Channels   │     │
│  │   Receiver   │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  │ • WhatsApp   │     │
│                                       │ • Email      │     │
│                                       │ • SMS        │     │
│                                       │ • Push       │     │
│                                       └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### Fluxo de Processamento

```
1. Evento Trigger
   ↓
2. Serviço cria Notificação
   ↓
3. Valida Preferências do Usuário
   ↓
4. Renderiza Template
   ↓
5. Envia para N8N via Webhook
   ↓
6. N8N roteia para canal específico
   ↓
7. Recebe confirmação de entrega
   ↓
8. Atualiza status no banco
```

---

## 🗄️ Estrutura de Banco de Dados

### 📊 Diagrama ER

```
┌─────────────────────┐
│  TipoNotificacao    │
├─────────────────────┤
│ id (PK)            │
│ codigo (UNIQUE)    │
│ nome               │
│ descricao          │
│ ativo              │
│ template_padrao    │
│ prioridade_padrao  │
│ whatsapp_config    │◄────┐
└─────────────────────┘      │
         ▲                   │
         │                   │
         │                   │
┌─────────────────────┐      │
│  CanalNotificacao   │      │
├─────────────────────┤      │
│ id (PK)            │      │
│ codigo (UNIQUE)    │      │
│ nome               │      │
│ ativo              │      │
│ configuracao       │      │
│ icone              │◄──┐  │
└─────────────────────┘   │  │
         ▲                │  │
         │                │  │
         │                │  │
┌─────────────────────────────────────┐
│         Notificacao                 │
├─────────────────────────────────────┤
│ id (PK)                            │
│ tipo_id (FK) ──────────────────────┘
│ canal_id (FK) ─────────────────────┘
│ destinatario_id (FK → User)        │
│ destinatario_email                 │
│ destinatario_telefone              │
│ titulo                             │
│ mensagem                           │
│ dados_contexto (JSON)              │
│ status                             │
│ prioridade                         │
│ tentativas                         │
│ max_tentativas                     │
│ data_criacao                       │
│ data_envio                         │
│ data_agendamento                   │
│ n8n_webhook_id                     │
│ n8n_execution_id                   │
│ n8n_response (JSON)                │
│ erro_detalhes                      │
└─────────────────────────────────────┘
         ▲
         │
         │
┌─────────────────────────────────────┐
│   PreferenciaNotificacao            │
├─────────────────────────────────────┤
│ id (PK)                            │
│ usuario_id (FK → User)             │
│ tipo_notificacao_id (FK)           │
│ canal_preferido_id (FK)            │
│ ativo                              │
│ horario_inicio                     │
│ horario_fim                        │
│ dias_semana (JSON)                 │
│ UNIQUE(usuario, tipo, canal)       │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│     TemplateNotificacao             │
├─────────────────────────────────────┤
│ id (PK)                            │
│ tipo_notificacao_id (FK)           │
│ canal_id (FK)                      │
│ nome                               │
│ assunto                            │
│ corpo_html                         │
│ corpo_texto                        │
│ variaveis (JSON)                   │
│ ativo                              │
│ UNIQUE(tipo_notificacao, canal)    │
└─────────────────────────────────────┘
```

### 📝 Detalhamento das Tabelas

#### 1. **TipoNotificacao** (`vendas_web_tiponotificacao`)

Armazena os tipos de notificações disponíveis no sistema.

| Campo              | Tipo         | Descrição                                    | Exemplo                  |
|--------------------|--------------|----------------------------------------------|--------------------------|
| id                 | BigInt (PK)  | Identificador único                          | 1                        |
| codigo             | VARCHAR(50)  | Código único do tipo (UNIQUE)                | 'lead_novo'              |
| nome               | VARCHAR(100) | Nome descritivo                              | 'Novo Lead'              |
| descricao          | TEXT         | Descrição detalhada                          | 'Notificação quando...'  |
| ativo              | BOOLEAN      | Se o tipo está ativo                         | true                     |
| template_padrao    | TEXT         | Template padrão da mensagem                  | 'Olá {{nome}}...'        |
| prioridade_padrao  | VARCHAR(20)  | Prioridade padrão                            | 'normal'                 |
| whatsapp_config    | JSONB        | Configurações específicas do WhatsApp        | {"format": "text"}       |

**Choices para `codigo`:**
- `lead_novo` - Novo Lead
- `lead_convertido` - Lead Convertido
- `venda_aprovada` - Venda Aprovada
- `venda_rejeitada` - Venda Rejeitada
- `prospecto_aguardando` - Prospecto Aguardando Validação

**Choices para `prioridade_padrao`:**
- `baixa` - Baixa
- `normal` - Normal
- `alta` - Alta
- `urgente` - Urgente

**Índices:**
- PRIMARY KEY (id)
- UNIQUE INDEX (codigo)
- INDEX (ativo)
- INDEX (nome)

---

#### 2. **CanalNotificacao** (`vendas_web_canalnotificacao`)

Define os canais de comunicação disponíveis.

| Campo         | Tipo        | Descrição                           | Exemplo                     |
|---------------|-------------|-------------------------------------|-----------------------------|
| id            | BigInt (PK) | Identificador único                 | 1                           |
| codigo        | VARCHAR(20) | Código único do canal (UNIQUE)      | 'whatsapp'                  |
| nome          | VARCHAR(50) | Nome do canal                       | 'WhatsApp'                  |
| ativo         | BOOLEAN     | Se o canal está ativo               | true                        |
| configuracao  | JSONB       | Configurações específicas do canal  | {"api_key": "xxx"}          |
| icone         | VARCHAR(50) | Classe do ícone FontAwesome         | 'fab fa-whatsapp'           |

**Choices para `codigo`:**
- `whatsapp` - WhatsApp
- `webhook` - Webhook

**Índices:**
- PRIMARY KEY (id)
- UNIQUE INDEX (codigo)
- INDEX (ativo)

---

#### 3. **Notificacao** (`vendas_web_notificacao`)

Registro de todas as notificações enviadas ou agendadas.

| Campo                  | Tipo           | Descrição                                | Exemplo                     |
|------------------------|----------------|------------------------------------------|-----------------------------|
| id                     | BigInt (PK)    | Identificador único                      | 1                           |
| tipo_id                | BigInt (FK)    | Referência ao tipo de notificação       | 1                           |
| canal_id               | BigInt (FK)    | Referência ao canal utilizado           | 2                           |
| destinatario_id        | Int (FK)       | Referência ao usuário destinatário      | 5                           |
| destinatario_email     | VARCHAR(254)   | Email do destinatário (opcional)        | 'user@email.com'            |
| destinatario_telefone  | VARCHAR(20)    | Telefone do destinatário (opcional)     | '5511999999999'             |
| titulo                 | VARCHAR(200)   | Título da notificação                   | 'Novo Lead Recebido'        |
| mensagem               | TEXT           | Corpo da mensagem                       | 'Um novo lead foi...'       |
| dados_contexto         | JSONB          | Dados para personalização               | {"lead": {"nome": "João"}}  |
| status                 | VARCHAR(20)    | Status atual                            | 'enviada'                   |
| prioridade             | VARCHAR(20)    | Nível de prioridade                     | 'alta'                      |
| tentativas             | Int            | Número de tentativas de envio           | 1                           |
| max_tentativas         | Int            | Máximo de tentativas permitidas         | 3                           |
| data_criacao           | TIMESTAMP      | Data/hora de criação                    | '2025-10-23 10:00:00'       |
| data_envio             | TIMESTAMP      | Data/hora do envio efetivo              | '2025-10-23 10:01:30'       |
| data_agendamento       | TIMESTAMP      | Data/hora para envio agendado           | '2025-10-23 15:00:00'       |
| n8n_webhook_id         | VARCHAR(100)   | ID do webhook no N8N                    | 'webhook-123'               |
| n8n_execution_id       | VARCHAR(100)   | ID da execução no N8N                   | 'exec-456'                  |
| n8n_response           | JSONB          | Resposta do N8N                         | {"status": "success"}       |
| erro_detalhes          | TEXT           | Detalhes de erros (se houver)           | 'Connection timeout'        |

**Choices para `status`:**

| Código | Tradução | Descrição Completa | Quando Ocorre |
|--------|----------|-------------------|---------------|
| `pendente` | **Pendente** | Aguardando processamento | Notificação criada mas ainda não enviada. Estado inicial. |
| `enviando` | **Enviando** | Em processo de envio | Sendo processada pelo sistema ou N8N. Estado transitório. |
| `enviada` | **Enviada** | Enviada com sucesso | Confirmação de entrega recebida do canal. Estado final de sucesso. |
| `falhou` | **Falhou** | Falhou no envio | Erro durante processamento após todas as tentativas. Estado final de erro. |
| `cancelada` | **Cancelada** | Cancelada pelo usuário | Cancelada manualmente antes do envio. Estado final. |

**Fluxo de Status:**
```
[pendente] → [enviando] → [enviada] ✅
                    ↓
                [falhou] ❌
                    
[pendente] → [cancelada] 🚫
```

**Observações Importantes:**
- **pendente**: Pode permanecer neste status se estiver agendada para envio futuro
- **enviando**: Status transitório, geralmente dura poucos segundos
- **enviada**: Confirma que o canal (WhatsApp/Email/etc) recebeu e processou
- **falhou**: Após 3 tentativas (configurável), muda para este status
- **cancelada**: Apenas através de ação manual ou regra de negócio

**Choices para `prioridade`:**

| Código | Tradução | Descrição | Processamento |
|--------|----------|-----------|---------------|
| `baixa` | **Baixa** | Prioridade baixa, não urgente | Processada em lotes maiores, pode ter delay |
| `normal` | **Normal** | Prioridade padrão | Processamento regular, até 5 minutos |
| `alta` | **Alta** | Prioridade alta, importante | Processamento prioritário, até 1 minuto |
| `urgente` | **Urgente** | Prioridade máxima, crítica | Processamento imediato, até 30 segundos |

**Índices:**
- PRIMARY KEY (id)
- INDEX (status)
- INDEX (data_criacao)
- INDEX (tipo_id)
- INDEX (canal_id)
- INDEX (destinatario_id)

**Foreign Keys:**
- tipo_id → vendas_web_tiponotificacao(id) ON DELETE CASCADE
- canal_id → vendas_web_canalnotificacao(id) ON DELETE CASCADE
- destinatario_id → auth_user(id) ON DELETE CASCADE

---

#### 4. **PreferenciaNotificacao** (`vendas_web_preferencianotificacao`)

Armazena as preferências de notificação de cada usuário.

| Campo                  | Tipo         | Descrição                                | Exemplo                     |
|------------------------|--------------|------------------------------------------|-----------------------------|
| id                     | BigInt (PK)  | Identificador único                      | 1                           |
| usuario_id             | Int (FK)     | Referência ao usuário                   | 5                           |
| tipo_notificacao_id    | BigInt (FK)  | Tipo de notificação                     | 1                           |
| canal_preferido_id     | BigInt (FK)  | Canal preferido                         | 2                           |
| ativo                  | BOOLEAN      | Se a preferência está ativa             | true                        |
| horario_inicio         | TIME         | Horário inicial para receber            | '08:00:00'                  |
| horario_fim            | TIME         | Horário final para receber              | '18:00:00'                  |
| dias_semana            | JSONB        | Dias da semana permitidos [0-6]         | [0, 1, 2, 3, 4]             |

**Constraint:**
- UNIQUE (usuario_id, tipo_notificacao_id, canal_preferido_id)

**Índices:**
- PRIMARY KEY (id)
- UNIQUE INDEX (usuario, tipo, canal)
- INDEX (usuario_id)
- INDEX (ativo)

**Foreign Keys:**
- usuario_id → auth_user(id) ON DELETE CASCADE
- tipo_notificacao_id → vendas_web_tiponotificacao(id) ON DELETE CASCADE
- canal_preferido_id → vendas_web_canalnotificacao(id) ON DELETE CASCADE

---

#### 5. **TemplateNotificacao** (`vendas_web_templatenotificacao`)

Templates de notificação personalizados por canal.

| Campo                  | Tipo         | Descrição                                | Exemplo                     |
|------------------------|--------------|------------------------------------------|-----------------------------|
| id                     | BigInt (PK)  | Identificador único                      | 1                           |
| tipo_notificacao_id    | BigInt (FK)  | Tipo de notificação                     | 1                           |
| canal_id               | BigInt (FK)  | Canal específico                        | 2                           |
| nome                   | VARCHAR(100) | Nome do template                        | 'Novo Lead - WhatsApp'      |
| assunto                | VARCHAR(200) | Assunto (para email)                    | 'Novo Lead Recebido'        |
| corpo_html             | TEXT         | Template HTML (para email)              | '<html>...</html>'          |
| corpo_texto            | TEXT         | Template texto simples                  | 'Olá {{nome}}...'           |
| variaveis              | JSONB        | Lista de variáveis disponíveis          | ["nome", "empresa", "tel"]  |
| ativo                  | BOOLEAN      | Se o template está ativo                | true                        |

**Constraint:**
- UNIQUE (tipo_notificacao_id, canal_id)

**Índices:**
- PRIMARY KEY (id)
- UNIQUE INDEX (tipo_notificacao, canal)
- INDEX (ativo)

**Foreign Keys:**
- tipo_notificacao_id → vendas_web_tiponotificacao(id) ON DELETE CASCADE
- canal_id → vendas_web_canalnotificacao(id) ON DELETE CASCADE

---

### 🔗 Relacionamentos

```
User (1) ──────< (N) PreferenciaNotificacao
User (1) ──────< (N) Notificacao

TipoNotificacao (1) ──────< (N) PreferenciaNotificacao
TipoNotificacao (1) ──────< (N) Notificacao
TipoNotificacao (1) ──────< (N) TemplateNotificacao

CanalNotificacao (1) ──────< (N) PreferenciaNotificacao
CanalNotificacao (1) ──────< (N) Notificacao
CanalNotificacao (1) ──────< (N) TemplateNotificacao
```

---

## 🔌 APIs REST

### 📍 Endpoints Disponíveis

Todas as APIs estão protegidas por autenticação (`@login_required`) e requerem o token CSRF no header.

**Base URL**: `https://aurora.consulteplus.com`

---

### 1. **Enviar Notificação**

Envia uma notificação para um ou mais destinatários.

**Endpoint**: `POST /api/notificacoes/enviar/`

**Headers**:
```http
Content-Type: application/json
X-CSRFToken: {csrf_token}
Cookie: sessionid={session_id}
```

**Request Body**:
```json
{
  "tipo": "lead_novo",
  "destinatarios": [1, 2, 3],
  "dados_contexto": {
    "lead": {
      "nome": "João Silva",
      "empresa": "Empresa ABC",
      "email": "joao@empresa.com",
      "telefone": "(11) 99999-9999",
      "origem": "Site"
    }
  },
  "prioridade": "alta",
  "agendamento": "2025-10-24T15:00:00",
  "canais_especificos": ["whatsapp", "email"]
}
```

**Parâmetros**:

| Campo              | Tipo     | Obrigatório | Descrição                                    |
|--------------------|----------|-------------|----------------------------------------------|
| tipo               | string   | Sim         | Código do tipo de notificação                |
| destinatarios      | array    | Sim*        | IDs dos usuários destinatários               |
| destinatario_email | string   | Sim*        | Email do destinatário externo                |
| dados_contexto     | object   | Não         | Dados para personalização do template        |
| prioridade         | string   | Não         | Prioridade: baixa/normal/alta/urgente        |
| agendamento        | datetime | Não         | Data/hora para envio agendado (ISO 8601)     |
| canais_especificos | array    | Não         | Lista de canais específicos                  |

*Deve fornecer `destinatarios` OU `destinatario_email`

**Response** (200 OK):
```json
{
  "success": true,
  "message": "3 notificações criadas com sucesso",
  "notificacoes": [
    {
      "id": 123,
      "tipo": "Novo Lead",
      "canal": "WhatsApp",
      "destinatario": "user1@email.com",
      "status": "enviada",
      "data_criacao": "2025-10-23T10:00:00Z"
    },
    {
      "id": 124,
      "tipo": "Novo Lead",
      "canal": "Email",
      "destinatario": "user2@email.com",
      "status": "pendente",
      "data_criacao": "2025-10-23T10:00:01Z"
    }
  ]
}
```

**Response** (400 Bad Request):
```json
{
  "error": "Tipo de notificação inválido"
}
```

---

### 2. **Listar Notificações**

Lista as notificações com filtros e paginação.

**Endpoint**: `GET /api/notificacoes/listar/`

**Query Parameters**:

| Parâmetro   | Tipo    | Descrição                              | Exemplo           |
|-------------|---------|----------------------------------------|-------------------|
| status      | string  | Filtrar por status                     | enviada           |
| tipo        | integer | Filtrar por tipo (ID)                  | 1                 |
| canal       | integer | Filtrar por canal (ID)                 | 2                 |
| data_inicio | date    | Data inicial (YYYY-MM-DD)              | 2025-10-01        |
| data_fim    | date    | Data final (YYYY-MM-DD)                | 2025-10-31        |
| limit       | integer | Limite de resultados                   | 50                |
| offset      | integer | Offset para paginação                  | 0                 |

**Exemplo de Request**:
```http
GET /api/notificacoes/listar/?status=enviada&limit=20&offset=0
```

**Response** (200 OK):
```json
{
  "success": true,
  "count": 150,
  "next": "/api/notificacoes/listar/?status=enviada&limit=20&offset=20",
  "previous": null,
  "results": [
    {
      "id": 123,
      "tipo": {
        "id": 1,
        "codigo": "lead_novo",
        "nome": "Novo Lead"
      },
      "canal": {
        "id": 2,
        "codigo": "whatsapp",
        "nome": "WhatsApp",
        "icone": "fab fa-whatsapp"
      },
      "destinatario": {
        "id": 5,
        "username": "usuario1",
        "email": "usuario1@email.com"
      },
      "titulo": "Novo Lead Recebido - João Silva",
      "mensagem": "Um novo lead foi cadastrado...",
      "status": "enviada",
      "prioridade": "alta",
      "tentativas": 1,
      "data_criacao": "2025-10-23T10:00:00Z",
      "data_envio": "2025-10-23T10:01:30Z",
      "n8n_execution_id": "exec-456"
    }
  ]
}
```

---

### 3. **Obter Estatísticas**

Retorna estatísticas completas do sistema de notificações.

**Endpoint**: `GET /api/notificacoes/estatisticas/`

**Query Parameters**:

| Parâmetro   | Tipo | Descrição                | Exemplo     |
|-------------|------|--------------------------|-------------|
| data_inicio | date | Data inicial (YYYY-MM-DD)| 2025-10-01  |
| data_fim    | date | Data final (YYYY-MM-DD)  | 2025-10-31  |

**Exemplo de Request**:
```http
GET /api/notificacoes/estatisticas/?data_inicio=2025-10-01&data_fim=2025-10-31
```

**Response** (200 OK):
```json
{
  "success": true,
  "estatisticas": {
    "total_notificacoes": 1250,
    "notificacoes_hoje": 45,
    "notificacoes_enviadas": 1100,
    "notificacoes_pendentes": 20,
    "notificacoes_falharam": 130,
    "taxa_entrega": 89.4,
    "canais_ativos": 2,
    "tipos_ativos": 5,
    "evolucao_data": [
      {
        "date": "17/10",
        "enviadas": 45,
        "falharam": 5
      },
      {
        "date": "18/10",
        "enviadas": 52,
        "falharam": 3
      }
    ],
    "tipos_notificacao": [
      {
        "nome": "Novo Lead",
        "codigo": "lead_novo",
        "total": 450,
        "enviadas": 420,
        "falharam": 20,
        "pendentes": 10,
        "taxa_sucesso": 95.5
      }
    ],
    "canais_notificacao": [
      {
        "nome": "WhatsApp",
        "codigo": "whatsapp",
        "total": 800,
        "enviadas": 750
      }
    ]
  }
}
```

---

### 4. **Gerenciar Preferências**

Obtém ou atualiza as preferências de notificação do usuário.

**Endpoint GET**: `GET /api/notificacoes/preferencias/`

**Response** (200 OK):
```json
{
  "success": true,
  "preferencias": [
    {
      "id": 1,
      "tipo_notificacao": {
        "id": 1,
        "nome": "Novo Lead",
        "codigo": "lead_novo"
      },
      "canal_preferido": {
        "id": 2,
        "nome": "WhatsApp",
        "codigo": "whatsapp"
      },
      "ativo": true,
      "horario_inicio": "08:00:00",
      "horario_fim": "18:00:00",
      "dias_semana": [0, 1, 2, 3, 4]
    }
  ]
}
```

**Endpoint POST**: `POST /api/notificacoes/preferencias/`

**Request Body**:
```json
{
  "tipo_notificacao_id": 1,
  "canal_preferido_id": 2,
  "ativo": true,
  "horario_inicio": "08:00",
  "horario_fim": "18:00",
  "dias_semana": [0, 1, 2, 3, 4]
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Preferência salva com sucesso",
  "preferencia": {
    "id": 1,
    "tipo_notificacao_id": 1,
    "canal_preferido_id": 2,
    "ativo": true,
    "horario_inicio": "08:00:00",
    "horario_fim": "18:00:00",
    "dias_semana": [0, 1, 2, 3, 4]
  }
}
```

---

### 5. **Testar Notificação**

Envia uma notificação de teste.

**Endpoint**: `POST /api/notificacoes/teste/`

**Request Body**:
```json
{
  "tipo": "lead_novo",
  "canal": "whatsapp",
  "destinatario": 5
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Notificação de teste enviada com sucesso",
  "notificacao": {
    "id": 999,
    "status": "enviada",
    "canal": "WhatsApp",
    "destinatario": "usuario@email.com"
  }
}
```

---

### 6. **Gerenciar Tipos de Notificação**

**Listar Tipos**: `GET /api/tipos-notificacao/`

**Response** (200 OK):
```json
{
  "success": true,
  "tipos": [
    {
      "id": 1,
      "codigo": "lead_novo",
      "nome": "Novo Lead",
      "descricao": "Notificação quando um novo lead é cadastrado",
      "ativo": true,
      "prioridade_padrao": "normal"
    }
  ]
}
```

**Obter Tipo Específico**: `GET /api/tipos-notificacao/{tipo_id}/`

**Criar Tipo**: `POST /api/tipos-notificacao/`

**Atualizar Tipo**: `PUT /api/tipos-notificacao/{tipo_id}/`

**Deletar Tipo**: `DELETE /api/tipos-notificacao/{tipo_id}/`

---

### 7. **Gerenciar Canais de Notificação**

**Listar Canais**: `GET /api/canais-notificacao/`

**Response** (200 OK):
```json
{
  "success": true,
  "canais": [
    {
      "id": 1,
      "codigo": "whatsapp",
      "nome": "WhatsApp",
      "ativo": true,
      "icone": "fab fa-whatsapp",
      "configuracao": {
        "api_url": "https://api.whatsapp.com",
        "timeout": 30
      }
    }
  ]
}
```

**Obter Canal Específico**: `GET /api/canais-notificacao/{canal_id}/`

**Criar Canal**: `POST /api/canais-notificacao/`

**Atualizar Canal**: `PUT /api/canais-notificacao/{canal_id}/`

**Deletar Canal**: `DELETE /api/canais-notificacao/{canal_id}/`

---

### 8. **Gerenciar Templates**

**Listar Templates**: `GET /api/templates-notificacoes/`

**Response** (200 OK):
```json
{
  "success": true,
  "templates": [
    {
      "id": 1,
      "tipo_notificacao": {
        "id": 1,
        "nome": "Novo Lead"
      },
      "canal": {
        "id": 2,
        "nome": "WhatsApp"
      },
      "nome": "Template Lead WhatsApp",
      "assunto": "Novo Lead Recebido",
      "corpo_texto": "Olá! Um novo lead foi cadastrado: {{lead.nome}}",
      "variaveis": ["lead.nome", "lead.empresa", "lead.telefone"],
      "ativo": true
    }
  ]
}
```

**Obter Template Específico**: `GET /api/templates-notificacoes/{template_id}/`

**Criar Template**: `POST /api/templates-notificacoes/`

**Atualizar Template**: `PUT /api/templates-notificacoes/{template_id}/`

**Deletar Template**: `DELETE /api/templates-notificacoes/{template_id}/`

---

### 🔐 Autenticação e Segurança

**Headers Obrigatórios**:
```http
Cookie: sessionid={session_id}
X-CSRFToken: {csrf_token}
```

**Obter CSRF Token**:
```javascript
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');
```

**Rate Limiting**:
- Máximo de 100 requisições por minuto por usuário
- Máximo de 1000 notificações por hora

**Permissões**:
- **Superusuário**: Acesso total
- **Grupo adm_all**: Gerenciar configurações
- **Usuário comum**: Apenas suas próprias preferências

---

## 🚀 Serviço de Notificações

### NotificationService

Classe principal que gerencia toda a lógica de notificações.

**Localização**: `vendas_web/services/notification_service.py`

### Métodos Principais

#### 1. `enviar_notificacao()`

```python
def enviar_notificacao(
    self,
    tipo_codigo: str,
    destinatarios: List[User],
    dados_contexto: Dict[str, Any] = None,
    prioridade: str = 'normal',
    agendamento: datetime = None,
    canais_especificos: List[str] = None
) -> List[Notificacao]:
    """
    Envia notificação para uma lista de usuários
    
    Args:
        tipo_codigo: Código do tipo de notificação
        destinatarios: Lista de usuários destinatários
        dados_contexto: Dados para personalização
        prioridade: Prioridade da notificação
        agendamento: Data/hora para envio agendado
        canais_especificos: Lista de canais específicos
        
    Returns:
        Lista de objetos Notificacao criados
    """
```

**Exemplo de Uso**:
```python
from vendas_web.services.notification_service import notification_service
from django.contrib.auth.models import User

# Buscar destinatários
users = User.objects.filter(groups__name='vendedores')

# Enviar notificação
notificacoes = notification_service.enviar_notificacao(
    tipo_codigo='lead_novo',
    destinatarios=list(users),
    dados_contexto={
        'lead': {
            'nome': 'João Silva',
            'empresa': 'Empresa ABC',
            'email': 'joao@empresa.com',
            'telefone': '(11) 99999-9999'
        }
    },
    prioridade='alta'
)
```

---

#### 2. `enviar_notificacao_para_grupo()`

```python
def enviar_notificacao_para_grupo(
    self,
    tipo_codigo: str,
    grupo_nome: str,
    dados_contexto: Dict[str, Any] = None,
    prioridade: str = 'normal'
) -> List[Notificacao]:
    """
    Envia notificação para todos os usuários de um grupo
    
    Args:
        tipo_codigo: Código do tipo de notificação
        grupo_nome: Nome do grupo Django
        dados_contexto: Dados para personalização
        prioridade: Prioridade da notificação
        
    Returns:
        Lista de objetos Notificacao criados
    """
```

**Exemplo de Uso**:
```python
# Enviar para todos os vendedores
notificacoes = notification_service.enviar_notificacao_para_grupo(
    tipo_codigo='venda_aprovada',
    grupo_nome='vendedores',
    dados_contexto={
        'venda': {
            'valor': 'R$ 1.500,00',
            'cliente': 'Maria Santos',
            'plano': 'Plano 100MB'
        }
    },
    prioridade='normal'
)
```

---

#### 3. `enviar_notificacao_externa()`

```python
def enviar_notificacao_externa(
    self,
    tipo_codigo: str,
    email: str = None,
    telefone: str = None,
    dados_contexto: Dict[str, Any] = None,
    canal_preferido: str = 'email',
    prioridade: str = 'normal'
) -> Optional[Notificacao]:
    """
    Envia notificação para destinatário externo (não-usuário)
    
    Args:
        tipo_codigo: Código do tipo de notificação
        email: Email do destinatário
        telefone: Telefone do destinatário
        dados_contexto: Dados para personalização
        canal_preferido: Canal a ser utilizado
        prioridade: Prioridade da notificação
        
    Returns:
        Objeto Notificacao criado ou None
    """
```

**Exemplo de Uso**:
```python
# Enviar para cliente externo
notificacao = notification_service.enviar_notificacao_externa(
    tipo_codigo='venda_aprovada',
    email='cliente@email.com',
    telefone='5511999999999',
    dados_contexto={
        'cliente': {
            'nome': 'João Silva',
            'plano': 'Plano 100MB'
        },
        'venda': {
            'valor': 'R$ 150,00',
            'data_ativacao': '2025-10-25'
        }
    },
    canal_preferido='whatsapp',
    prioridade='alta'
)
```

---

#### 4. `obter_estatisticas()`

```python
def obter_estatisticas(
    self,
    data_inicio: datetime = None,
    data_fim: datetime = None
) -> Dict[str, Any]:
    """
    Obtém estatísticas do sistema de notificações
    
    Args:
        data_inicio: Data inicial para filtro
        data_fim: Data final para filtro
        
    Returns:
        Dicionário com estatísticas completas
    """
```

**Exemplo de Uso**:
```python
from datetime import datetime, timedelta

# Estatísticas dos últimos 30 dias
data_fim = datetime.now()
data_inicio = data_fim - timedelta(days=30)

stats = notification_service.obter_estatisticas(
    data_inicio=data_inicio,
    data_fim=data_fim
)

print(f"Total de notificações: {stats['total_notificacoes']}")
print(f"Taxa de entrega: {stats['taxa_entrega']}%")
```

---

### Fluxo Interno do Serviço

```python
# 1. Validação do tipo de notificação
tipo = TipoNotificacao.objects.get(codigo=tipo_codigo, ativo=True)

# 2. Para cada destinatário
for usuario in destinatarios:
    # 3. Obter preferências do usuário
    preferencias = self._obter_preferencias_usuario(usuario, tipo)
    
    # 4. Para cada canal preferido
    for preferencia in preferencias:
        # 5. Verificar horário permitido
        if not self._horario_permitido(preferencia):
            # Agendar para próximo horário válido
            data_envio = self._calcular_proximo_horario(preferencia)
        
        # 6. Buscar ou criar template
        template = self._obter_template(tipo, canal)
        
        # 7. Renderizar mensagem
        mensagem = self._renderizar_template(template, dados_contexto)
        
        # 8. Criar registro de notificação
        notificacao = Notificacao.objects.create(
            tipo=tipo,
            canal=canal,
            destinatario=usuario,
            titulo=titulo,
            mensagem=mensagem,
            dados_contexto=dados_contexto,
            prioridade=prioridade,
            status='pendente',
            data_agendamento=data_envio
        )
        
# 9. Processar notificações pendentes
self._processar_notificacoes_pendentes()
```

---

### Configuração

**Variáveis de Ambiente** (`settings.py`):

```python
# N8N Integration
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'https://n8n.aurora.com/webhook/notifications')
N8N_API_KEY = os.getenv('N8N_API_KEY', '')

# Notification Settings
NOTIFICATION_MAX_RETRIES = 3
NOTIFICATION_RETRY_DELAYS = [2, 4, 8]  # minutos
NOTIFICATION_TIMEOUT = 30  # segundos
NOTIFICATION_BATCH_SIZE = 100

# Site URL
SITE_URL = os.getenv('SITE_URL', 'https://aurora.consulteplus.com')
```

---

## 📱 Tipos de Notificação

### Tipos Disponíveis

#### 1. **lead_novo** - Novo Lead
- **Descrição**: Disparada quando um novo lead é cadastrado no sistema
- **Prioridade Padrão**: Normal
- **Variáveis Disponíveis**:
  - `lead.nome` - Nome do lead
  - `lead.empresa` - Empresa do lead
  - `lead.email` - Email do lead
  - `lead.telefone` - Telefone do lead
  - `lead.origem` - Origem do lead
  - `lead.mensagem` - Mensagem do lead
- **Canais Recomendados**: WhatsApp, Email

**Template Exemplo**:
```
🆕 Novo Lead Recebido!

Nome: {{lead.nome}}
Empresa: {{lead.empresa}}
Email: {{lead.email}}
Telefone: {{lead.telefone}}
Origem: {{lead.origem}}

Mensagem: {{lead.mensagem}}

Acesse o sistema para mais detalhes.
```

---

#### 2. **lead_convertido** - Lead Convertido
- **Descrição**: Disparada quando um lead é convertido em prospecto
- **Prioridade Padrão**: Alta
- **Variáveis Disponíveis**:
  - `lead.nome` - Nome do lead
  - `prospecto.numero` - Número do prospecto
  - `prospecto.vendedor` - Vendedor responsável
- **Canais Recomendados**: WhatsApp, Push

---

#### 3. **venda_aprovada** - Venda Aprovada
- **Descrição**: Disparada quando uma venda é aprovada
- **Prioridade Padrão**: Alta
- **Variáveis Disponíveis**:
  - `venda.numero` - Número da venda
  - `venda.valor` - Valor da venda
  - `venda.cliente` - Nome do cliente
  - `venda.vendedor` - Vendedor responsável
  - `venda.plano` - Plano contratado
- **Canais Recomendados**: WhatsApp, Email, Push

---

#### 4. **venda_rejeitada** - Venda Rejeitada
- **Descrição**: Disparada quando uma venda é rejeitada
- **Prioridade Padrão**: Alta
- **Variáveis Disponíveis**:
  - `venda.numero` - Número da venda
  - `venda.motivo` - Motivo da rejeição
  - `venda.cliente` - Nome do cliente
- **Canais Recomendados**: WhatsApp, Email

---

#### 5. **prospecto_aguardando** - Prospecto Aguardando Validação
- **Descrição**: Disparada quando um prospecto está aguardando validação
- **Prioridade Padrão**: Normal
- **Variáveis Disponíveis**:
  - `prospecto.numero` - Número do prospecto
  - `prospecto.nome` - Nome do prospecto
  - `prospecto.vendedor` - Vendedor responsável
  - `prospecto.tempo_espera` - Tempo de espera
- **Canais Recomendados**: Email, Webhook

---

### Como Criar Novo Tipo de Notificação

#### Via Django Admin

1. Acesse: `/admin/vendas_web/tiponotificacao/`
2. Clique em "Adicionar Tipo de Notificação"
3. Preencha os campos:
   - **Código**: `novo_tipo` (único, snake_case)
   - **Nome**: `Novo Tipo de Notificação`
   - **Descrição**: Descrição detalhada
   - **Template Padrão**: Template com variáveis `{{var}}`
   - **Prioridade Padrão**: normal
   - **Ativo**: ✓
4. Salvar

#### Via Código Python

```python
from vendas_web.models import TipoNotificacao

tipo = TipoNotificacao.objects.create(
    codigo='novo_tipo',
    nome='Novo Tipo de Notificação',
    descricao='Descrição detalhada do novo tipo',
    ativo=True,
    template_padrao='Template com {{variaveis}}',
    prioridade_padrao='normal',
    whatsapp_config={
        'format': 'text',
        'max_length': 4096
    }
)
```

#### Via API REST

```javascript
fetch('/api/tipos-notificacao/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
    },
    body: JSON.stringify({
        codigo: 'novo_tipo',
        nome: 'Novo Tipo de Notificação',
        descricao: 'Descrição detalhada',
        template_padrao: 'Template com {{variaveis}}',
        prioridade_padrao: 'normal',
        ativo: true
    })
})
```

---

## 📢 Canais de Comunicação

### Canais Disponíveis

#### 1. **WhatsApp**

**Código**: `whatsapp`  
**Ícone**: `fab fa-whatsapp`

**Características**:
- ✅ Entrega instantânea
- ✅ Alta taxa de abertura (~98%)
- ✅ Suporte a emojis e formatação básica
- ⚠️ Limitação: 4096 caracteres

**Configuração**:
```json
{
  "api_url": "https://api.whatsapp.com/send",
  "api_key": "sua_chave_api",
  "timeout": 30,
  "retry_count": 3
}
```

**Formato da Mensagem**:
```python
{
    "phone": "5511999999999",
    "message": "Texto da mensagem",
    "format": "text"
}
```

---

#### 2. **Webhook**

**Código**: `webhook`  
**Ícone**: `fas fa-webhook`

**Características**:
- ✅ Integração com sistemas externos
- ✅ Payload JSON customizável
- ✅ Suporte a callbacks
- ✅ Sem limitação de tamanho

**Configuração**:
```json
{
  "url": "https://external-system.com/webhook",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer token",
    "Content-Type": "application/json"
  },
  "timeout": 30
}
```

**Formato do Payload**:
```json
{
  "event": "notification",
  "type": "lead_novo",
  "timestamp": "2025-10-23T10:00:00Z",
  "data": {
    "notificacao_id": 123,
    "titulo": "Novo Lead",
    "mensagem": "...",
    "dados_contexto": {}
  }
}
```

---

### Como Adicionar Novo Canal

#### Via Django Admin

1. Acesse: `/admin/vendas_web/canalnotificacao/`
2. Clique em "Adicionar Canal de Notificação"
3. Preencha:
   - **Código**: `novo_canal`
   - **Nome**: `Novo Canal`
   - **Ativo**: ✓
   - **Ícone**: `fas fa-icon`
   - **Configuração**: `{"key": "value"}`
4. Salvar

#### Implementar Handler no N8N

1. Criar novo workflow no N8N
2. Adicionar Webhook Receiver
3. Adicionar Router com condição: `canal === 'novo_canal'`
4. Implementar lógica de envio
5. Retornar resposta de sucesso/falha

---

## 🖥️ Interface Web

### Dashboard de Notificações

**URL**: `https://aurora.consulteplus.com/configuracoes/notificacoes/`

**Abas Disponíveis**:

1. **📋 Tipos de Notificação**
   - Lista todos os tipos cadastrados
   - Adicionar/Editar/Remover tipos
   - Configurar prioridade e templates

2. **📜 Histórico Geral**
   - Lista todas as notificações enviadas
   - Filtros: status, tipo, canal, data
   - Paginação e ordenação
   - Visualizar detalhes

3. **🧪 Testar Notificação**
   - Enviar notificação de teste
   - Selecionar tipo, canal e destinatário
   - Visualizar resposta em tempo real

4. **📊 Estatísticas**
   - Cards com métricas principais
   - Gráfico de evolução (linha)
   - Tabela detalhada por tipo
   - Filtros por período

### Funcionalidades

#### Enviar Notificação de Teste

```javascript
async function enviarTeste() {
    const response = await fetch('/api/notificacoes/teste/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            tipo: 'lead_novo',
            canal: 'whatsapp',
            destinatario: userId
        })
    });
    
    const data = await response.json();
    console.log(data);
}
```

#### Filtrar Estatísticas

```javascript
async function filtrarEstatisticas() {
    const dataInicio = document.getElementById('dataInicioNovo').value;
    const dataFim = document.getElementById('dataFimNovo').value;
    
    const response = await fetch(
        `/api/notificacoes/estatisticas/?data_inicio=${dataInicio}&data_fim=${dataFim}`
    );
    
    const data = await response.json();
    renderizarEstatisticas(data.estatisticas);
}
```

---

## 🔗 Integração N8N

### Workflow Recomendado

```
┌─────────────────────┐
│  Webhook Receiver   │
│  /webhook/notify    │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│   Function Node     │
│  Extrair Dados      │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│   Router Node       │
│  Direcionar Canal   │
└──────────┬──────────┘
           │
      ┌────┼─────┬────────┐
      │    │     │        │
      ↓    ↓     ↓        ↓
   ┌────┬────┬────────┬────────┐
   │ WA │ EM │  SMS   │ HOOK   │
   └────┴────┴────────┴────────┘
      │    │     │        │
      └────┼─────┴────────┘
           │
           ↓
┌─────────────────────┐
│   HTTP Response     │
│  Return Status      │
└─────────────────────┘
           │
           ↓
┌─────────────────────┐
│   Webhook POST      │
│  Update Django      │
└─────────────────────┘
```

### Configuração do Webhook

**URL**: `https://n8n.aurora.consulteplus.com/webhook/notifications`

**Método**: POST

**Headers**:
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer n8n_api_key"
}
```

**Payload Enviado pelo Django**:
```json
{
  "notificacao_id": 123,
  "tipo": "lead_novo",
  "canal": "whatsapp",
  "titulo": "Novo Lead Recebido - João Silva",
  "mensagem": "Um novo lead foi cadastrado...",
  "destinatario": {
    "id": 5,
    "nome": "Usuário Nome",
    "email": "usuario@email.com",
    "telefone": "5511999999999"
  },
  "dados_contexto": {
    "lead": {
      "nome": "João Silva",
      "empresa": "Empresa ABC",
      "email": "joao@empresa.com",
      "telefone": "(11) 99999-9999",
      "origem": "Site"
    }
  },
  "prioridade": "alta",
  "timestamp": "2025-10-23T10:00:00Z"
}
```

**Resposta Esperada**:
```json
{
  "success": true,
  "execution_id": "exec-456",
  "status": "sent",
  "message": "Notificação enviada com sucesso",
  "timestamp": "2025-10-23T10:01:30Z"
}
```

### Exemplo de Função N8N (JavaScript)

```javascript
// Extrair dados do webhook
const notificacao = $input.first().json;

// Formatar para WhatsApp
if (notificacao.canal === 'whatsapp') {
    return {
        json: {
            phone: notificacao.destinatario.telefone,
            message: notificacao.mensagem,
            format: 'text'
        }
    };
}

// Formatar para Email
if (notificacao.canal === 'email') {
    return {
        json: {
            to: notificacao.destinatario.email,
            subject: notificacao.titulo,
            html: notificacao.mensagem,
            from: 'noreply@aurora.consulteplus.com'
        }
    };
}

return notificacao;
```

---

## 💻 Exemplos de Uso

### Exemplo 1: Notificar Novo Lead

```python
from vendas_web.services.notification_service import notification_service
from django.contrib.auth.models import User

# Quando um novo lead é criado
def criar_lead(request):
    # Criar lead...
    lead = Lead.objects.create(
        nome=request.POST['nome'],
        email=request.POST['email'],
        telefone=request.POST['telefone'],
        empresa=request.POST.get('empresa', ''),
        origem=request.POST.get('origem', 'Site')
    )
    
    # Notificar vendedores
    vendedores = User.objects.filter(groups__name='vendedores')
    
    notificacoes = notification_service.enviar_notificacao(
        tipo_codigo='lead_novo',
        destinatarios=list(vendedores),
        dados_contexto={
            'lead': {
                'nome': lead.nome,
                'empresa': lead.empresa,
                'email': lead.email,
                'telefone': lead.telefone,
                'origem': lead.origem
            }
        },
        prioridade='alta'
    )
    
    return JsonResponse({'success': True, 'lead_id': lead.id})
```

---

### Exemplo 2: Notificar Venda Aprovada

```python
def aprovar_venda(request, venda_id):
    venda = Venda.objects.get(id=venda_id)
    venda.status = 'aprovada'
    venda.save()
    
    # Notificar vendedor
    notification_service.enviar_notificacao(
        tipo_codigo='venda_aprovada',
        destinatarios=[venda.vendedor],
        dados_contexto={
            'venda': {
                'numero': venda.numero,
                'valor': f'R$ {venda.valor:,.2f}',
                'cliente': venda.cliente.nome,
                'plano': venda.plano.nome
            }
        },
        prioridade='alta',
        canais_especificos=['whatsapp', 'email']
    )
    
    # Notificar cliente (externo)
    notification_service.enviar_notificacao_externa(
        tipo_codigo='venda_aprovada',
        email=venda.cliente.email,
        telefone=venda.cliente.telefone,
        dados_contexto={
            'cliente': {
                'nome': venda.cliente.nome
            },
            'venda': {
                'plano': venda.plano.nome,
                'valor': f'R$ {venda.valor:,.2f}',
                'data_ativacao': venda.data_ativacao.strftime('%d/%m/%Y')
            }
        },
        canal_preferido='whatsapp'
    )
    
    return JsonResponse({'success': True})
```

---

### Exemplo 3: Notificação Agendada

```python
from datetime import datetime, timedelta

def agendar_notificacao_relatorio():
    # Agendar para amanhã às 9h
    amanha_9h = (datetime.now() + timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    
    # Notificar gestores
    notification_service.enviar_notificacao_para_grupo(
        tipo_codigo='relatorio_diario',
        grupo_nome='gestores',
        dados_contexto={
            'relatorio': {
                'periodo': 'Ontem',
                'total_vendas': 15,
                'valor_total': 'R$ 25.000,00'
            }
        },
        prioridade='normal'
    )
```

---

### Exemplo 4: Webhook Customizado

```python
# Configurar webhook para integração externa
canal_webhook = CanalNotificacao.objects.create(
    codigo='crm_externo',
    nome='CRM Externo',
    ativo=True,
    icone='fas fa-link',
    configuracao={
        'url': 'https://crm.empresa.com/webhook/leads',
        'method': 'POST',
        'headers': {
            'Authorization': 'Bearer token_secreto',
            'Content-Type': 'application/json'
        },
        'timeout': 30
    }
)

# Enviar notificação via webhook
notification_service.enviar_notificacao(
    tipo_codigo='lead_novo',
    destinatarios=[usuario],
    canais_especificos=['crm_externo'],
    dados_contexto={
        'lead': {...}
    }
)
```

---

## ⚙️ Configuração e Deploy

### Requisitos

- **Python**: 3.10+
- **Django**: 4.2+
- **PostgreSQL**: 13+
- **N8N**: Latest version
- **Redis**: 6+ (opcional, para cache)

### Variáveis de Ambiente

Criar arquivo `.env`:

```bash
# Django
SECRET_KEY=sua_chave_secreta
DEBUG=False
ALLOWED_HOSTS=aurora.consulteplus.com

# Database
DB_NAME=aurora_db
DB_USER=postgres
DB_PASSWORD=senha_segura
DB_HOST=localhost
DB_PORT=5432

# N8N Integration
N8N_WEBHOOK_URL=https://n8n.aurora.consulteplus.com/webhook/notifications
N8N_API_KEY=n8n_api_key_secreto

# Site
SITE_URL=https://aurora.consulteplus.com

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=seu_email@gmail.com
EMAIL_HOST_PASSWORD=sua_senha
EMAIL_USE_TLS=True

# Notificações
NOTIFICATION_MAX_RETRIES=3
NOTIFICATION_RETRY_DELAYS=2,4,8
NOTIFICATION_TIMEOUT=30
NOTIFICATION_BATCH_SIZE=100
```

### Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-repo/aurora-isp.git
cd aurora-isp/dashboard_comercial/gerenciador_vendas

# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar banco de dados
python manage.py makemigrations
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Configurar dados iniciais de notificações
python manage.py setup_notifications

# Coletar arquivos estáticos
python manage.py collectstatic --no-input

# Rodar servidor (desenvolvimento)
python manage.py runserver 0.0.0.0:8000
```

### Deploy em Produção

#### Com Gunicorn + Nginx

**1. Instalar Gunicorn**:
```bash
pip install gunicorn
```

**2. Criar arquivo `gunicorn_config.py`**:
```python
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
errorlog = "/var/log/gunicorn/error.log"
accesslog = "/var/log/gunicorn/access.log"
loglevel = "info"
```

**3. Rodar Gunicorn**:
```bash
gunicorn gerenciador_vendas.wsgi:application -c gunicorn_config.py
```

**4. Configurar Nginx** (`/etc/nginx/sites-available/aurora`):
```nginx
server {
    listen 80;
    server_name aurora.consulteplus.com;

    location /static/ {
        alias /caminho/para/staticfiles/;
    }

    location /media/ {
        alias /caminho/para/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**5. Habilitar site**:
```bash
sudo ln -s /etc/nginx/sites-available/aurora /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**6. Configurar SSL com Certbot**:
```bash
sudo certbot --nginx -d aurora.consulteplus.com
```

---

### Comandos de Gerenciamento

```bash
# Processar notificações pendentes
python manage.py process_notifications

# Processar com limite
python manage.py process_notifications --limit 100

# Forçar processamento
python manage.py process_notifications --force

# Testar notificações
python manage.py test_notifications

# Limpar notificações antigas (30+ dias)
python manage.py cleanup_notifications --days 30

# Configurar dados iniciais
python manage.py setup_notifications

# Adicionar telefone aos usuários
python manage.py add_phone_to_users

# Configurar preferências padrão
python manage.py setup_user_preferences
```

---

## 📊 Monitoramento e Estatísticas

### Métricas Disponíveis

#### Dashboard Principal

**Cards de Resumo**:
- **Total de Notificações**: Todas as notificações no período
- **Enviadas com Sucesso**: Notificações entregues
- **Falharam**: Notificações com erro
- **Aguardando Envio**: Notificações pendentes

**Gráfico de Evolução**:
- Linha temporal dos últimos 7 dias (ou período filtrado)
- Uma linha para cada tipo de notificação
- Interativo com tooltips

**Tabela Detalhada por Tipo**:
- Nome e código do tipo
- Total, enviadas, falhadas, pendentes
- Taxa de sucesso (%)
- Ordenação por total decrescente

### Filtros

- **Data Início**: Filtrar a partir de uma data
- **Data Fim**: Filtrar até uma data
- **Limpar**: Remover filtros

### Exportar Dados

```python
import csv
from vendas_web.models import Notificacao

# Exportar para CSV
with open('notificacoes.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow([
        'ID', 'Tipo', 'Canal', 'Destinatário', 'Status',
        'Data Criação', 'Data Envio'
    ])
    
    for notif in Notificacao.objects.all():
        writer.writerow([
            notif.id,
            notif.tipo.nome,
            notif.canal.nome,
            notif.destinatario.email if notif.destinatario else notif.destinatario_email,
            notif.status,
            notif.data_criacao,
            notif.data_envio
        ])
```

---

## 🐛 Troubleshooting

### Problema 1: Por que Notificações Ficam Pendentes? ⏳

**Entendendo o Status Pendente:**

Uma notificação fica com status `pendente` quando foi criada mas **ainda não foi processada/enviada**. Isso é **NORMAL** e acontece por diversos motivos estratégicos:

#### 🔍 Motivos Comuns (Por Ordem de Frequência)

**1. ⏰ Fora do Horário Permitido (80% dos casos)**
```python
# Exemplo: Usuário configurou para receber apenas das 8h às 18h
# Se notificação for criada às 20h, ficará pendente até 8h do dia seguinte

from vendas_web.models import PreferenciaNotificacao

pref = PreferenciaNotificacao.objects.filter(
    usuario=usuario,
    tipo_notificacao__codigo='lead_novo'
).first()

print(f"Horário permitido: {pref.horario_inicio} - {pref.horario_fim}")
# Saída: Horário permitido: 08:00:00 - 18:00:00
```

**Solução**: Aguardar o próximo horário válido (automático) ou ajustar preferências do usuário.

---

**2. 📅 Dia da Semana Não Permitido (15% dos casos)**
```python
# Exemplo: Usuário configurou para receber apenas em dias úteis (0-4)
# Se notificação for criada no sábado, ficará pendente até segunda-feira

pref = PreferenciaNotificacao.objects.first()
print(f"Dias permitidos: {pref.dias_semana}")
# Saída: Dias permitidos: [0, 1, 2, 3, 4]  # Segunda a Sexta

from datetime import datetime
hoje = datetime.now().weekday()
print(f"Hoje é: {hoje}")  # 5 = Sábado, 6 = Domingo

if hoje not in pref.dias_semana:
    print("❌ Hoje não é um dia permitido para esta notificação")
```

**Solução**: Aguardar próximo dia útil (automático) ou ajustar preferências.

---

**3. 📆 Agendamento Futuro (3% dos casos)**
```python
# Notificação foi criada com agendamento para o futuro

from vendas_web.models import Notificacao

notif = Notificacao.objects.filter(status='pendente').first()
print(f"Data de criação: {notif.data_criacao}")
print(f"Data agendada: {notif.data_agendamento}")
# Saída:
# Data de criação: 2025-10-23 10:00:00
# Data agendada: 2025-10-24 15:00:00  # Agendada para amanhã!
```

**Solução**: Aguardar a data/hora agendada (automático).

---

**4. 🔄 Retry Após Falha (1% dos casos)**
```python
# Notificação falhou mas ainda tem tentativas disponíveis
# Sistema aplica backoff exponencial: 2min, 4min, 8min

notif = Notificacao.objects.filter(status='pendente', tentativas__gt=0).first()
print(f"Tentativas: {notif.tentativas}/{notif.max_tentativas}")
print(f"Próxima tentativa em: {notif.data_agendamento}")
# Saída:
# Tentativas: 1/3
# Próxima tentativa em: 2025-10-23 10:02:00  # 2 minutos após falha
```

**Solução**: Aguardar próxima tentativa automática ou investigar erro.

---

**5. 🚫 Sem Preferências Configuradas (1% dos casos)**
```python
# Usuário não tem preferências para este tipo de notificação

from vendas_web.models import PreferenciaNotificacao

prefs = PreferenciaNotificacao.objects.filter(
    usuario=usuario,
    tipo_notificacao__codigo='lead_novo'
)

if not prefs.exists():
    print("❌ Usuário não tem preferências configuradas!")
    print("   Notificação não será enviada.")
```

**Solução**: Configurar preferências do usuário no admin ou dashboard.

---

**6. ⚙️ Processamento Manual Necessário (<1% dos casos)**
```python
# Sistema não está processando notificações automaticamente
# Falta configuração de cron job ou Celery

# Verificar se há notificações pendentes antigas
from django.utils import timezone
from datetime import timedelta

antigas = Notificacao.objects.filter(
    status='pendente',
    data_criacao__lt=timezone.now() - timedelta(hours=1)
).count()

print(f"Notificações pendentes há mais de 1 hora: {antigas}")

if antigas > 0:
    print("⚠️ Possível problema no processamento automático!")
```

**Solução**: Configurar processamento automático (ver abaixo).

---

#### ✅ Soluções Práticas

**1. Verificar Motivo Específico de UMA Notificação:**
```python
from vendas_web.models import Notificacao
from django.utils import timezone

notif_id = 123  # ID da notificação
notif = Notificacao.objects.get(id=notif_id)

print(f"📋 Análise da Notificação #{notif_id}")
print(f"Status: {notif.status}")
print(f"Criada em: {notif.data_criacao}")
print(f"Agendada para: {notif.data_agendamento}")
print(f"Tentativas: {notif.tentativas}/{notif.max_tentativas}")

# Verificar se já deveria ter sido enviada
if notif.data_agendamento and notif.data_agendamento <= timezone.now():
    print("❌ JÁ DEVERIA TER SIDO ENVIADA!")
    print("   → Possível problema no processamento automático")
else:
    print(f"✅ Agendada corretamente para: {notif.data_agendamento}")

# Verificar preferências do destinatário
if notif.destinatario:
    from vendas_web.models import PreferenciaNotificacao
    prefs = PreferenciaNotificacao.objects.filter(
        usuario=notif.destinatario,
        tipo_notificacao=notif.tipo
    )
    if prefs.exists():
        pref = prefs.first()
        print(f"\n📱 Preferências do usuário:")
        print(f"   Horário: {pref.horario_inicio} - {pref.horario_fim}")
        print(f"   Dias: {pref.dias_semana}")
    else:
        print("❌ Usuário sem preferências configuradas!")
```

---

**2. Processar Notificações Pendentes Manualmente:**
```bash
# Processar todas pendentes que já podem ser enviadas
python manage.py process_notifications

# Processar com limite
python manage.py process_notifications --batch-size 100

# Ver o que seria processado (dry-run)
python manage.py process_notifications --dry-run

# Forçar retry de notificações que falharam 3x
python manage.py process_notifications --force-retry

# Processar apenas notificações recentes (últimas 24h)
python manage.py process_notifications --max-age-hours 24
```

---

**3. Configurar Processamento Automático (Recomendado):**

**Opção A: Cron Job (Linux)**
```bash
# Editar crontab
crontab -e

# Adicionar linha para processar a cada 5 minutos
*/5 * * * * cd /path/to/project && /path/to/venv/bin/python manage.py process_notifications >> /var/log/notifications.log 2>&1
```

**Opção B: Celery Beat (Recomendado para Produção)**
```python
# settings.py
CELERY_BEAT_SCHEDULE = {
    'process-notifications-every-2-minutes': {
        'task': 'vendas_web.tasks.process_notifications',
        'schedule': 120.0,  # 2 minutos
    },
}

# vendas_web/tasks.py
from celery import shared_task
from vendas_web.services.notification_service import notification_service

@shared_task
def process_notifications():
    """Task do Celery para processar notificações pendentes"""
    notification_service.processar_notificacoes_pendentes()
```

**Opção C: Systemd Timer (Linux)**
```ini
# /etc/systemd/system/process-notifications.service
[Unit]
Description=Processar notificações pendentes

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python manage.py process_notifications

# /etc/systemd/system/process-notifications.timer
[Unit]
Description=Timer para processar notificações

[Timer]
OnBootSec=5min
OnUnitActiveSec=2min

[Install]
WantedBy=timers.target

# Ativar timer
sudo systemctl enable process-notifications.timer
sudo systemctl start process-notifications.timer
```

---

**4. Monitorar Notificações Pendentes:**
```python
from vendas_web.models import Notificacao
from django.utils import timezone
from datetime import timedelta

# Estatísticas rápidas
stats = {
    'total_pendentes': Notificacao.objects.filter(status='pendente').count(),
    'prontas_enviar': Notificacao.objects.filter(
        status='pendente',
        data_agendamento__lte=timezone.now()
    ).count(),
    'aguardando_horario': Notificacao.objects.filter(
        status='pendente',
        data_agendamento__gt=timezone.now()
    ).count(),
    'pendentes_antigas': Notificacao.objects.filter(
        status='pendente',
        data_criacao__lt=timezone.now() - timedelta(hours=2)
    ).count(),
}

print("📊 Status das Notificações Pendentes:")
for key, value in stats.items():
    print(f"  {key}: {value}")

# Se houver muitas pendentes antigas, há problema!
if stats['pendentes_antigas'] > 10:
    print("\n⚠️ ALERTA: Muitas notificações pendentes antigas!")
    print("   → Verificar se processamento automático está funcionando")
```

---

**5. Investigar Notificações "Travadas":**
```python
# Notificações que estão pendentes há muito tempo
from vendas_web.models import Notificacao
from django.utils import timezone
from datetime import timedelta

travadas = Notificacao.objects.filter(
    status='pendente',
    data_criacao__lt=timezone.now() - timedelta(hours=6),
    data_agendamento__lte=timezone.now()
).select_related('tipo', 'canal', 'destinatario')

print(f"🔍 {travadas.count()} notificações 'travadas' encontradas:\n")

for notif in travadas[:5]:  # Mostrar primeiras 5
    print(f"ID: {notif.id}")
    print(f"  Tipo: {notif.tipo.nome}")
    print(f"  Canal: {notif.canal.nome}")
    print(f"  Destinatário: {notif.destinatario}")
    print(f"  Criada: {notif.data_criacao}")
    print(f"  Agendada: {notif.data_agendamento}")
    print(f"  Tentativas: {notif.tentativas}/{notif.max_tentativas}")
    print(f"  Erro: {notif.erro_detalhes or 'N/A'}")
    print()

# Processar manualmente estas específicas
if travadas.exists():
    print("💡 Execute: python manage.py process_notifications")
```

---

#### 📊 Dashboard de Diagnóstico

```python
def diagnosticar_notificacoes_pendentes():
    """Diagnóstico completo de notificações pendentes"""
    from vendas_web.models import Notificacao, PreferenciaNotificacao
    from django.utils import timezone
    from datetime import timedelta
    
    agora = timezone.now()
    
    print("=" * 60)
    print("🔍 DIAGNÓSTICO DE NOTIFICAÇÕES PENDENTES")
    print("=" * 60)
    
    # 1. Total
    total = Notificacao.objects.filter(status='pendente').count()
    print(f"\n📊 Total de notificações pendentes: {total}")
    
    if total == 0:
        print("✅ Nenhuma notificação pendente!")
        return
    
    # 2. Por motivo
    prontas = Notificacao.objects.filter(
        status='pendente',
        data_agendamento__lte=agora
    ).count()
    
    agendadas = Notificacao.objects.filter(
        status='pendente',
        data_agendamento__gt=agora
    ).count()
    
    print(f"\n📦 Classificação:")
    print(f"  ✅ Prontas para enviar: {prontas}")
    print(f"  ⏰ Agendadas para futuro: {agendadas}")
    
    # 3. Por idade
    ultima_hora = Notificacao.objects.filter(
        status='pendente',
        data_criacao__gte=agora - timedelta(hours=1)
    ).count()
    
    ultimo_dia = Notificacao.objects.filter(
        status='pendente',
        data_criacao__gte=agora - timedelta(days=1),
        data_criacao__lt=agora - timedelta(hours=1)
    ).count()
    
    antigas = total - ultima_hora - ultimo_dia
    
    print(f"\n⏱️ Por idade:")
    print(f"  🆕 Última hora: {ultima_hora}")
    print(f"  📅 Último dia: {ultimo_dia}")
    print(f"  🗓️ Mais antigas: {antigas}")
    
    # 4. Alertas
    print(f"\n⚠️ Alertas:")
    
    if prontas > 50:
        print(f"  🔴 {prontas} notificações prontas mas não enviadas!")
        print(f"     → Verificar processamento automático")
    
    if antigas > 10:
        print(f"  🟠 {antigas} notificações pendentes há mais de 1 dia!")
        print(f"     → Pode indicar problema de configuração")
    
    if prontas == 0 and agendadas > 0:
        print(f"  🟢 Todas pendentes estão corretamente agendadas")
    
    # 5. Recomendações
    print(f"\n💡 Recomendações:")
    
    if prontas > 0:
        print(f"  1. Execute: python manage.py process_notifications")
    
    if antigas > 0:
        print(f"  2. Configure processamento automático (cron/celery)")
    
    print(f"  3. Monitore regularmente com este diagnóstico")
    
    print("\n" + "=" * 60)

# Executar diagnóstico
diagnosticar_notificacoes_pendentes()
```

---

#### 🎯 Resumo: Quando se Preocupar

| Situação | Normal? | Ação |
|----------|---------|------|
| Notificações pendentes criadas há < 1h | ✅ Sim | Aguardar horário/processamento |
| Notificações com `data_agendamento` futura | ✅ Sim | Aguardar agendamento |
| Notificações prontas (`data_agendamento` passada) há < 10min | ✅ Sim | Aguardar próximo processamento |
| Notificações prontas há > 30min | ⚠️ Alerta | Verificar processamento automático |
| Muitas notificações (>50) prontas não enviadas | ❌ Problema | Configurar processamento ou executar manual |
| Notificações com 3 tentativas falhadas | ❌ Problema | Investigar erros em `erro_detalhes` |

---

### Problema 2: Erro de conexão com N8N

**Sintomas**:
- Status muda para "falhou"
- Log mostra "Connection timeout" ou "Connection refused"

**Soluções**:

1. **Verificar URL do webhook**:
```python
from django.conf import settings
print(settings.N8N_WEBHOOK_URL)
```

2. **Testar conectividade**:
```bash
curl -X POST https://n8n.aurora.com/webhook/notifications \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

3. **Verificar logs do N8N**:
- Acessar painel do N8N
- Verificar execuções recentes
- Procurar por erros

4. **Aumentar timeout**:
```python
# settings.py
NOTIFICATION_TIMEOUT = 60  # 60 segundos
```

---

### Problema 3: Templates não renderizam

**Sintomas**:
- Variáveis aparecem como `{{variavel}}` na mensagem
- Mensagem sem dados personalizados

**Soluções**:

1. **Verificar dados de contexto**:
```python
dados_contexto = {
    'lead': {
        'nome': 'João Silva'  # Deve estar exatamente assim
    }
}
```

2. **Verificar sintaxe do template**:
```python
# Correto
template = "Olá {{lead.nome}}"

# Incorreto
template = "Olá {{ lead.nome }}"  # Espaços extras
template = "Olá {{lead nome}}"     # Sem ponto
```

3. **Testar renderização**:
```python
from django.template import Template, Context

template_str = "Olá {{lead.nome}}"
template = Template(template_str)
contexto = Context({'lead': {'nome': 'João'}})
resultado = template.render(contexto)
print(resultado)  # Deve mostrar: Olá João
```

---

### Problema 4: Taxa de falha alta

**Sintomas**:
- Muitas notificações com status "falhou"
- Taxa de entrega baixa

**Soluções**:

1. **Analisar erros comuns**:
```python
from django.db.models import Count
from vendas_web.models import Notificacao

erros = Notificacao.objects.filter(
    status='falhou'
).values('erro_detalhes').annotate(
    count=Count('id')
).order_by('-count')

for erro in erros:
    print(f"{erro['count']}: {erro['erro_detalhes']}")
```

2. **Verificar dados de destinatários**:
```python
# Telefones inválidos
notifs_sem_telefone = Notificacao.objects.filter(
    canal__codigo='whatsapp',
    destinatario_telefone__isnull=True
)
print(f"Notificações sem telefone: {notifs_sem_telefone.count()}")
```

3. **Implementar validação mais rigorosa**:
```python
import re

def validar_telefone(telefone):
    # Remove caracteres não numéricos
    telefone = re.sub(r'\D', '', telefone)
    
    # Deve ter 10 ou 11 dígitos
    if len(telefone) not in [10, 11]:
        return False
    
    return True
```

---

### Problema 5: Performance lenta

**Sintomas**:
- Processamento de notificações demora muito
- Timeout em requisições

**Soluções**:

1. **Adicionar índices**:
```sql
CREATE INDEX idx_notificacao_status ON vendas_web_notificacao(status);
CREATE INDEX idx_notificacao_data ON vendas_web_notificacao(data_criacao);
CREATE INDEX idx_notificacao_tipo ON vendas_web_notificacao(tipo_id);
```

2. **Processar em lotes**:
```python
# Processar em lotes de 50
BATCH_SIZE = 50

notificacoes = Notificacao.objects.filter(status='pendente')[:BATCH_SIZE]
for notif in notificacoes:
    processar_notificacao(notif)
```

3. **Usar Celery para processamento assíncrono**:
```python
from celery import shared_task

@shared_task
def processar_notificacao_async(notificacao_id):
    notif = Notificacao.objects.get(id=notificacao_id)
    # Processar...
```

---

### Logs Úteis

**Habilitar logs detalhados** (`settings.py`):

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': '/var/log/aurora/notifications.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'vendas_web.notifications': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

**Visualizar logs**:
```bash
# Logs do Django
tail -f /var/log/aurora/notifications.log

# Logs do Gunicorn
tail -f /var/log/gunicorn/error.log

# Logs do Nginx
tail -f /var/log/nginx/error.log
```

---

## 📈 Melhores Práticas

### 1. Segurança

- ✅ Sempre validar dados de entrada
- ✅ Usar HTTPS em produção
- ✅ Proteger chaves de API (environment variables)
- ✅ Implementar rate limiting
- ✅ Sanitizar templates
- ✅ Validar permissões de usuário

### 2. Performance

- ✅ Processar notificações em background (Celery)
- ✅ Usar cache para templates
- ✅ Implementar índices no banco
- ✅ Processar em lotes
- ✅ Monitorar uso de recursos

### 3. Confiabilidade

- ✅ Implementar retry automático
- ✅ Logar todos os erros
- ✅ Monitorar taxa de falha
- ✅ Ter fallback para canais
- ✅ Validar dados antes de enviar

### 4. Usabilidade

- ✅ Fornecer feedback claro
- ✅ Respeitar preferências do usuário
- ✅ Enviar em horários adequados
- ✅ Personalizar mensagens
- ✅ Ter opção de "não perturbe"

---

## 📞 Suporte

### Contatos

- **Email**: suporte@aurora.consulteplus.com
- **Documentação Online**: https://aurora.consulteplus.com/documentacao/
- **Status do Sistema**: https://status.aurora.consulteplus.com

### Recursos

- **Logs**: Django Admin → Notificações
- **Estatísticas**: Dashboard de Notificações
- **API Docs**: https://aurora.consulteplus.com/api/docs/

---

## 🔮 Roadmap

### Versão 2.1 (Q4 2025)
- [ ] Notificações push para mobile (PWA)
- [ ] Integração com Slack
- [ ] Integração com Microsoft Teams
- [ ] Templates visuais drag-and-drop
- [ ] A/B testing de templates

### Versão 2.2 (Q1 2026)
- [ ] Analytics avançados
- [ ] Machine learning para otimização de horários
- [ ] Notificações por geolocalização
- [ ] Integração com calendário
- [ ] API GraphQL

### Versão 3.0 (Q2 2026)
- [ ] Interface mobile dedicada
- [ ] Webhooks bidirecionais
- [ ] Integração com CRM externo
- [ ] Multi-tenancy
- [ ] Suporte a múltiplos idiomas

---

**Versão**: 2.0.0  
**Data**: 23 de outubro de 2025  
**Autor**: Equipe Megalink  
**Licença**: Proprietário

---

© 2025 Megalink. Todos os direitos reservados.

