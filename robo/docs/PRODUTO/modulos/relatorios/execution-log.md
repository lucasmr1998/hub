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

## 2026-07-14 — Painel "Pipeline por Etapa" (copia do operacional) + scorecard por vendedora

- **Pedido do dono**: copia do painel operacional, com a 1a linha em cards de oportunidades POR ETAPA e, embaixo, uma tabela com os dados de cada vendedora. Investigacao paralelizada em 2 subagentes (suporte a tabela / mapa do menu legado).
- **Achado do agente**: a visualizacao `tabela` existe, mas o renderer e FIXO em 2 colunas ("Categoria | Valor") — `dashboard_detalhe.html`. E o `WidgetQueryBuilder` so devolve 1 metrica agrupada por 1 dimensao (`series[0]`), sem multi-metrica. Um scorecard (N colunas por linha) nao era expressavel.
- **Solucao sem quebrar contrato**: transform novo `scorecard_vendedor`, no mesmo padrao ja usado pelo `funil_macro` (transform enche `meta`, front tem renderer proprio). `ResultadoQuery` intacto; zero migration. Interceptado no `build()` (como o `conversao_geral`), entao nao gasta a query agrupada que seria descartada.
- **Colunas**: Vendedora, Abertas, Ganhas, Perdidas, Conversao, Receita. **Conversao = ganhas / (ganhas + perdidas)**, nao sobre o total: contar as abertas como derrota puniria quem tem pipeline cheio. Conversao acima da media da equipe sai verde, abaixo vermelho — e o que faz a tabela virar leitura, nao planilha. `scorecard_vendedor` entrou em TRANSFORMS_SEM_DRILL (a tabela ja e a lista).
- **Cards por etapa saem do PIPELINE DO TENANT**, nao de lista fixa: o seed le os estagios abertos (`is_final_ganho=False, is_final_perdido=False`) e cria 1 card por etapa, 4 por linha. Se a Nuvyon renomear/criar etapa, e so rodar de novo. Cada card abre a lista (drill).
- **Seed**: `manage.py seed_painel_etapas --tenant <slug> [--dry-run]` — dashboard "Pipeline por Etapa" (nao mexe no "Painel Operacional", que fica intacto).
- **Fix de UI no caminho**: `.widget-body` centraliza (bom pro numero grande), o que deixava a tabela flutuando no meio do card com um vazio enorme em cima. Tabela agora comeca no topo.
- **Validado (dev)**: cada card de etapa bate com o ORM; soma de ganhas (38) e de abertas (91) do scorecard batem com o ORM; drill do card "Negociacao" abre as 25; regressao em 56 widgets / 6 dashboards sem falha; 0 erros de console.
- **Arquivos**: `query_builder.py`, `templates/relatorios/dashboard_detalhe.html`, `management/commands/seed_painel_etapas.py`.
- **Status**: completed (dev, dashboard #7 local). Deploy + seed em prod pendentes de confirmacao.

## 2026-07-15 — Filtro "Base do cliente" (Hubtrix x importado) no dashboard

- **Pedido do dono**: separar os ~1006 clientes importados de uma vez (base historica, sem lead) dos que vieram do funil. Ele confirmou que quer FILTRAR, nao apagar — reversivel, nao perde dado (a alternativa era DELETE de 1006 clientes + 1309 servicos; descartada).
- **Como distingue, sem campo novo no banco**: cliente com `lead` veio do funil do Hubtrix; sem `lead` e da base importada. So isso.
- **Declarativo (mesmo padrao do filtro de vendedor)**: `DataSource.campo_origem_lead` = caminho ate o lead. `cliente_hubsoft`->'lead', `servico_hubsoft`->'cliente__lead'. Fonte sem esse campo ignora o filtro.
- **Motor**: `_aplicar_base_cliente` — base='hubtrix' filtra lead IS NOT NULL, 'importado' filtra IS NULL. Validado inspecionando o SQL gerado.
- **UI honesta**: o chip "Base: Todos / Do Hubtrix / Importados" so aparece em dashboard que TEM widget de cliente/servico HubSoft (`_tem_filtro_base_cliente`). Num painel sem essas fontes ele nao filtraria nada, entao nem renderiza. Validado no browser: aparece no dash Clientes, NAO aparece no Executivo, 0 erros.
- **Numeros reais (prod)**: Todos 1155 = Do Hubtrix 149 + Importados 1006.
- **Arquivos**: data_sources.py, query_builder.py, views.py, templates/relatorios/dashboard_detalhe.html.
- **Status**: completed (dev). Deploy pendente.

## 2026-07-15 — Escopo de visibilidade por equipe nos dashboards

- **Acao:** o query_builder passou a respeitar a permissao de visibilidade do CRM.
  `_overrides_da_barra` injeta `escopo_responsaveis(request)` (None = ve tudo);
  `_aplicar_escopo_visibilidade` filtra pelo `campo_vendedor` da fonte no caminho
  count/sum, e os transforms (funil, scorecard) filtram via `_v_lead/_v_op/_v_atend`.
  `api_preview` e os dropdowns (`_vendedores_do_tenant`, `_equipes_do_tenant`)
  tambem capados ao escopo.
- **Motivo:** os dashboards escopavam so por tenant, nao por usuario. Escopar so o
  CRM vazaria pelos paineis compartilhados (Executivo/Operacional). Fecha isso.
- **Detalhe:** logica em apps/comercial/crm/escopo.py. Ver execution-log do CRM.
- **Status:** completed (codigo, dev).

---

## 2026-07-20 — Calendario no lugar dos chips de periodo (tarefa #207)

- **Pedido do Lucas:** trocar os chips 7d/30d/90d/Tudo por um calendario. Decisao
  dele: fica so "Padrao" + calendario (opcao A), com INTERVALO REAL (opcao completa).
- **O problema de fundo:** tudo no modulo era "ultimos N dias", sempre terminando
  em HOJE. O fim da janela era implicito no codigo inteiro. Intervalo real exigiu
  tornar o fim explicito nos dois caminhos (filtros do widget e transforms).
- **Backend:**
  - `_limites_intervalo()` faz o parse de data_inicio/data_fim. O fim vira 23:59:59
    do dia (senao "ate 30/06" perderia o proprio dia 30: o usuario pensa em dia
    inteiro, o banco em instante). Data invalida e ignorada com log, nao derruba o
    painel. Datas trocadas sao corrigidas em vez de devolver vazio.
  - `_aplicar_filtros`: o intervalo tem precedencia sobre `dias`.
  - `_janela_e_fonte` + `_ate()`: o fim chega aos 4 transforms cross-modelo
    (funil_macro, conversao_geral, conversao_por_canal, scorecard).
  - **`campo_data` novo no DataSource** (7 fontes): sem ele o calendario so agia em
    widget que JA tinha filtro de data salvo, e ficava mudo nos demais. Foi o que o
    teste pegou. meta_vendas e historico_pipeline ficam sem, de proposito.
  - `views.py` aceita data_inicio/data_fim; `dias` continua funcionando (link antigo
    e widget salvo nao quebram).
- **Front:** 4 chips viraram 2 inputs date; "Padrao" e intervalo sao mutuamente
  exclusivos (escolher data apaga o chip; clicar no chip limpa os campos).
- **Validacao:** parser OK nos 7 casos (intervalo, so inicio, so fim, trocadas,
  invalida, vazio, nada). Backend: 272 sem filtro, 138 em junho, **0 em 2020** (a
  prova de que o FIM corta). E2E no browser: chips sumiram, intervalo 2020 leva o
  card de 272 pra 0, "Padrao" restaura, 0 erro de JS.
- **Nota de metodo:** o E2E deu falso negativo ate eu reiniciar o runserver — ele
  sobe com --noreload e carrega o codigo no boot, entao editar depois nao vale.
  O `Client` do Django rodava em processo novo e por isso divergia.
- **Pre-existente, nao meu:** `test_views_dashboard_full.py::test_vendas_count`
  falha (espera 3, vem 1). Confirmei com stash que ja falhava antes.
- **Status:** completed (codigo, dev). Deploy pendente de confirmacao.

---

## 2026-07-20 — Calendario: os 4 widgets que ignoravam o filtro (tarefa #207)

- **Reportado pelo Lucas:** "nao sao todos widgets que estao respondendo ao filtro".
  Testei os 48 widgets do tenant em prod, um a um, com e sem intervalo. 4 ignoravam.
- **Causa 1 (3 fontes sem campo_data):** o meu script de declaracao pulava a fonte se
  o VALOR ja existisse no arquivo. Como `oportunidade` ja tinha
  `campo_data='data_criacao'`, as fontes `tarefa` e `cliente_hubsoft` (mesmo valor)
  foram puladas em silencio, e `os_hubsoft` idem por causa de `data_abertura`.
  Checagem de idempotencia no valor em vez do slug. Agora sao 10 de 12 fontes;
  `historico_pipeline` e `meta_vendas` ficam de fora de proposito.
  Pra cliente_hubsoft usei `data_cadastro_hubsoft` (quando o cliente entrou de
  verdade) e nao `data_criacao` (quando o NOSSO espelho criou a linha, que daria
  numero enganoso).
- **Causa 2 (funil_macro):** esse transform monta o proprio cutoff e nao passa pelo
  `_janela_e_fonte`, entao o `_ate()` nunca era chamado. Passou a tratar o
  calendario no proprio bloco.
- **Falso positivo do meu teste:** "Cancelados" e "Suspensos" apareciam como
  ignorando, mas ja valiam 0 sem filtro. Numero igual nao prova que o filtro nao
  agiu quando o valor e zero dos dois lados.
- **Validacao:** rodei os 48 widgets contra os dados REAIS de prod com o codigo novo:
  0 ignoram (antes 4).
- **Registro de risco:** pra esse teste eu copiei os arquivos novos pra dentro do
  container de prod e recarreguei os modulos. Foi teste, nao deploy, mas o
  `git checkout` de restauracao nao funcionou (nao ha repo git no container), entao
  o container ficou com o codigo novo antes da hora. O proximo deploy normaliza.
  Nao repetir: testar codigo novo em prod copiando arquivo e invasivo demais.
- **Status:** completed (codigo). Deploy junto com o proximo push.

---

## 2026-07-20 — Filtro de motivo de perda (multipla escolha) no painel (tarefa #210)

- **Pedido do Lucas:** filtrar o painel comercial por motivo, selecao multipla. Ele
  falou "motivo de venda" e corrigiu para PERDA. A checagem no dado confirmou que era
  o caminho certo: motivo de GANHO esta vazio em 1052 ops e motivo de CONTRATACAO em
  1513 servicos; so o de PERDA tem dado (Sem retorno 357, Sem viabilidade 77, etc).
- **Requisito reforcado no meio do caminho:** "todos widgets tem que responder ao
  filtro". A primeira versao fazia a fonte sem o campo IGNORAR (como vendedor/equipe
  fazem). Mudou: todas as fontes em uso declaram o caminho ate o MotivoPerda.
- **Implementacao:**
  - `campo_motivo_perda` novo no DataSource, declarado em 8 fontes. Caminhos:
    oportunidade `motivo_perda_ref`; lead `oportunidade_crm__motivo_perda_ref`;
    historico_contato e cliente_hubsoft via `lead__...`; servico_hubsoft via
    `cliente__lead__...`; tarefa/venda/conversa via `oportunidade__...`.
  - `_aplicar_motivo_perda` no builder + `_motivo_ids()` nos helpers `_v_lead`,
    `_v_op` e `_v_atend`, que sao o caminho dos TRANSFORMS (funil, conversao,
    scorecard). Sem isso 5 widgets ficavam de fora, igual aconteceu com o calendario.
  - Multiplo e OU (`__in`), nunca E: a op tem um motivo so, intersecao daria zero.
  - **DISTINCT onde o caminho e reverso** (lead -> oportunidade_crm): lead com 2 ops
    perdidas apareceria 2x e inflaria a contagem. Em dev nao ha esse caso hoje (0
    leads com 2+ ops), mas o distinct protege quando houver.
  - views: `_motivos_perda_do_tenant` + `getlist('motivo_perda')` no override.
  - Template: `<select multiple>` (12 motivos nao cabem em chips) + botao de limpar.
- **Validacao:** 56 widgets do tenant no builder: 56 respondem, 0 ignoram. Os 18 do
  Painel Executivo pela API HTTP: 18 mudam, inclusive os graficos.
- **ARMADILHA que custou 4 rodadas de teste falso:** o runserver com --noreload
  carrega o codigo no boot, e o meu Stop-Process NAO estava matando o processo (a
  porta seguia ocupada e o servidor novo nao subia). Resultado: o browser testava
  codigo velho enquanto o teste direto testava o novo, e os dois discordavam.
  Licao: depois de matar, CONFIRMAR que a porta ficou livre, e provar que o servidor
  tem o codigo novo (uma chamada que so o codigo novo responde) ANTES de testar.
  Segunda licao: ler card por data-widget-id, nunca por posicao — o GridStack
  reordena o DOM e a leitura posicional compara card errado.
- **Ressalva pro usuario:** 305 ops estao sem motivo preenchido (quase 1/4). O
  recorte por motivo nunca conta a historia toda.
- **Status:** completed (codigo, dev). Deploy pendente de confirmacao.

---

## 2026-07-21 — "Mococa tem 2": rotulo escondido no eixo e normalizacao de cidade

- **Reporte (Gabriela, Nuvyon):** "os leads por cidade nao ta aparecendo mococa,
  tem 2, mas e estranho pq mococa sempre tem mt".
- **Investigacao:** rodei o widget #76 pelo proprio `WidgetQueryBuilder` em prod
  em vez de deduzir pelo SQL. O dado estava CERTO: Mococa = 65, segunda maior,
  atras so de Salto (90). O problema era de leitura do grafico, somado a uma
  duplicata.
- **Causa 1 (a que enganou):** o grafico tem 20 barras mas so 10 rotulos. Em
  `echarts_option.js`, o eixo de categoria da barra **horizontal** nao tinha
  `interval: 0` (a vertical tinha), entao o ECharts escondia um rotulo sim outro
  nao quando nao cabiam todos. A barra de 65 ficou anonima e o unico rotulo com
  "Mococa" visivel era o da vizinha "Mococa Sp = 2". Dai a leitura.
- **Causa 2:** o transform `normalizar_cidade` so tirava sufixo de UF **com
  barra** (`/SP`) e nao ignorava acento, entao "Mococa Sp" e "Sumare" viravam
  fatias separadas de "Mococa" e "Sumaré".
- **Output:**
  - `apps/relatorios/static/relatorios/echarts_option.js`: `interval: 0` no eixo
    de categoria horizontal, fonte menor a partir de 15 categorias, rotulo longo
    truncado (nome inteiro segue no tooltip) e `grid.bottom` reduzido de 50 pra
    24 na horizontal, onde o eixo de baixo so tem numeros e aqueles 50px eram
    altura desperdicada, justamente o que faltava pros rotulos caberem.
  - `apps/relatorios/query_builder.py`: `normalizar_cidade` agora tira UF com
    qualquer separador (barra, hifen, virgula ou espaco) e agrupa ignorando
    acento, mas **exibe a grafia mais usada do grupo**, pra "Sumaré" nao virar
    "Sumare" na tela. Constante `_UFS_RE` com a lista real de UFs em vez de
    `[a-z]{2}`, pra nao amputar cidade que termine em duas letras (Cotia, Bauru).
  - `tests/test_relatorios_query_builder.py`: arquivo estava vazio, agora com 10
    casos do transform.
- **Efeito medido nos dados reais da Nuvyon:** 20 fatias viram 18. Mococa 65 ->
  67, Sumaré 22 -> 23.
- **Achados registrados, NAO corrigidos aqui:**
  1. O widget so enxerga 348 dos 1135 leads, porque 788 (69%) estao **sem
     cidade** e o filtro do widget e `cidade existe`. Esses somem calados, o que
     faz o grafico parecer completo. Mesma causa raiz do bloco A: a cidade so e
     preenchida quando o endereco e completado no Hubtrix, e no geral o cadastro
     e completado no HubSoft.
  2. Widget #77 "Vendas por cidade" esta com `agrupamento={}`, entao em vez de
     barras por cidade devolve uma barra unica "Total: 1129". Esta no painel da
     Nuvyon.
- **Status:** completed (as duas causas); pending (os dois achados acima)
