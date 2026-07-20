# Recrutamento e Selecao: plano da entrega

Corte escolhido: **opcao B**, fundacao mais pipeline. Cobre os passos 1 a 3 da
ordem sugerida pela spec de origem (`03-recrutamento-selecao.md`), e para antes
da triagem com IA e da ponte pro Departamento Pessoal, que sao as duas lacunas
que a propria spec marca como bloqueantes.

## Por que agora, e por que este corte

A spec abre a ordem de construcao com um pre requisito absoluto:

> "`people_staff` mais o cadastro do Departamento Pessoal precisam existir antes,
> com o dedup implementado como constraint. Nao comece Recrutamento sem isso,
> porque a TA de entrevista termina exatamente ali."

Esse pre requisito esta pago: e o que `apps/people` entregou. E o corte B para
exatamente onde a spec manda parar, porque **B1** (se a IA move o candidato de
etapa sozinha, contraditorio entre duas entrevistas da mesma pessoa) e **B2** (a
ponte candidato para colaborador, que nenhuma fonte especifica) mudariam
arquitetura, e nao so tela.

O que a spec diz do passo 3, e que e o argumento central do corte:

> "E a espinha dorsal sobre a qual triagem e entrevista sao so views. Construir
> isso como estrutura generica antes de construir as duas TAs evita retrabalho."

## O que ja existe e vai ser reusado

Nada disso nasce do zero, e essa e a razao de o custo ser menor agora do que
seria em qualquer outro momento.

| Ja construido no DP | Serve pra que no R&S |
|---|---|
| `LinkCadastroUnidade` mais `SubmissaoLinkCadastro` | Link de candidatura por canal, com QR, contador e desativacao manual |
| View publica com escopo de tenant por token, rate limit, honeypot e consentimento LGPD | Formulario publico de candidatura, mesma infra |
| `Cargo` como entidade, com `descricao` ja anotada como "Aparece na abertura de vaga" | FK da Vaga |
| `Unidade` mais `config_efetiva()` (global com override por unidade) | Configuracao de pipeline e quadro por loja |
| `registrar_colaborador()` com dedup de CPF em constraint | A ponte, quando ela chegar |
| Padrao de board com maquina de estados | Board de candidatos |
| `tests/test_templates_contrato.py` | Guards de acento e de render valem pro modulo novo de graca |

## Decisoes fechadas com o Lucas

### D1. Candidato em tabela propria, nao situacao de Colaborador

Candidato nao e quadro ativo. Se virasse mais uma `situacao` do `Colaborador`,
toda consulta de RH (board do DP, analises, feedback, clima) teria que lembrar de
excluir candidato, e o vocabulario racharia de novo. Ja pagamos esse erro uma vez
neste modulo, com o D2 da spec do DP.

### D2. CPF so na aprovacao, pelo link de cadastro que ja existe

O problema: candidato e unico por **WhatsApp** e o formulario de candidatura
**nao coleta CPF** de proposito, porque a Visio testou e descartou por atrito de
conversao. Colaborador e unico por **CPF**, com constraint de banco. Sao chaves
diferentes nas duas pontas, e a spec marca isso como bloqueante B2.

A saida escolhida nao inventa dedup novo:

```
Candidatura              Aprovacao                Cadastro
(sem CPF)                (RH decide)              (com CPF)

Candidato ─────────────► aprovado ──────────────► LinkCadastroUnidade
 unico por WhatsApp                                (ja construido)
                                                         │
                                                         ▼
                                                  registrar_colaborador()
                                                   dedup por CPF, constraint
                                                         │
                                                         ▼
                                                  Candidato.colaborador
```

O candidato preenche o CPF no formulario do DP que ja existe, entao o dedup
acontece no lugar onde a constraint mora. A dor numero um do cliente e "nao chega
candidato": pedir documento na porta de entrada trabalha contra isso.

Consequencia de modelagem: `Candidato.colaborador` e FK nula com `PROTECT`,
preenchida so na aprovacao. Nao e o candidato que vira colaborador, e o
colaborador que passa a referenciar de qual candidatura veio.

### D3. Retencao com prazo declarado e expurgo automatico

A spec e explicita sobre o tamanho disso:

> "O banco de talentos guarda dados pessoais indefinidamente sem vaga ativa.
> Isso *e* o produto. Base legal, consentimento no formulario, prazo de retencao
> e caminho de exclusao: nada definido."

Decisao: o formulario de candidatura declara o prazo (default 12 meses sem
movimentacao), e uma rotina em `apps/cron` anonimiza o que vencer. O prazo e
configuravel por tenant, no mesmo lugar do texto de consentimento que o DP ja
tem (`ConfiguracaoPeople.texto_consentimento_lgpd` mais
`versao_consentimento_lgpd`).

Anonimizar em vez de deletar: a linha some como pessoa (nome, WhatsApp, email,
endereco, curriculo) e sobrevive como numero, pra que a analise de funil nao
minta retroativamente sobre quantos candidatos chegaram por cada canal.

## Modelo de dados

> A secao 2 da spec de origem avisa que e a parte mais fraca do documento:
> nenhum nome de tabela ou campo foi confirmado por code scan, nao existe DDL, e
> os nomes estao marcados `# unverified`. Tratamos como inventario de conceitos.
> Os nomes abaixo sao nossos.

Tudo em `apps/people/models_recrutamento.py`, com re-export em `models.py`, no
padrao de `apps/sistema/models.py`. Todos herdam `TenantMixin`, com `db_table`
prefixado `people_` e indices comecando por `tenant`.

### `Vaga` (`people_vaga`)

Fonte da verdade da divulgacao. A spec e firme nisso (regra 4.2): requisitos,
cargo, horario e criterio vivem na vaga, e arte, link, QR e texto de rede social
sao **derivados** dela. Hoje na Visio estao separados, e a propria criadora
classifica como defeito.

Campos: `unidade` FK PROTECT, `cargo` FK PROTECT, `titulo`, `tipo_contratacao`,
`turno`, `justificativa` (nova posicao ou substituicao), `colaborador_substituido`
FK nula, `observacoes`, `limite_aprovados` (default 50, minimo 1),
`status` (rascunho, publicada, pausada, encerrada), `publicada_em`, `encerrada_em`,
`criada_por`.

### `RequisitoVaga` (`people_requisito_vaga`)

Tabela propria, e nao lista num JSON, por causa da regra 4.3 da spec: cada
requisito e **texto de anuncio** ou **criterio de filtro**, ou ambos, controlado
por toggle. E o mecanismo que permite filtrar por coisa que nao convem publicar.

> "Preserve a distincao, nao colapse os dois usos num campo so."

Campos: `vaga` FK CASCADE, `texto`, `obrigatorio` (bool), `aparece_no_anuncio`
(bool), `usar_na_triagem` (bool), `ordem`.

Os dois booleanos separados sao o ponto. Um enum de tres valores parece mais
enxuto e destroi o caso "aparece no anuncio E filtra".

### `LinkCandidatura` (`people_link_candidatura`)

Irmao do `LinkCadastroUnidade`, e nao o mesmo model: o do DP e um por unidade com
constraint parcial de unicidade, e este e **varios por vaga**, um por canal, que
e justamente a atribuicao de origem.

Campos: `vaga` FK CASCADE nula (nula significa link de banco de talentos, sem
vaga), `unidade` FK PROTECT, `token` unique global, `canal`, `apelido_interno`,
`cta`, `telefone_contato`, `texto_compartilhamento`, `candidaturas` (contador),
`ativo`, `desativado_em`, `criado_por`.

**Sem expiracao automatica.** Decisao consciente da origem, com motivo:

> "A gente usa muito Facebook, entao as vezes as pessoas entram la no grupo
> antigo, publicacao ta la, elas se candidatam."

Publicacao antiga continua rendendo candidato meses depois. Desativacao e manual.
Isso diverge do `LinkCadastroUnidade` do DP, que tem `expira_em`, e a divergencia
e proposital.

### `EtapaPipeline` (`people_etapa_pipeline`)

Aqui esta a diferenca arquitetural em relacao ao DP, e ela merece atencao.

No DP, `estados.py` e uma maquina **fixa em codigo**, e essa e a fonte da verdade.
No R&S as etapas sao **configuraveis por loja**: ordenaveis, ligaveis e
desligaveis. O default entregue pronto e `Triagem, Historico, Teste
Comportamental, Selecao, Teste pratico, Avaliacao Gestor, Admissao`, e a spec cita
uma rede nos EUA rodando so `triagem, entrevista com RH, admissao`.

**A divisao: saida terminal em codigo, etapa intermediaria em dado.**

- Etapas intermediarias sao linhas nesta tabela. So ordenam e nomeiam.
- Saidas terminais (`admitido`, `banco_talentos`, `inapto`, `arquivado`) ficam em
  `apps/people/estados_recrutamento.py`, porque **tem comportamento**: `admitido`
  aciona a ponte pro DP, `banco_talentos` entra na retencao do D3, e `inapto` e
  final. Comportamento nao vai pra tabela de configuracao, senao o cliente
  consegue configurar um estado que o codigo nao sabe tratar.

Campos: `unidade` FK nula (nula e o default do tenant, no padrao de
`config_efetiva`), `nome`, `ordem`, `ativa`, `sla_dias` (prazo maximo na fase).

Etapa desligada **nao e apagada**. A spec e explicita: *"esse botao ele fica, ele
nao some, ele fica invisivel"*. Candidato parado numa etapa que foi desligada
continua existindo e precisa aparecer em algum lugar.

### `Candidato` (`people_candidato`)

Campos de identidade: `nome_completo`, `whatsapp` (E.164 sem `+`),
`data_nascimento`, `email`, endereco, `experiencia_previa`,
`disponibilidade_horario`, `curriculo` (upload).

Campos de processo: `vaga` FK PROTECT nula, `unidade` FK PROTECT,
`link_origem` FK SET_NULL, `etapa` FK nula pra `EtapaPipeline`, `saida` (nula
enquanto no pipeline), `motivo_saida`, `colaborador` FK nula PROTECT (D2).

Campos de LGPD: `consentimento_*` no padrao do DP, mais `anonimizado_em`.

Constraint que implementa a regra 4.5 da spec:

```python
UniqueConstraint(fields=['tenant', 'whatsapp'],
                 name='people_candidato_whatsapp_unico_por_tenant')
```

O motivo declarado nao e seguranca, e integridade de metrica:

> "Fica parecendo pra gente um numero falso, parece que tem 300 pessoas que se
> candidataram pra aquela vaga, mas 20 e a mesma pessoa se candidatando
> incansavelmente."

Furo conhecido e admitido pela origem: a mesma pessoa com numeros diferentes
passa. Documentar no docstring, nao fingir que nao existe.

Resposta de conflito no formulario publico e **generica**, mesma postura do DP:
dizer que o numero ja existe transformaria a pagina num oraculo de "fulano se
candidatou aqui?", aberto na internet.

### `HistoricoCandidato` (`people_historico_candidato`)

Espelho do `HistoricoSituacao` do DP, pelo mesmo motivo: e a fonte primaria da
telemetria de funil. Tempo medio por etapa e taxa de conversao por canal viram
group by, sem ferramenta externa.

Campos: `candidato` FK CASCADE, `de_etapa`, `para_etapa`, `para_saida`, `motivo`,
`usuario`, `origem`, `criado_em` indexado.

**Motivo obrigatorio na saida.** A spec marca isso como coluna real observada em
demo que ficou fora da especificacao: *"O campo `motivo` nao existe em nenhum dos
contratos de conclusao dos manifests. E uma coluna real. Modele-a."*

### `QuadroUnidade` (`people_quadro_unidade`)

`unidade` FK, `cargo` FK, `quadro_definido`, e os derivados calculados
(`admitidos_ativos`, `em_processo`). E o que limita a captacao junto com o
`limite_aprovados` da vaga.

## Ordem de implementacao

Cada passo commitavel, com `manage.py check` limpo e teste passando.

**Passo 0.** Tarefa no Workspace (CLAUDE.md 1.7). Nada codifica antes.

**Passo 1.** `estados_recrutamento.py` (saidas terminais, transicoes,
`EFEITOS`), mais `EtapaPipeline` e o seed do pipeline default. Python puro no
modulo de estados, testavel sem banco, no padrao de `estados.py`.

**Passo 2.** `Vaga` mais `RequisitoVaga`, com CRUD. A spec chama `vaga-criar` de
a TA mais bem documentada do pacote, unica com todas as telas capturadas.

**Passo 3.** `LinkCandidatura` mais QR, e a atribuicao por canal. Sai **junto**
com a vaga, nao depois. A spec e enfatica:

> "Se sairem depois, os dados de origem nascem quebrados e o `pipeline-analise`
> nunca tera o que mostrar."

**Passo 4.** `Candidato` mais o formulario publico de candidatura, com dedup por
WhatsApp em constraint e o consentimento do D3. Reusa `tenant_scope.py`, os rate
limits e o honeypot do DP.

**Passo 5.** Board do pipeline, com etapas configuraveis, saidas terminais,
motivo obrigatorio e contadores por fase num unico `values().annotate()`.

**Passo 6.** `QuadroUnidade` e a regra de parada por vaga (`limite_aprovados`).

**Passo 7.** Rotina de expurgo do D3 em `apps/cron`, com teste de que anonimiza
sem apagar a linha.

**Fora deste corte**, e cada um com sua razao: triagem com IA (B1 nao resolvido,
e exige decidir provedor), entrevista com roteiro, ponte pro DP (B2, cujo desenho
ja esta decidido no D2 mas cuja implementacao depende do passo de entrevista),
banco de talentos como view de busca (so tem valor com volume acumulado),
analise de pipeline (a propria equipe da Visio considera remover), Indeed,
Meta Ads, teste comportamental e requisicao de vaga com aprovacao.

## Riscos

**1. Pipeline configuravel abre porta pra estado invalido.** Se a etapa e dado, o
cliente pode desligar todas, ou reordenar de um jeito que deixe candidato orfao.
Mitigacao: saidas terminais em codigo, minimo de uma etapa ativa validado no
servico, e candidato em etapa desativada continua visivel num agrupamento
proprio, em vez de sumir do board.

**2. `whatsapp` unico por tenant tem o mesmo problema de NULL do CPF.** Se algum
caminho gravar string vazia, a segunda vazia estoura com `IntegrityError`
incompreensivel. Mesma solucao do DP: normalizar pra `None` no `save()` e
`CheckConstraint` de formato, que e o que impede a classe inteira de bug.

**3. Upload de curriculo e superficie nova.** O DP nunca recebeu arquivo. Entra
validacao de tipo e tamanho, storage, e o expurgo do D3 precisa apagar o arquivo
tambem, nao so anonimizar a linha.

**4. Vaga com `justificativa=substituicao` cria obrigacao no DP.** A spec
descreve a ponte DP para R&S como confirmada: escolher quem sera substituido
**registra alerta de pendencia no quadro do DP**, que permanece ate a pessoa ser
desligada. Motivo real: *"acontecia muito do gerente contratar e acabarem
esquecendo a pessoa que ia ser substituida, e aquilo ficava um custo a mais pra
loja."* Nao e leitura de dado, e criacao de obrigacao do outro lado.

**5. O repo e publico e ja tem PII real.** Curriculo, WhatsApp e endereco de
candidato nao podem entrar em fixture, seed de demo ou teste com dado
verdadeiro. O seed usa dado gerado, como o `seed_people_demo`.
