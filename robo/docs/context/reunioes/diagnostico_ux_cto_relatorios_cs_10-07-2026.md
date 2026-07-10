# Diagnostico UX + CTO: modulos Relatorios e CS (10/07/2026)

> Metodo: Playwright em ambiente LOCAL (banco `aurora_dev`, tenant Nuvyon com seed
> realista) + 2 agentes de diagnostico com persona (UX e CTO) lendo os 41 screenshots
> e o codigo. **Zero toque em producao, nem SELECT.** Nenhum arquivo de produto foi
> editado. Este doc so descreve achados e propoe plano; nada foi aplicado.

**Evidencias (screenshots):** `robo/dashboard_comercial/gerenciador_vendas/tests/e2e/screenshots/diagnostico_ux_cto/20260710_203331/`
(prefixo `rel_*` = modulo Relatorios, `cs_*` = modulo CS; `log_captura.json` = status HTTP + erros de console por pagina).

**Seed local:** 222 leads, 167 oportunidades (38 ganhas, 38 perdidas com motivo), 272 atendimentos,
30 membros de clube, 6 parceiros, 12 cupons, 15 indicacoes, e o Painel Executivo reconstruido
localmente com 18 widgets (todos validados com dado real no `WidgetQueryBuilder`).

---

## 0. Resumo executivo

O modulo de **Relatorios** e o mais maduro do produto: infra declarativa boa, layout no
design system. Os problemas sao de **confiabilidade percebida** (filtros que nao aplicam,
KPIs sem unidade) e **isolamento multi-tenant** (Widget sem tenant proprio).

O modulo de **CS** e um legado do "megaroleta" migrado pela metade. Carrega tres dividas
graves: **jornadas do assinante quebradas** (500s), **marca de outro cliente vazando no tenant
errado** ("Clube Megalink" na landing da Nuvyon), e **falhas estruturais de multi-tenancy**
na sua superficie publica (landing, OTP, cupom, roleta rodam com tenant None sobre um
`TenantManager` fail-open, enxergando o banco inteiro).

A causa raiz que amplifica quase tudo no CS: **o tenant so e resolvido a partir do usuario
logado** (`middleware.py:84-93`), e o `TenantManager` e **fail-open** (`managers.py:28-35`:
sem tenant no contexto, retorna linhas de todos os tenants). Toda pagina publica do CS roda
sem tenant e ve o banco inteiro.

Contagem de achados: **7 P0 (critico)**, **8 P1/P2 tecnicos**, **26 achados de UX**
(12 relatorios + 14 CS). Bugs 500 confirmados em runtime: 2.

---

## 1. Achados P0 (critico: seguranca / vazamento de dados entre tenants)

Todos confirmados lendo arquivo:linha nesta sessao.

| # | Achado | Evidencia | Cenario de falha |
|---|---|---|---|
| **P0-1** | Superficie publica do clube sem resolucao de tenant. `landing_clube` faz `LandingConfig.objects.first()` sem tenant; anonimo => manager fail-open retorna config de qualquer tenant, ou None e cai no default "Clube Megalink". Vale tb pra banners/categorias/parceiros/cidades. | `apps/cs/clube/views/core_views.py:10-17`; runtime cs_28 | Cliente da Nuvyon abre a landing e ve marca, WhatsApp e premios de OUTRO provedor |
| **P0-2** | Auth de membro e OTP cross-tenant. `validar_otp` busca `MembroClube.objects.filter(cpf=...)` sem tenant. CPF em 2 tenants => loga no membro errado. Linhas com `tenant=request.tenant` em request publico filtram `tenant IS NULL` (quebrado dos 2 lados). | `apps/cs/clube/views/api_views.py:580` (e 49,202,746,771) | Vazamento de pontos, cupons e PII de membro entre provedores concorrentes |
| **P0-3** | Escrita cross-tenant em widgets. `Widget` e `models.Model` puro, **sem FK tenant**. `api_widget_excluir` busca por pk global e valida so `criado_por` + permissao de papel, nunca `dashboard.tenant == request.tenant`. Leitura idem (`api_widget_config`, `api_widget_dados` aceitam widget compartilhado de outro tenant). | `apps/relatorios/models.py:103`; `views.py:379-384`, `41-47`, `282-286`, `320-323` | Admin do tenant B enumera IDs e exclui/le config de widgets do tenant A. **Unico cross-tenant exploravel por usuario autenticado comum hoje.** |
| **P0-4** | Singleton global `RoletaConfig id=1` com escrita em GET. `get_or_create(id=1)` num model `TenantMixin`: 2o tenant colide na PK => IntegrityError 500. E escreve no banco em GET. | `apps/cs/clube/views/dashboard_views.py:366`; runtime cs_07 (500) | 1o tenant "sequestra" a config; os demais nao conseguem configurar o clube |
| **P0-5** | Webhooks N8N hardcoded compartilhados por todos os tenants (`roletacodconfirmacao`, `roletaconsultarcliente` no host da v4riem). | `apps/cs/clube/services/otp_service.py:5`; `hubsoft_service.py:26` | CPF/telefone de clientes de qualquer tenant trafegam pela instancia N8N de um cliente especifico (LGPD + acoplamento). Existe `IntegracaoAPI` por tenant pra isso, nao usado |
| **P0-6** | Conexao direta ao banco do ERP com credencial global unica e cache key global. `psycopg2.connect` com env `HUBSOFT_DB_*` do processo, sem tenant; cache key `'hubsoft_clientes_por_cidade'` sem sufixo. | `apps/cs/clube/services/hubsoft_service.py:9-19,183` | Desenho single-tenant num produto multi-tenant. Dano contido hoje (so Nuvyon tem HubSoft ativo), bloqueador pro 2o tenant |
| **P0-7** | `validar_cupom` publico muta estado sem auth. Da baixa em cupom (`status='utilizado'`) sem login/tenant/rate-limit pra quem souber o `codigo_unico`; a busca retorna dados de membro cross-tenant. | `apps/cs/parceiros/views.py:358-403` | Script de forca bruta queima cupons de membros de qualquer tenant |

**Nota de infra que amplifica P0-1/2/7:** `TenantManager` fail-open (`apps/sistema/managers.py:28-35`)
+ tenant resolvido so do usuario logado (`apps/sistema/middleware.py:84-93`).

---

## 2. Achados P1 / P2 (tecnicos, alto e medio)

| # | Sev | Achado | Evidencia |
|---|---|---|---|
| P1-1 | Alto | Area de membro do clube 100% quebrada. `redirect('roleta_index')` sem namespace `clube:` (=> NoReverseMatch 500, cs_29). Latente irmao: template estende `'roleta/membro/base_membro.html'` inexistente (existe `clube/membro/`), entao membro logado tomaria TemplateDoesNotExist. Nunca exercitada apos migracao. | `apps/cs/clube/views/membro_views.py:25,42`; `templates/clube/membro/hub.html:1` |
| P1-2 | Alto | `login_url` morto em 19 views. 15x `login_url='/roleta/dashboard/login/'` (rota `/roleta/` nao existe no urls raiz) + 4x `login_url='/parceiro/login/'` (real e `/cs/parceiros/parceiro/login/`). | parceiros/indicacoes/carteirinha views; `views_painel.py:54,111,155,186` |
| P1-3 | Alto | Controle de acesso do CS depende de fail-open de permissao. Views so `@login_required`, sem checar `perfil.acesso_cs`. `PermissaoMiddleware` deixa passar usuario sem `PermissaoUsuario` (retrocompat), e `test_module_access.py:44-71` **codifica isso como esperado** (protege a regressao errada). | `apps/sistema/models.py:385-388`; `middleware.py:131,171-174` |
| P1-4 | Alto | Relatorios com tenant None viram consulta global. `_base_queryset` so filtra `if self.tenant`; usuario sem perfil + fail-open => widget agrega todos os tenants. | `apps/relatorios/query_builder.py:169-174` |
| P2-1 | Medio | Par `facebook`/`organico` hardcoded como taxonomia de canais em 6 pontos + view + template. "Organico" = "nao facebook". Tenant que anuncia no Google nao segmenta. | `query_builder.py:141-146,210-213,348-360,430-437,502-507`; `views.py:296` |
| P2-2 | Medio | Literais de dominio no funil: status `'fluxo_inicializado'` cravado como "atendimento"; etapa `'Endereco Validado'` como default (mitigado: configuravel via `agrupamento.etapa_viabilidade`). | `query_builder.py:363,446` |
| P2-3 | Medio | Escrita em GET tb nos outros singletons de CS (`IndicacaoConfig`, `LandingConfig`), com defaults Megalink. | `apps/cs/indicacoes/models.py:7-12`; `apps/cs/clube/models.py:228-236` |
| P2-4 | Medio | Codigo morto com tabela viva: `nps` (`urlpatterns=[]`, nao incluido no urls raiz) mas com models migrados em prod; `retencao/models.py` (`ScoreCliente`, `AlertaChurn` orfaos; views usam model do CRM). | `apps/cs/nps/`; `apps/cs/retencao/models.py` |
| P2-5 | Medio | jQuery 1.10.2 (2013, CVE-2015-9251 e cia) em pagina publica + `.zip` binario commitado em static. | `apps/cs/clube/static/clube/js/jquery-1.10.2.js`; `.../images/Roleta Premios Virtuais.zip` |

---

## 3. Achados de UX

### 3.1 Relatorios (12 achados)

**Alto impacto**
- **R1. Filtros globais nao aplicam nem refletem o estado da URL.** `rel_03` (`?dias=7`) e `rel_04` (`?fonte=facebook`) sao identicos a `rel_02`: mesmos 120 leads / 88 ops / 26 vendas, chip continua "Padrao"/"Todas". Agravante: `fonte=facebook` nem existe como opcao (so Todas/Meta Ads/Organico), mas os graficos mostram whatsapp/site/facebook/telefone/indicacao/google. Filtro que parece aplicado e nao muda nada destroi a confianca no painel inteiro.
- **R2. Mobile inutilizavel.** `rel_06`: grid mantem 4 colunas no viewport mobile, KPIs cortados ("120", "Conve geral", "778"), barra de filtros estoura, funil ilegivel. O dono do provedor abre exatamente no celular.
- **R3. KPIs sem unidade.** `rel_02`: "Conversao geral 21,7" (sem %), "Receita gerada 2.778,2" (sem R$), "Ticket medio 106,85" (sem R$).

**Medio impacto**
- **R4. Funis com problema de leitura**: ultimo degrau do "Funil do mes" cortado na borda; "Funil com viabilidade" ordenado por valor e nao por etapa (Ganho no topo do funil nao faz sentido). `rel_02`
- **R5. "Gargalo do funil" ilegivel**: rotulos 45 graus, primeiro cortado, eixo Y espremido. `rel_02`
- **R6. Consultora sem nome vira barra "—"** (5 vendas sem responsavel escondidas atras de um traco). `rel_02`
- **R7. Duplicidade Relatorios vs Dashboards na sidebar** (2 itens vizinhos, so icones, quase iguais). `sidebar.html:55-61`, `rel_01`
- **R8. Wizard comeca por "qual tabela" e nao "qual pergunta"** (11 fontes com jargao de dev, sigla TMA sem expandir). `rel_08`

**Baixo impacto**
- R9. Modo edicao sem affordance de estado; lixeira colada no lapis. `rel_07`
- R10. Modal "?" cumpre pouco (nao diz regra de contagem, fonte nem periodo). `rel_05`
- R11. Acentuacao inconsistente na mesma tela ("PERIODO"/"Padrao"/"Organico" acentuados ao lado de "Conversao"/"Instalacoes" sem acento). `rel_02`
- R12. Lista com 8 chips de setor pra 1 dashboard so. `rel_01`

### 3.2 CS (14 achados)

**Alto impacto**
- **C1. Tres jornadas quebradas, duas do assinante final**: (a) `/cs/clube/dashboard/config/` 500 IntegrityError com pagina de debug exposta (cs_07); (b) `/cs/clube/membro/` 500 NoReverseMatch (cs_29); (c) `/cs/clube/` preso pra sempre em "Carregando ambiente..." (cs_27, 404 no console).
- **C2. Marca de OUTRO cliente exposta no tenant Nuvyon**: landing publica inteira "Clube Megalink" (cs_28), form de config preenchido com "Clube Megalink" (cs_09), default Megalink no visual de indicacao (cs_19). A carteirinha prova que da pra fazer certo: usa "Clube Nuvyon" (cs_24).
- **C3. Menu com 19 itens, duplicacoes e estado ativo quebrado**: "Indicacoes" e "Parceiros" duas vezes com mesmos icones (`sidebar_subnav.html:154-225`); matchers por substring (`'indica' in url_name`) destacam os dois ao mesmo tempo (cs_13, cs_14); Configuracoes fica abaixo do fold; paginas de Carteirinha sem item ativo (cs_24-26).
- **C4. Vocabulario de roleta exposto em todas as camadas**: "Visual da roleta" (cs_06), "Relatorios da roleta"/"Top 10 jogadores" (cs_12), "Historico de giros" (cs_04), "+20 giros" (cs_08), e ate a URL publica que o assinante compartilha `.../roleta/indicar/...` (cs_18). O produto vende "clube de vantagens".
- **C5. Mobile do CS inutilizavel**: sidebar (60px) + subnav (240px) fixos e abertos deixam ~90px pro conteudo; sem hamburger. "Dashboa do clube", "Validac WhatsA". cs_31
- **C6. Tabela de Membros com dados crus e acoes perigosas**: coluna Cidade exibe literal "None" (30 linhas); CPF completo em texto claro (LGPD); "Saldo de pontos" editavel inline sem confirmacao/undo/trilha; sem paginacao. cs_02

**Medio impacto**
- C7. Jargao tecnico na UI da operadora ("Gatilho sistemico" em texto livre, slug interno em monospace, "fas fa-tag" literal na coluna Icone, "Executar scanner"). cs_08, cs_11, cs_15
- C8. Dois design systems convivendo + restos de um terceiro (dropdown "Periodo:" vs chips; inputs "Choose File" nativos; botao primario sem rotulo em cs_25; portal do parceiro roxo fora dos tokens em cs_30). 
- C9. Graficos zerados com eixo 0 a 1,0 fracionario em vez de empty state. cs_12,13,16,20
- C10. Redundancias e recortes de tabela (KPIs repetidos cs_16/cs_17; cupons com coluna Acoes clipada cs_22; TIPO=CONDICAO redundante cs_26).
- C11. Cadastro de cidade em texto livre ("Ex: Teresina"), origem estrutural do "None" e das variantes de grafia. cs_05

**Baixo impacto**
- C12. Typo "2 cupomns disponiveis" em pagina publica (6 cards). cs_28
- C13. KPI "Taxa de conversao" sem valor (cs_13); "0.0%" mistura ponto com virgula do resto (cs_16).
- C14. Campos nulos como "—" mudo sem tratamento ("Sem cidade"). cs_13,16,17

### 3.3 Menu CS proposto (de 19 pra 14 itens, sem duplicacao)

```
Customer Success
  Visao geral            (Dashboard do clube, KPIs em linguagem de clube)
  Membros
  Retencao
INDICACOES
  Painel de indicacoes   (funde home + lista, KPIs sao os mesmos)
  Links dos membros
  Pagina de indicacao
PARCEIROS E CUPONS
  Parceiros
  Cupons                 (Resgates como tab interna, nao pagina orfa)
  Categorias
SORTEIOS E GAMIFICACAO
  Premios
  Sorteios               (atual Giros)
  Niveis e missoes       (atual Gamificacao)
PAGINA PUBLICA DO CLUBE
  Landing e aparencia    (funde Landing + Banners + Assets em tabs)
  Carteirinhas
CONFIGURACOES
  Configuracoes do clube (Cidades como secao em select)
```
Corrigir os matchers de item ativo pra `url_name` exato (fim do duplo destaque). Relatorios saem do menu lateral (viram tabs ou dashboards no modulo novo, setor Customer Success ja existe).

---

## 4. Avaliacao de arquitetura (Relatorios)

**Bom.** Registry declarativo (`data_sources.py`) e a decisao certa: schema whitelisted por
`FieldSpec`, validacao de campo antes de filtrar (`query_builder.py:176-179`), operadores num
dict fechado (`OPERADORES_VALIDOS`), zero SQL cru, lazy import de model. Container Dashboard +
Widget declarativo em JSON e o padrao de mercado (HubSpot/Metabase).

**Onde racha: os transforms.** O contrato declarativo vale ate ~linha 300. Dali, `_aplicar_transform`
e um bloco de ~394 linhas com 7 transforms que **importam direto** `apps.comercial.*`, **ignoram
o queryset** que o pipeline montou ("IGNORA o queryset" esta nas docstrings) e reimplementam
janela/fonte cada um. Na pratica sao **dois engines no mesmo arquivo**: um generico declarativo e
um conjunto de relatorios fixos do funil comercial disfarcados de transform. Recomendacao: transform
como classe registrada (slug, data_sources_suportados, contrato de janela/fonte herdado).

**Estado mutavel escondido.** Transforms se comunicam por atributos de instancia
(`self._funil_detalhe`, `self._macro_meta`, `self._transform_meta`) e um chama o outro por recursao
(`funil_viabilidade` -> `funil_cumulativo`). Funciona por request, mas e fragil e nao testavel isolado.

**Sem cache.** Zero cache no modulo. Cada load de dashboard = 1 request por widget; `funil_cumulativo`
puxa todos os `op_ids` e o historico inteiro pra memoria e processa em Python. Passa no volume atual;
com um tenant de 50k oportunidades, um dashboard de 8 widgets vira 8 varreduras de historico por
refresh. Recomendacao: cache por `(tenant, widget, overrides)` TTL 60-300s antes de otimizar query.

---

## 5. Inventario de hardcode classificado

**(a) Valor de negocio que deveria ser config por tenant** (prioridade de correcao):
- Marca "Megalink" em defaults de model/migration (`clube/models.py:230,233`, `indicacoes/models.py:7,12`, `carteirinha/models.py:29`), views (`dashboard_views.py:369`, `indicacoes/views.py:185`, `carteirinha/views.py:55,113,164`, `api_views.py:140`) e ~10 templates (landing, email_base com "Conectando o Piaui e Maranhao", membro, base do dashboard, validar_cupom, carteirinha).
- Webhooks N8N por tenant (`otp_service.py:5`, `hubsoft_service.py:26`) => `IntegracaoAPI`.
- Taxonomia facebook/organico (P2-1) => catalogo por tenant (choices dinamicos do campo `fonte`).
- Etapa 'Endereco Validado' e status 'fluxo_inicializado' (P2-2).

**(b) Constante tecnica aceitavel, mas merece settings/constante nomeada:**
- Janela 30 dias, top 50, minimo 3 leads, top 12 canais (`query_builder.py:119,272,522,524`).
- Timeout 10s, TTL cache 3600s (+ cache key precisa sufixo de tenant), porta ERP '9432' (`otp_service.py:25`, `hubsoft_service.py:16,183`).

**(c) Cosmetico:**
- `PALETTE` e cores hex inline no JS do `dashboard_detalhe.html` (415, bloco 500-733); URLs `/dashboards/` cravadas no JS (deveriam ser `{% url %}`); CDNs pinados sem fallback (gridstack@9, echarts@5.5.0).

---

## 6. Plano de acao priorizado

Ordem de ataque recomendada (assinante primeiro, depois operadora, depois confianca/mobile).
Esforco: P (pequeno, horas), M (medio, 1-2 dias), G (grande, decisao de arquitetura).

### P0 — Seguranca / dados (fazer antes de qualquer melhoria cosmetica)

| Bloco | Itens | Esforco | Bloqueia |
|---|---|---|---|
| **FK tenant no `Widget` + checagem nas `api_widget_*`** | P0-3 | M | unico cross-tenant exploravel por usuario comum hoje. Comeca por AQUI |
| **Fixes 500 do CS na cara do cliente** | P1-1 (NoReverseMatch + template base), P0-4 (RoletaConfig get_or_create por tenant, fim da escrita em GET), P2-3 (LandingConfig/IndicacaoConfig idem) | P | operadora e assinante |
| **Branding Megalink => config por tenant** | item 5a marca (defaults, views, templates, emails) | M | risco de marca cruzada, o achado mais constrangedor perante o cliente |
| **Webhooks OTP/consulta => `IntegracaoAPI` por tenant** | P0-5 | M | **bloqueador de LGPD/contrato pra onboarding de qualquer tenant novo no CS** |
| **Auth do `validar_cupom`** | P0-7 | P a M | painel do parceiro ja existe e ajuda |
| **Multi-tenant do `HubsoftService` do clube** | P0-6 (credencial via IntegracaoAPI, cache key por tenant) | M | `HubsoftService` moderno em `apps/integracoes` serve de referencia |
| **Resolucao de tenant em rota publica + fail-close do manager em contexto publico** | P0-1, P0-2 | **G** | decisao de arquitetura do SaaS. Pre-requisito real pra vender o clube pro 2o provedor |

### P1 — Hardcode de negocio + acesso

- `login_url` mortos nas 19 views (P1-2) — **P**
- Corrigir/endurecer `test_module_access.py` + checar `acesso_cs` nas views CS (P1-3) — **M**
- Taxonomia de fontes configuravel + literais de dominio (P2-1, P2-2) — **M**
- Relatorios com tenant None (P1-4) — cai junto com o fix do manager

### P2 — UX / menu CS

- Reorganizacao do menu CS (secao 3.3) + matchers de ativo — **M**
- Formatar KPIs com unidade (R$/%) + "Sem cidade"/"Sem responsavel" no lugar de None/— (R3, R6, C6, C14) — **P**
- Sincronizar chips de filtro com querystring + opcoes de Fonte do dado real (R1) — **P a M**
- Mobile de relatorios e CS (1 coluna < 768px, drawer no CS) (R2, C5) — **M**
- Vocabulario de clube no lugar de roleta (C4) + rota publica neutra — **M**
- Empty state de grafico, funis legiveis, wizard por template (R4, R5, R8, C9) — **M**

### P3 — Limpeza / divida

- Remover nps e retencao mortos (drop de tabela com cuidado em prod) (P2-4) — **P**
- jQuery legado + `.zip` em static (P2-5) — **P**
- Tokens do DS no JS de relatorios, `{% url %}` no lugar de path cravado, fallback de CDN (secao 5c) — **P a M**
- Cache por `(tenant, widget, overrides)` no query builder (secao 4) — **M**

### Top 5 quick wins (alto impacto, baixo esforco)
1. Consertar as 3 jornadas quebradas do CS (cs_07, cs_27, cs_29).
2. Trocar todo default "Megalink" pelo nome do tenant + corrigir typo "cupomns".
3. Formatar KPIs do Painel Executivo com unidade + tratar None/—.
4. Sincronizar chips de filtro com a querystring (opcoes de Fonte do dado real).
5. Pente fino nos rotulos do menu CS + matchers de ativo + botao vazio de cs_25.

---

## 7. Estrategia de testes minima (por risco, nao por cobertura)

1. **Isolamento de tenant nas APIs de widget** (primeiro): tenant B recebe 403/404 em `api_widget_dados/config/excluir` de dashboard do tenant A. Hoje FALHA — trava o fix do P0-3 e vira regressao permanente. Padrao: `test_tenant_isolation.py`.
2. **Smoke publico do clube por tenant**: requests anonimos a `/cs/clube/`, `/clube/`, `/membro/` com 2 tenants; sem 500 (pega NoReverseMatch e IntegrityError) e config = tenant resolvido.
3. **Contrato do query_builder por transform** (7 transforms, dataset fixo, assert de labels/data): 700 linhas de logica densa com zero teste; refactor da secao 4 e cego sem isso.
4. **Corrigir `test_module_access.py`**: inverter expectativa (sem `acesso_cs` => 403) e decidir fail-close.
5. **`validar_cupom` + OTP**: baixa de cupom exige vinculo correto; OTP nao loga membro de outro tenant.
6. **Operadores + validacao de campo do builder** (tabela parametrizada, campo/operador invalido ignorado sem excecao).

E2E Playwright fica DEPOIS: o log de captura pegou os 500 sem browser (smoke de status code basta).

---

## 8. Tarefas Workspace propostas (criar apos aprovacao do Lucas)

> Workspace vive no banco de prod. Nesta sessao NAO criei/atualizei tarefa nenhuma.
> Proposta pra criar depois que voce validar os achados (tenant Aurora HQ, projeto 4, responsavel 20):

- **T-P0-A** Isolamento multi-tenant do Widget (FK tenant + checagem nas api_widget_*) + teste de isolamento. [P0, M]
- **T-P0-B** Fixes 500 do CS: area de membro (NoReverseMatch + template), RoletaConfig/LandingConfig/IndicacaoConfig por tenant sem escrita em GET. [P0, P]
- **T-P0-C** Branding por tenant (matar defaults "Megalink" em models/views/templates/emails). [P0, M]
- **T-P0-D** Webhooks OTP/consulta cliente do clube => IntegracaoAPI por tenant. [P0, M] (bloqueador de onboarding CS)
- **T-P0-E** Auth do validar_cupom + isolamento do resgate. [P0, P-M]
- **T-P0-F** Multi-tenant do HubsoftService do clube (credencial + cache key por tenant). [P0, M]
- **T-P0-G** Resolucao de tenant em rota publica + fail-close do manager em contexto publico. [P0, G] (decisao de arquitetura)
- **T-P1-A** login_url mortos (19 views) + acesso_cs nas views CS + corrigir test_module_access. [P1, P-M]
- **T-P1-B** Taxonomia de fontes configuravel + literais de dominio do funil. [P1-P2, M]
- **T-P2-A** Reorganizacao do menu CS (19 -> 14) + matchers de ativo. [P2, M]
- **T-P2-B** Confianca do Painel Executivo: filtros que aplicam + KPIs com unidade + None/— tratados. [P2, P-M]
- **T-P2-C** Mobile de relatorios e CS. [P2, M]
- **T-P2-D** Vocabulario de clube no lugar de roleta + rota publica neutra. [P2, M]
- **T-P3-A** Limpeza: nps/retencao mortos, jQuery legado, zip em static. [P3, P]
- **T-P3-B** Cache no query builder + tokens do DS no JS + {% url %} + fallback CDN. [P3, M]
- **T-testes** Suite minima (secao 7). [M]
- Concluir a **#182** (esta tarefa de diagnostico) referenciando este doc.

---

*Diagnostico executado por 2 agentes com persona (UX e CTO) sobre navegacao Playwright em
ambiente local. Nenhuma alteracao de codigo de produto, nenhum acesso a producao.*
