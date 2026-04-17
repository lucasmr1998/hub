# 14. Comercial — Modulo de Atendimento

**Status:** Em producao
**Ultima atualizacao:** 17/04/2026
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
Mensagem chega no Inbox (WhatsApp, Site, Widget)
          ↓
Signal on_mensagem_recebida (apps/inbox/signals.py)
          ↓
Existe atendimento ativo? → processar_resposta_<tipo>
          ↓
Nao → buscar_fluxo_por_canal(canal, tenant)
          ↓
Fluxo encontrado? → iniciar_por_canal(lead, canal)
          ↓
Cria AtendimentoFluxo → iniciar_fluxo_visual()
          ↓
Percorre grafo: entrada → nodos...
          ↓
Nodo pausa? (questao, delay, ia_respondedor, ia_agente, finalizacao)
  → PAUSA, retorna resultado
          ↓
Signal envia resposta do bot no Inbox → webhook do canal → WhatsApp
          ↓
Lead responde
          ↓
Signal detecta atendimento ativo → dispatch por nodo_atual.tipo:
  - questao: processar_resposta_visual
  - ia_respondedor: processar_resposta_ia_respondedor
  - ia_agente: processar_resposta_ia_agente
          ↓
Valida/extrai/classifica → segue branch true/false
          ↓
[loop ate finalizacao ou transferir_humano]
```

---

## Models

### AtendimentoFluxo

Sessao ativa de um lead (ou usuario) em um fluxo.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| lead | FK → LeadProspecto | Lead sendo atendido (nullable — Assistente CRM usa usuario) |
| fluxo | FK → FluxoAtendimento | Fluxo utilizado |
| historico_contato | FK → HistoricoContato | Historico vinculado (opcional) |
| nodo_atual | FK → NodoFluxoAtendimento | Posicao atual no grafo (nullable quando finaliza) |
| status | CharField(30) | iniciado, em_andamento, pausado, completado, abandonado, erro, cancelado |
| questao_atual | PositiveInteger | Indice da questao atual (legado) |
| total_questoes | PositiveInteger | Total de questoes/nodos tipo questao |
| questoes_respondidas | PositiveInteger | Quantas foram respondidas |
| dados_respostas | JSONField | Respostas + variaveis + historico IA + contexto assistente |
| motivo_finalizacao | CharField(30) | completado, sem_resposta, abandonado_usuario, transferido, cancelado_atendente, cancelado_sistema, tempo_limite |
| recontato_tentativas | PositiveInteger | Tentativas de recontato feitas |
| recontato_proximo_em | DateTime | Quando executar proximo recontato |
| score_qualificacao | Integer(1-10) | Score calculado ao finalizar |
| tempo_total | PositiveInteger | Duracao em segundos |

**Tabela:** `atendimentos_fluxo`

**Estrutura do `dados_respostas`:**

```json
{
    "<nodo_id>": {"resposta": "...", "data_resposta": "...", "titulo": "..."},
    "variaveis": {"classificacao": "...", "curso_interesse": "..."},
    "ia_agente_<nodo_id>": {"messages": [...], "turnos": N},
    "ia_historico_<nodo_id>": [mensagens de um ia_respondedor],
    "_ultima_mensagem": "ultima mensagem do lead",
    "_assistente_usuario_id": <user_id>,
    "_assistente_tenant_id": <tenant_id>,
    "_conversa_id": <conversa_id>
}
```

### LogFluxoAtendimento

Registro de cada passo executado no fluxo visual (util para debug e auditoria).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| atendimento | FK → AtendimentoFluxo | Sessao |
| nodo | FK → NodoFluxoAtendimento | Nodo executado (nullable) |
| lead | FK → LeadProspecto | Lead (indexed) |
| tipo_nodo | CharField(30) | Tipo do nodo executado |
| subtipo_nodo | CharField(50) | Subtipo do nodo |
| status | CharField(20) | sucesso, erro, aguardando, agendado, fallback |
| mensagem | TextField | Descricao legivel do que aconteceu |
| dados | JSONField | Dados extras (resposta, branch, score, variaveis) |
| data_execucao | DateTime | Quando executou |

**Tabela:** `atendimento_log_fluxo`

### ExecucaoFluxoAtendimento

Fila de execucoes pendentes (delays agendados).

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

Engine conversacional assincrono. A execucao **pausa** em nodos que aguardam resposta do lead (questao, ia_respondedor, ia_agente, delay).

### Funcoes principais

| Funcao | Descricao |
|--------|-----------|
| `buscar_fluxo_por_canal(canal, tenant)` | Busca fluxo ativo por canal (exato → "qualquer" → None) |
| `iniciar_por_canal(lead, canal, tenant)` | Cria atendimento automaticamente por canal |
| `iniciar_fluxo_visual(atendimento)` | Encontra nodo entrada, percorre ate primeira pausa |
| `processar_resposta_visual(atendimento, resposta)` | Valida resposta, salva no lead, segue conexoes |
| `processar_resposta_ia_respondedor(atendimento, resposta)` | Multi-turno do ia_respondedor |
| `processar_resposta_ia_agente(atendimento, resposta)` | Multi-turno do ia_agente com tools |
| `executar_pendentes_atendimento(tenant)` | Cron: executa delays pendentes |
| `_consultar_base_para_fallback(mensagem, atendimento)` | Consulta KB no fallback, registra perguntas sem resposta |

### Traversal do grafo

O engine usa recursao: `_percorrer_a_partir_de(nodo)` → `_executar_nodo(nodo)` → se continua, `_seguir_conexoes(nodo)` → para cada saida, `_percorrer_a_partir_de(destino)`.

**Um nodo "pausa"** retornando um dict (`{tipo, mensagem, questao, ...}`) que sobe pela pilha e e processado pelo signal do Inbox.

**Um nodo "continua"** retornando `None` — o engine segue para os destinos via `_seguir_conexoes`.

### Sistema de branches

Conexoes tem `tipo_saida`:
- **default** — saida padrao (entrada, acao, delay, ia_respondedor, ia_agente, finalizacao)
- **true / false** — saida condicional (questao com IA, condicao, ia_extrator)

Quando a questao tem IA integrada:
- IA sucesso → `branch='true'`
- IA falha → `branch='false'` (geralmente vai pro fallback: ia_agente ou ia_respondedor)

### Validacao de respostas (cascata)

Para nodo `questao`, `_validar_resposta_questao` roda em cascata:

1. **Resposta vazia** — rejeita se espera resposta
2. **Opcoes** — valida contra lista (para selecao)
3. **Tipo** — email (@), telefone (10+ digitos), CPF/CNPJ (11/14), CEP (8), numero
4. **Regex** — valida contra padrao customizado
5. **Integracao IA** (so quando `ia_acao='validar'`) — chama provider com prompt
6. **Webhook** — chama URL externa com resposta + prompt, espera `{valido, mensagem}`

Se valida, salva a resposta e processa IA integrada (`extrair`, `classificar`, `classificar_extrair`).

### Base de Conhecimento nos Fallbacks

Quando `fluxo.base_conhecimento_ativa=True` e uma questao cai no branch `false`:

1. `_consultar_base_para_fallback(resposta, atendimento)` e chamado
2. Extrai termos relevantes (remove stop words e pontuacao)
3. Query em `ArtigoConhecimento` (titulo/tags primeiro, conteudo depois)
4. **Encontrou:** retorna texto formatado → injetado no `contexto._base_conhecimento`
5. **Nao encontrou:** registra `PerguntaSemResposta` com lead e mensagem

O `ia_respondedor` e `ia_agente_inicial` leem `contexto._base_conhecimento` e injetam no system_prompt antes da chamada LLM.

**Dois pontos de consulta:**
- Quando validacao basica falha (linha ~120 em `processar_resposta_visual`)
- Quando IA falha (`ia_sucesso=False`, linha ~180)

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

**`pular_se_preenchido`:** se o campo ja tem valor no lead, pula a questao automaticamente e processa IA com o valor existente.

### Acoes disponiveis

| Acao | Descricao |
|------|-----------|
| criar_oportunidade | Cria oportunidade no CRM (nao duplica, atualiza `dados_custom`) |
| mover_estagio | Move oportunidade do lead para outro estagio |
| criar_tarefa | Cria tarefa no CRM com responsavel |
| webhook | Chama URL externa (GET/POST) com contexto |
| enviar_whatsapp | Envia mensagem WhatsApp adicional |
| enviar_email | Envia email |
| notificacao_sistema | Cria notificacao no painel |

### Tools do ia_agente

O nodo `ia_agente` suporta function calling. Tools registradas no engine:

**Sistema:**
- `atualizar_lead(campo, valor)` — atualiza campo do lead
- `consultar_base_conhecimento(pergunta)` — busca artigos na base + registra pergunta se nao encontrou

**Assistente CRM (disponiveis quando `TOOLS_ASSISTENTE` importado):**
- consultar_lead, listar_oportunidades, mover_oportunidade
- criar_nota, criar_tarefa, atualizar_lead, resumo_pipeline
- listar_tarefas, proxima_tarefa, agendar_followup
- buscar_historico, marcar_perda, marcar_ganho, agenda_do_dia, ver_comandos

Contexto do Assistente CRM (usuario + tenant do vendedor) e recuperado de `atendimento._assistente_usuario` ou de `dados_respostas._assistente_usuario_id`.

### Saida one-shot no ia_agente

Se a LLM retorna JSON `{sair: true, motivo: "..."}`:
- `_executar_ia_agente_inicial` sai do nodo sem pausar
- Segue conexoes de saida
- Permite usar ia_agente como classificador que roteia na primeira mensagem

---

## Integracao com Inbox

O signal `on_mensagem_recebida` em `apps/inbox/signals.py`:

1. Mensagem de contato chega no Inbox (post_save em `Mensagem`)
2. Ignora se `_skip_automacao=True`
3. Verifica se existe atendimento ativo para o lead:
   - **nodo atual = questao/ia_respondedor/ia_agente:** chama handler especifico
   - **Sem atendimento:** `iniciar_por_canal` (prioriza fluxo vinculado ao `CanalInbox.fluxo`)
4. Resultado do engine e enviado:
   - `{tipo: 'questao'}` → `_enviar_mensagens_bot` (ou `_enviar_mensagem_interativa_bot` se tem opcoes)
   - `{tipo: 'ia_respondedor'|'ia_agente'}` → `_enviar_mensagens_bot`
   - `{tipo: 'finalizado'}` → `_enviar_mensagens_bot` + marca `conversa.modo_atendimento='finalizado_bot'`
   - `{tipo: 'transferido'}` → `_enviar_mensagens_bot` + modo_atendimento='humano'
5. `_enviar_mensagens_bot` divide o texto por paragrafos (maximo 3 mensagens) e envia via `_enviar_webhook_async` → provider (Uazapi/Evolution)

---

## Recontato Automatico

Quando o lead para de responder no meio do fluxo, o sistema envia mensagens automaticas para retomar o contato.

### Configuracao (por fluxo)

Cada fluxo tem `recontato_ativo` e `recontato_config` (JSON):
- **tentativas**: lista com `tempo_minutos` e `mensagem` para cada tentativa
- **usar_ia**: se true, gera mensagem com IA baseada no contexto
- **acao_final**: `abandonar` (finaliza) ou `transferir_humano` (envia para fila)

### Campos no AtendimentoFluxo

- `motivo_finalizacao`: completado, sem_resposta, abandonado_usuario, transferido, cancelado_atendente, cancelado_sistema, tempo_limite
- `recontato_tentativas`: contador de tentativas enviadas
- `recontato_proximo_em`: datetime do proximo recontato agendado

### Cron

`python manage.py executar_recontato` — roda a cada 5 minutos. Detecta atendimentos parados (nodo que pausa e sem resposta), envia mensagem, incrementa tentativa, ou finaliza se esgotou.

### Retomada

Quando o lead responde apos recontato, o signal reseta `recontato_tentativas` e retoma o fluxo automaticamente de onde parou.

---

## Assistente CRM (fluxo cross-tenant)

O Assistente CRM reutiliza o engine de fluxo para processar mensagens de vendedores via WhatsApp da Hubtrix.

**Particularidades:**
- `AtendimentoFluxo.lead` e nullable (vendedor nao e lead)
- Dados em `dados_respostas._assistente_usuario_id`, `_tenant_id`, `_conversa_id`
- Fluxo roda no tenant Aurora HQ, mas tools operam no tenant do vendedor
- `_obter_integracao_ia` tem fallback sem filtro de tenant
- `_executar_ia_agente_inicial` injeta dados do vendedor no prompt quando `contexto.assistente_modo=True`

Detalhes em `17-ASSISTENTE_CRM.md`.

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

### Painel de logs no editor (botao "Logs")
- Lista todos os atendimentos do fluxo (lead, status, duracao)
- Click no atendimento → timeline de execucao de cada nodo
- Util para debug de prompts e condicoes

---

## Simulador de teste

Botao "Testar" no toolbar do editor abre um modal chat para testar o fluxo sem precisar do WhatsApp.

- Configura nome e telefone fake
- Envia mensagens e ve resposta do bot em tempo real
- Cria `AtendimentoFluxo` com lead temporario
- API: `POST /api/fluxos/<id>/simular/`

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
| `engine.py` | Engine visual: traversal, IA integrada, fallback com KB, acoes, tools, assistente CRM |
| `views.py` | Editor, salvar fluxo, sessoes, detalhe, fluxo ao vivo, simulador |
| `views_api.py` | APIs N8N dual-mode |
| `apps/inbox/signals.py` | Signal que conecta mensagens do Inbox ao engine + envia resposta do bot |
| `apps/inbox/services.py` | `_enviar_webhook_async` — envio via provider (Uazapi/Evolution) |
| `services/atendimento_service.py` | Integracao Matrix/HubSoft |
