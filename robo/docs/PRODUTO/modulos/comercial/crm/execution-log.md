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
