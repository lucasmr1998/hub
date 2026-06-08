# Hubtrix N8N API — CRM (Pipelines, Oportunidades, Tarefas)

## Pipelines e estagios

### Listar pipelines com estagios

`GET /api/v1/n8n/crm/pipelines/`

Retorna pipelines do tenant + estagios de cada.

```json
{
  "success": true,
  "pipelines": [
    {
      "id": 3,
      "slug": "matriculas",
      "nome": "Matriculas FATEPI",
      "estagios": [
        { "id": 11, "slug": "novo", "nome": "Novo", "ordem": 1 },
        { "id": 12, "slug": "qualificado", "nome": "Qualificado", "ordem": 2 },
        { "id": 13, "slug": "ganho", "nome": "Ganho", "ordem": 3, "is_final_ganho": true },
        { "id": 14, "slug": "perdido", "nome": "Perdido", "ordem": 4, "is_final_perdido": true }
      ]
    }
  ]
}
```

### Listar estagios (filtros)

`GET /api/v1/n8n/crm/estagios/?pipeline_slug=matriculas`

Sem filtro retorna todos do tenant. Com `pipeline_slug` filtra.

---

## Oportunidades

### Criar oportunidade

`POST /api/v1/n8n/crm/oportunidades/`

Cria ou retorna existente (idempotente por `lead_id`).

```json
{
  "lead_id": 61,
  "pipeline_slug": "matriculas",
  "estagio_slug": "novo",
  "titulo": "Joao - Direito"
}
```

### Resposta

```json
{
  "success": true,
  "oportunidade_id": 58,
  "criada": true,
  "estagio": { "id": 11, "slug": "novo" }
}
```

Se ja existia: `criada=false`. **Nao duplica.**

### Mover oportunidade pra outro estagio

`PUT /api/v1/n8n/crm/oportunidades/58/`

```json
{ "estagio_slug": "qualificado" }
```

### Atribuir responsavel

```json
{ "responsavel_username": "aurora" }
```

(Ou `responsavel_id: <user_id>`)

### Buscar por lead

`GET /api/v1/n8n/crm/oportunidades/buscar/?lead_id=61`

### Buscar por telefone

`GET /api/v1/n8n/crm/oportunidades/buscar/?telefone=5586999`

Retorna primeira oportunidade ativa (nao em estagio final) do lead com aquele telefone.

---

## Encerrar oportunidade com motivo (bot/automacao)

`POST /api/public/n8n/crm/oportunidade/<pk>/encerrar-com-motivo/`

Move pra estagio `is_final_perdido` e classifica motivo via OpenAI gpt-4o-mini baseado na ultima mensagem do cliente.

### Body

```json
{
  "ultima_mensagem_cliente": "muito caro, fica pra proxima",
  "estagio_perdida_id": 42
}
```

`estagio_perdida_id` opcional — sem ele, pega primeiro `is_final_perdido` ativo do tenant.

### Resposta

```json
{
  "status": "success",
  "motivo_classificado": "Preco",
  "motivo_id": 3,
  "confidence": 0.86,
  "oportunidade_id": 58,
  "estagio": "Perdida"
}
```

### Comportamento

- Classifica entre `MotivoPerda` ativos do tenant
- Se `confidence < 0.5`: cai em "Outro" + observacao livre
- Se LLM falhar (sem chave / erro API): igual — cai em "Outro" + msg crua
- `motivo_perda_origem='bot'` em 100% das escritas (permite rollback seletivo)
- **Idempotente**: se ja encerrada com motivo, retorna o atual sem reclassificar

### Erros

- `400` — `ultima_mensagem_cliente` ausente / tenant sem estagio `is_final_perdido`
- `401` — token invalido
- `404` — oportunidade nao no tenant

---

## Tarefas

### Criar tarefa

`POST /api/v1/n8n/crm/tarefas/`

```json
{
  "lead_id": 61,
  "titulo": "Ligar para Joao sobre Direito",
  "tipo": "ligacao",
  "prioridade": "alta",
  "data_prevista": "2026-06-10"
}
```

**Tipos validos:** `ligacao`, `whatsapp`, `email`, `visita`, `followup`, `proposta`, `instalacao`, `suporte`, `outro`.

**Prioridades:** `baixa`, `normal`, `alta`, `urgente`.

### Atualizar / concluir

`PUT /api/v1/n8n/crm/tarefas/<id>/`

```json
{
  "status": "concluida",
  "resultado": "Lead interessado em Direito noturno"
}
```

**Status validos:** `pendente`, `em_andamento`, `concluida`, `cancelada`.

---

## Fluxo tipico (Vero)

```
1. Lead criado (POST /leads/)
2. Oportunidade criada no pipeline padrao (POST /crm/oportunidades/)
3. Tarefa "primeiro contato" criada (POST /crm/tarefas/)
4. Agente IA conversa, atualiza oportunidade (estagio = qualificado)
5. Se cliente diz nao -> POST /crm/oportunidade/<id>/encerrar-com-motivo/
   (move pra Perdida + classifica motivo automaticamente)
```

## Engine de automacao do pipeline (server-side)

Independente desses endpoints, o Hubtrix tem **engine de regras** que dispara acoes quando oportunidade muda de estagio ou bate condicoes. Documentado em [../../../modulos/comercial/crm/automacoes-pipeline.md](../../../modulos/comercial/crm/automacoes-pipeline.md).

Ex.: a regra #19 da Nuvyon ("Docs validados -> Gerar contrato HubSoft") dispara automaticamente quando todas imagens do lead viram `documentos_validos`, sem precisar de POST externo. Bot externo nao precisa orquestrar contrato — so atualizar oportunidade.
