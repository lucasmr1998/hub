# Paridade integração HubSoft com SGP — 27/04/2026

**Data:** 27/04/2026
**Participantes:** Lucas + Tech Lead/PM (sessão IA)
**Duração:** ~6h (sessão intensiva)

---

## Contexto

A integração HubSoft do Hubtrix estava em patamar funcional menor que a SGP, que evoluiu rápido nos commits anteriores (Bloco 1+2+3 SGP — sincronização inversa, listar títulos, operacional). Como o HubSoft é o ERP mais consumido pelos clientes do Hubtrix (Megalink, FATEPI), a defasagem era estrategicamente ruim.

A sessão começou com pedido de análise comparativa entre SGP e HubSoft. Evoluiu para inventário completo da Postman collection oficial (185 endpoints), análise das integrações HubSoft já existentes no sistema, e execução de plano de paridade em 7 blocos (H1–H7).

---

## Principais pontos discutidos

### Análise inicial — gaps HubSoft × SGP

- HubSoft consumia apenas **5 dos 185 endpoints** disponíveis (~3%).
- Boilerplate HTTP duplicado em 4 métodos (sem `_request` único).
- Campos hardcoded em 2 lugares — sem ponte com `CampoCustomizado` do CRM.
- `contrato_service` reimplementava auth/log fora do `HubsoftService`.
- `MATRIX_EMPRESA = "megalink"` hardcoded — não funciona pra outros provedores HubSoft.
- Acesso direto ao banco PostgreSQL HubSoft (cs/clube) sem multi-tenancy.
- Cobertura de testes baixa.

### O que HubSoft já tinha à frente do SGP

- Detecção de alterações entre syncs (`houve_alteracao` + `historico_alteracoes`).
- Normalização inteligente de comparação (`_valores_iguais`).
- Modelagem rica de serviços (`ServicoClienteHubsoft`).

### Postman collection — endpoints relevantes pro Hubtrix

Levantados por categoria:
- **Catálogos de configuração** (11 endpoints `/configuracao/*`)
- **Financeiro** (4 endpoints úteis — corte de 6 que não cabem)
- **Operacional** (8 endpoints — extrato + 7 ações)
- **Viabilidade** (2 endpoints — endereço e CEP)
- **Atendimento/OS** (originalmente 8 — depois reduzido a 2 quando definimos que Inbox não seria adotado)

### Mudanças de premissa durante a sessão

1. **Inbox descartado** — provedores não vão usar o Inbox do Hubtrix por enquanto. Isso invalidou parte do H6 (atendimento bidirecional) e a tarefa `inbox_acoes_hubsoft_*` (que ficou bloqueada).
2. **Mapeamento ERP fica depois do H7** — eu (Tech Lead) tinha proposto encaixar entre H4 e H5; o usuário argumentou que H5/H6 não dependem dele tanto assim, então melhor fechar a paridade primeiro e fazer mapeamento como meta-melhoria depois.
3. **H6 reduzido a leitura** — só `listar_atendimentos_cliente` e `listar_os_cliente` foram implementados; criar/editar/abrir OS ficam bloqueados até Inbox ser adotado.

### Bug fix encontrado durante a sessão

Tela `/comercial/configuracoes/campos-leads/` criava `CampoCustomizado` sem `tenant=request.tenant` (usava `objects.create()` direto). `TenantManager` filtra leituras automaticamente, mas em creates o tenant precisa ser passado explicitamente. Query em produção mostrou 1 registro, com `tenant_id=3`, sem órfãos. Corrigido.

---

## Decisões tomadas

| Decisão | Motivo |
|---------|--------|
| Refatorar `HubsoftService` com `_request` único antes de qualquer feature nova (H1) | Sem isso, blocos H2–H6 duplicariam boilerplate; não testável de forma limpa |
| Mover anexar/aceitar contrato pra dentro do `HubsoftService` | Eliminar duplicação de auth/log; padronizar auditoria |
| Generalizar `MATRIX_EMPRESA` via `configuracoes_extras['matrix']` | Permitir outros provedores HubSoft (não só Megalink) |
| Cortar de escopo `enviar_email/sms/push` no H3 | Hubtrix tem motor próprio de notificações |
| Cortar `liquidar_fatura`, `conta_pagar`, `cobranca_avulsa` | Gestão financeira interna do provedor — fora do domínio Hubtrix |
| Ações destrutivas H4 NÃO entram no Sandbox sem `confirm()` | Perigosas demais — só com confirmação explícita do usuário |
| H6 reduzido a leitura (só `listar_atendimentos`/`listar_os`) | Inbox não será adotado pelos provedores; bidirecional perdeu sentido |
| Mapeamento ERP fica depois do H7 | Visão completa do uso real informa melhor o desenho do mapeamento |
| Default = `automatico` em todas as features de sync | Preserva comportamento atual de tenants existentes |

---

## Entregáveis (commits desta sessão)

| Commit | Bloco | Conteúdo |
|---|---|---|
| `eb5e499` | H1 | `_request` único + extração `contrato_service` + Matrix configurável |
| `3fa138a` | H2 backend | 11 catálogos sincronizáveis + management command |
| `34f656b` | H2 UI | Selects populados por cache + botão "sincronizar tudo" |
| `5c22df5` | Polimento | Paridade visual card HubSoft com SGP |
| `9a11f22` | Bug fix | Badge component renderiza `label=0` |
| `2175fb1` | UX | Logs expansíveis com payload + resposta JSON |
| `f037982` | H3 | 4 endpoints financeiros (faturas, renegociação) |
| `3e663a2` | H3 UI | Sandbox financeiro no painel + tarefa Inbox criada |
| `08dcee3` | UX | Refactor pra tabs do design system |
| `725feac` | UX | Credenciais como primeira aba (default) |
| `3ea197e` | Bug fix | `CampoCustomizado.create` sem tenant |
| `6c6de3e` | Docs | Tarefa de mapeamento ERP criada |
| `9a46514` | H4 | 8 endpoints operacionais |
| `d1069ca` | H5 + H6 | Viabilidade + atendimento/OS leitura |
| `a8e7e73` | H7 | 41 testes (supera os 27 do SGP) |
| `6f1db08` | UX | Padronização cards na listagem |
| `3c88465` | UI | Sandbox cobre todos os endpoints H4/H5 |
| `68841f2` | Polimento | 2 features de sync novas + cron de catálogos |
| `f236309` | Docs | Atualização 02-CRON.md + 01-HUBSOFT.md |

**Cobertura final:** ~32/185 endpoints (~17%), saindo de 5/185 (~3%) no início.

---

## Pendências

| Pendência | Responsável |
|-----------|-------------|
| Tarefa `mapeamento_campos_erp_27-04-2026.md` (ponte ERP ↔ `CampoCustomizado`) | Tech Lead, próxima na fila |
| Tarefa `inbox_acoes_hubsoft_27-04-2026.md` — bloqueada até produto definir onde atendentes operam | PM |
| Avaliar deprecação do banco direto `cs/clube/services/hubsoft_service.py` em favor da REST | Tech Lead, sub-tarefa do mapeamento |
| Configurar entrada `Aurora HubSoft Catalogos` no EasyPanel (1x/dia, `--apenas-automatico`) | Ops |

---

## Próximos passos

- [ ] Iniciar tarefa de mapeamento ERP ↔ `CampoCustomizado`
- [ ] Documentar lista de campos disponíveis HubSoft (referência) em `docs/PRODUTO/integracoes/06-MAPEAMENTO-ERP.md` quando começar
- [ ] Verificar com FATEPI (cliente real HubSoft) se algum endpoint coberto cobre dor não atendida hoje
- [ ] Configurar cron de catálogos em produção depois de validar comportamento em ambiente local
