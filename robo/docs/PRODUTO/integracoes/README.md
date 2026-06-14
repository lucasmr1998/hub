# Integracoes — indice

Documentacao das integracoes externas do Hubtrix. Tem duas camadas:

1. **Docs de produto/decisao** (este nivel): visao geral, decisoes arquiteturais, dicionario de dados, runbooks.
2. **Docs de API** (`apis/`): referencia tecnica por provider — endpoints, payloads, exemplos curl, collection Postman bruta.

## Por provider (visao consolidada)

| Tema | Arquivo |
|---|---|
| HubSoft (Nuvyon) — visao completa | [01-HUBSOFT.md](01-HUBSOFT.md) |
| Lista geral de integracoes (uazapi, N8N, providers IA, etc) | [02-INTEGRACOES.md](02-INTEGRACOES.md) |
| Endpoints publicos do Hubtrix chamados pelo N8N | [03-APIS_N8N.md](03-APIS_N8N.md) |
| Guia pra integrar novo ERP (Gigamax, futuros) | [04-GUIA-NOVA-INTEGRACAO-ERP.md](04-GUIA-NOVA-INTEGRACAO-ERP.md) |
| Pipeline contrato HubSoft Nuvyon (regra `gerar_contrato_hubsoft`) | [05-PIPELINE-HUBSOFT-NUVYON.md](05-PIPELINE-HUBSOFT-NUVYON.md) |
| SGP (inSystem) — Gigamax | [05-SGP.md](05-SGP.md) |
| Deploy bot Selenium Nuvyon (EasyPanel) | [06-DEPLOY-BOT-NUVYON.md](06-DEPLOY-BOT-NUVYON.md) |
| Painel de Ordens de Servico (tentativas via Matrix) | [07-ORDENS-SERVICO.md](07-ORDENS-SERVICO.md) |
| Painel de Contratos (tentativas de criar/aceitar contrato HubSoft) | [08-CONTRATOS.md](08-CONTRATOS.md) |

## Referencia tecnica de API

`apis/` agrupa **endpoints HTTP detalhados por provider** com curl, payloads, observacoes de uso no Hubtrix e collection Postman bruta. E onde olhar quando precisa saber "qual o JSON que eu mando pra criar contrato HubSoft" ou "como eu disparo HSM via Matrix".

| Provider | Estado | Pasta |
|---|---|---|
| **Matrix Brasil** (Chatbots & IA) | Doc completa V1+V2 | [apis/matrix/](apis/matrix/README.md) |
| **HubSoft** | Placeholder — usar [01-HUBSOFT.md](01-HUBSOFT.md) por enquanto | [apis/hubsoft/](apis/hubsoft/README.md) |
| **uazapi** | Placeholder | [apis/uazapi/](apis/uazapi/README.md) |
| **N8N (endpoints Hubtrix expostos)** | Placeholder — ver tambem [03-APIS_N8N.md](03-APIS_N8N.md) | [apis/n8n-hubtrix/](apis/n8n-hubtrix/README.md) |

Ver tambem [apis/README.md](apis/README.md) pra convencoes e roadmap.

## Onde estao as credenciais (por tenant)

Tudo em `IntegracaoAPI` (model em [apps/integracoes/models.py](../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/models.py)):

- `tenant` FK
- `tipo` (`hubsoft`, `matrix`, `uazapi`, `n8n`, etc)
- `base_url`
- `token` (Fernet-encrypted) ou OAuth client_id/secret em `configuracoes_extras`
- `configuracoes_extras` (JSON com dicionario de config por provider — ex.: HubSoft tem `os_matrix`, `id_origem_padrao`, `cache`, `modos_sync`, `dias_vencimento_permitidos_hubsoft`, `id_contrato_modelo`, `id_empresa_padrao`, `vendedor_id_padrao`)
- `ativa` bool

Filtragem obrigatoria por `tenant` em todas as queries — ver regra em [CLAUDE.md](../../../../CLAUDE.md#multi-tenancy-critico).
