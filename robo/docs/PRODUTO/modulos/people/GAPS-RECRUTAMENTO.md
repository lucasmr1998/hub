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
| **13** | **Campos do Perfil que faltam** | **4h** | **ABERTO** |
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

## Os que estao abertos

### 13. Campos do Perfil que faltam

A aba Perfil deles mostra: cargo pretendido, categoria de experiencia, "ja
trabalhou em alguma empresa deste grupo?", endereco com rua e numero, e
trajetoria profissional em texto livre.

**Nao copiar "como conheceu a vaga"**: eles PERGUNTAM ao candidato; nos MEDIMOS
pelo link de origem, que e mais confiavel que memoria de quem preencheu.

Parte disso ja da pra fazer sem codigo, com os campos custom por vaga.

### 14. Botao "Reativar" no card de saida

A rota de reabrir ja existe (`SAIDAS_REABRIVEIS`). Falta o botao no card, que
nos cards de Inaptos deles fica ao lado do motivo.

### 15. "Selecionar varios" no kanban

Temos selecao em lote na LISTA, e nao no kanban. Eles tem nos dois.

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
