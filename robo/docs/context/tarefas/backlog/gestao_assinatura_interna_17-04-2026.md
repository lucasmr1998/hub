---
name: "Módulo de gestão de assinatura interna (upgrade, downgrade, pagamento, suspensão)"
description: "Permitir que o proprio Hubtrix gerencie a assinatura dos seus clientes (ISPs) sem dependencia de ferramentas externas"
prioridade: "🟡 Média"
responsavel: "Tech + Financeiro"
---

# Gestão de assinatura interna — 17/04/2026

**Data:** 17/04/2026
**Responsável:** Tech + Financeiro
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando priorização

---

## Descrição

Hoje a gestão de assinatura dos clientes Hubtrix (quem tá ativo, quem pagou, quem tá inadimplente, quem quer upgrade) acontece fora do próprio Hubtrix — provavelmente planilha + gateway externo (Stripe / ASAAS / outro). Conforme o número de tenants cresce, isso vira gargalo operacional e risco financeiro.

Vira **módulo próprio dentro do Hubtrix** em algum momento. Precisa definir quando — antes ou depois de atingir X tenants pagantes?

Surgiu no detalhamento do estágio 3 de A1 (Contratação — Fechamento) em `PRODUTO/VISAO.md`.

---

## Tarefas

- [ ] Decidir escopo inicial (MVP vs completo): cobrança + inadimplência é suficiente? ou precisa upgrade/downgrade self-service já no v1?
- [ ] Escolher gateway integrado (Stripe, ASAAS, Pagar.me, Gerencianet, IUGU)
- [ ] Modelo `Assinatura` no admin_aurora (tenant, plano, ciclo, valor, status, data_proxima_cobranca)
- [ ] Integração com gateway (webhook pagamento confirmado, pagamento falhou, cancelamento)
- [ ] Painel do cliente Hubtrix ("meu plano", "minha fatura", "minhas assinaturas")
- [ ] Regras de suspensão automática por inadimplência (grace period, suspensão, cancelamento)
- [ ] Upgrade/downgrade de plano self-service
- [ ] Relatório financeiro MRR / churn mensal / LTV no aurora-admin
- [ ] Notas fiscais automáticas (se aplicável para SaaS no BR)

---

## Impacto esperado

- Operação financeira escalável (suporta 50+ tenants sem gargalo)
- Redução de dependência de ferramentas externas
- Cliente Hubtrix tem controle da própria assinatura (reduz tickets "quanto pagamos?")
- Dados financeiros consolidados pro CFO (MRR, churn, LTV)

---

## Decisão pendente

**Quando começar?** Trade-off:
- Começar cedo: desperdício enquanto tenants < 10 (planilha resolve)
- Começar tarde: quando já tá complicado, vira projeto urgente
- **Proposta:** começar quando chegar a 10-15 tenants pagantes ou 6 meses, o que vier primeiro
