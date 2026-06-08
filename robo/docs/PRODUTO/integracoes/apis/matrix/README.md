# Matrix Brasil — API (Chatbots & IA)

Plataforma omnichannel da Matrix Brasil (`matrixdobrasil.ai`). E o sistema que a **Nuvyon** usa pra atender clientes via WhatsApp (instancia em `nuvyon.matrixdobrasil.ai`). Tambem pode ser usada como **broker de disparo** (HSM, livre, SMS) se o tenant nao tiver uazapi proprio.

## Quando o Hubtrix interage com a Matrix

| Caso | Direcao | Quem chama quem |
|---|---|---|
| Cliente conversa com a Matrix da Nuvyon (atendimento humano/bot) | n/a | Tudo dentro da Matrix, Hubtrix nao participa |
| Matrix da Nuvyon precisa **abrir atendimento HubSoft** ou consultar agenda/datas | Matrix -> Hubtrix | Matrix chama `https://app.hubtrix.com.br/api/public/n8n/matrix/*` (ver [n8n-hubtrix/](../n8n-hubtrix/README.md)) |
| Hubtrix quer **disparar HSM** pro cliente Nuvyon (notificacao de contrato, boleto, etc) | Hubtrix -> Matrix | Hubtrix chama `POST /rest/v1/sendHsm` da Matrix Nuvyon |
| Hubtrix quer **acompanhar status de mensagem** disparada | Hubtrix -> Matrix | `GET /rest/v2/hsmEnviadas` |

## Base URL

Por tenant:
- Nuvyon: `https://nuvyon.matrixdobrasil.ai`
- Outros tenants Matrix Brasil: `https://<tenant>.matrixdobrasil.ai`

A URL base **e por instancia** — sempre vem do `IntegracaoAPI.base_url` do tenant.

## Auth

Duas opcoes (depende da versao):

| Versao | Header | Valor |
|---|---|---|
| v1 | `Authorization` | API Key crua (sem prefixo `Bearer`) |
| v2 | `Authorization` | `Bearer <jwt>` — obtido via `POST /rest/v2/authuser` (`login` + `chave`) |

**v2 e o caminho recomendado.** O JWT do v2 tem validade curta (1h em geral); estrategia: cachear o token + refresh quando expirar.

Onde pegar credenciais:
- UI da Matrix da empresa: Sistema > Configuracoes > aba Integracoes > "Copiar token" (v1)
- Pra v2: usuario + chave de API (configurados na Matrix)

## Versoes

A API tem **v1** (`/rest/v1/...`) e **v2** (`/rest/v2/...`). Em geral:
- v2 reescreve endpoints v1 com auth bearer
- v2 acrescenta endpoints novos (auth, agentes, voz, catalogos, dialogoWhatsapp)
- v1 segue funcional mas alguns endpoints estao marcados como deprecados (ex.: `mensagemAlt`, `mensagemInteg` — descontinuados em 2023-12-31)

Diretriz: **novas integracoes Hubtrix devem usar v2**.

## Estrutura desta doc

| Arquivo | Cobertura |
|---|---|
| [01-atendimento-mensagens.md](01-atendimento-mensagens.md) | Criar atendimento, enviar msg em atendimento existente, transferir humano, finalizar, agendar |
| [02-disparos.md](02-disparos.md) | `sendHsm`, `dialogoWhatsapp`, `sendSms` — **iniciar conversa do nosso lado** |
| [03-contato-blocklist.md](03-contato-blocklist.md) | Criar/alterar contato, blacklist/blocklist |
| [04-relatorios-agente-voz.md](04-relatorios-agente-voz.md) | Agente, relatorios analiticos, integracao voz, catalogo, tabela generica |
| [endpoints-summary.json](endpoints-summary.json) | **Lista estruturada** de TODOS endpoints v1+v2 com path/method/desc — util pra grep/lookup rapido |
| `Chatbots-IA-API.postman_collection.json` | Collection Postman oficial bruta (a dropar — ver [.README.md](Chatbots-IA-API.postman_collection.json.README.md)) |

## Formato de erro padrao

```json
{
  "cod_error": 1,
  "msg": "sem autorizacao"
}
```

Codigos HTTP usados:
- `200` sucesso
- `400` erro generico (auth invalida, payload errado)
- `401` token invalido (v2)
- `403` token nao informado
- `404` recurso nao encontrado
- `412` erro de validacao de parametros

## Codigos de canal (`cod_integracao` / `id_canal`)

Tabela referencia usada em varios endpoints:

| ID | Canal |
|---|---|
| 1 | WhatsApp |
| 7 | E-mail |
| 9 | SMS |
| 10 | Telegram |
| 11 | BotTelegram |
| 13 | Viber |
| 14 | BotSkype |
| 15 | Voz |
| 17 | Presencial |
| 18 | API |
| 19 | Workplace |
| 20 | Slack |
| 22 | Hangouts |
| 24 | Reclame Aqui |
| 25 | Instagram |

## Status de atendimento

| ID | Status |
|---|---|
| 1 | Aguardando atendimento |
| 2 | Em atendimento |
| 3 | Finalizado |
| 4 | Desconexao em fila |
| 5 | Cancelado |
| 6 | Transferido |
| 7 | Automatico |
| 8 | Abandonado |
| 9 | Finalizado por inatividade |
| 10 | Abandono - Redirecionado |
| 11 | Atendimento Pendente |
| 12 | Finalizado por desconexao |
| 13 | Em pesquisa |
| 14 | Transferido pendencia (fila prioritaria) |
| 15 | Transferido pra automatico |

---

**Versao da collection:** capturada em 2026-06-07 (Postman exporter 38602602).
**Origem:** [Chatbots-IA-API.postman_collection.json](Chatbots-IA-API.postman_collection.json) — substituir esse arquivo quando o provider publicar versao nova; atualizar esta linha com a data.
