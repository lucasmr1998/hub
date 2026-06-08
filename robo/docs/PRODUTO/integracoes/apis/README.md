# APIs externas — referência consolidada

Cada subpasta concentra a documentação de UMA API externa que o Hubtrix consome (ou pode consumir). Mantemos aqui:

- **README.md** por provider — visão geral, auth, base URLs, versionamento
- **Docs temáticos** quebrados por dominio (atendimento, contato, disparos etc), com curl/exemplos e observações de uso no Hubtrix
- **Collection bruta** (Postman/OpenAPI) quando o fornecedor disponibiliza, versionada junto

Quando uma API for usada por algum modulo do produto, linkar daqui pra `robo/docs/PRODUTO/modulos/<modulo>/...` (e vice-versa).

---

## Providers documentados

| Provider | Estado | O que e | Quem usa hoje | Doc |
|---|---|---|---|---|
| **HubSoft** | ✅ completa (6 docs) | ERP/ISP (clientes, contratos, OS, financeiro, viabilidade, catalogos) | Nuvyon (prod) | [hubsoft/](hubsoft/README.md) |
| **Matrix Brasil** | ✅ completa (4 docs + JSON resumo) | Plataforma omnichannel (Chatbots & IA) — WhatsApp, SMS, Voz | Nuvyon (Matrix proprio dela em `matrixdobrasil.ai/nuvyon`) | [matrix/](matrix/README.md) |
| **N8N (Hubtrix endpoints)** | ✅ completa (6 docs) | Endpoints publicos do Hubtrix chamados pelo N8N/Matrix | TR Carrion (Vero), Nuvyon (Matrix) | [n8n-hubtrix/](n8n-hubtrix/README.md) |
| **uazapi** | 🟡 placeholder | Provedor WhatsApp nao-oficial | aurora-hq, fatepifaespi | [uazapi/](uazapi/README.md) |

---

## Convencoes

- **Auth**: cada provider documenta o cabecalho/parametro de auth no seu README.
- **Tenancy**: toda chamada a API externa **deve** carregar credencial do tenant correto (vinda de `IntegracaoAPI.configuracoes`). Nunca hardcoded.
- **Erros**: documentamos sempre o formato de erro retornado pelo provider (ex.: HubSoft retorna `{status, msg}`; Matrix retorna `{cod_error, msg}`).
- **Versionamento**: Matrix tem v1 e v2. Preferir v2 pra implementacoes novas (auth bearer + escopo melhor definido).

---

## Como atualizar

1. Quando o provider mudar (release notes, novo endpoint, deprecacao): atualizar a doc do dominio afetado + o `README.md` do provider.
2. Quando trocar a versao da collection: substituir o JSON e marcar a data + versao no README do provider.
3. Mexer no nosso lado (ex.: novo wrapper em `apps/integracoes/services/`): linkar o codigo daqui (`file_path:linha`).
