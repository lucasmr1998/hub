### APIs de Consulta (GET) — Leads e Histórico de Contato

Estas APIs permitem consultar `LeadProspecto` e `HistoricoContato` com filtros, paginação e ordenação.

### Autenticação

- **Obrigatória**: o projeto usa um middleware que exige usuário autenticado.
- Faça login em `/admin/login/` antes de chamar as APIs (cookies de sessão do Django).
- Em chamadas via `curl`/Postman, inclua o cookie de sessão: `Cookie: sessionid=SEU_SESSION_ID`.

### Convenções

- Datas: `YYYY-MM-DD` (ex.: `2025-01-31`).
- Booleanos: `true`/`false` (aceita também `1/0`, `sim/nao`).
- Paginação: `page` (1..N), `per_page` (1..100, padrão 20).
- Ordenação: use `ordering` com campos permitidos; prefixe com `-` para desc (ex.: `-data_cadastro`).

---

### GET /api/consultar/leads/

- **Parâmetros de filtro**:
  - **id**: filtra por ID exato
  - **search**: busca parcial em `nome_razaosocial`, `email`, `telefone`, `empresa`, `cpf_cnpj`, `id_hubsoft`
  - **origem**: ex.: `whatsapp`, `site`, `google`, `facebook`, `instagram`, `indicacao`, `telefone`, `email`, `outros`
  - **status_api**: ex.: `pendente`, `processado`, `erro`, `sucesso`, `rejeitado`, `aguardando_retry`, `processamento_manual`
  - **ativo**: `true` | `false`
  - **data_inicio**: filtra `data_cadastro` a partir de (inclusive)
  - **data_fim**: filtra `data_cadastro` até (inclusive)
- **Paginação**: `page`, `per_page`
- **Ordenação** (`ordering`): `id`, `data_cadastro`, `data_atualizacao`, `nome_razaosocial`, `valor` (use `-` para desc)

Exemplos:

```bash
curl -s \
  -H "Cookie: sessionid=SEU_SESSION_ID" \
  "http://localhost:8000/api/consultar/leads/?search=joao&origem=whatsapp&ordering=-data_cadastro&page=1&per_page=20"
```

```bash
curl -s \
  -H "Cookie: sessionid=SEU_SESSION_ID" \
  "http://localhost:8000/api/consultar/leads/?ativo=true&data_inicio=2025-01-01&data_fim=2025-01-31"
```

Resposta (exemplo):

```json
{
  "results": [
    {
      "id": 123,
      "nome_razaosocial": "João da Silva",
      "email": "joao@exemplo.com",
      "telefone": "+5551999999999",
      "empresa": "Empresa X",
      "origem": "whatsapp",
      "status_api": "pendente",
      "data_cadastro": "2025-01-20T12:34:56",
      "data_atualizacao": "2025-01-21T08:00:00",
      "valor": 1500.0,
      "valor_formatado": "R$ 1.500,00",
      "origem_display": "WhatsApp",
      "status_api_display": "Pendente"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20,
  "pages": 1,
  "ordering": "-data_cadastro"
}
```

---

### GET /api/consultar/historicos/

- **Parâmetros de filtro**:
  - **id**: filtra por ID exato
  - **telefone**: busca parcial
  - **lead_id**: filtra contatos do lead
  - **status**: ex.: `fluxo_inicializado`, `fluxo_finalizado`, `transferido_humano`, `convertido_lead`, `venda_confirmada`, etc.
  - **sucesso**: `true` | `false`
  - **converteu_lead**: `true` | `false`
  - **converteu_venda**: `true` | `false`
  - **data_inicio**: filtra `data_hora_contato` a partir de (inclusive)
  - **data_fim**: filtra `data_hora_contato` até (inclusive)
- **Paginação**: `page`, `per_page`
- **Ordenação** (`ordering`): `id`, `data_hora_contato`, `telefone`, `status` (use `-` para desc)

Exemplos:

```bash
curl -s \
  -H "Cookie: sessionid=SEU_SESSION_ID" \
  "http://localhost:8000/api/consultar/historicos/?telefone=55999&sucesso=true&data_inicio=2025-01-01&data_fim=2025-01-31&ordering=-data_hora_contato"
```

```bash
curl -s \
  -H "Cookie: sessionid=SEU_SESSION_ID" \
  "http://localhost:8000/api/consultar/historicos/?lead_id=10&converteu_venda=true&page=1&per_page=10"
```

Resposta (exemplo):

```json
{
  "results": [
    {
      "id": 987,
      "telefone": "+5551999999999",
      "status": "venda_confirmada",
      "data_hora_contato": "2025-01-25T09:15:00",
      "duracao_segundos": 180,
      "converteu_lead": true,
      "converteu_venda": true,
      "valor_venda": 299.9,
      "status_display": "Venda Confirmada",
      "duracao_formatada": "3m 0s",
      "valor_venda_formatado": "R$ 299,90",
      "lead_info": {
        "id": 10,
        "nome_razaosocial": "Empresa ABC",
        "telefone": "+555188888888",
        "empresa": "Empresa ABC"
      }
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 10,
  "pages": 1,
  "ordering": "-data_hora_contato"
}
```

---

### Notas

- Em caso de erro de validação de método, a API retorna `405`.
- Erros internos retornam `500` com mensagem simplificada.
- Se precisar tornar as rotas públicas, isente-as no `LoginRequiredMiddleware` (arquivo `vendas_web/middleware.py`).


