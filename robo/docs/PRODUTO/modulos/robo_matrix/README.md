# Modulo robo_matrix (adaptador de contrato Matrix)

App `apps/comercial/robo_matrix`. Expoe o contrato da API do robo_v2 (consumida
pela plataforma de bot Matrix) por cima do motor nativo de atendimento do Hubtrix,
de forma multi-empresa. O mesmo flow do Matrix roda em varias empresas: so o
prefixo da URL (`/robo/<token>/ia/...`) muda, e o `<token>` (api_token de uma
IntegracaoAPI ativa) identifica o tenant. O corpo do payload permanece identico
ao do robo_v2.

## Por que
O robo_v2 (projeto techub) e single-tenant e cheio de parametros fixos por
empresa (persona, planos, IDs HubSoft, credenciais). Trazendo so a casca do
contrato para o Hubtrix e resolvendo tudo por tenant (motor de atendimento visual,
catalogo HubSoft sincronizado, configuracoes_extras da IntegracaoAPI, Agente + RAG),
a venda automatica passa a ser configuravel por empresa sem fork de codigo.

## Arquivos
- `PLANO.md` plano de construcao em fases (Fase 0 a 7).
- `execution-log.md` trilha do que foi executado.
- `referencia_robo_v2/` documentacao de referencia do robo_v2 (origem do porte).
  Contrato da API, arquitetura e integracao Matrix. Copias limpas: contem apenas
  exemplos sinteticos (CPF de teste, telefones placeholder), sem PII real nem
  segredos.

## Estado
Fase 0 concluida: app criado, resolucao de tenant por token na URL, endpoint de
diagnostico `/ia/ping`, seed de dev e testes de isolamento. Ver `execution-log.md`.
