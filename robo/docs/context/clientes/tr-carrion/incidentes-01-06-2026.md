# TR Carrion — Incidentes 31/05–01/06/2026

Diagnóstico e correções do dia 31/05–01/06 que destravaram **conversão de leads em vendas**. Caso raiz: a Vero coletava dados completos mas várias etapas não chegavam no Hubtrix (bugs silenciosos).

---

## Resumo executivo

| # | Bug | Impacto | Status |
|---|---|---|---|
| 1 | Vero N8N flow: nodes `Registrar RG Frente/Verso Hubtrix` com **sintaxe JSON quebrada** no jsonBody | ~80 leads desde 22/05 enviaram RG mas nunca tiveram imagem registrada no Hubtrix → regra "Docs recebidos → Criar Venda" não disparava → vendas perdidas | ✅ corrigido (commit `82d9369`) |
| 2 | Endpoint Hubtrix `/api/public/n8n/lead/imagem/`: monta URL como `MEDIA_URL + arquivo` mas arquivo do `inbox.Mensagem` vive em **volume privado** (`/app/private_media/inbox_midia/`) | `link_url` em `imagens_lead_prospecto` aponta pra path inexistente → preview broken na tela de docs do CRM/Vendas | ⚠️ workaround pra Bruna feito; código do view ainda precisa fix |
| 3 | Workflow `[Vero] Follow-up Abandonados D+2h`: filtro `corte_ativacao='2026-05-30 12:53'` exclui exatamente os leads abandonados antes dessa data | 100 execuções nas últimas 8h, **zero follow-ups enviados** — leads abandonados de 27-29/05 ficaram fora do scope | ⏳ fix proposto (NOW-3d janela móvel), aguarda OK |
| 4 | Workflow Vero não chamava `/conhecimento/registrar-pergunta/` ao transferir pra humano | TR Carrion não estava alimentando `PerguntaSemResposta` apesar de 85.7% das conversas virarem humano | ✅ corrigido (commit `ea31b72`) — node `RegistrarPerguntaSemResposta` adicionado entre `Por Nodo Atual main#13` e `Step Aguarda Humano` |

---

## 1. Bug RG nodes — sintaxe N8N inválida

### Diagnóstico

Nodes `Registrar RG Frente Hubtrix` e `Registrar RG Verso Hubtrix` no workflow `Df1BgcXdg3HAUZwf` tinham `jsonBody` com sintaxe N8N **inválida**:

```
={ { "tenant_slug": "tr-carrion", "lead_id": ={{ ... }}, "link_url": ={{ ... }}, "descricao": "RG frente" } }
```

A combinação de expressão externa `=` + objeto literal `{...}` + expressões aninhadas `={{...}}` confunde o parser do N8N. **Falha local antes de chegar ao HTTP request:**

```
{"error": "The value in the \"JSON Body\" field is not valid JSON"}
```

### Como descobri

1. Pesquisei caso da Bruna (lead #416, op#357): preencheu tudo, `vero_session=concluido`, mas oportunidade parada em "Aguardando Vendedor"
2. `imagens_lead_prospecto` da Bruna: **0 registros** — apesar de URLs dos RGs estarem em `vero_session.dados`
3. Inspecionei executions recentes do flow Vero filtrando por telefone — achei erros nos nodes Registrar RG Frente/Verso

### Fix

Trocou `jsonBody` (string única com tudo aninhado) por `bodyParameters` (campos separados):

```python
"bodyParameters": [
  {"name": "tenant_slug", "value": "tr-carrion"},
  {"name": "lead_id",     "value": "={{ $node['Load Session'].json.dados?.lead_id ?? $node['Load Session'].json.lead_id }}"},
  {"name": "link_url",    "value": "={{ $node['Uazapi Download RG Frente'].json.fileURL }}"},
  {"name": "descricao",   "value": "RG frente"}
]
```

Aplicado via API N8N: deactivate → update → activate (janela morta 1.09s).

Backups versionados:
- `_backup_vero_pre_fix_rg.json` (snapshot pré-fix)
- `_proposta_vero_com_fix_rg.json` (estado pós-fix)

### Validação

Backfill da Bruna confirmou caminho funcional:
1. POST `/api/public/n8n/lead/imagem/` com cada RG (URLs do `vero_session.dados`)
2. → 2 registros criados em `imagens_lead_prospecto` ✅
3. → regra `id=7` "Docs recebidos → Criar Venda" disparou ✅
4. → op#357 movida de "Aguardando Vendedor" → "Em Negociacao" ✅
5. → venda#16 criada em `crm_vendas` automaticamente ✅

---

## 2. Bug URL imagens — `MEDIA_URL` vs `private_media`

### Diagnóstico

View `apps/integracoes/views_n8n_webhook.py:registrar_imagem_lead` faz:

```python
url_final = django_settings.MEDIA_URL + str(msg.arquivo)
# = "/media/" + "2026/05/ACC...jpg"
# = "/media/2026/05/ACC...jpg"
```

**Mas o arquivo real está em** `/app/private_media/inbox_midia/2026/05/ACC...jpg`. O `inbox.Mensagem.arquivo` (FileField) tem storage privado definido em `apps/inbox/models.py:20`:

```python
kwargs['location'] = os.path.join(settings.BASE_DIR, 'private_media', 'inbox_midia')
```

Como `MEDIA_ROOT=/app/media` e o arquivo vive em `/app/private_media/inbox_midia/`, o URL gerado aponta pra path inexistente → preview broken.

### Workaround temporário pra Bruna

Atualizei `link_url` das 2 imagens (#46 e #47) pra usar o endpoint inbox que serve mídia privada autenticada:

```sql
UPDATE imagens_lead_prospecto SET link_url='/inbox/api/conversas/312/midia/4612/' WHERE id=46;
UPDATE imagens_lead_prospecto SET link_url='/inbox/api/conversas/312/midia/4614/' WHERE id=47;
```

### Fix pendente (código)

`views_n8n_webhook.py:registrar_imagem_lead` precisa ser ajustado: quando achar `inbox.Mensagem` correspondente, construir URL como:

```python
url_final = f'/inbox/api/conversas/{msg.conversa_id}/midia/{msg.pk}/'
```

Sem isso, **qualquer novo lead que enviar RG continua caindo no mesmo bug**. Bug A do escopo "fix definitivo do código".

---

## 3. Workflow Follow-up D+2h — `corte_ativacao` bloqueando

### Diagnóstico

Workflow `[Vero] Follow-up Abandonados D+2h` (`tYckyds4TqPpFOWd`):
- Ativo, rodando a cada ~5min (schedule "A cada 30min" mas executa mais frequente)
- 100 execuções nas últimas 8h analisadas → **zero follow-ups enviados**
- `Buscar Stale` sempre retorna `items=0`

Query SQL do node `Buscar Stale`:

```sql
SELECT ... FROM vero_session
WHERE atualizado_em < NOW() - INTERVAL '5 minutes'
  AND atualizado_em > NOW() - INTERVAL '7 days'
  AND atualizado_em > '2026-05-30 12:53:59.605182+00:00'  -- corte_ativacao
  AND nodo_atual NOT IN ('inicio', 'concluido', 'aguarda_humano')
  AND COALESCE((dados->>'_followup_count')::int, 0) < 2
```

Estado real no DB:
```
sessions distrib últimos 7 dias:
  aguarda_humano   10
  aguarda_cep       7  ← elegível, mas atualizado_em pré-30/05 12:53
  aguarda_nome      5  ← idem
  aguarda_plano     4  ← idem
  undefined         3  ← idem
  concluido         3
  aguarda_email     1  ← idem
```

**Todos os 20 leads em estados intermediários têm `atualizado_em` ANTERIOR ao corte_ativacao** → filtro zera tudo.

### Fix proposto (aguardando OK)

```sql
-- ANTES:
AND atualizado_em > '2026-05-30 12:53:59'

-- DEPOIS:
AND atualizado_em > NOW() - INTERVAL '3 days'   -- janela móvel
```

Comportamento novo: pega abandonados nos últimos 3 dias. Dispara follow-up imediato pros 20 leads parados.

---

## 4. Vero não alimentava PerguntaSemResposta

### Diagnóstico

Endpoint `/api/public/n8n/conhecimento/registrar-pergunta/` foi criado em 31/05 (commit `162a3cf`), mas o flow Vero do TR Carrion nunca foi atualizado pra chamá-lo. Tabela `suporte_perguntas_sem_resposta` do tenant TR Carrion estava **vazia** apesar de 85.7% das conversas virarem "humano".

### Fix

Adicionado node `RegistrarPerguntaSemResposta` (HTTP POST) entre `Por Nodo Atual` branch main#13 (transferência pra humano) e `Step Aguarda Humano`.

Cria `IntegracaoAPI` tipo=n8n pro TR Carrion (id=24) com Bearer token específico pra autenticar a chamada. Body: `pergunta=$('Entrada').json.mensagem`.

`continueOnFail=True` garante que falha do registro não trava o handoff do bot.

### Validação

Próxima conversa que cair em "transferir pra humano" vai gerar entrada automaticamente em `/suporte/conhecimento/perguntas/` do TR Carrion.

---

## Lista de leads pendentes pra backfill (80)

Leads do TR Carrion com `status_api='erro'` entre 22/05 e 29/05, candidatos a backfill manual de imagens (similar ao que foi feito pra Bruna):

```sql
SELECT id, nome_razaosocial, telefone, data_cadastro
FROM leads_prospectos
WHERE tenant_id=(SELECT id FROM sistema_tenant WHERE slug='tr-carrion')
AND status_api='erro' ORDER BY data_cadastro DESC;
```

**Estratégia pra cada lead (caso decidam rodar em massa):**

1. SELECT URLs `doc_rg_frente_url` / `doc_rg_verso_url` do `vero_session` por telefone
2. POST `/api/public/n8n/lead/imagem/` 2x (frente + verso) com `X-N8N-Webhook-Secret`
3. Regra `id=7` dispara automaticamente — venda criada
4. Update `link_url` pra apontar pro endpoint inbox (workaround do bug #2 até fix do código)

**Antes de rodar em massa:** validar que o vendedor não vai ficar com 80 oportunidades aparecendo de uma vez no funil. Possível impacto operacional.

---

## Backups versionados nesta pasta

- `_baseline_vero_orquestrador_01-06-2026.json` — snapshot pré-edição
- `_backup_vero_pre_registrar_pergunta.json` — pré-adição do node RegistrarPerguntaSemResposta
- `_proposta_vero_com_registrar_pergunta.json` — pós-edição (com token redigido)
- `_backup_vero_pre_fix_rg.json` — pré-fix dos nodes RG
- `_proposta_vero_com_fix_rg.json` — pós-fix RG
