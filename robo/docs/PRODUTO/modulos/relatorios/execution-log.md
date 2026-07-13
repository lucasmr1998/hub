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

## 2026-07-13 — Redesign visual do Painel Executivo (apresentacao Gabi)

- Contexto: painel funcional mas "muito feio". Direcao escolhida pelo Lucas: KPI executivo compacto (padrao stat_card). Foco no dash #2 Painel Executivo (18 widgets).
- KPI (widgets numero): passaram a renderizar no padrao executivo (label uppercase discreto + numero alinhado a esquerda, ~1.9rem) via CSS escopado por `[data-viz="numero"]`. Formatacao com UNIDADE, config-driven: `config_extra.formato` = moeda (R$, compacto acima de 1k) / percentual (%) / numero (abrevia >1k); nulo = travessao. Helper JS `fmtValor(n, formato)`. Widget-card ganhou `data-viz` e `data-formato` no template.
- Funis: rotulo movido pra FORA (position:right) com linha guia; antes era branco por dentro, ilegivel em segmento estreito. Formatter nao duplica numero quando o label ja embute (regex /[|(:]/). Conserta "Funil do mes" (linha final composta vazando) e "Funil com viabilidade" (texto ilegivel + numero duplicado).
- Barra: passa a horizontal quando ha >6 categorias OU rotulo longo (>14 chars). Conserta "Gargalo do funil" (era vertical a 30/45 graus, cortado) e "Conversao por canal".
- Validado local (Playwright, dash #2): KPIs com R$/%/abrev, dois funis legiveis, gargalo horizontal completo.
- Pendente: (1) setar `config_extra.formato` nos widgets de PROD (dado, vai junto no deploy com confirmacao); (2) opcionais: secoes de grupo no grid, relabel "Sem responsavel" no lugar de "—" em Vendas por consultora, altura dos KPI cards.
- Arquivos: `apps/relatorios/templates/relatorios/dashboard_detalhe.html` (CSS+JS+template). Sem mudanca em views/models/query_builder.
- Status: completed (local, aguardando validacao do Lucas)

## 2026-07-13 — Delta vs periodo anterior nos KPIs

- KPI numero passou a mostrar delta vs periodo anterior (▲/▼ +X% vs periodo anterior). Backend: `_valor_periodo_anterior` recomputa a metrica na janela anterior (mesmo N de dias deslocado), so pra widget com filtro `ultimos_dias`; blindado (erro -> None, nao afeta o numero). So se aplica a Leads/Novas ops/Vendas/Receita/Ticket; conversao (transform) e snapshots (sem janela) ficam sem delta.
- Semantica: 'direcao' (movimento real -> seta) separada de 'positivo' (bom/ruim -> cor), conforme `config_extra.sentido` do widget ('maior_melhor' default, 'menor_melhor' pra Leads sem atendimento / Leads parados, onde cair e bom). Respeita o filtro global de periodo (7d/30d/...).
- Front: `.widget-delta` renderizado abaixo do numero (preenche o respiro do card). Verde/vermelho/neutro.
- Validado local (dash #2): Vendas ▲53,3% verde, Leads do mes ▼5,5% vermelho, Leads sem atendimento ▼30,6% VERDE.
- Pendente prod: alem de config_extra.formato, setar config_extra.sentido='menor_melhor' nos KPIs "ruins"; e o codigo do delta precisa de um 2o deploy.
- Arquivos: `apps/relatorios/query_builder.py` (+_valor_periodo_anterior, comparativo no _calcular_numero), `dashboard_detalhe.html` (CSS+JS do delta).
- Status: completed (local)

## 2026-07-13 — Limpeza do painel: delta sem base + widget oculto

- Delta: so aparece quando ha base anterior REAL (`anterior > 0`). Tenant com < 30 dias de historico (ex: Nuvyon, base comecou 22/06) tinha periodo anterior = 0, e o delta mostrava "novo" em todo card. Agora suprime; reaparece sozinho quando houver periodo anterior.
- Widget oculto: `config_extra.oculto=true` some do modo CONSULTA (view filtra), mas continua no modo EDICAO pra reexibir/gerenciar. Forma reversivel de tirar widget redundante do dashboard sem deletar.
- Motivacao: painel #15 da Nuvyon estava visualmente bagunçado (KPIs no meio, funil no topo, 5 widgets de canal, 2 roscas quase iguais). Usado pra ocultar "Meta Ads vs Organico" (64) e "Vendas por canal" (69) e reordenar (KPIs no topo).
- Arquivos: `query_builder.py` (comparativo so com base>0), `views.py` (filtro oculto no modo consulta).
- Status: completed (codigo). Layout/oculto aplicados como dado em prod (dash #15).

## 2026-07-13 — Migracao dos relatorios legados (Frente B): fonte historico_contato + 3 dashboards

- Contexto: migrar os relatorios legados (apps/dashboard, /relatorios/leads|clientes|atendimentos) pro modulo novo /dashboards/, cada um virando um Dashboard. Decisao do dono: legados PERMANECEM no ar em paralelo.
- Codigo (unico): nova fonte `historico_contato` (model leads.HistoricoContato) em data_sources.py — campos status(18 choices), origem_contato, data_hora_contato(granularidades), duracao_segundos, sucesso, converteu_lead, converteu_venda; metricas count + avg:duracao_segundos. Legado define "atendimento" como status='fluxo_inicializado'.
- Dashboards (dado, via seed por tenant): Leads (fonte lead, 1:1), Clientes (servico_hubsoft/cliente_hubsoft, 1:1), Atendimentos (historico_contato). Cada um com KPIs de periodo (com delta de brinde), pizza e linha 30d.
- Validado dev (nuvyon local): 6+8+6 widgets, todos rodam no builder; Atendimentos renderiza 272 total / 123 em 30d, pizza por status, linha por dia. Clientes fica 0 local (sem espelho HubSoft local; prod tem ~1000). Leads 222.
- Pendente: rodar o seed dos 3 dashboards em prod (dado, com confirmacao); Conversoes (bonus, funil_macro) e Analise de atendimentos (fonte atendimento_fluxo) ficam pra depois.
- Arquivo: apps/relatorios/data_sources.py.
- Status: completed (dev). Deploy do codigo + seed em prod pendente de confirmacao.

## 2026-07-13 — Painel #15: KPIs numa linha so e funil macro simplificado

- Pedido do dono (2 ajustes visuais, painel Comercial da Nuvyon): (1) "esses 6 kpis poderiam estar juntos numa mesma linha"; (2) "vamos deixar esse funil mais simples, tire a informacao do meta ads e organico".
- (1) e DADO, nao codigo: os 6 KPIs foram pra w=2 (12 colunas / 6 cards) em y=0 e os demais widgets subiram 2 linhas. UPDATE transacional em prod (dash #15, tenant nuvyon), 16 widgets, autorizado nominalmente. Titulos encurtados pra caber no card estreito (o detalhe segue no "?" de cada card): "Receita gerada", "Ticket medio", "Leads sem atendimento", "Leads parados", "Instalacoes pendentes".
- (2) e CODIGO: o transform `funil_macro` emitia `quebra` (Meta Ads x Organico) dentro do card de Oportunidades. Removida a emissao no query_builder e o render nos DOIS renderizadores (dashboard_detalhe.html e decks/deck_render.js) pra nao deixar caminho morto. O recorte por fonte continua disponivel pelo chip global do dashboard (Meta Ads / Organico), que filtra o funil inteiro em vez de quebrar so uma etapa.
- Nota de divida: o funil macro esta duplicado (inline no dashboard_detalhe.html e no deck_render.js). O motor de ECharts ja foi extraido pra static compartilhado; o funil macro (HTML puro) ainda nao. Extrair no proximo toque.
- Arquivos: apps/relatorios/query_builder.py, apps/relatorios/templates/relatorios/dashboard_detalhe.html, apps/decks/static/decks/deck_render.js.
- Status: completed (codigo). Layout em prod ja aplicado; o funil simplificado precisa de deploy.
