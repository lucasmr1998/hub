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

## Campos que o tenant inventa

O catalogo de `campos_candidatura.py` e fixo em codigo porque cada campo de la
tem coluna no `Candidato`. `CampoCandidatura` e a saida pro que nao tem coluna:
uma vaga de motoboy quer CNH, uma de caixa nao, e nenhuma justifica migration
em producao.

**A divisao de papel e a mesma dos campos de sistema:** em `/people/campos/` o
TENANT define o campo (rotulo, tipo, opcoes, secao); em cada vaga ele escolhe se
pede e se e obrigatorio, pelo mesmo `config_campos`. Um segundo modelo mental
faria o usuario ter que aprender qual campo se configura onde.

Tipos: texto curto, texto longo, numero, data, lista de opcoes, sim ou nao.
Nao ha `file`: curriculo ja e o anexo do formulario, e um segundo upload
precisaria de storage privado, limite e expurgo proprios.

### As quatro decisoes que sustentam isso

**1. A chave e prefixada com `custom__`.** Sem prefixo, um tenant que criasse a
chave "email" produziria um campo com o mesmo nome do campo de sistema, e o
POST, a config da vaga e a validacao passariam a disputar a mesma chave em
silencio. O prefixo torna a colisao impossivel por construcao, em vez de depender
de uma lista de nomes proibidos que envelhece.

**2. O expurgo LGPD zera `dados_custom` INTEIRO**, sem inspecionar o conteudo.
O campo e inventado pelo tenant, entao nao ha como saber o que ele pos ali: um
cliente cria "Nome da mae" ou "CPF" e, se a limpeza fosse por chave conhecida,
esse dado sobreviveria a retencao e a promessa do consentimento quebraria em
silencio. Zerar tudo e a unica limpeza que nao depende de adivinhar. E o ponto
mais importante desta feature, e o que dois testes protegem primeiro.

**3. Campo novo nasce DESLIGADO nas vagas.** Criar um campo no nivel do tenant
nao pode, sozinho, mudar o formulario de uma vaga que ja esta no ar recebendo
candidato.

**4. O slug nao muda na edicao.** Ele e a chave das respostas ja gravadas;
trocar deixaria toda resposta anterior orfa, sem erro nenhum, so um campo que
aparece vazio pra quem ja respondeu. Renomear o rotulo continua livre.

### As guardas da tela

| Guarda | Por que |
|---|---|
| Nao apaga campo ja respondido | O valor ficaria no `dados_custom` sem nada que diga o que a chave significava. Pra parar de perguntar, o caminho e desativar |
| Lista sem opcao e recusada | Um select vazio e um campo que o candidato nao consegue preencher |
| Opcao fora da lista e descartada no POST | Valor que nao esta entre as opcoes e POST forjado, nao erro de digitacao |

O catalogo continua **Python puro, sem Django**: as funcoes recebem os campos do
tenant como parametro (`extras`), ja convertidos por `CampoCandidatura.como_campo()`.
Quem consulta o banco e o model. E o que mantem `campos_candidatura.py` testavel
em milissegundos.

---

## Atraso por etapa

`EtapaPipeline.sla_dias` existia desde o inicio e era CAMPO MORTO: o help_text do
model e o helper da tela de fluxo prometiam "depois disso o candidato aparece
como atrasado nesta etapa", e nada no modulo calculava atraso.

O que faltava era saber DESDE QUANDO. `Candidato.etapa_desde` e preenchido por
`mover_para_etapa`, e nao da pra usar `atualizado_em` no lugar: corrigir o
telefone do candidato bumparia o campo e o zeraria sem ele ter andado no
processo. A migration 0017 fez o back-fill a partir do `HistoricoCandidato`, com
fallback pro `criado_em`; sem isso o recurso nasceria mostrando "sem atraso" pra
todo mundo que ja estava no pipeline.

Tres bordas, todas com teste:

| Caso | Comportamento |
|---|---|
| Etapa sem `sla_dias` | NUNCA marca atraso. Prazo em branco e "sem prazo", nao "prazo zero" |
| Candidato que saiu do processo | Nao conta. Parado numa saida terminal e o estado final esperado |
| Exatamente no prazo | Ainda nao esta atrasado. Prazo de 3 dias significa que no terceiro dia esta em dia |

---

## Captacao continua (link sem vaga)

`LinkCandidatura.vaga` sempre aceitou nulo, o help_text documentava, a view
publica tratava o caso e havia testes cobrindo. **So nao existia botao que
criasse um**: o unico caminho de criacao era de dentro de uma vaga, e ele sempre
setava a vaga. Capacidade completa no backend, sem porta de entrada.

`/people/captacao/` e a porta. Vale por si: um QR fixo no balcao capta o ano
inteiro, sem depender de haver vaga aberta naquele dia, e quem chega cai direto
no banco de talentos.

A **unidade continua obrigatoria** mesmo sem vaga. Sem ela o candidato do banco
nao fica ligado a loja nenhuma, e o RH daquela loja nao encontra ele.

---

## Taxa de conversao por link

A tela dizia quantas candidaturas cada link trouxe e nao quantas pessoas
abriram. Sem o denominador nao da pra saber qual canal converte: 200 visitas com
2 candidaturas e pior que 30 com 8, e so a taxa mostra isso.

**Conta VISITANTE, e nao acesso.** Candidatura e uma pessoa; se o denominador
fosse acesso, numerador e denominador ficariam em unidades diferentes e a taxa
nao significaria nada. Recarregar a pagina, ou voltar pra corrigir um campo, e
comum num formulario.

### As tres decisoes

**1. Cookie proprio, e NAO a sessao do Django.** A sessao mora numa tabela do
banco e o `clearsessions` nao roda em lugar nenhum do projeto (prod tinha 144
linhas, 100 ja vencidas e nunca limpas). Criar uma sessao por visitante anonimo
de QR faria essa virar a tabela que mais cresce no sistema, sem nada limpando. O
cookie nao gera linha nenhuma, e guarda apenas "ja contei este visitante neste
link". Um teste garante que visita nao cria sessao.

**2. Robo nao conta.** WhatsApp e Facebook BUSCAM a URL pra montar o preview
quando alguem cola o link, e os dois sao justamente os canais de divulgacao em
uso. Sem o filtro por User-Agent, o ato de divulgar ja geraria movimento que
ninguem fez, e a leitura da tela se inverteria. A heuristica esta em
`utils.py::e_robo` e e assumidamente incompleta: robo que mente o User-Agent
passa. O objetivo nao e barrar abuso (pra isso ha rate limit), e sim tirar o
vies SISTEMATICO dos previews, que acontecem toda vez que alguem divulga.

**3. A taxa e escondida quando nao da pra confiar nela.** Link criado ANTES da
medicao ja tem candidatura sem visita correspondente, e a divisao daria numero
acima de 100%. Um numero que nasce quebrado destroi a confianca na tela inteira,
entao a celula diz "medindo visitas desde <data>" ate a contagem alcancar.

### Limites assumidos

Quem bloqueia cookie conta a cada visita, e quem abre no celular e depois no
computador conta duas. Os dois erram **pra cima**, entao a taxa real e melhor
que a exibida, nunca pior. Errar pro lado pessimista e o certo pra decidir verba.

Nenhum dado pessoal e gravado: quem so visitou nao consentiu com nada.

---

## Curriculo: formatos e o erro do Chrome

**Aceita imagem**, e nao so PDF e Word. Candidato de vaga operacional muitas
vezes nao tem curriculo em PDF: tem uma FOTO do curriculo impresso. Recusar
imagem fecha a porta pra essa fatia, e a dor numero um do cliente e "nao chega
candidato". A origem tambem aceita: os prints mostram "Curriculo (imagem)".
`.heic` entra porque e o padrao de foto do iPhone.

Os TRES lugares que falam de formato (o `accept` do campo, a validacao do POST e
o texto que o candidato le) saem de `EXTENSOES_CURRICULO`, em
`campos_candidatura.py`. Chumbar nos tres foi o que fez o honeypot divergir da
view em 21/07 e descartar candidato real.

### ERR_UPLOAD_FILE_CHANGED

O Chrome guarda o "modificado em" do arquivo no momento da SELECAO e confere de
novo no envio. Se mudou, aborta com tela propria, sem chegar no servidor: o
candidato so ve "Nao foi possivel acessar seu arquivo". No Android isso quebra o
tempo todo com arquivo vindo do Google Drive ou da Galeria, que sincronizam e
reescrevem sozinhos. Aconteceu com candidato real em 21/07.

**Conserto**: ler os bytes na selecao e trocar o arquivo do input por uma copia
em memoria. O que e enviado nao existe mais no disco, entao nao ha o que o Chrome
reconferir. Degrada bem: navegador sem `DataTransfer` nao troca nada e o envio
segue como antes.

Validado no navegador, e nao so por teste: com um arquivo de 30 dias no disco, o
arquivo no input passa a ter `lastModified` de agora.

---

## Mensagem de WhatsApp por etapa

Reuso da mecanica que ja existia no Departamento Pessoal (`MensagemEtapa`), com
a MESMA decisao de produto: **nada e enviado automaticamente**. O botao ABRE o
WhatsApp com o texto pronto, e o RH manda do proprio numero.

`wa.me` e nao API de proposito: funciona pra qualquer cliente, sem integracao
contratada, sem custo por mensagem e sem risco de bloqueio de numero. Quem tem
Uazapi automatiza pela engine, que e outro caminho e continua disponivel.

### ETAPA ou SAIDA, nunca os dois

`MensagemRecrutamento` aponta pra uma `EtapaPipeline` (FK) ou pra uma saida
(constante), e uma `CheckConstraint` garante que seja exatamente um. E a divisao
que estrutura o modulo inteiro: etapa e DADO, saida e CODIGO. Sem a constraint,
uma linha com os dois so seria descoberta quando a tela nao achasse a mensagem,
e o sintoma seria "sumiu", nao "esta errado".

**Saida tem precedencia sobre etapa** na hora de escolher qual exibir. Quem saiu
continua apontando pra ultima etapa em que esteve, e mandar a mensagem daquela
etapa pra quem foi reprovado seria constrangedor.

### Onde se configura e onde se usa

Configura em `/people/fluxo/`, junto das etapas, porque e configuracao do fluxo.
Usa na ficha do candidato, que mostra a mensagem ja renderizada pra fase atual e
deixa editar **so para aquele candidato**, sem alterar o padrao. O texto do
proprio produto de origem diz isso na tela, e a nossa repete.

Placeholders: `{{nome}}`, `{{primeiro_nome}}`, `{{vaga}}`, `{{unidade}}`,
`{{cargo}}`. Placeholder sem valor vira string vazia: a mensagem vai pro
candidato, e chave de template aparecendo pra ele e pior que a frase ficar curta.

Candidato anonimizado pelo expurgo LGPD nao gera link: sem numero, `wa.me/`
abriria uma tela de erro do WhatsApp em vez de simplesmente nao aparecer.

---

## A ponte pro Departamento Pessoal

E o unico ponto do modulo onde um Candidato vira Colaborador, e era a ultima
lacuna estrutural do corte B: a FK `Candidato.colaborador` existia desde o
inicio esperando quem a preenchesse.

**COPIA, E NAO VINCULO.** As condicoes da vaga sao copiadas pro colaborador no
ato da admissao. Depois disso nao ha ligacao viva: mudar a vaga no mes que vem
nao altera o que ficou registrado pra quem ja entrou. E requisito trabalhista,
nao preferencia. A origem descreve a mesma semantica na propria tela.

**Os dois registros coexistem.** O candidato nao "vira" colaborador nem some.
Apagar destruiria a analise de canal, que responde de onde vieram os que ficaram.

**Entra em `em_admissao`, e nao em experiencia**, e nasce com
`pendente_revisao=True`: falta CPF, e e justamente isso que a fase de admissao do
DP existe pra coletar. O formulario publico nao pede CPF de proposito (atrito de
conversao), entao o caminho e o link de cadastro do DP.

**Conflito de dedup nao cria segunda linha.** Ex funcionario voltando ja existe
no DP; a R1 do modulo proibe a duplicata, e quem decide se e a mesma pessoa e o
RH. O servico devolve o conflito em vez de escolher sozinho.

---

## Triagem por IA

**Sob demanda**, por um botao na ficha. Nao roda na chegada da candidatura, por
dois motivos: o `disparar_evento` executa a engine em tempo de request, e uma
chamada de LLM ali faria o candidato esperar dez segundos no celular; e assim o
custo fica sob controle do RH, que analisa quem interessa em vez dos 76 que
chegaram.

**Nunca move o candidato.** Devolve veredito sugerido, resumo, sinais de atencao
e a avaliacao requisito a requisito. A decisao continua humana, e ha teste
garantindo que nem com veredito "inapto" o candidato sai do lugar. A origem
repete a mesma regra: "sempre precisa de revisao humana".

**Recusa analisar sem requisito de triagem cadastrado.** Sem criterio declarado
a IA inventaria o proprio, e a consistencia que ela promete viraria
arbitrariedade com cara de objetividade.

**O que NAO vai pro prompt**: nome, WhatsApp, email e endereco de rua. Nao
ajudam a avaliar aptidao e so aumentam a exposicao de dado pessoal a um
terceiro. Cidade e bairro entram porque deslocamento e criterio real em vaga
operacional.

Guarda modelo e tokens por analise. "Quanto custa" era discussao aberta
inclusive na origem; com o consumo gravado, a pergunta se responde com dado real
em uma semana em vez de continuar debate.

Le PDF via `pypdf` (Python puro, sem dependencia de sistema). **Imagem nao e
lida**: precisaria de OCR. Quem manda foto continua sendo analisado pelo que
preencheu no formulario, e a analise registra `usou_curriculo=False` pra o RH
saber que a sugestao saiu mais pobre.

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
| `/people/candidatos/` | Board do pipeline: chips por etapa, lista da selecao, toggle kanban |
| `/people/candidatos/?saida=<chave>` | A mesma tela mostrando quem SAIU do processo |
| `/people/candidatos/<pk>/` | Ficha do candidato: Perfil, Historico, Curriculo |
| `/people/fluxo/` | Configuracao das etapas do pipeline |
| `/people/campos/` | Campos de candidatura que o tenant inventa |
| `/people/captacao/` | Links de captacao continua, sem vaga, pro banco de talentos |
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
| `test_people_campos_custom.py` | Expurgo limpa o JSON, sem colisao com campo de sistema, campo novo nasce desligado, as guardas da tela |
| `test_people_pipeline_board.py` | Mover livre, sair com motivo, etapa desativada nao some candidato, chips com contagem, saida clicavel, lote |
| `test_people_fluxo_config.py` | Edicao do fluxo respeita escopo; as duas guardas que impedem perda de dado |
| `test_people_atraso_e_captacao.py` | As bordas do atraso (etapa sem prazo, quem saiu, mover zera) e o link sem vaga ponta a ponta |
| `test_people_visitas_link.py` | Robo nao conta, refresh nao conta duas vezes, e quando a taxa NAO pode ser exibida |
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

- **Selecao em lote** no board. Com 76 candidatos numa etapa, mover um a um e sofrido. FECHADO.
- **QR inline** na lista de links (mostram a imagem, nao so o botao de baixar) e um botao "Visualizar" que abre a pagina publica. FECHADO.
- **Excluir link**, alem de desativar. Nos so desativamos, de proposito, pra preservar a atribuicao de canal. FECHADO com guarda: so exclui link SEM candidatura; com candidatura, desativa.
- Vaga criada por **wizard de 4 passos**; nosso formulario com abas cobre o mesmo. Nao vamos fazer.

### Onde a nossa implementacao ficou melhor

- **Toggle por requisito, nao por grupo.** O print mostra um unico toggle pro bloco "Requisitos Obrigatorios" inteiro. O nosso permite publicar um requisito e filtrar calado outro, que e o mecanismo que a regra 4.3 da spec descreve.
- **Requisitos estruturados**, nao textarea de texto livre. Sem estrutura, a triagem futura nao teria o que ler.
- **"Como chegou" e medido** pelo link de origem, nao perguntado ao candidato.
- **Expurgo LGPD com prazo declarado e anonimizacao**, sem equivalente visivel no material deles.

Estes gaps NAO entraram no corte B. Viraram a tarefa 213.

---

## Como os tres gaps de alto impacto foram fechados (tarefa 213)

### O board: chips, nao colunas

`views/pipeline.py` monta uma barra de chips (etapa, contador, cor) mais a lista
de UMA selecao. As contagens saem de **duas consultas agregadas**, uma por eixo,
nao de uma por chip:

```python
por_etapa = dict(base.filter(saida='').values_list('etapa').annotate(n=Count('id')))
por_saida = dict(base.exclude(saida='').values_list('saida').annotate(n=Count('id')))
```

O kanban continua existindo atras do toggle `?vista=kanban`, porque arrastar e
melhor com poucos candidatos. A escolha do padrao e a lista: e a vista que
aguenta os 76 candidatos numa etapa que o print da operacao mostrou.

**Fora de etapa.** Candidato cuja etapa foi desativada ou apagada nao some: cai
num chip proprio (`sem-etapa`), calculado como o resto entre o total por etapa e
os ids das etapas vivas. Sem isso, desativar uma etapa esconderia gente.

### As saidas viraram destino navegavel

Os quatro chips de saida (`?saida=admitido|banco_talentos|inapto|arquivado`)
usam a MESMA lista, so trocando o filtro. O banco de talentos deixou de ser um
registro sem tela: e um clique a partir do board, mostrando o motivo da saida
sob o nome.

### `/people/fluxo/`: a etapa virou configuracao de verdade

Criar, renomear, cor, prazo, reordenar (troca de `ordem` com a vizinha),
ativar/desativar e apagar. Editar reusa o formulario de criar, com `pk` num
hidden: dois formularios paralelos e a origem classica de um divergir do outro.

**As duas guardas, que sao o ponto da tela:**

| Guarda | Por que |
|---|---|
| Nao apaga etapa com candidato dentro | Apagar deixaria a pessoa orfa. Com gente dentro, o caminho e desativar, que preserva o vinculo e joga o candidato pro chip "Fora de etapa" |
| Nao reseta o fluxo com candidato no meio | Resetar tiraria todos de etapa de uma vez |

Uma unidade **herda** o fluxo do tenant ate criar a primeira etapa propria. O
aviso disso aparece ANTES de criar, nao depois: descobrir pelo efeito e ruim.

As saidas aparecem na tela como cartoes fixos, com o motivo escrito de nao serem
configuraveis (cada uma tem comportamento: admitir aciona a ponte com o DP,
banco de talentos entra na retencao LGPD). E a decisao "etapa e dado, saida e
codigo" ficando visivel pro usuario em vez de so viver no codigo.

### Mover em lote

`api_lote` processa **um a um pelos servicos**, nunca `queryset.update()`. Um
update em massa pularia `HistoricoCandidato` e o candidato perderia a trilha,
que e justamente o que da pra responder "quanto tempo esse processo levou".
