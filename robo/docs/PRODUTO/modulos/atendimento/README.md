# Atendimento

**Status:** Em producao
**App:** `apps/comercial/atendimento/`

Engine de atendimento — executa os fluxos conversacionais desenhados no modulo [Fluxos](../fluxos/). Este modulo cuida do **runtime**: sessoes ativas com leads, validacao de respostas, logs, integracao com Inbox/WhatsApp, recontato automatico.

Para a **configuracao** dos fluxos (editor visual, tipos de nodos) ver [Fluxos](../fluxos/).

---

## Indice

| Arquivo | Conteudo |
|---------|----------|
| [models.md](models.md) | AtendimentoFluxo, LogFluxoAtendimento, ExecucaoFluxoAtendimento + tabelas |
| [engine.md](engine.md) | Engine (traversal, branches, validacao cascata, KB fallbacks, acoes, tools IA) |
| [tipos-de-nodo.md](tipos-de-nodo.md) | Catalogo completo: cada tipo de nodo, campos aceitos, saidas, exemplo |
| [exemplo-fluxo-ia.md](exemplo-fluxo-ia.md) | Fluxo real comentado (FATEPI v3): 3 jornadas, estado a cada passo, como debugar |
| [integracao-inbox.md](integracao-inbox.md) | Signal do Inbox que dispara o engine |
| [recontato-automatico.md](recontato-automatico.md) | Cron de reengajamento, config e retomada |
| [sessoes.md](sessoes.md) | Telas: lista, detalhe, fluxo ao vivo, logs no editor |
| [simulador.md](simulador.md) | Simulador de teste de fluxo |
| [endpoints.md](endpoints.md) | Paginas e APIs |

---

## Contexto

O engine suporta dois modos de execucao:

- **Legado:** QuestaoFluxo sequencial (questao por indice)
- **Visual:** Engine node-based com traversal do grafo (`engine.py`)

O Assistente CRM (cross-tenant, ver [assistente-crm/](../assistente-crm/)) reutiliza este mesmo engine com particularidades documentadas la.

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

## Arquivos do app

| Arquivo | Descricao |
|---------|-----------|
| `models.py` | Todos os models (legado + visual) |
| `engine.py` | Engine visual: traversal, IA integrada, fallback com KB, acoes, tools, assistente CRM |
| `views.py` | Editor, salvar fluxo, sessoes, detalhe, fluxo ao vivo, simulador |
| `views_api.py` | APIs N8N dual-mode |
| `apps/inbox/signals.py` | Signal que conecta mensagens do Inbox ao engine + envia resposta do bot |
| `apps/inbox/services.py` | `_enviar_webhook_async` — envio via provider (Uazapi/Evolution) |
| `services/atendimento_service.py` | Integracao Matrix/HubSoft |
