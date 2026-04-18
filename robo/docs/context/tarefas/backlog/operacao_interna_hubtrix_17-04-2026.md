---
name: "Operação interna do Hubtrix (health score de tenants + NPS + self-service + offboarding)"
description: "Conjunto de capacidades admin-side pro time Hubtrix operar a propria base de clientes (ISPs) com maturidade"
prioridade: "🟡 Média"
responsavel: "Tech + PM + CS Hubtrix"
---

# Operação interna do Hubtrix — 17/04/2026

**Data:** 17/04/2026
**Responsável:** Tech + PM + CS Hubtrix
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando priorização

---

## Descrição

Assim como Contratação (estágios 1-3 de A1), a Evolução (estágios 9-10) revelou que a **administração interna do próprio Hubtrix** é imatura. O time Hubtrix hoje não tem ferramentas pra operar sua base de tenants com método.

Juntei 4 lacunas num projeto único porque são do mesmo domínio e provavelmente têm sobreposições de implementação:

1. **Health score automatizado de tenants**
2. **NPS dos tenants** (pesquisa do Hubtrix com os ISPs)
3. **Self-service de upgrade de plano** (remove atrito de expansão)
4. **Offboarding formalizado** (quando tenant cancela)

Surgiu no detalhamento dos estágios 9-10 de A1 em `PRODUTO/VISAO.md`.

---

## 1. Health score automatizado de tenants

Dashboard interno (visível só para operadores `aurora-admin`) mostrando a **saúde de cada tenant** com score composto:

- Uso diário (DAU/MAU) — tenant está ativo?
- Tickets abertos — tem problema não resolvido?
- Integrações quebradas — Uazapi / IA / ERP com erro?
- NPS pendente ou baixo
- Atividade dos módulos contratados
- Tempo desde último login do admin

Cada fator com peso. Score 0-100 por tenant. Listagem ordenada por risco (maior risco primeiro).

### Tarefas

- [ ] Definir fórmula do health score (quais fatores, pesos)
- [ ] Model `HealthScoreTenant` atualizado por cron diário
- [ ] Dashboard `/aurora-admin/health/` com lista ordenada
- [ ] Alerta automático quando tenant cai abaixo de threshold (ex: score < 40)
- [ ] Histórico de score (gráfico de evolução por tenant)

---

## 2. NPS dos tenants

O Hubtrix não pergunta aos seus clientes o que eles acham do produto. Feedback é acidental.

### Tarefas

- [ ] Model `NPSHubtrix` (tenant, usuário, nota, comentário, data)
- [ ] Cron mensal que dispara pesquisa ao admin principal de cada tenant
- [ ] Envio via e-mail ou notificação no painel
- [ ] Dashboard `/aurora-admin/nps/` com média por período e por plano
- [ ] Auto-categorização (promotor / neutro / detrator)
- [ ] Alerta automático quando detrator ou comentário crítico

---

## 3. Self-service de upgrade de plano

Remover atrito de expansão. ISP que quer mais módulos/seats/canal hoje precisa falar com alguém. Self-service resolve.

### Tarefas

- [ ] Página `/configuracoes/plano/` dentro do tenant, mostra plano atual + opções
- [ ] Comparação de planos com CTA "fazer upgrade"
- [ ] Integração com gateway (depende de [gestao_assinatura_interna](./gestao_assinatura_interna_17-04-2026.md))
- [ ] Aplicar mudança de plano imediata após confirmação do pagamento
- [ ] Upsell proativo: quando uso se aproxima do limite do plano, mostrar banner

---

## 4. Offboarding formalizado

Quando tenant cancela, hoje não há processo. Precisa formalizar pra LGPD e pra risco legal.

### Tarefas

- [ ] Fluxo de cancelamento pelo admin do tenant (com motivo categorizado)
- [ ] Export LGPD-compliant dos dados do tenant (JSON + anexos)
- [ ] Retenção legal de documentos que por lei não podem ser apagados (contratos, faturas)
- [ ] Anonimização de dados que não precisam ser retidos
- [ ] Deleção programada após período legal
- [ ] Documentação clara do que é mantido e por quanto tempo

---

## Impacto esperado

- **Time Hubtrix** opera a base com método (antecipação de churn, priorização)
- **NPS sistemático** = fonte de dados reais pra roadmap de produto
- **Self-service** = growth orgânico sem dependência de contato comercial pra expandir
- **Offboarding LGPD-compliant** = redução de risco legal e reputacional

---

## Relação com outras tarefas

- Depende parcialmente de [gestao_assinatura_interna_17-04-2026.md](./gestao_assinatura_interna_17-04-2026.md) — o upgrade self-service precisa do módulo de assinatura/cobrança pronto
- Complementa [dogfooding_funil_interno_17-04-2026.md](./dogfooding_funil_interno_17-04-2026.md) — dogfooding cuida de leads (pré-venda); este projeto cuida de clientes ativos (pós-venda)

---

## Priorização sugerida

Dentro deste projeto, ordem natural:

1. **Health score** (urgente — risco de perder tenant sem saber que está em risco)
2. **NPS** (baixa complexidade, alto valor pra roadmap)
3. **Self-service upgrade** (depende de assinatura interna)
4. **Offboarding** (importante pra LGPD, mas baixa urgência até ter churn real)
