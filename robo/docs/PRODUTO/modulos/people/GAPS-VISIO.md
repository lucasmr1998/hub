# Gaps entre o DP da Visio e o modulo People do Hubtrix

> **Origem**: 14 screenshots do produto real da Visio, em `people_visio/`, capturados
> em 2026-07-20. Sao informacao NOVA: o pacote de handoff que originou a tarefa 205
> declarava explicitamente que "nenhum screenshot foi exportado" e que "a UI precisa
> ser inferida da descricao textual dos steps".
>
> **Como ler**: cada gap tem um status. `RESOLVIDO` ja esta em codigo. `DECISAO` precisa
> de resposta do Lucas antes de virar codigo. `DISCOVERY` precisa de print ou conversa
> com a Visio, porque nem o print nem a spec dizem o suficiente.

Data: 2026-07-20
Tarefa de origem: 205 (fundacao + cadastro)
Tarefa de fechamento: 206

---

## Resumo

| # | Gap | Impacto | Status |
|---|---|---|---|
| 1 | Multiplos links ativos por unidade | **Contradiz o que construimos** | RESOLVIDO |
| 2 | Cargo e entidade, nao texto | Modelagem | RESOLVIDO |
| 3 | Fluxo tem 7 etapas (Ativos, Ferias, Afastamentos) | Maquina de estados | RESOLVIDO |
| 4 | Comunicacao por etapa, envio sempre manual | Modelagem + produto | RESOLVIDO |
| 5 | Grupo como camada entre tenant e loja | **Arquitetural** | NAO SE APLICA |
| 6 | Template de formulario configuravel por campo | Feature grande | DECISAO |
| 7 | Template varia por pais (BR/MX/US) | Escopo de mercado | DECISAO |
| 8 | Checklist configuravel por etapa | Feature (ja prevista pra fase 2) | DECISAO |
| 9 | Pedido de Documentacao separado do cadastro | Feature | DECISAO |
| 10 | Central de Acoes | Tela nova | DISCOVERY |
| 11 | Analises (dashboard de DP) | Tela nova | DISCOVERY |
| 12 | Arquivo | Tela nova | DISCOVERY |
| 13 | Parceiros e Prestadores | Tela nova | DISCOVERY |
| 14 | Permissoes por documento sensivel | Seguranca | DISCOVERY |

---

## 1. Multiplos links ativos por unidade `RESOLVIDO`

**O que o print mostra** (`formularios/editar-forms.png`): a aba Links lista varios links
da MESMA loja, todos com status Ativo, criados em datas diferentes, cada um com seu
proprio contador de cadastros. "Subway Santo Angelo Av Getulio Vargas" aparece quatro
vezes.

**O que construimos**: constraint no banco garantindo UM link ativo por unidade
(`people_link_ativo_unico_por_unidade`), com "Novo Link" rotacionando e matando o
anterior.

**De onde veio o erro**: a spec dizia *"cada cartao de loja tem tambem as acoes Desativar
e um botao Novo Link"*. Interpretei "cartao por loja" como "link por loja". O produto real
tem uma LISTA de links por loja.

**Por que importa**: nao e detalhe de tela, e constraint de banco. Uma loja com alta
rotatividade quer varios links vivos (um por campanha, por turno, por recrutador) sem
invalidar os outros. Com a constraint, gerar o segundo link derrubaria o primeiro que
esta circulando.

**O que ficou**: constraint removida. `rotacionar_link` continua existindo (invalidar um
link vazado e caso real), mas agora e uma acao sobre UM link, nao sobre a unidade.
Cada link ganhou `nome` pra o RH distinguir na lista.

---

## 2. Cargo e entidade, nao texto `RESOLVIDO`

**O que o print mostra** (`cargos/home.png`, `criar_cargo.png`, `editar_cargo.png`):
tela de CRUD com busca, coluna de origem ("Global"), descricao longa por cargo, e o
aviso: *"Cadastre os cargos utilizados pela sua empresa. Eles serao utilizados
automaticamente no cadastro de colaboradores, na abertura de vagas e na Escala. Voce
cadastra uma unica vez e reutiliza em todo o Visio RH."*

**O que construimos**: `cargo = CharField(max_length=120)`, texto livre, com o comentario
"vira FK quando Recrutamento chegar".

**Por que importa**: cargo e o eixo de varios relatorios e ja e compartilhado com
Recrutamento e Escala no produto real. Texto livre produz "Atendente", "atendente" e
"Atendente " como tres cargos distintos, e isso corrompe qualquer agregacao.

**O que ficou**: model `Cargo` com CRUD, FK em `Colaborador`, e data migration
convertendo o texto existente (agrupando por nome normalizado, sem perder dado).

---

## 3. O fluxo tem 7 etapas `RESOLVIDO`

**O que o print mostra** (`configs/fluxo_departament_pessoal.png`):

| Etapa | Recursos configuraveis |
|---|:---:|
| Cadastro Inicial | 2 |
| Admissao | 5 |
| Periodo de Experiencia | 3 |
| **Ativos** | 1 |
| **Ferias** | 2 |
| **Afastamentos** | 2 |
| Desligamento | 5 |

**O que construimos**: 7 situacoes, mas com vocabulario diferente e sem Ferias nem
Afastamento. Nosso `efetivado` corresponde ao `Ativos` deles.

**Nota importante**: a spec listava "Afastamentos" como uma das quatro abas que
*"nenhuma fonte descreve o que fazem"* e mandava nao construir por adivinhacao. O print
resolve: e etapa do ciclo de vida, com checklist de acompanhamento proprio.

**O que ficou**: `ferias` e `afastamento` entraram na maquina de estados, com as
transicoes de ida e volta a partir de `efetivado`. Sao estados temporarios: a pessoa sai
de `efetivado` e volta pra `efetivado`. `Ativos` continua se chamando `efetivado`
internamente (o vocabulario ja esta em banco, log e catalogo de eventos; renomear agora
seria migracao de dados sem ganho).

---

## 4. Comunicacao por etapa, com envio sempre manual `RESOLVIDO`

**O que o print mostra** (`configs/configurar_etapa_fluxo1.png`): cada etapa tem uma
"Mensagem padrao" com variavel (`Ola, {{nome}}! Voce esta na etapa "Cadastro Inicial" do
seu processo com a gente.`), e dois avisos explicitos:

> "Prepare a mensagem que o RH podera enviar ao colaborador quando ele chegar nesta
> etapa — **nada e enviado automaticamente**."

> "Fica disponivel como sugestao pro RH enviar ao colaborador nesta etapa — **o envio e
> sempre manual, editavel antes de enviar, sem alterar este padrao**."

**Por que importa**: e decisao de produto, nao de implementacao, e eu teria feito o
contrario. O caminho natural seria disparar no evento `people.colaborador.experiencia_iniciada`.
A Visio decidiu que a mensagem e sugestao, nao automacao, e o RH edita antes de mandar.

**O que ficou**: model `MensagemEtapa` por tenant e etapa, com o texto padrao e o escopo
(todo o grupo ou lojas especificas). O envio em si fica pra quando a integracao de
WhatsApp entrar no modulo. **O evento continua sendo emitido** — quem quiser automatizar
monta fluxo na engine, o que nao conflita com o envio manual da tela.

---

## 5. Grupo como camada entre tenant e loja `RESOLVIDO, NAO SE APLICA`

**O que o print mostra**: o seletor "EDITANDO O FLUXO DO GRUPO: Grupo Lucas Knebel", o
campo "Grupo dono" obrigatorio ao criar cargo, e a escolha de escopo por recurso: *"Todo
o grupo (aplica a todas as lojas do grupo, inclui as que entrarem depois)"* ou *"Loja(s)
especifica(s)"*.

**Decisao do Lucas (2026-07-20)**: no Hubtrix nao existe essa camada. **Uma empresa com
varias unidades, tudo no mesmo tenant.** Grupo e conceito da Visio pra separar clientes
dentro da instancia dela; na nossa arquitetura multi tenant, quem faz esse papel e o
proprio `Tenant`.

**Consequencia**: o modelo que ja construimos (`Tenant` → `Unidade`) esta correto e nao
muda. Onde a Visio diz "grupo", nos lemos "tenant":

| Visio | Hubtrix |
|---|---|
| Grupo dono (do cargo) | `tenant` |
| Editando o fluxo do grupo | Configuracao do tenant |
| Aplica a todo o grupo | Vale pro tenant inteiro |
| Loja(s) especifica(s) | Override por `Unidade` |

Isso ja e exatamente o que `config_efetiva(unidade)` faz desde o passo 1: global do
tenant com override por unidade. Era o desenho certo por acidente feliz.

---

## 6. Template de formulario configuravel `DECISAO`

**O que o print mostra** (`formularios/criar-forms.png`, `templates.png`,
`visualizar_forms.png`): "Novo Template" com um bloco por campo do sistema, cada um com
dois toggles (**Solicitar** e **Obrigatorio**) e **rotulo customizavel**. O template tem
nome e grupo dono, e cada link de cadastro aponta pra um template.

Aviso relevante na tela de templates: *"Documentos de identificacao e dados bancarios do
colaborador nao entram aqui — ficam protegidos numa etapa propria de seguranca."*

**O que construimos**: formulario publico fixo em codigo.

**Por que NAO resolvi sozinho**: e um form builder. Model de template, model de campo,
render dinamico, validacao dinamica e a tela de edicao. Do tamanho de tres ou quatro dos
passos que ja fizemos, e com decisoes de produto no meio (o que pode ser desligado? campo
obrigatorio do sistema pode virar opcional?).

**Meio caminho possivel**: existe um construtor de formulario no Hubtrix
(`FormularioLanding.campos_json`, em `apps/marketing/landing_pages/`). Vale avaliar reuso
antes de escrever do zero.

---

## 7. Template varia por pais `DECISAO`

**O que o print mostra**: coluna "PAIS" na lista de templates, botao "Novo Template —
Brasil", e o texto de um campo: *"Documento fiscal que identifica o colaborador (CPF no
Brasil, CURP no Mexico). Nao existe nos EUA."*

**Impacto no que ja construimos**: nosso dedup e ancorado em CPF, com validacao de digito
verificador brasileira. Num tenant sem CPF (EUA), o dedup cairia inteiro no match fraco,
que por desenho nunca resolve sozinho.

**Pergunta**: o People do Hubtrix vai atender fora do Brasil? Se sim, o campo de documento
precisa ser generico (`documento_fiscal` + `tipo`) e a validacao precisa ser por pais.
Se nao, ignoramos e seguimos com CPF.

---

## 8. Checklist configuravel por etapa `DECISAO`

**O que o print mostra**: "Checklist do Processo — Crie uma lista de atividades para
acompanhar tudo o que precisa ser realizado nesta etapa", presente em varias etapas.

Ja estava previsto pra fase de Admissao (fora do escopo da 205). O print mostra que ele
nao e so da admissao: e um recurso por etapa.

**Nota**: o Hubtrix ja tem `Checklist` e `ItemChecklist` em `apps/automacao`, usados pelo
bot de vendas. Vale avaliar reuso.

---

## 9. Pedido de Documentacao separado do formulario `DECISAO`

**O que o print mostra** (`formularios/home.png`): dois cards distintos, "Formulario de
Cadastro" e "Pedido de Documentacao", cada um com seus proprios links. Sao fluxos
separados: um coleta dados, outro coleta arquivos.

**O que construimos**: so o de cadastro (dados). Faz sentido, o de documentos pertence a
fase de Admissao.

---

## 10 a 14. Telas sem print interno `DISCOVERY`

Tenho um print da navegacao mostrando que existem, e nada do que ha dentro.

| Area | O que da pra dizer |
|---|---|
| **Central de Acoes** | E o primeiro item do menu, entao provavelmente e a home do modulo. A spec mencionava "Central de Acoes" como a superficie de "o que fazer hoje", com alertas de prazo de experiencia e admissao atrasada |
| **Analises** | Tenho o print do dashboard (ver abaixo), mas nao das telas internas |
| **Arquivo** | Nao sei o que faz. Pode ser colaboradores arquivados, ou repositorio de documentos |
| **Parceiros e Prestadores** | "Cadastre e gerencie clinicas, contabilidades e outros prestadores utilizados na operacao". Liga com exame admissional/demissional e com o email pro contador |
| **Permissoes** | "Configure quem pode acessar informacoes e documentos sensiveis dos colaboradores". E granularidade por TIPO DE DADO, mais fina que a nossa por funcionalidade |

### Sobre Analises, o que o print mostra

`Captura de tela 2026-07-20 020400.png`:

- Cadastros no periodo, com variacao vs periodo anterior
- **Taxa de efetivacao por coorte** ("dos cadastrados no periodo, % efetivados hoje")
- Efetivados dessa coorte
- **Parados ha +3 dias** ("colaboradores sem avancar na admissao")
- Desligamentos no periodo
- **Lojas por prioridade**: card por loja com cadastros, efetivados e parados, e um
  status de acao ("14 parados — acao necessaria", "Admissao saudavel — sem pendencias")
- **Funil de admissao**: Cadastro → Processo Admissional → Experiencia → Efetivados
- **Evolucao mensal**: cadastros vs desligamentos

**Boa noticia**: todos esses numeros saem do `HistoricoSituacao`, que ja esta sendo
gravado desde o passo 4. A telemetria foi desenhada como fonte primaria justamente pra
isso. Construir Analises e trabalho de tela e query, nao de instrumentacao.

---

## O que NAO mudou de avaliacao

A fundacao continua correta e e o que essas telas precisariam por baixo:

- Dedup no banco, com a regra de fonte unica
- Maquina de estados como fonte da verdade, com a guarda que impede transicao sem trilha
- `HistoricoSituacao` como fonte primaria de telemetria
- Escopo por unidade
- Gate de contratacao por tenant

Nenhum print contradiz nada disso. O que os prints mostram e que o produto real e **maior**
do que a spec documentava, nao que ele e **diferente** no que a spec cobria.
