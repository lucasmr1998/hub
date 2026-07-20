# Execution log, modulo People

Trilha do que foi executado no modulo. Entrada mais nova embaixo.

---

## 2026-07-19 — Decisao de trazer o People da Visio pro Hubtrix

- **Acao**: analise do pacote de handoff em `Desktop/visio/gtm-pre-content-prep/docs/handoff/people-module/` (5 docs por Tool) e da estrutura do Hubtrix pra encaixe.
- **Decisao**: comecar pela FUNDACAO (passos 0 e 1 da ordem sugerida do doc de departamento pessoal), nao pelo Feedback. Nada do modulo funciona sem cadastro de colaborador, e a regra de fonte unica com dedup e herdada por todas as outras Tools.
- **Decisao**: criar `people.Unidade` dentro do tenant. O Hubtrix nao tinha nenhum conceito de unidade, e a spec inteira assume escopo por loja.
- **Decisao**: People vira modulo comercializavel completo, com toggle por tenant.
- **Output**: plano aprovado, tarefa 205 criada no Workspace.
- **Status**: completed

## 2026-07-19 — Fundacao: modelo, maquina de estados e dedup

- **Acao**: passos 1 a 4 do plano. `apps/people/` com Unidade, ConfiguracaoPeople, Colaborador e HistoricoSituacao; `estados.py` como fonte da verdade do ciclo de vida; servico de cadastro com dedup; telemetria.
- **Decisao**: `estados.py` e a nova fonte da verdade. A spec avisava que os nomes de estado dela eram proposta de quem escreveu o documento, nao valores lidos do schema, e pedia que a reconstrucao documentasse a propria maquina.
- **Decisao**: tres defeitos da spec nascem corrigidos. D1 (tres pontos de entrada, nao um), D2 (vocabulario unico) e D4 (prorrogar e auto transicao, e `em_desligamento` e estacionamento opcional e nao pedagio).
- **Decisao**: guarda no `save()` impede mudar `situacao` fora de `mover_situacao()`. O buraco do `queryset.update()` e fechado por varredura de codigo em `tests/test_people_contrato.py`.
- **Decisao**: CPF ausente e `NULL` e nao string vazia, porque a unique por tenant e o que sustenta o dedup.
- **Decisao**: match fraco (telefone, ou nome mais nascimento) NUNCA reaproveita sozinho: devolve conflito pra um humano decidir.
- **Decisao**: `HistoricoSituacao` e a fonte primaria de telemetria. LogSistema e a engine de automacao sao canais derivados e blindados.
- **Output**: commits 3e8158b, 713c4ea, 7bed2e1, a72b81c. 132 testes.
- **Status**: completed

## 2026-07-20 — Modulo comercializavel, telas e navegacao

- **Acao**: passos 5 a 9 do plano. Registro do modulo, CRUD de unidade, board kanban, ficha do colaborador e links de cadastro.
- **Decisao**: gate proprio em `apps/people/permissoes.py`. O `PermissaoMiddleware` do sistema so verifica funcionalidade, nunca contratacao, entao quem digitasse a URL entrava num modulo nao comprado. Ficou no app: ensinar o middleware a olhar contratacao mudaria o comportamento de todos os modulos de uma vez.
- **Decisao**: tres listas hardcoded de modulo viraram derivadas de `Plano.MODULO_CHOICES`, que passa a ser fonte unica.
- **Decisao**: componentes `select` e `checkbox` criados no Design System antes de usar, porque nao existiam.
- **Decisao**: CSS do kanban entrou no DS. E o segundo board do produto; o de projetos tem CSS inline no proprio template e continua funcionando.
- **Decisao**: quando a transicao e recusada por falta de campo, o board PERGUNTA o que falta e repete, em vez de reverter o card calado.
- **Decisao**: a ficha edita quem a pessoa e; o board muda em que fase ela esta. Situacao e datas de vinculo ficam fora do formulario pra que toda mudanca gere historico.
- **Output**: commits a7d16c4, 53441f4, b262463, e33fe21, 7543040. 244 testes.
- **Status**: completed

## 2026-07-20 — Prints do produto real revelam 14 gaps

- **Acao**: analise de 14 screenshots do DP da Visio (`people_visio/`), que sao informacao nova: o pacote de handoff declarava que nenhum screenshot foi exportado e que a UI precisaria ser inferida do texto.
- **Output**: `GAPS-VISIO.md` com os 14 mapeados, cada um marcado como resolvido, decisao ou discovery.
- **Achado que contradiz o construido**: uma unidade tem VARIOS links de cadastro ativos ao mesmo tempo. A constraint de um ativo por unidade era invencao nossa, vinda de ler "cada cartao de loja" como "um link por loja".
- **Achado**: cargo e entidade com CRUD, nao texto livre.
- **Achado**: o fluxo tem SETE etapas. Ferias e Afastamentos nao aparecem em lugar nenhum da spec, e Afastamentos era justamente uma das abas que a spec dizia que "nenhuma fonte descreve o que faz".
- **Achado**: a mensagem por etapa e sugestao pro RH, com envio sempre manual. Decisao de produto que teria sido feita ao contrario.
- **Decisao do Lucas**: nao existe camada de Grupo no Hubtrix. Uma empresa com varias unidades, tudo no mesmo tenant. Onde a Visio diz grupo, lemos tenant, que e o que `config_efetiva()` ja fazia.
- **Status**: completed

## 2026-07-20 — Alinhamento com o DP real

- **Acao**: fechamento de sete gaps, mais os passos 10 e 11 do plano original.
- **Output**: commits 13c6105 (links multiplos, Cargo entidade, Ferias e Afastamento, QR), 423dd28 (auto cadastro publico, CRUD de cargo), ecbb7e4 (configuracao do fluxo, templates de formulario, Analises).
- **Decisao**: a view publica usa duas defesas de tenant somadas, escopo e explicito. Nenhuma basta sozinha: explicito nao protege codigo chamado indiretamente (a engine de automacao, disparada pela telemetria, usa `.objects` livremente), e escopo sozinho depende do `finally` num servidor que reusa thread. Ha teste que suja o thread local com outro tenant de proposito.
- **Decisao**: resposta de conflito no formulario publico e generica. Dizer que o CPF ja existe transformaria a pagina num oraculo de "fulano trabalha aqui?", aberto na internet.
- **Decisao**: recurso do fluxo ainda nao construido aparece marcado como em construcao em vez de sumir da tela, pra que o mapa do modulo fique visivel.
- **Decisao**: efetivacao em Analises e por COORTE. Dividir efetivados do mes por cadastrados do mes compara gente diferente e produz numero que sobe quando a operacao piora.
- **Bugs proprios encontrados e corrigidos**: card do board abria `<a>` e fechava `</div>`; classes de CSS inexistentes no formulario de unidade; erro de sintaxe de template que passou pelo `manage.py check`. Os tres levaram a testes novos (varredura de render entre eles).
- **Output**: 293 testes verdes, 20 telas renderizando. Tarefa 208 criada pro que sobrou.
- **Status**: completed

## 2026-07-20 — Auditoria de UX com Playwright

- **Acao**: captura das 23 telas do modulo (desktop e mobile) e comparacao contra o Design System, a pedido do Lucas, que apontou que varias coisas estavam fora do padrao.
- **Output**: commits db3689b (lote de UX) e 9b0594b (rotulo no historico). Script reutilizavel em `tests/e2e/people_visual.py`.

**O que estava errado**

- **Tabelas sem estilo em 6 telas.** Usei a classe `entity-table`, que nao existe no CSS. O componente `entity_table.html` do DS e outra coisa: uma LINHA de entidade pra lista, nao uma tabela. O correto e `.table-wrap` + `.table`. Terceira vez na mesma sessao que inventei nome de classe em vez de copiar do DS.
- **Funil de admissao** montado a mao com flex inline, usando o `progress_bar` (componente de 160px pra celula de tabela) esticado a 1200px, o que virava um traco. O DS ja tinha `breakdown_row`, que e exatamente rotulo + meta + barra + percentual. O proprio docstring do `progress_bar` apontava pra ele.
- **Percentual do funil sobre a maior fase**, o que fazia tres das quatro linhas marcarem 100%. Passou a ser sobre o total.
- **Board com a ultima coluna cortada**: o inline dizia `minmax(186px, 1fr)` e o DS ja da `min-width: 240px` em `.kanban-col`. O item vence a track, entao a conta de largura saia errada.
- **Aba Historico da ficha** mostrava `em_admissao` em vez de `Em admissao`. O `__str__` do model ja usava `estados.rotulo()`; so a tela nao usava.
- **Acentuacao**, terceira ocorrencia no modulo: ~25 strings de interface, rotulos de situacao e etapa, choices de model, itens da sidebar e o catalogo de campos.

**Bug em componente compartilhado**

`breakdown_row` tinha o mesmo defeito de locale que o `progress_bar`: em pt-br com USE_L10N o Django renderiza 28.6 como "28,6", que dentro de `style="width: ...%"` e CSS invalido. O navegador descarta a regra e a barra aparece CHEIA. Falha calada, nao quebra pagina. **O relatorio win/loss do CRM usa esse componente e esta sujeito ao mesmo problema em prod hoje.** Corrigido no componente, entao o CRM se beneficia junto.

**Divida encontrada, nao corrigida**

O shell do layout (`base.html`, `layout_app.html`, `sidebar.html`, `sidebar_subnav.html`) tem ZERO media query. Em largura de celular, sidebar e subnav ocupam 300px e sobra quase nada pro conteudo. **Nao e especifico do People**: toda pagina logada com subnav quebra igual. Nao mexi porque muda o layout de todos os modulos e ha outras sessoes na mesma arvore. O formulario publico do People, que e o unico que o colaborador abre no celular, tem tratamento mobile proprio e funciona.

**Decisao: guard em teste, nao vigilancia**

Cacar esses erros print a print nao estava funcionando (o de acento voltou tres vezes). Dois testes novos em `tests/test_templates_contrato.py`:

- varredura de acento no texto visivel do People. Distingue texto de comentario, ignora atributo de tag multilinha, e promove os parametros de include que viram tela (`label`, `helper`, `title`) sem promover identificador (`name`, `type`). Pegou 25 ocorrencias.
- compilacao de todo template do projeto, que `manage.py check` nao faz.

Os dois tem meta teste provando que pegam o caso real e nao acusam o falso. Motivo: a primeira versao do guard de acento acusava o proprio comentario que explicava o codigo, e uma varredura quebrada passa calada dando falsa seguranca.

- **Limpeza**: `campos_formulario` tinha a chave `label` que ninguem lia, duplicando `rotulo_padrao` e ja divergindo dela (`Numero` contra `Número`). Removida.
- **Status**: completed
