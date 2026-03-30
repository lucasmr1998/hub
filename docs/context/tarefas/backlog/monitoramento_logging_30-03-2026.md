# Monitoramento e Logging Estruturado — 30/03/2026

**Data:** 30/03/2026
**Responsável:** DevOps
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

O projeto possui apenas logs do Gunicorn e um model `LogIntegracao` para auditoria de integrações. Não há APM, alertas, structured logging nem dashboard de monitoramento. Com multi-tenancy ativo, é crítico monitorar a saúde do sistema por tenant.

---

## Tarefas

- [ ] Configurar logging estruturado no Django (JSON format)
- [ ] Definir níveis de log por módulo (comercial, CS, integrações)
- [ ] Implementar health check endpoint (/health/)
- [ ] Configurar alertas para erros críticos (integrações HubSoft, falhas de API)
- [ ] Avaliar ferramenta de APM (Sentry, Grafana ou similar)
- [ ] Criar dashboard básico de monitoramento (uptime, erros, latência)
- [ ] Monitorar métricas por tenant (uso, erros, volume)

---

## Contexto e referências

- Model existente: `LogIntegracao` em `apps/integracoes/`
- Gunicorn logs: `/var/log/gunicorn/robovendas/`

---

## Resultado esperado

Logging estruturado em JSON, health check endpoint, alertas de erros críticos configurados. Visibilidade sobre a saúde do sistema em produção.
