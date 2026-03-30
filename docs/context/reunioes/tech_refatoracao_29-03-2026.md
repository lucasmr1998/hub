# Refatoração técnica e migração CS — 29/03/2026

**Data:** 29/03/2026
**Participantes:** CEO, Assistente IA (Tech Lead, DevOps, QA, Segurança)
**Duração:** sessão extensa (dia inteiro)

---

## Contexto

Necessidade de refatorar o monolito vendas_web em apps separados por módulo, implementar multi-tenancy para viabilizar o modelo SaaS, reforçar segurança de credenciais e migrar o módulo CS (megaroleta) para dentro do hub.

---

## Principais pontos discutidos

- Separação do monolito vendas_web em 10 apps por módulo (Opção A aprovada pelo CEO), organizados em quatro áreas: Base (sistema, notificacoes, integracoes, dashboard), Comercial (leads, atendimento, cadastro, viabilidade, crm), Marketing (campanhas) e CS (clube, parceiros, indicacoes, carteirinha).
- Implementação completa de multi-tenancy com Tenant, PerfilUsuario, TenantMixin, TenantManager e TenantMiddleware.
- Segurança: secrets removidos do código fonte e migrados para variáveis de ambiente.
- Criação do Painel Admin Aurora (/aurora-admin/) com dashboard de tenants, gerenciamento de planos e features.
- Migração do megaroleta (módulo CS) para dentro do hub: 4 apps, 20 models, 76 URLs, 67+ templates.
- Templates CS integrados ao layout do hub (vendas_web/base.html).
- Sidebar CS com sub-seções: Clube, Parceiros, Carteirinhas, Indicações.
- Criação de 3 novos agentes: Segurança (AppSec), DevOps, QA.
- Definição do CRM do parceiro com 5 estágios: Lead identificado, Em contato, Em negociação, Trial ativo, Finalizada.

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| Opção A (sub-apps por pasta) para estrutura de apps Django | Melhor organização modular mantendo compatibilidade com o Django |
| Gestão (17 models, agentes IA) NÃO migra para o hub | Complexidade elevada e escopo separado do hub comercial |
| Templates CS estendem vendas_web/base.html (layout unificado) | Experiência visual consistente em todos os módulos |
| Modais com display:none inline para evitar conflito CSS | Solução pragmática para conflitos de estilo entre módulos |

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Deploy do multi-tenancy em produção | DevOps / Tech Lead |
| Rotacionar credenciais no servidor | DevOps / Segurança |
| Logo da AuroraISP (bloqueia materiais visuais) | CEO / Design |
| Testes automatizados de isolamento de tenant | QA / Tech Lead |
| Refinamento visual dos templates CS | Tech Lead / UX |
| URLs hardcoded na landing page do clube | Tech Lead |

---

## Próximos passos

- [ ] Deploy do multi-tenancy: rodar migrations, criar seed do tenant Megalink, preencher tenant_id
- [ ] Rotacionar todas as credenciais no servidor de produção
- [ ] Escrever testes automatizados de isolamento de tenant
- [ ] Refinar visualmente os templates CS integrados
- [ ] Substituir URLs hardcoded na landing page do clube por {% url %}
- [ ] Definir logo da AuroraISP para desbloquear materiais visuais
