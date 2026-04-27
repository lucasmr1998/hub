---
name: "Paridade da integração HubSoft com SGP + cobertura ampla da API"
description: "Refatorar HubsoftService para o padrão do SGPService e expandir consumo da API HubSoft (catálogos, financeiro, operacional, viabilidade, atendimento bidirecional). Hoje usamos 5 de 185 endpoints disponíveis."
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Paridade integração HubSoft — 26/04/2026

**Data:** 26/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** 🔧 Em andamento (H1 concluído em 26/04/2026)

---

## Descrição

O `HubsoftService` está num patamar funcional menor que o `SGPService`, que evoluiu rápido nos últimos commits (Bloco 1+2+3 do SGP — sincronização inversa, listar títulos, operacional). Como o HubSoft é o ERP mais consumido pelos clientes do Hubtrix (Megalink, FATEPI), a defasagem é estrategicamente ruim.

Análise da Postman collection oficial (`Hubsoft API.postman_collection.json` na raiz, 185 endpoints) mostra que existe muito mais superfície disponível do que o que consumimos hoje (5 endpoints, ~3%). Várias dessas rotas resolveriam dores reais (cobrança ativa, suporte 1ª linha, viabilidade, atendimento bidirecional Inbox ↔ HubSoft).

**Objetivo desta tarefa:** trazer o `HubsoftService` pra paridade com o `SGPService` (refactor + catálogos), depois ir além expondo financeiro, operacional, viabilidade e atendimento.

---

## Tarefas

### Bloco H1 — Refactor `_request` único + limpeza estrutural (não-invasivo) ✅

- [x] Extrair `_request(method, endpoint, ...)` central em `HubsoftService`, espelhando o padrão do `SGPService._request`
- [x] Adicionar `_get`, `_post`, `_put` como wrappers do `_request` (PATCH/DELETE serão adicionados quando os blocos H4/H6 precisarem)
- [x] Centralizar `_payload_seguro` para mascarar segredos (password, token, client_secret, access_token) em log
- [x] Refatorar `obter_token`, `cadastrar_prospecto`, `consultar_cliente` para usar o novo `_request`
- [x] Mover `cadastro/contrato_service.anexar_arquivos_contrato` e `aceitar_contrato` pra dentro de `HubsoftService` como métodos próprios. `contrato_service` virou apenas orquestração (Matrix, baixar imagens, gerar PDF da conversa).
- [x] Generalizar `MATRIX_EMPRESA` hardcoded em `contrato_service.buscar_id_contrato` — agora aceita `integracao=...` e lê `configuracoes_extras['matrix']` (`url`, `empresa`), com fallback histórico pra Megalink.
- [x] Validado: `manage.py check` limpo, suite `tests/test_models_integracoes.py` + `tests/test_services_sgp.py` passa (43 testes)

### Bloco H2 — Sincronizar catálogos de configuração ✅

**Backend + UI concluídos em 26/04/2026.**

- [x] `sincronizar_servicos_catalogo` (planos) — `GET /configuracao/servico` → upsert em `ProdutoServico`. Preço fica em 0 e é preservado em re-syncs (HubSoft não traz valor em `/configuracao/servico`, só em `/cliente.servicos[].valor`).
- [x] `sincronizar_vencimentos` — `GET /configuracao/vencimento` → upsert em `OpcaoVencimentoCRM`
- [x] `sincronizar_catalogo_cacheado('vendedores')` — `GET /configuracao/vendedor` → cache em `configuracoes_extras['cache']['vendedores']`
- [x] `sincronizar_catalogo_cacheado('origens_cliente')` — `GET /configuracao/origem_cliente` → cache
- [x] `sincronizar_catalogo_cacheado('origens_contato')` — `GET /configuracao/origem_contato` → cache
- [x] `sincronizar_catalogo_cacheado('meios_pagamento')` — `GET /configuracao/meio_pagamento` → cache
- [x] `sincronizar_catalogo_cacheado('grupos_cliente')` — `GET /configuracao/grupo_cliente` → cache
- [x] `sincronizar_catalogo_cacheado('motivos_contratacao')` — `GET /configuracao/motivo_contratacao` → cache
- [x] `sincronizar_catalogo_cacheado('tipos_servico')` — `GET /configuracao/tipo_servico` → cache
- [x] `sincronizar_catalogo_cacheado('servico_status')` — `GET /configuracao/servico_status` → cache
- [x] `sincronizar_catalogo_cacheado('servicos_tecnologia')` — `GET /configuracao/servico_tecnologia` → cache
- [x] Wrapper `sincronizar_configuracoes(dry_run=False)` dispara todos em sequência, com captura de erro por catálogo (um falhar não derruba os outros)
- [x] Management command `sincronizar_catalogo_hubsoft --categoria=todos|<chave> --integracao-id --tenant --dry-run`
- [x] UI no painel `/configuracoes/integracoes/<pk>/`: card "Configuracao de cadastro automatico" com 5 selects (plano, vendedor, dia de vencimento, origem cliente, origem servico) populados pelo cache HubSoft + card "Catalogos sincronizados" com 11 linhas e botão "Sincronizar tudo". APIs `api_integracao_defaults` e `api_integracao_sincronizar_catalogo` aceitam HubSoft (antes só SGP). Features de sync hubsoft expandidas para incluir `sincronizar_planos/vencimentos/vendedores`.

### Bloco H3 — Financeiro (escopo enxuto, aprovado em 26/04/2026)

**Backend concluído.** 4 endpoints essenciais implementados; 6 itens cortados de escopo após análise de cabimento.

- [x] `listar_faturas_cliente(cpf_cnpj | id_cliente | codigo_cliente, apenas_pendente, limit, order_*)` — `GET /cliente/financeiro`
- [x] `simular_renegociacao(ids_faturas, qtd_parcelas, vencimento, ...)` — `POST /financeiro/renegociacao/simular`
- [x] `efetivar_renegociacao(...)` — `POST /financeiro/renegociacao/efetivar`
- [x] `listar_renegociacoes(cpf_cnpj, status, data_*, paginacao)` — `GET /financeiro/renegociacao`
- [x] Helper `_renegociacao_post` compartilhado entre simular/efetivar (mesmo shape)
- [ ] **Cortado de escopo:** `enviar_email/sms/push` (motor próprio do Hubtrix), `listar_faturas_admin`, `liquidar_fatura`, `conta_pagar`, `cobranca_avulsa` — fora do dominio do Hubtrix (gestao financeira interna do provedor é HubSoft direto).
- [ ] **Avaliar substituição** de `cs/clube/services/hubsoft_service.checar_pontos_extras_cpf` (SQL direto) pelo equivalente REST agora possível com `listar_faturas_cliente`. Se cobrir, deprecar o acesso direto ao banco. (Sub-tarefa, fica pra depois de validar com o CS.)
- [ ] UI no Inbox/Atendimento: ações rápidas "ver faturas em aberto", "gerar 2ª via" (link/PIX da fatura), "simular acordo". **Movido pra tarefa dedicada:** `inbox_acoes_hubsoft_26-04-2026.md`.
- [x] **Sandbox de teste no painel da integração** (`/configuracoes/integracoes/<pk>/`) — atendente/admin testa `listar_faturas_cliente` e `listar_renegociacoes` por CPF antes de plugar nos fluxos finais.

### Bloco H4 — Operacional / suporte de 1ª linha ✅

**Backend concluído em 26/04/2026.** UI no Inbox vai pra tarefa dedicada.

- [x] `verificar_extrato_conexao(busca, termo_busca, limit, data_*)` — `GET /cliente/extrato_conexao`. Busca por login/ipv4/ipv6_wan/ipv6_lan/mac. Disponível tambem no Sandbox da pagina de detalhe da integracao.
- [x] `solicitar_desconexao(id_cliente_servico)` — `GET /cliente/solicitar_desconexao/<id>`
- [x] `desbloqueio_confianca(id_cliente_servico, dias_desbloqueio)` — `POST /cliente/desbloqueio_confianca`
- [x] `suspender_servico(id_cliente_servico, tipo_suspensao)` — `POST /cliente/cliente_servico/suspender/:id`
- [x] `habilitar_servico(id_cliente_servico, motivo_habilitacao)` — `POST /cliente/cliente_servico/habilitar/:id`
- [x] `ativar_servico(id_cliente_servico)` — `POST /cliente/cliente_servico/ativar/:id`
- [x] `reset_mac_addr(id_cliente_servico)` — `POST /cliente/reset_mac_addr`
- [x] `reset_phy_addr(id_cliente_servico)` — `POST /cliente/reset_phy_addr`
- [ ] Plugar essas operações no Inbox/Atendimento como ações rápidas — **movido pra tarefa dedicada `inbox_acoes_hubsoft_26-04-2026.md`**. Acoes destrutivas (suspender/reset/desbloqueio) NAO entram no Sandbox da pagina de gerenciamento — so no Inbox com permissao.

### Bloco H5 — Viabilidade e cobertura

- [ ] `consultar_viabilidade_endereco(cep, numero, ...)` — `POST /mapeamento/viabilidade/consultar`
- [ ] `consultar_viabilidade_coords(lat, lng)` — `POST /mapeamento/viabilidade/consultar`
- [ ] `listar_planos_disponiveis_cep(cep)` — `GET /prospecto/create?cep=` (combina viabilidade + filtro de plano)
- [ ] Integrar no fluxo de cadastro de lead em `apps/comercial/viabilidade/` — substitui consulta manual

### Bloco H6 — Atendimento bidirecional Inbox ↔ HubSoft

- [ ] `criar_atendimento_hubsoft(lead, payload)` — `POST /atendimento`
- [ ] `editar_atendimento(id, payload)` — `PUT /atendimento/:id`
- [ ] `adicionar_mensagem_atendimento(id, mensagem, anexos)` — `POST /atendimento/adicionar_mensagem/:id`
- [ ] `adicionar_anexo_atendimento(id, file)` — `POST /atendimento/adicionar_anexo/:id`
- [ ] `listar_atendimentos_cliente(cpf, ...)` — `GET /cliente/atendimento`
- [ ] `abrir_os_a_partir_de_atendimento(id_atendimento)` — `POST /ordem_servico/abrir_os?id_atendimento=`
- [ ] `agendar_os(payload)` — `POST /ordem_servico/agendar`
- [ ] `consultar_horarios_disponiveis_agenda(...)` — `GET /ordem_servico/horarios_disponiveis_agenda`
- [ ] Espelhar conversa do Inbox no atendimento HubSoft (sync bidirecional, não destrutivo)

### Bloco H7 — Testes e documentação

- [ ] Cobertura unitária para H1 (refactor `_request`, mascaramento de credencial, log)
- [ ] Cobertura para H2 (sincronização de catálogos com mock de response)
- [ ] Cobertura para H3 (financeiro, renegociação)
- [ ] Cobertura para H4 (suspender/habilitar/ativar, reset MAC)
- [ ] Cobertura para H5 (viabilidade)
- [ ] Cobertura para H6 (atendimento, OS)
- [ ] Atingir paridade com os 27 testes do `SGPService`
- [ ] Atualizar `robo/docs/PRODUTO/integracoes/01-HUBSOFT.md` em cada bloco que entregar

---

## Ordem sugerida e gating

```
H1 (refactor) → H2 (catálogos) → H3 (financeiro) → H5 (viabilidade)
                                       ↓                  ↓
                                       H4 (operacional) → H6 (atendimento)
                                                            ↓
                                                            H7 (testes finais)
```

H1 é gating duro — sem `_request` único, todos os outros blocos duplicam boilerplate e ficam difíceis de testar.

H2 é gating pra UI — sem catálogos sincronizados, os defaults da integração continuam sendo JSONField editado a mão.

---

## Antes de cada bloco

1. **Extrair shape do payload e response da Postman collection**. Cada item da collection tem exemplo de request/body e response — usar como fonte da verdade para evitar o que aconteceu com o `consultacliente` do SGP (shape descoberto só em produção).
2. **Validar com integração real do FATEPI** ou Megalink antes de marcar como entregue.
3. **Atualizar `01-HUBSOFT.md`** ao fechar o bloco (regra do CLAUDE.md).

---

## Contexto e referências

- `robo/dashboard_comercial/gerenciador_vendas/apps/integracoes/services/hubsoft.py` — service atual (727 linhas)
- `robo/dashboard_comercial/gerenciador_vendas/apps/integracoes/services/sgp.py` — referência de paridade (932 linhas, 27 testes)
- `Hubsoft API.postman_collection.json` — collection oficial (185 endpoints) na raiz do repo
- `robo/docs/PRODUTO/integracoes/01-HUBSOFT.md` — doc do módulo (atualizada com cobertura real e débitos técnicos)
- `robo/docs/PRODUTO/integracoes/05-SGP.md` — referência do que já foi feito no SGP
- Commits SGP referência: `528da1b` (testes), `20e80de` (Bloco 3 operacional), `87ea396` (Bloco 2 financeiro), `10f850b` (Bloco 1 sincronização inversa)
- Tarefa relacionada: `discovery_sgp_gigamax_23-04-2026.md` (mostra o método aplicado ao SGP)
- Tarefa relacionada: `resiliencia_integracoes_erp_17-04-2026.md`

---

## Resultado esperado

- `HubsoftService` no mesmo nível arquitetural do `SGPService` (`_request` central, `_payload_seguro`, mascaramento padronizado).
- Cobertura de endpoints HubSoft sai de 5/185 (~3%) para ~30/185 (~16%) cobrindo as áreas que importam pro Hubtrix: comercial, cobrança, suporte, viabilidade, atendimento.
- Painel de configuração da integração HubSoft em `/configuracoes/integracoes/<pk>/` com selects populados por cache (catálogos sincronizados), botão "sincronizar catálogos" e botão "testar conexão" funcionais.
- `cadastro/contrato_service` extinto, fluxo absorvido pelo `HubsoftService`.
- Inbox/Atendimento com ações rápidas HubSoft (suspender, habilitar, reset MAC, anexar documento, abrir OS).
- Cobertura de testes equivalente aos 27 do `SGPService`.
- Acesso direto ao banco PostgreSQL do HubSoft (`cs/clube/services/hubsoft_service.py`) **avaliado para deprecação** em favor da API REST de financeiro.
