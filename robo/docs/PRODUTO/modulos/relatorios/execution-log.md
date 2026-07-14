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

## 2026-07-13 — Filtro global de VENDEDOR na barra do dashboard

- **Pedido do dono**: filtros por cidade e por vendedor. Vendedor primeiro (este bloco); cidade fica pra proxima.
- **Descoberta que definiu o desenho**: existem DOIS universos de vendedor e eles nao batem. No CRM o dono e o `responsavel` (User); no HubSoft e o `vendedor_nome` (string), e la aparecem pessoas que **nem existem no CRM** (Aloysio Rosseti, Giane Moraes, Renata Pinheiro, Gabriela Ferreira, "HubSoft (Sistema)") — gente que fecha direto no ERP, fora do Hubtrix. Nao da pra unificar sem um mapa; entao o filtro vale no universo do CRM e a base HubSoft fica de fora, **com aviso visivel** (opcao B, escolhida pelo dono).
- **Declarativo, nada hardcoded**: `DataSource.campo_vendedor` (novo) declara o caminho ORM ate o User em cada fonte. `oportunidade` -> `responsavel`; `lead` -> `oportunidade_crm__responsavel`; `historico_contato` -> `lead__oportunidade_crm__responsavel`; `venda`/`historico_pipeline` -> `oportunidade__responsavel`; `tarefa` -> `responsavel`. Fonte sem dono (cliente_hubsoft, servico_hubsoft, fatura, os, conversa, meta_vendas) fica `None` e ignora o filtro. Lead<->Oportunidade e **OneToOne** (`oportunidade_crm`), entao o join NAO duplica linha.
- **Transforms cross-modelo**: funil_macro, conversao_geral, conversao_por_canal e funil_viabilidade montam queryset na mao e nao passam pelo `_aplicar_filtros`. Ganharam os helpers `_v_lead/_v_op/_v_atend`. Sem isso o funil (o widget principal) ignorava o filtro em silencio.
- **Honestidade visual**: `meta.ignora_vendedor` sai da API quando ha filtro ativo e a fonte nao tem dono; o card ganha o selo ambar "sem recorte por vendedor". Evita que alguem filtre por uma vendedora e leia o numero global como se fosse dela.
- **Armadilha do Django encontrada**: `values_list(...).distinct()` num model com `Meta.ordering` devolve REPETIDOS (o ORM injeta a coluna de ordenacao no SELECT). Pegou primeiro no meu proprio script de validacao (a soma por vendedor deu 4283 contra um total de 222) e a view tinha o mesmo risco. Corrigido com `.order_by()` vazio antes do distinct.
- **Validado (dev)**: por fonte, a soma por vendedor sempre <= total (a diferenca sao as ops sem responsavel, que existem de verdade); builder bate com o ORM cru (42/32/30); funil reparte por vendedora; no browser o select filtra os KPIs (101 -> 12 leads, conversao 22,8% -> 58,3%) e os 8 cards HubSoft aparecem marcados. 0 erros de console.
- **Arquivos**: `data_sources.py`, `query_builder.py`, `views.py`, `templates/relatorios/dashboard_detalhe.html`.
- **Status**: completed (dev). Deploy pendente. Filtro de CIDADE pendente (exige normalizacao: 37 grafias distintas em prod, tipo 'caconde' vs 'Caconde', 'RIBEIRAO PRETO/SP' vs 'Ribeirao Preto').

## 2026-07-13 — DRILL-DOWN: o numero do card vira lista

- **Motivacao**: o dono pediu um painel OPERACIONAL. Um card que diz "110 leads sem contato" e nao mostra QUEM sao os 110 e decorativo: a vendedora precisa da lista pra ligar. Drill-down e a capacidade que faltava, e serve tambem ao painel executivo (auditar um numero antes de levar pra reuniao).
- **Declarativo**: `DataSource.colunas_drill` (colunas da tabela) + `DataSource.url_detalhe` (rota da ficha). Declarado em oportunidade (-> crm:oportunidade_detalhe), lead (-> comercial_leads:lead_detail), historico_contato, servico_hubsoft e tarefa. Fonte sem colunas_drill nao fica clicavel.
- **Motor**: `WidgetQueryBuilder.registros(categoria, limite, offset)` reusa `_aplicar_filtros` (mesmos filtros do widget + os globais da barra: periodo, fonte, vendedor) e recorta pela fatia clicada. `suporta_drill()` bloqueia transforms cujo numero nao vem de UM queryset (funil_macro, conversao_*, gargalo, viabilidade) e tambem `normalizar_cidade`: a barra diz "Ribeirao Preto" mas no banco existem 'RIBEIRAO PRETO' e 'RIBEIRAO PRETO/SP', entao filtrar pelo rotulo traria lista incompleta — melhor nao abrir do que abrir errado (volta quando o filtro de cidade normalizada existir).
- **API**: `GET /dashboards/api/widget/<pk>/registros/?categoria=&pagina=` (50/pagina). `meta.drill` na API de dados diz ao front se o card e clicavel.
- **UI**: clique no numero do KPI ou na barra/fatia do grafico abre modal com tabela, link pra ficha em cada linha e paginacao.
- **DOIS BUGS MEUS, pegos pelo teste de consistencia (valor da barra == total da lista)**:
  1. Lia `agrupamento['campo']`, mas a chave e `dimensao` (a mesma do `_calcular_agrupado`). O recorte sumia calado: o modal dizia "— Ana" e listava as 23 vendas de todo mundo.
  2. Nao tratava o rotulo `'—'` (que o motor da pra nulo/vazio): clicar na fatia "sem vendedor" abria lista vazia enquanto o grafico dizia 4.
- **Validado (dev, Playwright)**: para 3 categorias de cada widget agrupado, o numero do grafico bate com o total da lista (inclusive a fatia vazia); KPI abre 50 de 101 com link pra ficha; paginacao anda; 0 erros de console.
- **Arquivos**: `data_sources.py`, `query_builder.py`, `views.py`, `urls.py`, `templates/relatorios/dashboard_detalhe.html`.
- **Status**: completed (dev). Deploy pendente de aprovacao.

## 2026-07-13 — PAINEL OPERACIONAL (a fila do dia) + campos calculados

- **Pergunta do dono**: "fizemos um painel executivo; num painel OPERACIONAL o que eu deveria ver?". Executivo = placar (resultado, tendencia), olhado 1x por semana. Operacional = FILA (o que esta parado, ha quanto tempo, de quem e), olhado varias vezes por dia. Cada card e uma pilha de trabalho, nao uma estatistica — por isso todos abrem lista.
- **Desenho saiu dos dados reais, nao de teoria**: 110 leads sem NENHUM contato (78 ha 3+ dias) e 44 cadastros travados por falta de CPF, em prod. Casa com a analise anterior: 44% das perdas sao "sem retorno" contra 9 pro concorrente — a Nuvyon quase nao perde pro mercado, perde pro proprio processo. Dai o card principal ser "leads sem contato".
- **Ficou DE FORA de proposito**: "tarefas vencidas". O modulo de tarefas tem ZERO uso no tenant (0 pendentes, 0 vencidas). Card que marca zero pra sempre ensina a equipe a ignorar o painel.
- **CAMPOS CALCULADOS (engine)**: `DataSource.anotacoes` (novo) permite campo que so existe via agregacao — o caso e `qtd_contatos = Count('historico_contatos')`, sem o qual "lead sem nenhum contato" nao e expressavel. Aplicado SOB DEMANDA (`_anotar`): so entra no queryset quando o widget usa o campo, senao toda query da fonte carregaria um GROUP BY de graca.
- **BUG SERIO ACHADO (o mais grave da sessao)**: o operador `existe`/`nao_existe` comparava com string vazia em QUALQUER campo. Em campo numerico (id_plano_rp) o banco estoura, o `except` engolia calado e **o filtro sumia** — o card "Cadastro travado" mostrou **222 leads (a base inteira) em vez de 2**. Um card sem filtro nao quebra: ele MENTE. Fix: `_q()` monta o Q respeitando o tipo do FieldSpec (vazio so e '' em texto; em numero/data/FK so existe NULL) e o except agora loga WARNING com widget, fonte, campo e operador.
- **Widgets (10)**: fila do dia (6 KPIs: leads sem contato / sem contato 3+ dias / cadastro travado / ops sem dono / paradas 7+ dias / instalacoes pendentes) + carga por vendedora + onde as ops estao paradas + atendimentos por dia (14d) + motivos de perda (7d). Seed idempotente: `manage.py seed_painel_operacional --tenant <slug> [--dry-run]`.
- **Validado (dev)**: cada KPI conferido contra query ORM independente (todos batem); todos abrem drill; a lista traz link pra ficha; graficos rendem; 0 erros de console. A barra "—" de "carga por vendedora" (22) casa com o card "ops sem dono" (22), ou seja, o painel e coerente consigo mesmo.
- **Nota**: um teste meu tambem estava errado (contra-prova de "sem CPF" so olhava string vazia, e os leads tinham CPF NULL). O widget estava certo. Contra-prova sempre por ORM independente, nao por reimplementacao do mesmo filtro.
- **Arquivos**: `data_sources.py`, `query_builder.py`, `management/commands/seed_painel_operacional.py`.
- **Status**: completed (dev, dashboard #6 local). PENDENTE: aprovacao do dono + deploy + rodar o seed em prod (dado, exige confirmacao).

## 2026-07-14 — Filtro global por TIME (dormente ate a Nuvyon cadastrar) + fix do select no modo edicao

- **Pedido**: "a gente consegue adicionar um filtro por time?". Sim: a estrutura ja existia (EquipeVendas + PerfilVendedor.equipe, OneToOne com User). Caminho ORM: responsavel -> perfil_crm -> equipe.
- **O problema nao era codigo, era CADASTRO**: em prod ha **1 equipe** ("Equipe Mococa") e **1 vendedora vinculada** — justamente a que tem 1 oportunidade. As outras 15 (incluindo a Thais, com 204 ops) nao tem nem PerfilVendedor. Um select com uma opcao que recorta 1 de 700 oportunidades nao informa, engana.
- **Decisao do dono (opcao B)**: implementar agora e deixar o filtro DORMINDO. `_equipes_do_tenant` so devolve lista quando ha **2+ equipes ativas com membros**; abaixo disso o select nem renderiza. No dia em que a Nuvyon cadastrar os times, o filtro acorda sozinho, sem deploy.
- **Implementacao** (mesmo padrao do filtro de vendedor, nada hardcoded): `DataSource.campo_equipe` declara o caminho por fonte; `_aplicar_equipe` no motor; helpers `_v_lead/_v_op/_v_atend` ganharam o recorte por time pros transforms cross-modelo (senao o funil ignoraria o filtro calado — a mesma armadilha do vendedor). Fonte sem dono (base HubSoft) ignora e o card exibe o selo "sem recorte por vendedor/time".
- **BUG DO DONO (achado por ele, olhando a tela)**: "pq no painel executivo mostra o filtro por vendedora e no operacional nao?". Nao era o painel, era o MODO: as duas views usam o mesmo template, mas so a de consulta passava `vendedores`. No modo edicao a barra ficava com periodo/fonte e sem o select. Corrigido (commit 0a41358) e as duas views agora passam tambem `equipes`.
- **Validado (dev)**: com 2 times simulados, a soma por time <= total (a diferenca sao as ops sem responsavel) e o funil reparte (78/62/62, vendas 20); no browser o select aparece so com 2+ times, filtra (leads 101 -> 25, conversao 22,8% -> 48%) e volta a sumir quando os times sao removidos. Cadastro de teste feito com rollback/limpeza, sem sujar o dev.
- **Arquivos**: `data_sources.py`, `query_builder.py`, `views.py`, `templates/relatorios/dashboard_detalhe.html`.
- **Status**: completed (dev). Deploy pendente. **Acao da Nuvyon**: cadastrar os times de verdade (por cidade? por canal?) e vincular cada vendedora — sem isso o filtro segue dormindo, por desenho.
