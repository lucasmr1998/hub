# Multi-tenancy e Produto — 29/03/2026

**Data:** 29/03/2026
**Participantes:** CEO, CTO
**Duração:** ~2 horas (segunda sessão do dia)

---

## Contexto

Continuação da sessão de refatoração em apps. Após criar a estrutura de apps e migrar os models, o foco foi implementar multi-tenancy funcional e as features de produto necessárias para aceitar o primeiro cliente.

---

## Principais pontos implementados

### Multi-tenancy
- Models migrados para novos apps com `app_label = 'vendas_web'` temporário (para compatibilidade com admin/views legados)
- `vendas_web/models.py` substituído por re-exports dos novos apps
- FKs cross-app corrigidas para usar app_labels corretos
- `TenantManager` com auto-filtro por tenant via thread-local
- `TenantMixin.save()` auto-preenche tenant no create
- `all_tenants` como escape hatch para admin/commands
- Isolamento testado com 3 tenants (Megalink, Provedor Teste, Mega Fibra)

### Produto
- Command `criar_tenant` para onboarding automatizado (Tenant + User + Perfil + Config)
- IntegracaoAPI vinculada ao Tenant (cada provedor tem seu HubSoft)
- Context processor multi-tenant (módulos, planos, cores, logo por tenant)
- Tela de setup inicial (`/setup/`) com coleta de dados da empresa e credenciais HubSoft
- Middleware redireciona ao setup se tenant não tem ConfiguracaoEmpresa
- Controle de módulos na topbar (comercial e marketing condicionais)

### Segurança
- SECRET_KEY removida do código (variável de ambiente obrigatória)
- Senha do banco removida (sem fallback)
- Token Matrix API removido (variável de ambiente)
- Credenciais HubSoft removidas do setup_hubsoft.py (variáveis de ambiente)
- DEBUG=False por padrão (opt-in via env)
- `.env.example` criado
- IP do servidor removido do ALLOWED_HOSTS

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| `app_label = 'vendas_web'` temporário nos models | Admin e views legados ainda importam de vendas_web. Será removido quando admin migrar |
| Managers nos models de sistema | ConfiguracaoEmpresa e outros precisam de `all_tenants` para funcionar no context processor |
| SECRET_KEY vazia no settings base, validação no production | Permite settings_local definir sua própria sem falhar no import |
| Setup HubSoft opcional | Nem todo provedor usa HubSoft. O setup permite pular |

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Deploy multi-tenancy em produção | Dev |
| Migração de dados: preencher tenant_id nos registros existentes | Dev |
| Rotacionar credenciais no servidor (senha DB, SECRET_KEY, token Matrix) | Dev + Ops |
| Mover views/urls/templates/signals para novos apps | Dev |
| Remover `app_label = 'vendas_web'` quando admin migrar | Dev |
| Remover vendas_web após migração completa | Dev |

---

## Próximos passos

- [ ] Deploy em produção (migrations + seed Megalink + preencher tenant_id)
- [ ] Rotacionar credenciais no servidor
- [ ] Mover views para novos apps (incremental)
- [ ] Remover app_label temporário
- [ ] Testes automatizados para isolamento de tenant
