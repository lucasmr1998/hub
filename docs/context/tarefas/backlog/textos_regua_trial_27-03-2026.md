---
name: Textos da Régua de Conversão do Trial
description: Escrever os textos de cada mensagem da régua de trial por canal (WhatsApp, e-mail, notificação)
type: tarefa
status: pendente
criado_em: 27/03/2026
---

## Objetivo

Escrever os textos de todas as mensagens da régua de trial seguindo a estrutura definida em:
`exports/drafts/email/regua_trial_estrutura.md`

## Atividades

### Trilho comum
- [ ] D+0 — E-mail de boas-vindas

### Trilho Ativo
- [ ] D+1 ⚡ — Notificação de celebração (primeiro lead processado)
- [ ] D+3 — E-mail de relatório de uso
- [ ] D+7 — E-mail mostrando funcionalidade não utilizada
- [ ] D+10 — Script WhatsApp para o parceiro
- [ ] D+12 — Script WhatsApp para o parceiro + e-mail de urgência
- [ ] D+14 — E-mail de encerramento + notificação

### Trilho Inativo
- [ ] D+1 — WhatsApp PMM (verificar problema técnico)
- [ ] D+3 — WhatsApp PMM (sessão de ativação assistida)
- [ ] D+5 — WhatsApp PMM (entender o motivo de não uso)
- [ ] D+7 — E-mail + WhatsApp PMM (última tentativa)
- [ ] D+10 — Script WhatsApp para o parceiro

## Responsável

PMM redige todos os textos. Scripts do parceiro (D+10 e D+12) salvos em exports/drafts/scripts_vendas/. Demais mensagens em exports/drafts/whatsapp/ e exports/drafts/email/.

## Dependências

- Estrutura da régua aprovada (exports/drafts/reguas/regua_trial_estrutura.md) ✅
- Definir ferramenta de detecção de uso/não uso para bifurcar os trilhos
