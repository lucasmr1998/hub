# Gaps entre o Recrutamento da Visio e o nosso

Irmao do `GAPS-VISIO.md`, que faz o mesmo pro Departamento Pessoal.

**Fonte**: prints do produto RODANDO que o Lucas mandou em 21/07 (board completo,
uma tela por aba da ficha, tela de links, tela de criar vaga). Nao a spec de
handoff.

**A regra que este documento existe pra lembrar**: a spec `03-recrutamento-selecao.md`
avisa em varios pontos que os nomes e fluxos ali sao PROPOSTA, e nao leitura do
schema. Tres vezes em 21/07 seguir a spec sem confrontar com print custou
trabalho, incluindo semear uma etapa ("Historico") que nao existe no produto
real. **Print do produto rodando ganha da spec escrita, sempre.**

**A segunda regra**: copiar MECANICA, nunca CONTEUDO. O checklist deles
(disponibilidade, locomocao, idade) e de franquia de alimentacao; pra provedor
seria CNH, NR-35, curso tecnico. A mecanica (checklist na entrevista) e certa, a
lista nao pode vir chumbada.

---

## Contexto que muda a priorizacao

Em 21/07, **so a aurora-hq tem o modulo People ligado em prod**. Nuvyon, TR
Carrion e Gigamax estao com ele desligado. Ninguem paga por isso ainda, e a
unica vaga em producao e a nossa.

Ou seja: "focar em provedor" e hipotese sobre o proximo cliente, nao exigencia
de um cliente atual. A recomendacao aberta e conversar com o RH da Nuvyon e da
TR Carrion antes de construir mais coisa especifica de vertical.

---

## Resumo

| # | Gap | Custo | Status |
|---|---|---|---|
| 1 | Curriculo: formatos e erro de upload do Chrome | medio | RESOLVIDO |
| 33 | Triagem le curriculo em Word (docx); .doc recusado | 2h | RESOLVIDO |
| 13 | Campos do Perfil: era configuracao, nao gap | sem codigo | NAO E GAP |
| 2 | Mensagem de WhatsApp por etapa e por saida | meio dia | RESOLVIDO |
| 3 | Analise por IA sob demanda | 1 dia | RESOLVIDO |
| 4 | Ponte pro Departamento Pessoal | 1,5 dia | RESOLVIDO |
| 5 | Ficha organizada por etapa, com blocos | 2 dias | RESOLVIDO |
| 6 | Perfil Avaliador | meio dia | RESOLVIDO |
| 7 | Motivo de reprovacao em lista fechada | 3h | RESOLVIDO |
| 8 | Atraso por etapa (`sla_dias` era campo morto) | meio dia | RESOLVIDO |
| 9 | Captacao continua (link sem vaga) | meio dia | RESOLVIDO |
| 10 | Taxa de conversao por link | meio dia | RESOLVIDO |
| 11 | Etapas alinhadas ao produto rodando | 2h | RESOLVIDO |
| 12 | Board: filtro por canal e periodo, dias no card | 2h | RESOLVIDO |
| 26 | Lista como grade de cards, e nao tabela | 2h | RESOLVIDO |
| 27 | Card com telefone, dias e acoes rapidas | 2h | RESOLVIDO |
| 28 | Saidas como coluna no kanban | 1h | RESOLVIDO |
| 29 | Chips inline, numa linha so | 1h | RESOLVIDO |
| 30 | Botao "Reativar" no card de saida | 1h | RESOLVIDO |
| 31 | Board numa superficie branca so | 1h | RESOLVIDO |
| 32 | Filtro e chip sem recarregar a pagina | 3h | RESOLVIDO |
| **15** | **"Selecionar varios" no kanban** | **3h** | **ABERTO** |
| **16** | **Requisicao de vaga com aprovacao** | **2 dias** | **ABERTO** |
| **17** | **Perfil comportamental (teste + perfil por IA)** | **2 dias** | **ABERTO** |
| **18** | **Roteiro de entrevista gerado por IA** | **1 dia** | **ABERTO** |
| **19** | **Descricao da vaga por IA** | **1 dia** | **ABERTO** |
| **20** | **Banco de artes por IA (post, poster, story)** | **2 dias** | **ABERTO** |
| **21** | **Chamada para redes sociais por IA** | **meio dia** | **ABERTO** |
| **22** | **Notificacao automatica ao candidato** | **1 dia** | **DECISAO** |
| **23** | **Calendario de entrevista com auto agendamento** | **2 dias** | **ABERTO** |
| **24** | **Freelancers (aba propria nas requisicoes)** | **?** | **DISCOVERY** |
| **25** | **Analise de pipeline** | **?** | **DESCARTADO** |

---

## Auditoria de classificacao (23/07)

Depois que o item 13 se revelou configuracao disfarcada de gap, o Lucas pediu a
mesma regua no resto da lista. A regua: **gap e o que o produto NAO CONSEGUE
fazer**. O resto e configuracao, decisao, ou enfeite.

| Categoria | Itens | Custo | O que significa |
|---|---|---|---|
| **Capacidade que falta E bloqueia operar** | 16, 23 | ~4 a 5 dias | Sem isso, alguem nao consegue fazer o trabalho |
| **Capacidade que falta, NAO bloqueia** | 17, 20 | ~4 dias | Novo, porem ninguem para se nao existir |
| **Acelerador de IA (o manual ja funciona)** | 18, 19, 21 | ~2,5 dias | So deixa mais rapido o que ja da pra fazer |
| **Paridade/UX (a capacidade existe em outra tela)** | 15 | 3h | Ninguem fica sem conseguir |
| **Decisao, nao build** | 22 | — | Ver secao propria |
| **Discovery** | 24 | — | Nao construir por adivinhacao |
| **Descartado** | 25 | — | A propria origem quer remover |

**A conclusao que muda a leitura do modulo:** o que realmente falta pra o
recrutamento OPERAR sao **dois itens, 16 e 23, cerca de 4 a 5 dias**. Os outros
~7 dias sao acelerador, vitrine ou polimento. A lista aparentava 11 a 12 dias de
"falta"; a maior parte disso nao impede ninguem de trabalhar.

**Duas ressalvas que sairam da auditoria:**

- **17 (perfil comportamental) tem evidencia CONTRA**, registrada no proprio
  material da origem: a cliente esperava resposta binaria (recomenda ou nao) e a
  IA devolve nuance. Construir sabendo que o usuario original nao gostou e
  comecar com a objecao ja conhecida.
- **20 (banco de artes por IA)** e marketing, nao recrutamento, e concorre com
  ferramenta de design que o cliente provavelmente ja usa. Custo alto (2 dias)
  pra um problema que nao e nosso.

---

## Os que estao abertos

### 13. Campos do Perfil, RECLASSIFICADO em 23/07 (nao era gap)

Estava listado como gap de 4h. **Nao era.** O Lucas apontou o erro: gap de
produto e quando o produto NAO CONSEGUE fazer. Aqui ele consegue.

A aba Perfil da origem mostra cargo pretendido, categoria de experiencia, "ja
trabalhou em alguma empresa deste grupo?" e trajetoria profissional. Todos esses
sao criaveis HOJE, pela tela de Campos (aba do hub de Configuracoes), sem
codigo e sem deploy: foi exatamente pra isso que os campos custom existem.

**A licao de classificacao**, que vale pro resto desta lista: o documento foi
escrito comparando print a print, e nessa leitura "campo que eles mostram e a
gente nao" virou gap. Confundiu **capacidade que falta** com **configuracao que
ninguem fez**. Item que so precisa de alguem preencher uma tela nao e backlog de
engenharia, e infla a conta de quanto falta pra fechar o modulo.

**O que sobrou de real, e e pequeno:**

- **Endereco com rua e numero em coluna propria.** Unico que exigiria codigo +
  migration. Fica ABERTO E OPCIONAL, sem estimativa, porque tem contra: e mais
  PII no formulario publico e mais peso pro expurgo LGPD. So vale com uso
  concreto declarado (ex: calcular deslocamento), e nao "porque eles tem".
- **Campos nascem vazios pro tenant novo.** A origem entrega os campos prontos;
  os nossos comecam do zero. Isso NAO e falta de capacidade, e falta de
  DEFAULT. Se virar problema, a solucao e semear campos sugeridos no
  provisionamento, que e decisao de onboarding, nao feature.

**Nao copiar "como conheceu a vaga"**: eles PERGUNTAM ao candidato; nos MEDIMOS
pelo link de origem, que e mais confiavel que memoria de quem preencheu.

### 15. "Selecionar varios" no kanban

Temos selecao em lote na LISTA, e nao no kanban. Eles tem nos dois.

**Classificacao: paridade/UX, e nao capacidade que falta.** Mover ou dar saida
em lote JA E POSSIVEL hoje: o RH troca pra vista de lista e faz. O que falta e a
mesma acao sem trocar de vista. Ninguem fica impedido de trabalhar, entao nao
disputa prioridade com 16 e 23.

### 16. Requisicao de vaga com aprovacao

**O maior gap de governanca.** O gestor da loja clica "Solicitar Vaga", a vaga
nasce "Aguardando aprovacao", e o RH aprova ou rejeita com motivo. Justificativa
obrigatoria (aumento de quadro ou substituicao), e a substituicao aponta quem
saiu, ligando com o Quadro.

Hoje qualquer um com `people.gerir_vagas` abre vaga direto, sem registro de quem
pediu nem por que. Numa rede de franquia (e num grupo de provedores) e
justamente o controle que o dono quer.

Nao e model novo: e a mesma `Vaga` com dois status a mais e tres campos.

### 17 a 21. A familia de IA

O que a origem faz com IA, alem da triagem que ja temos:

- **Perfil comportamental**: envia perguntas situacionais e devolve um mapa de
  perfil. Ha uma objecao registrada na origem: a cliente esperava binario
  (recomenda ou nao) e a IA devolve nuance.
- **Roteiro de entrevista por candidato**: perguntas especificas pro CV daquela
  pessoa. Hoje o nosso roteiro e lista fixa configuravel.
- **Descricao da vaga**, **artes de divulgacao** (post, poster, story, com QR
  embutido) e **chamada pra redes sociais**.

O provedor de IA nao e bloqueio: ja chamamos OpenAI e Groq por tenant. O que
sobra e custo por chamada, e a `AnaliseCandidato` ja grava tokens pra essa
pergunta se responder com dado real.

**Classificacao (auditoria 23/07), porque os cinco nao sao a mesma coisa:**

- **17 perfil comportamental** e **20 artes**: capacidade que realmente falta,
  porem nenhuma das duas bloqueia operar. Ver as ressalvas na secao de
  auditoria: a 17 tem objecao registrada da propria cliente da origem, e a 20 e
  marketing competindo com ferramenta de design.
- **18 roteiro, 19 descricao da vaga, 21 chamada de redes**: sao
  **ACELERADORES**, nao capacidades ausentes. O roteiro ja existe (lista
  configuravel por etapa), a descricao da vaga ja se escreve, e o texto de redes
  tambem. A IA so deixa mais rapido. Adiar nao impede ninguem de contratar.

**Aceitar imagem de curriculo esta amarrado aqui**: foi decidido em 21/07
recusar imagem porque a IA le PDF e nao le foto. Reabrir exige OCR no mesmo
pacote.

### 22. Notificacao automatica ao candidato

Hoje toda mensagem e manual (abre o WhatsApp). A origem tambem e manual, e diz
o motivo em dois lugares: "nada e enviado automaticamente".

**E DECISAO, e nao gap**: quem quiser automatizar monta um fluxo na engine de
automacao, que ja escuta os eventos do modulo. Construir automacao dentro do
People seria um segundo motor pior que o que ja existe.

### 23. Calendario de entrevista com auto agendamento

O candidato escolhe o horario sozinho. A origem estima economizar de 5 a 10
mensagens de WhatsApp e de 1 a 3 dias por contratacao. Temos o bloco de
agendamento (data e local), porem quem preenche e o RH.

### 24. Freelancers

A tela de Requisicoes deles tem duas abas: Vagas e Freelancers. Nao sabemos o
que muda entre as duas. **Nao construir por adivinhacao**: precisa de discovery.

### 25. Analise de pipeline

A propria equipe da origem considera remover. Deixado por ultimo de proposito.

---

## Onde a nossa implementacao ficou melhor

- **Toggle por requisito, e nao por grupo.** O print deles tem um unico toggle
  pro bloco "Requisitos Obrigatorios" inteiro; o nosso permite publicar um
  requisito e filtrar calado outro, que e o mecanismo que a regra 4.3 da spec
  descreve.
- **"Como chegou" e MEDIDO** pelo link de origem, e nao perguntado.
- **Expurgo LGPD com prazo declarado e anonimizacao**, sem equivalente visivel
  no material deles.
- **Taxa de conversao por link**, que eles nao mostram: eles contam candidatura,
  nao visita.
- **Etapa e configuravel de verdade**, inclusive quais blocos cada uma mostra.
- **Avaliador com usuario**, e nao link publico sem login: a avaliacao decide
  contratacao, e "quem avaliou" precisa ser identidade e nao nome digitado.
