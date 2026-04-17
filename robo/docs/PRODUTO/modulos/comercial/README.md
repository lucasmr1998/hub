# Comercial

**Status:** Em producao
**App:** `apps/comercial/`

Modulo que cobre todo o funil de vendas do provedor: da captacao do lead ate o contrato ativado no HubSoft. Composto por 5 sub-apps independentes que se integram via ForeignKeys e signals.

```
Lead chega (WhatsApp/Site/Instagram)
    │
    ▼
┌─────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────────┐
│  LEADS  │────▶│ ATENDIMENTO  │────▶│ CADASTRO │────▶│ VIABILIDADE  │
│ Captura │     │ Bot N8N      │     │ Registro │     │ Cobertura    │
└────┬────┘     └──────────────┘     └──────────┘     └──────────────┘
     │
     ▼
┌─────────┐
│   CRM   │  Pipeline Kanban, Tarefas, Metas, Segmentos, Retencao
└─────────┘
```

> **Nota:** `apps/comercial/atendimento/` e o engine de atendimento, documentado em [atendimento/](../atendimento/). Nao esta detalhado aqui para evitar duplicacao.

---

## Indice

| Arquivo | Sub-app | Descricao |
|---------|---------|-----------|
| [leads.md](leads.md) | `leads/` | Captura, qualificacao, historico de contatos |
| [cadastro.md](cadastro.md) | `cadastro/` | Auto-cadastro publico + planos + vencimentos + CEP |
| [viabilidade.md](viabilidade.md) | `viabilidade/` | Cobertura por cidade/bairro/CEP |
| [crm/](crm/) | `crm/` | Pipeline, oportunidades, tarefas, metas, segmentos, retencao |

Para o engine de atendimento (`apps/comercial/atendimento/`), ver [atendimento/](../atendimento/).

---

## Integracoes entre submodulos

```
Leads ──signal──▶ CRM (auto-cria oportunidade quando score >= 7)
Leads ──signal──▶ CRM/Segmentos (avalia segmentos dinamicos)
Atendimento ──FK──▶ Leads (AtendimentoFluxo.lead)
Cadastro ──gera──▶ Leads (CadastroCliente.gerar_lead())
Viabilidade ──consulta──▶ Cadastro (verificacao de cobertura)
HistoricoContato ──signal──▶ CRM (conversao automatica)
CRM ──webhook──▶ HubSoft (confirmacao de contrato)
CRM ──webhook──▶ N8N (nova oportunidade, mudanca de estagio, tarefa vencida)
CRM/Segmentos ──event──▶ Automacoes (lead_entrou_segmento)
```

---

## Estatisticas

| Metrica | Valor |
|---------|-------|
| Sub-apps | 5 (leads, atendimento, cadastro, viabilidade, crm) |
| Models | 28 |
| Views | 80+ funcoes |
| Templates | 22 |
| APIs | 70+ endpoints |
| Signals | 7 |
| Indices | 50+ |

---

## Stack

TenantMixin (multi-tenancy), Django 5.2, DRF, PostgreSQL.
