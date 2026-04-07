# CRM do Parceiro — AuroraISP

**Versão:** 1.0
**Data:** 28/03/2026

---

## Qualificação de entrada

Todo lead entra com uma qualificação definida na primeira etapa. Isso determina a prioridade e o caminho no pipeline, não se o lead entra ou não.

| Qualificação | Critério | Impacto |
|--------------|----------|---------|
| **A** | Usa HubSoft | Alta prioridade. Trial de 14 dias disponível. Integração nativa |
| **B** | Outro ERP | Média prioridade. Entra no pipeline normalmente, sem trial |

---

## Pipeline — 5 estágios

### 1. Lead identificado

**Critério de avanço:** contato do decisor confirmado.

**Campos obrigatórios:**
- Nome do provedor
- Cidade
- Nome do decisor
- WhatsApp do decisor
- ERP utilizado
- Qualificação (A ou B)
- Estimativa de clientes ativos
- Estimativa de vendedores
- Fonte do lead (comunidade, indicação, outbound, evento, inbound)

---

### 2. Em contato

**Tarefas internas:**
- [ ] Diagnóstico enviado
- [ ] Demo agendada
- [ ] Demo realizada

**Critério de avanço:** demo realizada com decisor presente e sem objeção bloqueante.

**Campos obrigatórios:**
- Data do diagnóstico enviado
- Data da demo agendada
- Data da demo realizada
- Decisor presente na demo (sim/não)
- Dores principais identificadas
- Simulação de ROI com dados reais do ISP

---

### 3. Em negociação

**Tarefas internas:**
- [ ] Proposta enviada
- [ ] Follow-up D+2
- [ ] Follow-up D+5

**Critério de avanço:** prospect sinalizou interesse em fechar ou iniciou trial.

**Campos obrigatórios:**
- Módulo(s) de interesse
- Plano de interesse (Starter / Start / Pro)
- MRR estimado
- Data da proposta enviada
- Objeções levantadas
- Próxima ação e data

---

### 4. Trial ativo

*(Exclusivo para leads qualificação A — HubSoft)*

**Tarefas internas:**
- [ ] Ativação feita
- [ ] Acompanhamento D+7
- [ ] Encerramento D+14

**Critério de avanço:** trial encerrado com decisão tomada.

**Campos obrigatórios:**
- Data de início do trial
- Data de encerramento prevista
- Módulo em trial
- Responsável Aurora pelo acompanhamento

---

### 5. Finalizada

**Campos obrigatórios:**
- Resultado: Ganho / Perdido
- Se ganho: módulo(s) contratado(s), plano, MRR fechado, data de início
- Se perdido: motivo da perda, data de encerramento

---

## Responsabilidades

| Atividade | Parceiro | Aurora |
|-----------|----------|--------|
| Preencher e avançar cards | ✅ | — |
| Revisão semanal do funil | Participa | Conduz |
| Ativação e onboarding | — | ✅ |
| Acompanhamento do trial | — | ✅ |

---

## Observação

Enquanto o módulo Comercial Pro não inclui CRM próprio para a AuroraISP, este documento serve como base para configurar a ferramenta provisória do parceiro (Notion, Planilha Google ou Pipedrive).
