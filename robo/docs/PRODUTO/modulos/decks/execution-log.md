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
