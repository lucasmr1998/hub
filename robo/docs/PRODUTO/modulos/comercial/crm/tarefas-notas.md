# CRM — Tarefas e Notas

## TarefaCRM

**Tabela:** `crm_tarefas`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `oportunidade` / `lead` | FK | Vinculado a oportunidade ou lead |
| `responsavel` | FK User | Quem deve executar |
| `tipo` | CharField | ligacao / whatsapp / email / visita / followup / proposta / instalacao / suporte / outro |
| `titulo` / `descricao` | Char / Text | Descricao |
| `status` | CharField | pendente / em_andamento / concluida / cancelada / vencida |
| `prioridade` | CharField | baixa / normal / alta / urgente |
| `data_vencimento` | DateTime | Prazo |
| `lembrete_em` | DateTime | Lembrete automatico |

`save()` auto-marca como `vencida` se prazo venceu.

---

## NotaInterna

**Tabela:** `crm_notas_internas`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `oportunidade` / `lead` | FK | Contexto |
| `autor` | FK User | Quem escreveu |
| `mencoes` | M2M User | Mencoes (@usuario) |
| `conteudo` | TextField | Texto |
| `tipo` | CharField | geral / reuniao / ligacao / email / importante / alerta |
| `is_fixada` | BooleanField | Fixada no topo |

---

## Telas

- `tarefas_lista.html` — tarefas agrupadas em tabs (hoje / semana / vencidas / concluidas)
- `oportunidade_detalhe.html` — notas e tarefas na lateral do detalhe da oportunidade
