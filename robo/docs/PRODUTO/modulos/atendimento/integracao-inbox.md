# Atendimento — Integracao com Inbox

O elo entre o Inbox (que recebe mensagens dos canais) e o Engine (que executa fluxos) e o signal `on_mensagem_recebida` em `apps/inbox/signals.py`.

---

## Fluxo do signal

1. Mensagem de contato chega no Inbox (`post_save` em `Mensagem`)
2. Ignora se `_skip_automacao=True`
3. Verifica se existe atendimento ativo para o lead:
   - **nodo atual = questao/ia_respondedor/ia_agente:** chama handler especifico
   - **Sem atendimento:** `iniciar_por_canal` (prioriza fluxo vinculado ao `CanalInbox.fluxo`)
4. Resultado do engine e enviado de acordo com o tipo retornado:
   - `{tipo: 'questao'}` → `_enviar_mensagens_bot` (ou `_enviar_mensagem_interativa_bot` se tem opcoes)
   - `{tipo: 'ia_respondedor'|'ia_agente'}` → `_enviar_mensagens_bot`
   - `{tipo: 'finalizado'}` → `_enviar_mensagens_bot` + marca `conversa.modo_atendimento='finalizado_bot'`
   - `{tipo: 'transferido'}` → `_enviar_mensagens_bot` + `modo_atendimento='humano'`
5. `_enviar_mensagens_bot` divide o texto por paragrafos (maximo 3 mensagens) e envia via `_enviar_webhook_async` → provider (Uazapi/Evolution)

---

## Dispatch por tipo de nodo atual

Quando existe atendimento ativo, o dispatch olha `nodo_atual.tipo`:

| Tipo | Handler |
|------|---------|
| questao | `processar_resposta_visual` |
| ia_respondedor | `processar_resposta_ia_respondedor` |
| ia_agente | `processar_resposta_ia_agente` |

Outros tipos (delay, acao, etc) nao esperam resposta — se mensagem chega enquanto esta num nodo desses, o engine nao reprocessa ate o delay/acao terminar.
