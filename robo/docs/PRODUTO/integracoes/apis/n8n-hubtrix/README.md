# Endpoints publicos Hubtrix (consumidos por N8N e Matrix)

Documentacao dos endpoints HTTP que o **Hubtrix expoe pra sistemas externos** (N8N do TR Carrion/Vero, Matrix da Nuvyon, agentes LLM, etc) acessarem. Aqui **somos o servidor**.

Doc original consolidada: [../../03-APIS_N8N.md](../../03-APIS_N8N.md). Esta pasta quebra por dominio.

## Base URL

| Ambiente | URL |
|---|---|
| Dev local | `http://127.0.0.1:8001` |
| Producao | `https://app.hubtrix.com.br` |

Endpoints publicos N8N (escopo deste doc) vivem sob:

- `/api/v1/n8n/...` — endpoints DRF tradicionais
- `/api/public/n8n/...` — endpoints publicos via token, sem CSRF

## Auth

Header `Authorization: Bearer <token>`.

Token vem de `IntegracaoAPI` tipo `n8n` ativa do tenant. Decorator `@api_token_required` em [apps/sistema/decorators.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/sistema/decorators.py) resolve `request.tenant` a partir do token (multi-tenant transparente — cada N8N tem seu token vinculado a 1 tenant).

Exemplo:
```
Authorization: Bearer qB0L0dkBULVQd6KlMlg24HV1hGxxQqIoFUrzZVN6yEU
```

## Estrutura desta doc

| Arquivo | Cobertura |
|---|---|
| [01-leads.md](01-leads.md) | Criar, atualizar, buscar lead |
| [02-crm.md](02-crm.md) | Pipelines, oportunidades, tarefas |
| [03-inbox.md](03-inbox.md) | Mensagem recebida, mensagem enviada como bot |
| [04-matrix-wrappers.md](04-matrix-wrappers.md) | Wrappers HubSoft (datas, agenda, abrir-atendimento, abrir-os) — usados pelo Matrix Nuvyon |
| [05-base-conhecimento.md](05-base-conhecimento.md) | RAG: `registrar-pergunta`, `buscar` |
| [06-atendimento-crm-bot.md](06-atendimento-crm-bot.md) | Telemetria de erros do bot + encerrar oportunidade com motivo |

## Quem consome o que

| Consumidor | Workflow N8N | Endpoints |
|---|---|---|
| **Vero (TR Carrion)** | `Df1BgcXdg3HAUZwf` | `/api/v1/n8n/inbox/*`, `/api/v1/n8n/leads/`, `/api/v1/n8n/crm/*`, `/api/public/n8n/conhecimento/*`, `/api/public/n8n/atendimento/registrar-erro-resposta/` |
| **Matrix (Nuvyon)** | Drawflow visual da Matrix | `/api/public/n8n/matrix/*` (datas, agenda, abrir-atendimento, abrir-os) |
| **Agente LLM (futuro v2)** | A definir | `/api/public/n8n/conhecimento/buscar/`, `/api/public/n8n/crm/oportunidade/<id>/encerrar-com-motivo/` |

## Formato de resposta padrao

Sucesso:
```json
{ "status": "success", "data": {...} }
```
ou (variante DRF):
```json
{ "success": true, ... }
```

Erro:
```json
{ "status": "error", "msg": "Descricao" }
```
ou (validacao):
```json
{ "success": false, "errors": { "campo": ["mensagem"] } }
```

## Codigos HTTP

- `200` sucesso
- `400` validacao / erro local / erro do HubSoft repassado (ver [../hubsoft/02-atendimento-os.md#por-que-4xx-mesmo-pra-erro-hubsoft](../hubsoft/02-atendimento-os.md#por-que-4xx-mesmo-pra-erro-hubsoft))
- `401` token ausente/invalido
- `404` recurso nao encontrado no tenant

## Onde estao os codigos

URLs registradas em:
- [apps/integracoes/urls_n8n_public.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/urls_n8n_public.py) — endpoints publicos com token
- [apps/comercial/.../urls.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/comercial/) — DRF leads, CRM
- [apps/integracoes/views_matrix_os.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/views_matrix_os.py) — wrappers Matrix
- [apps/integracoes/views_agente.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/) — base de conhecimento, telemetria
