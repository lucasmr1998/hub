# Arquitetura — nível repositório

Visão de alto nível dos dois fluxos de atendimento e de como os serviços se encaixam.
Para detalhes de cada serviço, ver:
- API IA: [`ia_validacao/docs/`](../ia_validacao/docs/) — `API_REFERENCE.md`, `ARQUITETURA.md`, `INTEGRACAO_MATRIX.md`
- Django/CRM: [`dashboard_comercial/gerenciador_vendas/README.md`](../dashboard_comercial/gerenciador_vendas/README.md) e [`docs/DOCUMENTACAO_CRM.md`](DOCUMENTACAO_CRM.md)

---

## Componentes

- **Matrix** — plataforma do bot de WhatsApp. Cada nó do flow chama os endpoints HTTP.
- **nginx** — proxy: `/ia/*` → `127.0.0.1:8090/*` (FastAPI). Demais rotas → Django.
- **FastAPI** (`ia_validacao/`) — IA: valida respostas, decide o próximo passo, conversa.
- **Django** (`dashboard_comercial/gerenciador_vendas/`) — dados (leads, NewService),
  regras de validação (`RegraValidacao`), HubSoft, agendamento, logs.

A FastAPI **não tem banco**: lê/escreve no Django via HTTP (cliente `robovendas`).

---

## Fluxo 1 — Determinístico (em produção, estável)

Duas chamadas por mensagem do cliente:

1. `POST /ia/validar` → `engine.validar_por_regra` valida a resposta contra a
   `RegraValidacao` da pergunta, persiste (via `_alvo`), dispara hooks (Hubsoft,
   agendamento, status, tags).
2. `POST /ia/proximo-passo` → `onboarding.decidir_proximo_passo` decide a próxima
   pergunta / menu / transbordo, baseado no estado do lead.

Código-chave: `src/regras/engine.py`, `src/onboarding.py`, `src/regras/alvo.py`.

---

## Fluxo 2 — Conversacional (`/ia/conv/turno`)

Camada de IA por cima, isolada do determinístico (pacote `src/conversacional/`).
Uma rota, **dois modos** detectados pela forma do corpo da requisição
(`rotas.py::TurnoRequest.modo`):

| Modo | Quando | O que faz | Mapeia no flow |
|---|---|---|---|
| **rotear** | corpo só com `ultima_mensagem` | decide a próxima pergunta/menu/transbordo (reusa `decidir_proximo_passo`). **NÃO valida.** | nó `api_proximo_passo` |
| **validar** | corpo com `answer` + `question_id` | valida a resposta, persiste, dispara hooks. **NÃO avança.** Trata conversa livre (dúvida/correção). | nó `api_validar` |

### Contrato de resposta (nomes que o flow do Matrix lê via `store`)

| Campo | Significado |
|---|---|
| `resposta_correta` | `"true"`/`"false"` — branch principal (= válido) |
| `message` | mensagem de SUCESSO/próxima pergunta (→ `{#mensagem_resposta}`) |
| `retorno_erro_api` | mensagem de ERRO que re-pede (→ `{#retorno_erro_api}`) |
| `needsReception` / `deve_transbordar` | `"true"`/`"false"` — transbordo p/ atendente |
| `encerrar` | `"true"`/`"false"` — finalizar atendimento |
| `proxima_pergunta_id`, `status_lead`, `proximo_passo`, `isAClient` | roteamento |

`message` e `retorno_erro_api` são **mutuamente exclusivos**. Detalhe e a tabela
completa de casos em `src/conversacional/rotas.py` (`_mapear_resposta`) e no flow
`ia_validacao/fluxos/flow_matrix_conversacional.json`.

### Princípio de isolamento

Bugs de validação/resposta/plano do conversacional se corrigem DENTRO de
`src/conversacional/` — sem editar `engine.py`/`onboarding.py` (o determinístico).
O conversacional só REUSA: os validadores puros (`src/extractors/`), a persistência
(`_alvo`) e o roteador de mensagem (`decidir_proximo_passo`, read-only).

---

## Dados e integrações

- **RegraValidacao** (Django, app `ia_validador`) — config por pergunta
  (extractor, opções, mensagens, ações). Fonte de verdade; a FastAPI cacheia.
- **LeadProspecto** (app `vendas_web`) e **NewService** (app `integracoes`) — alvos de
  escrita; `_alvo` decide qual.
- **HubSoft / API Matrix / ViaCEP** — integrações externas via `src/integracoes/`.
- **LogInteracaoIA** (Django) — log de toda chamada (`validar`, `proximo-passo`,
  `conv-turno`), para auditoria e debug.

---

## Verificação rápida

```bash
# FastAPI de pé?
curl -s http://127.0.0.1:8090/conv/health

# suíte offline da camada conversacional (sem rede/IA)
cd ia_validacao && PYTHONPATH=. .venv/bin/python3 tests/test_conv_simulacao.py
```
