---
name: "Dogfooding: operar o funil comercial interno do Hubtrix com o próprio Hubtrix"
description: "Configurar tenant interno do Hubtrix pra gerenciar leads/oportunidades do proprio negocio B2B"
prioridade: "🟡 Média"
responsavel: "Tech + Comercial"
---

# Dogfooding do funil interno — 17/04/2026

**Data:** 17/04/2026
**Responsável:** Tech + Comercial
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando priorização

---

## Descrição

O Hubtrix vende pra ISPs um sistema que centraliza lead → oportunidade → cliente. Hoje **não usa o próprio produto pra gerenciar os próprios leads B2B** — ISPs que demonstram interesse são atendidos por planilha, WhatsApp pessoal, ou outro CRM.

Isso é uma inconsistência de narrativa ("vendemos o que não usamos") e uma oportunidade perdida de validação contínua do produto.

Surgiu no detalhamento do estágio 1 de A1 em `PRODUTO/VISAO.md`.

---

## Tarefas

- [ ] Criar tenant interno "hubtrix-hq" (se ainda não existe) com plano Pro
- [ ] Configurar módulo Comercial/CRM com pipeline específico pra venda B2B (estágios: MQL → Demo → Proposta → Fechado/Perdido)
- [ ] Configurar Inbox com canal WhatsApp comercial do Hubtrix
- [ ] Criar fluxo de atendimento automatizado pra MQLs (qualifica, agenda demo, transfere pra humano)
- [ ] Integrar formulário "request-a-demo" do site comercial (ver tarefa do site) pra criar Lead automaticamente
- [ ] Migrar leads/oportunidades atuais (se houver em outro sistema/planilha) pro Hubtrix
- [ ] Documentar o próprio fluxo de vendas como case de uso público
- [ ] Usar relatórios internos pra identificar gaps que clientes provavelmente também sentem

---

## Impacto esperado

- Validação contínua do produto pelo time que mais entende dele
- Narrativa coerente ("usamos o que vendemos") em materiais comerciais
- Melhor priorização do roadmap baseada em uso real
- Case de venda pronto: o próprio funil do Hubtrix
