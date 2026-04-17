# 13. Comercial — Modulo de Fluxos

**Status:** Em producao
**Ultima atualizacao:** 17/04/2026
**App:** `apps/comercial/atendimento/`

---

## Contexto

O modulo de Fluxos e o motor de fluxos conversacionais (bot) da Hubtrix. Suporta dois modos:

- **Legado (questoes lineares):** QuestaoFluxo com perguntas sequenciais e roteamento por indice
- **Visual (node-based):** Editor Drawflow com nodos de diferentes tipos conectados por arestas

O campo `FluxoAtendimento.modo_fluxo` define qual engine usar. Os dois modos coexistem.

A **execucao** dos fluxos esta documentada em `14-MODULO_ATENDIMENTO.md`.

---

## FluxoAtendimento

Define um fluxo reutilizavel.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| nome | CharField(255) | Nome do fluxo |
| descricao | TextField | Descricao detalhada |
| tipo_fluxo | CharField(20) | qualificacao, vendas, suporte, onboarding, pesquisa, customizado |
| status | CharField(20) | ativo, inativo, rascunho, teste |
| canal | CharField(20) | Canal que ativa o fluxo: qualquer, whatsapp, site, facebook, instagram, google, telefone, email, indicacao, manual |
| max_tentativas | PositiveInteger | Maximo de tentativas (padrao: 3) |
| tempo_limite_minutos | PositiveInteger | Tempo limite em minutos |
| permite_pular_questoes | Boolean | Permite pular questoes opcionais |
| modo_fluxo | Boolean | False = legado, True = visual (node-based) |
| fluxo_json | JSONField | Estado do editor Drawflow para re-import |
| **base_conhecimento_ativa** | Boolean | Fallbacks consultam ArtigoConhecimento automaticamente |
| recontato_ativo | Boolean | Ativar recontato automatico |
| recontato_config | JSONField | Config de recontato (tentativas, mensagens) |
| criado_por | CharField(100) | Usuario criador |
| ativo | Boolean | Ativo/inativo |

**Tabela:** `fluxos_atendimento`

---

## Sistema Visual (Node-Based)

### NodoFluxoAtendimento

No do fluxograma visual.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| fluxo | FK → FluxoAtendimento | Fluxo pai (cascade) |
| tipo | CharField(30) | entrada, questao, condicao, acao, delay, finalizacao, transferir_humano, ia_classificador, ia_extrator, ia_respondedor, ia_agente |
| subtipo | CharField(50) | Ex: texto, select, campo_check, webhook, criar_oportunidade |
| configuracao | JSONField | Config especifica do no |
| pos_x, pos_y | IntegerField | Posicao no canvas |
| ordem | PositiveIntegerField | Ordem |

**Tabela:** `atendimento_nodofluxo`

### ConexaoNodoAtendimento

Aresta dirigida entre dois nodos.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| fluxo | FK → FluxoAtendimento | Fluxo pai |
| nodo_origem | FK → NodoFluxoAtendimento | Origem |
| nodo_destino | FK → NodoFluxoAtendimento | Destino |
| tipo_saida | CharField(10) | default, true, false |

**Tabela:** `atendimento_conexaonodo`
**Constraint:** unique (nodo_origem, nodo_destino, tipo_saida)

---

## Tipos de Nodos

Cada nodo tem um comportamento especifico quando o engine o executa. A tabela abaixo resume se o nodo **pausa** (aguarda resposta do lead) ou **continua** (engine segue para o proximo nodo).

| Tipo | Pausa? | 1 input | Outputs | Funcao |
|------|--------|---------|---------|--------|
| entrada | nao | 0 | 1 (default) | Ponto de inicio |
| questao (espera=true) | sim | 1 | 2 (true/false) | Pergunta + valida resposta |
| questao (espera=false) | nao | 1 | 1 (true) | Envia mensagem e continua |
| condicao | nao | 1 | 2 (true/false) | Avalia campo + operador + valor |
| acao | nao | 1 | 1 (default) | Executa acao (CRM, webhook, etc.) |
| delay | sim | 1 | 1 (default) | Pausa por X tempo (retomada via cron) |
| finalizacao | sim (fim) | 1 | 0 | Encerra o atendimento |
| transferir_humano | sim (fim bot) | 1 | 0 | Coloca conversa em fila humana |
| ia_classificador | nao | 1 | 1 (default) | Classifica mensagem em categoria |
| ia_extrator | nao | 1 | 2 (true/false) | Extrai dados estruturados |
| ia_respondedor | sim | 1 | 1 (default) | Responde com IA e pausa |
| ia_agente | sim | 1 | 1 (default) | Agente conversacional com tools |

### Entrada

Ponto de inicio do fluxo. O engine busca o nodo de entrada ao iniciar o fluxo visual.

**Config:** nenhuma

### Questao

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
| salvar_em | Campo do lead onde salvar a resposta (nome_razaosocial, email, telefone, cpf_cnpj, cidade, cep, rua, etc.) |
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

**Fallback com base de conhecimento:** Quando `FluxoAtendimento.base_conhecimento_ativa=true`, o engine consulta `ArtigoConhecimento` antes de seguir para o branch `false`. Se encontra artigos, injeta no contexto (`_base_conhecimento`) para o ia_respondedor/ia_agente usar. Se nao encontra, registra a pergunta em `PerguntaSemResposta`.

### Condicao

Avalia uma condicao e segue branch true ou false.

**Subtipos:** campo_check, resposta_check

**Config:**

| Campo | Descricao |
|-------|-----------|
| campo | Campo a verificar (lead.origem, lead.score, lead.cidade, ultima_resposta, var.classificacao, var.custom, etc.) |
| operador | igual, diferente, contem, maior, menor, maior_igual, menor_igual |
| valor | Valor para comparacao |

Campos com ponto (`var.classificacao`) sao resolvidos no contexto construido pelo engine.

### Acao

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

**criar_oportunidade** — Config: pipeline_id, estagio (slug), responsavel_id, titulo. Nao duplica se lead ja tem oportunidade (atualiza `dados_custom`).

**mover_estagio** — Config: estagio (slug). Move oportunidade ativa do lead.

### Delay

Pausa a execucao por um tempo. Registra `ExecucaoFluxoAtendimento` com data agendada. Cron `executar_pendentes_atendimento` retoma quando chega a hora.

**Config:** `valor` (numero) + `unidade` (minutos, horas, dias)

### Finalizacao

Finaliza o atendimento com score opcional.

**Subtipos:** finalizar (simples), calcular_score (com score 1-10)

**Config:**
- `mensagem_final`: mensagem enviada ao lead
- `score`: score calculado (atualiza `lead.score_qualificacao`)

### Transferir para Humano

Tira o atendimento do bot e coloca na fila humana do Inbox.

**Comportamento:**
- Marca `Conversa.modo_atendimento = 'humano'`
- Distribui para fila do canal (round-robin entre agentes)
- Se fora do horario de atendimento, envia `FilaInbox.mensagem_fora_horario`
- Encerra o atendimento do fluxo (`motivo_finalizacao='transferido'`)

**Config:** `fila_id` (opcional — se vazio, usa fila padrao do canal)

### Classificador IA (ia_classificador)

Analisa a mensagem do usuario e retorna uma categoria como variavel. NAO pausa.

**Config:**

| Campo | Descricao |
|-------|-----------|
| integracao_ia_id | Integracao de IA (OpenAI, Anthropic, Groq, Google AI) |
| modelo | Modelo a usar (gpt-4o-mini, claude-haiku, etc.) |
| prompt | Instrucoes para classificacao |
| categorias | Lista de categorias possiveis |
| variavel_saida | Nome da variavel onde salvar (padrao: `classificacao`) |

**Uso tipico:** Antes de uma `condicao`, para decidir qual branch seguir baseado na intencao do usuario.

### Extrator IA (ia_extrator)

Extrai dados estruturados da mensagem. NAO pausa. Tem 2 outputs (true se extraiu, false se nao extraiu nada).

**Config:**

| Campo | Descricao |
|-------|-----------|
| integracao_ia_id | Integracao de IA |
| modelo | Modelo a usar |
| prompt | Instrucoes extras para extracao |
| campos_extrair | Lista: `[{nome, tipo, descricao}]` |
| salvar_no_lead | Se true, salva campos extraidos diretamente no lead |

**Uso tipico:** Apos o usuario informar dados (nome, curso, cidade), extrair e salvar automaticamente.

### Respondedor IA (ia_respondedor)

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
| mensagem_timeout | Mensagem se LLM falhar |

**Injecao automatica:**
- Se `contexto._base_conhecimento` existe (vindo do fallback com KB ativa), os artigos sao adicionados ao system_prompt antes da chamada LLM
- Dados do lead sao adicionados ao prompt automaticamente
- Variaveis IA (`var.classificacao`, etc.) disponiveis para interpolacao

**Uso tipico:** Responder perguntas, apresentar valores, retomar pergunta do fluxo apos duvida do lead.

### Agente IA (ia_agente)

Agente conversacional multi-turno com tools. PAUSA a cada turno.

**Config:**

| Campo | Descricao |
|-------|-----------|
| integracao_ia_id | Integracao de IA |
| modelo | Modelo a usar |
| system_prompt | Prompt completo do agente |
| max_turnos | Maximo de turnos de conversa (padrao: 10) |
| tools_habilitadas | Lista: consultar_base_conhecimento, atualizar_lead, tools do Assistente CRM (consultar_lead, listar_oportunidades, criar_tarefa, etc.) |
| tools_customizadas | Tools custom configuradas pelo usuario |
| mensagem_timeout | Mensagem de fallback |

**Comportamento multi-turno:**
1. Recebe mensagem do lead → chama LLM com historico + tools
2. Se LLM chama tool → executa → re-chama LLM com resultado → loop ate max 5 iteracoes
3. LLM retorna texto final → envia ao lead → PAUSA

**One-shot (saida imediata):** Se a resposta da LLM contem JSON `{sair: true, motivo: "..."}`, o engine:
- Sai do nodo sem pausar
- Segue as conexoes de saida (permite usar ia_agente como classificador que roteia na primeira mensagem)

**Uso tipico:**
- Assistente CRM via WhatsApp (tools operam no CRM)
- Fallback inteligente com base de conhecimento
- Classificador one-shot com saida por JSON

---

## Variaveis e Contexto

O engine constroi um `contexto` (dict) a cada execucao. Prompts e condicoes usam variaveis desse contexto via `{{nome}}`.

| Variavel | Origem |
|----------|--------|
| `lead_nome`, `lead_telefone`, `lead_email`, `lead_cidade`, etc. | Campos do lead |
| `lead_score`, `lead_origem`, `lead_valor` | Campos do lead |
| `ultima_resposta` | Ultima resposta do usuario |
| `resposta_nodo_<id>` | Resposta de um nodo especifico |
| `var.<nome>` | Variavel salva por ia_classificador / ia_extrator / classificar_extrair |
| `<nome>` | Mesma variavel (atalho sem prefixo `var.`) |
| `assistente_modo` | True quando e fluxo do Assistente CRM |
| `oport_dados_custom_<campo>` | Campo custom da oportunidade (setado pelo extrator) |
| `_base_conhecimento` | Artigos da base injetados automaticamente no fallback |

As variaveis IA ficam em `atendimento.dados_respostas.variaveis`.

---

## Editor Visual

**URL:** `/configuracoes/fluxos/<id>/editor/`
**Biblioteca:** Drawflow v0.0.59 (CDN)
**Layout:** Sidebar (paleta de nos) + Canvas (Drawflow) + Config Panel (direita)

**Sidebar (todos colapsados por padrao):**
- Entrada: Inicio do Fluxo
- Interacao (icone WhatsApp): Texto, Selecao, Imagem, Pix
- Condicoes: Verificar Campo, Verificar Resposta
- Acoes: Criar Oportunidade, Mover Estagio, Criar Tarefa, Webhook, Notificacao
- Inteligencia Artificial (icone brain, cor roxa): Classificador, Extrator, Respondedor, Agente
- Controle: Atraso, Finalizar Fluxo, Finalizar com Score, Transferir para Humano

**Toolbar:**
- Undo/Redo (Ctrl+Z / Ctrl+Y)
- Zoom +/- / Reset
- Recontato (modal config)
- **Base Conhecimento** (toggle — ativa consulta automatica nos fallbacks)
- Salvar
- Desativar / Ativar
- Logs (painel lateral com atendimentos e execucao passo a passo)
- Testar (simulador embutido)

**Salvar:** POST para `/api/fluxos/<id>/salvar-fluxo/` com `{drawflow_state, nodos[], conexoes[]}`.

**Carregar:** Importa de `fluxo_json` ou reconstroi do banco se nao houver JSON salvo.

**Debug visual:** Cada card mostra o `#pk` do nodo no canto direito do titulo (cinza pequeno) para facilitar identificar nodos em warnings e logs.

---

## Integracao com IA

A validacao por IA usa o modulo de integracoes (`apps/integracoes/`). O provedor configura uma integracao do tipo OpenAI, Anthropic, Groq ou Google AI com API key e modelo.

**Providers suportados:**

| Provider | Tipo | Modelo padrao |
|----------|------|---------------|
| OpenAI | openai | gpt-4o-mini |
| Anthropic | anthropic | claude-haiku-4-5-20251001 |
| Groq | groq | llama-3.1-8b-instant |
| Google AI | google_ai | gemini-2.0-flash |

**Fallback cross-tenant:** `_obter_integracao_ia` busca primeiro no tenant do fluxo; se nao achar, busca sem filtro (util para o Assistente CRM que roda no tenant Aurora HQ mas pode usar integracao do vendedor).

---

## Base de Conhecimento nos Fallbacks

Quando `FluxoAtendimento.base_conhecimento_ativa = True`, o engine enriquece automaticamente os fallbacks de questoes com artigos da base.

**Como funciona:**

1. Lead responde algo que nao passa na validacao ou extracao IA
2. Engine chama `_consultar_base_para_fallback(mensagem, atendimento)` antes de seguir o branch `false`
3. Funcao faz query por texto em `ArtigoConhecimento` (titulo/tags/conteudo)
4. **Encontrou artigos:** injeta no contexto como `_base_conhecimento`. O `ia_respondedor` ou `ia_agente` recebe esse texto no system_prompt e usa para responder
5. **Nao encontrou:** registra `PerguntaSemResposta` para o cliente criar artigo depois

**Custo:** zero chamadas LLM extras (so query SQL). O ia_respondedor que ja executaria recebe o contexto melhorado.

**Escalavel:** funciona para qualquer fluxo de qualquer cliente. Basta ligar o toggle.

---

## Canal de Ativacao

Cada fluxo tem um `canal` que define quando e ativado automaticamente:

1. Mensagem chega no Inbox (ex: WhatsApp)
2. Signal `on_mensagem_recebida` detecta o canal
3. Engine busca fluxo ativo para o canal (`buscar_fluxo_por_canal`)
4. Prioridade: fluxo especifico vinculado ao `CanalInbox` → fluxo do canal exato → fluxo "qualquer" → nenhum
5. Cria atendimento e inicia o fluxo
6. Pergunta do bot e enviada de volta no Inbox como mensagem bot

---

## Endpoints

### Paginas (HTML)

| URL | Descricao |
|-----|-----------|
| `/configuracoes/fluxos/` | Gerenciamento de fluxos (CRUD + botoes Editor Visual, Ativos, Questoes) |
| `/configuracoes/fluxos/<id>/editor/` | Editor visual Drawflow |
| `/configuracoes/sessoes/` | Acompanhamento de sessoes ativas |
| `/configuracoes/sessoes/<id>/` | Detalhe da sessao com logs |
| `/configuracoes/sessoes/<id>/fluxo/` | Visualizacao do fluxo ao vivo (nodo atual pulsando) |

### APIs

| Metodo | URL | Descricao |
|--------|-----|-----------|
| GET | `/api/fluxos/` | Listar fluxos |
| POST | `/api/fluxos/criar/` | Criar fluxo |
| PUT | `/api/fluxos/<id>/atualizar/` | Atualizar fluxo |
| DELETE | `/api/fluxos/<id>/deletar/` | Deletar fluxo |
| POST | `/api/fluxos/<id>/salvar-fluxo/` | Salvar editor visual |
| POST | `/api/fluxos/<id>/toggle/` | Ativar/desativar + toggle base_conhecimento |
| POST | `/api/fluxos/<id>/simular/` | Simulador de teste embutido |

---

## Relacionamentos

```
FluxoAtendimento
├── questoes → QuestaoFluxo (1:N, legado)
├── nodos → NodoFluxoAtendimento (1:N, visual)
├── conexoes → ConexaoNodoAtendimento (1:N, visual)
├── canais_inbox → CanalInbox (1:N, canal pode forcar fluxo)
└── atendimentos → AtendimentoFluxo (1:N)

NodoFluxoAtendimento
├── saidas → ConexaoNodoAtendimento (1:N)
├── entradas → ConexaoNodoAtendimento (1:N)
├── logs → LogFluxoAtendimento (1:N)
└── execucoes_pendentes → ExecucaoFluxoAtendimento (1:N)
```

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `models.py` | FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento, ExecucaoFluxoAtendimento, LogFluxoAtendimento + legado |
| `engine.py` | Engine visual: traversal, IA integrada, fallback com KB, acoes, delays, tools, assistente CRM |
| `views.py` | Editor visual, salvar fluxo, sessoes, detalhe, fluxo ao vivo, simulador |
| `views_api.py` | APIs CRUD, N8N dual-mode |
| `templates/editor_fluxo.html` | Editor Drawflow |
| `templates/sessoes.html` | Lista de sessoes |
| `templates/sessao_detalhe.html` | Detalhe com logs |
| `templates/sessao_fluxo_visual.html` | Fluxo ao vivo read-only |
| `templates/fluxos.html` | CRUD de fluxos |
