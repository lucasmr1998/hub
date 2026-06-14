---
modulo: Integracoes — Painel de Ordens de Servico
status: 🟢 Implementado
data: 14/06/2026
---

# Integracoes — Painel de Ordens de Servico

Visibilidade dentro do Hubtrix de toda **tentativa de abertura de OS** que o flow Matrix dispara via `POST /api/public/n8n/matrix/abrir-os/`. Cada chamada vira 1 linha em `OrdemServicoTentativa`, com payload enviado + resposta HubSoft + motivo de falha categorizado. Painel em **`/configuracoes/integracoes/ordens-servico/`** (cada tenant ve so os seus).

Motivacao: o `abrir-os/` em prod tinha taxa de erro de **71%** (5 falhas / 2 sucessos em 7d) sem visibilidade nenhuma. Painel resolve o gargalo e habilita evolucao futura (Nivel 2: conciliacao automatica que tenta tecnicos alternativos).

## Fluxo

```
Matrix → POST /api/public/n8n/matrix/abrir-os/
   ↓
views_matrix_os.abrir_os (cria tentativa pendente)
   ↓
HubsoftService.abrir_os() → HubSoft real
   ├─ 200 → tentativa.status = 'sucesso', id_ordem_servico_hubsoft preenchido
   └─ erro → tentativa.status = 'falha', motivo categorizado por regex
   ↓
Resposta JSON pro Matrix (200/400 — sem mudanca de contrato)
   ↓
Painel /integracoes/ordens-servico/ lista todas as tentativas
```

## Schema — `OrdemServicoTentativa` (TenantMixin)

Tabela `integracoes_ordem_servico_tentativa`. Campos principais:

| Campo | Tipo | Funcao |
|---|---|---|
| `grupo_tentativas_id` | UUID, db_index | Agrupa retries do mesmo `id_atendimento_hubsoft` (1 grupo = 1 OS no HubSoft, N tentativas) |
| `tentativa_numero` | smallint | 1ª, 2ª, 3ª... |
| `id_atendimento_hubsoft` | bigint | Vem do payload Matrix |
| `id_ordem_servico_hubsoft` | bigint | So preenche em sucesso |
| `lead`, `cliente_hubsoft`, `servico` | FK nullable | Resolve via `id_cliente_servico` → ServicoClienteHubsoft → ClienteHubsoft → LeadProspecto.cliente_hubsoft |
| `integracao` | FK IntegracaoAPI | Por qual integracao foi |
| `status` | enum | `sucesso` / `falha` / `pendente` |
| `motivo_falha_categoria` | enum | `tecnico_ocupado` / `slot_indisponivel` / `data_invalida` / `id_invalido` / `outro` |
| `motivo_falha_mensagem` | text | String crua do HubSoft (max 2000 chars) |
| `payload_enviado`, `resposta_hubsoft` | jsonb | Auditoria completa |
| Slot programado | data + hora inicio/termino + id_tecnico + cidade | |
| `duracao_ms` | int | Tempo total da chamada |
| `origem` | enum | `matrix` (automatico) / `retry_manual` (UI) |
| `usuario_retry` | FK User | Quem clicou re-tentar |
| `criado_em` | datetime, db_index | Timestamp |

**Indices compostos:**
- `(tenant, -criado_em)` — lista padrao
- `(tenant, status, -criado_em)` — filtro de status
- `(tenant, id_atendimento_hubsoft)` — lookup por atendimento
- `grupo_tentativas_id` — detalhe agrupado

**Constraint:** `unique(grupo_tentativas_id, tentativa_numero)`.

## Categorizacao da falha

Funcao `categorizar_falha_hubsoft(msg)` em [services/hubsoft_errors.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/hubsoft_errors.py). Patterns regex case-insensitive testados na mensagem retornada pelo `HubsoftServiceError`. Default: `outro`.

Pra adicionar nova categoria ou ampliar wording: editar `_PATTERNS` no arquivo. Resiliente a mudanca de copy do HubSoft.

## URLs

| URL | View | Permissao |
|---|---|---|
| `GET /configuracoes/integracoes/ordens-servico/` | `lista_ordens_servico` | `integracoes.ver_ordens_servico` |
| `GET /configuracoes/integracoes/ordens-servico/<uuid:grupo_id>/` | `detalhe_ordem_servico` | `integracoes.ver_ordens_servico` |
| `POST /configuracoes/integracoes/ordens-servico/<uuid:grupo_id>/retentar/` | `retentar_ordem_servico` | `integracoes.gerenciar_ordens_servico` |

## Permissoes

Adicionadas em [seed_funcionalidades.py](../../../dashboard_comercial/gerenciador_vendas/apps/sistema/management/commands/seed_funcionalidades.py):

- `integracoes.ver_ordens_servico` — leitura. Atendente ve o painel.
- `integracoes.gerenciar_ordens_servico` — re-tentar manualmente, marcar resolvido. Gerente/admin.

Rodar `python manage.py seed_funcionalidades` apos deploy (idempotente).

## KPIs do dia (mostrados no topo)

- **Total hoje** — todas as tentativas do dia
- **Sucessos** — `status='sucesso'`
- **Falhas** — `status='falha'`
- **Taxa de sucesso** — `sucessos / total * 100`
- **Top 3 motivos de falha** — categorias agrupadas
- **Tempo medio** — `Avg(duracao_ms)` das bem-sucedidas

## Filtros disponiveis na lista

`?status=&data_de=&data_ate=&tecnico=&cidade=` — combina com paginacao (`?page=N`, 50/pg).

## Re-tentativa manual

No detalhe (acesso com `gerenciar`), botao "Re-tentar" abre modal pra ajustar:
- Data/hora inicio + termino
- ID do tecnico

Reusa o `grupo_tentativas_id` (mantém histórico) e marca `origem='retry_manual'` + `usuario_retry`. Chama `HubsoftService.abrir_os()` igual ao automatico.

## Queries SQL de troubleshooting

Dia atual por tenant:
```sql
SELECT status, motivo_falha_categoria, count(*)
FROM integracoes_ordem_servico_tentativa
WHERE tenant_id = 12 AND criado_em::date = CURRENT_DATE
GROUP BY 1,2;
```

Atendimentos que precisaram de mais de 1 tentativa:
```sql
SELECT id_atendimento_hubsoft, count(*) AS tentativas,
       array_agg(status ORDER BY tentativa_numero) AS sequencia,
       max(tentativa_numero) FILTER (WHERE status='sucesso') AS qual_deu_certo
FROM integracoes_ordem_servico_tentativa
WHERE tenant_id = 12 AND criado_em > NOW() - INTERVAL '7 days'
GROUP BY id_atendimento_hubsoft
HAVING count(*) > 1
ORDER BY tentativas DESC;
```

Top motivos da semana:
```sql
SELECT motivo_falha_categoria, count(*) AS qtd,
       array_agg(DISTINCT left(motivo_falha_mensagem, 80)) AS exemplos
FROM integracoes_ordem_servico_tentativa
WHERE tenant_id = 12 AND status='falha' AND criado_em > NOW() - INTERVAL '7 days'
GROUP BY 1 ORDER BY qtd DESC;
```

## Limitacoes conhecidas (V1)

- **Sem cron de sincronizacao com HubSoft** — se a OS for cancelada/concluida diretamente no HubSoft, o painel nao sabe (mostra status do momento da abertura). Pra evolucao: criar cron que chama `listar_os_cliente()` periodicamente e atualiza `id_ordem_servico_hubsoft` + adiciona campo `status_atual_hubsoft`.
- **Sem retentativa automatica** — re-tentar e manual. Nivel 2 do plano original previa loop interno tentando proximos tecnicos do turno antes de devolver 400 pro Matrix.
- **Sem visao Aurora-HQ cross-tenant** — esta fora do escopo desta entrega.
- **Resposta de erro nao expande pra payload completo do HubSoft** — apenas `str(e)` da `HubsoftServiceError` e capturado. Se for necessario response body bruto, ampliar a exception pra carregar `response.json()` em outro atributo.

## Arquivos criados/alterados

- **Model:** [apps/integracoes/models_os.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/models_os.py) (novo) + import em [models.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/models.py)
- **Migration:** [0015_ordemservicotentativa.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/migrations/0015_ordemservicotentativa.py)
- **Categorizador:** [services/hubsoft_errors.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/hubsoft_errors.py) (novo)
- **Patch endpoint Matrix:** [views_matrix_os.py:abrir_os](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/views_matrix_os.py) (persiste tentativa)
- **Views painel:** [views_ordens_servico.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/views_ordens_servico.py) (novo)
- **URLs:** [urls.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/urls.py)
- **Templates:** [ordens_servico_lista.html](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/templates/integracoes/ordens_servico_lista.html), [ordens_servico_detalhe.html](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/templates/integracoes/ordens_servico_detalhe.html)
- **Sub-nav:** [sidebar_subnav.html](../../../dashboard_comercial/gerenciador_vendas/templates/partials/sidebar_subnav.html) — entrada provisoria em Sistema/Integracoes
- **Permissoes:** [seed_funcionalidades.py](../../../dashboard_comercial/gerenciador_vendas/apps/sistema/management/commands/seed_funcionalidades.py) — +2 funcionalidades

## Deploy

1. `python manage.py migrate integracoes`
2. `python manage.py seed_funcionalidades` (cria as 2 funcionalidades novas)
3. Atribuir as funcionalidades aos perfis (Atendente: `ver_*`; Gerente/Admin: ambas)
4. Validar: simular `abrir-os/` (sucesso + falha) → conferir painel → testar retry
