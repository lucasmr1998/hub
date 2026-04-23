# Automações — Exemplo comentado (C02 Follow-up) + debug playbook

Este documento percorre uma automação ponta a ponta, mostrando como ela fica no editor, o que acontece em cada passo, qual estado aparece nas tabelas de execução e como debugar quando algo dá errado.

> ⚠ **A régua C02 aqui é ilustrativa.** Está especificada em [reguas-padrao.md](reguas-padrao.md) como **spec** — ainda não é implementação em produção (diferente dos fluxos de atendimento da FATEPI v3, que rodam em prod hoje). O objetivo aqui é ensinar o mecanismo com um caso realista, e servir de referência executável quando alguém for implementar.

Antes de ler isto, recomendado já ter passado pelo [README](README.md) + [engine.md](engine.md) + [models.md](models.md).

---

## C02 — Follow-up de Lead Sem Resposta (ilustrativa)

**Gatilho:** `lead_qualificado` (score atinge ≥ 7 mas o vendedor ainda não respondeu)
**Canais:** WhatsApp + notificação interna
**Rate limit:** `max_execucoes_por_lead=1` + `cooldown_horas=168` (7 dias — não repetir follow-up completo mais de 1x por semana)

### Grafo no editor visual

```
TRIGGER (lead_qualificado)
     │ default
     ▼
DELAY (4 horas)
     │ default
     ▼
CONDIÇÃO (lead.ultima_resposta == vazio)                   ← respondeu no WhatsApp nesse intervalo?
     ├── true (não respondeu) ─> AÇÃO enviar_whatsapp
     │                                  "{{lead_nome}}, conseguiu ver minha mensagem?"
     │                                      │ default
     │                                      ▼
     │                              DELAY (20 horas)        ← total 24h desde qualificado
     │                                      │
     │                                      ▼
     │                              CONDIÇÃO (ainda vazio?)
     │                                 ├── true ─> AÇÃO enviar_whatsapp
     │                                 │             "Quer que eu retome seu caso agora?"
     │                                 │                │
     │                                 │                ▼
     │                                 │          DELAY (24h)
     │                                 │                │
     │                                 │                ▼
     │                                 │          CONDIÇÃO (ainda vazio?)
     │                                 │             ├── true ─> AÇÃO notificacao_sistema
     │                                 │             │             "Lead {{lead_nome}} não respondeu em 48h — contato manual"
     │                                 │             │                │
     │                                 │             │                ▼
     │                                 │             │          DELAY (24h)
     │                                 │             │                │
     │                                 │             │                ▼
     │                                 │             │          AÇÃO mover_estagio → "frio"
     │                                 │             │                │
     │                                 │             │                ▼
     │                                 │             │             (fim)
     │                                 │             └── false ─> (fim — lead respondeu, parar cascata)
     │                                 └── false ─> (fim)
     └── false (respondeu) ─> (fim)
```

**6 nodos, 4 delays encadeados, 3 pontos de saída limpa** (candidato respondeu em qualquer checkpoint → para).

---

## Jornada 1 — Maria (reengajou em 24h)

Maria foi qualificada via score ≥ 7 às **10:00** de terça-feira. Vendedor não respondeu, mas Maria respondeu ao follow-up automático de 4h.

### Timeline do evento

| T | Quem | Ação | Registros |
|---|---|---|---|
| 10:00 | Sistema | `on_lead_qualificado` signal dispara | `LogExecucao` id=101 `status=sucesso` `evento_dados={lead_id, score}` |
| 10:00 | Engine | Trigger node → Delay (4h) | `ExecucaoPendente` id=55 `data_agendada=14:00` |
| 14:00 | Cron | Retoma id=55 → Condição: `lead.ultima_resposta == vazio`? **SIM** | — |
| 14:00 | Engine | Ação `enviar_whatsapp` ("Maria, conseguiu ver...?") | `LogExecucao` id=102 `status=sucesso` |
| 14:00 | Engine | Delay 20h | `ExecucaoPendente` id=56 `data_agendada=10:00 quarta` |
| **18:30** | **Maria** | **Responde no WhatsApp** | Signal `mensagem_recebida` grava em `HistoricoContato` → `lead.ultima_resposta` atualizado |
| 10:00 quarta | Cron | Retoma id=56 → Condição: `lead.ultima_resposta == vazio`? **NÃO** | — |
| 10:00 quarta | Engine | Branch `false` → sem destino → fim | `LogExecucao` id=103 `status=cancelado` (ou não registra, depende da impl) |

### Estado final nas 3 tabelas (Maria)

**`ExecucaoPendente` (cron fila):**

| id | nodo | lead | data_agendada | status |
|---|---|---|---|---|
| 55 | delay_4h | Maria | 14:00 ter | `executado` |
| 56 | delay_20h | Maria | 10:00 qua | `executado` |

**`LogExecucao` (auditoria):**

| id | regra | acao/nodo | lead | status | resultado |
|---|---|---|---|---|---|
| 101 | C02 | trigger | Maria | sucesso | iniciada por lead_qualificado |
| 102 | C02 | enviar_whatsapp | Maria | sucesso | Mensagem enviada via N8N |
| 103 | C02 | condicao_vazia | Maria | cancelado | Branch false: lead respondeu |

**`ControleExecucao` (rate limit):**

| lead | regra | total_execucoes_periodo | ultima_execucao |
|---|---|---|---|
| Maria | C02 | 1 | 14:00 ter |

Maria continuará com `total_execucoes_periodo=1` por 7 dias (cooldown). Se o score dela cair e voltar a subir na mesma semana, a régua não dispara de novo — bom, evita parecer robô.

---

## Jornada 2 — Pedro (nunca respondeu, cascata completa)

Pedro qualificado às **09:00** segunda. Vendedor não respondeu. Pedro também nunca respondeu.

| T | Engine | Registros chave |
|---|---|---|
| 09:00 seg | trigger → delay 4h | pendente 70 |
| 13:00 seg | cond `vazio`? sim → wpp + delay 20h | pendente 71, log 202 |
| 09:00 ter | cond `vazio`? sim → wpp + delay 24h | pendente 72, log 203 |
| 09:00 qua | cond `vazio`? sim → notificacao_sistema + delay 24h | pendente 73, log 204 |
| 09:00 qui | mover_estagio `frio` → fim | log 205 |

**Oportunidade de Pedro** fica no estágio **"frio"** após 72h. Vendedor que tinha esquecido recebe notificação interna no dia 3 ("Pedro não respondeu em 48h — contato manual").

`ControleExecucao` para Pedro: `total_execucoes_periodo=1`. Se Pedro voltar a responder e o lead for requalificado dentro de 7 dias, a régua não dispara outra cascata. Isso está certo — quem responde já "despertou" o vendedor via signal normal.

---

## Debug playbook

Quando uma automação **não disparou**, **disparou errado**, ou **travou**, siga essa ordem de investigação.

### 1. A régua está ativa e é do tenant certo?

```python
from apps.marketing.automacoes.models import RegraAutomacao
RegraAutomacao.all_tenants.filter(nome__icontains='C02', ativa=True).values(
    'id', 'tenant_id', 'evento', 'modo_fluxo', 'max_execucoes_por_lead', 'cooldown_horas'
)
```

Sem resultado = regra inativa/inexistente/tenant errado. 95% dos "não disparou" são isso.

### 2. O signal realmente foi disparado?

```python
from apps.marketing.automacoes.models import LogExecucao
LogExecucao.all_tenants.filter(
    regra__nome__icontains='C02',
    lead__telefone='<telefone>',
).order_by('-data_execucao')[:10].values(
    'status', 'resultado', 'evento_dados', 'data_execucao'
)
```

Se **0 logs**: signal não engatou. Causas comuns:
- `_skip_automacao=True` no save do lead (operação em lote, seed, assistente CRM)
- Lead salvo via SQL bruto (bypass do ORM)
- Tenant sem `post_save` conectado (ver [signals.md](signals.md))
- Score nunca chegou a `>= 7`

### 3. Ficou travada em `ExecucaoPendente`?

```python
from apps.marketing.automacoes.models import ExecucaoPendente
from django.utils import timezone
ExecucaoPendente.all_tenants.filter(
    status='pendente',
    data_agendada__lt=timezone.now(),
).values('id', 'regra_id', 'lead_id', 'data_agendada', 'nodo_id')
```

Pendente **no passado** com status pendente = cron não rodou ou travou. Ver último heartbeat do cron em [ops/02-CRON.md](../../../ops/02-CRON.md).

### 4. Foi bloqueada por rate limit?

```python
LogExecucao.all_tenants.filter(
    regra__nome__icontains='C02',
    lead__telefone='<telefone>',
    status='bloqueado_rate_limit',
).values('data_execucao', 'resultado')
```

Se tiver registros: rate limit ativo. Para confirmar quantas execuções já contam:

```python
from apps.marketing.automacoes.models import ControleExecucao
ControleExecucao.all_tenants.filter(
    lead__telefone='<telefone>',
    regra__nome__icontains='C02',
).values('total_execucoes_periodo', 'primeira_execucao_periodo', 'ultima_execucao')
```

Se precisar resetar pra testes: `ControleExecucao.delete()` da linha específica (nunca em lote sem filtro de tenant).

### 5. Branch errado na condição?

Se a condição escolheu o branch "errado", abra `LogExecucao.evento_dados` dos logs recentes e confira o contexto que chegou. Campo que não resolveu provavelmente foi escrito como `lead.X` mas o contexto só tem `lead_X` flat, ou vice-versa. Ver [engine.md > campos disponíveis](engine.md#campos-disponiveis-para-condicoes-editor-visual).

### 6. Ação executada mas mensagem não chegou

Logs do lado do provedor (N8N / Uazapi / Evolution):

```python
# Achar id da execucao
LogExecucao.all_tenants.filter(
    acao__tipo='enviar_whatsapp', lead__telefone='X', status='sucesso'
).values('id', 'resultado')
```

Campo `resultado` costuma ter o response_id ou erro do webhook. Se `status=sucesso` mas cliente não recebeu, problema é downstream (provedor, número bloqueado, template fora da janela de 24h WhatsApp Business, etc.) — não é problema do engine.

---

## Armadilhas conhecidas

| Armadilha | Sintoma | Prevenção |
|---|---|---|
| **Delay sobrevive a mudança de régua** | Alguém edita a régua enquanto tem execuções pendentes agendadas. Cron retoma com estrutura velha | Depois de editar, `ExecucaoPendente.filter(regra=X, status=pendente).update(status=cancelado)` se a mudança é incompatível |
| **Loop entre regras** | Regra A modifica lead → signal dispara → regra B modifica lead → signal dispara → regra A... | Usar `_skip_automacao=True` em ações de automação; evitar que ação modifique campo que dispara outra regra do mesmo tenant |
| **`_skip_automacao` esquecido em lote** | Import de 10k leads não dispara nenhuma régua | Documentar política: imports de seed usam skip; imports de cliente real não usam |
| **Variável não existe no contexto do evento** | Template renderiza literal `{{lead_score}}` ou string vazia | Conferir tabela [engine.md > variáveis](engine.md#substituicao-de-variaveis-nos-templates) — nem toda variável está disponível em todo evento |
| **Rate limit com janela mal-calibrada** | Lead recebe duplicado ou não recebe nunca | `cooldown_horas` vs `periodo_limite_horas` confundidos: cooldown é mínimo entre execuções; periodo é a janela de max_execucoes |
| **Cron desligado sem alarme** | Pendentes acumulam silenciosamente | Alarme externo que checa `ExecucaoPendente.filter(status=pendente, data_agendada__lt=now - 15min).count() < 10` |
| **Condição com campo que o evento não preenche** | Condição sempre cai no branch false mesmo quando deveria ser true | Logar `evento_dados` em `LogExecucao` é a fonte da verdade — nem toda regra tem `dias_sem_contato`, só `lead_sem_contato` tem |

---

## Relacionados

- [README.md](README.md) — arquitetura geral
- [engine.md](engine.md) — BFS, 8 ações, variáveis, rate limit
- [models.md](models.md) — 7 modelos (RegraAutomacao, NodoFluxo, ConexaoNodo, ExecucaoPendente, ControleExecucao, LogExecucao, CondicaoRegra, AcaoRegra)
- [signals.md](signals.md) — quem dispara o que, quando
- [editor-visual.md](editor-visual.md) — paleta de nodos
- [endpoints.md](endpoints.md) — URLs, templates, management commands, testes E2E
- [reguas-padrao.md](reguas-padrao.md) — catálogo de réguas (spec)
- [ops/02-CRON.md](../../../ops/02-CRON.md) — detalhes do cron que processa pendentes
- [modulos/atendimento/exemplo-fluxo-ia.md](../../atendimento/exemplo-fluxo-ia.md) — padrão equivalente para atendimento (caso real em prod, não spec)
