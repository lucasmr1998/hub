# Engine n8n-style + Bot de Suporte Conversacional — 28-29/06/2026

**Data:** 28-29/06/2026
**Participantes:** Lucas + Tech Lead/CRM (Claude)
**Duração:** sessão longa (2 dias)

---

## Contexto

Começou no **go-live da convergência de marketing**, mas o usuário redirecionou: as regras antigas de marketing **não eram mais usadas** (0 execuções/30d), então **migrar zumbi não fazia sentido**. Decisão: construir a **1ª automação nativa de verdade** na engine nova — um **bot de triagem de suporte** pra Hubtrix (tenant `aurora-hq`). No caminho, deixar a engine **com cara de n8n** (recursos que o usuário foi pedindo ao testar).

---

## Principais pontos discutidos

- **Marketing convergência:** não migrar regras mortas; a engine é a base pra automação nova + aposentar o motor antigo. Go-live ficou só preparado (flag `AUTOMACAO_WIRING_ATIVO` virou env-driven, commit `edd62a5`).
- **Bot de suporte = arquitetura conversacional multi-agente.** Evoluiu por conversa: classificar todo "oi" é robótico → `conversa` virou uma saída do switch → **Conversador** que sonda. Multi-agente (token + prompts focados) com `conversa` como 4ª intenção.
- **Memória = a própria conversa** (não tabela nova): registry extensível (`services/memoria.py`), 1º tipo `conversa` = mensagens da conversa do inbox (prod) / turnos do chat (teste). Compartilhada entre agentes; classificador não polui (não responde → não vira mensagem). Campo `Agente.memoria` (migration `0008`).
- **Dúvida da memória resolvida (verificado no código):** Uazapi entra **por webhook MAS via inbox** (`receber_mensagem` cria Conversa → `mensagem_recebida` → engine nova com a Conversa no Contexto) → **memória funciona** no canal real. Stateless só vale pro nó-gatilho `webhook` cru.
- **Recursos n8n adicionados:** switch modelo Rules, nó `chat` de teste (caminho verde + I/O por nó), drag-to-reference, seletor de conta/credencial (= IntegracaoAPI), `responder_webhook` + modo de resposta no Webhook, reproduzir execução no canvas.
- **Nada hardcoded** (princípio reforçado, salvo em memória `feedback_nada_hardcoded`): valores vêm de config/modelo/dropdown.

---

## Decisões tomadas

| Decisão | Motivo |
|---|---|
| Não migrar regras de marketing mortas | 0 uso; valor zero; engine é o futuro, não ressuscitar zumbi |
| Bot de suporte multi-agente (classificador → switch → especialistas) | Token + prompts focados; `conversa` como 4ª saída resolve o "oi" robótico |
| Memória = a conversa (registry, tipo `conversa`) | Sem tabela nova; compartilhada de graça; classificador não polui |
| Switch no modelo "Rules" do n8n | Reusa operadores do `if`; genérico (vs string-igualdade) |
| Gatilho de prod = nó `evento` (mensagem_recebida) | Coexiste com chat de teste (evento inicia do nó, não do `inicio`) |
| `sessao` memory adiada | Inbox cobre o canal real; só precisa pra webhook custom |

---

## Pendências

| Pendência | Responsável |
|---|---|
| Go-live em prod (ativo=True + AUTOMACAO_WIRING_ATIVO) — decisão de negócio | Lucas |
| Memória `sessao` (session-keyed + store) pra integração webhook custom | quando precisar |
| `modo_atendimento` default='humano' → definir quando vira 'bot' (pré-prod) | produto |
| Multi-trigger pro webhook (hoje usa `grafo['inicio']`) | futuro |
| Select com rótulo amigável (hoje mostra valores crus: imediato/ultimo_no/...) | editor |
| RAG não roda no dev (embeddings `proxies` bug) — Respondedor só valida em prod | infra dev |
| Fase 3: identificar cliente (telefone → tenant) no ticket | futuro |
| Apagar fluxos de teste em dev: "Teste Webhook", "Triagem (Webhook)" | limpeza |

---

## Próximos passos

- [ ] Decidir go-live do bot de suporte em prod (ativar fluxo + wiring)
- [ ] (se webhook custom) construir memória tipo `sessao`
- [ ] Afinar ramos dúvida (RAG em prod) / financeiro com mais casos
- [ ] Fase 3: identificar cliente no ticket

---

## Estado pra retomada (dev, aurora-hq)

- **Agentes** (`/automacao/agentes/`): Classificador de Suporte (id 3), Capturador de Bug (4), Conversador (5), Respondedor (6), Financeiro (7) — todos `memoria='conversa'`, integração OpenAI id 8.
- **Fluxo "Triagem de Suporte"** (inativo): `chat` (teste) + `evento mensagem_recebida` (prod) → guard "humano assumiu?" → Classificador → switch (bug/duvida/financeiro/conversa) → especialistas. Ticket abre via tool `abrir_ticket` (service `tickets.criar_ticket`).
- **Tudo dev-only e dormente.** Validado ponta a ponta com LLM real (tickets #7/#8/#9). Webhook testável em `http://127.0.0.1:8001/automacao/webhook/<token>/` (fluxo precisa `ativo=True`).
- **Commits da sessão:** `edd62a5` (env flag) · `155a423` (switch Rules) · `0b6ea46` (switch rules v2) · `25d73f5` (chat+memória+I/O) · `20b4394` (drag+conta+output) · `ba884bd`/`f4f30b1` (responder webhook) · `aa63d35` (reproduzir execução) · `e0003bc` (mapa de entrada).
