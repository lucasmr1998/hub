# Motivos de Perda (CRM)

**Última atualização:** 01/06/2026
**Status:** ✅ Em produção (deploy 31/05 + 01/06)

---

## Visão geral

Sistema completo de categorização de oportunidades perdidas no CRM com:
- Lista de motivos catalogados por tenant (`MotivoPerda`)
- Modal **obrigatório** (opcional, configurável) ao mover card pra "Perdida"
- Validação backend (`api_mover_oportunidade`)
- Backfill histórico via LLM
- Captura automática via bot (endpoint público N8N)
- Relatório Win/Loss
- Origem rastreável (`humano` / `llm_backfill` / `bot`)

## Modelos

### `MotivoPerda(TenantMixin)` (`crm_motivos_perda`)
- `nome` (charfield)
- `ativo` (bool)
- `ordem` (int) — pra dropdown
- `related_name='oportunidades'` apontando pra `OportunidadeVenda.motivo_perda_ref`

### `OportunidadeVenda` campos novos
- `motivo_perda` (text) — observação/justificativa livre
- `motivo_perda_ref` (FK pra MotivoPerda)
- `motivo_perda_categoria` (charfield, legado)
- `concorrente_perdido` (charfield)
- `motivo_perda_origem` (choices: humano/llm_backfill/bot, default humano) — **adicionado em T6 pra rastreio + rollback seletivo**

### `ConfiguracaoCRM` flags novas (T0/T8)
- `motivo_perda_obrigatorio` (bool, default False) — quando True, backend rejeita 400 se mover pra "Perdida" sem motivo
- `motivo_perda_pede_concorrente` (bool, default True) — quando motivo selecionado contém "concorrente", UI mostra campo extra "qual?"

## UI

| Tela | URL | Função |
|---|---|---|
| **Gerenciar motivos** | `/crm/motivos-perda/` | CRUD com contador de uso por motivo. Antes era seção dentro de `/crm/configuracoes/` (gigante e poluído) |
| **Configurações CRM** | `/crm/configuracoes/` | Toggle das 2 flags de obrigatoriedade |
| **Win/Loss** | `/crm/relatorios/win-loss/` | Relatório por motivo (já existia, agora linkado no sidebar) |
| **Modal Kanban** | `/crm/` ao arrastar card pra "Perdida" | Dropdown motivo + concorrente condicional + obs |
| **Modal Detalhe** | `/crm/oportunidade/<id>/` ao mudar select de estágio | Idem Kanban, dinâmico em-tela |

Subnav Comercial agora tem **secção "Relatorios"** + link "Motivos de perda" em "Configuracoes CRM".

## Endpoints públicos N8N

### `POST /api/public/n8n/crm/oportunidade/<pk>/encerrar-com-motivo/` (T5)

Bot/N8N encerra oportunidade movendo pra `is_final_perdido` + classifica motivo via OpenAI a partir da última mensagem do cliente.

Body:
```json
{
  "ultima_mensagem_cliente": "muito caro, fica pra proxima",
  "estagio_perdida_id": 42  // opcional
}
```

Comportamento:
- `motivo_perda_origem='bot'` em todas as escritas
- Confidence < 0.5 → "Outro" + obs livre (não trava)
- Idempotente: se já encerrada com motivo, retorna o atual

## Backfill histórico via LLM (T6)

Management command `apps/comercial/crm/management/commands/backfill_motivos_perda.py`.

```bash
# Dry-run obrigatório primeiro (default):
python manage.py backfill_motivos_perda --tenant <slug>

# Após revisar amostra impressa, aplicar:
python manage.py backfill_motivos_perda --tenant <slug> --apply
```

**Flags principais:**
- `--tenant <slug>` — OBRIGATÓRIO (recusa rodar sem)
- `--apply` — sem ele é dry-run
- `--confidence-min 0.7` — abaixo cai pra "Outro"
- `--max-msgs-cliente 5` / `--max-msgs-atendente 3` — janela de contexto pro LLM
- `--sample-size 10` — amostra exibida pra revisão humana

**Política:**
- LLM lê **últimas 5 msgs do cliente + 3 do atendente** (filtra ruído)
- Confidence ≥ 0.7 → associa motivo catalogado + obs
- Confidence < 0.7 → cai em "Outro" + justificativa livre
- `motivo_perda_origem='llm_backfill'` em 100% das escritas
- **Rollback fácil:** `UPDATE crm_oportunidades SET motivo_perda_ref_id=NULL WHERE motivo_perda_origem='llm_backfill' AND tenant_id=<>;`

**LGPD:** o LLM lê mensagens reais do cliente. Antes de rodar em tenants com cliente final (TR Carrion, FATEPI, Nuvyon, etc), validar autorização contratual. Aurora HQ + Demo são internos, sem bloqueio.

## Regra de automação "Docs recebidos → Criar Venda"

Não é parte direta da feature Motivos de Perda, mas conecta o ciclo:

- Tabela: `crm_regras_pipeline_estagio` id=7 (TR Carrion)
- Condição: `imagem_status=existe` (lead tem registro em `imagens_lead_prospecto`)
- Ação: `criar_venda` (insert em `crm_vendas`) + move estágio pra "Em Negociacao"
- Disparada por signal post-save em `ImagemLeadProspecto`

**Pré-requisito pra funcionar:** o flow N8N precisa registrar imagens via endpoint `/api/public/n8n/lead/imagem/` corretamente. Ver [tr-carrion/incidentes-01-06-2026.md](../../../../context/clientes/tr-carrion/incidentes-01-06-2026.md) pra histórico de bugs nesse caminho.

## Workspace tarefas

Feature foi quebrada em 9 tarefas no Workspace (projeto "Hubtrix Desenvolvimento", Aurora HQ):

| ID | Tarefa | Commit |
|---|---|---|
| #139 | T0 — Migration ConfiguracaoCRM flags | `35396aa` |
| #141 | T2 — Backend valida motivo | `5857b0b` |
| #140 | T8 — UI toggle | `32212af` |
| #144 | T7 — Tela dedicada `/crm/motivos-perda/` | `217a591` |
| #145 | T4 — Link Win/Loss subnav | `217a591` |
| #142 | T1 — Modal motivo Kanban | `fc856fa` |
| #143 | T3 — Modal motivo detalhe | `1ae268f` |
| #146 | T6 — Backfill LLM + campo origem | `d13847a` |
| #147 | T5 — Endpoint bot encerrar-com-motivo | `4e1ecbf` |
