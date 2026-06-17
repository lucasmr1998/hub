# Modulo Relatorios (Dashboards Self-Service)

Sistema estilo Hubspot/Mixpanel onde o usuario monta proprios dashboards
arrastando widgets configurados via Data Source + Metrica + Agrupamento +
Filtros + Visualizacao. Multi-tenant, pessoal + compartilhado, sem deploy
necessario pra criar nova metrica.

Entregue em 17/06/2026 (sessao Nuvyon + relatorios).

## Telas

| URL | O que faz | Quem ve |
|---|---|---|
| `/dashboards/` | Lista de dashboards (proprios + compartilhados) | Tem `relatorios.ver_dashboards` |
| `/dashboards/<id>/` | View read-only do dashboard com widgets em GridStack | Compartilhado OU criador |
| `/dashboards/<id>/editar/` | Modo edicao: drag-drop layout + botao adicionar widget | Criador OU admin |
| `/dashboards/criar/` | Form pra criar dashboard novo | Tem `relatorios.criar_dashboard` |

Sidebar principal tem icone "Dashboards" (`bi-grid-1x2`) ao lado de "Relatorios"
(legados em `apps.dashboard.urls`).

## Wizard de Widget

Modal sobreposto, 4 steps tipo wizard, drafts em memoria (so persiste no
DB ao concluir step 4):

1. **Fonte de dados** — 11 cards: Oportunidades, Leads, Tarefas, Conversas,
   Vendas, Historico de Estagios, Clientes HubSoft, Servicos, Faturas, OS,
   Atendimentos, Meta Vendas
2. **Metrica** — radio Contagem/Soma/Media + select de campo (se sum/avg)
   + titulo do widget
3. **Agrupamento** (dimensao + granularidade pra serie temporal `dia/semana/mes/ano`)
   **+ Filtros** dinamicos (linhas com campo + operador + valor)
4. **Visualizacao** — chips com 6 opcoes (Numero, Barra, Linha, Pizza, Tabela, Funil)
   **+ Preview live** via POST /api/preview/ (chama o WidgetQueryBuilder
   sem persistir)

## Backend

### Models (`apps/relatorios/models.py`)

- **`Dashboard`** (`TenantMixin`): nome, descricao, icone, criado_por,
  compartilhado (bool), ordem, config (JSON com layout grid + filtros globais)
- **`Widget`** (FK Dashboard): titulo, data_source, metrica (JSON),
  agrupamento (JSON), filtros (JSON), visualizacao, layout (JSON
  `{x,y,w,h}` do GridStack)

### Registry de Data Sources (`apps/relatorios/data_sources.py`)

Padrao declarativo (mesmo modelo de `automacao_condicoes.py`):
- 11 fontes registradas via funcao `registrar(DataSource(...))`
- Cada fonte declara `model_path`, `campos` (com `FieldSpec` tipado),
  `metricas` suportadas (`count`, `sum:campo`, `avg:campo`)
- Engine **NUNCA gera SQL cru** — sempre ORM, filtros validados contra schema
- Adicionar fonte nova = criar classe + decorator. Zero mudanca no engine.

### Query Engine (`apps/relatorios/query_builder.py`)

`WidgetQueryBuilder(widget, tenant).build()` resolve:
- **Filtros**: 10 operadores (`igual`, `diferente`, `maior`, `menor`,
  `contem`, `comeca`, `em`, `entre`, `existe`, `nao_existe`)
- **Metrica**: `Count`, `Sum`, `Avg` (Django ORM aggregates)
- **Agrupamento**:
  - Categorico (campo string/choice): `values().annotate().order_by('-_valor')`
  - Serie temporal: `TruncDay/Week/Month/Year` quando dimensao eh datetime+granularidade
- Cap de **50 buckets** pra evitar viz com 1000+ labels

Saida: `ResultadoQuery {labels, series, total, meta}` compativel com Chart.js.

### Espelhos HubSoft (`apps/integracoes/models_hubsoft_relatorios.py`)

Models criados pra habilitar relatorios sobre dados HubSoft em escala
(antes so tinhamos ClienteHubsoft + ServicoClienteHubsoft via sync por lead):

- **`FaturaHubsoft`** — `id_fatura_hubsoft`, valor, vencimento, pagamento,
  status (`aberta`/`paga`/`vencida`/`cancelada`)
- **`OrdemServicoHubsoft`** — OS real do HubSoft (NAO confundir com
  `OrdemServicoTentativa` que registra tentativas via Matrix). Status,
  tecnico, datas, motivo
- **`AtendimentoHubsoft`** — chamados (atendimentos abertos no HubSoft)

Indices compostos `(tenant, status, data_*)` pra queries rapidas em
filtros tipicos.

### Sync em lote (`apps/integracoes/services/hubsoft_relatorios.py`)

4 helpers que iteram endpoints `/todos` paginados do HubSoft:

- `sincronizar_base_clientes` — `/cliente/todos` com delta `data_inicio`.
  REUSA `_sincronizar_dados_cliente` existente (popula ClienteHubsoft +
  ServicoClienteHubsoft com `servicos` inline).
- `sincronizar_base_os` — `/ordem_servico/todos` dos ultimos N dias
- `sincronizar_base_atendimentos` — `/atendimento/todos` dos ultimos N dias
- `sincronizar_base_faturas` — itera `ClienteHubsoft` ativos do tenant
  + chama `listar_faturas_cliente` por cliente (HubSoft NAO tem
  `/faturas/todos`). Rate limit configuravel.

Todos retornam `ResultadoSync` dataclass com criados/atualizados/erros/duracao.

### Management commands

- `sync_base_clientes_hubsoft --tenant <slug> [--full | --dias N] [--max-paginas N] [--dry-run]`
- `sync_base_os_hubsoft --tenant <slug> [--dias N]`
- `sync_base_atendimentos_hubsoft --tenant <slug> [--dias N]`
- `sync_base_faturas_hubsoft --tenant <slug> [--max-clientes N] [--rate-limit S]`

### CronJobs cadastrados em prod (desativados)

Gerenciados em `/aurora-admin/cron/` (toggle on/off + rodar agora):

| Nome | Schedule | Status |
|---|---|---|
| `sync_base_clientes_hubsoft` | `0 */4 * * *` (4h) | Desativado |
| `sync_base_os_hubsoft` | `*/30 * * * *` (30min) | Desativado |
| `sync_base_atendimentos_hubsoft` | `0 */6 * * *` (6h) | Desativado |
| `sync_base_faturas_hubsoft` | `0 2 * * *` (1x dia) | Desativado |

Pra ativar em prod: ir em `/aurora-admin/cron/` e clicar no toggle.
Bootstrap full Nuvyon (~15min, 24.560 clientes) pode ser feito via
"Rodar agora" no painel ou via SSH:
`python manage.py sync_base_clientes_hubsoft --tenant nuvyon --full`.

## Permissoes (Funcionalidades)

3 novas em `seed_funcionalidades.py`:
- `relatorios.ver_dashboards` — leitura
- `relatorios.criar_dashboard` — criar/editar pessoais
- `relatorios.compartilhar_dashboard` — marcar como compartilhado (so admin)

Atribuidas aos perfis 79 (Vendedor) + 89 (Admin) do tenant Nuvyon em
17/06/2026. Outros tenants (TR Carrion, FATEPI, Aurora-HQ) precisam ser
atribuidas manualmente.

## Dependencias front

- **GridStack.js v9** (CDN `https://cdn.jsdelivr.net/npm/gridstack@9/`) — drag-drop grid
- **Chart.js v4** (CDN ja em uso pelo projeto) — render dos graficos
- Zero React/Vue — JS vanilla seguindo padrao do projeto

## Limitacoes conhecidas do MVP (backlog)

| Limitacao | Workaround |
|---|---|
| Editar widget abre wizard zerado (nao pre-popula) | Excluir + criar de novo |
| Botao "Excluir dashboard" so na API, sem UI | Acessar `/admin/relatorios/dashboard/` |
| Form de renomear/compartilhar dashboard sem UI | Idem |
| Sem export PDF/CSV | Imprimir PDF do navegador |
| Sem alertas baseados em widget (ex: "alertar se cair > 20%") | — |
| Cross-tenant Aurora-HQ (super-admin ver tudo) | — |

## Estado em prod (17/06/2026)

- Dashboard demo "Demo HubSoft" (id=1) criado pra Nuvyon com 5 widgets
- Tabelas espelhos vazias (0 linhas) — crons desativados, bootstrap
  manual pendente quando quiser usar dados completos
- 1.005 clientes HubSoft / 1.307 servicos ja sincronizados (sync de 10
  paginas rodado em 17/06)

## Briefing Nuvyon — 12 relatorios

| # | Relatorio | Status |
|---|---|---|
| 1 | Leads por origem | ✅ Dataset pronto. Falta CAC (Meta/Google Ads — fora de escopo MVP) |
| 2 | Funil completo | ✅ Pronto via Oportunidade + agrupamento `estagio__nome` |
| 3 | Motivos de perda | ✅ Pronto via Oportunidade + filtro `estagio.is_final_perdido` |
| 4 | Velocidade atendimento | ⚠️ Precisa definir estagio "Proposta enviada" em ConfiguracaoCRM |
| 5 | Performance consultoras (TMA) | ⚠️ Precisa campo `Lead.atendido_em` + signal |
| 6 | Leads parados | ✅ Pronto via Lead + filtro `data_atualizacao < N dias` |
| 7 | Follow-up | ✅ Pronto via Tarefa |
| 8 | Conversao por etapa | ✅ Pronto via HistoricoPipelineEstagio |
| 9 | Cobertura e viabilidade | ⚠️ Precisa backfill `consultar_viabilidade` pros 500+ leads historicos |
| 10 | Cancelamento pre-instalacao | ⚠️ Parcial via `ServicoClienteHubsoft.data_cancelamento`. Faltam OS detalhadas |
| 11 | Meta diaria | ✅ Dataset pronto via MetaVendas |
| 12 | Executivo | ⚠️ Composicao dos demais — montar quando os outros estiverem cobertos |
