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

## 2026-07-20 — Recrutamento, passo 3 (tarefa 211)

- **Acao**: LinkCandidatura por canal, com QR e atribuicao de origem. Commit e6d4d3e.

**Onde o link mora, e por que importa**

Dentro da pagina da vaga, junto dos requisitos, e nao numa tela de configuracao. E a mesma correcao do passo 2, agora completa: separar obriga a redigitar no link o que ja esta na vaga, e e o defeito que a criadora do produto de origem aponta duas vezes.

`LinkCandidatura.texto_padrao()` e onde "a vaga e a fonte da verdade" deixa de ser frase e vira codigo: o texto de divulgacao sai do cargo, turno e requisitos da vaga. **So entram os requisitos marcados pra aparecer no anuncio**, entao criterio de triagem calado nao vaza pro texto publicado. Ha teste especifico desse nao vazamento, porque e o mecanismo inteiro dos dois booleanos separados do passo 2.

**Tres diferencas deliberadas em relacao ao LinkCadastroUnidade do DP**

| | Link do DP | Link de candidatura | Por que |
|---|---|---|---|
| Quantidade | Varios por unidade | Varios por vaga, **um por canal** | E a atribuicao de origem. Sem ela o franqueado gasta em canal que nao converte sem saber |
| Expiracao | Tem `expira_em` | **Nao expira** | Decisao consciente da origem: *"a gente usa muito Facebook, entao as vezes as pessoas entram la no grupo antigo, publicacao ta la, elas se candidatam"* |
| Teto | Tem `max_submissoes` | **Sem teto** | A regra de parada mora na vaga e e sobre APROVADOS: ao atingir, a triagem para e a captacao continua. Teto no link cortaria a captacao junto |

A ausencia de expiracao tem teste que olha o schema. Ausencia de campo nao quebra nada sozinha, e alguem poderia "consertar" adicionando expiracao sem saber que a falta dela e proposital.

**Decisoes menores**

- **Canal e choices, nao texto livre**, pelo mesmo motivo que Cargo virou entidade: "Facebook", "facebook" e "face" viram tres canais e corrompem justamente a atribuicao que o link existe pra medir.
- **Desativar nao apaga.** Apagar levaria junto as candidaturas que vieram pelo link. Efeito colateral conhecido e avisado na confirmacao: QR ja impresso para de funcionar.
- **QR em SVG**, como no DP: o uso real e cartaz na parede da loja. Uma campanha citada na origem abriu a sexta loja com QR impresso em ponto de onibus.
- **Sem unique por (vaga, canal)**: dois grupos de Facebook diferentes e caso real. Quem distingue e o apelido interno.

**Correcao de UX pega na captura com Playwright**

As transicoes de status saiam em ordem alfabetica, o que punha "Encerrada", que e irreversivel, antes de "Publicada", que e a acao desejada quase sempre. Passaram a sair na ordem canonica da maquina; encerrar virou acao secundaria e ganhou confirmacao explicando que nao reabre.

**PENDENCIA que atravessa pro passo 4**

A pagina publica `/people/candidatura/<token>/` ainda nao existe. Ate o passo 4, o QR gerado aponta pra rota que responde 404. **Nao publicar QR impresso antes disso.** Registrado tambem no commit.

- **Output**: 24 testes novos, 392 no modulo. Migration 0007 aplicada em dev.
- **Status**: completed. Proximo: passo 4, formulario publico de candidatura com dedup por WhatsApp em constraint e o consentimento LGPD com prazo (decisao D3).

## 2026-07-20 — Recrutamento, passo 4 (tarefa 211)

- **Acao**: formulario publico de candidatura, model Candidato, dedup por WhatsApp e retencao LGPD. Commit 38731bf.
- **O que fecha**: o QR do passo 3 apontava pra 404. Agora leva a uma pagina real, mobile-first, sem login.

**Candidato em tabela propria (decisao D1)**

Nao e situacao do Colaborador. Fosse, toda consulta de RH teria que excluir candidato, e o vocabulario racharia. A ponte pro DP anda por `Candidato.colaborador`, FK nula preenchida so na admissao: nao e o candidato que vira colaborador, e o colaborador que passa a referenciar de qual candidatura veio. Os dois coexistem porque respondem perguntas diferentes.

**Dedup por WhatsApp (decisao D2)**

O formulario nao coleta CPF de proposito: a origem testou e descartou por atrito de conversao, e a dor numero um do cliente e "nao chega candidato". CPF entra depois, na aprovacao, pelo formulario do DP, onde a constraint de CPF ja mora. Mesmo tratamento de NULL que o CPF: ausente e NULL, presente e unico por tenant, mais CheckConstraint de formato e normalizacao pra None no save.

O dedup NAO devolve conflito com candidatos, ao contrario do DP. A pagina e publica: confirmar quem esta na base diria "fulano se candidatou aqui" pra qualquer um, e o unico dado pra perguntar e um telefone. Resposta generica. O que o visitante digitou volta pra ele nao redigitar, mas nada do candidato existente vaza. Teste dessa distincao.

**Retencao LGPD (decisao D3)**

Prazo (`dias_retencao_candidato`, default 365) gravado em cada candidato NO ATO, nao calculado na hora do expurgo: se o prazo mudar depois, quem se candidatou sob a regra antiga tem direito a ela. O consentimento mostra o prazo pro candidato na tela. `anonimizar()` tira a pessoa e mantem a linha, porque se a linha sumisse o funil de tres meses atras diria que chegaram menos candidatos do que chegaram. O curriculo e apagado de verdade. O cron que chama isso e o passo 7.

**Seguranca**

Mesma postura da view publica do DP: tenant pelo token com escopo mais tenant explicito, 404 generico, CSRF ligado, rate limit por IP e por token, honeypot com sucesso falso, upload so PDF ou Word ate 5 MB. Rota com prefixo proprio (`people/candidatura/`), e nao sufixo do link do DP, porque sao publicos diferentes. O teste de isolamento suja o thread local com outro tenant DE PROPOSITO antes da request, pra provar que a protecao existe e nao que teve sorte numa suite limpa.

- **Output**: 24 testes novos, 423 no modulo. Migration 0009 aplicada em dev.
- **Status**: completed. Proximo: passo 5, o board do pipeline, onde as etapas viram tela e o candidato passa a se mover por elas ate uma saida.

## 2026-07-20 — Recrutamento, passo 5 (tarefa 211)

- **Acao**: board do pipeline. As sete etapas viram tela e o candidato do passo 4 aparece. Commit 0aade33.
- **Diferenca em relacao ao board do DP**: mover entre etapas e livre (etapa e configuracao, nao maquina; o RH sabe quando pular Teste Pratico), e sair do pipeline e acao com modal, nao arrasto, porque exige motivo e passa por regra (admitido vinculado nao volta).
- **HistoricoCandidato** nasce aqui, fonte do funil. Guarda de_etapa/para_etapa como texto e nao FK, porque etapa pode ser desativada ou renomeada e o historico precisa continuar legivel.
- **Etapa desativada nao some o candidato**: ele aparece numa area "fora de etapa" pra ser realocado, com a conta do funil ainda fechando.

**Dois bugs meus que o teste pegou**

- `FOR UPDATE cannot be applied to the nullable side of an outer join`: o `select_for_update` com `select_related` da etapa (FK nula) quebrava no Postgres. Teria ido pra prod e viraria 500 no board com dois RHs mexendo junto. Relock so a linha do candidato.
- `mover_para_etapa` devolvia objeto novo sem atualizar o passado, o mesmo bug de objeto stale que o `mover_situacao` do DP ja teve. Agora sincroniza os campos de volta no objeto do chamador.

- **Nota de metodo**: varias falhas de teste neste passo foram andaime de teste, nao bug de codigo (fixture sem ConfiguracaoEmpresa, helper de cliente com assinatura errada). Causa: escrevi o fixture sem ler o `_cliente` que ja existia em test_people_configuracao. Ler o padrao existente antes de escrever o proprio teria evitado.
- **Output**: 23 testes novos, 440 no modulo. Migration 0010 aplicada em dev.
- **Status**: completed.

## 2026-07-20 — Recrutamento, passos 6 e 7 (tarefa 211). Corte B fechado.

- **Acao**: quadro por unidade, regra de parada e expurgo LGPD. Commit b7cd860.

**Quadro por unidade (passo 6)**

A moldura que transforma "vaga aberta" em "faltam 5 de 8". Os derivados (ativos, em processo) sao consulta na hora, nunca coluna: contagem guardada e o caminho mais curto pra divergir do real. Ativos le do DP (Colaborador da casa), em processo le do R&S (Candidato no pipeline). A mesma pessoa nao conta duas vezes, porque quem foi admitido ja saiu do pipeline.

**Regra de parada (passo 6)**

Regra 4.4 da spec: ao atingir `limite_aprovados`, a triagem para. Sem IA de triagem, aqui e AVISO e nao bloqueio. Admitir alem do teto continua possivel; a decisao e do RH, e o sistema so garante que passar do teto seja consciente. Teste confirma que admitir o candidato alem do limite passa, com aviso.

**Expurgo LGPD (passo 7)**

Comando `expurgar_candidatos` roda pelo `dispatcher_cron`, anonimiza quem tem `retencao_ate` vencida. Anonimiza, nao deleta: a linha e a origem sobrevivem pra analise de canal nao mentir; o que some e a pessoa e o arquivo do curriculo. `all_tenants` porque e obrigacao legal que vale pra todos de uma vez. Idempotente, com `--dry-run`. O corte e `retencao_ate < hoje`: quem vence hoje ainda tem o dia.

**PENDENCIA DE ATIVACAO (prod)**

O comando existe, porem so roda quando houver um `CronJob` cadastrado apontando pra ele. Antes de confiar no expurgo em prod:

1. Criar `CronJob` com comando `expurgar_candidatos` e schedule diario (ex: uma vez por dia de madrugada).
2. Rodar `expurgar_candidatos --dry-run` uma vez em prod pra ver a contagem antes de anonimizar de verdade.

Sem o passo 1, o codigo esta la mas o dado nunca e expurgado, e a promessa do consentimento nao se cumpre. Mesma classe de pendencia das tarefas 180/181.

**Bug meu**: assumi `Colaborador.cargo` como texto (era assim no plano) e filtrei por nome. Cargo virou FK quando os prints da Visio mostraram CRUD. Filtro por FK agora.

- **Output**: 27 testes novos, 462 no modulo. Migration 0011 aplicada em dev.
- **Status**: completed. **Corte B (passos 1 a 7) fechado.** Fora do corte, cada um com sua razao no RECRUTAMENTO-PLANO.md: triagem IA, entrevista, ponte pro DP, banco de talentos como busca, analise de pipeline, Indeed, Meta.

## 2026-07-21 — Gaps dos prints da Visio: board em chips, saidas navegaveis, tela de fluxo (tarefa 213)

- **Acao**: fechar os tres gaps de alto impacto que os 11 screenshots do produto real revelaram, mais os tres de medio impacto. O corte B tinha sido desenhado sem esses prints; eles sao informacao nova, nao mudanca de escopo.

**1. O board nao escalava.** Renderizava todas as colunas de uma vez, e um print da propria operacao mostra 76 candidatos numa unica etapa. Virou barra de chips (etapa, contador, cor) mais a lista de UMA selecao, com o kanban preservado atras de `?vista=kanban` porque arrastar e melhor com poucos candidatos. As contagens saem de duas consultas agregadas, uma por eixo, nao de uma por chip.

**2. As saidas eram invisiveis (o pior dos tres).** O board filtrava `saida=''`, entao quem saia do pipeline DESAPARECIA da interface. O banco de talentos, que a spec descreve como sendo o produto, era um registro sem tela. Agora as quatro saidas sao chips clicaveis que reusam a mesma lista trocando so o filtro.

**3. Nao havia tela de configuracao do fluxo.** `EtapaPipeline` ja suportava ordem, ativa e sla_dias, mas sem tela o cliente ficava preso nas sete etapas do seed, o que contradiz o proprio desenho de "etapa e dado". Criada `/people/fluxo/` com criar, renomear, cor, prazo, reordenar, ativar e apagar. Editar reusa o formulario de criar.

- **Decisao**: as duas guardas da tela de fluxo sao a parte que importa, nao o CRUD. Nao apaga etapa com candidato dentro (deixaria a pessoa orfa; com gente dentro o caminho e desativar) e nao reseta o fluxo com candidato no meio. Desativar preserva o vinculo e joga o candidato pro chip "Fora de etapa", calculado como o resto entre o total por etapa e os ids das etapas vivas: sem esse chip, desativar uma etapa esconderia gente.

- **Decisao**: `api_lote` processa um a um pelos servicos, nunca `queryset.update()`. Update em massa pularia `HistoricoCandidato` e o candidato perderia a trilha, que e o que responde "quanto tempo esse processo levou".

- **Campo novo**: `EtapaPipeline.cor` (migration 0015), com paleta em `estados_recrutamento.py` e fallback pela ordem quando vazia. A cor tambem alimenta o ponto do chip no board, entao nao e decoracao: e o que da continuidade visual entre as duas telas.

**Bugs meus, achados nos prints depois de prontos:**

- `.lote-barra { display: flex }` numa classe vence o `[hidden]` do user agent, entao a barra de acao em lote aparecia dizendo "0 selecionados" com nada selecionado. Precisou de `.lote-barra[hidden] { display: none }` explicito.
- O divisor vertical "SAIDAS" entre os chips se soltava na quebra de linha, deixando saidas em duas fileiras separadas. Virou um grupo proprio com rotulo lateral.
- O handler de clique do card estava DEPOIS da guarda `podeMover`, entao quem so tinha `people.ver` nao conseguia abrir a ficha. Abrir ficha e leitura: o handler foi pra antes da guarda.

- **Output**: 498 testes passando no modulo (`test_people_fluxo_config.py` novo com 15; `test_people_pipeline_board.py` foi de 18 pra 27). `manage.py check` limpo. Migration 0015 aplicada em dev.
- **Status**: completed em dev, **nao pushado**. Aguardando validacao visual do Lucas antes de subir.

## 2026-07-21 — Campos de candidatura criados pelo tenant (CampoCandidatura)

- **Acao**: o Lucas olhou a tabela de campos da vaga e perguntou "n tem campo de telefone por exemplo". Duas coisas sairam dai: a resposta imediata (telefone ESTA la, e o WhatsApp travado, mas a tela escondia os travados e explicava a ausencia em prosa acima do card, fora do campo de visao) e a pergunta de fundo, que era poder criar campo proprio. Feito o segundo, com o primeiro de carona.

- **Decisao**: model proprio (`CampoCandidatura` em `apps/people`), e nao reuso do `CampoCustomizado` de `comercial/leads`. Reusar seria zero tabela nova, mas People e modulo vendido separado e passaria a importar de comercial; alem disso a tela de gestao dos campos de lead viraria gaveta de entulho com entidades de outros modulos. O contrato foi copiado do que ja funciona la (nome, slug, tipo, opcoes, ordem, ativo), entao o modelo mental e o mesmo sem o acoplamento.

- **Decisao**: o tenant DEFINE o campo, a vaga ESCOLHE se pede. Mesma divisao dos campos de sistema, pelo mesmo `config_campos`. Um segundo modelo mental faria o usuario ter que aprender qual campo se configura onde.

**As quatro decisoes que sustentam a feature:**

1. **Chave prefixada com `custom__`.** Sem prefixo, um tenant que criasse a chave "email" produziria um campo homonimo do de sistema, e o POST, a config da vaga e a validacao passariam a disputar a mesma chave calados. O prefixo torna a colisao impossivel por construcao, em vez de depender de lista de nomes proibidos que envelhece.
2. **O expurgo LGPD zera `dados_custom` inteiro**, sem olhar o conteudo. O campo e inventado pelo tenant: se a limpeza fosse por chave conhecida, um campo "CPF" ou "Nome da mae" sobreviveria a retencao e a promessa do consentimento quebraria em silencio. Era o custo escondido que eu tinha levantado ANTES de implementar, e entrou no mesmo commit, nao depois.
3. **Campo novo nasce desligado nas vagas.** Criar um campo no nivel do tenant nao pode, sozinho, mudar o formulario de vaga que ja esta no ar recebendo gente.
4. **O slug nao muda na edicao.** E a chave das respostas gravadas; trocar deixaria toda resposta anterior orfa sem erro nenhum. Renomear o rotulo continua livre.

- **Catalogo continua puro**: `campos_candidatura.py` recebe os campos do tenant como parametro (`extras`), ja convertidos por `como_campo()`. Quem consulta o banco e o model. Mantem o modulo testavel em milissegundos.

- **Componente novo**: `components/textarea.html`, que faltava na biblioteca. `.field-input` fixa `height: 38px`, entao precisou de `.field-textarea` com altura automatica.

**Bug de design system, achado pela segunda vez em dois dias:**

`[hidden]` do user agent tem especificidade de elemento, entao QUALQUER classe nossa com `display` vence e o elemento aparece com o atributo. Ontem foi a `.lote-barra` do board ("0 selecionados" com nada selecionado); hoje foi o botao "Cancelar edicao" visivel sem edicao nenhuma. Duas ocorrencias e sinal de que o fix pontual estava errado: virou regra global `[hidden] { display: none !important; }` em `_components_styles.html`, e o remendo local do board foi removido.

**Armadilha de ambiente, que me custou dois ciclos de print:**

Django 4.1+ usa o cached template loader MESMO em DEBUG. Com `runserver --noreload`, edicao de template fica invisivel ate reiniciar o processo. Foi o que fez o print mostrar o botao "Cancelar edicao" ainda visivel depois do fix ja estar no arquivo. Mesma causa do "8003 servindo template velho" anotado ontem. Regra pratica: mexeu em template com `--noreload`, reinicia antes de conferir.

- **Correcao de brinde**: no `sidebar_subnav.html`, o item Configuracoes acendia junto com Fluxo porque o teste era `'config' in url_name`, e `fluxo_config` contem 'config'. Trocado por prefixo. Ja aparecia errado no print de ontem.

- **Output**: 520 testes no modulo (16 novos em `test_people_campos_custom.py`). Migration 0016. `manage.py check` limpo.
- **Status**: completed em dev, **nao pushado**, junto com a tarefa 213. Aguardando validacao.

## 2026-07-21 — INCIDENTE em prod: 500 na ficha e candidatura descartada pelo honeypot

- **Acao**: dois bugs achados pelo Lucas em producao, no mesmo dia do deploy dos campos custom. Corrigidos no commit 2741ec7.

### Bug 1: 500 em /people/candidatos/<pk>/ (introduzido por mim hoje)

Ao adicionar `_respostas_custom`, inseri a funcao ENTRE o decorator
`@requer_people` e a view `detalhe`. O decorator passou a decorar a auxiliar, que
recebe `candidato` no lugar de `request`, e estourava em `test_func(request.user)`.

**O 500 era o sintoma barulhento. O silencioso era pior:** `detalhe` ficou sem
checagem de permissao nenhuma. O isolamento por tenant continuou (TenantManager
filtra), mas qualquer usuario logado do tenant abriria a ficha de um candidato,
que e PII.

**Por que passou:** nao havia UM teste abrindo essa view. So o endpoint do
curriculo tinha cobertura. Entraram quatro testes (abre, exige permissao, mostra
o rotulo do campo custom, ignora resposta de campo apagado). Varredura no
projeto inteiro atras da mesma classe de erro (decorator em funcao privada):
caso unico.

### Bug 2: honeypot descartando candidato real (anterior a hoje)

O campo se chamava `sobrenome_confirmacao`, fora da tela por CSS e nao por
`type=hidden`, de proposito, pra preenchedor automatico cair nele. **O Chrome
IGNORA `autocomplete=off` em campo que parece dado pessoal**, e "sobrenome" e
justamente o token que ele reconhece.

O candidato abria o formulario, o navegador preenchia o campo escondido junto
com o resto, e a view devolvia a pagina de SUCESSO sem gravar nada. Um candidato
real perdido hoje, sem rastro nenhum: os dados dele nao dao pra recuperar.

Diagnostico por ELIMINACAO, nao por log: e o unico caminho do codigo que mostra
sucesso sem criar candidato. Duplicidade mostraria erro; falha na etapa inicial
deixaria o candidato no banco sem etapa. Confirmado no banco de prod que existe
um so candidato (o teste de 04:58 UTC) e que o link tem `candidaturas=1`.

**O mesmo campo, com o mesmo nome, estava no formulario publico do DP.** Os dois
corrigidos.

- **Decisao**: o nome virou constante unica (`apps/people/utils.py::NOME_HONEYPOT`)
  e vai pro template pelo CONTEXTO. Chumbado dos dois lados, um dia divergiriam,
  e ai o honeypot para de funcionar em silencio, o que e pior que nao ter.
- **Decisao**: a rejeicao passa a ser REGISTRADA no lado de recrutamento. Ja era
  no DP (SubmissaoLinkCadastro). Honeypot que erra calado nao tem como ser
  auditado, e o custo do falso positivo e um candidato perdido.
- **Teste que trava o nome**: falha se o campo escolhido contiver qualquer token
  que o autofill reconhece (nome, sobrenome, email, tel, cpf, endereco, etc).

### Achado colateral, fora do escopo de People

`apps/sistema/decorators.py:175` trata **usuario sem `PermissaoUsuario`
cadastrado como acesso total** ("retrocompat legado"). Vale pra TODOS os modulos.
Meu teste de permissao passou por engano ate eu perceber. Nao mexi, porque muda
o comportamento do sistema inteiro, mas e regra que envelhece mal e merece
decisao propria.

### Licao de processo

Os dois bugs sao da mesma familia: **codigo que falha em silencio**. O decorator
orfao removeu uma protecao sem erro nenhum, e o honeypot descartava gente sem
deixar registro. Nos dois casos o conserto nao foi so corrigir, foi tornar a
falha VISIVEL (teste que abre a view, log na rejeicao).

- **Output**: 526 testes no modulo. Sem migration. Deploy 21/07.
- **Status**: completed. Pendencia com o Lucas: pedir pro candidato reenviar,
  porque o dado dele nao foi gravado em lugar nenhum.

## 2026-07-21 — Atraso por etapa, captacao continua e taxa de conversao (tarefas 217 e 216)

- **Acao**: fechar duas promessas quebradas do recrutamento (217) e dar o denominador que faltava pra decidir verba por canal (216).

### Tarefa 217

**`sla_dias` era campo morto.** O help_text do model e o helper da tela de fluxo prometiam "depois disso o candidato aparece como atrasado nesta etapa", e nada calculava. Faltava saber DESDE QUANDO: entrou `Candidato.etapa_desde`, preenchido por `mover_para_etapa`. Nao serve `atualizado_em`, porque corrigir o telefone do candidato zeraria o relogio sem ele ter andado no processo. A migration 0017 faz back-fill pelo `HistoricoCandidato`, com fallback pro `criado_em`; sem isso o recurso nasceria mostrando "sem atraso" pra quem ja esta no pipeline.

**Link de banco de talentos nao era criavel.** O model aceitava nulo, o help_text documentava, a view publica tratava e havia TESTES cobrindo. So nao existia botao. `/people/captacao/` e a porta.

- **Decisao**: descartei do escopo a etapa "Teste Comportamental", que eu tinha listado como rotulo sem comportamento. Revisto e admitido: a etapa e so o nome de uma coluna e nada na interface promete enviar teste. Um RH aplica o teste por fora e move o card. Isso e gap de IA, nao promessa quebrada. Eu tinha escalado e desescalado esse item duas vezes antes de concluir.

### Tarefa 216

**Conta VISITANTE, nao acesso.** Candidatura e uma pessoa; com acesso no denominador, a taxa nao significaria nada.

- **Decisao**: cookie proprio, e NAO a sessao do Django. A sessao mora em tabela e o `clearsessions` nao roda em lugar nenhum do projeto (prod tinha 144 linhas, 100 vencidas e nunca limpas). Uma sessao por visitante anonimo de QR faria essa virar a tabela que mais cresce, sem nada limpando. Ha teste garantindo que visita nao cria sessao.
- **Decisao**: filtro de User-Agent. WhatsApp e Facebook buscam a URL pra montar o preview, e sao justamente os canais em uso: sem o filtro, divulgar ja geraria movimento que ninguem fez. Heuristica assumidamente incompleta; o objetivo e tirar o vies SISTEMATICO dos previews, nao barrar abuso (pra isso ha rate limit).
- **Decisao**: esconder a taxa quando ela nao e confiavel. Link anterior a medicao daria numero acima de 100%, e numero que nasce quebrado destroi a confianca na tela inteira. A celula diz "medindo visitas desde <data>" ate alcancar.
- Limites assumidos e documentados: cookie bloqueado e troca de aparelho contam a mais. Os dois erram PRA CIMA, entao a taxa real e melhor que a exibida. Errar pro lado pessimista e o certo pra decidir verba.

**Componente extraido**: `people/_link_conversao.html`, no segundo uso (aba Divulgacao e Captacao continua). A regra de quando NAO mostrar a taxa e justamente a parte que nao pode divergir entre as duas telas.

- **Output**: 559 testes no modulo (15 da 217, 18 da 216). Migrations 0017, 0018 e 0019 aplicadas em dev. `check` limpo.
- **Status**: completed em dev. **Nao pushado.**

## 2026-07-21 — Limpeza dos candidatos de teste em prod

- **Acao**: apagados 6 candidatos de teste, mantido o unico real (James Dean). Autorizado pelo Lucas, com confirmacao explicita do registro ambiguo (um deles tinha nome completo, Gmail e curriculo com cara de real).
- **Decisao**: o contador `LinkCandidatura.candidaturas` foi RECALCULADO da contagem real, e nao decrementado. Ele e denormalizado e nao decrementa sozinho no delete; subtrair propagaria qualquer divergencia previa. Sem isso a taxa de conversao da 216 nasceria mentindo, com denominador certo e numerador inflado.
- **Pendencia**: os cinco PDFs de curriculo continuam no volume `private_media` do servidor. Daqui so ha acesso ao banco, e apagar a linha nao apaga o arquivo. E dado pessoal orfao, um deles um contrato social. Comando de limpeza entregue pro Lucas rodar no console do EasyPanel.
- **Pergunta RESPONDIDA (21/07)**: o candidato id=2 tinha sido criado sem curriculo com o campo aparentemente obrigatorio. O Lucas confirmou que mexeu no toggle depois daquele envio, entao o candidato entrou enquanto o campo ainda era opcional. **Nao ha furo na validacao**; a obrigatoriedade esta valendo.

## 2026-07-21 — Tarefas 216 e 217 concluidas, e o estado real de prod

- **Acao**: deploy confirmado com as migrations 0017, 0018 e 0019 aplicadas, e os DOIS back-fills verificados em prod (6/6 candidatos com `etapa_desde`, os 2 links com data de medicao). Tarefas 216 e 217 marcadas como concluidas no Workspace, com `log_execucao` preenchido.

- **Taxa de conversao funcionando em producao**, medida logo apos o deploy: link 1 com 4 candidaturas em 10 visitas (40%), link 2 com 2 em 8 (25%). As duas exibiveis, e o filtro de robo nao esta derrubando gente real.

- **Prod tem uso REAL agora.** Depois da limpeza dos testes, chegaram 5 candidatos de verdade e apareceu um segundo link. Confirmado com o Lucas: nao sao testes. A partir daqui, qualquer limpeza de dado em prod precisa de identificacao individual, porque nao da mais pra distinguir teste de candidato pelo nome.

- **Padrao que se repetiu tres vezes hoje**: sessoes concorrentes pushando trabalho meu sem aviso (tarefa 213 de manha, depois 216 e 217). Nao quebrou nada, mas "commitado, aguardando validacao" deixou de significar "nao esta no ar". Ou `main` passa a ser tratado como sempre-deployavel, ou trabalho nao validado fica sem commit, o que contraria o CLAUDE.md 1.10.

### Pendencias abertas com o Lucas

1. **Cinco PDFs orfaos** no volume `private_media` do servidor, da limpeza dos testes. Dado pessoal, um deles um contrato social. So o console do EasyPanel alcanca.
2. **Tres ajustes de upload**, e com gente se candidatando agora este e o que mais custa: aceitar IMAGEM (candidato de vaga operacional fotografa o curriculo), tirar a obrigatoriedade do curriculo, e corrigir o `ERR_UPLOAD_FILE_CHANGED` lendo o arquivo em memoria.
3. **CronJob do expurgo LGPD** segue sem confirmacao de que roda. Ficou mais critico depois dos campos custom, porque o tenant pode gravar dado sensivel que ele mesmo inventou.

## 2026-07-21 — Curriculo aceita imagem, e o conserto do ERR_UPLOAD_FILE_CHANGED (tarefa 218, item 1)

- **Acao**: primeiro item do bloco de mecanica universal levantado nos prints da Visio. Escolhido primeiro porque era o unico travando candidato REAL: o curriculo estava obrigatorio na vaga em prod, entao quem batia no erro do Chrome nao conseguia se candidatar de jeito nenhum.

- **Decisao**: aceitar imagem (`.jpg`, `.jpeg`, `.png`, `.webp`, `.heic`). Candidato de vaga operacional fotografa o curriculo impresso. `.heic` porque e o padrao do iPhone, e sem ele metade dos candidatos de iOS esbarra num formato que o proprio aparelho gerou.
- **Decisao**: os TRES lugares que falam de formato passam a derivar de `EXTENSOES_CURRICULO`. Estavam chumbados, e foi exatamente esse tipo de divergencia que matou o honeypot hoje de manha.
- **Conserto do ERR_UPLOAD_FILE_CHANGED**: le os bytes na selecao e troca o arquivo do input por copia em memoria. Validado no navegador de verdade, com arquivo de 30 dias no disco virando `lastModified` de agora. Teste de template garante que o bloco nao seja removido por engano, porque o erro acontece no aparelho do candidato e nao gera log nenhum aqui.

- **Bug meu no processo**: os 4 testes que fazem POST passavam isolados e falhavam na suite completa. Causa: o rate limit de 5 POSTs por minuto e compartilhado entre arquivos de teste que batem no mesmo endpoint. Ja existia a fixture `sem_rate_limit` nos outros arquivos e eu nao a segui. Corrigido.

- **Nao mexido de proposito**: a obrigatoriedade do curriculo. O padrao de fabrica ja e OPCIONAL; quem marcou como obrigatorio na vaga em prod foi o Lucas, e desmarcar e um clique na tela dele. Nao vou dar UPDATE em config de prod por conta propria.

- **Output**: 578 testes no modulo, 19 novos. Sem migration.
- **Status**: completed em dev, nao pushado.

## 2026-07-21 — Mensagem de WhatsApp por etapa (tarefa 218, item 6)

- **Acao**: segundo item do bloco. Escolhido logo depois do upload porque era o mais barato da lista inteira: e REUSO, nao construcao. O `MensagemEtapa` do DP ja existia com a mesma decisao de produto no docstring.

- **Decisao**: model proprio (`MensagemRecrutamento`) em vez de estender o `MensagemEtapa` do DP. O do DP e chaveado pelas situacoes do DP, que sao constantes; aqui a etapa e uma LINHA configuravel. Forcar os dois no mesmo model deixaria o campo `etapa` polimorfico e mais dificil de ler que a duplicacao.
- **Decisao**: `CheckConstraint` garantindo etapa OU saida, nunca os dois nem nenhum. Verificado no banco de dev: as duas combinacoes invalidas sao recusadas pelo Postgres, nao so pelo Python.
- **Decisao**: saida tem precedencia sobre etapa. Quem saiu continua apontando pra ultima etapa, e mandar a mensagem daquela etapa pra quem foi reprovado seria constrangedor.
- **Decisao**: `wa.me` e nao API. Funciona pra qualquer cliente, sem integracao contratada, sem custo por mensagem e sem risco de bloqueio de numero. Copiado da origem de proposito.
- O link e montado NO CLIQUE, e nao na renderizacao: o RH pode ter editado o texto, e o link precisa levar o que esta na tela naquele momento.

- **Bug meu**: usei `{{ "{{nome}}" }}` pra mostrar o placeholder literal na tela de ajuda, e o parser do Django quebra nisso. O certo e `{% verbatim %}`. Pego por compilar o template explicitamente, e nao por print.
- **Bug meu**: coloquei o bloco de WhatsApp ENTRE dois painteis de aba, o que faria ele aparecer em posicao diferente conforme a aba ativa. Movido pro fim, depois de todos os painteis: e acao, nao conteudo de aba.

- **Anotado pra depois**: a tela de fluxo agora empilha 11 textareas (7 etapas mais 4 saidas), cada uma com botao proprio. Funciona, porem fica longa. Se incomodar, vira accordion.

- **Output**: 595 testes no modulo, 17 novos. Migration 0020.
- **Status**: completed em dev, nao pushado.

## 2026-07-21 — Ponte pro DP e triagem por IA (tarefa 218, itens 13 e 8)

### Ponte pro Departamento Pessoal

- **Acao**: fechada a ultima lacuna estrutural do corte B. A FK `Candidato.colaborador` existia desde o inicio esperando quem a preenchesse.
- **Decisao**: COPIA, e nao vinculo. As condicoes da vaga sao copiadas no ato da admissao e nao ha ligacao viva depois. E requisito trabalhista, nao preferencia: o que valeu na contratacao tem que continuar valendo mesmo que a vaga seja reaproveitada e editada. O teste que protege isso e o mais importante do arquivo.
- **Decisao**: entra em `em_admissao` e nasce `pendente_revisao=True`. Falta CPF, e a fase de admissao do DP existe justamente pra coletar. Entrar em experiencia pularia a coleta.
- **Decisao**: `tipo_contratacao` da vaga (texto livre) so e copiado pro `regime_contratacao` do colaborador (choices) quando CASA com uma das opcoes. Copiar sem conferir gravaria valor que outras telas filtram e nunca encontrariam.
- **Decisao**: conflito de dedup devolve `acao='conflito'` em vez de criar segunda linha. Ex funcionario voltando ja existe no DP, e quem decide se e a mesma pessoa e o RH.

### Triagem por IA

- **Decisao que corrige a minha propria proposta anterior**: SOB DEMANDA, por botao, e nao por cron. Eu tinha proposto fila e cron por causa do custo e do tempo de request; os prints mostraram que a origem faz por botao, e isso resolve os dois de uma vez. Sincrono e certo aqui: e um botao que o usuario apertou e esta esperando.
- **Decisao**: NUNCA move o candidato. Ha teste garantindo que nem com veredito "inapto" ele sai do lugar. Automatizar a recusa seria decidir contratacao por LLM, sem ninguem pra responder por ela.
- **Decisao**: RECUSA analisar sem requisito de triagem cadastrado. Sem criterio declarado a IA inventa o proprio, e a consistencia que ela promete vira arbitrariedade com cara de objetividade.
- **Decisao de privacidade**: nome, WhatsApp, email e endereco de rua NAO vao pro prompt. Nao ajudam a avaliar aptidao e so aumentam a exposicao de dado pessoal a um terceiro. Cidade e bairro entram porque deslocamento e criterio real em vaga operacional.
- **Decisao**: veredito inventado pelo modelo cai em "insuficiente", que e o lado seguro: nao afirma nada sobre a pessoa e pede olho humano. Aceitar a categoria gravaria lixo num campo que outras telas filtram.
- **Instrumentado de proposito**: modelo e tokens gravados por analise. "Quanto custa" era discussao aberta, inclusive na origem, que registra o tema como pergunta de precificacao em aberto. Com o consumo gravado, a pergunta se responde com dado real em uma semana.
- **DEPENDENCIA NOVA**: `pypdf==6.14.2` no requirements. Python puro, sem dependencia de sistema, mesmo criterio que escolheu o `segno`. **Atencao no proximo deploy**: o build do EasyPanel vai instalar. Imagem nao e lida (precisaria de OCR); quem manda foto e analisado pelo formulario, com `usou_curriculo=False` registrado.

- **Output**: migrations 0020 e 0021. Testes novos: 16 da ponte, 16 da triagem.
- **Status**: completed em dev, nao pushado.

## 2026-07-21 — Curriculo volta a aceitar so PDF e Word (reversao)

- **Acao**: removido o suporte a imagem entregue horas antes no mesmo dia.
- **Decisao do Lucas**, e o motivo e coerencia de sistema: a triagem por IA le PDF e nao le foto, o que exigiria OCR. Aceitar imagem produziria candidato que entra no sistema e nao pode ser triado. Fila de curriculo que ninguem consegue processar e pior que a recusa na porta.
- **Consequencia registrada em teste e na doc**: quem so tem foto do curriculo impresso nao anexa. Com o campo obrigatorio, essa pessoa nao se candidata. As duas configuracoes andam juntas, e o toggle de obrigatorio segue pendente com o Lucas.
- O teste `test_imagem_NAO_e_aceita` trava a decisao: se alguem reabrir, tem que decidir OCR junto.
- O conserto do `ERR_UPLOAD_FILE_CHANGED` **continua valendo**: e independente do formato e resolve o erro que derrubou candidato real.
- **Output**: 19 testes no arquivo de formatos.

## 2026-07-21 — Ficha por etapa e perfil Avaliador (tarefa 218, itens 5 e 4)

- **Acao**: o Lucas escolheu a opcao A (copiar a estrutura da Visio). A ficha deixou de ser consulta e passou a ser onde o processo acontece.

- **Decisao que diferencia da origem**: as abas sao GERADAS das `EtapaPipeline` configuradas, e nao chumbadas. La o pipeline e fixo, aqui etapa e dado. Ha teste (`test_etapa_criada_pelo_cliente_vira_aba`) que existe justamente pra travar isso: se alguem chumbar as abas, a tela de fluxo vira mentira.
- **Model novo `AnotacaoEtapa`**: uma anotacao por etapa por candidato, com constraint. Por etapa e nao num campo unico porque, numa contratacao contestada, "o que o entrevistador anotou na Selecao" e pergunta diferente de "o que o gestor anotou na Avaliacao". Guarda quem editou por ultimo, que e a primeira pergunta nesse cenario.
- **Colisao achada no print**: a aba fixa "Historico" batia com a ETAPA padrao chamada "Historico". Renomeada pra "Movimentacoes", que tambem e mais preciso: ali so entra transicao, nao conteudo de trabalho.
- **Perfil Avaliador** (`people.avaliar`): anota e so. Nao move, nao abre vaga, nao admite. Com USUARIO, contra o link sem login da origem, por decisao do Lucas. O principio que ficou registrado: link publico e pra quem esta FORA da empresa; quem esta dentro tem conta.

- **Output**: migration 0022. 16 testes novos.
- **Status**: completed em dev, nao pushado.

## 2026-07-21 — Blocos por etapa: as abas passam a ter conteudo proprio

- **Defeito que o Lucas viu**: as sete abas da ficha mostravam a mesma coisa. Nao era bug (cada painel tinha id e nome corretos), era o que eu tinha colocado dentro: titulo, selo e um campo de anotacao vazio. Eu construi o container sem o conteudo.
- **Causa de fundo, e o meu erro**: na origem cada aba tem conteudo proprio porque o pipeline dela e FIXO e conhecido. As nossas etapas sao configuraveis, entao eu so tinha conteudo generico pra por. Isso eu deveria ter dito ANTES de codar, e nao depois de ele ver a tela. Mesmo erro do dia: portar a forma da Visio sem checar se o nosso desenho comporta.

- **Solucao**: `EtapaPipeline.blocos`, e cada bloco FAZ alguma coisa (codigo), enquanto QUAL etapa usa QUAIS blocos e dado. Mesmo criterio que separa etapa de saida no modulo.
- **As sete etapas padrao ja nascem com os blocos da origem**: Selecao com analise, roteiro, requisitos e notas (a "Entrevista RH" deles); Teste pratico com agendamento; Avaliacao Gestor com decisao; Admissao com a ponte pro DP. E o que permite copiar a ESTRUTURA sem herdar o PIPELINE.
- **Back-fill na migration 0023**: sem ele, toda etapa existente ficaria com `blocos=[]` e a aba nasceria vazia, inclusive em prod. Casa pelo nome; etapa criada pelo cliente recebe o minimo util.
- **Decisao**: `decisao` REGISTRA e nao move. Decisao errada e facil de corrigir; movimento automatico ja teria disparado mensagem e historico.
- **Decisao**: bloco desconhecido e filtrado (`blocos_validos`) em vez de quebrar a tela. Bloco removido do codigo continuaria gravado nas etapas dos tenants.
- Os blocos que ja existiam (analise IA, admissao, mensagem) sairam do fim da pagina, onde apareciam iguais em toda aba, e foram pra dentro da aba certa.

**Tres armadilhas de template que apareceram:**

1. Formulario aninhado: o bloco de IA tinha `<form>` proprio e passou a viver dentro do formulario da etapa. Trocado por `formaction` no botao.
2. Id duplicado: o bloco de mensagem repete uma vez por aba, e `id="abrir-whatsapp"` faria todos os botoes controlarem o textarea da primeira. Id por etapa.
3. `|join:"
"` dentro de atributo HTML gera quebra de linha literal, e o markup e o JSON saem invalidos. Trocado por `json_script`, que e o jeito certo no Django.

- **Output**: migration 0023. 652 testes no modulo, 25 no arquivo da ficha.
- **Status**: completed em dev, nao pushado.

## 2026-07-21 — Board e etapas alinhados ao produto RODANDO, e nao a spec

- **Achado do Lucas**: mandou o print do board real da Visio, e ele nao bate com a lista que eu semeei. Eu tinha portado as sete etapas da spec de handoff (`Triagem, Historico, Teste Comportamental, Selecao, Teste pratico, Avaliacao Gestor, Admissao`), e a propria spec avisava que os nomes eram PROPOSTA, nao leitura do schema.

**O board real tem SEIS etapas, e "Historico" nao existe:**

| Eu semeei (da spec) | Produto rodando (print) |
|---|---|
| Triagem | Análise de inscrição |
| **Histórico** | *nao existe* |
| Teste Comportamental | Perfil comportamental |
| Seleção | Entrevista / Seleção |
| Teste prático | Teste Prático |
| Avaliação Gestor | Avaliação Gestor |
| Admissão | Admissão |

- **Licao**: terceira vez no dia em que seguir a spec sem confrontar com print me custou trabalho. A regra que fica: **print do produto rodando ganha da spec escrita, sempre.**

**Outras diferencas do board, tambem corrigidas:**

- **Filtro por CANAL e por PERIODO**, que a origem tem e o nosso nao tinha. Canal responde "que canal esta trazendo gente"; periodo separa a safra da semana do acumulado, e num board com 400 candidatos e a diferenca entre a tela servir e nao servir.
- **Dias na etapa no card do kanban**. Ja existia na lista; no card so aparecia quando havia atraso. Com 80 candidatos numa coluna, "ha quanto tempo esta parado" e o que decide quem olhar primeiro.
- **Motivo de saida em LISTA FECHADA** (era texto livre). Com texto livre nunca da pra responder "por que a gente reprova", porque cada RH escreve diferente e nao ha o que agregar. A lista sai dos cards de Inaptos do print. "Outro" existe pra nao prender o RH, e ai o detalhe livre vira OBRIGATORIO, porque "Outro" sozinho nao diz nada. Fecha o item 7 da lista de gaps.

- **ATENCAO PRA O DEPLOY**: o seed novo so vale pra TENANT NOVO. A aurora-hq (e qualquer tenant existente) continua com as sete etapas antigas, inclusive a "Historico". Renomear ou apagar e mudanca de dado em prod e depende de decisao do Lucas: ele pode fazer na tela de fluxo, ou eu escrevo um comando pra alinhar.

- **Output**: migration 0024 (motivo_saida_codigo). 652 testes. Vinte e poucos testes ajustados por causa dos nomes de etapa.
- **Status**: completed em dev, nao pushado.

## 2026-07-21 — Board com paridade visual com a origem

- **Acao**: o Lucas mandou os dois prints do board real (lista e pipeline) e pediu paridade. Cinco diferencas fechadas.

1. **A lista virou GRADE DE CARDS**, e nao tabela. A tabela dava mais densidade, porem obrigava a abrir a ficha pra qualquer acao; com 82 candidatos numa etapa, abrir e voltar 82 vezes e o que faz o RH desistir da tela.
2. **Card unico pras duas vistas**, de proposito: card diferente por vista faria a acao rapida existir num lugar e nao no outro. Ganhou telefone, dias na etapa com aviso de prazo, e acoes rapidas (avancar, tirar do processo, reativar, curriculo).
3. **Saidas viraram coluna no kanban**, com limite de 20 cards e link "ver todos": o banco de talentos da origem tem 423 pessoas, e renderizar tudo travaria a tela. Coluna de saida NAO aceita soltar, porque toda saida exige motivo e o arrasto nao tem onde perguntar.
4. **Chips inline, numa linha so.** A versao anterior usava caixa por chip com o numero grande embaixo e ocupava tres vezes mais altura. Num board a lista e o conteudo, e o filtro nao pode empurrar ela pra baixo da dobra.
5. **Rotas num elemento que existe nas duas vistas** (`#pipeline-dados`). Antes viviam no `.kanban-board`, entao a acao do card nao funcionava na lista.

**ERRO GRAVE MEU NO PROCESSO, que vale registrar:**

Editei o template com `s.index(ancora_inicio)` e `s.index(ancora_fim)` por string. A ancora de fim (`{% if vista == 'kanban' %}`) aparecia ANTES no arquivo, no link de alternar vista. O slice virou string vazia, e `s.replace('', novo)` inseriu o bloco entre CADA CARACTERE: o arquivo foi de 14 KB pra **25 MB**, com 15.462 copias.

Recuperado com `git checkout HEAD --` (o commit anterior salvou) e refeito com a ferramenta de edicao, que exige ancora unica e falha alto quando ha ambiguidade. Onde precisei recortar um trecho grande, usei NUMERO DE LINHA achado por ancora unica, e nao index de string.

**A licao**: `str.index` numa ancora que se repete nao avisa, so devolve a errada. Editor com verificacao de unicidade existe justamente pra isso, e eu tinha um a mao.

- **Output**: 652 testes. Sem migration.
- **Status**: completed em dev, nao pushado.

## 2026-07-22 — Board numa superficie branca, e filtro que troca so o conteudo

- **Acao**: dois pedidos do Lucas sobre o board de candidatos. "visualmente n ta agradavel, deveria ter um fundo branco" e "no filtro n deveria trocar de pagina, deveria somente recarregar os conteudos".

**1. Fundo branco.** Filtro, chips e selecao viviam soltos direto no cinza da pagina, o que fazia a tela parecer rascunho. Agora o board inteiro vive numa `.section-card` unica, com um risco separando o filtro da selecao. **Cuidado com os tokens**, que e o erro mais comum aqui: `--color-bg` e a superficie de CARD (branco) e `--color-surface` e o fundo da PAGINA. Trocar os dois faz o card sumir no fundo.

De quebra, o form de filtro virou GRADE. Com flex os campos tinham larguras diferentes (a Vaga esticava, o Periodo caia sozinho pra linha de baixo) e a barra virava escada.

**2. Busca parcial.** Filtrar e trocar de chip agora buscam so o miolo (`?parcial=1`) e trocam o `innerHTML`, com `history.pushState`. A pagina cheia tem 107 KB e o parcial 9 KB.

Tres decisoes que sustentam isso:

- **Delegacao no documento, e nao listener por elemento.** Era o `pipeline.js` inteiro em `querySelectorAll().forEach()`, e nesse desenho o primeiro `innerHTML` novo deixaria todos os cards mortos. Reescrito com um listener por tipo de evento no `document`. `dragstart`, `dragover` e `drop` borbulham, entao o arrasto entrou junto.
- **O corte fica ANTES dos chips**, e nao depois. E o que faz o contador do chip ficar certo depois do filtro.
- **O modal e o `<script>` ficam FORA do miolo.** Trocar o no de um modal aberto o fecharia na cara do usuario; e o script reinjetado registraria os listeners de novo, fazendo um clique virar N requisicoes.

**Um bug que so aparece com o parcial**: a fase escolhida vem do chip, e nao do form. Sem carregar ela junto, filtrar por unidade devolvia o usuario pra fase padrao, e ele leria isso como "o filtro apagou meus candidatos". Resolvido com input escondido no form, e nao no JS, pra continuar funcionando sem JS.

O botao Filtrar continua existindo de proposito: trocar o select ja aplica, porem sem ele a pagina fica sem jeito de filtrar quando o JS nao carrega.

- **Output**: `_pipeline_conteudo.html` novo; `pipeline_board.html` e `pipeline.js` reescritos; `views/pipeline.py` escolhe o template por `parcial`. 2 testes novos (`test_parcial_devolve_so_o_miolo`, `test_filtro_preserva_a_fase_escolhida`), 29 no arquivo. Verificado no browser: lote, acao rapida, modal e arrasto continuam funcionando **em card que veio da troca parcial**, que e o cenario que o desenho antigo quebraria. Sem migration.
- **Status**: completed em dev, nao pushado.

## 2026-07-22 — Triagem por IA le curriculo em Word (docx)

- **Acao**: fechar o descompasso entre o que o upload ACEITA e o que a triagem LE. A gente aceitava .pdf/.doc/.docx e so lia .pdf, entao curriculo em Word rodava analise cega, so com o formulario, com cara de veredito completo.

1. **Le .docx**: paragrafos E tabelas. Tabela nao e detalhe, modelo de CV do Word diagrama com tabela e o historico inteiro mora dentro de uma. Ler so `doc.paragraphs` devolveria o nome e nada mais.
2. **`.doc` (Word binario pre 2007) saiu da lista de aceitos**, mesmo criterio que barrou imagem: nenhuma lib Python leve le. Aceitar e ler cego e pior que recusar na porta.
3. **Extensao -> extrator virou mapa (`LEITORES`)**, e um teste amarra `EXTENSOES_CURRICULO == LEITORES.keys()`: aceitar formato que a IA nao le foi exatamente o bug.
4. **`rotulo_formatos_curriculo()` passou a derivar da lista**, pra a frase que o candidato le nunca prometer formato recusado.

- **Contexto que mudou no meio**: outra sessao PUSHOU a triagem (831638c7) pra origin. Ela nao esta mais "esperando push". Este commit do docx (8cedeb4e) e o unico local, e precisa subir junto: origin tem "aceita docx" + "so le pdf", entao um deploy sem ele poe o bug da analise cega em prod.
- **Output**: `triagem_ia.py` e `campos_candidatura.py` alterados; 6 testes novos (22 no arquivo). 77 testes verdes no total (triagem + formato + candidatura), `check` limpo. `python-docx==1.2.0` ja versionado. Sem migration.
- **Status**: completed em dev, 1 commit local aguardando push.

## 2026-07-22 — Fluxo, Campos e Captacao viram um hub de Configuracoes em tabs

- **Acao**: o Lucas pediu pra transformar a pagina de Fluxo numa pagina de Configuracoes, quebrada em tabs, com "Nova etapa" em modal. Escopo escolhido por ele: consolidar os TRES itens do menu de Recrutamento (Fluxo, Campos, Captacao continua) numa pagina so.

**Arquitetura: tabs client-side.** Trocar de aba mostra/esconde painel, sem recarregar. E deliberado e ecoa o pedido anterior dele no board ("no filtro n deveria trocar de pagina"): recarregar numa troca de aba incomoda igual. Depois de um POST, a view volta com `?tab=`, e o JS reabre a aba certa. Sem isso, salvar uma mensagem devolveria o RH pra aba Etapas.

**Uma view, quatro contextos namespaceados.** `fluxo.configurar` virou o hub e junta `contexto_fluxo` + `campos.contexto_campos` + `vagas.contexto_captacao`. Os contextos foram extraidos das tres views antigas pra helpers reusaveis. Namespacear (`etapas_linhas`, `campos_linhas`) foi obrigatorio: as tres usavam `linhas` e colidiriam numa tela so.

**Nova etapa e Novo campo viraram modal.** Antes eram formularios inline embaixo da lista, que apareciam gigantes mesmo sem ninguem ir criar nada. Campo virou modal tambem, por consistencia: numa tela com quatro abas, botao-que-abre-modal numa e form-inline noutra e inconsistente. Captacao mantem "Novo link" inline (form so de criar, sem edicao a reusar).

**BUG LATENTE CORRIGIDO DE QUEBRA**: o fluxo antigo CHAMAVA `sincronizarBlocos()` mas nunca a definia. Resultado: marcar o bloco "Roteiro" ou "Requisitos a validar" nao revelava o textarea, entao o RH marcava e nao tinha onde escrever. O JS novo implementa a funcao. Confirmado no browser.

**Rotas antigas preservadas**: `/people/campos/` e `/people/captacao/` redirecionam pro hub na aba certa (bookmark antigo nao quebra); os POST de salvar voltam pro hub com `?tab=`. Menu: 3 itens viraram 1 ("Configuracoes"). Flyout do sidebar colapsado idem.

- **Output**: `config_recrutamento.html` + 4 partials de aba + `config_recrutamento.js` novos; `fluxo_config.html`, `campos_config.html`, `banco_talentos_links.html` removidos (orfaos); views `fluxo/campos/vagas` refatoradas; sidebar e flyout consolidados. 4 testes novos no hub (`test_people_fluxo_config`), 3 testes de rota antiga atualizados. Verificado no browser: 4 abas trocam sem reload, seletor de unidade some fora de Etapas/Mensagens, modal abre, sync de blocos funciona. Sem migration.
- **Nota**: ha DOIS itens "Configuracoes" no menu do People agora, um em Recrutamento (este) e um em Sistema (o do Departamento Pessoal). Convivem porque a secao desambigua, mas vale unificar quando o DP tambem virar hub.
- **Status**: completed em dev, aguardando push.

## 2026-07-22 — Quadro entra no hub de Configuracoes como 5a aba

- **Acao**: o Lucas pediu pra levar o Quadro pra dentro do hub tambem. Quadro por unidade e configuracao de headcount (quantas posicoes de cada cargo a loja deve ter, a moldura que vira "faltam 2 de 8"), entao encaixa nas Configuracoes junto de Etapas, Mensagens, Campos e Captacao.

- **Mesma mecanica das outras abas**: `contexto_quadro(request, unidade)` namespaceado (`quadro_linhas`, `quadro_form`), `quadro.lista` vira redirect pro hub, POST de salvar/remover voltam com `?tab=quadro`. Aba client-side, tabela + "+ Definir quadro" em modal.
- **Seletor de unidade UNIFICADO**: era "Fluxo de", valia so pra Etapas/Mensagens. Virou "Unidade" e passou a controlar tambem o Quadro (as tres sao por unidade), num seletor so no header. Campos e Captacao seguem do tenant inteiro, e o seletor some nelas.
- **Menu**: Quadro saiu do grupo Recrutamento (era item proprio); agora e aba. O is-active de Configuracoes passou a cobrir `quadro*` tambem. Flyout do sidebar idem. `quadro_lista.html` removido (orfao).
- **Output**: `_config_tab_quadro.html` novo; `quadro.py`, `fluxo.py`, shell, JS, sidebar e flyout ajustados. Testes do hub atualizados pra 5 abas + redirect do quadro; 2 testes de `test_people_quadro` repontados pro hub. 32 verdes (fluxo_config + quadro). Verificado no browser: 5 abas, Quadro troca sem reload, seletor de unidade aparece, modal abre. Sem migration.
- **Status**: completed em dev, aguardando push.

## 2026-07-23 — "Novo link" de Captacao vira botao + modal (regra geral)

- **Acao**: o Lucas viu o "Novo link de captacao" que eu tinha deixado inline e mandou a regra: "tudo que e para cadastrar deve ser como modal + botao, nao nesse formato". Convertido: cabecalho da aba Captacao ganhou "+ Novo link", o form foi pro modal (`modal-link`), com handler `data-novo-link`.
- **Consequencia**: as 5 abas do hub agora seguem o mesmo padrao (Etapas, Campos, Quadro, Captacao com botao+modal; Mensagens edita inline por design, nao e cadastro). Regra salva na memoria como padrao do produto, nao so desta tela.
- **Output**: `_config_tab_captacao.html` e `config_recrutamento.html` e `config_recrutamento.js` ajustados. 15 testes de captacao verdes (endpoint de criar inalterado). Sem migration.
- **Status**: completed em dev, aguardando push.

## 2026-07-23 — Menu do People: duas areas espelhadas (Recrutamento e Selecao / Departamento Pessoal)

- **Acao**: o Lucas pediu um grupo "Departamento Pessoal" com as coisas de DP que ja existiam, espelhando Recrutamento. As pecas do DP estavam espalhadas: o board ("Ciclo de vida") solto no topo, "Cadastro via link" em CADASTRO, e a config do DP la embaixo em SISTEMA.
- **Escolha do Lucas (opcao C)**: DP espelha Recrutamento, e Analises (triagem de curriculo por IA, que e de recrutamento) migra pro grupo Recrutamento. Sumiu o grupo Inteligencia.

Menu novo, simetrico:
- **Recrutamento e selecao**: Candidatos, Vagas, Analises, Configuracoes (hub fluxo_config).
- **Departamento pessoal**: Ciclo de vida (o board de colaboradores por situacao, era "Board" no topo), Cadastro via link, Configuracoes (config_home).
- **Cadastro** (base compartilhada): Unidades, Cargos.

Dois "Configuracoes", um por area; a secao desambigua, e o is-active nao colide (`config_*` do DP vs `fluxo/quadro/campo/banco_talentos` do recrutamento). Confirmado no browser: cada URL destaca exatamente um item.

**BUG DE BRINDE**: o flyout do sidebar colapsado le `it.url`, mas os itens de Recrutamento estavam com `href` e linkavam pra "#". Corrigido usando `url` em todos.

- **Output**: `sidebar_subnav.html` e o flyout de `layout_app.html` reescritos. Sem view/rota nova (so reagrupou o que existia). Nenhum teste depende do menu. Sem migration.
- **Nota**: o DP (Ciclo de vida, colaboradores, config do DP) ja existia em codigo mas estava meio escondido no menu; agora tem grupo proprio. A config do DP (config_home) ainda NAO e um hub em tabs como a de recrutamento, e um hub-com-cards; unificar o padrao fica pra depois.
- **Status**: completed em dev, aguardando push.

## 2026-07-23 — Fix: opcao "Para onde" do modal de saida nao mostrava selecao

- **Bug** (reportado pelo Lucas): no modal "Tirar do processo" do board, clicar numa opcao de "Para onde" (Admitido, Banco de talentos, Inapto, Arquivado) nao selecionava nada visivelmente.
- **Causa**: o `pipeline.js` JA marcava `.is-selected` e gravava o valor no campo escondido (funcionava de verdade), mas nao havia CSS pra `.is-selected` nesses botoes. A selecao acontecia e nao aparecia, entao o usuario achava que nao tinha selecionado.
- **Fix**: estilo de selecionado (fundo primary + texto branco), escopado por `[data-saida-opcao].is-selected` pra nao pegar `.is-selected` de tabs/sidebar, com `:hover` repetido pra vencer o hover do btn-secondary. Verificado no browser: o fundo muda de branco pra primary, o valor grava, e trocar de opcao mantem so uma selecionada.
- **Output**: `pipeline_board.html` (so CSS). Sem migration, sem mudanca de markup nem de JS.
- **Status**: completed em dev, aguardando push.

## 2026-07-23 — Fix: Analises estava no grupo errado do menu (era DP, nao recrutamento)

- **Bug** (erro meu): ao reorganizar o menu em duas areas, coloquei "Analises" em "Recrutamento e selecao". Mas a pagina de Analises e do Departamento Pessoal: le `Colaborador` + `HistoricoSituacao` (ciclo de vida do colaborador), sem relacao com recrutamento. A descricao errada que dei ("triagem por IA de recrutamento") induziu a escolha errada.
- **Fix**: movida pra o grupo Departamento Pessoal, logo apos "Ciclo de vida" (junta os dois views da area). Sidebar + flyout. Verificado no browser: em /analises/ ela acende certo, no grupo certo.
- **Nota**: a pagina vazia em prod NAO era bug, e falta de dado. aurora-hq tem 0 colaboradores e 0 HistoricoSituacao (DP nunca operado em prod), enquanto recrutamento tem 16 candidatos. A tela le dados de DP, entao fica vazia ate haver colaborador no board.
- **Output**: `sidebar_subnav.html` + flyout de `layout_app.html`. Sem migration.
- **Status**: completed em dev, aguardando push.

## 2026-07-23 — Leva de correcoes (item 1): ordem do menu

- **Acao**: pedido do Lucas. Em Recrutamento, **Vagas** passa a ser o primeiro item (a vaga nasce antes; candidato so existe depois que ha vaga). Em Departamento Pessoal, **Analises** passa a ser o primeiro.
- **Output**: `sidebar_subnav.html` + flyout de `layout_app.html`. Sem migration.
- **Status**: completed em dev.

## 2026-07-23 — Leva de correcoes (item 2): marcar um item do roteiro desmarcava outro

- **Bug** (reportado pelo Lucas, com print): na ficha do candidato, marcar um item do "Roteiro da conversa" ou dos "Requisitos a validar" mexia em outro item.
- **Causa**: `components/checkbox.html` fazia `id="{{ id|default:name }}"` e o label trazia `for` apontando pra esse id. Roteiro e checklist incluem o componente num `{% for %}` com `name="itens"` e SEM id, entao TODOS os checkboxes ficavam com `id="itens"`. Com id repetido, o `for` do label manda o clique pro PRIMEIRO input da pagina: clicar em qualquer item marcava/desmarcava o primeiro.
- **Fix, em duas camadas**:
  1. **Raiz, no componente**: removido o `for` do label. O label ENVOLVE o input, entao a associacao ja e implicita; sem `for`, o clique sempre acerta o input de dentro, imune a id repetido. Corrige os dois blocos de uma vez e previne a mesma classe de bug em qualquer uso futuro.
  2. **Validade do HTML**: `_itens()` em `views/candidatos.py` passou a gerar `dom_id` unico (`{prefixo}-{etapa.pk}-{i}`), e os blocos passam `id=opcao.dom_id`. A etapa entra no id porque o mesmo roteiro aparece numa aba por etapa.
- **Verificado no browser**: ids unicos (`checklist-2-0/1/2`) e clicar o 3o item mudou SO o indice 2, sem tocar nos outros.
- **Output**: `components/checkbox.html`, `views/candidatos.py`, `blocos/_roteiro.html`, `blocos/_checklist.html`. Sem migration.
- **Status**: completed em dev.
