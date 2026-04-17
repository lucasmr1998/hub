# Fluxos

**Status:** Em producao
**App:** `apps/comercial/atendimento/`

Motor de fluxos conversacionais (bot) da Hubtrix. Este modulo documenta o **design-time** (editor, tipos de nodos, configuracao). A **execucao** (runtime) esta em [atendimento/](../atendimento/).

Suporta dois modos:

- **Legado (questoes lineares):** QuestaoFluxo com perguntas sequenciais e roteamento por indice
- **Visual (node-based):** Editor Drawflow com nodos de diferentes tipos conectados por arestas

O campo `FluxoAtendimento.modo_fluxo` define qual engine usar. Os dois modos coexistem.

---

## Indice

| Arquivo | Conteudo |
|---------|----------|
| [nodos.md](nodos.md) | 11 tipos de nodos (entrada, questao, condicao, acao, delay, finalizacao, transferir, 4 IAs) |
| [editor-visual.md](editor-visual.md) | Editor Drawflow: sidebar, toolbar, salvar, debug |
| [variaveis-contexto.md](variaveis-contexto.md) | Variaveis disponiveis + interpolacao em prompts |
| [integracao-ia.md](integracao-ia.md) | Providers suportados + base de conhecimento nos fallbacks |
| [endpoints.md](endpoints.md) | Paginas e APIs |

---

## FluxoAtendimento

Define um fluxo reutilizavel.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| nome | CharField(255) | Nome do fluxo |
| descricao | TextField | Descricao detalhada |
| tipo_fluxo | CharField(20) | qualificacao, vendas, suporte, onboarding, pesquisa, customizado |
| status | CharField(20) | ativo, inativo, rascunho, teste |
| canal | CharField(20) | qualquer, whatsapp, site, facebook, instagram, google, telefone, email, indicacao, manual |
| max_tentativas | PositiveInteger | Maximo de tentativas (padrao: 3) |
| tempo_limite_minutos | PositiveInteger | Tempo limite em minutos |
| permite_pular_questoes | Boolean | Permite pular questoes opcionais |
| modo_fluxo | Boolean | False = legado, True = visual (node-based) |
| fluxo_json | JSONField | Estado do editor Drawflow para re-import |
| **base_conhecimento_ativa** | Boolean | Fallbacks consultam ArtigoConhecimento automaticamente |
| recontato_ativo | Boolean | Ativar recontato automatico |
| recontato_config | JSONField | Config de recontato |
| criado_por | CharField(100) | Usuario criador |
| ativo | Boolean | Ativo/inativo |

**Tabela:** `fluxos_atendimento`

---

## Sistema visual (models auxiliares)

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
| tipo_saida | CharField(50) | default, true, false, erro, categoria_* |

**Tabela:** `atendimento_conexaonodo`
**Constraint:** unique `(nodo_origem, nodo_destino, tipo_saida)`

---

## Canal de ativacao

Cada fluxo tem um `canal` que define quando e ativado automaticamente:

1. Mensagem chega no Inbox (ex: WhatsApp)
2. Signal `on_mensagem_recebida` detecta o canal
3. Engine busca fluxo ativo para o canal (`buscar_fluxo_por_canal`)
4. **Prioridade:** fluxo especifico vinculado ao `CanalInbox` → fluxo do canal exato → fluxo "qualquer" → nenhum
5. Cria atendimento e inicia o fluxo
6. Pergunta do bot e enviada de volta no Inbox como mensagem bot

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
| `models.py` | FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento, ExecucaoFluxo, LogFluxo + legado |
| `engine.py` | Engine visual: traversal, IA integrada, fallback com KB, acoes, delays, tools (ver [atendimento/engine.md](../atendimento/engine.md)) |
| `views.py` | Editor visual, salvar fluxo, sessoes, simulador |
| `views_api.py` | APIs CRUD, N8N dual-mode |
| `templates/editor_fluxo.html` | Editor Drawflow |
| `templates/fluxos.html` | CRUD de fluxos |
