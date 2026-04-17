# Inbox — Services

Arquivo: `apps/inbox/services.py`

---

## Funcoes principais

| Funcao | O que faz |
|--------|-----------|
| `receber_mensagem(telefone, nome, conteudo, tenant, ...)` | Processa mensagem WhatsApp: normaliza telefone, busca/cria conversa, vincula lead, distribui, notifica WS |
| `receber_mensagem_widget(visitor_id, nome, conteudo, tenant, ...)` | Processa mensagem do widget: usa visitor_id em vez de telefone, vincula lead por email/telefone |
| `enviar_mensagem(conversa, conteudo, user, ...)` | Agente envia: cria mensagem, calcula SLA, webhook async, WS notify |
| `atribuir_conversa(conversa, agente, atribuido_por)` | Atribui agente + mensagem de sistema |
| `resolver_conversa(conversa, user)` | Status → resolvida |
| `reabrir_conversa(conversa, user)` | Status → aberta |
| `transferir_conversa(conversa, transferido_por, para_agente/equipe/fila, motivo)` | Transfere + HistoricoTransferencia + redistribui se para equipe/fila |
| `criar_ticket_de_conversa(conversa, titulo, user, categoria)` | Cria Ticket com historico das ultimas 10 mensagens |
| `marcar_mensagens_lidas(conversa)` | Marca todas do contato como lidas + zera badge |
| `atualizar_status_entrega(identificador_externo, status, tenant)` | Atualiza delivery/read de mensagem externa |

---

## Modo de atendimento (bot vs humano)

### Campo `Conversa.modo_atendimento`

| Valor | Descricao |
|-------|-----------|
| `bot` | Fluxo de atendimento ativo. Bot esta respondendo automaticamente |
| `humano` | Conversa transferida para atendente humano (via nodo "Transferir para Humano") |
| `finalizado_bot` | Bot finalizou o fluxo sem transferencia para humano |

### Visibilidade no Inbox

| Perfil | O que ve |
|--------|----------|
| **Admin** (`inbox.ver_todas`) | Tudo. Abas Bot/Humano/Todas para filtrar |
| **Supervisor** (`inbox.ver_equipe`) | Conversas da equipe + nao atribuidas. Exclui bot |
| **Agente** | Suas conversas + nao atribuidas da fila da sua equipe |

### Nodo "Transferir para Humano" (editor de fluxos)

Tipo: `transferir_humano`. Icone: headset laranja. 1 input, 0 outputs.

Configuracao: fila de destino (select) + mensagem de transferencia.

Ao executar: muda `conversa.modo_atendimento` para `humano`, atribui fila/equipe, distribui agente, finaliza o fluxo do bot.

---

## Integracao com automacoes

Arquivo: `apps/inbox/signals.py`

| Signal | Evento disparado |
|--------|------------------|
| `on_conversa_criada` (Conversa created) | `conversa_aberta` |
| `on_mensagem_recebida` (Mensagem created, remetente=contato) | `mensagem_recebida` |
| `on_conversa_resolvida` (Conversa status=resolvida) | `conversa_resolvida` |

Tambem e via `on_mensagem_recebida` que o engine de atendimento e acionado — ver [atendimento/integracao-inbox.md](../atendimento/integracao-inbox.md).
