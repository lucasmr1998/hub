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

## 2026-07-20 — Recrutamento e Selecao, passo 1 (tarefa 211)

- **Acao**: base do pipeline. Maquina de saidas terminais e etapa configuravel por unidade. Commit b83f983.
- **Contexto**: corte B do `RECRUTAMENTO-PLANO.md`, escolhido entre tres opcoes. O pre requisito que a spec de origem exige antes de qualquer coisa (`people_staff` mais cadastro do DP, com dedup em constraint) ja estava pago pelo que o modulo entregou.

**A decisao que estrutura o resto do subdominio**

```
ETAPA INTERMEDIARIA  ->  DADO    (EtapaPipeline, por unidade)
SAIDA TERMINAL       ->  CODIGO  (estados_recrutamento.py)
```

O criterio e comportamento, nao estetica. Saida faz coisa: `admitido` aciona a ponte pro DP, `banco_talentos` entra na retencao com expurgo, `inapto` e decisao registrada. Comportamento em tabela de configuracao significa que o cliente cria um estado que o codigo nao sabe tratar, e isso so aparece em producao. Etapa so ordena e nomeia, entao pode ser dado.

Isto e o **oposto** do `estados.py` do DP, onde a maquina inteira e fixa, e a diferenca e proposital: fase de vinculo trabalhista nao e preferencia de cliente, etapa de processo seletivo e. A spec cita uma rede nos EUA rodando so `triagem, entrevista com RH, admissao` contra as sete etapas do default brasileiro.

**Decisoes menores, com o porque**

- **Motivo obrigatorio em toda saida.** A spec marca como coluna real observada em demo que ficou fora da especificacao escrita: *"O campo motivo nao existe em nenhum dos contratos de conclusao dos manifests. E uma coluna real. Modele-a."* Sem ela o board vira cemiterio e a analise de funil so consegue contar.
- **Reabertura assimetrica.** Banco, inapto e arquivado voltam pro pipeline. Se nao voltassem, o RH corrigiria clique errado cadastrando a pessoa de novo, que e a duplicata que a constraint de WhatsApp vai existir pra impedir. `admitido` volta enquanto NAO houver colaborador vinculado e trava depois, porque ai ja existe gente contratada apontando pro candidato. A regra depende do objeto, entao mora no servico; o modulo puro so expoe `pode_reabrir(saida, tem_colaborador_vinculado=)`.
- **Override substitui, nao soma.** Unidade com etapa propria ignora a do tenant. Somar produziria um pipeline montado de dois lugares que ninguem configurou.
- **Desativar etapa nao apaga.** Comportamento observado na origem (*"esse botao ele fica, ele nao some, ele fica invisivel"*). Apagar deixaria orfao o candidato parado nela.

**A peca que quase passa despercebida**

A `UniqueConstraint` usa `nulls_distinct=False`. Unidade nula significa "vale pro tenant inteiro"; sem esse flag o Postgres trata cada NULL como valor distinto, a constraint nao pega nada e o seed acumula uma Triagem nova a cada execucao. Verificado no banco, e nao so no teste: `UNIQUE NULLS NOT DISTINCT (tenant_id, unidade_id, nome)`. Ha teste que pede pro banco recusar a duplicata, porque constraint que ninguem exercita e comentario. Exige PG 15+, e dev e prod rodam PG 17.

- **Nota de ambiente**: a suite colidiu de novo com outra sessao rodando pytest na mesma pasta (`database "test_aurora_dev" already exists`). Resolvido com o `settings_teste_people.py` do scratchpad, que so troca o nome do banco de teste, em vez de derrubar a conexao da outra rodada.
- **Output**: 28 testes novos, 333 no modulo, `manage.py check` limpo, migration 0005 aplicada em dev.
- **Status**: completed. Proximo: passo 2 (Vaga mais RequisitoVaga).

## 2026-07-20 — Recrutamento, passo 2 (tarefa 211)

- **Acao**: Vaga e RequisitoVaga, models mais CRUD. Commits f4a5465 (models) e 13dc8aa (telas).

**A correcao de produto que este passo carrega**

A VAGA E A FONTE DA VERDADE DA DIVULGACAO. No produto de origem, criar a vaga e configurar o link de divulgacao sao fluxos separados, e a criadora aponta isso como o defeito de UX dela, duas vezes, em duas conversas diferentes: *"a ideia e juntar essa etapa de divulgacao com a etapa de vaga. Entao a fonte de verdade vai ser a vaga."* Aqui os requisitos sao editados dentro da propria pagina da vaga, e o LinkCandidatura do passo 3 vai apontar pra ela, nao o contrario.

**Requisito com dois usos, e nao um enum**

`aparece_no_anuncio` e `usar_na_triagem` sao booleanos separados. A spec avisa pra nao colapsar: e o mecanismo que permite filtrar por coisa que nao convem publicar. Um enum de tres valores parece mais enxuto e destroi o caso do meio, que e o mais comum. Exemplo real: "disponibilidade aos domingos" convem publicar; "experiencia minima de 6 meses" o RH prefere filtrar calado, pra nao afastar quem se candidataria.

**Tres constraints, cada uma fechando um estado que a tela deixaria passar**

- `limite_aprovados >= 1`, a regra de parada da triagem (default 50).
- `colaborador_substituido` so existe com justificativa de substituicao. Sem isso, trocar a justificativa depois deixa pendurada a referencia a alguem que ninguem esta substituindo, e o alerta de pendencia no DP passa a apontar pro nada.
- requisito precisa de pelo menos um uso. Um que nem publica nem filtra e dado morto, e a unica forma de descobrir seria estranhar o anuncio ja publicado.

O form espelha as duas primeiras em mensagem no campo certo. A constraint continua sendo a garantia; a validacao de form e a cortesia de nao entregar `IntegrityError` na cara.

**Status da vaga e fixo em codigo**, ao contrario das etapas do pipeline que sao dado. Nao e incoerencia: etapa de processo seletivo e preferencia de cliente, ciclo de vida de vaga nao e. Encerrada nao reabre, porque juntaria duas janelas de captacao no mesmo funil. Republicar depois de pausar preserva a `publicada_em` original, senao o tempo de captacao encolhe sozinho a cada pausa e a vaga parece mais eficiente do que foi.

**Dois erros meus que so aparecem renderizando**

- Passei lista de dicts pro `components/select.html`, que desempacota `for valor, rotulo in options`. Dict ali renderiza as CHAVES como se fossem as opcoes. O resto do modulo ja usava `values_list('pk', 'nome')`; passei a usar tambem.
- Os selects saiam com o `---------` default do Django em vez do "Selecione" que o modulo usa.

Os dois passam por `manage.py check` e por teste de model sem reclamar. Por isso ha teste de render, e por isso a captura com Playwright virou parte do fim de cada passo.

**Seguranca**: o queryset de cada select e filtrado por tenant no `__init__` do form. `ForeignKey.validate()` so confere existencia, nao dono, entao sem isso um POST forjado criaria vaga apontando pra loja de outro tenant. Ha teste que tenta exatamente isso.

- **Permissao**: `people.gerir_vagas` nova, com back-fill nos perfis existentes. Gestor entra junto de Admin, porque na rede de franquia e o gerente de loja quem sabe que esta faltando gente.
- **Fora de escopo, conforme a origem**: o fluxo de aprovacao de vaga (aguardando aprovacao, aprovada, rejeitada) existe no produto porem esta formalmente deferido la, classificado como edge case de rede grande.
- **Output**: 41 testes novos no passo 2 (24 de model, 17 de view), 374 no modulo. Migration 0006 aplicada em dev.
- **Status**: completed. Proximo: passo 3 (LinkCandidatura com QR e atribuicao por canal), que sai derivado da vaga.
