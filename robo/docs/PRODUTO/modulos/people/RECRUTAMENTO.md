# Recrutamento e Selecao

A etapa que vem ANTES do Departamento Pessoal: hoje o modulo cuida de quem ja foi
contratado, e recrutamento cobre como a pessoa chega ate a contratacao. Portado
da spec da Visio (`03-recrutamento-selecao.md`), onde roda live com clientes.

**Estado**: corte B construido e em prod (tarefa 211). Vaga, divulgacao com QR,
candidatura publica, board do pipeline, quadro por unidade e expurgo LGPD. Fora
do corte, cada um com sua razao no fim deste doc: triagem por IA, entrevista com
roteiro, ponte automatica pro DP, banco de talentos como busca, Indeed, Meta.

- **Rotas internas**: `/people/vagas/`, `/people/candidatos/`, `/people/quadro/`
- **Rota publica**: `/people/candidatura/<token>/` (sem login)
- **Permissao**: `people.gerir_vagas`
- **Plano de origem** (as decisoes, escrito antes de construir): `RECRUTAMENTO-PLANO.md`

---

## A decisao que estrutura tudo: etapa e dado, saida e codigo

No Departamento Pessoal a maquina de estados e FIXA em codigo (`estados.py`),
porque fase de vinculo trabalhista nao e preferencia de cliente. Aqui e o
contrario: **as etapas do pipeline sao configuraveis por unidade**, porque etapa
de processo seletivo E preferencia de cliente. A spec cita uma rede nos EUA
rodando so `triagem, entrevista, admissao` contra as sete etapas do default
brasileiro.

Entao o subdominio se divide assim:

```
ETAPA INTERMEDIARIA  ->  DADO      (model EtapaPipeline, por unidade)
SAIDA TERMINAL       ->  CODIGO    (estados_recrutamento.py)
```

O criterio nao e estetico, e **comportamento**. Saida faz coisa: `admitido`
aciona a ponte pro DP, `banco_talentos` entra na retencao com expurgo, `inapto`
e decisao registrada. Comportamento em tabela de configuracao deixaria o cliente
criar um estado que o codigo nao sabe tratar, e a descoberta acontece em prod.
Etapa so ordena e nomeia, entao pode ser dado.

As quatro saidas (`admitido`, `banco_talentos`, `inapto`, `arquivado`) vivem em
`apps/people/estados_recrutamento.py`, junto do status da vaga (que tambem e fixo:
ciclo de vida de vaga nao e preferencia).

---

## O fluxo, ponta a ponta

```
Vaga (rascunho)
  │  requisitos + condicoes + descricao
  ▼
Vaga publicada ── gera ──► LinkCandidatura (por canal, com QR)
                              │  URL publica
                              ▼
                         Candidato preenche no celular (sem login)
                              │  dedup por WhatsApp
                              ▼
                         cai na 1a etapa do pipeline
                              │  RH arrasta pelas etapas
                              ▼
                         Saida terminal (com motivo obrigatorio)
                              │
             admitido ───────┴─────── banco / inapto / arquivado
                │                            │
         (ponte pro DP,               (reabrivel; banco entra
          passo futuro)               na retencao LGPD)
```

### A vaga e a fonte da verdade da divulgacao

Requisito, cargo, condicoes e criterio vivem NA VAGA. Arte, link, QR e texto de
rede social sao **derivados** dela. Este e o defeito de UX mais citado pela
criadora do produto de origem: la, criar a vaga e criar o link sao telas
separadas, o que obriga a redigitar. Aqui os requisitos e a divulgacao moram
dentro da pagina da vaga, e `LinkCandidatura.texto_padrao()` monta o texto de
divulgacao a partir do que ja foi cadastrado. So os requisitos marcados pra
aparecer no anuncio entram; criterio de triagem calado nao vaza pro texto
publicado.

---

## Os models (`models_recrutamento.py`)

| Model | Papel | Detalhe que importa |
|---|---|---|
| `Vaga` | Posicao aberta numa unidade | Fonte da verdade. Status fixo (rascunho/publicada/pausada/encerrada). Encerrada nao reabre |
| `RequisitoVaga` | Um requisito, com DOIS usos | `aparece_no_anuncio` e `usar_na_triagem` sao booleanos separados, nao um enum: permite filtrar por coisa que nao convem publicar |
| `LinkCandidatura` | Link publico, um por CANAL | E a atribuicao de origem. Nao expira e nao tem teto, ao contrario do link do DP. Ver abaixo |
| `Candidato` | Quem se candidatou | Tabela propria, nao situacao de Colaborador. Dedup por WhatsApp. Ver abaixo |
| `EtapaPipeline` | Etapa configuravel por unidade | Override substitui, nao soma. Desativar nao apaga |
| `HistoricoCandidato` | Cada movimento no pipeline | Fonte do funil. Guarda etapa como TEXTO, nao FK, pra sobreviver a etapa renomeada |
| `QuadroUnidade` | Quantas posicoes de cada cargo a loja quer | Derivados (ativos, em processo) sao consulta, nunca coluna |

### LinkCandidatura: tres diferencas deliberadas em relacao ao link do DP

| | Link do DP | Link de candidatura | Por que |
|---|---|---|---|
| Quantidade | Varios por unidade | Varios por vaga, **um por canal** | Atribuicao de origem: sem isso o franqueado gasta em canal que nao converte sem saber |
| Expiracao | Tem `expira_em` | **Nao expira** | Publicacao antiga em grupo de Facebook rende candidato meses depois. Desativacao e manual |
| Teto | Tem `max_submissoes` | **Sem teto** | A regra de parada mora na vaga e e sobre APROVADOS: ao atingir, a triagem para, a captacao continua |

Desativar nao apaga: apagar levaria junto as candidaturas que vieram pelo link e
destruiria a atribuicao. Efeito colateral conhecido: QR ja impresso para de
funcionar. QR e SVG, nao PNG, porque o uso real e cartaz na parede.

### Candidato: dedup por WhatsApp, nao por CPF

O formulario NAO coleta CPF de proposito: a origem testou e descartou por atrito
de conversao, e a dor numero um do cliente e "nao chega candidato". O candidato
e unico por **WhatsApp** (mesmo tratamento de NULL do CPF: ausente e NULL,
presente e unico por tenant, mais CheckConstraint de formato). O CPF entra
depois, na aprovacao, pelo formulario do DP, onde a constraint de CPF ja mora.

A ponte pro DP anda por `Candidato.colaborador`, FK nula preenchida so na
admissao: nao e o candidato que "vira" colaborador, e o colaborador que passa a
referenciar de qual candidatura veio. Os dois coexistem porque respondem
perguntas diferentes. **A implementacao dessa ponte e passo futuro.**

Motivo do dedup por numero, declarado na origem: nao e seguranca, e integridade
de metrica ("parece que 300 se candidataram, mas 20 e a mesma pessoa
incansavel"). Furo conhecido e admitido: a mesma pessoa com numeros diferentes
passa.

---

## Retencao LGPD do banco de talentos

O banco de talentos guarda dado pessoal de quem nao foi contratado. Por isso:

- O prazo (`ConfiguracaoPeople.dias_retencao_candidato`, default 365) e gravado
  em cada candidato NO ATO (`retencao_ate`), nao calculado no expurgo: se o prazo
  mudar, quem se candidatou sob a regra antiga tem direito a ela.
- O formulario mostra o prazo pro candidato no texto de consentimento.
- O comando `expurgar_candidatos` (roda pelo `dispatcher_cron`) ANONIMIZA quem
  venceu, nao deleta: a linha e a origem sobrevivem pra analise de canal nao
  mentir retroativamente. O que some e a pessoa e o arquivo do curriculo.

**Pendencia de ativacao**: o comando so roda com um `CronJob` cadastrado
apontando pra ele. Sem isso, o dado nunca e expurgado. Ver o execution-log.

---

## Campos da candidatura sao configuraveis por vaga

Reusa o padrao do DP (catalogo em `campos_candidatura.py`, config em JSON), mas
por VAGA e nao global: uma vaga de estagio pede um conjunto, uma de motoboy pede
outro. Nome e WhatsApp sao travados (dedup e canal de retorno). A validacao le
so os campos solicitados: campo desligado nao grava nem se vier num POST forjado.

---

## Regra de parada

`Vaga.limite_aprovados` (default 50). Ao atingir, a triagem PARA e a captacao
continua. Como nao ha triagem por IA, aqui e AVISO e nao bloqueio: admitir alem
do teto continua possivel, porque a decisao e do RH; o sistema so garante que
passar do teto seja consciente e nao descuido.

---

## Rotas

| Rota | O que |
|---|---|
| `/people/vagas/` | Lista com filtro por status e unidade |
| `/people/vagas/<pk>/` | Vaga: requisitos, campos, divulgacao, publicacao (tudo numa tela) |
| `/people/candidatos/` | Board do pipeline, arrastavel |
| `/people/quadro/` | Faltam X de Y por cargo por unidade |
| `/people/candidatura/<token>/` | Publica, sem login, mobile first |

Todas as internas exigem `people.gerir_vagas` (menos as de leitura, que exigem
`people.ver`). A publica reusa a infra de seguranca do DP: tenant pelo token,
404 generico, CSRF, rate limit por IP e por token, honeypot.

---

## Provisionamento

Ativar `modulo_people` num tenant dispara o signal
`provisionar_pipeline_de_recrutamento`, que semeia as sete etapas padrao. A
migration `0008` fez o back-fill dos tenants que ja tinham o modulo. **Nao ligar
o modulo por SQL cru**: pula o signal e o board nasce sem coluna.

---

## Fora do corte, e por que

| Feature | Motivo de estar fora |
|---|---|
| Triagem por IA | Lacuna bloqueante da spec (a IA move candidato sozinha ou nao? contraditorio na origem) e exige decidir provedor |
| Entrevista com roteiro | Depende da triagem; o roteiro e geracao por IA |
| Ponte automatica pro DP | Lacuna bloqueante (mapeamento candidato->colaborador). O DESENHO esta decidido (CPF na aprovacao pelo link do DP); falta a implementacao |
| Banco de talentos como busca | So tem valor com volume acumulado |
| Analise de pipeline | A propria equipe da Visio considera remover |
| Indeed, Meta Ads | Integracao de terceiro, roadmap comercial |

---

## Testes

```bash
python -m pytest tests/test_people_recrutamento_*.py tests/test_people_candidatura_*.py tests/test_people_pipeline_*.py tests/test_people_quadro.py tests/test_people_expurgo.py tests/test_people_provisionamento.py -q
```

| Arquivo | O que protege |
|---|---|
| `test_people_recrutamento_estados.py` | A maquina de saidas e a constraint da etapa (nulls_distinct), pedindo pro banco recusar |
| `test_people_recrutamento_vaga*.py` | Vaga, requisitos com os dois usos, as constraints |
| `test_people_recrutamento_link.py` | As tres diferencas do link, e o texto que sai da vaga sem vazar triagem |
| `test_people_candidatura_publica.py` | Dedup, isolamento com thread local sujo, anti abuso |
| `test_people_candidatura_campos.py` | Campos configuraveis, travados, e o desligado que nao grava |
| `test_people_pipeline_board.py` | Mover livre, sair com motivo, etapa desativada nao some candidato |
| `test_people_quadro.py` | Ocupacao lida de dois lugares sem contar duas vezes; regra de parada avisa |
| `test_people_expurgo.py` | Vencido anonimiza, dentro do prazo NAO e tocado, curriculo apagado |
| `test_people_provisionamento.py` | Signal semeia o pipeline na ativacao, sem duplicar |

---

## Gaps achados nos prints do produto real (21/07/2026)

O Lucas apontou a pasta `toolboxes/people/tools/recrutamento-selecao/`, que tem
11 screenshots do produto rodando. A spec que guiou a construcao
(`03-recrutamento-selecao.md`) avisava que faltava screenshot em varias partes,
entao estes prints sao informacao nova. O que eles revelaram, alem do que ja
estava decidido como fora do corte:

### Alto impacto

**1. O board deles nao e colunas lado a lado.** E uma barra de chips por etapa
com contador (Triagem 0, Historico 0, Comportam. 2, ...) mais a lista de UMA
etapa por vez, com toggle entre lista e kanban. Isso nao e detalhe estetico: um
print da propria operacao mostra 76 candidatos numa unica etapa, e coluna lado a
lado nao aguenta esse volume. Nosso board renderiza todas as colunas de uma vez.

**2. As saidas aparecem no board deles, o nosso as esconde.** Eles mostram
`Admitidos 5 · Banco 2 · Inaptos 1` como chips clicaveis, separados por um
divisor "SAIDAS". O nosso board filtra `saida=''`, entao quem sai do pipeline
DESAPARECE da interface. O candidato continua no banco de dados e nao ha tela
que chegue nele. Considerando que o banco de talentos e descrito pela spec como
sendo o produto ("guarda quem nao foi contratado num banco reaproveitavel"),
isto e mais perto de um buraco funcional do que de um gap de UX.

**3. Existe editor visual do fluxo, e nos nao temos tela nenhuma.** A tela
"Configurar Fluxo" tem: arrastar pra reordenar, cor por etapa, engrenagem pra
configurar cada etapa, toggle de ativar/desativar, "+ Nova etapa", e as saidas
com "Arquivados" opcional (alternativa neutra a "Inaptos"). Salva
automaticamente e tem "Resetar padrao". Nosso `EtapaPipeline` suporta ordem,
ativa e sla_dias, mas sem tela o cliente fica preso nas sete etapas que o seed
criou, o que contraria o proprio desenho de "etapa e configuracao".

### Medio e baixo

- **Selecao em lote** no board. Com 76 candidatos numa etapa, mover um a um e sofrido.
- **QR inline** na lista de links (mostram a imagem, nao so o botao de baixar) e um botao "Visualizar" que abre a pagina publica.
- **Excluir link**, alem de desativar. Nos so desativamos, de proposito, pra preservar a atribuicao de canal.
- Vaga criada por **wizard de 4 passos**; nosso formulario com abas cobre o mesmo.

### Onde a nossa implementacao ficou melhor

- **Toggle por requisito, nao por grupo.** O print mostra um unico toggle pro bloco "Requisitos Obrigatorios" inteiro. O nosso permite publicar um requisito e filtrar calado outro, que e o mecanismo que a regra 4.3 da spec descreve.
- **Requisitos estruturados**, nao textarea de texto livre. Sem estrutura, a triagem futura nao teria o que ler.
- **"Como chegou" e medido** pelo link de origem, nao perguntado ao candidato.
- **Expurgo LGPD com prazo declarado e anonimizacao**, sem equivalente visivel no material deles.

Estes gaps NAO entraram no corte B. Viraram tarefa propria pra nao se perderem.
