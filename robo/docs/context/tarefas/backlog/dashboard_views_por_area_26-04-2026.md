---
name: "Dashboards por área (resolver submenu vazio + segmentar visões)"
description: "Quebrar a Dashboard única em sub-views por área (Comercial / Atendimento / Pós-venda / Relatórios) pra preencher o submenu lateral e dar foco operacional"
prioridade: "🟡 Média"
responsavel: "Tech Lead + PM"
---

# Dashboards por área — 26/04/2026

**Data:** 26/04/2026
**Responsável:** Tech Lead (implementação) + PM (escopo)
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando priorização

---

## Problema

Hoje a página `/sistema/dashboard/` mistura métricas de tudo (atendimento, leads, oportunidades, clientes) numa tela única. Dois efeitos colaterais:

1. **Submenu lateral fica vazio.** O design system reserva uma faixa à direita do icon-rail pra sub-itens. Como Dashboard só tem 1 view, a faixa aparece vazia e parece bug.
2. **Tela coringa.** Diretor comercial vê dado de CS misturado com leads. CS vê NPS junto com pipeline. Ninguém usa de fato porque ninguém é dono do número.

---

## Solução proposta

Quebrar Dashboard em **sub-views por área**, espelhando os 4 módulos do produto:

```
Dashboard
├── Visão geral              ← resumo executivo (default, mantém o que tem hoje)
├── Comercial                ← leads, oportunidades, pipeline, conversão, metas
├── Atendimento              ← sessões IA, taxa de qualificação, tempo de resposta, recontato
├── Pós-venda                ← NPS, churn preditivo, clube, indicação, retenção
└── Relatórios               ← exportar PDF, agendar envio, histórico (rota já existe)
```

Cada sub-view filtra/agrega métricas da sua área.

---

## Tarefas

### Backend
- [ ] Criar views novas em [apps/dashboard/views.py](robo/dashboard_comercial/gerenciador_vendas/apps/dashboard/views.py):
  - `dashboard_comercial_view` — query em `apps/comercial/`
  - `dashboard_atendimento_view` — query em `apps/comercial/atendimento/` + `apps/inbox/`
  - `dashboard_posvenda_view` — query em `apps/cs/`
- [ ] Adicionar rotas em [apps/dashboard/urls.py](robo/dashboard_comercial/gerenciador_vendas/apps/dashboard/urls.py):
  - `dashboard/comercial/`
  - `dashboard/atendimento/`
  - `dashboard/posvenda/`
- [ ] APIs específicas por área (cada view chama só os endpoints relevantes — não puxar tudo)

### Frontend / templates
- [ ] Criar templates em `apps/dashboard/templates/dashboard/`:
  - `comercial.html`
  - `atendimento.html`
  - `posvenda.html`
- [ ] Renomear template atual pra `visao_geral.html` (mantém conteúdo, vira a default)
- [ ] Cada template usa `{% extends "layouts/layout_app.html" %}` e os componentes do DS (stat_card, etc.)

### Sidebar / submenu
- [ ] Atualizar [partials/sidebar_subnav.html](robo/dashboard_comercial/gerenciador_vendas/templates/partials/sidebar_subnav.html) pra renderizar os 5 itens quando `modulo_atual == 'dashboard'`
- [ ] Marcar item ativo via `request.resolver_match.url_name`

### Permissões
- [ ] Adicionar funcionalidades em `apps/sistema` (seed):
  - `dashboard.comercial`
  - `dashboard.atendimento`
  - `dashboard.posvenda`
  - `dashboard.relatorios` (já existe?)
- [ ] Atribuir permissões aos perfis padrão:
  - Vendedor → vê só `comercial`
  - Supervisor Comercial → vê `comercial` + `visao_geral`
  - Supervisor CS → vê `posvenda` + `visao_geral`
  - Admin → vê tudo
- [ ] Decorator `@user_tem_funcionalidade('dashboard.X')` em cada view
- [ ] Filtrar item do submenu via `{% tem_funcionalidade %}` no template

### Testes
- [ ] Adicionar smoke test pra cada view nova em `tests/`
- [ ] Caso negativo: vendedor não acessa dashboard de CS
- [ ] Atualizar `test_permissoes_matriz.py` com as novas funcionalidades

### Documentação
- [ ] Atualizar [robo/docs/PRODUTO/modulos/dashboard/](robo/docs/PRODUTO/modulos/dashboard/) — incluir as 4 sub-views
- [ ] Atualizar `core/03-PERMISSOES.md` com as novas funcionalidades

---

## Métricas por área (escopo de cada dashboard)

### Visão geral (executivo)
Atendimentos · Leads · Oportunidades · Clientes · Receita do mês · Evolução 7 dias · Leads recentes

### Comercial
Leads novos (dia/semana/mês) · Pipeline aberto (R$) · Taxa de conversão · Tempo médio no funil · Metas individuais · Ranking vendedores · Oportunidades em risco

### Atendimento
Sessões IA ativas · Taxa de qualificação · Tempo médio de resposta · Recontatos disparados · Hand-off pra humano (volume + razão) · Canais (WhatsApp / Instagram / site)

### Pós-venda
NPS atual · Distribuição (promotor/neutro/detrator) · Churn previsto (próximos 30d) · Clientes no clube · Indicações geradas · Upsell rodando

### Relatórios
(rota já existe `relatorios_view`, integra ao submenu)

---

## Impacto esperado

- Submenu lateral preenchido em todas as páginas (consistência visual)
- Cada cargo tem uma dashboard que faz sentido pra ele
- Permissão granular (LGPD / segregação de dados)
- Reduz "tela única que ninguém usa" — métricas viram propriedade de quem é responsável

---

## Decisões a tomar antes de implementar

- [ ] **Default ao clicar "Dashboard":** vai pra `Visão geral` ou pra dashboard correspondente ao perfil do usuário (vendedor → Comercial direto)? Recomendação: **redirect por perfil** — vendedor abre direto no dele, admin abre em Visão geral.
- [ ] **Marketing tem dashboard próprio?** Hoje os dados de campanha caem em `apps/marketing/`. Pode virar uma 5ª sub-view ou ficar dentro de Comercial. Decidir.
- [ ] **Mobile:** o submenu colapsa de que jeito no mobile? (já tratado no DS, validar.)

---

## Referência cruzada

- [PRODUTO/modulos/dashboard/](../../../PRODUTO/modulos/dashboard/) — spec do módulo
- [BRAND/08-BRANDBOOK.md](../../../BRAND/08-BRANDBOOK.md) — padrões visuais
- Plano de migração DS: `C:\Users\lucas\.claude\plans\jazzy-giggling-wolf.md`
