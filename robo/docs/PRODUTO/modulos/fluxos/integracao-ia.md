# Fluxos — Integracao com IA

A validacao por IA e os nodos IA usam o modulo de integracoes (`apps/integracoes/`). O provedor configura uma integracao do tipo OpenAI, Anthropic, Groq ou Google AI com API key e modelo.

---

## Providers suportados

| Provider | Tipo | Modelo padrao |
|----------|------|---------------|
| OpenAI | openai | gpt-4o-mini |
| Anthropic | anthropic | claude-haiku-4-5-20251001 |
| Groq | groq | llama-3.1-8b-instant |
| Google AI | google_ai | gemini-2.0-flash |

Detalhes completos em [integracoes/02-INTEGRACOES.md](../../integracoes/02-INTEGRACOES.md).

---

## Fallback cross-tenant

`_obter_integracao_ia` busca primeiro no tenant do fluxo; se nao achar, busca sem filtro. Util para o Assistente CRM que roda no tenant Aurora HQ mas pode usar integracao do vendedor. Ver [assistente-crm/](../assistente-crm/).

---

## Base de Conhecimento nos Fallbacks

Quando `FluxoAtendimento.base_conhecimento_ativa = True`, o engine enriquece automaticamente os fallbacks de questoes com artigos da base.

### Como funciona

1. Lead responde algo que nao passa na validacao ou extracao IA
2. Engine chama `_consultar_base_para_fallback(mensagem, atendimento)` antes de seguir o branch `false`
3. Funcao faz query por texto em `ArtigoConhecimento` (titulo/tags/conteudo)
4. **Encontrou artigos:** injeta no contexto como `_base_conhecimento`. O `ia_respondedor` ou `ia_agente` recebe esse texto no system_prompt e usa para responder
5. **Nao encontrou:** registra `PerguntaSemResposta` para o cliente criar artigo depois

### Custo

Zero chamadas LLM extras (so query SQL). O ia_respondedor que ja executaria recebe o contexto melhorado.

### Escalavel

Funciona para qualquer fluxo de qualquer cliente. Basta ligar o toggle no editor (botao **Base Conhecimento** no toolbar).

---

## Tools customizadas

O nodo `ia_agente` aceita tools customizadas do tenant alem das tools padrao. Tools sao configuradas em `ToolCustomizada` com:

- Nome da funcao
- Schema JSON dos parametros
- URL do webhook que recebe a chamada
- Filtro por fluxo ou global ao tenant

O engine valida o schema antes de passar para a LLM e executa via chamada HTTP sincrona (timeout 30s).
