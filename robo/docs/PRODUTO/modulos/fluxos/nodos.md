# Fluxos — Tipos de Nodos

Cada nodo tem um comportamento especifico quando o engine o executa. A tabela abaixo resume se o nodo **pausa** (aguarda resposta do lead) ou **continua** (engine segue para o proximo nodo).

| Tipo | Pausa? | Inputs | Outputs | Funcao |
|------|--------|--------|---------|--------|
| entrada | nao | 0 | 1 (default) | Ponto de inicio |
| questao (espera=true) | sim | 1 | 2 (true/false) | Pergunta + valida resposta |
| questao (espera=false) | nao | 1 | 1 (true) | Envia mensagem e continua |
| condicao | nao | 1 | 2 (true/false) | Avalia campo + operador + valor |
| acao | nao | 1 | 2 (default/erro) | Executa acao (CRM, webhook, etc.) |
| delay | sim | 1 | 1 (default) | Pausa por X tempo (retomada via cron) |
| finalizacao | sim (fim) | 1 | 0 | Encerra o atendimento |
| transferir_humano | sim (fim bot) | 1 | 0 | Coloca conversa em fila humana |
| ia_classificador | nao | 1 | N (categoria_*) | Classifica mensagem em categoria |
| ia_extrator | nao | 1 | 2 (true/false) | Extrai dados estruturados |
| ia_respondedor | sim | 1 | 1 (default) | Responde com IA e pausa |
| ia_agente | sim | 1 | 1 (default) | Agente conversacional com tools |

---

## Entrada

Ponto de inicio do fluxo. O engine busca o nodo de entrada ao iniciar o fluxo visual.

**Config:** nenhuma

---

## Questao

Envia pergunta/mensagem ao lead. O comportamento depende de `espera_resposta`:

- **true**: PAUSA e aguarda resposta do lead
- **false**: envia mensagem e continua (mensagem acumulada ate proximo nodo que pausa)

**Subtipos no editor:** Texto, Selecao, Imagem, Pix

**Config:**

| Campo | Descricao |
|-------|-----------|
| modelo | Modelo pronto: nome, email, telefone, cpf, cidade, cep, endereco, plano |
| titulo | Texto da pergunta |
| descricao | Instrucoes adicionais |
| opcoes_resposta | Lista de opcoes (para selecao) |
| espera_resposta | true = pausa e aguarda, false = envia e continua |
| validacao | Tipo: texto, email, telefone, cpf_cnpj, cep, numero |
| regex | Regex customizado de validacao |
| salvar_em | Campo do lead onde salvar (nome_razaosocial, email, telefone, cpf_cnpj, cidade, cep, rua, etc.) |
| pular_se_preenchido | Se true e `salvar_em` ja tem valor no lead, pula a questao |
| ia_acao | validar, classificar, extrair, classificar_extrair (IA integrada na questao) |
| integracao_ia_id | ID da integracao IA |
| ia_categorias | Lista de categorias (para classificar) |
| ia_variavel_saida | Nome da variavel onde salvar a classificacao |
| ia_campos_extrair | Campos a extrair (para extrair/classificar_extrair) |
| mensagem_erro | Mensagem quando resposta invalida |

**Cascata de validacao:**

1. Resposta vazia (se espera_resposta=true)
2. Opcoes (para selecao)
3. Tipo (email, telefone, CPF, CEP, numero)
4. Regex
5. Integracao IA (validar)
6. Webhook externo

**IA integrada (`ia_acao`):**

| Acao | Comportamento |
|------|--------------|
| validar | IA valida a resposta (chama webhook/LLM) |
| extrair | IA extrai campos da resposta e salva em variaveis ou no lead |
| classificar | IA classifica em uma categoria de `ia_categorias` |
| classificar_extrair | Faz extrair + classificar numa chamada so (mais eficiente) |

Quando `ia_acao != validar`:

- IA sucesso → branch `true`
- IA falha → branch `false` (geralmente vai pro fallback: ia_agente ou ia_respondedor)

**Fallback com base de conhecimento:** ver [integracao-ia.md](integracao-ia.md#base-de-conhecimento-nos-fallbacks).

---

## Condicao

Avalia uma condicao e segue branch true ou false.

**Subtipos:** campo_check, resposta_check

**Config:**

| Campo | Descricao |
|-------|-----------|
| campo | Campo a verificar (lead.origem, lead.score, lead.cidade, ultima_resposta, var.classificacao, var.custom, etc.) |
| operador | igual, diferente, contem, maior, menor, maior_igual, menor_igual |
| valor | Valor para comparacao |

Condicoes compostas (AND/OR) tambem sao suportadas.

Campos com ponto (`var.classificacao`) sao resolvidos no contexto construido pelo engine — ver [variaveis-contexto.md](variaveis-contexto.md).

---

## Acao

Executa algo e continua.

**Subtipos:**

| Subtipo | Descricao |
|---------|-----------|
| criar_oportunidade | Cria oportunidade no CRM (pipeline, estagio, responsavel configurados) |
| mover_estagio | Move oportunidade do lead para outro estagio |
| criar_tarefa | Cria tarefa no CRM com responsavel |
| webhook | Chama URL externa (GET/POST) com contexto |
| enviar_whatsapp | Envia mensagem WhatsApp adicional |
| enviar_email | Envia email |
| notificacao_sistema | Cria notificacao no painel |

**criar_oportunidade** — Config: `pipeline_id`, `estagio` (slug), `responsavel_id`, `titulo`. Nao duplica se lead ja tem oportunidade (atualiza `dados_custom`).

**mover_estagio** — Config: `estagio` (slug). Move oportunidade ativa do lead.

**Branch de erro:** quando a acao falha (webhook 500, banco indisponivel, etc.), segue a saida `erro` se configurada. Senao propaga a excecao.

---

## Delay

Pausa a execucao por um tempo. Registra `ExecucaoFluxoAtendimento` com data agendada. Cron `executar_pendentes_atendimento` retoma quando chega a hora.

**Config:** `valor` (numero) + `unidade` (minutos, horas, dias)

---

## Finalizacao

Finaliza o atendimento com score opcional.

**Subtipos:** finalizar (simples), calcular_score (com score 1-10)

**Config:**

- `mensagem_final`: mensagem enviada ao lead (suporta interpolacao de variaveis)
- `score`: score calculado (atualiza `lead.score_qualificacao`)
- `motivo_finalizacao`: completado, ganho, perdido, sem_interesse, etc.

---

## Transferir para Humano

Tira o atendimento do bot e coloca na fila humana do Inbox.

**Comportamento:**

- Marca `Conversa.modo_atendimento = 'humano'`
- Distribui para fila do canal (round-robin entre agentes)
- Se fora do horario de atendimento, envia `FilaInbox.mensagem_fora_horario`
- Encerra o atendimento do fluxo (`motivo_finalizacao='transferido'`)

**Config:** `fila_id` (opcional — se vazio, usa fila padrao do canal)

---

## Classificador IA (ia_classificador)

Analisa a mensagem do usuario e retorna uma categoria como variavel. NAO pausa.

**Config:**

| Campo | Descricao |
|-------|-----------|
| integracao_ia_id | Integracao de IA (OpenAI, Anthropic, Groq, Google AI) |
| modelo | Modelo a usar (gpt-4o-mini, claude-haiku, etc.) |
| prompt | Instrucoes para classificacao |
| categorias | Lista de categorias possiveis |
| variavel_saida | Nome da variavel onde salvar (padrao: `classificacao`) |

**Branches multiplos:** cada categoria pode ter sua propria saida (`categoria_<nome>`). Util para rotear direto sem passar por condicao.

**Uso tipico:** decidir qual branch seguir baseado na intencao do usuario.

---

## Extrator IA (ia_extrator)

Extrai dados estruturados da mensagem. NAO pausa. Tem 2 outputs (true se extraiu, false se nao extraiu nada).

**Config:**

| Campo | Descricao |
|-------|-----------|
| integracao_ia_id | Integracao de IA |
| modelo | Modelo a usar |
| prompt | Instrucoes extras para extracao |
| campos_extrair | Lista: `[{nome, tipo, descricao}]` |
| salvar_no_lead | Se true, salva campos extraidos diretamente no lead |

**Uso tipico:** apos o usuario informar dados (nome, curso, cidade), extrair e salvar automaticamente.

---

## Respondedor IA (ia_respondedor)

Gera resposta conversacional com IA e envia ao usuario. PAUSA apos enviar. Multi-turno configuravel.

**Config:**

| Campo | Descricao |
|-------|-----------|
| integracao_ia_id | Integracao de IA |
| modelo | Modelo a usar |
| system_prompt | Prompt do sistema (aceita variaveis: `{{lead_nome}}`, `{{classificacao}}`, `{{oport_dados_custom_curso}}`, etc.) |
| incluir_historico | Se true, inclui mensagens anteriores no contexto |
| max_historico | Maximo de mensagens no historico (padrao: 10) |
| max_turnos | Maximo de turnos antes de sair (padrao: 10) |
| continuar_conversa | Se true, mantem o nodo ativo para turnos subsequentes |
| mensagem_timeout | Mensagem se LLM falhar |

**Injecao automatica:**

- Se `contexto._base_conhecimento` existe (vindo do fallback com KB ativa), os artigos sao adicionados ao system_prompt antes da chamada LLM
- Dados do lead sao adicionados ao prompt automaticamente
- Variaveis IA (`var.classificacao`, etc.) disponiveis para interpolacao

**Uso tipico:** responder perguntas, apresentar valores, retomar pergunta do fluxo apos duvida do lead.

---

## Agente IA (ia_agente)

Agente conversacional multi-turno com tools. PAUSA a cada turno.

**Config:**

| Campo | Descricao |
|-------|-----------|
| integracao_ia_id | Integracao de IA |
| modelo | Modelo a usar |
| system_prompt | Prompt completo do agente |
| max_turnos | Maximo de turnos de conversa (padrao: 10) |
| tools_habilitadas | Lista: consultar_base_conhecimento, atualizar_lead, tools do Assistente CRM |
| tools_customizadas | Tools custom configuradas pelo tenant |
| mensagem_timeout | Mensagem de fallback |

**Comportamento multi-turno:**

1. Recebe mensagem do lead → chama LLM com historico + tools
2. Se LLM chama tool → executa → re-chama LLM com resultado → loop ate max 5 iteracoes
3. LLM retorna texto final → envia ao lead → PAUSA

**One-shot (saida imediata):** Se a resposta da LLM contem JSON `{sair: true, motivo: "..."}`, o engine:

- Sai do nodo sem pausar
- Segue as conexoes de saida (permite usar ia_agente como classificador que roteia na primeira mensagem)

**Uso tipico:**

- Assistente CRM via WhatsApp (tools operam no CRM) — ver [assistente-crm/](../assistente-crm/)
- Fallback inteligente com base de conhecimento
- Classificador one-shot com saida por JSON
