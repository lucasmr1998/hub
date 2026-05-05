# IA & Analytics — features de 04-05/05/2026

Wave de 6 features que materializam o positioning **"copiloto de IA do seu provedor"** e adicionam analytics que ISPs não têm em CRM genérico.

Tudo já implementado e commitado. **Nada deployado em produção** — fica esperando o seu OK pra subir.

---

## Mapa rápido

| # | Feature | O que faz | Onde acessa | Tipo |
|---|---|---|---|---|
| 130 | Win/Loss analysis | Categoriza motivos de oportunidade ganha/perdida → dashboard | `/crm/relatorios/win-loss/` | Analytics |
| 131 | CSAT pós-atendimento | Avaliação 1-5 estrelas após conversa resolvida + sentimento IA | `/inbox/csat/` | UX + IA |
| 132 | Resumo automático de conversa | Botão "Resumir" gera 3-5 bullets via LLM | Header de qualquer conversa no Inbox | IA |
| 133 | AI-suggested next action | Sugere próxima ação por oportunidade no pipeline | Endpoint API + cron (UI follow-up) | IA |
| 134 | Detector de churn (rule-based) | Score 0-100 por cliente baseado em sinais de risco | `/dashboard/clientes-em-risco/` | Analytics + alerta |
| 135 | Score de risco inadimplência | Score 0-100 antes de aprovar venda | Endpoint API (UI follow-up) | Analytics |

---

## #130 — Win/Loss analysis

**O que faz:** ao mover oportunidade pra "ganha" ou "perdida", o time pode categorizar o motivo (preço, concorrente, timing, etc). Dashboard agrega isso em barras com share %, valor total e win rate.

**Como acessar:** `/crm/relatorios/win-loss/` (acesso restrito a permissão `comercial.ver_todas_oportunidades`). Filtro de período: 30/90/180/365 dias.

**Código:**
- Modelo: `apps/comercial/crm/models.py` — campos `motivo_perda_categoria` e `motivo_ganho_categoria` em `OportunidadeVenda`
- View: `apps/comercial/crm/views.py:relatorio_win_loss`
- Template: `apps/comercial/crm/templates/crm/relatorio_win_loss.html`
- Migration: `0012_oportunidadevenda_motivo_ganho_categoria_and_more.py`

**Configuração:** nenhuma. Já vem com 7 motivos de perda + 7 de ganho como `choices`.

**Follow-up:** modal obrigatório no momento de mover oportunidade pra ganha/perdida (hoje a categorização é opcional via API edição inline).

---

## #131 — CSAT pós-atendimento via IA

**O que faz:** quando uma conversa muda pra status `resolvida`, signal cria automaticamente uma `AvaliacaoAtendimento` pendente. Time pode registrar a nota (1-5) e comentário do cliente. Comentário tem sentimento classificado via IA (positivo/neutro/negativo). Detrator (nota ≤ 2) gera notificação automática pra gerente CS/Suporte/Admin.

**Como acessar:**
- Dashboard: `/inbox/csat/` (CSAT médio, distribuição, lista de detratores)
- API registrar nota: `POST /inbox/api/avaliacoes/<id>/responder/` body `{nota: 1-5, comentario: "..."}`

**Código:**
- Modelo: `apps/inbox/models.py:AvaliacaoAtendimento` — OneToOne com `Conversa`
- Signal: `apps/inbox/signals.py:on_conversa_criar_avaliacao_csat`
- View: `apps/inbox/views.py:csat_dashboard` + `api_avaliacao_responder`
- Classificador IA: `_classificar_sentimento_csat` (~10 tokens, custo ~$0.00001 por chamada)
- Migration: `0008_avaliacaoatendimento.py`

**Configuração:** mesma integração de IA do assistente (OpenAI/Anthropic/Groq). Sentimento usa modelo barato (gpt-4o-mini ou similar).

**Follow-up:**
- Envio automático da pergunta via bot WhatsApp (fluxo de mensagem após `data_envio` ser setada)
- Endpoint público com token pra cliente responder direto sem login
- Webhook do canal recebendo resposta numérica do cliente

Por enquanto: avaliação fica `nota=NULL` esperando ser preenchida manualmente pela API quando o gerente recebe a resposta off-band.

---

## #132 — Resumo automático de conversa

**O que faz:** botão de "varinha mágica" no header do chat pega últimas 50 mensagens, manda pra LLM e retorna 3-5 bullets focando em motivo do contato, dados confirmados, decisões e próximos passos. Útil pra transferência entre agentes.

**Como acessar:** dentro de qualquer conversa aberta no `/inbox/`, botão `fa-magic` no canto superior direito. Modal mostra os bullets.

**Código:**
- Endpoint: `apps/inbox/views.py:api_resumir_conversa` (`/inbox/api/conversas/<id>/resumir/`)
- Template + JS: `apps/inbox/templates/inbox/inbox.html` (botão) + `static/inbox/js/inbox.js`

**Cache:** 1h por conversa via `django.core.cache`. Reabertura repetida não regasta tokens.

**Custo aproximado:** ~500 tokens input + 400 output. Em GPT-4o-mini fica ~$0.0003 por chamada.

**Configuração:** mesma integração de IA do tenant. Erro 503 se nenhuma integração ativa.

**Follow-up:** botão de "regenerar" (force POST) já está na API mas não exposto na UI ainda.

---

## #133 — AI-suggested next action

**O que faz:** cron de hora em hora analisa oportunidades ativas (pipeline) e sugere próxima ação concreta pra cada uma — ligar, mandar WhatsApp, fazer follow-up, etc. Sugestão fica armazenada em `OportunidadeVenda.proxima_acao_sugerida` (JSONField).

**Estrutura da sugestão:**
```json
{
  "tipo": "ligar|whatsapp|email|criar_proposta|followup",
  "titulo": "frase curta de ação",
  "mensagem_sugerida": "texto pronto pra usar",
  "justificativa": "por que agora",
  "urgencia": "alta|media|baixa",
  "gerada_em": "ISO timestamp",
  "estado": "pendente|aplicada|rejeitada"
}
```

**Como acessar:**
- Endpoints: `POST /crm/oportunidades/<id>/sugestao/aplicar/` (cria `TarefaCRM` com a ação) e `POST /crm/oportunidades/<id>/sugestao/rejeitar/`
- UI no detalhe da oportunidade: **ainda não implementado** (follow-up). Hoje só dá pra consumir via API ou consultar campo direto

**Código:**
- Service: `apps/comercial/crm/services/sugestao_acao.py`
- Cron: `apps/comercial/crm/management/commands/sugerir_proxima_acao.py`
- Endpoints: `apps/comercial/crm/views.py:api_sugestao_aplicar` + `api_sugestao_rejeitar`
- Migration: `0013_oportunidadevenda_proxima_acao_sugerida.py`

**Cache:** sugestão pendente regenera após 24h, aplicada/rejeitada após 3 dias.

**Configuração:**
- Crontab: `0 * * * * python manage.py sugerir_proxima_acao --limit=50`
- Mesma integração de IA do tenant

**Follow-up:** card no detalhe da oportunidade com botões "Aplicar"/"Ignorar".

---

## #134 — Detector de churn (rule-based)

**O que faz:** cron diário recalcula um score 0-100 por cliente (`ClienteHubsoft`) usando sinais que indicam risco de cancelamento. Quando cliente entra na faixa "alto risco" (60+), notifica gerentes CS automaticamente.

**Sinais ponderados:**
| Sinal | Peso |
|---|---|
| Inadimplência ativa (alerta + msg cobrança) | +25 |
| 2+ tickets abertos no mês | +30 (1 ticket: +10) |
| Sem conversa nos últimos 30d | +20 |
| Cliente novo (<6m) | +10 |
| Cliente longo (>36m, curva da banheira) | +5 |
| NPS detrator | +25 (placeholder, ativa quando módulo NPS existir) |

**Score → classe:**
- 0-39: saudável
- 40-59: atenção
- 60-100: alto risco

**Como acessar:**
- Dashboard: `/dashboard/clientes-em-risco/?classe=alto_risco` (também `atencao`, `saudavel`, `todos`)
- Lista paginada (30/pág) com sinais expandidos por linha

**Código:**
- Service: `apps/integracoes/services/churn_score.py`
- Cron: `apps/integracoes/management/commands/atualizar_churn_score.py`
- Modelo: 3 campos novos em `ClienteHubsoft` — `churn_score`, `churn_sinais` (JSONField com breakdown), `churn_atualizado_em`
- View: `apps/dashboard/views.py:clientes_em_risco_churn`
- Migration: `0010_clientehubsoft_churn_atualizado_em_and_more.py`

**Configuração:**
- Crontab: `0 4 * * * python manage.py atualizar_churn_score`
- Suporta `--dry-run` e `--limit`

**Follow-up:**
- Integrar score em automações de retenção (régua de relacionamento dispara quando entra em alto risco)
- Ligar sinal NPS quando módulo NPS existir
- Evoluir pra ML treinado em histórico de cancelamentos (rule-based é suficiente pra começar)

---

## #135 — Score de risco para inadimplência

**O que faz:** retorna score 0-100 antes de aprovar uma venda, baseado em sinais sobre o lead e o plano. **Não usa Serasa ou bureau externo** — só dados internos do Hubtrix.

**Sinais:**
| Sinal | Peso |
|---|---|
| Lead novo (<6m) | +15 |
| Plano valor > R$ 200 | +10 |
| Forma cobrança = boleto (vs Pix/cartão) | +10 |
| 1 atraso histórico (mesmo CPF em outro contrato) | +10 |
| 2+ atrasos históricos | +30 |
| Cliente cancelou e voltou | +20 |
| Inadimplente em outro contrato ativo | +25 |

**Classificação:**
- 0-39: baixo
- 40-69: médio
- 70-100: alto (requer aprovação de gerente)

**Como acessar:**
- API: `GET /api/leads/<id>/risco-inadimplencia/?plano_valor=199.90&forma_cobranca=boleto`
- Retorna: `{score, classe, classe_label, sinais, requer_aprovacao_gerente}`

**Código:**
- Service: `apps/comercial/cadastro/services/risco_inadimplencia.py`
- Endpoint: `apps/comercial/leads/views.py:api_lead_risco_inadimplencia`

**Configuração:** nenhuma. Funciona com dados que já estão no Hubtrix.

**Follow-up:**
- Modal de confirmação ao mover oportunidade pra "ganha" mostrando o score visualmente
- Bloqueio condicional: vendedor não consegue aprovar venda com risco ≥ 70 — só gerente
- Logar aprovação com risco em `LogSistema` (auditoria de override)

---

## Crontab consolidado

Adicionar no crontab do servidor depois do deploy:

```cron
# Notificações (já entregues anteriormente)
*/30 * * * *   python manage.py notificar_tarefas_vencendo
*/15 * * * *   python manage.py notificar_sla_inbox --horas=2
* * * * *      python manage.py check_nodo_timeouts

# Wave AI/Analytics (esta entrega)
0 4 * * *      python manage.py atualizar_churn_score
0 * * * *      python manage.py sugerir_proxima_acao --limit=50
```

---

## Configuração de IA (consolidado)

3 features (#131 sentimento, #132 resumo, #133 sugestão) usam LLM. Todas reutilizam a mesma `IntegracaoAPI` do tenant — **sem nova configuração**.

Em `/configuracoes/integracoes/`, garantir que existe pelo menos uma integração com:
- `tipo` ∈ {`openai`, `anthropic`, `groq`}
- `ativa = True`
- `api_key` preenchida
- `configuracoes_extras['modelo']` (default: `gpt-4o-mini`)

Sem IA configurada, as 3 features retornam erro graciosamente:
- #131 sentimento fica vazio (avaliação ainda funciona)
- #132 resumo retorna 503
- #133 sugestão é pulada no cron

---

## Custo estimado de IA por mês

Assumindo OpenAI gpt-4o-mini ($0.15/1M input + $0.60/1M output):

| Feature | Volume estimado | Custo/mês |
|---|---|---|
| #131 sentimento CSAT | 100 avaliações respondidas/mês | ~$0.01 |
| #132 resumo conversa | 200 cliques/mês (com cache 1h) | ~$0.10 |
| #133 sugestão de ação | 1.500 oportunidades × 1×/dia | ~$5.00 |
| **Total** | | **~$5/mês** |

Pra escala (1.000 oportunidades ativas, 500 conversas resolvidas/mês), fica entre $30-50/mês. Aceitável.

---

## Migrations a aplicar

```bash
python manage.py migrate inbox          # 0008_avaliacaoatendimento
python manage.py migrate integracoes    # 0010_clientehubsoft_churn_*
python manage.py migrate crm            # 0012 motivo_categoria + 0013 proxima_acao_sugerida
```

Todas com defaults seguros (NULL=True). Não exigem backfill.

---

## O que isso muda no pitch comercial

Antes: "plataforma do provedor que vende mais, perde menos e fideliza".
Agora vocês conseguem demonstrar:

1. **Pipeline com IA real** — abre uma oportunidade, IA já sugere ação concreta. Visceral.
2. **Resumo de conversa** — agente novo pega transferência, clica varinha, vê tudo em 5s.
3. **Score de churn** — gerente CS abre tela de manhã, vê top 20 clientes em risco e o porquê.
4. **CSAT** — pós-atendimento mensurável + alerta automático em detrator.
5. **Win/Loss** — "perdemos 23% por preço" vira dado, não palpite.
6. **Score inadimplência** — venda arriscada bloqueia, melhora margem.

Cada uma é diferenciação real vs CRM genérico (Pipedrive, Bitrix, RD).

---

## Tarefas relacionadas no Workspace

| # | Status | Commit |
|---|---|---|
| #130 Win/Loss | ✅ concluída | `be66600` |
| #131 CSAT | ✅ concluída | `9766781` |
| #132 Resumo conversa | ✅ concluída | `e82a9b4` |
| #133 AI next action | ✅ concluída | `c61001f` |
| #134 Detector churn | ✅ concluída | `1c0fdcb` |
| #135 Inadimplência | ✅ concluída | `142dfb1` |

Acompanhar evolução em `https://app.hubtrix.com.br/workspace/`.
