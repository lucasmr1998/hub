# APIs para Integração N8N - Fluxos de Atendimento

Este documento descreve as APIs específicas criadas para permitir que o N8N gerencie completamente os fluxos de atendimento.

## 🚀 Fluxo Básico de Uso

### 1. Buscar ou Criar Lead
```http
GET /api/n8n/lead/buscar/?telefone=5511999887766
```

Se não existir, criar:
```http
POST /api/n8n/lead/criar/
Content-Type: application/json

{
    "nome_razaosocial": "João Silva",
    "telefone": "5511999887766",
    "email": "joao@email.com",
    "origem": "whatsapp",
    "canal_entrada": "whatsapp",
    "tipo_entrada": "contato_whatsapp",
    "observacoes": "Contato via WhatsApp"
}
```

### 2. Listar Fluxos Disponíveis
```http
GET /api/n8n/fluxos/?tipo=vendas
```

### 3. Iniciar Atendimento
```http
POST /api/n8n/atendimento/iniciar/
Content-Type: application/json

{
    "lead_id": 123,
    "fluxo_id": 1,
    "ip_origem": "192.168.1.100",
    "user_agent": "N8N-Bot/1.0",
    "dispositivo": "whatsapp",
    "observacoes": "Atendimento iniciado via N8N"
}
```

### 4. Consultar Status do Atendimento
```http
GET /api/n8n/atendimento/{atendimento_id}/consultar/
```

### 5. Registrar Resposta de Questão
```http
POST /api/n8n/atendimento/{atendimento_id}/responder/
Content-Type: application/json

{
    "resposta": "João Silva",
    "indice_questao": 1,
    "validar": true,
    "criar_registro_detalhado": true,
    "ip_origem": "192.168.1.100",
    "user_agent": "N8N-Bot/1.0"
}
```

### 6. Avançar para Próxima Questão
```http
POST /api/n8n/atendimento/{atendimento_id}/avancar/
```

### 7. Finalizar Atendimento
```http
POST /api/n8n/atendimento/{atendimento_id}/finalizar/
Content-Type: application/json

{
    "sucesso": true,
    "observacoes": "Atendimento finalizado com sucesso"
}
```

## 📋 APIs Detalhadas

### 🔍 Buscar Lead por Telefone
**Endpoint:** `GET /api/n8n/lead/buscar/`

**Parâmetros:**
- `telefone` (required): Número do telefone

**Resposta:**
```json
{
    "encontrado": true,
    "total_encontrados": 1,
    "leads": [
        {
            "id": 123,
            "nome": "João Silva",
            "email": "joao@email.com",
            "telefone": "5511999887766",
            "origem": "whatsapp",
            "status_api": "pendente",
            "data_cadastro": "2024-01-15T10:30:00Z",
            "score_qualificacao": 7,
            "total_contatos": 3,
            "total_atendimentos": 1
        }
    ]
}
```

### ➕ Criar Lead
**Endpoint:** `POST /api/n8n/lead/criar/`

**Body:**
```json
{
    "nome_razaosocial": "João Silva",
    "telefone": "5511999887766",
    "email": "joao@email.com",
    "origem": "whatsapp",
    "canal_entrada": "whatsapp",
    "tipo_entrada": "contato_whatsapp",
    "cpf_cnpj": "12345678901",
    "endereco": "Rua das Flores, 123",
    "cidade": "São Paulo",
    "estado": "SP",
    "cep": "01234-567",
    "observacoes": "Cliente interessado em plano premium",
    "criar_historico_contato": true
}
```

**Resposta:**
```json
{
    "lead_existente": false,
    "lead_criado": true,
    "lead_id": 124,
    "lead": {
        "id": 124,
        "nome": "João Silva",
        "email": "joao@email.com",
        "telefone": "5511999887766",
        "origem": "whatsapp",
        "status_api": "pendente",
        "data_cadastro": "2024-01-15T11:00:00Z"
    }
}
```

### 📋 Listar Fluxos Ativos
**Endpoint:** `GET /api/n8n/fluxos/`

**Parâmetros opcionais:**
- `tipo`: Filtrar por tipo de fluxo (vendas, qualificacao, suporte, etc.)

**Resposta:**
```json
{
    "fluxos": [
        {
            "id": 1,
            "nome": "Qualificação de Lead - Internet",
            "descricao": "Fluxo para qualificar leads interessados em planos de internet",
            "tipo_fluxo": "qualificacao",
            "total_questoes": 5,
            "max_tentativas": 3,
            "tempo_limite_minutos": 15,
            "permite_pular_questoes": false,
            "estatisticas": {
                "total_atendimentos": 150,
                "atendimentos_completados": 120,
                "taxa_completacao": 80.0,
                "tempo_medio_segundos": 180.5
            }
        }
    ],
    "total": 1
}
```

### 🚀 Iniciar Atendimento
**Endpoint:** `POST /api/n8n/atendimento/iniciar/`

**Body:**
```json
{
    "lead_id": 123,
    "fluxo_id": 1,
    "ip_origem": "192.168.1.100",
    "user_agent": "N8N-Bot/1.0",
    "dispositivo": "whatsapp",
    "observacoes": "Atendimento iniciado via N8N"
}
```

**Resposta:**
```json
{
    "atendimento_id": 456,
    "lead_id": 123,
    "fluxo_id": 1,
    "status": "iniciado",
    "questao_atual": 1,
    "total_questoes": 5,
    "progresso_percentual": 0.0,
    "primeira_questao": {
        "id": 10,
        "indice": 1,
        "titulo": "Qual é o seu nome completo?",
        "descricao": "Por favor, informe seu nome completo",
        "tipo_questao": "texto",
        "tipo_validacao": "obrigatoria",
        "tamanho_minimo": 3,
        "tamanho_maximo": 100
    },
    "data_inicio": "2024-01-15T11:00:00Z"
}
```

### 📞 Consultar Atendimento
**Endpoint:** `GET /api/n8n/atendimento/{atendimento_id}/consultar/`

**Resposta:**
```json
{
    "atendimento_id": 456,
    "lead_id": 123,
    "lead_nome": "João Silva",
    "lead_telefone": "5511999887766",
    "fluxo_id": 1,
    "fluxo_nome": "Qualificação de Lead - Internet",
    "status": "em_andamento",
    "questao_atual": 2,
    "total_questoes": 5,
    "questoes_respondidas": 1,
    "progresso_percentual": 20.0,
    "questao_atual_obj": {
        "id": 11,
        "indice": 2,
        "titulo": "Qual é o seu email?",
        "tipo_questao": "email",
        "tipo_validacao": "obrigatoria"
    },
    "proxima_questao": {
        "id": 12,
        "indice": 3,
        "titulo": "Qual velocidade de internet você precisa?"
    },
    "pode_avancar": false,
    "pode_voltar": true,
    "data_inicio": "2024-01-15T11:00:00Z",
    "data_ultima_atividade": "2024-01-15T11:05:00Z",
    "respostas": {
        "1": {
            "resposta": "João Silva",
            "data_resposta": "2024-01-15T11:02:00Z",
            "valida": true
        }
    }
}
```

### ✍️ Registrar Resposta
**Endpoint:** `POST /api/n8n/atendimento/{atendimento_id}/responder/`

**Body:**
```json
{
    "resposta": "joao.silva@email.com",
    "indice_questao": 2,
    "validar": true,
    "criar_registro_detalhado": true,
    "ip_origem": "192.168.1.100",
    "user_agent": "N8N-Bot/1.0",
    "dados_extras": {
        "canal": "whatsapp",
        "mensagem_id": "wamid.123456"
    }
}
```

**Resposta:**
```json
{
    "sucesso": true,
    "mensagem": "Resposta registrada com sucesso",
    "atendimento_id": 456,
    "questao_respondida": 2,
    "questao_atual": 2,
    "questoes_respondidas": 2,
    "progresso_percentual": 40.0,
    "questao_atual_obj": {
        "id": 11,
        "indice": 2,
        "titulo": "Qual é o seu email?"
    },
    "proxima_questao": {
        "id": 12,
        "indice": 3,
        "titulo": "Qual velocidade de internet você precisa?"
    },
    "pode_avancar": true,
    "atendimento_status": "em_andamento"
}
```

### ⏭️ Avançar Questão
**Endpoint:** `POST /api/n8n/atendimento/{atendimento_id}/avancar/`

**Resposta:**
```json
{
    "sucesso": true,
    "atendimento_id": 456,
    "questao_atual": 3,
    "questoes_respondidas": 2,
    "progresso_percentual": 40.0,
    "atendimento_status": "em_andamento",
    "proxima_questao": {
        "id": 12,
        "indice": 3,
        "titulo": "Qual velocidade de internet você precisa?",
        "tipo_questao": "select",
        "opcoes_resposta": ["100MB", "200MB", "500MB", "1GB"]
    },
    "finalizado": false
}
```

### ✅ Finalizar Atendimento
**Endpoint:** `POST /api/n8n/atendimento/{atendimento_id}/finalizar/`

**Body:**
```json
{
    "sucesso": true,
    "observacoes": "Cliente qualificado com sucesso. Interessado em plano 500MB."
}
```

**Resposta:**
```json
{
    "sucesso": true,
    "atendimento_id": 456,
    "status": "completado",
    "data_conclusao": "2024-01-15T11:15:00Z",
    "tempo_total": 900,
    "tempo_formatado": "15m 0s",
    "score_qualificacao": 8,
    "questoes_respondidas": 5,
    "total_questoes": 5,
    "progresso_percentual": 100.0
}
```

### ⏸️ Pausar Atendimento
**Endpoint:** `POST /api/n8n/atendimento/{atendimento_id}/pausar/`

**Body:**
```json
{
    "motivo_pausa": "Cliente solicitou pausa para verificar informações"
}
```

### ▶️ Retomar Atendimento
**Endpoint:** `POST /api/n8n/atendimento/{atendimento_id}/retomar/`

**Body:**
```json
{
    "observacoes_retomada": "Cliente retornou com as informações"
}
```

### 🔍 Obter Questão Específica
**Endpoint:** `GET /api/n8n/fluxo/{fluxo_id}/questao/{indice_questao}/`

**Resposta:**
```json
{
    "id": 12,
    "indice": 3,
    "titulo": "Qual velocidade de internet você precisa?",
    "descricao": "Selecione a velocidade que melhor atende suas necessidades",
    "tipo_questao": "select",
    "tipo_validacao": "obrigatoria",
    "opcoes_resposta": ["100MB", "200MB", "500MB", "1GB"],
    "permite_voltar": true,
    "permite_editar": true
}
```

## 🔧 Controle de Questões Respondidas

O sistema agora gerencia automaticamente a contabilização de questões respondidas:

1. **Contagem Automática**: O campo `questoes_respondidas` é atualizado automaticamente quando uma resposta é registrada
2. **Evita Duplicação**: Se uma questão já foi respondida, o contador não é incrementado novamente
3. **Recálculo Inteligente**: O sistema recalcula o total baseado nas respostas válidas armazenadas
4. **Progresso Preciso**: O percentual de progresso é calculado corretamente baseado nas questões efetivamente respondidas

## 🛡️ Tratamento de Erros

Todas as APIs retornam códigos de status HTTP apropriados:

- `200`: Sucesso
- `201`: Criado com sucesso
- `400`: Erro de validação/dados inválidos
- `404`: Recurso não encontrado
- `500`: Erro interno do servidor

Exemplo de resposta de erro:
```json
{
    "error": "Campo telefone é obrigatório"
}
```

## 📝 Logs

Todas as operações são registradas no sistema de logs (`LogSistema`) para auditoria e debugging.

## 🔄 Fluxo Completo de Exemplo

1. **Buscar Lead**: `GET /api/n8n/lead/buscar/?telefone=5511999887766`
2. **Criar se não existir**: `POST /api/n8n/lead/criar/`
3. **Listar fluxos**: `GET /api/n8n/fluxos/?tipo=vendas`
4. **Iniciar atendimento**: `POST /api/n8n/atendimento/iniciar/`
5. **Loop para cada questão**:
   - Consultar status: `GET /api/n8n/atendimento/{id}/consultar/`
   - Registrar resposta: `POST /api/n8n/atendimento/{id}/responder/`
   - Avançar questão: `POST /api/n8n/atendimento/{id}/avancar/`
6. **Finalizar**: `POST /api/n8n/atendimento/{id}/finalizar/`

Este conjunto de APIs permite que o N8N tenha controle completo sobre todo o fluxo de atendimento, desde a criação do lead até a finalização do atendimento, com total rastreabilidade e controle de estado.
