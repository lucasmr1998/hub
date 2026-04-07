# Admin Aurora e Planos — 29/03/2026

**Data:** 29/03/2026
**Participantes:** CEO, CTO, PM, PMM
**Duração:** ~1.5 horas (terceira sessão do dia)

---

## Contexto

Após implementar multi-tenancy e segurança, foco foi criar o painel de gestão do SaaS (Admin Aurora) e o sistema de planos com features configuráveis.

---

## Principais pontos implementados

### Admin Aurora (app separado: apps/admin_aurora/)
- Dashboard com stats: total tenants, ativos, em trial, erros 24h
- Tabela de provedores com plano, módulos, leads, users, status
- Criar novo provedor (formulário completo com trial)
- Detalhe do tenant: editar módulos/planos, gerenciar trial, ver users, status HubSoft
- Logs do sistema com filtros por nível
- Gerenciamento de planos com features por categoria
- Acesso exclusivo para staff (botão "Aurora" na topbar, roxo)
- URL: /aurora-admin/

### Sistema de Planos
- Model Plano (modulo, tier, preco_mensal, preco_transacional, unidade_transacional)
- Model FeaturePlano (slug, nome, categoria, ativo) vinculado ao Plano
- 9 planos criados (3 tiers x 3 módulos) conforme 08-PRECIFICACAO.md
- 115 features distribuídas entre os planos
- Tenant vinculado ao Plano via FK (plano_comercial_ref, plano_marketing_ref, plano_cs_ref)
- Método tenant.tem_feature(slug) para verificar acesso
- Command seed_planos para recriar features

### Testes automatizados
- pytest + pytest-django + factory-boy configurados
- 16 testes de isolamento de tenant (todos passando)
- Factories: TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory

### Controle de módulos
- Context processor multi-tenant (módulos, planos, cores, logo por tenant)
- Topbar condicional (Comercial e Marketing só aparecem se módulo ativo)
- CRM na sidebar do Comercial (só para plano Pro)

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| Admin Aurora como app separado (admin_aurora/) | Não misturar gestão do SaaS com o app sistema do usuário final |
| Plano como model (não hardcoded) | Permite gerenciar planos e features pelo painel sem deploy |
| Features com slug | O código verifica acesso por slug (tenant.tem_feature('crm-pipeline')), não por nome |
| Escada de features cumulativa | Starter tem X, Start tem X + Y, Pro tem X + Y + Z |
| Preços conforme documentação | Comercial 397/797/1397, Marketing 297/597/997, CS 247/497/897 |
| seed_planos como management command | Permite recriar features a qualquer momento |

---

## Próximos passos

- [ ] Deploy multi-tenancy em produção
- [ ] Rotacionar credenciais no servidor
- [ ] Mover views para novos apps (incremental)
- [ ] Testes automatizados para signals e APIs
