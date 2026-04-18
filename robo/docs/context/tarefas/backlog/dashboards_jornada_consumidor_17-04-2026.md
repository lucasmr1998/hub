---
name: "Dashboards e observabilidade da jornada do consumidor (A2)"
description: "Agrega analytics faltantes em multiplos estagios da jornada: funil do bot, saude do onboarding, ROI da indicacao, dashboard consolidado por cliente"
prioridade: "🟡 Média"
responsavel: "Tech + PM"
---

# Dashboards e observabilidade da jornada do consumidor — 17/04/2026

**Data:** 17/04/2026
**Responsável:** Tech + PM
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando priorização

---

## Descrição

Durante a detalhamento de A2 (jornada do consumidor), **quase todos os 10 estágios** apontaram falta de dashboard/analytics que transformasse dados existentes em visão acionável. O Hubtrix coleta muito dado mas expõe pouco pro operador do ISP.

Surgiu de A2 em `PRODUTO/VISAO.md`.

---

## Dashboards identificados como faltantes

| Estágio | Dashboard faltante | Fonte de dado |
|---------|--------------------|----------------|
| 3 Qualificação | Funil do bot (taxa de passagem nodo a nodo) | `LogFluxoAtendimento` + `NodoFluxoAtendimento` |
| 5 Fechamento | Integrações ERP (quantas passaram, quantas falharam, motivo) | Logs de integração + webhook retorno |
| 6 Ativação | "Meus clientes ativos" vs "minhas oportunidades" | Cliente (quando existir) + OportunidadeVenda |
| 7 Onboarding | Saúde do onboarding (% que fez cadastro no Clube, primeiro giro, leu régua) | `MembroClube` + `ExtratoPontuacao` + Automações |
| 8 Relacionamento | Saúde consolidada por cliente (NPS + tickets + inadimplência + uso) | Ticket + NPS + Cliente + HistoricoContato |
| 10 Indicação | ROI do programa de indicação (receita gerada vs pontos distribuídos) | Indicacao + LeadProspecto.valor |
| Transversal | Funil completo AARRR (Aquisição → Ativação → Retenção → Receita → Recomendação) | Cruzamento de vários models |

---

## Tarefas

### Fase 1 — dashboards unitários
- [ ] Dashboard "funil do bot" com Sankey/gráfico mostrando passagem por cada nodo
- [ ] Dashboard "integrações ERP" (sucesso/falha/retry)
- [ ] Dashboard "saúde do onboarding" (cohort analysis de últimos 30 dias)
- [ ] Dashboard "ROI de indicação"

### Fase 2 — dashboards consolidados
- [ ] Dashboard "saúde por cliente" (ficha única agregando NPS + tickets + uso + inadimplência)
- [ ] Dashboard "funil AARRR" transversal

### Infraestrutura
- [ ] Definir paradigma de cálculo (queries pesadas on-demand vs cache vs agregação periódica)
- [ ] Filtro universal por período + por equipe
- [ ] Export CSV/PDF por dashboard

---

## Impacto esperado

- ISP deixa de ser reativo (apagar incêndio) e vira proativo (tomada de decisão baseada em dado)
- Identificação de gargalos na jornada (onde leads somem, onde conversão cai)
- Justifica upgrade de plano (admins que veem valor renovam)
- Melhora percepção do produto em demo/venda
