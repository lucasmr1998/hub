# Atendimento — Catalogo de tipos de nodo

Referencia para quem monta ou debuga fluxos. Cada tipo abaixo documenta: **o que faz**, se **pausa** o engine ou continua, **campos aceitos** em `configuracao`, **saidas** possiveis (`tipo_saida` das conexoes) e **variaveis** que deixa no contexto.

Fonte da verdade: [`engine.py::_executar_nodo`](../../../dashboard_comercial/gerenciador_vendas/apps/comercial/atendimento/engine.py#L294).

---

## Tabela-resumo

| Tipo | Pausa? | Saidas tipicas | Uso |
|---|---|---|---|
| `entrada` | Não | `default` | Ponto de inicio. Exige 1 por fluxo |
| `questao` | Sim (se `espera_resposta=true`) | `true` / `false` | Pergunta + validacao. Com IA integrada usa `ia_acao` |
| `condicao` | Não | `true` / `false` | Avalia `campo operador valor` e roteia |
| `acao` | Não | `default` / `erro` | Efeito colateral: cria oportunidade, webhook, etc |
| `delay` | Sim (agendado) | `default` | Pausa o fluxo por X tempo |
| `finalizacao` | Sim (final) | — | Encerra atendimento com status + motivo |
| `transferir_humano` | Sim (final) | — | Manda pra fila do Inbox, finaliza bot |
| `ia_classificador` | Não | Categoria (ex: `curso_valido`) ou `default` | Classifica ultima mensagem |
| `ia_extrator` | Não | `true` / `false` | Extrai dados estruturados da ultima msg |
| `ia_respondedor` | Sim | `default` | Gera resposta conversacional (multi-turno opcional) |
| `ia_agente` | Sim | `default` | Agente com tools customizaveis |

---

## `entrada`

Marca o ponto onde o fluxo comeca. `iniciar_fluxo_visual` procura esse nodo. Passa direto para o proximo.

- **Pausa:** não
- **Saidas:** `default`
- **Config:** nenhuma obrigatoria
- **Exigencia:** exatamente 1 por fluxo com `modo_fluxo=True`

---

## `questao`

Pergunta ao lead e (opcionalmente) espera resposta. Com IA integrada (`ia_acao`), faz validacao/classificacao/extracao antes de rotear.

- **Pausa:** sim, se `espera_resposta=True`; não, se `false` (manda mensagem e continua)
- **Skip:** `pular_se_preenchido=True` faz o engine pular quando `lead.<salvar_em>` ja tem valor
- **Saidas:** sempre `true` (validou/IA ok) ou `false` (validacao falhou; vai pro fallback)

### Campos de configuracao

| Campo | Tipo | Obrigatorio | Descricao |
|---|---|---|---|
| `titulo` | str | sim | Pergunta enviada ao lead |
| `espera_resposta` | bool | sim | Pausa ate receber resposta |
| `salvar_em` | str |  | Campo do lead pra salvar (ex: `nome_razaosocial`, `email`, `cpf_cnpj`) |
| `pular_se_preenchido` | bool |  | Pula se `salvar_em` ja estiver preenchido no lead |
| `validacao` | str |  | `texto`, `email`, `telefone`, `cpf`, `cnpj`, `cep`, `numero`, `opcoes` |
| `opcoes` | list |  | Lista de opcoes aceitas quando `validacao='opcoes'` |
| `regex` | str |  | Regex adicional para validacao custom |
| `max_tentativas` | int |  | Padrao 3 |
| `ia_acao` | str |  | `validar` (default), `classificar`, `extrair`, `classificar_extrair` |
| `integracao_ia_id` | int |  | ID da `IntegracaoAPI` usada pela IA |
| `ia_modelo` | str |  | Ex: `gpt-4o-mini` |
| `prompt_validacao` | str |  | Prompt usado pela IA quando `ia_acao != validar` |
| `ia_categorias` | list |  | Categorias aceitas quando `ia_acao` envolve classificacao (ex: `[curso_valido, curso_invalido]`) |
| `ia_variavel_saida` | str |  | Nome da variavel onde salva a classificacao (ex: `validacao_curso`). Default: `classificacao` |
| `ia_campos_extrair` | list |  | Lista de `{nome, tipo, descricao}` que a IA extrai |
| `ia_salvar_no_lead` | bool |  | Grava campo extraido no lead/oportunidade |

### Variaveis deixadas no contexto

- `resposta_nodo_<id>` — a resposta bruta
- `ultima_resposta` — mesma coisa
- `var.<ia_variavel_saida>` — classificacao (ex: `var.validacao_curso = 'curso_valido'`)
- Campos extraidos: `var.<campo>` (pontos viram underscore: `oport.dados_custom.curso_interesse` vira `var.oport_dados_custom_curso_interesse`)

### Exemplo minimo (questao com classificador)

```json
{
  "titulo": "Qual curso voce tem interesse?",
  "espera_resposta": true,
  "validacao": "texto",
  "ia_acao": "classificar_extrair",
  "integracao_ia_id": 4,
  "ia_modelo": "gpt-4o-mini",
  "ia_categorias": ["curso_valido", "curso_invalido"],
  "ia_variavel_saida": "validacao_curso",
  "prompt_validacao": "Classifique...",
  "ia_campos_extrair": [
    {"nome": "oport.dados_custom.curso_interesse", "tipo": "string", "descricao": "Curso escolhido"}
  ],
  "ia_salvar_no_lead": true
}
```

---

## `condicao` (subtipo `campo_check`)

Avalia uma condicao contra o contexto e roteia. Suporta **condicao simples** (1 campo) ou **composta** (lista + operador logico `and`/`or`).

- **Pausa:** não
- **Saidas:** `true` (condicao verdadeira) / `false` (falsa)

### Campos — modo simples

| Campo | Tipo | Descricao |
|---|---|---|
| `campo` | str | Pode usar dot notation. Ex: `var.validacao_curso`, `lead.nome`, `resposta_nodo_523` |
| `operador` | str | `igual`, `diferente`, `contem`, `nao_contem`, `inicia_com`, `termina_com`, `maior`, `menor`, `maior_igual`, `menor_igual`, `vazio`, `nao_vazio` |
| `valor` | str | Valor de comparacao (ignorado em `vazio`/`nao_vazio`) |

### Campos — modo composto

```json
{
  "operador_logico": "and",
  "condicoes": [
    {"campo": "var.validacao_curso", "operador": "igual", "valor": "curso_valido"},
    {"campo": "lead_score", "operador": "maior_igual", "valor": "7"}
  ]
}
```

### Resolucao de `campo`

Duck typing em `_resolver_campo_contexto`: navega em dot notation usando `.get()`. Funciona pra `dict` e `ContextoLogado`. Se um nivel nao resolve, tenta a chave achatada (`var.X` → `var_X`). Detalhes em [`engine.md`](engine.md#contexto-e-resolucao-de-campos).

---

## `acao`

Efeito colateral. Subtipo define o que faz. Se a acao falhar e houver saida `tipo_saida='erro'`, roteia por la.

- **Pausa:** não
- **Saidas:** `default` (sucesso) ou `erro` (quando falha)

### Subtipos

| Subtipo | Efeito | Config relevante |
|---|---|---|
| `criar_oportunidade` | Cria `OportunidadeVenda` no CRM se ainda nao existir. Preenche `dados_custom` com variaveis `oport_dados_custom_*`. Distribui se sem responsavel | `pipeline_id`, `estagio` (slug), `responsavel_id`, `titulo` |
| `webhook` | Faz POST em URL externa com contexto | `url`, `headers`, `body` (template com variaveis) |
| `enviar_whatsapp` | Dispara mensagem via canal WhatsApp do tenant | `mensagem` (template) |
| `enviar_email` | Dispara email | `para`, `assunto`, `corpo` |
| `notificacao_sistema` | Cria `Notificacao` interna | `tipo_notificacao`, `destinatarios` |
| `criar_tarefa` | Cria tarefa no CRM | `titulo`, `responsavel_id`, `prazo_horas` |
| `mover_estagio` | Move oportunidade pra outro estagio do pipeline | `estagio` (slug) |

Template de `titulo`/`corpo`/`mensagem` aceita `{{lead_nome}}`, `{{oport_dados_custom_curso_interesse}}`, `{{var.X}}`, etc.

---

## `delay`

Pausa o fluxo por um tempo. Registra execucao pendente via `ExecucaoFluxoAtendimento`. Retomada pelo cron `executar_pendentes_atendimento`.

- **Pausa:** sim (agendado)
- **Saidas:** `default`

| Campo | Tipo | Descricao |
|---|---|---|
| `valor` | int | Quantidade |
| `unidade` | str | `segundos`, `minutos`, `horas`, `dias` |

---

## `finalizacao`

Encerra o atendimento.

- **Pausa:** sim (final). Nao tem saidas
- **Efeitos:** seta `status`, `motivo_finalizacao`, `data_conclusao`, `tempo_total`, opcionalmente `score_qualificacao`

| Campo | Tipo | Descricao |
|---|---|---|
| `status` | str | Status final (ex: `completado`, `abandonado`) |
| `motivo_finalizacao` | str | Motivo descritivo |
| `score` | int |  Score opcional (0-100); atualiza tambem `lead.score_qualificacao` |
| `mensagem_final` | str | Mensagem enviada ao lead (aceita variaveis) |

---

## `transferir_humano`

Entrega a conversa pra fila do Inbox. Bot finaliza.

- **Pausa:** sim (final). Atendimento fica com `status='transferido'`
- **Efeitos:** flipa `Conversa.modo_atendimento='humano'`, atribui `fila`/`equipe`, distribui via `distribuir_conversa`

| Campo | Tipo | Descricao |
|---|---|---|
| `fila_id` | int | ID da `FilaInbox`. Sem isso, usa padrao |
| `mensagem` | str | Mensagem enviada ao lead antes de transferir |

---

## `ia_classificador`

Chama LLM pra classificar a ultima mensagem em uma categoria. Nao pausa.

- **Pausa:** não
- **Saidas:** `<nome_da_categoria>` se existir conexao com `tipo_saida=<categoria>`. Senao, `default`

| Campo | Tipo | Descricao |
|---|---|---|
| `integracao_ia_id` | int | `IntegracaoAPI` |
| `modelo` | str | Ex: `gpt-4o-mini` |
| `categorias` | list | Nomes exatos das categorias (case preservado) |
| `prompt` | str | Instrucao base passada como `system` |
| `variavel_saida` | str | Nome da variavel onde grava. Default: `classificacao` |

**Variaveis deixadas:** `var.<variavel_saida>` = categoria escolhida.

**Exemplo:** categorias = `[duvida_valores, duvida_horarios, outro]`, conexao `tipo_saida='duvida_valores'` vai pra nodo especifico, `default` pega o resto.

---

## `ia_extrator`

Extrai campos estruturados da ultima mensagem via LLM.

- **Pausa:** não
- **Saidas:** `true` (extraiu pelo menos 1 campo) / `false` (nada extraido → fallback)

| Campo | Tipo | Descricao |
|---|---|---|
| `integracao_ia_id` | int | `IntegracaoAPI` |
| `modelo` | str |  |
| `prompt` | str | Instrucao base |
| `campos` | list | `[{nome, tipo, descricao}, ...]` |
| `salvar_no_lead` | bool | Grava campos extraidos no lead/oportunidade |

**Variaveis:** cada campo extraido vira `var.<nome_com_underscores>`.

---

## `ia_respondedor`

Gera resposta conversacional com LLM e pausa. Com `continuar_conversa=True`, faz multi-turno ate atingir `max_turnos`, depois segue fluxo.

- **Pausa:** sim
- **Saidas:** `default`

| Campo | Tipo | Descricao |
|---|---|---|
| `integracao_ia_id` | int |  |
| `modelo` | str |  |
| `system_prompt` | str | Prompt principal. Aceita variaveis (`{{lead_nome}}`, `{{var.X}}`) |
| `incluir_historico` | bool | Manda historico anterior. Default: True |
| `max_historico` | int | Limite de mensagens no contexto. Default: 10 |
| `continuar_conversa` | bool | Multi-turno. Default: False (1 resposta e segue) |
| `max_turnos` | int | Limite de idas e vindas. Default: 10 |
| `mensagem_timeout` | str | Usada se LLM nao responde |

**Uso tipico:** fallback de questao (`tipo_saida='false'` do questao aponta pra ia_respondedor) ou etapa conversacional livre.

**Armadilha conhecida (23/04/2026):** se o prompt nao obrigar a IA a terminar com a pergunta original, o candidato pode interpretar a resposta como "fim da conversa" e nao mandar proxima mensagem. Ver `docs/context/tarefas/finalizadas/fix_prompts_fatepi_v3_23-04-2026.md`.

---

## `ia_agente`

Agente IA com **tools customizaveis** (function calling). Pausa. Multi-turno obrigatorio.

- **Pausa:** sim
- **Saidas:** `default`

| Campo | Tipo | Descricao |
|---|---|---|
| `integracao_ia_id` | int |  |
| `modelo` | str |  |
| `system_prompt` | str |  |
| `tools` | list | Lista de tools (formato OpenAI) que o agente pode chamar |
| `max_turnos` | int | Default: 10 |

Tools customizaveis ficam em `ToolCustomizada` (modelo). Exemplo: agente CRM cross-tenant.

---

## Esqueleto minimo de um fluxo visual

```
entrada
  └ default ─> questao (nome, salvar_em=nome_razaosocial)
       ├ true  ─> questao (curso, ia_acao=classificar_extrair)
       │             ├ true  ─> condicao (var.validacao_curso == curso_valido)
       │             │             ├ true  ─> acao (criar_oportunidade)
       │             │             │             └ default ─> questao (forma_ingresso)
       │             │             │                              └ true ─> finalizacao (status=completado, score=80)
       │             │             └ false ─> questao (curso-invalido-retry)
       │             └ false ─> ia_respondedor (fallback curso)
       └ false ─> ia_respondedor (fallback nome)
```

---

## Relacionados

- [engine.md](engine.md) — como o engine percorre o grafo
- [models.md](models.md) — schema das tabelas `FluxoAtendimento`, `NodoFluxoAtendimento`, `ConexaoNodoAtendimento`, `AtendimentoFluxo`
- [simulador.md](simulador.md) — como testar fluxo sem WhatsApp
- [endpoints.md](endpoints.md) — APIs do editor visual
