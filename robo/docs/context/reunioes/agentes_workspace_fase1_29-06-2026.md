# Agentes do Workspace, Fase 1 entregue + bloqueio de pgvector (29/06/2026)

> Sessao autonoma (usuario dormindo, autorizou "terminar todas as fases", sem push).
> Branch: `feat/agentes-workspace`. Nada de push, nada de deploy, tudo em dev.

## O que e (contexto rapido)

"Terminar de trazer o workspace pra ca" = dar vida a camada de agentes IA do gestao
legado (megaroleta), expressa **sobre a engine `apps/automacao`**, dentro do `apps/workspace`.
Decisoes fechadas com o usuario (ver `context/reunioes/` anteriores + plano em
`.claude/plans/`): casa = workspace, motor = automacao reusado, interno (aurora-hq) agora
mas multi-tenant-ready, fonte unica do agente = `automacao.Agente`, aposentar `comando`,
NAO reimportar 1:1 do megaroleta (roster vem de `docs/AGENTES/`). Fase 0 salva em
`docs/PRODUTO/modulos/comando/analise-agentes-vs-engine-nova.md`.

## Fase 1 ENTREGUE e validada (commit `6cc24e5`)

Sem migration. Tres partes:

1. **5 tools de dados** em `apps/automacao/services/ia_tools.py` (read-only, tenant-scoped via
   `contexto.tenant`, reusam os models do registry `apps/relatorios/data_sources.py`):
   `status_pipeline`, `resumo_leads`, `vendas_periodo`, `churn_clientes`, `tickets_abertos`.
2. **Seed do roster**: `apps/workspace/management/commands/seed_agentes_workspace.py` le
   `docs/AGENTES/*.md` e cria `automacao.Agente` (idempotente). Rodou no aurora-hq: **24
   personas** (CEO, CTO, PMM, etc.), cada uma com as tools de dados + integracao OpenAI ativa.
3. **Entrada no workspace**: `apps/workspace/views/agentes.py` (lista + `chat_api` proprio que
   espelha o `simular` do automacao, sob permissao `workspace.ver`), template
   `templates/workspace/agentes.html` (roster + chat), rota em `workspace/urls.py`, item
   "Agentes" no subnav (`partials/sidebar_subnav.html`).

**Validacao end to end (dev, aurora_dev):** GET `/workspace/agentes/` renderiza (200, roster,
chat). POST no chat com o CEO + "como esta o pipeline?" → o LLM chamou a tool `status_pipeline`
e respondeu com **dado real**: "25 oportunidades, Lead Identificado: 24, Perdido: 1". Isolamento
multi-tenant confirmado (cada tenant so ve os proprios dados). `manage.py check` limpo.

## Fix de bonus (commit `58a9191`): grafo de migration do marketing

Ao tentar rodar a suite, achei um bug **pre-existente** da aposentadoria do marketing: a
migration `automacoes/0007` (DeleteModel de RegraAutomacao) nao declarava dependencia de
`emails/0003` (que converteu o FK `EnvioEmail.automacao` em int). Em build **fresh** (test DB,
deploy novo) o planner pode ordenar o delete antes da conversao do FK e quebrar com
`Related model 'automacoes.regraautomacao' cannot be resolved`. Prod nao quebrou porque o
migrate foi incremental (ordem temporal correta). Fix: adicionei a dependencia (nao re-roda
em prod, so corrige o grafo). Validado: o build fresh passou desse ponto.

## BLOQUEIO que parou Fase 2 e 3: pgvector ausente no ambiente local

- O Postgres local **nao tem a extensao pgvector** disponivel (`pg_available_extensions` vazio),
  nem ela esta criada no `aurora_dev`.
- As migrations `suporte/0007_pgvector_extension` (`CREATE EXTENSION vector`) +
  `0008_artigoconhecimento_embedding` (`VectorField(dimensions=1536)` + `HnswIndex`) **estao
  pendentes no aurora_dev** (suporte 7/8/9 nao aplicadas).
- Consequencia: **localmente nao da pra aplicar migration nenhuma** (qualquer `migrate` esbarra
  no `CREATE EXTENSION vector`), nem construir o test DB fresh. O model usa `VectorField` real,
  entao ate `--no-migrations` falharia.

**Por que isso parou Fase 2 e 3:** ambas precisam de migration (model `Proposta` com TenantMixin,
re-apontar as FKs `Tarefa.criado_por_agente`/`Documento.agente_origem` de `comando.Agente` →
`automacao.Agente`, aposentar `comando`). Sem conseguir **aplicar nem testar** essas migrations,
commita-las as cegas seria irresponsavel (uma migration ruim quebra o build de todos, e a
experiencia do bug do marketing acima mostra que grafo de migration nao testado esconde bugs
sutis). Por isso **parei conscientemente** em vez de fingir conclusao.

> Nota: eu dropei o `test_aurora_dev` durante o diagnostico (era um estado antigo, anterior a
> pgvector, que so passava por reuso). Reconstruir precisa de pgvector.

## Como destravar Fase 2 e 3 (precisa de decisao/ambiente)

Uma das duas, antes de continuar:
1. **Instalar pgvector** no Postgres local/CI (e aplicar `suporte 0007-0009` no aurora_dev). Caminho
   limpo, mantem a feature de RAG intacta.
2. **Tornar o RAG opcional em dev** (fix separado, toca migrations da suporte): `suporte 0007` skipa
   `CREATE EXTENSION` se indisponivel, e o `VectorField`/`0008` degrada quando nao ha pgvector.
   Mais invasivo (mexe na feature de busca semantica do bot), precisa do teu aval.

## Estado Fase 2 e 3 (a fazer, ja desenhado no plano)

Plano completo em `.claude/plans/a-gente-deve-gerar-expressive-pixel.md`. Resumo:
- **Fase 2:** gatilho autonomo/cron por agente (estende `automacao_retomar`/`execucao.py:86`);
  model `Proposta` (TenantMixin) no workspace + no `solicitar_aprovacao` (pausa) + UI de aprovacao;
  loop: agente pega `workspace.Tarefa` (nivel_delegacao>=1) → executa → proposta → humano aprova.
- **Fase 3:** migration re-apontando as 2 FKs `comando.Agente` → `automacao.Agente`; aposentar
  `comando` (husk, igual marketing).

## Tarefas abertas pra retomada
- Decidir o destravamento de pgvector (opcao 1 ou 2 acima).
- Atualizar `docs/PRODUTO/modulos/workspace/` com a feature de agentes (hook do pre-commit avisou).
- Fase 2 + Fase 3 (bloqueadas ate o pgvector).
- Branch `feat/agentes-workspace` NAO foi pushada (a pedido). 2 commits: `6cc24e5` (Fase 1) +
  `58a9191` (fix migration).

---

## ATUALIZACAO (mesma sessao): pgvector DESTRAVADO + Fase 2a e 3 entregues

**Bloqueio resolvido.** O Postgres local estava em **PG 18.3** (a frente do prod) **sem pgvector**.
Prod roda **PG 17.10 + pgvector 0.8.2**. O usuario instalou Docker; subimos `pgvector/pgvector:pg17`
(espelha prod) na **porta 5433** (pgvector 0.8.3). O `settings_local` agora le `DB_HOST`/`DB_PORT` do
env (default 127.0.0.1/5432, nao quebra ninguem); roda tudo com `DB_PORT=5433`. Os dados do
`aurora_dev` nativo (PG18) foram migrados pro Docker via `pg_dump` (downgrade PG18->17 limpo) +
`migrate` catch-up. Round-trip do CEO valida no Docker. `migrate` + `pytest` fresh agora rodam.

> Container `hubtrix-pg17` (volume `hubtrix_pg17_data`). Rodar comandos com `DB_PORT=5433`. O PG18
> nativo segue intacto na 5432.

**Fase 2a entregue (commit `f0258b7`):** propostas com aprovacao humana. Model `Proposta` (workspace,
TenantMixin, migration `0004`) + tool `solicitar_aprovacao` (agente propoe em vez de agir) +
`views/propostas.py` + template + rota `/workspace/propostas/` + subnav (aprovar/rejeitar, gate
`workspace.editar_todos`). Seed da a tool pros agentes. `test_workspace_propostas.py` (7 testes).

**Fase 3 (re-point) entregue (commit `a4ab444`):** `Tarefa.criado_por_agente` e
`Documento.agente_origem` re-apontadas de `comando.Agente` -> `automacao.Agente` (fonte unica).
Migration `0005`, sem dados. `comando` ficou orfao e vazio (0 rows).

**Validacao:** 45 testes verdes (build fresh com pgvector no Docker), `check` limpo, round-trip real.

**Frontier deixado (com motivo):**
- **Fase 2b (cron autonomo):** agente acordar sozinho e trabalhar backlog. NAO feito: falta decisao de
  design (o `Tarefa` tem `criado_por_agente` mas nao um "agente responsavel"; como atribuir tarefa a
  agente?) + e a parte mais arriscada (precisa guards anti-loop + limites por ciclo). Precisa do time.
- **Execucao diferida da Proposta:** v1 e advisory (aprovar so registra). Auto-executar o
  `dados_execucao` ao aprovar fica pro proximo incremento.
- **Aposentar `comando`:** orfao + vazio agora; husk + DeleteModel (igual marketing) e limpo, mas o
  drop em prod e gated por deploy. Deferido.

**Branch `feat/agentes-workspace`: 5 commits, NAO pushada.** Nada tocou prod. Mudanca local
nao-commitada: `settings_local.py` (le `DB_HOST`/`DB_PORT` do env) — enabler do dev Docker, seguro
(default 5432); decidir se commita.
