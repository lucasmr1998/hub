# Execution Log — Modulo CS

Trilha do que foi executado no modulo de Customer Success (clube, parceiros, indicacoes, carteirinha, retencao, nps). Entrada mais nova embaixo.

## 2026-07-10 — Diagnostico UX + CTO (Playwright local)

- Acao: diagnostico duplo (UX + CTO) do modulo CS (legado migrado do megaroleta) via Playwright em ambiente local, tenant Nuvyon com seed (30 membros, 6 parceiros, 12 cupons, 15 indicacoes). 32 screenshots cs_*. Nenhum toque em prod, nenhuma alteracao de codigo de produto.
- Bugs 500 confirmados em runtime: `/cs/clube/dashboard/config/` (IntegrityError: RoletaConfig.objects.get_or_create(id=1) hardcoded, model TenantMixin => colide na PK entre tenants + escreve em GET); `/cs/clube/membro/` (NoReverseMatch: redirect('roleta_index') sem namespace clube: + template estende 'roleta/membro/base_membro.html' inexistente); `/cs/clube/` preso em "Carregando ambiente..." (404 no console).
- Achados P0 (multi-tenancy): superficie publica do clube (landing/OTP/cupom/roleta) roda com tenant None sobre TenantManager fail-open (managers.py:28-35) => enxerga o banco inteiro. `landing_clube` (core_views.py:10) faz `.first()` sem tenant => Nuvyon exibe "Clube Megalink" (marca de outro cliente). `validar_otp` (api_views.py:580) busca CPF sem tenant. `validar_cupom` (parceiros/views.py:358) publico muta estado sem auth. Webhooks OTP/consulta HubSoft hardcoded compartilhados por todos os tenants (otp_service.py:5, hubsoft_service.py:26). HubsoftService do clube com credencial global unica e cache key sem sufixo de tenant.
- Achados P1: login_url='/roleta/dashboard/login/' morto em 15 views (+4 com /parceiro/login/ errado); views CS so @login_required sem checar acesso_cs (e test_module_access.py codifica o fail-open como esperado).
- Achados UX: menu com 19 itens, "Indicacoes" e "Parceiros" duplicados com mesmo icone, matchers por substring destacam 2 ao mesmo tempo; vocabulario de roleta (Giros/Premios/Assets) exposto ao usuario; CPF completo em texto claro + saldo editavel inline sem trilha; mobile inutilizavel; marca "Megalink" default em models/views/templates. Proposta de menu de 19 -> 14 itens no doc.
- Codigo morto: nps (urlpatterns vazio, nao incluido no urls raiz) com tabelas migradas em prod; retencao/models.py (ScoreCliente/AlertaChurn orfaos, views usam model do CRM). jQuery 1.10.2 + .zip commitado em static.
- Output: doc `robo/docs/context/reunioes/diagnostico_ux_cto_relatorios_cs_10-07-2026.md` (achados P0-P3 + menu proposto + estrategia de testes + tarefas propostas). Aguardando aprovacao do Lucas pra criar tarefas Workspace e executar.
- Status: completed (diagnostico); pending (execucao dos fixes)

## 2026-07-12 — Reestruturacao do menu CS (sidebar + tabs)

- Acao: sidebar do CS reduzida de 19 links soltos (5 secoes) para 8 itens em 3 grupos (Clube: Visao geral, Membros, Carteirinhas | Fidelizacao: Indicacoes, Parceiros, Sorteios | Sistema: Relatorios, Aparencia, Configuracoes). Cada area com sub-paginas ganhou uma faixa de abas (navegacao por link, estilo tabs-line do DS) renderizada no topo da pagina.
- Resgate de orfas: as 8 telas que existiam mas tinham sumido do menu na migracao do megaroleta voltaram como aba (Carteirinha: Modelos/Regras; Indicacoes: Lista/Indicados/Pagina publica; Parceiros: Resgates; Configuracoes: Cidades/Documentacao). Categorias movida pra area Parceiros.
- Vocabulario: Giros->Sorteios, Assets/"Visual da roleta"->Visual, Gamificacao->Niveis e missoes (labels de menu; conteudo das paginas nao mexido ainda).
- Fix de bug: matchers de item ativo agora usam url_name exato (antes eram substring: 'indica'/'parceiro' destacavam 2 itens ao mesmo tempo).
- Arquivos: `templates/partials/sidebar_subnav.html` (bloco cs reescrito), novo `templates/partials/cs_subtabs.html`, `templates/layouts/layout_app.html` (include central gated modulo_atual=='cs'), `templates/partials/_components_styles.html` (a.tabs-item text-decoration none + .cs-subtabs). Zero mudanca em views/urls/models.
- Validacao: manage.py check ok; 19 telas capturadas via Playwright local (200 em todas), sidebar e faixas conferidas visualmente. So local, sem push.
- Pendente: a area Configuracoes cai em dashboard_config, que ainda da 500 (P0-4 do diagnostico, get_or_create(id=1) singleton); nao e regressao (o menu antigo tambem apontava pra la). Precisa do fix P0-4. Tarefa Workspace T-P2-A a criar apos aprovacao.
- Status: completed (local, aguardando analise do Lucas)
