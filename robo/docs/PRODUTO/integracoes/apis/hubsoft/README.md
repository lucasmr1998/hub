# HubSoft — API

ERP/ISP usado pela **Nuvyon** (unico tenant em prod com HubSoft ativo hoje). Cobre clientes, contratos, OS, financeiro, viabilidade, agenda, catalogos.

Doc consolidada de produto (visao + decisoes): [../../01-HUBSOFT.md](../../01-HUBSOFT.md). Esta pasta detalha **endpoints HTTP por dominio**.

## Base URL

`https://api.<dominio-cliente>.hubsoft.com.br/api/v1/`

Exemplo Nuvyon: `https://api.artelecom.hubsoft.com.br/api/v1/integracao/`

Vem do `IntegracaoAPI.base_url` por tenant.

## Auth

**OAuth2 password grant.** Endpoint `POST /oauth/token`:

```bash
curl -X POST 'https://api.artelecom.hubsoft.com.br/oauth/token' \
  -H 'Content-Type: application/json' \
  -d '{
    "grant_type": "password",
    "client_id": "<client_id>",
    "client_secret": "<client_secret>",
    "username": "<api_user>",
    "password": "<api_password>"
  }'
```

Retorno:
```json
{ "access_token": "...", "token_type": "Bearer", "expires_in": 3600, "refresh_token": "..." }
```

Demais chamadas: header `Authorization: Bearer <access_token>`.

Wrapper Python: [apps/integracoes/services/hubsoft.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/hubsoft.py) — classe `HubsoftService`. Faz cache do token em `IntegracaoAPI.access_token` + `token_expira_em`, renova quando faltam <60s. `_request()` centraliza todas as chamadas com mascaramento de logs.

## Permissoes HubSoft requeridas

A credencial precisa ter no painel de **Usuarios da API** do HubSoft:

- Consultar cliente
- Cadastrar prospecto
- Consultar agenda OS
- **Criar atendimento** (pra `/abrir-atendimento/`)
- **Abrir OS** (pra `/abrir-os/`)
- Consultar/anexar contrato
- Consultar financeiro + renegociacao
- Consultar viabilidade
- Operacoes (suspender/habilitar/ativar/reset MAC/desbloqueio)

Erros de permissao chegam como HTTP 403 com `"O Usuário não possui a permissão desejada!"` na `msg`.

## Estrutura desta doc

| Arquivo | Cobertura |
|---|---|
| [01-clientes-contratos.md](01-clientes-contratos.md) | `prospecto`, `cliente`, `contrato/adicionar_anexo_contrato`, `contrato/aceitar_contrato`, `contrato/adicionar_contrato`, `configuracao/modelo_contrato`, `configuracao/empresa` |
| [02-atendimento-os.md](02-atendimento-os.md) | Atendimento + OS (abrir, listar, consultar agenda), listar OS do cliente |
| [03-financeiro.md](03-financeiro.md) | `cliente/financeiro`, `financeiro/renegociacao`, `simular`, `efetivar` |
| [04-operacional.md](04-operacional.md) | `extrato_conexao`, `solicitar_desconexao`, `desbloqueio_confianca`, `reset_mac_addr`, `reset_phy_addr`, `cliente_servico/suspender|habilitar|ativar` |
| [05-viabilidade.md](05-viabilidade.md) | `mapeamento/viabilidade/consultar` (endereco e coords) |
| [06-catalogos.md](06-catalogos.md) | 11 catalogos cacheados localmente (`servico`, `vencimento`, `vendedor`, `origem_cliente`, etc) |

## Formato de erro padrao

```json
{ "status": "error", "msg": "Mensagem do HubSoft" }
```

Codigos HTTP: `200` sucesso, `400` payload invalido, `401/403` permissao, `404` recurso, `422` validacao.

Wrapper levanta `HubsoftServiceError` em qualquer `status != success` ou HTTP >=400 (excluindo 422 que retorna estruturado).

## Cobertura atual

A Postman collection oficial tem ~185 endpoints. Hubtrix consome **~32 (~17%)**. Detalhes da paridade em [../../01-HUBSOFT.md#cobertura-real-da-api-hubsoft](../../01-HUBSOFT.md#cobertura-real-da-api-hubsoft).

## Configuracao por tenant

Em `IntegracaoAPI.configuracoes_extras['hubsoft']`:

```json
{
  "id_origem_padrao": 12,
  "vendedor_id_padrao": 7,
  "id_contrato_modelo": 236,
  "id_empresa_padrao": 74,
  "dias_vencimento_permitidos_hubsoft": [5, 10, 15, 20, 25],
  "os_matrix": {
    "id_agenda_ordem_servico": 46,
    "id_tipo_atendimento": 281,
    "id_status_atendimento": 1,
    "id_tipo_os": 4,
    "status_os": "pendente",
    "id_usuario_responsavel": null
  },
  "cache": { /* dados de catalogos cacheados */ },
  "modos_sync": {
    "enviar_lead": "automatico",
    "sincronizar_cliente": "automatico",
    "sincronizar_servicos": "automatico",
    "sincronizar_planos": "automatico",
    "sincronizar_vencimentos": "automatico",
    "sincronizar_vendedores": "automatico",
    "anexar_documentos_contrato": "automatico",
    "aceitar_contrato": "automatico"
  }
}
```

## Versionamento da doc

Quando o HubSoft publicar versao nova da Postman collection: substituir `Hubsoft-API.postman_collection.json` (a criar) e atualizar data nesta linha.

**Versao da doc:** 2026-06-07 — capturada via codigo (`HubsoftService` + `urls_n8n_public.py`) e doc legada `01-HUBSOFT.md`.
