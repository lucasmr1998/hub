# Execution log robo_matrix

## 2026-07-18 Fase 0 fundacao do adaptador

Acao: criado o app `apps/comercial/robo_matrix` (casca do contrato Matrix sobre o
motor de atendimento), com resolucao de tenant pelo token na URL.

Decisao:
. Reusar o motor `apps/comercial/atendimento` (editor visual) como cerebro do
  fluxo, em vez de portar a maquina de estados do robo_v2 como codigo. Contrato
  do Matrix vira um adaptador fino. Config por empresa reusa catalogo HubSoft,
  configuracoes_extras da IntegracaoAPI e Agente + RAG. Ver `PLANO.md`.
. Identidade da empresa por token na URL, reusando `IntegracaoAPI.api_token`
  (sem model novo).

Output:
. `apps/comercial/robo_matrix/` (auth.tenant_por_token_url, views.ping, urls,
  seed de dev `robo_matrix_seed_demo`).
. Isencao de `/robo/` no `LoginRequiredMiddleware`.
. Registro em INSTALLED_APPS e rota `/robo/` no urls raiz.
. Testes `tests/test_robo_matrix_tenant.py` (isolamento entre empresas, token
  invalido, integracao inativa). 3 passando.

Verificacao: `manage.py check` ok. Testes verdes. HTTP: token alpha resolve
demo-alpha, token beta resolve demo-beta, token invalido devolve 401.

Status: completed.

Proximo: Fase 1, endpoints `/proximo-passo`, `/validar`, `/recontato` traduzindo
o contrato do robo_v2 para `iniciar_por_canal` e `processar_resposta_visual`, com
golden tests comparando as respostas com o robo_v2.
