# Tarefa — API Health (saude de integracoes)

**Status:** backlog
**Aberta em:** 2026-04-25
**Origem:** sessao Gigamax/SGP — debug do bug de criptografia. Usuario quis garantia "daqui pra frente nao quebra mais com APIs".

## Problema

Hoje, quando uma integracao quebra (token revogado, endpoint mudou, permissao removida), a falha so aparece quando alguma rota interna tenta usar a API. O tenant nao sabe ate ouvir do usuario final ou ver erro no fluxo. Diagnostico e demorado (precisa ler `LogIntegracao` no admin, decifrar HTTP code).

## Escopo

### 1. Botao "testar conexao" na UI de integracoes
Ao salvar credenciais OU sob demanda, chamar `service.validar_credenciais()` da `IntegracaoAPI` (metodo que cada adapter ja tem). Mostrar resultado imediato no painel (verde / vermelho com motivo).

Endpoints novos:
- `POST /configuracoes/integracoes/<pk>/testar/` -> dispara `service.validar_credenciais()` e retorna `{ok, mensagem, http_code}`

### 2. Daily smoke test de todas integracoes ativas
Cron diario que roda `validar_credenciais()` em cada `IntegracaoAPI(ativa=True)`. Em caso de falha:
- Marca `IntegracaoAPI.health_status='falha'` (campo novo)
- Cria notificacao no painel do tenant (sino) — usar `apps.notificacoes`
- Email pro admin do tenant se `health_status` mudar de OK pra falha

Command novo:
- `python manage.py auditar_integracoes` (rodavel manual + via cron)

### 3. Indicador visual no painel de integracoes
Badge ao lado de cada integracao mostrando: 🟢 OK | 🟡 nunca testada | 🔴 falhou (data/hora + motivo)

### 4. Tela de "saude geral" (opcional)
`/configuracoes/integracoes/saude/` — dashboard listando todas integracoes do tenant + status atual + ultima verificacao.

## Premissas

- Cada `*Service` tem ou vai ter `validar_credenciais()` implementado (HubsoftService ja tem, SGPService ja tem). Padronizar interface.
- `LogIntegracao` ja loga toda chamada — usar como fonte de verdade pra historico.

## Fora de escopo

- Auto-renovacao de token (cada API tem politica diferente — fazer caso a caso depois)
- SLA / metricas de performance (entra em "monitoramento de integracoes" futuro)

## Validacao

- Fluxo: criar integracao com token errado de proposito -> botao "testar" mostra erro claro
- Fluxo: integracao com token bom -> badge verde + sem notificacao
- Fluxo: revogar token externo -> proximo cron detecta -> notificacao aparece pro admin
