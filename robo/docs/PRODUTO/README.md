# PRODUTO

Documentacao tecnica do Hubtrix organizada por area.

## Estrutura

```
core/           Docs transversais (status, roadmap, testes, permissoes)
integracoes/    Integracoes externas (HubSoft, N8N, outras)
ops/            Operacao (deploy, cron, notificacoes)
modulos/        Um diretorio por modulo funcional
```

## core/

| Doc | Conteudo |
|-----|----------|
| [00-STATUS](core/00-STATUS.md) | Estado atual de cada modulo (pronto / parcial / pendente) |
| [01-ROADMAP](core/01-ROADMAP.md) | Roadmap de produto |
| [02-TESTES](core/02-TESTES.md) | Estrategia de testes |
| [03-PERMISSOES](core/03-PERMISSOES.md) | Sistema de permissoes granulares |

## integracoes/

| Doc | Conteudo |
|-----|----------|
| [01-HUBSOFT](integracoes/01-HUBSOFT.md) | Integracao com HubSoft |
| [02-INTEGRACOES](integracoes/02-INTEGRACOES.md) | Demais integracoes (WhatsApp providers, IA providers, etc) |
| [03-APIS_N8N](integracoes/03-APIS_N8N.md) | APIs consumidas pelo N8N |

## ops/

| Doc | Conteudo |
|-----|----------|
| [01-DEPLOY](ops/01-DEPLOY.md) | Deploy em producao |
| [02-CRON](ops/02-CRON.md) | Servicos periodicos e cron jobs |
| [03-NOTIFICACOES](ops/03-NOTIFICACOES.md) | Motor de notificacoes do sistema |

## modulos/

Cada modulo tem um README com visao geral e arquivos separados por funcionalidade.

| Modulo | Descricao |
|--------|-----------|
| [atendimento/](modulos/atendimento/) | Engine de atendimento (runtime de fluxos, sessoes, recontato) |
| [comercial/](modulos/comercial/) | Leads, cadastro, viabilidade, CRM (pipeline, oportunidades, metas) |
| [inbox/](modulos/inbox/) | Chat multicanal, distribuicao, widget, websocket |
| [fluxos/](modulos/fluxos/) | Editor visual de fluxos, tipos de nodos, integracao IA |
| [assistente-crm/](modulos/assistente-crm/) | Assistente via WhatsApp cross-tenant |
| [marketing/](modulos/marketing/) | Campanhas UTM, segmentos, automacoes (regras e motor) |
| [suporte/](modulos/suporte/) | Tickets e SLA |
| [cs/](modulos/cs/) | Clube, parceiros, indicacoes, carteirinha, NPS, retencao |

---

**Convencao:** todo modulo tem `README.md` com visao geral + arquivos de funcionalidade (`leads.md`, `oportunidades.md`, etc). Modulos complexos podem ter subpastas (ex: `comercial/crm/`, `cs/clube/`).
