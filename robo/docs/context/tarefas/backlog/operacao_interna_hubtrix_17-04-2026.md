---
name: "Operação interna do Hubtrix (health, NPS, self-service, offboarding, assinatura, dogfooding)"
description: "Capacidades admin-side pro time Hubtrix operar sua base de tenants. Inclui health score, NPS de tenants, self-service de upgrade, offboarding LGPD, gestão de assinatura interna e dogfooding do funil B2B."
prioridade: "🟡 Média"
responsavel: "Tech + PM + CS + Financeiro Hubtrix"
---

# Operação interna do Hubtrix — 17/04/2026

**Data:** 17/04/2026
**Última atualização:** 26/04/2026 (consolidação)
**Responsável:** Tech + PM + CS + Financeiro Hubtrix
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando priorização

---

## Descrição

A administração interna do próprio Hubtrix é imatura. Time Hubtrix hoje não tem ferramentas pra operar sua base de tenants com método. Esta tarefa unifica **6 lacunas** do mesmo domínio (consolidação 26/04/2026):

1. **Health score automatizado de tenants**
2. **NPS dos tenants**
3. **Self-service de upgrade de plano**
4. **Offboarding formalizado**
5. **Gestão de assinatura interna** (cobrança, inadimplência, ciclo)
6. **Dogfooding do funil B2B** (Hubtrix usa Hubtrix pra vender Hubtrix)

Surgiu no detalhamento dos estágios 1, 3, 9-10 de A1 em `PRODUTO/VISAO.md`.

---

## 1. Health score automatizado de tenants

Dashboard interno (`aurora-admin`) com **saúde de cada tenant** via score composto:

- Uso diário (DAU/MAU)
- Tickets abertos
- Integrações quebradas (Uazapi / IA / ERP)
- NPS pendente ou baixo
- Atividade dos módulos contratados
- Tempo desde último login do admin

Cada fator com peso. Score 0-100 por tenant. Lista ordenada por risco.

### Tarefas

- [ ] Definir fórmula do health score (fatores, pesos)
- [ ] Model `HealthScoreTenant` atualizado por cron diário
- [ ] Dashboard `/aurora-admin/health/` com lista ordenada
- [ ] Alerta quando tenant cai abaixo de threshold (ex: < 40)
- [ ] Histórico de score (gráfico de evolução)

---

## 2. NPS dos tenants

O Hubtrix não pergunta aos seus clientes o que acham do produto. Feedback é acidental.

### Tarefas

- [ ] Model `NPSHubtrix` (tenant, usuário, nota, comentário, data)
- [ ] Cron mensal disparando pesquisa ao admin principal
- [ ] Envio via e-mail ou notificação no painel
- [ ] Dashboard `/aurora-admin/nps/` com média por período e por plano
- [ ] Auto-categorização (promotor / neutro / detrator)
- [ ] Alerta quando detrator ou comentário crítico

---

## 3. Self-service de upgrade de plano

ISP que quer mais módulos/seats/canal hoje precisa falar com alguém. Self-service remove o atrito.

### Tarefas

- [ ] Página `/configuracoes/plano/` dentro do tenant
- [ ] Comparação de planos com CTA "fazer upgrade"
- [ ] Integração com gateway (depende da seção 5)
- [ ] Aplicar mudança de plano imediata após confirmação do pagamento
- [ ] Upsell proativo: quando uso se aproxima do limite, banner

---

## 4. Offboarding formalizado (LGPD)

Quando tenant cancela, hoje não há processo. Precisa formalizar.

### Tarefas

- [ ] Fluxo de cancelamento pelo admin do tenant (motivo categorizado)
- [ ] Export LGPD-compliant dos dados do tenant (JSON + anexos)
- [ ] Retenção legal de documentos que por lei não podem ser apagados
- [ ] Anonimização de dados não retidos
- [ ] Deleção programada após período legal
- [ ] Documentação do que é mantido e por quanto tempo

---

## 5. Gestão de assinatura interna (absorvido de `gestao_assinatura_interna`)

Hoje a gestão de assinatura dos clientes Hubtrix (ativo, pago, inadimplente, upgrade) acontece **fora** do Hubtrix — provavelmente planilha + gateway externo. Conforme cresce, vira gargalo + risco financeiro.

### Tarefas

- [ ] Decidir escopo MVP vs completo: cobrança + inadimplência basta v1, ou já self-service?
- [ ] Escolher gateway (Stripe / ASAAS / Pagar.me / Gerencianet / IUGU)
- [ ] Model `Assinatura` no `admin_aurora` (tenant, plano, ciclo, valor, status, data_proxima_cobranca)
- [ ] Webhooks (pago, falhou, cancelado)
- [ ] Painel "meu plano / minha fatura" pro cliente
- [ ] Suspensão automática por inadimplência (grace period → suspensão → cancelamento)
- [ ] Upgrade/downgrade self-service (conecta com seção 3)
- [ ] Relatório financeiro MRR / churn / LTV no aurora-admin
- [ ] Notas fiscais automáticas (se aplicável)

### Decisão pendente

**Quando começar?**
- Cedo: desperdício enquanto < 10 tenants
- Tarde: vira projeto urgente sob pressão
- **Proposta:** começar quando atingir 10-15 tenants pagantes ou em 6 meses, o que vier primeiro

---

## 6. Dogfooding do funil B2B (absorvido de `dogfooding_funil_interno`)

O Hubtrix vende um sistema que centraliza lead → oportunidade → cliente, mas **não usa o próprio produto** pra gerenciar leads B2B. ISPs que demonstram interesse caem em planilha / WhatsApp pessoal / outro CRM. É inconsistência de narrativa ("vendemos o que não usamos") + oportunidade perdida de validação.

### Tarefas

- [ ] Criar tenant interno `hubtrix-hq` (se ainda não existe) com plano Pro
- [ ] Configurar Comercial/CRM com pipeline B2B (MQL → Demo → Proposta → Fechado/Perdido)
- [ ] Configurar Inbox com canal WhatsApp comercial do Hubtrix
- [ ] Fluxo de atendimento automatizado pra MQLs (qualifica, agenda demo, transfere)
- [ ] Integrar form "request-a-demo" do site comercial (cria Lead automaticamente)
- [ ] Migrar leads/oportunidades atuais (planilha) pro Hubtrix
- [ ] Documentar o próprio fluxo como case público
- [ ] Usar relatórios internos pra identificar gaps que clientes também sentem

---

## Impacto esperado

- Time Hubtrix opera a base com método (antecipação de churn, priorização)
- NPS sistemático = fonte de dados reais pro roadmap
- Self-service + assinatura = growth orgânico, sem gargalo financeiro
- Offboarding LGPD-compliant = risco legal/reputacional reduzido
- Dogfooding = validação contínua + narrativa coerente

---

## Priorização sugerida (dentro do projeto)

1. **Health score** (urgência — perder tenant sem saber)
2. **NPS interno** (baixa complexidade, alto valor)
3. **Gestão de assinatura** (gargalo eminente conforme cresce)
4. **Self-service upgrade** (depende da #3)
5. **Dogfooding** (longo prazo, precisa de tenant config)
6. **Offboarding** (importante p/ LGPD, baixa urgência até churn real)

---

## Histórico

- **17/04/2026:** 3 tarefas separadas (operacao_interna_hubtrix, gestao_assinatura_interna, dogfooding_funil_interno)
- **26/04/2026:** consolidadas nesta única — todas tratam de "Hubtrix operando o Hubtrix"
