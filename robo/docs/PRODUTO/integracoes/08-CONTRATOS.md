---
modulo: Integracoes — Painel de Contratos
status: 🟢 Implementado
data: 14/06/2026
---

# Integracoes — Painel de Contratos

Visibilidade dentro do Hubtrix de toda **tentativa de criar ou aceitar contrato HubSoft** disparada pela engine de automacao do CRM (`_acao_gerar_contrato_hubsoft` ou `_acao_assinar_contrato_hubsoft`). Cada execucao vira 1 linha em `ContratoTentativa`, com payload + resposta HubSoft + motivo de falha categorizado + identificacao de qual etapa do fluxo composto (criar→anexar→aceitar) parou.

Painel em **`/configuracoes/integracoes/contratos/`** (por tenant, multi-tenant via `TenantMixin`).

Motivacao: completar a observabilidade do pipeline Nuvyon (HubSoft) — depois do painel de OS, ver as **assinaturas de contrato** que tambem podem falhar silenciosamente (contrato ja existe, modelo invalido, documento rejeitado, token expirado, etc.) e habilitar re-tentativa manual.

## Fluxo

```
Engine de Automacao (signal: oportunidade movida, condicoes batem)
   ↓
_acao_gerar_contrato_hubsoft  OU  _acao_assinar_contrato_hubsoft
   ↓
iniciar_tentativa(oportunidade, acao, hubsoft_service) → ContratoTentativa(pendente)
   ↓
HubsoftService.criar_contrato / anexar_arquivos_contrato / aceitar_contrato
   ├─ sucesso → marcar_sucesso(tentativa, etapa='completo', id_contrato=...)
   ├─ HubsoftServiceError → marcar_falha(tentativa, exc, etapa='criar'/'anexar'/'aceitar')
   └─ ja feito antes → return False antes do tracking (zero linha gerada)
   ↓
Painel /integracoes/contratos/ lista todas as tentativas
```

## Schema — `ContratoTentativa` (TenantMixin)

Tabela `integracoes_contrato_tentativa`. Campos principais:

| Campo | Tipo | Funcao |
|---|---|---|
| `grupo_tentativas_id` | UUID, db_index | Agrupa retries do mesmo lead+acao |
| `tentativa_numero` | smallint | 1ª, 2ª, 3ª... |
| `acao` | enum | `gerar` ou `assinar` |
| `etapa` | enum | `criar` / `anexar` / `aceitar` / `completo` — em qual subtarefa parou |
| `id_cliente_servico` | bigint | Servico HubSoft alvo |
| `id_cliente_servico_contrato` | bigint | ID do contrato (preenche em sucesso) |
| `id_modelo_contrato`, `id_empresa` | int | Config usada |
| `lead`, `cliente_hubsoft`, `servico`, `oportunidade`, `integracao`, `regra_automacao` | FK | Trilha completa |
| `status` | enum | `sucesso` / `falha` / `pendente` / `pulado_idempotente` |
| `motivo_falha_categoria` | enum | 8 categorias — ver abaixo |
| `motivo_falha_mensagem` | text | String crua do HubSoft (max 2000 chars) |
| `payload_enviado`, `resposta_hubsoft` | jsonb | Auditoria |
| `anexos_enviados` | jsonb | Lista de `{nome, tamanho_bytes, mime}` quando anexar |
| `duracao_ms` | int | Tempo total |
| `origem` | enum | `automacao_pipeline` ou `retry_manual` |
| `usuario_retry` | FK User | Quem clicou re-tentar |
| `criado_em` | datetime, db_index | |

**Indices:** `(tenant, -criado_em)`, `(tenant, status, -criado_em)`, `(tenant, acao, -criado_em)`.
**Constraint:** `unique(grupo_tentativas_id, tentativa_numero)`.

## Categorias de falha

| Categoria | Quando |
|---|---|
| `contrato_ja_existe` | HubSoft retorna "ja existe contrato" — caso conhecido pra `criar_contrato` |
| `cliente_sem_servico` | Cliente HubSoft sem servico ativo |
| `modelo_nao_encontrado` | `id_contrato_modelo` invalido |
| `documento_rejeitado` | Arquivo rejeitado ao anexar (MIME, tamanho, etc) |
| `dados_invalidos` | CPF/CNPJ vazio ou mal formado, autorizacao_nome vazio |
| `token_expirado` | OAuth expired, 401 |
| `cliente_inexistente` | CPF nao localizado no HubSoft |
| `outro` | Default — nao matchou nenhum pattern |

Patterns em [services/hubsoft_errors.py::categorizar_falha_contrato](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/hubsoft_errors.py).

## URLs

| URL | View | Permissao |
|---|---|---|
| `GET /configuracoes/integracoes/contratos/` | `lista_contratos` | `integracoes.ver_contratos` |
| `GET /configuracoes/integracoes/contratos/<uuid:grupo_id>/` | `detalhe_contrato` | `integracoes.ver_contratos` |
| `POST /configuracoes/integracoes/contratos/<uuid:grupo_id>/retentar/` | `retentar_contrato` | `integracoes.gerenciar_contratos` |

## Permissoes (em `seed_funcionalidades.py`)

- `integracoes.ver_contratos` — leitura (atendente)
- `integracoes.gerenciar_contratos` — re-tentativa manual (gerente/admin)

Rodar `python manage.py seed_funcionalidades` apos deploy.

## KPIs do dia

- Total tentadas
- Sucessos
- Falhas
- Taxa de sucesso (sucessos / total %)
- Top 3 motivos de falha
- Tempo medio das bem-sucedidas

## Re-tentativa manual

No detalhe (acesso com `gerenciar`), botao "Re-tentar" **chama a propria acao da engine** (`_acao_gerar_contrato_hubsoft` ou `_acao_assinar_contrato_hubsoft`) passando a oportunidade. Logica de idempotencia continua valendo: se `lead.contrato_aceito=True`, a acao retorna sem chamar HubSoft.

Quando a re-tentativa gera nova `ContratoTentativa`, ela e marcada com `origem='retry_manual'` + `usuario_retry`.

## Helpers reutilizaveis

[`services/contrato_tracking.py`](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/contrato_tracking.py):

- `iniciar_tentativa(oportunidade, acao, hubsoft_service, regra=None, origem='automacao_pipeline')` → `(tentativa, t0)`
- `marcar_sucesso(tentativa, t0, resposta, etapa, id_contrato)`
- `marcar_falha(tentativa, t0, exc, etapa)`
- `marcar_pulado_idempotente(tentativa, t0, motivo)`

As 2 acoes (`_acao_gerar_*`, `_acao_assinar_*`) usam esse helper pra evitar duplicacao de codigo.

## Queries SQL de troubleshooting

Resumo do dia por categoria:
```sql
SELECT acao, etapa, status, motivo_falha_categoria, count(*)
FROM integracoes_contrato_tentativa
WHERE tenant_id = 12 AND criado_em::date = CURRENT_DATE
GROUP BY 1,2,3,4 ORDER BY count(*) DESC;
```

Leads com falhas recentes pra investigar:
```sql
SELECT t.id, t.acao, t.etapa, t.motivo_falha_categoria,
       l.nome_razaosocial, l.cpf_cnpj,
       t.motivo_falha_mensagem
FROM integracoes_contrato_tentativa t
JOIN leads_leadprospecto l ON l.id = t.lead_id
WHERE t.tenant_id = 12 AND t.status = 'falha'
  AND t.criado_em > NOW() - INTERVAL '24 hours'
ORDER BY t.criado_em DESC;
```

Tentativas que precisaram de mais de 1 retry pra dar certo:
```sql
SELECT lead_id, acao, count(*) AS tentativas,
       array_agg(status ORDER BY tentativa_numero) AS sequencia
FROM integracoes_contrato_tentativa
WHERE tenant_id = 12 AND criado_em > NOW() - INTERVAL '7 days'
GROUP BY 1,2 HAVING count(*) > 1
ORDER BY tentativas DESC;
```

## Arquivos criados/alterados

- **Model:** [models_contrato.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/models_contrato.py) (novo) + import em [models.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/models.py)
- **Migration:** [0016_contratotentativa.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/migrations/0016_contratotentativa.py)
- **Categorizador:** estendido [services/hubsoft_errors.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/hubsoft_errors.py) com `categorizar_falha_contrato`
- **Helper tracking:** [services/contrato_tracking.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/contrato_tracking.py) (novo)
- **Patches engine:** [automacao_pipeline.py](../../../dashboard_comercial/gerenciador_vendas/apps/comercial/crm/services/automacao_pipeline.py) — `_acao_gerar_contrato_hubsoft` e `_acao_assinar_contrato_hubsoft` persistem tentativa via helpers
- **Views painel:** [views_contratos_tentativas.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/views_contratos_tentativas.py) (novo)
- **URLs:** [urls.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/urls.py) — 3 novas
- **Templates:** [contratos_lista.html](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/templates/integracoes/contratos_lista.html), [contratos_detalhe.html](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/templates/integracoes/contratos_detalhe.html)
- **Sub-nav:** [sidebar_subnav.html](../../../dashboard_comercial/gerenciador_vendas/templates/partials/sidebar_subnav.html) — entrada "Contratos" ao lado de OS
- **Permissoes:** [seed_funcionalidades.py](../../../dashboard_comercial/gerenciador_vendas/apps/sistema/management/commands/seed_funcionalidades.py) — +2 funcionalidades

## Limitacoes conhecidas (V1)

- **Sem cron de sincronizacao com HubSoft pra status atual do contrato** — se o contrato for cancelado/alterado direto no HubSoft, painel nao sabe (snapshot do momento da tentativa).
- **Sem retentativa automatica em background** — sai pelo CRM engine (signal). Re-tentar manual requer clique no painel.
- **Anexos sao snapshot de metadados** — guardamos lista `{nome, tamanho, mime}` mas nao o binario.
- **Pulados por idempotencia nao geram linha** — quando `lead.contrato_aceito=True` no inicio da acao, a funcao retorna False antes do `iniciar_tentativa()`. Logo nao polui o painel com "pulados" rotineiros. Se quiser visibilidade desses casos no futuro, mover o `iniciar_tentativa` pra antes do gate.

## Deploy

1. `python manage.py migrate integracoes`
2. `python manage.py seed_funcionalidades` (cria as 2 funcionalidades novas)
3. Atribuir aos perfis (Atendente: `ver_contratos`; Gerente/Admin: ambas)
4. Validar com lead que dispare regra de contrato → conferir 1 linha aparecendo no painel
