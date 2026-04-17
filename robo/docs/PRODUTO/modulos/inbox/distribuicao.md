# Inbox — Engine de Distribuicao

Arquivo: `apps/inbox/distribution.py`

Decide em qual fila a conversa entra e qual agente recebe.

---

## Funcoes

| Funcao | O que faz |
|--------|-----------|
| `verificar_horario_atendimento(tenant)` | Checa `HorarioAtendimento` global (fila=None) para dia/hora atual |
| `verificar_horario_fila(fila)` | Checa horarios especificos da fila. Sem registros = sempre aberta |
| `determinar_fila(conversa, tenant)` | Itera `RegraRoteamento` por prioridade. Match por canal, etiqueta ou horario |
| `selecionar_agente(fila, tenant)` | Round-robin ou menor carga. Verifica `status=online` e capacidade |
| `distribuir_conversa(conversa, tenant)` | Orquestrador: fila, horario, agente, mensagem de sistema. Fora do horario envia mensagem automatica |

---

## Horarios por fila

Cada fila pode ter seus proprios horarios de atendimento (`HorarioAtendimento.fila`).

- Se a fila **nao tem** horarios → esta sempre aberta
- Se a fila **tem** horarios e esta fora do horario → envia `fila.mensagem_fora_horario` e coloca conversa como `pendente`

---

## Modos de distribuicao da fila

Configurado em `FilaInbox.modo_distribuicao`:

- **round-robin:** distribui em rotacao entre agentes online
- **menor carga:** escolhe agente com menos conversas ativas
- **manual:** nao atribui automaticamente, agente precisa pegar

Em todos os modos, o agente precisa estar com `PerfilAgenteInbox.status='online'` e abaixo da `capacidade_maxima`.

---

## Integracao

Chamado automaticamente em:

- `receber_mensagem()` — quando nova conversa e criada via WhatsApp
- `receber_mensagem_widget()` — nova conversa via widget
- `transferir_conversa()` — redistribui quando transfere para equipe/fila
- Nodo `transferir_humano` do engine de fluxos
