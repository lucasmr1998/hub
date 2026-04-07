---
name: "Limpeza de Apps Legados e Imports"
description: "Os models já foram migrados para os apps modulares (29/03). Restavam apps legados duplicados e imports antigos. A limpez"
prioridade: "🔴 Alta"
responsavel: "Dev"
---

# Limpeza de Apps Legados e Imports — 30/03/2026

**Data:** 30/03/2026
**Responsável:** Dev
**Prioridade:** 🔴 Alta
**Status:** 🔧 Em andamento

---

## Descrição

Os models já foram migrados para os apps modulares (29/03). Restavam apps legados duplicados e imports antigos. A limpeza principal foi concluída em 30/03.

---

## Tarefas

- [x] Remover `crm/` (raiz) do `INSTALLED_APPS` — substituído por `apps.comercial.crm`
- [x] Remover `integracoes/` (raiz) do `INSTALLED_APPS` — substituído por `apps.integracoes`
- [x] Registrar `apps.comercial.crm` e `apps.integracoes` no `INSTALLED_APPS`
- [x] Migrar imports de `from vendas_web.models import X` para `from apps.X.models import X` (~40 arquivos)
- [x] Migrar imports de `from crm.models import X` para `from apps.comercial.crm.models import X`
- [x] Migrar imports de `from integracoes.*` para `from apps.integracoes.*`
- [x] Mover middleware (LoginRequiredMiddleware) para `apps.sistema.middleware`
- [x] Mover context_processors para `apps.sistema.context_processors`
- [x] Atualizar URLs para usar `apps.integracoes.urls` em vez de `integracoes.urls`
- [x] Registrar apps CS e admin_aurora no settings.py principal
- [x] Corrigir settings_local.py para herdar INSTALLED_APPS do settings.py
- [x] `manage.py check` passando (0 erros)
- [x] 16 testes de isolamento passando
- [x] Migrar admin.py do vendas_web para apps modulares (Phase 2: admin split)
  - [x] apps/sistema/admin.py — AdminSiteCustom, ConfiguracaoEmpresa, ConfiguracaoSistema, LogSistema, StatusConfiguravel, UserAdmin
  - [x] apps/comercial/leads/admin.py — LeadProspecto, Prospecto, HistoricoContato, ImagemLeadProspecto
  - [x] apps/comercial/atendimento/admin.py — FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo, TentativaResposta, RespostaQuestao
  - [x] apps/comercial/cadastro/admin.py — ConfiguracaoCadastro, PlanoInternet, OpcaoVencimento, CadastroCliente, DocumentoLead
  - [x] apps/comercial/viabilidade/admin.py — CidadeViabilidade
  - [x] apps/notificacoes/admin.py — TipoNotificacao, CanalNotificacao, PreferenciaNotificacao, Notificacao, TemplateNotificacao
  - [x] apps/marketing/campanhas/admin.py — CampanhaTrafego, DeteccaoCampanha
  - [x] vendas_web/admin.py esvaziado (apenas comentarios de referencia)
- [x] Phase 4: Templates migrados para diretórios dos apps (31/03)
    - [x] apps/sistema/templates/sistema/ — login.html, configuracoes/{index,usuarios,recontato}.html
    - [x] apps/dashboard/templates/dashboard/ — 12 templates (dashboard, new_dash, vendas, relatorios, ajuda, api_swagger, n8n_guide, etc.)
    - [x] apps/comercial/leads/templates/comercial/leads/ — leads.html
    - [x] apps/comercial/cadastro/templates/comercial/cadastro/ — cadastro.html, configuracoes/{cadastro,planos,vencimentos}.html
    - [x] apps/comercial/atendimento/templates/comercial/atendimento/ — fluxos.html, questoes.html
    - [x] apps/notificacoes/templates/notificacoes/ — notificacoes.html, tipo_notificacao_detalhes.html
    - [x] apps/marketing/campanhas/templates/marketing/campanhas/ — campanhas.html
    - [x] render() calls atualizados em todas as views dos apps
    - [x] {% extends 'vendas_web/base.html' %} mantido (base.html fica no vendas_web por ora)
    - [x] Templates originais preservados em vendas_web/templates/ (sem exclusao)
- [ ] Remover monkey-patch de User em `vendas_web/models.py`
- [x] Migrar views/URLs do `vendas_web` para apps modulares
  - [x] Dashboard & Relatórios: 29 views migradas para `apps/dashboard/views.py` (31/03)
  - [x] URLs atualizadas em `vendas_web/urls.py` para importar de `apps.dashboard`
  - [x] Funil insights migrado de `vendas_web/funil_insights.py` para `apps/dashboard/views.py`
  - [x] Phase 5: URLs migradas para urls.py de cada app modular (31/03)
    - [x] apps/sistema/urls.py — auth, configuracoes, usuarios (10 routes)
    - [x] apps/comercial/leads/urls.py — leads, prospectos, historicos, vendas (20 routes)
    - [x] apps/comercial/atendimento/urls.py — fluxos, questoes, atendimentos, N8N (38 routes)
    - [x] apps/comercial/cadastro/urls.py — cadastro, planos, vencimentos, CEP (12 routes)
    - [x] apps/comercial/viabilidade/urls.py — viabilidade tecnica (1 route)
    - [x] apps/notificacoes/urls.py — notificacoes, templates, canais, whatsapp (25 routes)
    - [x] apps/marketing/campanhas/urls.py — campanhas de trafego (4 routes)
    - [x] apps/dashboard/urls.py — dashboard, relatorios, analise, docs (29 routes)
    - [x] gerenciador_vendas/urls.py atualizado com includes modulares
    - [x] vendas_web/urls.py esvaziado (todas as rotas migradas)
- [ ] Remover pastas `crm/` e `integracoes/` legadas da raiz (após validação em produção)

---

## Contexto e referências

- Refatoração concluída: `finalizadas/refatoracao_apps_29-03-2026.md`
- `vendas_web/models.py` é re-export (zero models próprios), mantido por compatibilidade de views
- `crm/` e `integracoes/` na raiz removidos do INSTALLED_APPS, imports atualizados

---

## Resultado esperado

Todos os imports apontam para `apps/`. Apps modulares registrados corretamente. Próximo passo: migrar views/URLs do vendas_web para os apps (tarefa separada).
