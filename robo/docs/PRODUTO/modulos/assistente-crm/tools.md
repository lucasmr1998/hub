# Assistente CRM — Tools

15 tools disponiveis no nodo `ia_agente` do fluxo do assistente. Cada tool recebe `(tenant, usuario, args)` e retorna string. Todas filtram por tenant do vendedor.

Registradas em `apps/assistente/tools.py` no dict `TOOLS_ASSISTENTE`.

---

## Consulta

| Tool | Funcao |
|------|--------|
| `consultar_lead` | Busca lead por nome/telefone |
| `listar_oportunidades` | Lista oportunidades (filtro por estagio) |
| `resumo_pipeline` | Metricas do pipeline |
| `listar_tarefas` | Lista tarefas pendentes |
| `proxima_tarefa` | Proxima tarefa a vencer |
| `agenda_do_dia` | Tarefas e followups do dia |
| `buscar_historico` | Historico de interacoes do lead |
| `ver_comandos` | Lista de comandos disponiveis |

---

## Acoes

| Tool | Funcao |
|------|--------|
| `mover_oportunidade` | Move oportunidade para outro estagio |
| `marcar_perda` | Marca oportunidade como perdida |
| `marcar_ganho` | Marca oportunidade como ganha |
| `criar_nota` | Cria nota no lead |
| `criar_tarefa` | Cria tarefa com vencimento |
| `atualizar_lead` | Atualiza campo do lead |
| `agendar_followup` | Agenda followup (nota + tarefa em conjunto) |

---

## Habilitacao no fluxo

No editor visual, dentro do nodo `ia_agente`, cada tool aparece como um checkbox com prefixo `[CRM]`. Marcando o checkbox, o engine inclui a tool na chamada LLM. O schema JSON (parametros esperados) e construido automaticamente a partir de `TOOLS_ASSISTENTE`.

---

## Auditoria

Toda chamada de tool gera entrada em `LogSistema` com:

- `categoria='assistente'`
- `acao=<nome_da_tool>`
- `usuario=<vendedor>`
- `dados=<args + resultado>`

Permite rastrear quem fez o que pelo assistente.

---

## Extensao futura

A fase 5 preve adicionar tools de Inbox, Suporte e Marketing para que o assistente cubra todas as areas operacionais. Cada nova tool segue o mesmo padrao: funcao Python + schema em `TOOLS_ASSISTENTE`, automaticamente disponivel no checkbox do editor.
