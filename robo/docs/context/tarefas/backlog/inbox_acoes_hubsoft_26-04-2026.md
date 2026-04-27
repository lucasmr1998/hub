---
name: "Acoes rapidas HubSoft no Inbox/Atendimento"
description: "Plugar os endpoints REST do HubsoftService (financeiro, operacional) como acoes rapidas dentro do Inbox e do detalhe do cliente, pra atendente resolver sem trocar de tela."
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Acoes rapidas HubSoft no Inbox/Atendimento — 26/04/2026

**Data:** 26/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

Os blocos H3 (financeiro) e H4 (operacional) da paridade HubSoft entregam capacidades novas ao `HubsoftService`. Hoje essas capacidades só são acessíveis via Python/management command. Esta tarefa cobre **plugar essas capacidades como ações rápidas dentro da UI de atendimento** — Inbox, detalhe do cliente, detalhe do lead.

Objetivo: o atendente resolve a maioria dos pedidos do cliente sem trocar de tela pro HubSoft.

Pre-requisito: H3 backend (já entregue, commit `f037982`) + H4 backend (a entregar).

---

## Tarefas

### Financeiro (depende de H3 — já entregue)

- [ ] No detalhe do cliente (HubSoft) e/ou conversa do Inbox, mostrar **lista de faturas em aberto** (chama `listar_faturas_cliente(apenas_pendente=True)`).
  - Cada fatura: vencimento, valor, status, link do PDF, copiar PIX, copiar código de barras.
  - Estado vazio: "Cliente não tem boletos em aberto."
- [ ] Botão **"Gerar 2ª via"** que copia link/PIX/código de barras pro clipboard e oferece envio via canal aberto (WhatsApp/email do Hubtrix, sem usar `enviar_email` do HubSoft).
- [ ] Botão **"Histórico de acordos"** (chama `listar_renegociacoes`) — mostra acordos passados e seus status.
- [ ] Fluxo de **"Simular acordo"**: modal com seleção de faturas em aberto + número de parcelas + data primeira parcela → mostra preview das parcelas geradas (chama `simular_renegociacao`).
- [ ] Fluxo de **"Efetivar acordo"**: confirma o que foi simulado e chama `efetivar_renegociacao`. Permissão exigida (cuidado: cria parcelas e cancela faturas originais).

### Operacional (depende de H4 — a entregar)

- [ ] Botão **"Verificar conexão"** (chama `verificar_extrato_conexao`) — mostra status atual: online/offline, última atividade.
- [ ] Botão **"Liberar acesso (desbloqueio de confiança)"** — usa `desbloqueio_confianca`. Requer confirmação.
- [ ] Botão **"Reset MAC"** — usa `reset_mac_addr`. Confirmação.
- [ ] Botões **"Suspender / Habilitar / Ativar serviço"** — só pra usuários com permissão de operacional.

### Auditoria e LGPD

- [ ] Toda ação executada vira `LogIntegracao` (já garantido pelo `HubsoftService._request`) e `LogAuditoria` no Hubtrix (categoria `integracao`, ação específica).
- [ ] Mostrar no log de atividade do cliente: "Atendente X gerou 2ª via da fatura Y em DD/MM HH:MM".
- [ ] Permissões granulares: `integracao.financeiro.consultar`, `integracao.financeiro.renegociar`, `integracao.operacional.suspender`, etc. (Documentar em `core/03-PERMISSOES.md`.)

---

## Onde plugar

- **Inbox** (`apps/inbox/`): painel lateral da conversa exibe ações HubSoft quando o cliente está identificado por CPF.
- **CRM** (`apps/comercial/crm/`): no detalhe da oportunidade/cliente.
- **Atendimento** (`apps/comercial/atendimento/`): no detalhe do atendimento ativo.

Não duplicar — extrair `templates/integracoes/_acoes_hubsoft.html` reutilizável recebendo o `cliente_hubsoft` ou `lead` no contexto.

---

## Resultado esperado

- Atendente vê faturas em aberto no painel da conversa sem precisar abrir HubSoft.
- Negocia descontos/parcelas direto pelo Hubtrix com auditoria.
- Resolve pendência de conexão (reset MAC, desbloqueio confiança) na própria conversa.
- Métrica esperada: redução de tempo médio de resolução por chamado HubSoft.

---

## Contexto e referências

- Tarefa pai: `paridade_integracao_hubsoft_26-04-2026.md` (blocos H3 + H4)
- Backend H3 já entregue: commit `f037982`
- Backend H4: a entregar
- `HubsoftService`: `apps/integracoes/services/hubsoft.py`
- Doc do módulo: `robo/docs/PRODUTO/integracoes/01-HUBSOFT.md`
