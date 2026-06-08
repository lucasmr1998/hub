# HubSoft API — Operacional

Endpoints que atuam **diretamente sobre o servico do cliente** (suspender, ativar, resetar MAC etc). Acoes destrutivas. UI no painel `/configuracoes/integracoes/<pk>/` aba **Sandbox** tem `confirm()` JS antes de disparar.

## Extrato de conexao

`GET /api/v1/integracao/cliente/extrato_conexao?id_cliente_servico=<id>` (e demais filtros)

Retorna historico de conexao/desconexao do servico (uteis pra diagnosticar quedas).

Service: `HubsoftService.verificar_extrato_conexao(id_cliente_servico)`.

---

## Solicitar desconexao do cliente

`GET /api/v1/integracao/cliente/solicitar_desconexao/{id_cliente_servico}`

Apesar do `GET`, **dispara desconexao** no provedor (limitacao da API HubSoft).

Service: `HubsoftService.solicitar_desconexao(id_cliente_servico)`.

---

## Desbloqueio de confianca

`POST /api/v1/integracao/cliente/desbloqueio_confianca`

Concede acesso ao cliente mesmo com fatura em atraso (tempo limitado, definido na config do HubSoft).

### Body

```json
{ "id_cliente_servico": 57515 }
```

Service: `HubsoftService.desbloqueio_confianca(id_cliente_servico)`.

---

## Reset MAC address

`POST /api/v1/integracao/cliente/reset_mac_addr`

Limpa o MAC associado ao servico — usado quando cliente troca de equipamento e provedor precisa "esquecer" o antigo.

### Body

```json
{ "id_cliente_servico": 57515 }
```

Service: `HubsoftService.reset_mac_addr(id_cliente_servico)`.

---

## Reset PHY address

`POST /api/v1/integracao/cliente/reset_phy_addr`

Equivalente ao MAC reset mas pra PHY (camada fisica — usado em fibra/GPON).

Service: `HubsoftService.reset_phy_addr(id_cliente_servico)`.

---

## Suspender servico

`POST /api/v1/integracao/cliente/cliente_servico/suspender/{id}`

Suspende temporariamente sem cancelar. Mantem dados pra reativar.

Service: `HubsoftService.suspender_servico(id_cliente_servico)`.

---

## Habilitar servico

`POST /api/v1/integracao/cliente/cliente_servico/habilitar/{id}`

Reativa servico suspenso.

Service: `HubsoftService.habilitar_servico(id_cliente_servico)`.

---

## Ativar servico (primeira ativacao)

`POST /api/v1/integracao/cliente/cliente_servico/ativar/{id}`

Liga servico pela primeira vez (apos instalacao e validacao tecnica).

Service: `HubsoftService.ativar_servico(id_cliente_servico)`.

---

## Quando usar cada acao

| Cenario | Endpoint |
|---|---|
| Cliente vai mudar de equipamento | `reset_mac_addr` + `reset_phy_addr` |
| Cliente em atraso > grace period | `solicitar_desconexao` |
| Cliente pediu "promessa de pagamento" | `desbloqueio_confianca` |
| Cancelamento temporario (ferias, viagem) | `suspender_servico` |
| Retorno de cancelamento temporario | `habilitar_servico` |
| Instalacao concluida + validada | `ativar_servico` |
| Cancelamento definitivo | (nao tem endpoint REST — feito no painel HubSoft) |

---

## Permissoes

Cada endpoint destrutivo exige permissao especifica liberada no painel **Usuarios da API** do HubSoft. Erros HTTP 403 voltam como `400` com `"O Usuário não possui a permissão desejada!"` (limitacao do EasyPanel — ver [02-atendimento-os.md#por-que-4xx](02-atendimento-os.md#por-que-4xx-mesmo-pra-erro-hubsoft)).

## Logs

Todas acoes destrutivas geram `LogIntegracao` com `tipo='acao'` (vs `tipo='consulta'`). Filtrar logs por `tipo=acao` pra auditar quem operou o que e quando.
