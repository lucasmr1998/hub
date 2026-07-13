# Execution Log — Modulo Decks (Apresentacoes)

Editor de apresentacoes (slides) montadas a partir dos widgets do modulo de relatorios. Entrada mais nova embaixo.

## 2026-07-13 — MVP do editor de deck (Frente A, C1a-C1d)

- Contexto: os numeros do painel sao usados em reuniao; o dono quis um editor de "deck" dentro do Hubtrix pra montar apresentacoes a partir dos widgets e apresentar em tela cheia. MVP: editor manual (arrasta blocos) + reordenar slides + Apresentar fullscreen + snapshot. Export PDF DEFERIDO (decisao do dono).
- App novo `apps/decks/` (TenantMixin no Deck; Slide/SlideBloco via FK, padrao Widget). Models: Deck (nome, tema, snapshot_em, compartilhado), Slide (ordem, titulo), SlideBloco (tipo widget|texto|kpi|imagem|titulo_secao, FK relatorios.Widget SET_NULL, dados_snapshot, conteudo, layout, estilo). db_table decks_*.
- Reuso da engine de relatorios (chave do MVP): `services.dados_widget` roda `WidgetQueryBuilder(...).build().to_dict()` (mesmo motor do dashboard). `deck_render.js` COPIOU as funcoes puras de render (montarOptionEcharts, PALETTE, fmt*) de dashboard_detalhe.html — DIVIDA: extrair pra static compartilhado quando for tocar o dashboard.
- Canvas: GridStack v9 (grade 16:9, cellHeight = altura/9). Persistencia espelha api_dashboard_layout. Editor em 3 colunas (tira de slides via SortableJS, canvas, biblioteca de blocos).
- Snapshot: botao "Congelar" roda o builder por bloco widget e grava dados_snapshot + snapshot_em. Editor usa dados ao vivo (api_bloco_widget_dados); Apresentar usa o snapshot congelado.
- Apresentar: `apresentar.html` estende layouts/base.html (block body), fullscreen sem chrome, slides via json_script, 1 slide/vez escalado 16:9, navegacao por teclado (setas/espaco/esc/F).
- Permissoes: decks.ver_decks/criar_deck/compartilhar_deck no seed_funcionalidades (registradas sob o modulo 'relatorios' pra aparecer na UI de perfis). Gate _perm + multi-tenant via Deck.
- Rotas: /decks/ (lista), /decks/criar/, /decks/<pk>/editar/, /decks/<pk>/apresentar/, /decks/<pk>/excluir/ + APIs (deck/slide/bloco/layout/congelar/widget_dados/widgets_disponiveis).
- Validado dev (Playwright, e2e_diag): criar deck, adicionar titulo + 3 widgets (KPI/pizza/linha reusando ECharts), congelar, apresentar fullscreen. 0 erros de console. Migration 0001 aplicada.
- Pendente: C1e PDF (fast-follow, WeasyPrint + captura de grafico como imagem, quando o dono pedir); edicao inline de texto/kpi/estilo mais rica; upload de imagem; entrada na sidebar; deploy prod (migration sobe via rebuild) com confirmacao.
- Arquivos: apps/decks/* (models/views/urls/admin/apps/services/static/templates/migrations), settings.py, urls.py, seed_funcionalidades.py.
- Status: completed (MVP dev). Deploy pendente de confirmacao.

## 2026-07-13 — Identidade visual (marca do tenant) + modelos de slide + paleta de grafico

- Motivacao do dono: (1) "as apresentacoes precisam ter modelos de identidade visual, o cliente vai personalizar"; (2) "os graficos dos relatorios antigos parecem bem mais bonitos".
- Causa do (2), achada no codigo: a paleta nova era PASTEL de baixa saturacao e as barras usavam todas a MESMA cor palida (PALETTE[0]); o legado (Chart.js) usava categorica saturada (#2563eb/#10b981/#f59e0b/...). Nao era impressao.
- Paleta agora sai da MARCA do tenant: `apps/relatorios/branding.paleta_tenant()` monta [cor_primaria, cor_secundaria, ...categorica saturada] a partir de `sistema.ConfiguracaoEmpresa` (que JA tinha cor_primaria/cor_secundaria/logo — zero migration). Serie unica (barra/linha) sai na cor do cliente.
- DIVIDA PAGA: motor de grafico extraido pra `apps/relatorios/static/relatorios/echarts_option.js` (PALETTE, fmt*, esc, montarOptionEcharts). Removidas 156 linhas duplicadas do dashboard_detalhe.html e as copias do deck_render.js. A paleta vive num lugar so e vale pro dashboard E pro deck (via window.CHART_PALETTE injetado pela view).
- Identidade do deck: `services.tema_deck(deck, tenant)` herda a marca (logo, cores, fonte, nome) e o deck sobrescreve pontualmente (Deck.tema). Aplicado por CSS vars (--deck-fundo/texto/primaria/fonte) no canvas do editor e no slide do Apresentar; logo da empresa no canto do slide. Modal "Tema" no editor (cor principal, fundo, mostrar logo) + "voltar pra marca da empresa".
- Modelos de slide: `apps/decks/modelos.py` com 6 modelos (branco, capa, secao, kpis, duas_colunas, grafico_comentario). "+ Slide" abre picker; os blocos ja nascem posicionados. Slot de grafico nasce SEM widget e o editor mostra "Escolher widget" (clicavel) -> picker preenche o slot.
- Status: codigo pronto, `manage.py check` limpo. PENDENTE VALIDAR: Docker Desktop estava parado (banco local fora), entao nao rodou Playwright. Validar editor/apresentar + a cor nova antes de subir.

## 2026-07-13 — Fix: modais do editor estavam sem o painel (classe errada)

- **Sintoma** (reportado pelo dono, com print): todos os modais do deck apareciam sem fundo. So os cards internos e o overlay escuro apareciam; o titulo ficava cinza sobre o escuro, ilegivel.
- **Causa**: escrevi o markup com `.modal-content`, que e a classe do **CSS legado** (`apps/sistema/static/sistema/css/dashboard.css:705`), carregado pelas 33 paginas antigas. O editor do deck estende `layouts/layout_app.html`, que traz o DS atual (`partials/_components_styles.html`), onde o painel e `.modal` + `.modal-sm|md|lg` (`.modal-overlay > .modal`). Resultado: nenhuma regra pintava o painel.
- **Fix**: `.modal-content` -> `.modal .modal-lg|md` nos 3 modais (modelos, tema, widget); `style="display:none"` -> atributo `hidden` (o padrao do DS, que o `abrirModal/fecharModal` do layout ja manipula); removidos os estilos inline de `modal-footer` (padding/border-top ja vem do DS). `modelo-grid` fixado em 3 colunas (com auto-fill os 6 modelos quebravam 4+2 dentro do modal-lg).
- **Licao**: o projeto tem DOIS sistemas de modal vivos. Em pagina que estende `layout_app`, usar SEMPRE `components/modal.html` (ou copiar a marcacao dele). `.modal-content` so funciona em quem carrega o `dashboard.css` legado.
- **Validado** (Playwright, dev): painel com `rgb(255,255,255)`, radius 12px, 800px; 6 cards de modelo renderizam; fecha com `hidden`+`display:none`; 0 erros de console.
- **Arquivos**: `apps/decks/templates/decks/editor.html`.
- **Status**: completed (dev). Deploy pendente.
