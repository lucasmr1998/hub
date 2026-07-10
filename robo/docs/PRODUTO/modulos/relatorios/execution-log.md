# Execution Log — Relatórios

> Trilha cronológica do que foi implementado/decidido no módulo de relatórios e dashboards self-service. Append no fim, entrada mais nova embaixo. Formato: `## YYYY-MM-DD — título`.

---

## 2026-07-04 — Campos motivo_perda_ref + flags final + operador ultimos_dias

- Ação: DataSource `oportunidade` expõe `motivo_perda_ref__nome` (choice, choices_from crm.MotivoPerda), `estagio__is_final_perdido` e `estagio__is_final_ganho` (bool). Novo operador `ultimos_dias` no query_builder (valor N → campo >= hoje-N dias) pra filtros de data relativa que não ficam obsoletos.
- Why: widgets de "Motivos de perda" agrupavam por `motivo_perda_categoria` (NULL em 96% das perdidas) — o dado real está na FK `motivo_perda_ref`. E não havia como criar widget "últimos 30 dias" sem hardcode de data.
- Output: commit `c8f6424`. Nuvyon: 14 dashboards seed deletados, painel único #15 com 3 widgets validados.
- Status: completed

## 2026-07-08 a 2026-07-10 — Relatorio executivo Nuvyon: engine ganhou metricas, operadores e transforms

- Acao: campo `lead__valor` exposto no data source oportunidade (+ metricas sum/avg; `valor_estimado` da op e property, nao coluna). Operadores novos: `ultimos_dias` (ja existia), `ha_mais_de_dias` (data mais antiga que N dias, pra "parado no estagio"). Transforms novos: `conversao_geral` (numero unico cross-modelo, atalho no build), `conversao_por_canal` (% por campo do lead, corta canal com <3 leads), `gargalo_funil` (% passagem entre etapas consecutivas reusando o funil cumulativo, pior no transform_meta), `funil_viabilidade` (leads -> estagio de viabilidade configuravel -> vendas), `normalizar_cidade` (agrupa variantes de grafia, title case, remove sufixo /UF). Helper `_janela_e_fonte` centraliza overrides de periodo/fonte dos transforms cross-modelo.
- Fix critico: `funil_cumulativo` contava op perdida como se tivesse atravessado o funil inteiro (estagio Perdido tem a maior ordem); corrigido em 2441c71 — Perdido nao avanca o alcance, ganho conta como funil completo.
- Feature: icone "?" nos widgets abre modal com a explicacao (`Widget.descricao`, varchar 255; funcao JS precisa ficar FORA do bloco modo_edicao). 17 widgets do dash #15 da Nuvyon com descricao preenchida.
- Gotchas: filtro de widget com campo fora do registry e descartado em silencio (query_builder valida campo do filtro mas NAO o campo da metrica); visualizacao numero mostra fmtNum(total) sem prefixo de moeda (por o R$ no titulo).
- Output: commits 9ba54e7, bcda76b, 2441c71, 98d6cff, caf8dbe, 1f87e99, 2f66aaa.
- Status: completed

## 2026-07-10 — Diagnostico UX + CTO (Playwright local)

- Acao: diagnostico duplo (UX + CTO) do modulo via Playwright em ambiente local, seed realista no tenant Nuvyon (222 leads, 167 ops, Painel Executivo reconstruido com 18 widgets validados). 41 screenshots + log de captura. Nenhum toque em prod, nenhuma alteracao de codigo de produto.
- Achados P0 (relatorios): `Widget` sem FK tenant => api_widget_excluir/config/dados aceitam widget de dashboard compartilhado de outro tenant (cross-tenant exploravel por usuario autenticado comum). `query_builder._base_queryset` so filtra `if self.tenant` (tenant None + manager fail-open = consulta global).
- Achados UX: filtros globais nao aplicam nem refletem a querystring (rel_03/rel_04 identicos ao padrao; `fonte=facebook` nem existe como opcao); KPIs sem unidade (R$/%); mobile inutilizavel (grid 4 colunas < 768px); funis/gargalo ilegiveis; wizard comeca por "qual tabela" e nao "qual pergunta".
- Arquitetura: registry declarativo bom, mas os 7 transforms furam o contrato (import direto de apps.comercial, ignoram o queryset, estado mutavel via self._*, recursao entre transforms). Zero cache. Zero testes do modulo.
- Hardcode: par facebook/organico em 6 pontos; 'Endereco Validado'/'fluxo_inicializado'; PALETTE e URLs /dashboards/ cravadas no JS; CDNs pinados sem fallback.
- Output: doc `robo/docs/context/reunioes/diagnostico_ux_cto_relatorios_cs_10-07-2026.md` (achados + plano P0-P3 + estrategia de testes + tarefas propostas). Aguardando aprovacao do Lucas pra criar tarefas Workspace e executar.
- Status: completed (diagnostico); pending (execucao dos fixes)
