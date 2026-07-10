# Execution Log — Modulo CS

Trilha do que foi executado no modulo de Customer Success (clube, parceiros, indicacoes, carteirinha, retencao, nps). Entrada mais nova embaixo.

## 2026-07-10 — Diagnostico UX + CTO (Playwright local)

- Acao: diagnostico duplo (UX + CTO) do modulo CS (legado migrado do megaroleta) via Playwright em ambiente local, tenant Nuvyon com seed (30 membros, 6 parceiros, 12 cupons, 15 indicacoes). 32 screenshots cs_*. Nenhum toque em prod, nenhuma alteracao de codigo de produto.
- Bugs 500 confirmados em runtime: `/cs/clube/dashboard/config/` (IntegrityError: RoletaConfig.objects.get_or_create(id=1) hardcoded, model TenantMixin => colide na PK entre tenants + escreve em GET); `/cs/clube/membro/` (NoReverseMatch: redirect('roleta_index') sem namespace clube: + template estende 'roleta/membro/base_membro.html' inexistente); `/cs/clube/` preso em "Carregando ambiente..." (404 no console).
- Achados P0 (multi-tenancy): superficie publica do clube (landing/OTP/cupom/roleta) roda com tenant None sobre TenantManager fail-open (managers.py:28-35) => enxerga o banco inteiro. `landing_clube` (core_views.py:10) faz `.first()` sem tenant => Nuvyon exibe "Clube Megalink" (marca de outro cliente). `validar_otp` (api_views.py:580) busca CPF sem tenant. `validar_cupom` (parceiros/views.py:358) publico muta estado sem auth. Webhooks OTP/consulta HubSoft hardcoded compartilhados por todos os tenants (otp_service.py:5, hubsoft_service.py:26). HubsoftService do clube com credencial global unica e cache key sem sufixo de tenant.
- Achados P1: login_url='/roleta/dashboard/login/' morto em 15 views (+4 com /parceiro/login/ errado); views CS so @login_required sem checar acesso_cs (e test_module_access.py codifica o fail-open como esperado).
- Achados UX: menu com 19 itens, "Indicacoes" e "Parceiros" duplicados com mesmo icone, matchers por substring destacam 2 ao mesmo tempo; vocabulario de roleta (Giros/Premios/Assets) exposto ao usuario; CPF completo em texto claro + saldo editavel inline sem trilha; mobile inutilizavel; marca "Megalink" default em models/views/templates. Proposta de menu de 19 -> 14 itens no doc.
- Codigo morto: nps (urlpatterns vazio, nao incluido no urls raiz) com tabelas migradas em prod; retencao/models.py (ScoreCliente/AlertaChurn orfaos, views usam model do CRM). jQuery 1.10.2 + .zip commitado em static.
- Output: doc `robo/docs/context/reunioes/diagnostico_ux_cto_relatorios_cs_10-07-2026.md` (achados P0-P3 + menu proposto + estrategia de testes + tarefas propostas). Aguardando aprovacao do Lucas pra criar tarefas Workspace e executar.
- Status: completed (diagnostico); pending (execucao dos fixes)
