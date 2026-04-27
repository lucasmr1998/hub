---
name: "Textos das réguas (trial + recuperação) — jornada completa do lead Hubtrix"
description: "Escrever todos os textos das mensagens de cada régua: conversão de trial (D+0 a D+14) e recuperação pós-trial (D+1 a D+30). Por canal e por segmento."
prioridade: "🟡 Média"
responsavel: "PMM"
type: tarefa
status: pendente
criado_em: 27/03/2026
atualizado_em: 26/04/2026
---

# Textos das réguas — jornada completa

**Responsável:** PMM
**Prioridade:** 🟡 Média
**Status:** ⏳ Pendente

---

## Objetivo

Escrever todos os textos das mensagens automáticas que compõem as réguas do funil Hubtrix, do início do trial até a recuperação pós-trial. Estruturas das réguas já aprovadas em:

- `exports/drafts/email/regua_trial_estrutura.md` ✅
- `exports/drafts/email/regua_recuperacao_pos_trial_estrutura.md` ✅

Esta tarefa unifica duas anteriores (consolidadas em 26/04/2026) por compartilharem responsável, canais, e por serem a mesma jornada vista em momentos diferentes.

---

## RÉGUA 1 — Conversão durante o trial

### Trilho comum
- [ ] D+0 — E-mail de boas-vindas

### Trilho **Ativo** (cliente está usando o trial)
- [ ] D+1 ⚡ — Notificação de celebração (primeiro lead processado)
- [ ] D+3 — E-mail de relatório de uso
- [ ] D+7 — E-mail mostrando funcionalidade não utilizada
- [ ] D+10 — Script WhatsApp para o parceiro
- [ ] D+12 — Script WhatsApp para o parceiro + e-mail de urgência
- [ ] D+14 — E-mail de encerramento + notificação

### Trilho **Inativo** (cliente assinou trial mas não está usando)
- [ ] D+1 — WhatsApp PMM (verificar problema técnico)
- [ ] D+3 — WhatsApp PMM (sessão de ativação assistida)
- [ ] D+5 — WhatsApp PMM (entender o motivo do não uso)
- [ ] D+7 — E-mail + WhatsApp PMM (última tentativa)
- [ ] D+10 — Script WhatsApp para o parceiro

**Dependência:** definir ferramenta de detecção de uso/não uso pra bifurcar os trilhos.

---

## RÉGUA 2 — Recuperação pós-trial

### Segmento: **Usou o trial** (engajou mas não converteu)
- [ ] D+1 — WhatsApp PMM (entender o que travou)
- [ ] D+7 — WhatsApp PMM + e-mail (oferta: 1 mês com 30% de desconto)
- [ ] D+15 — E-mail + WhatsApp PMM (oferta: setup gratuito)
- [ ] D+22 — WhatsApp parceiro + e-mail (oferta: setup grátis + 50% de desconto)
- [ ] D+30 — WhatsApp parceiro + e-mail (oferta: primeiro mês grátis. Última tentativa.)

### Segmento: **Não usou o trial**
- [ ] D+1 — WhatsApp PMM (entender o que aconteceu)
- [ ] D+7 — WhatsApp PMM + e-mail (oferta: extensão do trial por 7 dias)
- [ ] D+15 — E-mail + WhatsApp PMM (oferta: 1 mês com 30% de desconto)
- [ ] D+22 — WhatsApp parceiro + e-mail (oferta: setup gratuito)
- [ ] D+30 — WhatsApp parceiro + e-mail (oferta: primeiro mês grátis. Última tentativa.)

---

## Onde salvar os textos

- **Scripts do parceiro:** `exports/drafts/scripts_vendas/`
- **Mensagens WhatsApp:** `exports/drafts/whatsapp/`
- **E-mails:** `exports/drafts/email/`

---

## Responsável

PMM redige todos os textos. Aplicar diretrizes do brandbook ([BRAND/08-BRANDBOOK.md](../../BRAND/08-BRANDBOOK.md)) — tom direto, sem superlativo vazio, prova antes de promessa, sem traço como pontuação.

---

## Histórico

- **27/03/2026:** duas tarefas separadas criadas (textos_regua_trial + textos_regua_recuperacao)
- **26/04/2026:** consolidadas nesta — mesmo responsável, mesma natureza, mesma jornada do mesmo lead
