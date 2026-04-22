---
name: "API de tags pra leads (/api/leads/tags/)"
description: "Criar endpoint pra adicionar/remover tags em leads via API. Absorvido pela tarefa maior 'Automações do Pipeline'."
prioridade: "🔴 Alta"
responsavel: "Tech"
---

# API de tags pra leads — 21/04/2026

**Data:** 21/04/2026
**Responsável:** Tech
**Prioridade:** 🔴 Alta (bloqueante pra Nuvyon)
**Status:** ⚠️ **Absorvida** — virou parte da tarefa [automacao_pipeline_crm_21-04-2026.md](automacao_pipeline_crm_21-04-2026.md). Mantida aqui só como referência histórica da investigação inicial.

---

## Contexto

O fluxo Matrix da Megalink usa `POST /api/leads/tags/` em 3 pontos (pra marcar "Comercial", "Endereço", "Assinado"). Esse endpoint existe no sistema legado `robovendas` mas **não foi portado pro Hubtrix novo**.

Pra Nuvyon ligar o fluxo dela consumindo o Hubtrix multi-tenant, esse endpoint precisa existir.

Detalhes do uso e do fluxo em [fluxo_matrix_hubtrix.md](../../clientes/nuvyon/implementacoes/fluxo_matrix_hubtrix.md).

---

## Especificação

```http
POST /api/leads/tags/
Authorization: Bearer <api_token>
Content-Type: application/json

{
  "lead_id": 123,
  "tags_add": ["Comercial", "Assinado"],
  "tags_remove": ["Pendente"]
}
```

**Comportamento:**
- Decorator `@api_token_required` + `@csrf_exempt` (mesmo padrão dos outros endpoints)
- Valida `lead_id` obrigatório
- Busca `LeadProspecto` filtrando pelo tenant (automático via middleware)
- Aplica `tags_add` (ignorando duplicadas) e `tags_remove` (ignorando inexistentes)
- Retorna 200 com estado final das tags

**Retorno:**
```json
{
  "success": true,
  "lead_id": 123,
  "tags": ["Comercial", "Assinado"]
}
```

---

## Tarefas

- [ ] Verificar como o `LeadProspecto` armazena tags hoje (M2M? campo JSON? string separada?)
- [ ] Se não existe campo, definir o modelo (recomendo M2M com modelo `TagLead` ou `django-taggit`)
- [ ] Criar view `tags_lead_api` em `apps/comercial/leads/views.py`
- [ ] Adicionar rota em `apps/comercial/leads/urls.py`
- [ ] Teste unitário em `tests/` cobrindo add, remove, ambos, lead inexistente, tenant errado
- [ ] Registrar ação via `registrar_acao('leads', 'tags', ...)`
- [ ] Atualizar doc `PRODUTO/integracoes/03-APIS_N8N.md` com o novo endpoint

---

## Critério de aceite

- Endpoint responde 200 com tags atualizadas
- Endpoint respeita isolamento de tenant (lead de outro tenant retorna 404)
- Token inválido retorna 401
- Teste automatizado verde
- Fluxo Matrix Nuvyon consegue chamar o endpoint e marcar tags corretamente em ambiente de homologação

---

## Dependências / bloqueia

- **Bloqueia:** go-live do fluxo Matrix da Nuvyon
- **Depende de:** nada (pode ser feito agora)

---

## Referências

- Fluxo Megalink: `new_flow_comercial v7` (nós `api_26`, `api_27`, `api_28`)
- Guia técnico Nuvyon: [fluxo_matrix_hubtrix.md](../../clientes/nuvyon/implementacoes/fluxo_matrix_hubtrix.md)
- Checklist Nuvyon: [checklist_fluxo_atendimento.md](../../clientes/nuvyon/implementacoes/checklist_fluxo_atendimento.md)
