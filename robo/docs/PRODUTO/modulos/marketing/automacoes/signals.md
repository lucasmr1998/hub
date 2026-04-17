# Automacoes — Signals e eventos

Arquivo: `apps/marketing/automacoes/signals.py`

---

## Signals em tempo real

| Signal | Modelo | Evento disparado | Condicao |
|--------|--------|-------------------|----------|
| `on_lead_criado` | LeadProspecto (post_save, created=True) | `lead_criado` | Sempre |
| `on_lead_qualificado` | LeadProspecto (post_save, not created) | `lead_qualificado` | `score_qualificacao >= 7` |
| `on_oportunidade_movida` | OportunidadeVenda (post_save) | `oportunidade_movida` | Sempre |
| `on_docs_validados` | ImagemLeadProspecto (post_save, status=validado) | `docs_validados` | TODOS os docs validados |
| `on_indicacao_convertida` | Indicacao (post_save, status=convertido) | `indicacao_convertida` | Sempre |
| `avaliar_segmentos_dinamicos` | LeadProspecto (post_save) | `lead_entrou_segmento` | Por segmento em que o lead entrou |

---

## Signals do Inbox

O modulo Inbox tambem dispara eventos consumidos pelas automacoes:

- `conversa_aberta` — nova conversa criada
- `mensagem_recebida` — mensagem tipo=contato
- `conversa_resolvida` — conversa marcada como resolvida

Ver [inbox/services.md](../../inbox/services.md#integracao-com-automacoes).

---

## Eventos via Cron

Eventos disparados pelo management command `executar_automacoes_cron` (a cada 5 min):

| Evento | Gatilho |
|--------|---------|
| `lead_sem_contato` | Lead sem `HistoricoContato` ha X dias (X definido na condicao da regra) |
| `tarefa_vencida` | `TarefaCRM` com `data_vencimento < now` e status pendente/em_andamento |
| `disparo_segmento` | Regra com `segmento` FK ativa — dispara para cada lead do segmento |

Ver [endpoints.md](endpoints.md#management-command) para uso do command.

---

## Resumo: quem dispara o que

```
┌─────────────────────────┬──────────────┬────────────────────────────┐
│ Evento                  │ Disparado por│ Quando                     │
├─────────────────────────┼──────────────┼────────────────────────────┤
│ lead_criado             │ Signal       │ Lead salvo (created=True)  │
│ lead_qualificado        │ Signal       │ Lead score >= 7            │
│ oportunidade_movida     │ Signal       │ Oportunidade salva         │
│ docs_validados          │ Signal       │ Todos docs status=validado │
│ indicacao_convertida    │ Signal       │ Indicacao status=convertido│
│ lead_entrou_segmento    │ Signal       │ Lead avaliado em segmento  │
│ mensagem_recebida       │ Signal       │ Mensagem tipo=contato      │
│ conversa_aberta         │ Signal       │ Conversa criada            │
│ conversa_resolvida      │ Signal       │ Conversa status=resolvida  │
├─────────────────────────┼──────────────┼────────────────────────────┤
│ lead_sem_contato        │ Cron (5min)  │ Lead sem HistoricoContato  │
│ tarefa_vencida          │ Cron (5min)  │ TarefaCRM data vencida     │
│ disparo_segmento        │ Cron (5min)  │ Regra com segmento FK      │
├─────────────────────────┼──────────────┼────────────────────────────┤
│ venda_aprovada          │ Signal*      │ *Pendente implementacao    │
│ cliente_aniversario     │ Cron*        │ *Pendente implementacao    │
└─────────────────────────┴──────────────┴────────────────────────────┘
```

\* eventos definidos no model mas signal/cron ainda nao implementado.

---

## Flag de skip

`_skip_automacao=True` em qualquer save pula todos os signals. Util para:

- Operacoes em lote (seed de dados)
- Mensagens do assistente CRM (nao disparam signal do Inbox)
- Evitar loops quando automacao modifica o proprio lead
