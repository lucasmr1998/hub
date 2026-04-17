# 16. APIs para Agentes e N8N

**Ultima atualizacao:** 07/04/2026
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
