---
name: "Automações do Pipeline (módulo de automação do CRM)"
description: "Novo módulo que permite configurar regras que movimentam oportunidades automaticamente entre estágios do pipeline com base em tags, histórico, documentos e campos do lead. Substitui a lógica hardcoded do Hubtrix atual e porta a engine do robovendas em versão multi-tenant, configurável via UI."
prioridade: "🔴 Alta"
responsavel: "Tech"
---

# Automações do Pipeline — 21/04/2026

**Data:** 21/04/2026
**Responsável:** Tech
**Prioridade:** 🔴 Alta (bloqueia go-live Nuvyon + dívida com Megalink)
**Status:** ✅ Fase 1 MVP concluída em 21/04/2026

**Entregas da Fase 1:**
- `RegraPipelineEstagio` multi-tenant em `apps/comercial/crm/models.py` + migration 0009
- Engine em `apps/comercial/crm/services/automacao_pipeline.py`
- Signals: `m2m_changed` em `OportunidadeVenda.tags` + `post_save` em `LeadProspecto`/`HistoricoContato`/`ImagemLeadProspecto`/`ServicoClienteHubsoft`
- Endpoint `POST /api/leads/tags/` com `@api_token_required`
- Management command `seed_regras_pipeline_padrao`
- Django admin pra `RegraPipelineEstagio`
- Tela read-only `/crm/automacoes-pipeline/` + item no sidebar
- 8 testes passando em `tests/test_automacao_pipeline.py`
- Doc de produto em [robo/docs/PRODUTO/modulos/comercial/crm/automacoes-pipeline.md](../../../PRODUTO/modulos/comercial/crm/automacoes-pipeline.md)

Fases 2 e 3 (UI de edição visual, métricas, preview) seguem pendentes e continuarão sob nova tarefa quando priorizadas.

---

## Contexto

O `robovendas` (sistema legado single-tenant da Megalink) tem um motor de regras (`regras_engine.py`, 389 linhas) que move oportunidades entre estágios do pipeline quando condições são atendidas:
- Tag X foi adicionada
- Histórico com status Y existe
- Imagem de documento foi validada/rejeitada
- Lead converteu venda
- Campo do lead tem valor específico

O Hubtrix novo (multi-tenant) **não tem esse mecanismo**. Hoje a movimentação é manual ou via signal hardcoded (`verificar_conversao_historico` que só trata o caso "converteu_venda=True").

Descoberta surgida na análise do fluxo Matrix da Megalink rodando no robovendas, comparado ao Hubtrix — ver [fluxo_matrix_hubtrix.md](../../clientes/nuvyon/implementacoes/fluxo_matrix_hubtrix.md) seção 3.1.

**Por que virar feature, não gambiarra:**
- Megalink vai migrar pro Hubtrix eventualmente — se não portar, retrabalho garantido
- Qualquer tenant com fluxo de vendas automatizado vai precisar
- Solução já existe e foi testada em produção (robovendas)
- Não é específico da Nuvyon, é capacidade do produto

---

## Posicionamento no produto

**Módulo:** Automações do Pipeline

| Módulo | Automatiza | Dispara em |
|---|---|---|
| Automações de Marketing (existe) | Mensagens, réguas, campanhas | Eventos de lead |
| **Automações do Pipeline (novo)** | Movimentação de oportunidade no pipeline | Eventos de lead/oportunidade/documento |

**Menu:** CRM → Configurações CRM → Automações do Pipeline (`/crm/automacoes-pipeline/`)

**Diferenciação escrita pro usuário:**
- Marketing = mensagens automáticas
- Pipeline = movimentação automática de oportunidades

---

## Escopo faseado

### Fase 1 — MVP (bloqueia Nuvyon) — ~2 dias

**Backend:**
- [ ] Modelo `RegraPipelineEstagio` com `TenantMixin`
  - Campos: `nome`, `estagio` (FK), `condicoes` (JSON), `prioridade` (int), `ativo` (bool)
  - Baseado em `prod/dashboard_comercial/gerenciador_vendas/crm/models.py:44`
- [ ] Service `apps/comercial/crm/services/automacao_pipeline.py` (porta `regras_engine.py`)
  - Função `processar_oportunidade(oportunidade)` avalia e move
  - Tipos de condição: `tag`, `historico_status`, `lead_campo`, `lead_status_api`, `servico_status`, `imagem_status`, `converteu_venda`
  - Operadores: `igual`, `diferente`, `existe`, `nao_existe`, `todas_iguais`, `nenhuma_com`
- [ ] Signal `m2m_changed` na tag da oportunidade → chama engine
- [ ] Signal `post_save` em `HistoricoContato` → chama engine
- [ ] Signal `post_save` em `ServicoClienteHubsoft` → chama engine
- [ ] Signal `post_save` em `ImagemLeadProspecto` → chama engine
- [ ] Endpoint `POST /api/leads/tags/` (dispara o fluxo)
- [ ] Registrar movimentação em `HistoricoPipelineEstagio` com `motivo="Regra: <nome>"`
- [ ] Log de auditoria via `registrar_acao`

**Seed:**
- [ ] Management command `seed_regras_pipeline_padrao` — cria regras padrão ao criar tenant novo
- [ ] Regras padrão iniciais (equivalentes ao robovendas):
  - Tag "Assinado" → estágio "Cliente Ativo"
  - Histórico `converteu_venda=True` → "Ganho"
  - Imagens `todas_iguais=documentos_validos` → avança estágio
  - Imagens `existe=documentos_rejeitados` → "Doc Rejeitado"

**UI (read-only MVP):**
- [ ] Tela `/crm/automacoes-pipeline/` lista regras por estágio
- [ ] Detalhe da regra mostra condições formatadas em prosa ("se tag 'X' foi adicionada E histórico tem status 'Y'")
- [ ] Link pra editar no Django admin (sem UI própria ainda)

**Integração:**
- [ ] Migration pras tabelas novas
- [ ] Admin Django pra `RegraPipelineEstagio` (cadastro full via Django admin até UI visual existir)

**Docs:**
- [ ] `robo/docs/PRODUTO/modulos/comercial/crm-automacao-pipeline.md`
- [ ] Atualizar `README.md` do módulo comercial

**Testes:**
- [ ] `tests/test_automacao_pipeline.py` cobrindo:
  - Regra simples move oportunidade
  - Estágio final não é reavaliado
  - Prevenção de loop
  - Multi-tenant (regra de tenant A não afeta tenant B)
  - Cada tipo de condição (7 casos)

### Fase 2 — UI visual de edição (próximos tenants) — ~2 dias

- [ ] Tela de criar/editar regra com editor visual de condições
- [ ] Dropdown de tipo + operador + valor
- [ ] Ativar/desativar/duplicar regra pela UI
- [ ] Reordenação por prioridade drag-and-drop

### Fase 3 — Maturidade — ~3 dias

- [ ] Preview de impacto ("essa regra moveria N oportunidades hoje")
- [ ] Registry extensível de tipos de condição (nova condição = nova classe)
- [ ] Métricas por regra (quantas vezes disparou, última execução)
- [ ] Histórico de auditoria completo por regra
- [ ] Testes de performance (base grande, N regras)
- [ ] Async via Celery (evitar bloqueio do request de API)

---

## Critério de aceite da Fase 1

- Endpoint `POST /api/leads/tags/` responde 200 com tags atualizadas
- Adicionar tag dispara engine e, se regra bater, move oportunidade automaticamente
- Admin consegue ver regras ativas na tela `/crm/automacoes-pipeline/` (read-only)
- Tenant novo criado no aurora-admin já tem regras padrão seed
- Zero quebra pra tenant sem regras configuradas (fluxo manual preservado)
- `python manage.py check` limpo
- Testes passando
- Doc em `PRODUTO/modulos/comercial/crm-automacao-pipeline.md` criado

---

## Dependências / bloqueia

- **Bloqueia:** go-live do fluxo Matrix da Nuvyon (depende do endpoint `/api/leads/tags/` + engine funcionando)
- **Bloqueia:** eventual migração da Megalink do robovendas pro Hubtrix
- **Depende de:** nada (pode começar agora)

---

## Decisões tomadas

- Virar **feature do produto**, não gambiarra específica pra Nuvyon
- Nome definitivo: **Automações do Pipeline** (diferencia de Automações de Marketing)
- Menu: `CRM → Configurações CRM → Automações do Pipeline`
- Multi-tenant nativo desde dia 1 (TenantMixin)
- Fase 1 bloqueia Nuvyon; Fases 2 e 3 são evolutivas
- Seed de regras padrão no novo tenant pra começar útil, não vazio

---

## Referências

- Engine original: `prod/dashboard_comercial/gerenciador_vendas/crm/services/regras_engine.py` (389 linhas)
- Modelo original: `prod/dashboard_comercial/gerenciador_vendas/crm/models.py:44` (RegraPipelineEstagio)
- Signals originais: `prod/dashboard_comercial/gerenciador_vendas/crm/signals.py`
- View original de tags: `prod/dashboard_comercial/gerenciador_vendas/vendas_web/views.py:7641`
- Guia Nuvyon: [fluxo_matrix_hubtrix.md](../../clientes/nuvyon/implementacoes/fluxo_matrix_hubtrix.md)
- Superseda: [api_leads_tags_21-04-2026.md](api_leads_tags_21-04-2026.md) (vira parte desta tarefa maior)
