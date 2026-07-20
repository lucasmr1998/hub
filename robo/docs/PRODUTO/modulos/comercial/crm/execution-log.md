# Execution log — módulo CRM

Trilha do que foi executado no módulo CRM (incidentes, decisões,
mudanças que afetaram prod). Append-only, entrada mais nova no fim.

---

## 2026-06-29 — Bug regras #28/#29/#30 "Vincular plano escolhido como item"

**Acao:** Desativadas em prod 3 regras do tenant Nuvyon (id=12):
  - #28 "Vincular plano escolhido como item" (estagio: Dados Completos)
  - #29 "Vincular plano escolhido como item" (estagio: Aguardando Documentos)
  - #30 "Vincular plano escolhido como item" (estagio: Analises - Doc & Score)

**Causa raiz:** Motor de regras (`apps/comercial/crm/services/automacao_pipeline.py:97-99`)
**sempre move a op pro estagio da regra** quando dispara — mesmo
quando a unica acao da regra eh `adicionar_item_oportunidade` (que
nao deveria mover).

Resultado: leads novos que escolhiam plano caiam direto em
"Analises - Doc & Score" (estagio que pressupoe documentos enviados
e analise feita) sem ter passado pela coleta de doc/score.

**Caso real que evidenciou:** Op 1861 (lead 1702 Johnny). Cliente foi
transferido pra humano ao digitar CEP (incompatibilidade cobertura),
mas op estava em "Analises - Doc & Score" — operador comercial
ficaria confuso vendo a op em estagio que pressupoe analise feita.

**Decisao:** Desativar as 3 regras incorretas, manter so a #27
(estagio = Plano Escolhido, que faz sentido). Perda funcional eh
pequena: leads onde `id_plano_rp` aparece DEPOIS da op ja ter
avancado de "Plano Escolhido" perdem o item vinculado automatico.
Operador adiciona manualmente nesses raros casos.

**Numeros antes do fix:**
  - Regra #30 disparou 49 vezes (49 ops Nuvyon caem indevidamente
    em "Analises - Doc & Score" desde a criacao)
  - Regras #28 e #29 disparou 0 vezes (estagios menos comuns)
  - Regra #27 (correta) disparou 0 — provavel desempate por ID
    priorizou #30 quando ambas batiam

**Fix definitivo (pendente — medio prazo):** Refactor do motor pra
introduzir `tipo_regra=acao_pura` que executa a acao SEM mover a op.
Permite re-ativar as regras com seguranca.

**Como executei:**
```python
RegraPipelineEstagio.all_tenants.filter(
    id__in=[28, 29, 30], tenant_id=12
).update(ativo=False)
```
Output: "Update aplicado: 3 regras"

**Status:** completed. Acompanhar nas proximas 24h se algum lead
novo escolhe plano e VAI para "Plano Escolhido" corretamente (em vez
de pular pra "Analises - Doc & Score").

**Reverter (se necessario):** UPDATE ativo=True nos mesmos ids.

**Correcao em massa das ops afetadas (2026-06-29):**
37 ops foram movidas de "Analises - Doc & Score" -> "Em Atendimento"
porque tinham caido aqui pela regra #30 sem ter documentacao
completa. Mantidas em "Analises - Doc & Score":
- Op 1755 Maikebinkan: regra correta #25 (tag aguardando_validacao)
- Op 1736 Gabriel: movida manualmente (motivo vazio)
- Op 1787 Tiago: score=aprovado, deixar vendedor decidir
- Op 1790 Antonio: score=aprovado, deixar vendedor decidir
HistoricoPipelineEstagio registrado pra cada uma com motivo
"Correcao em massa". Notificacoes disparadas pros responsaveis.

---

## 2026-06-29 — Motivo de perda obrigatorio + bug 2 estagios "Perdido"

**Acao 1 (codigo):** commit `320f83c` adiciona 2 campos novos no
catalogo `CAMPOS_DISPONIVEIS` em
`apps/comercial/crm/services/requisitos_estagio.py`:
- `oportunidade.motivo_perda_categoria` (categoria — escolha estruturada)
- `oportunidade.motivo_perda` (texto livre)

Permite marcar como obrigatorios em qualquer estagio via UI
`/crm/configuracoes/`.

**Acao 2 (UPDATE em prod, tenant 12 nuvyon):**
1. Estagio id=84 ("Perdido"): tipo='novo' -> 'perdido' (era bug
   irmão do que vimos com "Ativacao Confirmada" — quebrava analises
   automaticas filtradas por tipo).
2. Estagios id=73 e id=84: `campos_obrigatorios` agora inclui
   `oportunidade.motivo_perda_categoria`. Vendedora nao consegue
   mais mover pra "Perdido" sem categorizar a perda.

**Diagnostico que motivou:** Dos 22 leads enriquecidos pelo Sprint 4
que viraram perdidos, 17 (77%) estavam sem motivo registrado. Todos
movidos por vendedoras humanas (thais.moreira lidera com 12).

**Pendencia:** Existem 2 estagios "Perdido" no pipeline Nuvyon
(id=73 vazio + id=84 com 22 ops). Aguardando decisao do Lucas pra
consolidar (mover ops 84->73 + deletar 84) OU manter ambos.

---

## 2026-07-14 — Fix: acao criar_tarefa da automacao de pipeline nunca funcionou

**Acao:** Investigacao dos bugs do modulo de tarefas, disparada por pedido de video
tutorial. Consulta read-only em prod pra medir impacto.

**Diagnostico (o achado da sessao):** `_acao_criar_tarefa` em
`crm/services/automacao_pipeline.py:908` importava `Tarefa`, nome que nunca existiu.
A classe e `TarefaCRM`. O `ImportError` era engolido pelo try/except de
`_executar_acoes_regra`, a regra registrava `resultado: 'erro'` num log que ninguem
le, e a tarefa nunca era criada. Em silencio, desde sempre.

**Impacto medido em prod:** a Nuvyon tem a regra 26 "Viabilidade pendente revisao ->
criar tarefa" ATIVA, cuja unica acao e `criar_tarefa`. Ela ja disparou **34 vezes**
(ultima em 13/07/2026 13:43) e criou **zero** tarefas. Ou seja: 34 leads com
viabilidade pendente de revisao nunca geraram tarefa pra ninguem olhar. As 46 tarefas
da Nuvyon em prod sao todas manuais.

**Decisao:** corrigir os 3 bugs de baixo risco agora; o 4o (falta de tela de editar
tarefa) e feature faltando, vai pro backlog.

**Output:**
1. `automacao_pipeline.py`: `Tarefa` -> `TarefaCRM` (import + 2 usos + docstring).
   O resto da funcao ja estava correto (placeholders, idempotencia, fallback de
   responsavel). Nao gera enxurrada retroativa: so age em disparo novo, e a
   idempotencia impede duplicata.
2. `crm/views.py:api_tarefa_concluir`: quem tem `ver_todas_oportunidades` passa a
   concluir tarefa do time. Antes o card mostrava o botao pro gestor
   (`_tarefa_card.html:35` nao checa dono) mas o backend exigia
   `responsavel=request.user`, entao o clique voltava 404 calado. Decisao de produto
   do Lucas: liberar o gestor. O log registra quando a conclusao foi feita por outro.
3. Links de notificacao de tarefa corrigidos: `notificar_tarefas_vencendo.py` apontava
   pra `/crm/tarefas/<id>/` (rota inexistente) e `notificacoes/signals.py` usava o
   prefixo errado `/comercial/crm/tarefas/`. Os dois davam 404. Agora vao pra
   `/crm/tarefas/`.
4. Novo `tests/test_automacao_pipeline_criar_tarefa.py` (4 testes). Chamam a acao
   DIRETO de proposito: passar pelo executor da regra nao serve de regressao porque
   ele engole a excecao. Validado reintroduzindo o bug: o teste falha com o
   ImportError exato.

**Efeito colateral esperado no proximo deploy:** a regra 26 da Nuvyon volta a
funcionar e passa a criar tarefa a cada disparo, notificando o responsavel (o signal
`notificar_tarefa_atribuida` dispara porque `criado_por` e None na automacao).
Avisar a Nuvyon antes de subir.

**Status:** completed (codigo). Deploy pendente de confirmacao do Lucas.

**Backlog aberto:** nao existe tela de editar/cancelar TarefaCRM. So lista, criar e
concluir. Errou titulo ou data, so pelo admin do Django.

---

## 2026-07-15 — Fix: adicionar membro a equipe nao movia quem ja tinha perfil

- **Acao:** `equipes_view` (action `adicionar_membro`) usava
  `PerfilVendedor.objects.get_or_create(user=user, defaults={equipe, cargo})`.
  Como `PerfilVendedor` e OneToOne com User e quase todo usuario ja tem perfil,
  os defaults eram ignorados: adicionar alguem que ja tinha perfil nao trocava a
  equipe. Bug silencioso (a tela nao mudava). Reportado pelo Lucas ao tentar por
  a Gabriela Ferreira na EQUIPE CACONDE.
- **Decisao:** trocar por `update_or_create`. Como `equipe` e FK unica, a
  operacao MOVE a pessoa pro novo time (sai do anterior). Se um gerente precisar
  cuidar de mais de um time no futuro, exige mudar o modelo (M2M ou usar `lider`).
- **Output:** commit bf13cc4. `manage.py check` limpo.
- **Status:** completed (codigo). Deploy pendente de confirmacao do Lucas.

---

## 2026-07-15 — Feature: visibilidade de oportunidades por equipe (permissao)

- **Acao:** novo nivel de visibilidade dirigido por funcionalidade
  `comercial.ver_oportunidades_da_equipe`. Modelo de 3 niveis: `ver_todas` ->
  tudo; `ver_da_equipe` -> os times que a pessoa lidera (EquipeVendas.lider) +
  o time de que e membro (PerfilVendedor.equipe); nenhuma -> so as suas.
- **Decisao (Opcao A):** reusar `EquipeVendas.lider` pro vinculo gerente->times
  (FK no lado do time = um gerente lidera N times, sem migration). Fonte unica de
  verdade em `apps/comercial/crm/escopo.py::escopo_responsaveis(request)` (None =
  ve tudo, senao lista de user ids). Adicionar membro com cargo Gerente passou a
  definir o lider do time (nao mexe no equipe dele); vendedor/supervisor/diretor
  continuam membros.
- **Enforcement:** 6 pontos do CRM (pipeline, oportunidades_lista, mover,
  tarefas_lista, api_tarefa_concluir, win_loss) + relatorios (query_builder
  `_aplicar_escopo_visibilidade` no caminho count/sum e `_v_lead/_v_op/_v_atend`
  nos transforms; `_overrides_da_barra` injeta o escopo; `api_preview` e os 2
  callers do decks tambem; dropdowns de vendedor/equipe capados ao escopo).
- **Efeito colateral (intencional):** os relatorios antes nao escopavam por
  usuario (so por tenant), entao QUALQUER um via tudo. Agora quem nao tem
  ver_todas so ve o proprio escopo tambem nos dashboards, batendo com o CRM.
  Vendedor comum passa a ver so os dados dele nos paineis. Se quiserem que
  vendedor veja agregados da empresa, criar uma excecao separada.
- **Output:** seed rodado em dev (1 funcionalidade nova). manage.py check limpo.
  Smoke da logica OK (None / [self] / uniao). Depende do cadastro de times/lideres
  (tarefa 190) pra ligar de verdade; sem time, cai no default seguro (so as suas).
- **Status:** completed (codigo, dev). Seed em prod + atribuir a permissao ao
  perfil (UI) + deploy pendentes de confirmacao do Lucas.

---

## 2026-07-15 — Origem obrigatoria no modal Nova oportunidade (condicional)

- **Acao:** os campos Origem do cliente (id_origem) e Origem do contato
  (id_origem_servico) do modal "Nova oportunidade" (pipeline) viraram
  obrigatorios. Pedido da Nuvyon.
- **Decisao (Opcao B):** obrigatorio SO onde o tenant tem origens configuradas
  (cache HubSoft). pipeline.html e compartilhado; tenant sem HubSoft
  (tr-carrion, gigamax) tem dropdown vazio e travar ali impediria criar
  oportunidade manual. Nuvyon tem 24 origens_cliente + 4 origens_contato ->
  obrigatorio; demais -> nao trava. Auto ajusta se outro tenant configurar
  origens depois.
- **Como:** frontend com asterisco condicional ({% if opcoes_origens_* %}) e
  validacao no criarOportunidade() por options.length>1; backend com guard
  _tenant_tem_origens em api_criar_oportunidade (defense in depth). Webhook/
  Matrix nao passa por esse endpoint, entao entrada automatica nao e afetada.
- **Output:** manage.py check limpo.
- **Status:** completed (codigo, dev). Deploy pendente de confirmacao do Lucas.

---

## 2026-07-15 — Fix: plano 500 normal de Sumare nao aparecia (so o Mig)

- **Report:** vendedora Nuvyon: "500mb de Sumare so tem o Mig, adicionar o normal".
- **Diagnostico:** NAO era HubSoft nem cidade. O HubSoft devolve o 500 normal
  (id_servico 515, "7- PLANO_500M - CONNECTIONS", R$99,90) pra todos os CEPs de
  Sumare. O dropdown do completar-venda mostra o catalogo curado
  (ProdutoServico categoria=plano ativo=True, id_externo) INTERSECTADO com os
  ids do HubSoft no CEP; so cai na lista crua se o curado nao tiver nada da
  regiao. No crm_produtos da Nuvyon o 515 estava ativo=False (id 163); so o Mig
  (id 435, id_externo 1155) estava ativo, por isso a vendedora so via o Mig.
- **Fix:** ProdutoServico.all_tenants.filter(id=163).update(ativo=True) em prod
  (verificada a identidade da linha antes; .update sem signals). Confirmado: o
  dropdown de Sumare passou a listar 515 (normal) + 1155 (Mig).
- **Pendencia observada:** o Mig ativo (id 435) esta com preco R$ 0,00, provavel
  erro de cadastro. Padrao "normal desativado / Mig ativo" pode existir em outras
  velocidades/cidades (auditoria sugerida, nao feita).
- **Status:** completed (dado em prod, live sem rebuild).

---

## 2026-07-15 — Central de Acoes (MVP, pagina role aware estilo Visio)

- **Acao:** pagina nova /crm/central-acoes/ que lista "o que fazer agora"
  priorizado, escopado por papel via escopo_responsaveis (vendedor ve o dele,
  gerente ve o do time). Tarefa Workspace #200.
- **Arquitetura (Opcao A):** view no CRM (central_acoes_view, gate ver_pipeline)
  + motor em apps/comercial/crm/central_acoes.py (coletar_acoes). Reusa o
  escopo_responsaveis ja em prod, entao o role aware sai de graca.
- **6 sinais (regua do strawman):** oportunidade parada no estagio >7d (critico)
  / 3-7d (atencao) via data_entrada_estagio; tarefa vencida (critico); oport sem
  dono (critico, so pra quem ve o time); lead status_api=erro (critico); oport
  nova <24h (oportunidade). Contadores por severidade. Ordena critico > atencao
  > oportunidade, urgencia dentro.
- **Template:** crm/central_acoes.html (estende sistema/base.html, estilo Visio:
  chips de contador + lista clicavel com bolinha de severidade). Entrada nova na
  sidebar (Operacao, topo). Cap de 60 itens exibidos + total.
- **Validacao:** manage.py check limpo; smoke em dev (template compila, coletor
  roda: 241 criticos/3 atencao/244 itens num superuser, ordenacao correta).
- **Pendente/futuro:** filtro por equipe/loja na barra, feed de "Atualizacoes",
  cap paginado ("ver todos"). Sinal de lead-novo usa oport <24h como proxy de
  "sem 1o contato" (sem join em HistoricoContato ainda).
- **Status:** completed (codigo, dev). Deploy pendente de validacao do Lucas.

---

## 2026-07-15 — Central de Acoes: UX (secoes + selo de tipo)

- **Feedback do Lucas:** lista chapada de 73 itens iguais, "nao sei o que e o
  que". Faltava rotulo de tipo e agrupamento.
- **Ajuste:** coletar_acoes passou a devolver `grupos` (3 baldes por severidade)
  e cada item ganhou `tipo` (Parada / Sem dono / Tarefa / Erro / Nova). Template
  virou 3 secoes colapsaveis (<details>): Criticos e Atencao abertos, Oportunidades
  fechada por padrao (some o volume verde). Cada linha tem selo de tipo colorido.
- **Status:** completed (codigo, dev).

---

## 2026-07-15 — Central de Acoes: secoes fechadas + paginacao

- **Feedback do Lucas:** trazer tudo fechado por padrao e paginar.
- **Ajuste:** todas as 3 secoes agora iniciam fechadas (sem `open`). Cada secao
  pagina client side (15/pagina, ‹ ›, "Pagina X de Y · N itens") sobre os itens
  carregados, sem cortar em 50. Menos ruido, abre so o que interessa.
- **Status:** completed (codigo, dev).

---

## 2026-07-16 — Central de Acoes: layout Cockpit (cards + fila)

- **Feedback do Lucas:** UX das sanfonas fechadas nao ficou boa; escolheu (via
  mockups A/B/C) a estrutura Cockpit.
- **Ajuste:** 5 cards por TIPO no topo (Parada / Sem dono / Tarefa / Erro / Nova)
  com contagem e cor por severidade; clicar num card foca a fila embaixo. Fila
  unica paginada (15/pag) filtrada por tipo + filtro de equipe (dropdown, so pra
  quem ve o time). Cada linha mantem a bolinha de severidade real. coletar_acoes
  passou a devolver itens (flat, com chave/severidade), tipos (tiles), equipes.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Card kanban: Proxima tarefa vira badge por status

- **Pedido do Lucas:** o campo de tarefa no card deve ser badge amarelo se
  pendente, vermelho se vencida.
- **Ajuste:** o campo "Proxima tarefa" (ja existia em CAMPOS_CARD_DISPONIVEIS)
  agora carrega `vencida` no dado do card (_card_data) e o renderCampoCard do
  kanban o desenha como badge: amarelo (is-pendente, relogio) ou vermelho
  (is-vencida, triangulo). Preview do modal de personalizar atualizado.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Central de Acoes vira home do Comercial (KPIs)

- **Decisao do Lucas:** a tela vira a landing do Comercial; as acoes sao uma
  parte, com numeros em cima que ajudem vendedor e gestor.
- **Ajuste:** funcao kpis_comerciais (central_acoes.py) com 4 KPIs escopados via
  escopo_responsaveis (o mesmo numero vira 'meu'/'do time'): Em negociacao (qtd +
  R$), Ganhas no mes (qtd + R$), Conversao do mes (ganhas/fechadas), Novas 7d; +
  Sem dono (so gestor). Linha de KPI cards acima do cockpit; H1 virou 'Comercial'
  com secao '⚡ Central de Acoes'. Nav principal do Comercial (sidebar) aponta pra
  /crm/central-acoes/ (pipeline continua em /crm/).
- **Follow-up:** seletor de periodo, progresso vs meta, drill dos cards ganhas/
  conversao/novas. Tarefa #200.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — KPIs da home usam o componente stat_card do DS

- **Feedback do Lucas:** os cards de cima deviam seguir o padrao do DS (stat_card).
- **Fix:** eu tinha inventado um .ca-kpi proprio; refatorado pra
  {% include "components/stat_card.html" %} (label + icone colorido + valor +
  footnote). Cada KPI ganhou icon + icon_variant; clicavel via wrapper
  .stat-card-link. Removido o CSS custom. Regra de ouro do DS respeitada.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Central de Acoes: cards e fila unificados num painel

- **Feedback do Lucas:** unificar os cards de tipo e a fila num bloco so, com o
  titulo "Central de Acoes".
- **Ajuste:** um card unico (.ca-panel) com cabecalho "Central de Acoes", os 5
  tipos viraram barra de abas no topo (aba ativa com sublinhado colorido) e a
  fila logo abaixo, no mesmo container. JS ajustado (.ca-tile -> .ca-tab).
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Central de Acoes: abas viram colunas de triagem

- **Feedback do Lucas:** em vez de abas, colunas (OP Paradas | Sem dono | Tarefas
  | Novas...); e paginacao de 5 na fila.
- **Ajuste:** coletar_acoes devolve `colunas` (agrupado por tipo, label plural).
  Painel unico com o titulo Central de Acoes e as colunas lado a lado, cada uma
  com header (contagem + label colorido), lista e paginacao propria de 5. Coluna
  vazia (ex: Erros=0) fica escondida. Filtro de equipe repagina todas as colunas.
  Em tela estreita as colunas rolam na horizontal.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Central de Acoes: filtro de equipe (esconder com 1 time + fix)

- **Feedback do Lucas:** supervisor de 1 time nao devia ver o seletor de equipe;
  so com 2+ equipes. E garantir o filtro pra todos.
- **Ajuste:** filtro de equipe so aparece com equipes|length > 1 (supervisor de um
  time ve so o dele, sem dropdown). Fix: Tarefas e Erros nao carregavam a equipe
  no item (tag vazia), entao filtrar por equipe zerava essas colunas. Agora
  setam _equipe_nome via oportunidade.responsavel.perfil_crm.equipe (+ select_
  related pra evitar N+1).
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Central de Acoes: fix do filtro (contador + tag tarefa + seletor travado)

- **Feedback do Lucas:** (1) seletor de equipe nao devia sumir com 1 time, e sim
  ficar travado mostrando o time; (2) header dizia "31 Tarefas" mas a fila
  filtrada zerava.
- **Ajuste:** (1) com 1 equipe o seletor aparece desabilitado com o nome do time
  (informativo; o escopo ja restringe). (2) contador do header (.ca-col-count)
  passa a refletir o filtro via JS. (3) a tag de equipe da TAREFA vinha do
  responsavel da OPORTUNIDADE, mas o escopo e pelo responsavel da TAREFA; alinhado
  pra _equipe_de(t.responsavel). Agora 30/30 tarefas com equipe (era 6/30), o
  filtro casa com o escopo.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Central de Acoes: tabela operacional por vendedor

- **Pedido do Lucas:** abaixo da Central de Acoes, tabela por membro da equipe
  (so gestor/supervisor), colunas agrupadas por categoria. Confirmado: colunas
  fechadas, mes corrente, celulas clicaveis.
- **Ajuste:** tabela_operacional(request) em central_acoes.py (None pro vendedor
  comum). 2 queries agrupadas por responsavel. Colunas: Oportunidades (Criadas,
  Ganhas, Perdidas, Aberto, Paradas) | Tarefas (Feitas, Pendentes, Vencidas) +
  linha Total da equipe. Cabecalho em 2 niveis (categoria + sub). Cada celula
  linka pra a lista do vendedor (oportunidades_lista/tarefas_lista ?responsavel).
- **Follow-up:** drill fino por metrica (ex: so as paradas do vendedor) quando a
  lista suportar esses filtros; plugar no seletor de periodo. Tarefa #200.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Tabela operacional: filtro de equipe recorta as linhas

- **Feedback do Lucas:** o filtro de equipe nao refletia na tabela operacional;
  gestor multi time filtrando deveria recortar os vendedores tambem.
- **Ajuste:** cada linha ganhou a equipe (data-equipe via _equipe_de + select_
  related perfil_crm__equipe). O JS do filtro passou a esconder as linhas de fora
  da equipe e recalcular o Total da equipe pelas linhas visiveis.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — "Parada" passa a usar o SLA do estagio (fix de definicao)

- **Feedback do Lucas:** "parada" deve comparar o tempo no estagio com o SLA
  daquele estagio (sla_horas, configuravel no CRM), nao um corte fixo de dias.
- **Diagnostico (prod):** os SLAs da Nuvyon estao em 2h por estagio. Por isso a
  automacao dizia ~100 paradas (121 abertas, 100 acima do SLA de 2h) e estava
  CERTA; meu corte fixo (>3d=24, >7d=6) subestimava. Estagio sem SLA (ex:
  Aguardando Assinatura) nao gera parada.
- **Ajuste:** parada = data_entrada_estagio + sla_horas < agora, via expressao
  ORM _SLA_DEADLINE. Aplicado na coluna OP Paradas (severidade: critico se passou
  2x o SLA, senao atencao; subtitulo mostra tempo no estagio) e na tabela
  operacional (query separada por vendedor). data_entrada_estagio e atualizado no
  arraste do kanban (api_mover_oportunidade), entao o campo e confiavel.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Filtro da home vira server-side (KPIs refletem) + filtro de pessoa

- **Feedback do Lucas:** os KPIs (primeira linha) nao mudavam com o filtro de
  equipe (eram server-side, o filtro era client-side). E adicionar filtro de pessoa.
- **Ajuste:** o filtro virou server-side (GET ?equipe / ?pessoa). Novos helpers
  escopo_efetivo(request) (base estreitado pelo filtro; pessoa > equipe) e
  pode_ver_time(request) (gate pela permissao base). coletar_acoes, kpis_comerciais
  e tabela_operacional passam a usar escopo_efetivo pros dados e pode_ver_time pro
  gate. Assim KPIs, colunas e tabela refletem o filtro. Form com 2 selects (equipe
  + pessoa) que submetem ao mudar; equipe travada quando ha so 1 time. O filtro
  client-side antigo ficou inerte (paginacao segue).
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Filtro da home via AJAX (sem recarregar a pagina)

- **Feedback do Lucas:** o filtro server-side recarregava a pagina toda; queria
  so atualizar as informacoes, rapido como antes.
- **Ajuste:** conteudo (KPIs + Central de Acoes + tabela) extraido pro partial
  crm/_ca_conteudo.html, dentro de #ca-conteudo. A view responde so o partial
  quando ?fragment=1. Os selects de equipe/pessoa chamam caFiltrar() que faz
  fetch do fragment e troca so o #ca-conteudo (com fade), reexecutando a
  paginacao. history.replaceState mantem a URL. Continua server-side (KPIs em R$
  corretos), mas sem reload da pagina inteira.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Fila de Tarefas: inclui "vence hoje" (atencao) alem das vencidas

- **Pedido do Lucas:** na coluna Tarefas da fila, mostrar tambem as que vencem
  hoje (amarelo), nao so as vencidas (vermelho).
- **Ajuste:** filtro passou de data_vencimento < agora pra < fim do dia local.
  Vencida (< agora) = critico, "Vencida ha Xh/dias"; vence hoje (>= agora, ate
  o fim do dia) = atencao, "Vence hoje". Removido helper _plural (orfao).
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Tarefas: aba Concluidas paginada (fim do teto silencioso de 20)

- **Pedido do Lucas:** "pq eu so vejo 20 tarefas concluidas?".
- **Causa:** views.py tinha `qs.filter(status='concluida')[:20]` fixo enquanto a
  aba vizinha ja paginava. A tela nao quebrava, ela omitia: o contador da aba
  mostrava `|length` da fatia (20), entao o proprio numero confirmava a mentira.
- **Ajuste:** Paginator(30) com parametro proprio `?page_concluidas=` (a aba
  "Todas pendentes" continua no `?page=`, as duas navegam independentes).
  Contadores das duas abas passam a usar `paginator.count` (total real), nao o
  tamanho da pagina. Links de paginacao agora preservam os filtros ativos
  (`query`), o que antes se perdia tambem na aba "Todas". JS reabre a aba
  Concluidas quando a URL tem `page_concluidas` (o reload voltava pra "Todas").
- **DS:** `components/pagination.html` ganhou o param opcional `page_param`
  (default 'page', retrocompativel) em vez de forkar a marcacao. Habilita
  qualquer tela com duas listas paginadas.
- **Validacao:** `manage.py check` ok. Smoke em dev com 45 tarefas temporarias
  (criadas e removidas, junto das 45 notificacoes que o signal gerou): 49
  concluidas -> 2 paginas, 30 + 19, sem sobreposicao, listas independentes,
  contador exibindo 49. Antes: 20 de 49.
- **Status:** completed (codigo, dev). Deploy em prod pendente de confirmacao.

---

## 2026-07-16 — Pipeline: padrao de mercado (N+1, agregacao, paginacao por coluna)

- **Pedido do Lucas:** "o pipeline ta demorando um pouco pra carregar" e, apos a
  analise, "a gente tem que seguir o padrao de qualidade do mercado". Tarefa #202.
- **Diagnostico (medido em prod, nuvyon, 953 ops ativas):** o HTML da pagina
  estava inocente (0.02s, 13 queries). O gargalo era o `api_pipeline_dados`:
  1.33s, **567 queries**, **961 KB** de payload, 953 cards no DOM sem
  virtualizacao. SQL somava so 0.19s (14%): o banco nunca foi o problema, eram
  os round-trips + Python + payload.
- **Item 0 (N+1):** 488 das 567 queries eram identicas em `crm_produtos` (nome do
  plano, 1 por card) e buscavam **26 planos distintos**. Mais 74 em
  `campanha_trafego`. Mapa numa query so (via `.objects`, tenant-scoped) +
  select_related. Equivalencia provada contra dados reais de prod: 26/26
  resolvidos, 0 divergencia, 0 id_externo duplicado, nenhum compartilhado entre
  tenants.
- **Item 1 (agregacao):** `totais_por_estagio()` no OportunidadeQuerySet. O
  cabecalho da coluna saia de `len(ops)`; com paginacao viraria o tamanho da
  pagina e a tela mentiria (mesmo bug do contador da aba de concluidas, e pior:
  o vendedor decide o dia por esse numero). `Sum('valor_estimado_anotado')` e
  proibido (aggregate de aggregate), entao a soma dos itens virou subquery
  escalar, o que tirou o JOIN e o risco de Count inflado. Conferido contra os
  valores reais de prod: total geral R$ 7008.40 identico, estagio a estagio.
- **Item 2 (payload):** MEDIDO e descartado quase todo. Nenhum campo domina (o
  maior, dados_custom, e 9.5%). O corte total possivel era ~19% com risco de
  mexer no JS em varios pontos, enquanto o item 3 corta ~85% sozinho. Feito so
  o corte com justificativa propria: `dados_custom` parou de mandar as chaves
  internas (`_*`) que o card ja descartava no browser (higiene, nao perf).
  Sobra registrada: 4 campos repetem o mesmo responsavel (137 KB) e
  valor/valor_estimado sao iguais. Reavaliar so se o payload voltar a incomodar.
- **Item 3 (paginacao):** 20 cards por coluna + "Carregar mais", endpoint
  `api_pipeline_estagio_cards`, `_qs_pipeline_filtrado` compartilhado (a proxima
  fatia tem que sair do mesmo recorte). `order_by('-data_criacao', '-id')`: o
  ordering do model nao desempata e a coluna repetiria/pularia card entre as
  levas. List view avisa "Mostrando X de Y" pra nao parecer completa.
- **Item 4 (busca server-side):** ja era server-side. Nao precisou de codigo, mas
  foi VERIFICADO em vez de assumido: busca por um card fora da 1a leva (op #268)
  encontra o card, e o contador respeita o filtro.
- **Item 5 (virtualizacao):** NAO feito, por decisao tecnica. O item 3 derrubou o
  DOM de 953 pra ~160 nos, e virtualizar so agrega complexidade (drag and drop
  com no reciclado e notoriamente ruim) sem ganho real. Revisitar se alguem
  expandir muito uma coluna e reclamar.
- **Validacao:** `manage.py check` ok; 30 testes (`test_automacao_pipeline`,
  `test_automacao_acoes_crm`, `test_automacao_adicionar_item_oportunidade`)
  passando; E2E Playwright em dev: coluna com 25 mostra "20 de 25", clique traz
  os 5, 0 duplicado no DOM, topo segue em 25, 0 erro de console.
- **Numeros (dev, 167 cards):** 567 -> 32 queries; payload 961 KB -> 106 KB.
  Medicao de prod pendente do deploy.
- **Limitacao conhecida:** mover card recarrega o board e a coluna volta a 20.
- **Status:** completed (codigo, dev). Deploy em prod pendente de confirmacao.

---

## 2026-07-20 — Timeline da op mostra os dados usados na criacao do prospecto (tarefa #206)

- **Pedido do Lucas:** ver na oportunidade o historico de quando o lead foi criado
  no HubSoft, com o nome e o telefone que foram usados na criacao.
- **Descoberta que barateou tudo:** o dado JA existia. LogIntegracao guarda
  `payload_enviado` (nome_razaosocial, telefone, cep, endereco, numero, bairro,
  servico{id_servico,valor}, id_vendedor, id_vencimento, id_origem_cliente,
  observacao) e `resposta_recebida`. Zero model, zero migration, zero gravacao
  nova. Vale RETROATIVO: 1759 chamadas POST /prospecto em prod (31/05 a 20/07),
  1583 ja vinculadas a lead.
- **Implementacao:** helper `_dados_criacao_prospecto(log, tenant)` extrai o
  snapshot; a view junta `prospecto_criacoes` na timeline (tipo
  'prospecto_hubsoft'); template renderiza no padrao dos outros itens, com visual
  distinto pra sucesso vs falha. Mostra o nome/telefone DO MOMENTO da criacao, que
  pode diferir do lead atual (e assim da pra ver que entrou como "CLIENTE"/"Nao" e
  foi corrigido depois, ver #201).
- **Multi-tenancy:** o nome do plano so e resolvido com tenant EXPLICITO. Primeira
  versao usava all_tenants sem filtro quando tenant era None, o que mostraria o
  plano de outro tenant no historico deste, em silencio. Provado em dev com o mesmo
  id_externo cadastrado em 2 tenants: cada um ve so o seu; sem tenant, mostra o id.
- **Robustez:** helper nunca levanta (payload None/string invalida/lista/servico
  como string/vazio testados). Timeline quebrada seria pior que item faltando.
- **Validacao:** manage.py check limpo. Helper rodado contra payloads REAIS de prod
  (sucesso e falha). Render provado pelo HTML da resposta: 8 de 8 checks (titulos,
  nome, telefone, cep, id do prospecto, mensagem de erro, data-tipo).
- **Nota de metodo:** o E2E via Playwright deu falso negativo (login falhou e ele
  leu a pagina de login com status 200). O teste que valeu foi o do HTML renderizado.
- **Status:** completed (codigo, dev). Deploy pendente de confirmacao.

---

## 2026-07-20 — Busca no select de plano do "Completar dados"

- **Pedido do Lucas:** "precisa ter um campo de busca aqui" (select de plano do modal
  de completar dados). Sao 48 planos ativos e a lista rolava as cegas.
- **Feito:** campo de texto acima do select + contador ("2 de 6"). Filtra por nome,
  case insensitive.
- **Decisao que importa:** a busca filtra `_ccPlanosValidos` (a lista JA recortada
  pelo CEP consultado), nunca `_ccTodosPlanos`. Buscar no catalogo inteiro traria de
  volta plano que a regiao nao vende, desfazendo em silencio a protecao do filtro
  por CEP.
- **Protecao:** o plano JA ESCOLHIDO permanece na lista mesmo quando nao casa com a
  busca. Sem isso, digitar um termo qualquer apagaria a escolha do vendedor sem ele
  perceber (o select ficaria vazio e o campo obrigatorio voltaria a pendente).
- **Validado no browser** com 6 planos injetados: busca por 600/MIG/CONNECTIONS/salto
  filtra certo, contador acompanha, e a escolha sobrevive a uma busca que nao casa.
- **Limitacao conhecida:** busca por nome, nao por preco formatado ("99,9" da 0).
- **Status:** completed (codigo, dev). Deploy pendente.

---
