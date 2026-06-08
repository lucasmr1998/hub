# Diagnostico Critico dos Nodos do Fluxo de Atendimento

**Data:** 17/04/2026
**Objetivo:** Analise franca e critica de cada tipo de nodo, com problemas reais encontrados, inconsistencias e sugestoes.

---

## Visao geral

O engine tem **11 tipos de nodos**. Cada um foi adicionado em momentos diferentes, o que gerou inconsistencias de padrao. Algumas decisoes criticas:

- Nem todos os nodos tem as mesmas responsabilidades (logging, contexto, tratamento de erro)
- A "forma de pausar" varia: alguns retornam dict, outros setam nodo_atual, outros fazem os dois
- A propagacao de contexto entre nodos e implicita (dict por referencia) — frageis quando o fluxo esta complexo
- Nao ha contrato claro de entrada/saida de cada nodo (tipagem)

---

## 1. `entrada`

**O que faz:** ponto inicial do fluxo. Passa direto e segue conexao default.

**Criticas:**
- OK. Nodo mais simples, funciona bem.
- Nao faz nada alem de logar. Poderia ter validacao tipo "fluxo tem entrada?" no save do fluxo.

**Veredito:** 👍 Sem problemas reais.

---

## 2. `questao`

**O que faz:** pergunta algo ao lead, opcionalmente valida/extrai com IA.

**Criticas:**

**Muito sobrecarregado.** Um unico tipo de nodo faz:
- Pergunta simples (so envia mensagem)
- Pergunta com validacao (tipo, regex)
- Pergunta com extracao IA
- Pergunta com classificacao IA
- Pergunta com extracao + classificacao (classificar_extrair)
- Pergunta com pulo condicional (pular_se_preenchido)
- Pergunta sem espera (mensagem intercalada)

Cada combinacao e um comportamento diferente. O codigo tem `if ia_acao != 'validar'` espalhado em varios pontos.

**`pular_se_preenchido` tem bug subtil.** Se o lead ja tem nome salvo, pula a pergunta, mas continua processando IA. Se a IA classifica mal, pode falhar sem que o lead tenha enviado nada.

**A diferenca "espera_resposta=true/false" gera comportamentos muito diferentes.** Quando False, a mensagem acumula em `_mensagens_pendentes` e e enviada no proximo nodo que pausa. Isso e magico demais — nao aparece em lugar nenhum da doc do editor e confunde quem configura.

**Duas saidas (true/false) quando ia_acao=validar nao faz sentido.** Se nao tem IA, o branch false nunca e acionado. O editor mostra as duas conexoes sempre, o que confunde.

**Veredito:** 👎 Precisa ser quebrado em tipos mais especificos. Ideal:
- `mensagem` (antigo `espera_resposta=false`)
- `pergunta_simples` (sem IA)
- `pergunta_com_ia` (com ia_acao)

Ou pelo menos: melhor validacao no save + doc clara do comportamento.

---

## 3. `condicao`

**O que faz:** avalia campo + operador + valor, segue branch true ou false.

**Criticas:**

**Operadores limitados.** Suporta: igual, diferente, contem, maior, menor, maior_igual, menor_igual. Nao tem: inicia_com, termina_com, regex, entre (range), na lista. Para fluxos complexos, falta expressividade.

**Acesso a campos com dot notation e fragil.** `lead.score` funciona, mas `oport.dados_custom.curso` nao funciona direto — precisa usar `var.curso_interesse` (extraido pelo extrator). Cria dependencia obrigatoria do extrator antes de qualquer condicao relacionada a oportunidade.

**Nao tem "condicao composta" (AND/OR).** Se quero `score >= 7 AND origem == 'whatsapp'`, preciso de dois nodos de condicao em serie. Fica visualmente poluido.

**Sem log detalhado.** O log diz "Condicao: score igual 7 → true", mas se o campo nao for encontrado, retorna false silenciosamente. Debug fica dificil.

**Veredito:** 👎 Funcional mas limitado. Precisa de condicao composta (`operador_logico=and|or`) + mais operadores.

---

## 4. `acao`

**O que faz:** executa uma acao e continua (criar_oportunidade, mover_estagio, webhook, etc.).

**Criticas:**

**Nao pausa nem em caso de erro.** Se `criar_oportunidade` falhar (banco caiu, integracao quebrada), o log registra o erro mas o fluxo continua como se nada tivesse acontecido. Isso pode deixar o fluxo em estado inconsistente (ex: mover estagio de oportunidade que nao foi criada).

**Sem retry.** Webhook caiu? Falhou. Sem tentativa automatica.

**`criar_oportunidade` silenciosa quando ja existe.** Atualiza `dados_custom` mas nao loga isso claramente. Dev fica pensando "porque nao criou?".

**Subtipos sao string (`subtipo`) sem enum.** Se digitar "criar_oportuniade" (typo) no banco, nao da erro — so nao executa nada.

**Veredito:** 👎 Precisa de tratamento de erro explicito: branch `erro` opcional que e seguido se a acao falha. E enum de subtipos validado no save.

---

## 5. `delay`

**O que faz:** pausa o fluxo por X tempo via cron.

**Criticas:**

**Depende do cron rodar.** Se `executar_pendentes_atendimento` nao rodar (ex: cron quebrou no servidor), o fluxo fica preso indefinidamente.

**Sem "timeout maximo".** Se o lead agendar algo pra daqui a 3 meses, o atendimento fica aberto 3 meses. Deveria ter limite maximo.

**Serializacao do contexto e fraca.** `_serializar_contexto` remove objetos nao serializaveis — mas o contexto salvo pode ser reconstruido diferente quando o cron retoma. Variaveis podem sumir.

**Veredito:** 👎 Funciona mas fragil. Precisa de monitoramento (alerta se cron nao roda). E logica de timeout maximo.

---

## 6. `finalizacao`

**O que faz:** encerra o atendimento, opcionalmente define score.

**Criticas:**

**Score fixo no config do nodo.** Deveria poder ser dinamico — calcular score baseado nas respostas (ex: score = pontos por questao respondida, deducao por tempo, etc.). Hoje, se quero score diferente por caminho, preciso de varios nodos de finalizacao.

**Nao tem "motivo_finalizacao" configuravel.** Todos os nodos de finalizacao usam `motivo_finalizacao='completado'`. Mas o fluxo pode ter varios caminhos que finalizam (ganho, perda, sem interesse, etc.). Ficou tudo "completado".

**Mensagem final nao suporta variaveis.** Deveria interpolar `{{lead_nome}}` etc.

**Veredito:** 👎 Muito limitado. Precisa de score calculado, motivo configuravel e interpolacao.

---

## 7. `transferir_humano`

**O que faz:** tira do bot, coloca na fila humana.

**Criticas:**

**Acoplado ao Inbox.** Se o canal nao e Inbox (ex: widget, email), o transferir nao faz sentido. Deveria ter validacao.

**Distribuicao e sincrona.** `distribuir_conversa` roda dentro do engine. Se o distribuidor falha ou demora, trava.

**Nao tem "confirmacao de recebimento".** O bot diz "transferindo" mas se nao tem agente disponivel, a conversa fica na fila sem feedback. Deveria ter mensagem diferente para "sem agentes online".

**Nao volta ao bot.** Se o agente humano nao responder em X tempo, deveria ter opcao de devolver ao bot (escalar pra outro fluxo). Hoje e caminho sem volta.

**Veredito:** 👎 Funciona no caso feliz. Sem tratamento de casos reais (fora do horario, fila cheia, agente nao responde).

---

## 8. `ia_classificador`

**O que faz:** classifica a mensagem em uma categoria, salva como variavel.

**Criticas:**

**Sai direto sem branch.** Ao contrario do `ia_extrator` que tem true/false, o classificador sempre segue a unica saida default. Para rotear, e obrigatorio usar `condicao` depois. Isso forca mais nodos no fluxo.

**Match de categoria fragil.** Se a LLM retorna "acao" (sem acento) e a categoria e "Acao" (com C maiusculo), faz match parcial. Mas se retornar algo fora da lista (ex: "outro"), usa a primeira categoria da lista. Isso **mascara erros** — a classificacao falhou mas o fluxo continua como se tivesse acertado.

**Nao persiste o raw da LLM.** Debug fica impossivel — nao da pra saber o que a IA realmente respondeu.

**Veredito:** 👎 Precisa de branches multiplos (um por categoria) em vez de obrigar `condicao` depois. E registrar o raw da LLM nos logs.

---

## 9. `ia_extrator`

**O que faz:** extrai dados da mensagem em JSON, salva em variaveis/lead/oportunidade.

**Criticas:**

**Prefixos `oport.dados_custom.` sao confusos.** Voce tem que saber que `oport.dados_custom.curso` vira variavel `oport_dados_custom_curso`. Nao e explicado em lugar nenhum. Tenho que olhar o codigo pra entender.

**Parse de JSON frega.** Se a LLM responde com markdown (```json), o codigo tenta limpar. Se responde com texto antes do JSON, quebra. Sem retry.

**"Extraiu 0 campos" = branch false.** Correto tecnicamente, mas semanticamente estranho: se a IA entendeu a pergunta mas a resposta nao tinha dados (ex: "nao sei meu CPF"), cai no fallback errado.

**Nao valida os dados extraidos.** A LLM pode retornar `{cpf: "123"}` (invalido) e o engine salva no lead. Precisaria de validacao por tipo apos extracao.

**Veredito:** 👎 Funcional mas com gotchas. Precisa: doc dos prefixos, validacao de dados extraidos, retry no parse.

---

## 10. `ia_respondedor`

**O que faz:** agente conversacional simples, gera resposta e pausa.

**Criticas:**

**`max_turnos` nao esta sendo respeitado na implementacao atual.** Olhei o codigo e o `max_turnos` esta sempre vazio no config. O loop de historico nao incrementa turnos. Nunca sai.

**Historico cresce indefinidamente.** Em conversas longas, o prompt fica enorme, custa muito e a LLM perde foco.

**Sem condicao de saida clara.** Como o respondedor sabe quando a conversa "acabou"? Nao tem logica de "finalize quando o usuario despedir-se". Fica rodando para sempre ate algo externo interromper.

**Prompt expose variaveis internas.** `{{oport_dados_custom_curso_interesse}}` vira texto bruto se a variavel nao foi setada. Usuario final ve "escolheu " (vazio) na resposta do bot.

**Veredito:** 👎👎 O mais usado e o mais cheio de problemas. Multi-turno precisa ser revisitado.

---

## 11. `ia_agente`

**O que faz:** agente conversacional com tools (function calling).

**Criticas:**

**Tools hardcoded no codigo.** Tem uma lista de tools do "assistente CRM" misturada com tools do sistema. Nao e extensivel — se um cliente quer uma tool custom, precisa fazer deploy.

**One-shot via `{sair: true}` e fragil.** Depende da LLM retornar JSON exato. Se retornar texto com chaves no meio (ex: "o JSON { sair: true }"), o regex pode dar falso positivo.

**Loop de tool calling limitado a 5 iteracoes.** Sem aviso ao usuario quando atinge o limite. A conversa simplesmente para de evoluir.

**Tools nao tem versionamento.** Se mudar a assinatura de `atualizar_lead`, quebra todos os fluxos que usam.

**Veredito:** 👎 Poderoso mas nao production-ready. Precisa: tools por tenant (nao hardcoded), aviso de limite de turnos, versionamento.

---

## Problemas Transversais

### 1. Contexto implicito

O `contexto` e um dict passado por referencia entre nodos. Quando vai pra fundo no grafo (recursao), pode ser mutado silenciosamente por qualquer nodo. Dificil debugar.

**Solucao:** contexto imutavel ou com eventos de mudanca logados.

### 2. Propagacao de erros inconsistente

Alguns nodos logam erro e continuam. Outros retornam dict de erro. Outros levantam excecao. Nao ha padrao.

**Solucao:** exception hierarchy propria + comportamento padronizado (continuar, parar, fallback).

### 3. Falta de tipagem

Configuracoes de cada nodo sao dicts com chaves magicas (`titulo`, `ia_acao`, `pular_se_preenchido`, etc.). Typo na chave vira bug silencioso.

**Solucao:** schemas JSON validados no save. Ou dataclasses.

### 4. Engine em 1 arquivo

2200 linhas no `engine.py`. Scroll infinito. Funcoes relacionadas nao ficam juntas.

**Solucao:** quebrar por tipo de nodo — `engine/nodes/questao.py`, `engine/nodes/ia_respondedor.py`, etc.

### 5. Sem testes unitarios

O engine tem teste de integracao no simulador, mas nao testa cada nodo isoladamente. Um bug numa funcao comum (ex: `_salvar_variavel`) pode quebrar 4 nodos sem ninguem notar.

**Solucao:** testes unitarios por nodo + integracao por fluxo.

---

## Priorizacao de melhorias

| Prioridade | Item | Impacto | Esforco |
|------------|------|---------|---------|
| **P0** | Logar raw das LLMs (classificador, extrator, respondedor, agente) | Alto — resolve 80% dos bugs de IA | Baixo |
| **P0** | Motivo_finalizacao configuravel + interpolacao na mensagem_final | Alto | Baixo |
| **P1** | Branches multiplos no ia_classificador (um por categoria) | Alto | Medio |
| **P1** | Branch `erro` opcional no nodo acao | Medio | Baixo |
| **P1** | Validacao de schema JSON no save de nodo | Alto | Medio |
| **P2** | Condicao composta (AND/OR) | Medio | Medio |
| **P2** | `max_turnos` funcionando no ia_respondedor | Alto | Baixo |
| **P2** | Tools extensiveis por tenant no ia_agente | Medio | Alto |
| **P3** | Refatorar engine em modulos por tipo de nodo | Manutenibilidade | Alto |
| **P3** | Testes unitarios por tipo de nodo | Qualidade | Alto |

---

## Conclusao

O engine funciona e entrega valor. Mas cada tipo de nodo tem debitos que vao crescer quando o produto escalar. Os itens P0 e P1 sao "tapar buracos obvios" — o cliente percebe o bug e reclama. Os P2/P3 sao saude de longo prazo.

A recomendacao: **rodar os P0/P1 antes de adicionar features novas**. Sao 3-5 dias de trabalho focado que estabilizam muito o sistema.
