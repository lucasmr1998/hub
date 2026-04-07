# 13. Comercial — Modulo de Fluxos

**Status:** ✅ Em producao
**Ultima atualizacao:** 06/04/2026
**App:** `apps/comercial/atendimento/`

---

## Contexto

O modulo de Fluxos e o motor de fluxos conversacionais (bot) da AuroraISP. Suporta dois modos:

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
| tipo | CharField(20) | entrada, questao, condicao, acao, delay, finalizacao |
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

### Entrada

Ponto de inicio do fluxo. 0 inputs, 1 output.

**Config:** `canal` (canal que ativa o fluxo)

### Questao (Interacao)

Envia mensagem ao lead. Pode esperar resposta ou nao.

**Subtipos na sidebar:** Texto, Selecao, Imagem, Pix

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
| max_tentativas | Maximo de tentativas (padrao: 3) |
| mensagem_erro | Mensagem quando resposta invalida |
| webhook_validacao | URL do webhook para validacao externa |
| prompt_validacao | Prompt enviado ao webhook/IA junto com a resposta |
| integracao_ia_id | ID da integracao de IA para validacao (OpenAI, Claude, Groq, Gemini) |

**Cascata de validacao:**
1. Resposta vazia (se espera_resposta)
2. Opcoes (para selecao)
3. Tipo (email, telefone, CPF, CEP, numero)
4. Regex
5. Integracao IA (chama provider configurado)
6. Webhook externo

**Modelos prontos:** Ao selecionar um modelo (ex: "Nome"), preenche automaticamente titulo, validacao e campo de salvamento.

### Condicao

Avalia uma condicao e segue branch true ou false. 1 input, 2 outputs.

**Subtipos:** campo_check, resposta_check

**Config:**

| Campo | Descricao |
|-------|-----------|
| campo | Campo a verificar (lead.origem, lead.score, lead.cidade, ultima_resposta, etc.) |
| operador | igual, diferente, contem, maior, menor, maior_igual, menor_igual |
| valor | Valor para comparacao |

### Acao

Executa algo e continua. 1 input, 1 output.

**Subtipos:**

| Subtipo | Descricao |
|---------|-----------|
| criar_oportunidade | Cria oportunidade no CRM (pipeline padrao, estagio inicial) |
| webhook | Chama URL externa (GET/POST) |
| criar_tarefa | Cria tarefa no CRM |
| mover_estagio | Move oportunidade de estagio |
| notificacao_sistema | Cria notificacao no sistema |

### Delay

Pausa a execucao por um tempo. 1 input, 1 output.

**Config:** `valor` (numero) + `unidade` (minutos, horas, dias)

### Finalizacao

Finaliza o atendimento. 1 input, 0 outputs.

**Subtipos:** finalizar (simples), calcular_score (com score 1-10)

**Config:** `mensagem_final`, `score` (para calcular_score)

---

## Editor Visual

**URL:** `/configuracoes/fluxos/<id>/editor/`
**Biblioteca:** Drawflow v0.0.59 (CDN)
**Layout:** Sidebar (paleta de nos) + Canvas (Drawflow) + Config Panel (direita)

**Sidebar (todos colapsados por padrao):**
- Entrada: Inicio do Fluxo
- Interacao (icone WhatsApp): Texto, Selecao, Imagem, Pix
- Condicoes: Verificar Campo, Verificar Resposta
- Acoes: Criar Oportunidade, Webhook, Criar Tarefa, Mover Estagio, Notificacao
- Controle: Atraso, Finalizar Fluxo, Finalizar com Score

**Salvar:** POST para `/api/fluxos/<id>/salvar-fluxo/` com `{drawflow_state, nodos[], conexoes[]}`

**Carregar:** Importa de `fluxo_json` ou reconstroi do banco se nao houver JSON salvo.

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

**Fluxo:** Resposta do lead + prompt de validacao → API do provider → JSON `{valido, mensagem}` → aceita ou rejeita

---

## Canal de Ativacao

Cada fluxo tem um `canal` que define quando e ativado automaticamente:

1. Mensagem chega no Inbox (ex: WhatsApp)
2. Signal `on_mensagem_recebida` detecta o canal
3. Engine busca fluxo ativo para o canal (`buscar_fluxo_por_canal`)
4. Prioridade: fluxo do canal exato → fluxo "qualquer" → nenhum
5. Cria atendimento e inicia o fluxo
6. Pergunta do bot e enviada de volta no Inbox como mensagem "Aurora"

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
| `/configuracoes/questoes/` | Gerenciamento de questoes (legado) |

### APIs

| Metodo | URL | Descricao |
|--------|-----|-----------|
| GET | `/api/fluxos/` | Listar fluxos |
| POST | `/api/fluxos/criar/` | Criar fluxo |
| PUT | `/api/fluxos/<id>/atualizar/` | Atualizar fluxo |
| DELETE | `/api/fluxos/<id>/deletar/` | Deletar fluxo |
| POST | `/api/fluxos/<id>/salvar-fluxo/` | Salvar editor visual |

---

## Relacionamentos

```
FluxoAtendimento
├── questoes → QuestaoFluxo (1:N, legado)
├── nodos → NodoFluxoAtendimento (1:N, visual)
├── conexoes → ConexaoNodoAtendimento (1:N, visual)
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
| `engine.py` | Engine visual: traversal, validacao (tipo/regex/IA/webhook), acoes, delays |
| `views.py` | Editor visual, salvar fluxo, sessoes, detalhe, fluxo ao vivo |
| `views_api.py` | APIs CRUD, N8N dual-mode |
| `templates/editor_fluxo.html` | Editor Drawflow |
| `templates/sessoes.html` | Lista de sessoes |
| `templates/sessao_detalhe.html` | Detalhe com logs |
| `templates/sessao_fluxo_visual.html` | Fluxo ao vivo read-only |
| `templates/fluxos.html` | CRUD de fluxos |
