---
name: "Home personalizada por perfil + dashboard unificado + insights acionáveis"
description: "Cada perfil (atendente, vendedor, gerente, CS, admin) tem sua própria tela inicial. Admin ganha dashboard unificado com insights proativos."
prioridade: "🔴 Alta"
responsavel: "Tech + PM"
---

# Home personalizada por perfil — 17/04/2026

**Data:** 17/04/2026
**Responsável:** Tech + PM
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando priorização

---

## Descrição

Hoje todos os usuários veem os mesmos dashboards, independente do perfil. Um atendente vê dashboard de vendedor, de CS, de admin. Isso é problema de **UX** (o usuário tem que caçar o que importa pra ele) e de **permissão/segurança** (informação que não deveria ser visível pra certos perfis).

Solução em **3 camadas**:

1. **Home personalizada por perfil** (UX) — cada perfil abre o Hubtrix e encontra SEU conteúdo
2. **Dashboard unificado do admin** (conteúdo) — admin vê saúde do tenant inteiro numa tela só
3. **Insights acionáveis** (inteligência) — sistema detecta problemas e sugere ação

Surgiu no detalhamento dos estágios 7-8 de A1 em `PRODUTO/VISAO.md`.

---

## Camada 1: Home personalizada por perfil

Cada perfil tem sua home, definida pelo `PerfilUsuario.cargo` (ou tag):

| Perfil | Home |
|--------|------|
| **Atendente (Inbox)** | Fila de conversas minhas + SLA breach + mensagens sem resposta |
| **Vendedor** | Próximas tarefas hoje, oportunidades a avançar, meta individual |
| **Gerente de vendas** | Pipeline health, meta do time, ranking de vendedores |
| **CS** | Alertas de retenção, NPS pendente, tickets críticos do Clube |
| **Admin** | Dashboard unificado + insights (ver camadas 2 e 3) |

---

## Camada 2: Dashboard unificado (admin)

Uma tela só agregando KPIs dos módulos:

- Funil do mês (leads → oportunidades → contratos fechados)
- NPS atual
- Conversas sem resposta (Inbox)
- Tickets abertos + SLA breach (Suporte)
- Alertas de retenção ativos (CRM/Retenção)
- Engajamento no Clube (giros, missões concluídas)
- Status das integrações (ERP, WhatsApp, IA — sinal vermelho/amarelo/verde)
- Meta do mês vs realizado

---

## Camada 3: Insights acionáveis

Sistema detecta padrões e **sugere ação específica** em cima do dashboard:

- "12 conversas sem resposta há >2h → [Abrir Inbox filtrado]"
- "3 tarefas do CRM vencidas → [Ver lista]"
- "Integração Uazapi falhou ontem às 14h → [Diagnosticar]"
- "Meta do mês: 34/100 — no ritmo atual bate 72% → [Ver pipeline]"
- "Tenant sem atividade há 5 dias — risco de churn precoce → [Investigar]" (pro admin Hubtrix)

Cada insight tem: mensagem curta + 1 botão de ação direta.

---

## Tarefas

### Camada 1
- [ ] Mapear perfis atuais (`PerfilUsuario.cargo`) e decidir tipologia final
- [ ] Definir qual home renderiza por perfil (URL padrão após login)
- [ ] Criar template por perfil (`atendente_home.html`, `vendedor_home.html`, etc.)
- [ ] Restringir acesso a dashboards de outros perfis via permissão granular (atendente NÃO acessa `/crm/desempenho/`)

### Camada 2
- [ ] Definir os 8-10 KPIs agregados mais críticos pro admin
- [ ] Criar view `admin_home_view` com queries agregadas por módulo
- [ ] Template `admin_home.html` com cards dos KPIs
- [ ] Performance: queries precisam ser rápidas (cache em Redis, ou agregação periódica)

### Camada 3
- [ ] Definir catálogo inicial de 10-15 insights possíveis
- [ ] Service `InsightsService.detectar_insights(tenant, perfil)` que roda detecções
- [ ] Cada insight tem: regra de detecção + mensagem + link de ação
- [ ] Atualização periódica (cron 15min? push via WebSocket?)
- [ ] Permitir admin ignorar/silenciar insights temporariamente

### Infra
- [ ] Permissões granulares reforçadas (hoje pode haver leaks)
- [ ] Testes de permissão por perfil

---

## Impacto esperado

- **Atendente** abre e já vê o que tem que fazer → produtividade diária maior
- **Vendedor** tem "modo foco" (próxima tarefa, próxima oportunidade)
- **Admin** identifica problemas antes que virem crise
- **Segurança** reduz risco de informação vazada entre perfis
- **Retenção** sinaliza tenants em risco de churn precoce (insight interno do Hubtrix)

---

## Prioridade alta porque

- É UX fundamental (impressão do produto em onboarding)
- Cruza com permissão/segurança (risco real hoje)
- Dashboard admin é esperado por clientes B2B SaaS
- Base pra features de inteligência mais avançadas depois
