---
name: "Resiliência nas integrações ERP (retry, fila, monitoring, alerta)"
description: "Hoje uma falha na integracao com HubSoft no fechamento de venda exige intervencao manual e e invisivel pro admin ate alguem reclamar"
prioridade: "🔴 Alta"
responsavel: "Tech"
---

# Resiliência nas integrações ERP — 17/04/2026

**Data:** 17/04/2026
**Responsável:** Tech
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando priorização

---

## Descrição

Estágio 5 de A2 (Fechamento) revelou 3 lacunas críticas na integração ERP:

1. **Sem retry automático** — se HubSoft retorna erro temporário (timeout, 5xx), a integração falha e fica assim. Vendedor precisa perceber e acionar manualmente.
2. **Sem fila de reenvio** — toda chamada é síncrona. Se o ERP está fora do ar, perdemos a chance de enviar depois automaticamente.
3. **Sem dashboard de integrações** (% sucesso, falhas recentes) — operação é cega. Alguém descobre que a integração caiu só quando um cliente reclama que o contrato não virou.

Essas 3 lacunas combinadas fazem o Hubtrix **parecer pior do que é** — uma falha operacional vira problema visível pro cliente.

Surgiu de A2 estágio 5 em `PRODUTO/VISAO.md`.

---

## Tarefas

### Retry automático + fila de reenvio
- [ ] Model `IntegracaoERPExecucao` (status: pendente/processando/sucesso/falha/em_retry, tentativas, último_erro, data_proxima_tentativa)
- [ ] Mudar integração de síncrona pra assíncrona (fila `django-q` ou `celery`?)
- [ ] Policy de retry (exponential backoff: 1min → 5min → 30min → 2h → 24h → desistir)
- [ ] Alerta pro admin depois de N tentativas falhando
- [ ] Button "Forçar reenvio" na oportunidade/contrato quando falha permanente

### Dashboard de integrações
- [ ] Página `/configuracoes/integracoes/saude/` com:
  - % de sucesso últimos 7/30 dias por ERP
  - Lista de falhas recentes com motivo
  - Status atual (última chamada bem-sucedida há quanto tempo)
  - Gráfico de latência ao longo do tempo
- [ ] Alertas configuráveis (se taxa de erro > X% → notifica admin)

### Logs estruturados
- [ ] Todas as chamadas de integração registram em `LogSistema` categoria `integracao`
- [ ] Payload de entrada e saída (sem PII sensível)
- [ ] Tempo de resposta, status HTTP

---

## Impacto esperado

- Operação mais robusta (tolerância a falha temporária do ERP)
- Admin enxerga a saúde da integração em tempo real
- Redução drástica de incidentes "contrato não foi pro ERP" que viram reclamação de cliente
- Base pra estender quando entrarem SGP, IXC, MK

---

## Prioridade alta porque

- Afeta o momento mais crítico da jornada (fechamento de venda)
- Pode causar perda de receita (contrato não efetiva no ERP, cobrança não acontece)
- Fácil de justificar ROI (cada falha manualmente resgatada custa X minutos de vendedor)
