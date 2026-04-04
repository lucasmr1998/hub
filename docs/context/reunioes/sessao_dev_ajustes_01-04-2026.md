# Sessão Dev: Ajustes, Populacão e Automações — 01/04/2026

**Data:** 01/04/2026
**Participantes:** Lucas (CEO), Claude (Tech Lead / CTO / CS / Jurídico)
**Duração:** ~3 horas

---

## Contexto

Continuação da sessão intensiva de desenvolvimento. Foco em corrigir bugs, popular o sistema completo para ambos os tenants, reorganizar menus, documentar integrações e iniciar o módulo de Automações.

---

## Principais pontos discutidos

- Sistema CS não mostrava dados porque script populava apenas tenant Megalink, não Aurora
- 9 models com `unique=True` global impediam multi-tenancy (mesmo código em tenants diferentes dava erro)
- Chart.js não carregava em 6 templates do CS (extends `sistema/base.html` que não inclui Chart.js)
- Referências ao `vendas_web` ainda existiam em imports, admin e template do `/admin/`
- Reorganização completa dos menus: Comercial, Marketing, CS, Suporte
- Sistema de notificações existe estruturalmente mas está 100% desativado (envio, testes, configurações)
- Signals espalhados e hardcoded, necessidade de gerenciamento configurável pelo cliente
- Proposta de módulo de Automações em Marketing para substituir signals hardcoded
- Documentação das integrações HubSoft para onboarding
- Contrato modelo para primeiro cliente (Grupo Magister)

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| Corrigir `unique=True` para `unique_together('tenant', campo)` em 9 models | Multi-tenancy quebrava com dados em 2+ tenants |
| Reorganizar menu CS em 3 seções: Customer Success, Fidelização, Configurações | Menu antigo tinha 5 seções fragmentadas |
| Indicações vai para Fidelização, não CS | É mecânica de benefício/engajamento |
| Membros renomeado para Clientes no menu CS | Mais claro para o usuário final |
| Retenção removido do menu temporariamente | Módulo não está pronto |
| Vendas movido para dentro do CRM, Desempenho virou Dashboard do Comercial | Organização mais lógica |
| CS renomeado para Customer Success no menu | Nome completo mais profissional |
| Módulo Automações será em Marketing | Clients devem gerenciar signals/regras de automação de forma visual |
| Frontend primeiro, backend depois para Automações | Validar UX antes de implementar |
| Contrato modelo criado do zero | Primeiro cliente real (Grupo Magister) |

---

## O que foi feito

### Correções
- Populou sistema completo para Megalink + Aurora HQ (leads B2B, CRM, CS, giros, validações)
- Corrigiu 9 models: RegraPontuacao, TipoNotificacao, CanalNotificacao, Cidade, MembroClube, CategoriaParceiro, CupomDesconto, ResgateCupom, CampanhaTrafego, TagCRM
- Adicionou Chart.js em 6 templates CS
- Removeu todas as referências a `vendas_web` em `apps/`
- Removeu template legado `templates/admin/index.html`
- Corrigiu UserAdmin com campo `telefone` inexistente
- Removeu seção "Estatísticas do Sistema" das configurações
- Removeu seção "Equipes" duplicada das configurações CRM
- Tarefas CRM abre na aba "Todas Pendentes" por padrão
- Botão Excluir pipeline virou ícone discreto

### Menus reorganizados
- Comercial: Dashboard (ex-Desempenho) > CRM (Pipeline, Vendas, Tarefas) > Config (Configurações, Equipes, Metas)
- Marketing: Leads, Campanhas, Automações (novo), Landing Page, Segmentos
- Customer Success: Dashboard, Clientes > Fidelização (Indicações, Parceiros, Cupons, Roleta) > Configurações (Banners, Carteirinhas, Níveis e XP)
- Removidos: Cadastro do Comercial, Aurora do topbar

### Documentação
- `docs/PRODUTO/03-INTEGRACOES_HUBSOFT.md`: mapa completo das integrações, requisitos de onboarding, checklist
- `docs/OPERACIONAL/contratos/contrato_grupo_magister_01-04-2026.md` + PDF

### Novo módulo: Automações (frontend only)
- App `apps/marketing/automacoes/` criado
- Lista de automações com toggle, KPIs, filtros, busca
- Builder visual: Quando (9 eventos) > Se (condições dinâmicas) > Então (ações encadeáveis com delay)
- Registrado no INSTALLED_APPS, URLs e menu

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Implementar backend do módulo Automações (models, signals dinâmicos, execução) | Dev |
| Reativar sistema de notificações (implementar service de envio, signals automáticos) | Dev |
| Implementar módulo Retenção (churn alerts, NPS) | Dev |
| Deploy em produção do multi-tenancy | DevOps |
| Revisar e assinar contrato Grupo Magister | Lucas / Jurídico |
| Popular dados de `ResgateCupom` no script (gráfico Resgates fica vazio) | Dev |

---

## Próximos passos

- [ ] Validar frontend de Automações e ajustar UX
- [ ] Implementar backend de Automações (RegraAutomacao model, engine de execução)
- [ ] Reativar e conectar sistema de notificações ao módulo de Automações
- [ ] Implementar módulo Retenção no CS
- [ ] Preparar deploy produção
- [ ] Onboarding Grupo Magister
