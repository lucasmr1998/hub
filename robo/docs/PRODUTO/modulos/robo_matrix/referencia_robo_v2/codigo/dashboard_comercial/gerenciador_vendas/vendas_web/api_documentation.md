# Documentação de APIs — Consultas GET

> Foco nos endpoints GET dos modelos **LeadProspecto**, **ImagemLeadProspecto**, **Prospecto** e **HistoricoContato**.

---

## Índice

1. [GET /api/consultar/leads/](#1-get-apiconsultarleads)
2. [GET /api/consultar/historicos/](#2-get-apiconsultarhistoricos)
3. [GET /api/historico-contatos/](#3-get-apihistorico-contatos)
4. [GET /api/leads/imagens/listar/](#4-get-apileadsimageslistar)
5. [GET /api/leads/imagens/por-cliente/](#5-get-apileadsimagespor-cliente)
6. [GET /api/dashboard/leads/](#6-get-apidashboardleads)
7. [GET /api/dashboard/prospectos/](#7-get-apidashboardprospectos)
8. [GET /api/dashboard/historico/](#8-get-apidashboardhistorico)
9. [GET /api/dashboard/contato/<telefone>/historico/](#9-get-apidashboardcontatotelefoneshistorico)

---

## Informações Gerais

- **Base URL:** `https://seudominio.com`
- **Formato de datas:** `YYYY-MM-DD` nos query params
- **Paginação:** parâmetros `page` e `per_page` (máx: 100)
- **Ordenação:** prefixo `-` para decrescente. Ex: `-data_cadastro`
- **Booleanos em query params:** `true` ou `false` (string)

---

## 1. GET /api/consultar/leads/

Consulta leads do modelo **LeadProspecto** com filtros e paginação.

**Autenticação:** Não obrigatória

### Parâmetros de Query

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `page` | integer | Não | Página (padrão: `1`) |
| `per_page` | integer | Não | Itens por página (padrão: `20`, máx: `100`) |
| `id` | integer | Não | Busca por ID específico — ignora todos os outros filtros |
| `search` | string | Não | Busca em: `nome_razaosocial`, `email`, `telefone`, `empresa`, `cpf_cnpj`, `id_hubsoft` |
| `origem` | string | Não | Filtro exato por `origem`. Valores: `site`, `facebook`, `instagram`, `google`, `whatsapp`, `indicacao`, `telefone`, `email`, `outros` |
| `status_api` | string | Não | Filtro exato por `status_api`. Valores: `pendente`, `processado`, `erro`, `sucesso`, `rejeitado`, `aguardando_retry`, `processamento_manual` |
| `ativo` | boolean | Não | `true` ou `false` |
| `data_inicio` | date | Não | Filtro `data_cadastro >= valor` |
| `data_fim` | date | Não | Filtro `data_cadastro <= valor` |
| `ordering` | string | Não | Campos permitidos: `id`, `data_cadastro`, `data_atualizacao`, `nome_razaosocial`, `valor` (padrão: `-data_cadastro`) |

### Exemplo de Requisição

```bash
curl "https://seudominio.com/api/consultar/leads/?status_api=pendente&origem=whatsapp&page=1&per_page=50"
```

### Exemplo N8N (HTTP Request Node)

```json
{
  "method": "GET",
  "url": "https://seudominio.com/api/consultar/leads/",
  "qs": {
    "status_api": "pendente",
    "origem": "whatsapp",
    "page": 1,
    "per_page": 50
  }
}
```

### Resposta de Sucesso (200)

```json
{
  "results": [
    {
      "id": 123,
      "nome_razaosocial": "João Silva",
      "email": "joao@example.com",
      "telefone": "11999999999",
      "valor": "99.90",
      "empresa": "Empresa X",
      "origem": "whatsapp",
      "status_api": "pendente",
      "ativo": true,
      "cpf_cnpj": "123.456.789-00",
      "rg": null,
      "endereco": null,
      "rua": "Av. Paulista",
      "numero_residencia": "1000",
      "bairro": "Bela Vista",
      "cidade": "São Paulo",
      "estado": "SP",
      "cep": "01310100",
      "ponto_referencia": null,
      "canal_entrada": "whatsapp",
      "tipo_entrada": "contato_whatsapp",
      "score_qualificacao": 7,
      "tentativas_contato": 1,
      "data_ultimo_contato": "2026-03-13T10:00:00Z",
      "data_cadastro": "2026-03-13T09:00:00Z",
      "data_atualizacao": "2026-03-13T10:00:00Z",
      "id_hubsoft": null,
      "id_origem": null,
      "observacoes": null,
      "ativo": true,
      "documentacao_completa": false,
      "documentacao_validada": false,
      "contrato_aceito": false,
      "valor_formatado": "R$ 99,90",
      "origem_display": "WhatsApp",
      "status_api_display": "Pendente"
    }
  ],
  "total": 150,
  "page": 1,
  "per_page": 50,
  "pages": 3,
  "ordering": "-data_cadastro"
}
```

### Erros Possíveis

| Código | Descrição |
|--------|-----------|
| 405 | Método HTTP não permitido (use GET) |
| 500 | Erro interno do servidor |

---

## 2. GET /api/consultar/historicos/

Consulta registros do modelo **HistoricoContato** com filtros e paginação.

**Autenticação:** Não obrigatória

### Parâmetros de Query

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `page` | integer | Não | Página (padrão: `1`) |
| `per_page` | integer | Não | Itens por página (padrão: `20`, máx: `100`) |
| `id` | integer | Não | Busca por ID específico — ignora todos os outros filtros |
| `telefone` | string | Não | Filtro parcial em `telefone` (contém) |
| `lead_id` | integer | Não | Filtro exato por `lead_id` |
| `status` | string | Não | Filtro exato por `status` (ver valores abaixo) |
| `sucesso` | boolean | Não | `true` ou `false` |
| `converteu_lead` | boolean | Não | `true` ou `false` |
| `converteu_venda` | boolean | Não | `true` ou `false` |
| `data_inicio` | date | Não | Filtro `data_hora_contato >= valor` |
| `data_fim` | date | Não | Filtro `data_hora_contato <= valor` |
| `ordering` | string | Não | Campos permitidos: `id`, `data_hora_contato`, `telefone`, `status` (padrão: `-data_hora_contato`) |

### Valores válidos para `status`

| Valor | Descrição |
|-------|-----------|
| `fluxo_inicializado` | Fluxo Inicializado |
| `fluxo_finalizado` | Fluxo Finalizado |
| `transferido_humano` | Transferido para Humano |
| `chamada_perdida` | Chamada Perdida |
| `ocupado` | Ocupado |
| `desligou` | Desligou |
| `nao_atendeu` | Não Atendeu |
| `abandonou_fluxo` | Abandonou o Fluxo |
| `numero_invalido` | Número Inválido |
| `erro_sistema` | Erro do Sistema |
| `convertido_lead` | Convertido em Lead |
| `venda_confirmada` | Venda Confirmada |
| `venda_rejeitada` | Venda Rejeitada |
| `venda_sem_viabilidade` | Venda Sem Viabilidade |
| `cliente_desistiu` | Cliente Desistiu |
| `aguardando_validacao` | Aguardando Validação |
| `followup_agendado` | Follow-up Agendado |
| `nao_qualificado` | Não Qualificado |

### Exemplo de Requisição

```bash
curl "https://seudominio.com/api/consultar/historicos/?telefone=11999&converteu_lead=true&data_inicio=2026-03-01"
```

### Exemplo N8N

```json
{
  "method": "GET",
  "url": "https://seudominio.com/api/consultar/historicos/",
  "qs": {
    "telefone": "{{ $json.telefone }}",
    "converteu_lead": "true"
  }
}
```

### Resposta de Sucesso (200)

```json
{
  "results": [
    {
      "id": 5678,
      "telefone": "11999999999",
      "status": "fluxo_finalizado",
      "sucesso": true,
      "converteu_lead": true,
      "converteu_venda": false,
      "data_hora_contato": "2026-03-13T09:30:00Z",
      "data_conversao_lead": "2026-03-13T09:45:00Z",
      "data_conversao_venda": null,
      "valor_venda": null,
      "origem_contato": "whatsapp",
      "duracao_segundos": 185,
      "nome_contato": "João Silva",
      "transcricao": null,
      "observacoes": null,
      "protocolo_atendimento": "PROT-2026-001",
      "codigo_atendimento": "ATD-9999",
      "id_conta": null,
      "numero_conta": null,
      "ultima_mensagem": "Obrigado pelo atendimento!",
      "status_display": "Fluxo Finalizado",
      "duracao_formatada": "3m 5s",
      "valor_venda_formatado": null,
      "lead_info": {
        "id": 123,
        "nome_razaosocial": "João Silva",
        "telefone": "11999999999",
        "empresa": null
      }
    }
  ],
  "total": 42,
  "page": 1,
  "per_page": 20,
  "pages": 3,
  "ordering": "-data_hora_contato"
}
```

### Erros Possíveis

| Código | Descrição |
|--------|-----------|
| 405 | Método HTTP não permitido |
| 500 | Erro interno do servidor |

---

## 3. GET /api/historico-contatos/

Busca histórico de contatos de um lead específico por `lead_id`, `prospecto_id` ou `telefone`.  
Retorna no máximo **50 registros** ordenados do mais recente para o mais antigo.

**Autenticação:** Não obrigatória

### Parâmetros de Query (ao menos um obrigatório)

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `lead_id` | integer | Condicional | Busca pelo ID do LeadProspecto e também por todos os registros com o mesmo telefone |
| `prospecto_id` | integer | Condicional | Busca via o lead associado ao Prospecto |
| `telefone` | string | Condicional | Busca por telefone exato |

### Exemplo de Requisição

```bash
# Por lead_id
curl "https://seudominio.com/api/historico-contatos/?lead_id=123"

# Por telefone
curl "https://seudominio.com/api/historico-contatos/?telefone=11999999999"
```

### Exemplo N8N

```json
{
  "method": "GET",
  "url": "https://seudominio.com/api/historico-contatos/",
  "qs": {
    "telefone": "{{ $json.telefone }}"
  }
}
```

### Resposta de Sucesso (200)

```json
{
  "historicos": [
    {
      "id": 5678,
      "telefone": "11999999999",
      "status": "fluxo_finalizado",
      "status_display": "Fluxo Finalizado",
      "status_categoria": "sucesso",
      "data_hora_contato": "2026-03-13T09:30:00Z",
      "data_hora_contato_formatada": "13/03/2026 09:30",
      "sucesso": true,
      "converteu_lead": true,
      "converteu_venda": false,
      "valor_venda": null,
      "duracao_segundos": 185,
      "duracao_formatada": "3m 5s",
      "origem_contato": "whatsapp",
      "nome_contato": "João Silva",
      "transcricao": null,
      "observacoes": null,
      "protocolo_atendimento": "PROT-2026-001",
      "codigo_atendimento": "ATD-9999",
      "lead": {
        "id": 123,
        "nome": "João Silva",
        "nome_razaosocial": "João Silva",
        "email": "joao@example.com",
        "telefone": "11999999999",
        "empresa": "",
        "cpf_cnpj": "123.456.789-00",
        "rg": "",
        "endereco": "",
        "rua": "Av. Paulista",
        "numero_residencia": "1000",
        "bairro": "Bela Vista",
        "cidade": "São Paulo",
        "estado": "SP",
        "cep": "01310100",
        "ponto_referencia": "",
        "valor": "R$ 99,90"
      }
    }
  ],
  "total": 3
}
```

### Erros Possíveis

| Código | Descrição |
|--------|-----------|
| 400 | Nenhum parâmetro fornecido (`lead_id`, `prospecto_id` ou `telefone`) |
| 404 | Lead ou Prospecto não encontrado |
| 500 | Erro interno |

---

## 4. GET /api/leads/imagens/listar/

Lista as imagens vinculadas a um **LeadProspecto** (modelo `ImagemLeadProspecto`).

**Autenticação:** Não obrigatória (`@csrf_exempt`)

### Parâmetros de Query

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `lead_id` | integer | **Sim** | ID do LeadProspecto |

### Exemplo de Requisição

```bash
curl "https://seudominio.com/api/leads/imagens/listar/?lead_id=123"
```

### Exemplo N8N

```json
{
  "method": "GET",
  "url": "https://seudominio.com/api/leads/imagens/listar/",
  "qs": {
    "lead_id": "{{ $json.lead_id }}"
  }
}
```

### Resposta de Sucesso (200)

```json
{
  "lead_id": 123,
  "total": 2,
  "imagens": [
    {
      "id": 456,
      "link_url": "https://example.com/rg_frente.jpg",
      "descricao": "RG Frente",
      "data_criacao": "2026-03-13T09:00:00Z"
    },
    {
      "id": 457,
      "link_url": "https://example.com/rg_verso.jpg",
      "descricao": "RG Verso",
      "data_criacao": "2026-03-13T09:01:00Z"
    }
  ]
}
```

### Erros Possíveis

| Código | Descrição |
|--------|-----------|
| 400 | Parâmetro `lead_id` não informado |

---

## 5. GET /api/leads/imagens/por-cliente/

Busca imagens de lead a partir do ID de um cliente no **Hubsoft** (integração externa).

**Autenticação:** Requer login (`@login_required`)

### Parâmetros de Query

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `cliente_hubsoft_id` | integer | **Sim** | ID do ClienteHubsoft |

### Exemplo de Requisição

```bash
curl "https://seudominio.com/api/leads/imagens/por-cliente/?cliente_hubsoft_id=789" \
  -H "Cookie: sessionid=SEU_SESSION_ID"
```

### Resposta de Sucesso (200)

```json
{
  "success": true,
  "lead": {
    "id": 123,
    "nome_razaosocial": "João Silva",
    "telefone": "11999999999"
  },
  "imagens": [
    {
      "id": 456,
      "link_url": "https://example.com/rg_frente.jpg",
      "descricao": "RG Frente",
      "status_validacao": "pendente",
      "data_criacao": "2026-03-13T09:00:00Z"
    }
  ],
  "total": 1
}
```

### Erros Possíveis

| Código | Descrição |
|--------|-----------|
| 400 | Parâmetro `cliente_hubsoft_id` não informado |
| 404 | Cliente Hubsoft não encontrado |

---

## 6. GET /api/dashboard/leads/

Lista leads para o dashboard com filtros e paginação. Retorna os mesmos dados do modelo **LeadProspecto** otimizados para exibição na tela.

**Autenticação:** Não obrigatória

### Parâmetros de Query

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `page` | integer | Não | Página (padrão: `1`) |
| `search` | string | Não | Busca geral por nome, telefone, email |
| `origem` | string | Não | Filtro por `origem` |
| `status` | string | Não | Filtro por `status_api` |
| `ativo` | boolean | Não | `true` ou `false` |
| `valor` | string | Não | `"sim"` (valor > 0) ou `"nao"` (sem valor) |
| `data_inicio` | date | Não | Filtro `data_cadastro >=` |
| `data_fim` | date | Não | Filtro `data_cadastro <=` |
| `id` | integer | Não | Retorna detalhes de um lead específico (modal) |

### Exemplo de Requisição

```bash
curl "https://seudominio.com/api/dashboard/leads/?origem=whatsapp&ativo=true&page=2"
```

### Resposta de Sucesso (200)

```json
{
  "leads": [...],
  "total": 150,
  "page": 2,
  "per_page": 20,
  "total_pages": 8
}
```

---

## 7. GET /api/dashboard/prospectos/

Lista prospectos do modelo **Prospecto** para o dashboard.

**Autenticação:** Não obrigatória

### Parâmetros de Query

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `page` | integer | Não | Página (padrão: `1`) |
| `search` | string | Não | Busca textual |
| `status` | string | Não | Filtro por status. Valores: `pendente`, `processando`, `processado`, `erro`, `finalizado`, `cancelado`, `aguardando_validacao`, `validacao_aprovada`, `validacao_rejeitada` |
| `prioridade` | string | Não | Filtro por prioridade (`1` a `5`) |
| `id` | integer | Não | Detalhe de um prospecto específico |

### Exemplo de Requisição

```bash
curl "https://seudominio.com/api/dashboard/prospectos/?status=aguardando_validacao"
```

### Resposta de Sucesso (200)

```json
{
  "prospectos": [
    {
      "id": 789,
      "nome_prospecto": "João Silva - Internet 200MB",
      "status": "aguardando_validacao",
      "prioridade": 3,
      "score_conversao": "75.00",
      "data_criacao": "2026-03-13T09:00:00Z",
      "lead": {
        "id": 123,
        "nome_razaosocial": "João Silva",
        "telefone": "11999999999"
      }
    }
  ],
  "total": 20,
  "page": 1,
  "per_page": 20,
  "total_pages": 1
}
```

---

## 8. GET /api/dashboard/historico/

Lista registros do modelo **HistoricoContato** para o dashboard.

**Autenticação:** Não obrigatória

### Parâmetros de Query

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `page` | integer | Não | Página (padrão: `1`) |
| `search` | string | Não | Busca por telefone, nome |
| `status` | string | Não | Filtro por `status` (ver tabela de valores na seção 2) |
| `sucesso` | boolean | Não | `true` ou `false` |
| `data_inicio` | date | Não | Filtro `data_hora_contato >=` |
| `data_fim` | date | Não | Filtro `data_hora_contato <=` |
| `id` | integer | Não | Detalhe de um registro específico |

### Exemplo de Requisição

```bash
curl "https://seudominio.com/api/dashboard/historico/?sucesso=true&data_inicio=2026-03-01"
```

### Resposta de Sucesso (200)

```json
{
  "historicos": [...],
  "total": 380,
  "page": 1,
  "per_page": 20,
  "total_pages": 19
}
```

---

## 9. GET /api/dashboard/contato/<telefone>/historico/

Retorna o histórico completo de um telefone específico — todos os registros do modelo **HistoricoContato** vinculados a esse número.

**Autenticação:** Não obrigatória

### Parâmetros de URL

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `telefone` | string | **Sim** | Número de telefone (ex: `11999999999`) |

### Exemplo de Requisição

```bash
curl "https://seudominio.com/api/dashboard/contato/11999999999/historico/"
```

### Exemplo N8N

```json
{
  "method": "GET",
  "url": "https://seudominio.com/api/dashboard/contato/{{ $json.telefone }}/historico/"
}
```

### Resposta de Sucesso (200)

```json
{
  "telefone": "11999999999",
  "historico": [
    {
      "id": 5678,
      "status": "fluxo_finalizado",
      "sucesso": true,
      "converteu_lead": true,
      "data_hora_contato": "2026-03-13T09:30:00Z",
      "duracao_segundos": 185,
      "origem_contato": "whatsapp"
    }
  ],
  "total": 3
}
```

### Erros Possíveis

| Código | Descrição |
|--------|-----------|
| 500 | Erro interno |

---

## Resumo dos Endpoints GET

| Endpoint | Modelo | Auth | Paginação | Filtro Principal |
|----------|--------|------|-----------|-----------------|
| `GET /api/consultar/leads/` | LeadProspecto | Não | Sim | `search`, `origem`, `status_api`, `ativo` |
| `GET /api/consultar/historicos/` | HistoricoContato | Não | Sim | `telefone`, `lead_id`, `status`, `sucesso` |
| `GET /api/historico-contatos/` | HistoricoContato | Não | Não (máx 50) | `lead_id`, `prospecto_id`, `telefone` |
| `GET /api/leads/imagens/listar/` | ImagemLeadProspecto | Não | Não | `lead_id` |
| `GET /api/leads/imagens/por-cliente/` | ImagemLeadProspecto | **Sim** | Não | `cliente_hubsoft_id` |
| `GET /api/dashboard/leads/` | LeadProspecto | Não | Sim | `search`, `origem`, `status`, `ativo`, `valor` |
| `GET /api/dashboard/prospectos/` | Prospecto | Não | Sim | `search`, `status`, `prioridade` |
| `GET /api/dashboard/historico/` | HistoricoContato | Não | Sim | `search`, `status`, `sucesso` |
| `GET /api/dashboard/contato/<telefone>/historico/` | HistoricoContato | Não | Não | Telefone na URL |
