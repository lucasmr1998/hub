# 14. Comercial — Modulo de Atendimento

**Status:** ✅ Em producao
**Ultima atualizacao:** 06/04/2026
**App:** `apps/comercial/atendimento/`

---

## Contexto

O modulo de Atendimento gerencia a **execucao** dos fluxos conversacionais: sessoes ativas com leads, respostas, validacao, logs e integracao com Inbox/WhatsApp. A **configuracao** de fluxos esta documentada em `13-MODULO_FLUXOS.md`.

Suporta dois modos de execucao:
- **Legado:** QuestaoFluxo sequencial (questao por indice)
- **Visual:** Engine node-based com traversal do grafo (engine.py)

---

## Arquitetura — Modo Visual

```
Mensagem chega no Inbox (WhatsApp, Site, etc.)
          ↓
Signal on_mensagem_recebida (inbox/signals.py)
          ↓
engine.buscar_fluxo_por_canal(canal, tenant)
          ↓
   Fluxo encontrado? → engine.iniciar_por_canal(lead, canal)
          ↓
   Cria AtendimentoFluxo → engine.iniciar_fluxo_visual()
          ↓
   Percorre grafo: entrada → nodos...
          ↓
   Encontra nodo questao (espera_resposta=true)?
     → PAUSA, envia pergunta no Inbox como bot "Aurora"
          ↓
   Lead responde no WhatsApp
          ↓
   Signal detecta atendimento ativo → engine.processar_resposta_visual()
          ↓
   Valida resposta (tipo → regex → IA → webhook)
          ↓
   Salva no campo do lead (se configurado)
          ↓
   Segue conexoes → proximo nodo (condicao/acao/delay/finalizacao)
          ↓
   [loop ate finalizar]
          ↓
   Nodo finalizacao → score + atualiza lead → mensagem final no Inbox
```

---

## Models

### AtendimentoFluxo

Sessao ativa de um lead em um fluxo.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| lead | FK → LeadProspecto | Lead sendo atendido |
| fluxo | FK → FluxoAtendimento | Fluxo utilizado |
| historico_contato | FK → HistoricoContato | Historico vinculado (opcional) |
| nodo_atual | FK → NodoFluxoAtendimento | Posicao no modo visual (nullable) |
| status | CharField(30) | iniciado, em_andamento, pausado, completado, abandonado, erro, cancelado |
| questao_atual | PositiveInteger | Indice da questao atual (legado) |
| total_questoes | PositiveInteger | Total de questoes/nodos tipo questao |
| questoes_respondidas | PositiveInteger | Quantas foram respondidas |
| dados_respostas | JSONField | Respostas: `{nodo_id: {resposta, data, titulo, ...}}` |
| score_qualificacao | Integer(1-10) | Score calculado ao finalizar |
| tempo_total | PositiveInteger | Duracao em segundos |

**Tabela:** `atendimentos_fluxo`

### LogFluxoAtendimento

Registro de cada passo executado no fluxo visual.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| atendimento | FK → AtendimentoFluxo | Sessao |
| nodo | FK → NodoFluxoAtendimento | Nodo executado (nullable) |
| lead | FK → LeadProspecto | Lead (indexed) |
| tipo_nodo | CharField(20) | entrada, questao, condicao, acao, delay, finalizacao |
| subtipo_nodo | CharField(50) | Subtipo do nodo |
| status | CharField(20) | sucesso, erro, aguardando, agendado |
| mensagem | TextField | Descricao do que aconteceu |
| dados | JSONField | Dados extras (resposta, branch, score...) |
| data_execucao | DateTime | Quando executou |

**Tabela:** `atendimento_log_fluxo`

### ExecucaoFluxoAtendimento

Fila de execucoes pendentes (delays).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| atendimento | FK → AtendimentoFluxo | Sessao |
| nodo | FK → NodoFluxoAtendimento | Nodo de delay |
| contexto_json | JSONField | Contexto serializado |
| data_agendada | DateTime | Quando executar |
| status | CharField(20) | pendente, executado, cancelado, erro |

**Tabela:** `atendimento_execucao_pendente`

---

## Engine (engine.py)

Engine conversacional assincrono. A execucao **pausa** em nos de questao (espera_resposta=true) e delay.

### Funcoes principais

| Funcao | Descricao |
|--------|-----------|
| `buscar_fluxo_por_canal(canal, tenant)` | Busca fluxo ativo por canal (exato → "qualquer" → None) |
| `iniciar_por_canal(lead, canal, tenant)` | Cria atendimento automaticamente por canal |
| `iniciar_fluxo_visual(atendimento)` | Encontra nodo entrada, percorre ate primeira questao |
| `processar_resposta_visual(atendimento, resposta)` | Valida resposta, salva no lead, segue conexoes |
| `executar_pendentes_atendimento(tenant)` | Cron: executa delays pendentes |

### Traversal do grafo

| Tipo nodo | Comportamento |
|-----------|--------------|
| entrada | Passa direto, segue conexao default |
| questao (espera=true) | **PAUSA**, retorna dados da pergunta |
| questao (espera=false) | Envia mensagem, continua sem parar |
| condicao | Avalia campo/operador/valor, segue branch true ou false |
| acao | Executa (webhook, criar oportunidade, etc.), continua |
| delay | Agenda ExecucaoFluxoAtendimento, **PAUSA** |
| finalizacao | Calcula score, atualiza lead, **FIM** |

### Validacao de respostas (cascata)

1. **Resposta vazia** — rejeita se espera resposta
2. **Opcoes** — valida contra lista (para selecao)
3. **Tipo** — email (@), telefone (10+ digitos), CPF/CNPJ (11/14), CEP (8), numero
4. **Regex** — valida contra padrao customizado
5. **Integracao IA** — chama provider configurado (OpenAI, Claude, Groq, Gemini) com prompt
6. **Webhook** — chama URL externa com resposta + prompt, espera `{valido, mensagem}`

### Salvar resposta no lead

Se o nodo de questao tem `salvar_em` configurado, a resposta e salva diretamente no campo do lead:

| salvar_em | Campo do lead |
|-----------|---------------|
| nome_razaosocial | Nome |
| email | Email |
| telefone | Telefone |
| cpf_cnpj | CPF/CNPJ |
| cidade | Cidade |
| estado | Estado |
| cep | CEP |
| rua | Rua |
| bairro | Bairro |
| empresa | Empresa |
| observacoes | Observacoes |

### Acoes disponiveis

| Acao | Descricao |
|------|-----------|
| criar_oportunidade | Cria oportunidade no CRM (pipeline padrao, nao duplica) |
| webhook | Chama URL externa (GET/POST) com contexto |
| criar_tarefa | Cria tarefa no CRM com responsavel |
| mover_estagio | Move oportunidade de estagio |
| notificacao_sistema | Cria notificacao no painel |

### Validacao por IA

Usa integracoes configuradas em `/integracoes/` (modelo IntegracaoAPI).

| Provider | Tipo | Modelo padrao |
|----------|------|---------------|
| OpenAI | openai | gpt-4o-mini |
| Anthropic | anthropic | claude-haiku-4-5-20251001 |
| Groq | groq | llama-3.1-8b-instant |
| Google AI | google_ai | gemini-2.0-flash |

**Fluxo:** Prompt + resposta → API do provider → JSON `{valido, mensagem}` → aceita ou rejeita

---

## Integracao com Inbox

O signal `on_mensagem_recebida` em `apps/inbox/signals.py`:

1. Mensagem de contato chega no Inbox
2. Verifica se existe atendimento ativo aguardando resposta → processa resposta
3. Se nao, tenta iniciar novo fluxo pelo canal
4. Envia pergunta/mensagem do bot de volta no Inbox como remetente "Aurora" (tipo bot)
5. Envia via webhook externo (WhatsApp) se configurado no canal

---

## Telas de acompanhamento

### Sessoes (`/configuracoes/sessoes/`)
- Lista todas as sessoes com status, progresso, nodo atual
- Filtros por status (em andamento, completado, etc.) e por fluxo
- Botao "Ativos" nos cards de fluxo filtra sessoes ativas

### Detalhe da sessao (`/configuracoes/sessoes/<id>/`)
- Info: fluxo, canal, inicio, duracao, score, progresso
- Nodo atual (onde o lead esta)
- Respostas do lead
- **Log de execucao** passo a passo: cada nodo com status, mensagem e timestamp

### Fluxo ao vivo (`/configuracoes/sessoes/<id>/fluxo/`)
- Editor Drawflow em modo **read-only**
- Nodos executados com **borda verde**
- Nodo atual com **borda azul pulsando**
- Sidebar com legenda, dados da sessao e respostas

---

## Endpoints

### Paginas

| URL | Descricao |
|-----|-----------|
| `/configuracoes/sessoes/` | Lista de sessoes |
| `/configuracoes/sessoes/<id>/` | Detalhe com logs |
| `/configuracoes/sessoes/<id>/fluxo/` | Visualizacao ao vivo |

### APIs (dual-mode: legado + visual)

| Metodo | URL | Descricao |
|--------|-----|-----------|
| POST | `/api/n8n/atendimento/iniciar/` | Iniciar atendimento (detecta modo_fluxo) |
| POST | `/api/n8n/atendimento/<id>/responder/` | Responder (detecta modo_fluxo) |
| POST | `/api/n8n/atendimento/<id>/finalizar/` | Finalizar |
| POST | `/api/n8n/atendimento/<id>/pausar/` | Pausar |
| POST | `/api/n8n/atendimento/<id>/retomar/` | Retomar |

---

## Tabelas

| Model | Tabela |
|-------|--------|
| AtendimentoFluxo | `atendimentos_fluxo` |
| NodoFluxoAtendimento | `atendimento_nodofluxo` |
| ConexaoNodoAtendimento | `atendimento_conexaonodo` |
| ExecucaoFluxoAtendimento | `atendimento_execucao_pendente` |
| LogFluxoAtendimento | `atendimento_log_fluxo` |
| RespostaQuestao | `respostas_questao` (legado) |
| TentativaResposta | `tentativas_resposta` (legado) |

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `models.py` | Todos os models (legado + visual) |
| `engine.py` | Engine visual: traversal, validacao, acoes, IA, delays, logs |
| `views.py` | Editor, salvar fluxo, sessoes, detalhe, fluxo ao vivo |
| `views_api.py` | APIs N8N dual-mode |
| `apps/inbox/signals.py` | Signal que conecta mensagens do Inbox ao engine |
| `services/atendimento_service.py` | Integracao Matrix/HubSoft |
