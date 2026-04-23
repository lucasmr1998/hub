# Atendimento — Engine

Engine conversacional assincrono (`engine.py`). A execucao **pausa** em nodos que aguardam resposta do lead (questao, ia_respondedor, ia_agente, delay).

---

## Funcoes principais

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

---

## Traversal do grafo

O engine usa recursao: `_percorrer_a_partir_de(nodo)` → `_executar_nodo(nodo)` → se continua, `_seguir_conexoes(nodo)` → para cada saida, `_percorrer_a_partir_de(destino)`.

**Um nodo "pausa"** retornando um dict (`{tipo, mensagem, questao, ...}`) que sobe pela pilha e e processado pelo signal do Inbox.

**Um nodo "continua"** retornando `None` — o engine segue para os destinos via `_seguir_conexoes`.

---

## Sistema de branches

Conexoes tem `tipo_saida`:

- **default** — saida padrao (entrada, acao, delay, ia_respondedor, ia_agente, finalizacao)
- **true / false** — saida condicional (questao com IA, condicao, ia_extrator)
- **erro** — saida quando nodo falha (acao, ia_*)
- **categoria_*** — saida por categoria (ia_classificador)

Quando a questao tem IA integrada:

- IA sucesso → `branch='true'`
- IA falha → `branch='false'` (geralmente vai pro fallback: ia_agente ou ia_respondedor)

---

## Contexto e resolucao de campos

O engine monta o contexto via `_construir_contexto(atendimento)` e o envolve em `ContextoLogado` (dict wrapper que grava cada mutacao pra debug). O contexto contem:

- `lead`, `lead_id`, `lead_nome`, `lead_telefone`, ... (campos do Lead)
- `var` — dict com variaveis salvas por ia_classificador / ia_extrator (ex: `var.validacao_curso`, `var.tipo_fallback`)
- Variaveis IA tambem ficam no nivel raiz pra compat (`validacao_curso`, `tipo_fallback`)
- `resposta_nodo_<id>` — respostas anteriores do atendimento
- `ultima_resposta`, `_ultima_mensagem` — convenience

### Dot notation em condicoes

Nodos `condicao` (campo_check) usam `_resolver_campo_contexto(campo, contexto)` pra navegar em dot notation: `var.validacao_curso`, `lead.nome`, etc.

**Importante:** `_resolver_campo_contexto` usa **duck typing** (`hasattr(obj, 'get')`) pra decidir se um nivel eh um mapping. Isso aceita `dict` puro E `ContextoLogado` (MutableMapping). Versao antiga usava `isinstance(obj, dict)` e quebrou silenciosamente toda condicao `var.X` no dia que ContextoLogado foi introduzido — veja `tests/test_engine_nodos.py::TestResolverCampoContexto` pra regressao.

Fallback: se o caminho nao resolve, tenta `contexto.get('var_validacao_curso')` (chave flat com underscore).

---

## Validacao de respostas (cascata)

Para nodo `questao`, `_validar_resposta_questao` roda em cascata:

1. **Resposta vazia** — rejeita se espera resposta
2. **Opcoes** — valida contra lista (para selecao)
3. **Tipo** — email (@), telefone (10+ digitos), CPF/CNPJ (11/14), CEP (8), numero
4. **Regex** — valida contra padrao customizado
5. **Integracao IA** (so quando `ia_acao='validar'`) — chama provider com prompt
6. **Webhook** — chama URL externa com resposta + prompt, espera `{valido, mensagem}`

Se valida, salva a resposta e processa IA integrada (`extrair`, `classificar`, `classificar_extrair`).

---

## Base de Conhecimento nos Fallbacks

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

---

## Salvar resposta no lead

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

---

## Acoes disponiveis

O nodo `acao` suporta as seguintes acoes:

| Acao | Descricao |
|------|-----------|
| criar_oportunidade | Cria oportunidade no CRM (nao duplica, atualiza `dados_custom`) |
| mover_estagio | Move oportunidade do lead para outro estagio |
| criar_tarefa | Cria tarefa no CRM com responsavel |
| webhook | Chama URL externa (GET/POST) com contexto |
| enviar_whatsapp | Envia mensagem WhatsApp adicional |
| enviar_email | Envia email |
| notificacao_sistema | Cria notificacao no painel |

---

## Tools do ia_agente

O nodo `ia_agente` suporta function calling. Tools registradas no engine:

**Sistema:**

- `atualizar_lead(campo, valor)` — atualiza campo do lead
- `consultar_base_conhecimento(pergunta)` — busca artigos na base + registra pergunta se nao encontrou

**Assistente CRM** (disponiveis quando `TOOLS_ASSISTENTE` importado — ver [assistente-crm/tools.md](../assistente-crm/tools.md)):

- consultar_lead, listar_oportunidades, mover_oportunidade
- criar_nota, criar_tarefa, atualizar_lead, resumo_pipeline
- listar_tarefas, proxima_tarefa, agendar_followup
- buscar_historico, marcar_perda, marcar_ganho, agenda_do_dia, ver_comandos

Contexto do Assistente CRM (usuario + tenant do vendedor) e recuperado de `atendimento._assistente_usuario` ou de `dados_respostas._assistente_usuario_id`.

---

## Saida one-shot no ia_agente

Se a LLM retorna JSON `{sair: true, motivo: "..."}`:

- `_executar_ia_agente_inicial` sai do nodo sem pausar
- Segue conexoes de saida
- Permite usar ia_agente como classificador que roteia na primeira mensagem
