# TR Carrion — Incidentes 02/06/2026

Diagnostico e correcoes do dia 02/06. Caso raiz: **bot respondia conversas ja atribuidas a agente humano** (caso Michele) + **endpoint /lead/imagem/ exigia lead_id que a session do Vero nao guarda** (caso Juliana, mesmo bug da Anna 29/05). Sistema ficou exposto pelo periodo em que os workflows ficaram ativos sem a defesa em profundidade.

---

## Resumo executivo

| # | Bug | Impacto | Status |
|---|-----|---------|--------|
| 1 | `/api/public/n8n/inbox/mensagem/` aceitava `modo_atendimento='bot'` mesmo com a conversa em `modo='humano'` e/ou `agente_id != None` — sobrescrevia silenciosamente | Bot respondia por cima do agente humano. Caso Michele (conv #331): 4 msgs do Vero enviadas DEPOIS da Kelle ter assumido | ✅ corrigido (`12d7a61`) |
| 2 | Endpoint `/api/public/n8n/lead/imagem/` exigia `lead_id` mas a `vero_session.dados` nao guarda esse campo — expressao N8N resolvia undefined, body sem `lead_id`, 400 | Conversas travavam ao enviar foto do RG. Caso Juliana (conv #332) + Anna (29/05) + Michele (parcial, 14:25) | ✅ corrigido (`26780f1`) — agora aceita `telefone` como fallback |
| 3 | `apps/inbox/distribution.py`: atribuicao automatica setava `agente_id` mas deixava `modo='bot'` — abria janela pro Vero responder | Toda conversa distribuida automaticamente vulneravel ao bug #1 | ✅ corrigido (`92d013d`) |
| 4 | `Consultar Hubtrix Estado` retornava `modo_atendimento` cru — Vero olhava so esse campo, sem cruzar com `agente_id` | Sem flag canonico de "bot pode atuar". Cada caminho que setasse modo='bot' indevido vazava | ✅ corrigido (`92d013d`) — endpoint passa a retornar flag `bot_pode_atuar` e N8N consome ele |

---

## 1. Bug regressao humano -> bot no /inbox/mensagem/

### Diagnostico

O workflow Vero (`Df1BgcXdg3HAUZwf`) chama `POST /api/public/n8n/inbox/mensagem/` em todo turno via node `RegistrarMsgCliente`, enviando `modo_atendimento='bot'` no body (default do orquestrador). O endpoint Hubtrix sobrescrevia cegamente:

```python
modo = payload.get('modo_atendimento')
if modo:
    if conversa.modo_atendimento != modo:
        conversa.modo_atendimento = modo
        conversa.save(update_fields=['modo_atendimento'])
```

Sequencia do caso Michele (conv #331):
- 14:28 — Kelle (agente_id=21) foi atribuida e respondeu manualmente
- 15:07:20 — Michele mandou "??"
- Vero registrou a msg com `modo='bot'` → conversa regrediu de `humano` para `bot`
- Vero seguiu o fluxo e enviou 4 msgs por cima:
  - 12:05:58 "preciso da frente do seu RG ou CNH..."
  - 12:06:25 duplicada
  - 12:07:27 "Tudo bem! Vou anotar..."
  - 12:08:43 "Entao, vamos seguir?"

### Fix (commit `12d7a61`)

`apps/integracoes/views_n8n_webhook.py` linha 670+:

```python
modo = payload.get('modo_atendimento')
if modo:
    modo_atual = conversa.modo_atendimento
    tem_agente = bool(conversa.agente_id)
    quer_voltar_pra_bot = (modo == 'bot' and (modo_atual == 'humano' or tem_agente))
    if quer_voltar_pra_bot:
        logger.warning('[N8N inbox] Tentativa de regredir modo humano->bot bloqueada ...')
        avisos.append('modo_atendimento mantido humano (agente atribuido)')
    else:
        # ... aplica modo normalmente
```

### Recuperacao

4 msgs do bot revogadas via `POST uazapi /message/delete` com `fromAll=true`. A Michele deve ver "Esta mensagem foi apagada" no WhatsApp dela.

---

## 2. Bug /lead/imagem/ exigia lead_id que session do Vero nao tem

### Diagnostico

O endpoint Hubtrix `POST /api/public/n8n/lead/imagem/` (registra foto do RG enviada pelo cliente) validava `lead_id` como obrigatorio. O node N8N `Registrar RG Frente Hubtrix` montava o body com:

```javascript
"lead_id": "={{ $node['Load Session'].json.dados?.lead_id ?? $node['Load Session'].json.lead_id }}"
```

Mas a `vero_session.dados` so guarda CEP, CPF, plano, etc. — **nunca grava lead_id**. A expressao resolvia `undefined`, o N8N removia o campo do body, e o endpoint respondia 400.

Conversas afetadas nas ultimas 200 execucoes com erro:
- `555199113780` (Juliana) — 3 falhas, ultima 15:06:46
- `5511953551590` (Michele) — 2 falhas, ultima 14:26:25
- Anna `5514997370736` (29/05) — bug original que ja tinha sido suspeitado

### Fix (commit `26780f1`)

`apps/integracoes/views_n8n_webhook.py` `registrar_imagem_lead`:

```python
# Aceita telefone como fallback quando lead_id ausente
if lead is None and telefone:
    tel_normalizado = ''.join(ch for ch in telefone if ch.isdigit())
    if tel_normalizado:
        lead = (
            LeadProspecto.all_tenants
            .filter(tenant=tenant, telefone__contains=tel_normalizado[-9:])
            .order_by('-id')
            .first()
        )
```

Workflow N8N (`Df1BgcXdg3HAUZwf`) — nodes `Registrar RG Frente Hubtrix` e `Registrar RG Verso Hubtrix` ganharam parametro `telefone` no body:

```javascript
"telefone": "={{ $node['Entrada'].json.telefone }}"
```

### Recuperacao Juliana

Lead 482 ja tinha 2 imagens enviadas mas nao registradas. Manualmente registradas via endpoint:
- `ImagemLeadProspecto #49` (RG frente, msg #5182)
- `ImagemLeadProspecto #50` (RG verso, msg #5183)

Flavia (agente_id=23) atribuida — segue manualmente.

---

## 3. Bug distribuicao automatica nao silenciava bot

### Diagnostico

`apps/inbox/distribution.py` linha 204:

```python
agente = selecionar_agente(fila, tenant)
if agente:
    conversa.agente = agente
    conversa.save(update_fields=['fila', 'equipe', 'agente'])
```

`agente_id` setado mas `modo_atendimento` permanece como estava (geralmente `bot`). Cada conversa distribuida automaticamente herdava o bug — bot podia continuar respondendo apesar de ter agente.

`services.py:atribuir_conversa` e `services.py:assumir_conversa` ja faziam isso corretamente. So a distribuicao automatica nao.

### Fix (commit `92d013d`)

```python
agente = selecionar_agente(fila, tenant)
if agente:
    conversa.agente = agente
    update_fields = ['fila', 'equipe', 'agente']
    if conversa.modo_atendimento != 'humano':
        conversa.modo_atendimento = 'humano'
        update_fields.append('modo_atendimento')
    conversa.save(update_fields=update_fields)
```

---

## 4. Bug Vero olhava modo_atendimento isolado

### Diagnostico

O endpoint `/api/public/n8n/conversa/estado/` retornava `modo_atendimento` cru. O node N8N `Ja em Humano?` checava apenas:

```
{{ $node['Consultar Hubtrix Estado'].json.modo_atendimento }} != 'humano'
```

Se modo='bot' no DB por qualquer motivo (bug em outro caminho, race, signal), o Vero seguia respondendo apesar de `agente_id` estar setado.

### Fix (commit `92d013d`)

Endpoint passa a retornar flag canonico:

```python
bot_pode_atuar = bool(
    conversa.modo_atendimento == 'bot'
    and conversa.agente_id is None
    and conversa.status not in ('resolvida', 'arquivada')
)
```

Node N8N `Ja em Humano?` atualizado pra checar `bot_pode_atuar === true`. Se for false (ou undefined em loose mode), bot cala — fail-safe natural.

### Validacao pos-deploy

```
Michele (humano, agente=21) -> bot_pode_atuar=false ✅
Juliana (humano, agente=23) -> bot_pode_atuar=false ✅
Tel inexistente             -> existe=false, bot_pode_atuar=true ✅
POST /lead/imagem/ telefone -> 201 imagem_id=48 (smoke test) ✅
```

---

## Defesa em profundidade — invariante "agente atribuido = bot calado"

Mesmo a falha de qualquer 1 das 4 camadas, as outras 3 ainda contem o bug:

| Camada | Onde | Protege contra |
|--------|------|----------------|
| **A** | `/conversa/estado/` retorna `bot_pode_atuar` | Vero ler estado correto antes de cada turno |
| **B** | N8N `Ja em Humano?` consome o flag | Bug de leitura no workflow |
| **C** | `distribution.py` forca `modo='humano'` | Atribuicao automatica sem trocar modo |
| **D** | `/inbox/mensagem/` bloqueia regressao | Webhook sobrescrevendo modo |

---

## Linha do tempo (02/06/2026)

| Hora | Evento |
|------|--------|
| 12:05–12:08 | Michele recebe 4 msgs do Vero apos Kelle ter assumido — usuario detecta |
| 13:30 | Investigacao iniciada — paramos `Df1BgcXdg3HAUZwf` |
| 14:00 | Causa raiz B identificada (`/lead/imagem/` exige lead_id) — commit `26780f1` |
| 14:30 | Causa raiz A (regressao humano->bot) identificada — commit `12d7a61` |
| 15:00 | Camadas A+C aplicadas — commit `92d013d` |
| 15:15 | 4 msgs do bot revogadas via uazapi |
| 15:30 | Rebuild EasyPanel concluido, todos os fixes ativos |
| 15:45 | Validacao em prod: 100% dos cenarios passaram |
| 15:50 | Juliana: imagens RG frente/verso registradas manualmente |
| 16:00 | Orquestrador Vero reativado |

---

## Aprendizados

1. **Flags canonicos derivados > campos crus**. `modo_atendimento` sozinho nao era suficiente. `bot_pode_atuar` consolida a regra de negocio no servidor e impede que cada cliente da API tenha que recombinar campos.
2. **Webhooks que aceitam estado cliente precisam ter guardas**. Qualquer endpoint que receba `modo_atendimento` no payload precisa checar se a transicao e legitima — nunca aceitar regressoes silenciosas.
3. **Bugs duplicados sao bugs sistemicos**. Anna (29/05) + Juliana (02/06) com mesmo sintoma "travou nas imagens" indicava bug recorrente, nao caso isolado. Endpoint deveria aceitar identificador alternativo (telefone) ja na primeira versao.
4. **`continueOnFail=true` mascara incidentes silenciosos**. Ja sabido (incidente Fabiana), reforcado aqui. Cada erro em registro de dado critico deve falhar audivelmente.

---

## Pendencias relacionadas (nao bloqueantes)

- Texto pra Kelle (sobre Michele) e Flavia (sobre Juliana) — Copywriter
- Cron `detectar_conversas_quebradas` (alertar lacunas msg) — backlog
- Dashboard `/aurora-admin/webhooks/` (LogWebhookN8N) — backlog
- Onda 4 reimport 8 conversas TR Carrion (1576 msgs) — aguarda autorizacao A/B/C
