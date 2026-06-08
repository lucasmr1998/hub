# Inbox — Atendimento e distribuicao (visao completa)

Documento de referencia consolidado: como uma conversa nasce, e roteada, atribuida a um atendente, e o que acontece quando ninguem assume ou responde. Cobre **modelo de dados, fluxo, cron de inatividade, comportamento atual e gaps conhecidos**.

Ultima atualizacao: 2026-06-07
Autor: sessao de investigacao TR Carrion + cron `cron_inatividade_atendente`

---

## 1. Conceitos basicos

```
Tenant
│
├── CanalInbox          (WhatsApp uazapi, SMS, Email, Widget...)
│
├── EquipeInbox         (1 nivel — "grupo de pessoas com funcao comum")
│   └── MembroEquipeInbox  (user + cargo: agente / supervisor / gerente)
│
├── FilaInbox           (cada fila pertence a 1 equipe)
│   ├── modo_distribuicao: round_robin | menor_carga | manual
│   ├── prioridade
│   ├── horarios (opcional)
│   └── config inatividade (Nivel A + Nivel B — ver secao 5)
│
├── RegraRoteamento     (decide QUAL fila a conversa nova entra)
│   └── filtros por canal / etiqueta / horario / regex
│
├── PerfilAgenteInbox   (1:1 com User)
│   ├── status: online | ausente | offline
│   ├── capacidade_maxima: max conv simultaneas
│   ├── ultimo_heartbeat: ping JS do navegador
│   └── property `disponivel` = status=online E conversas_abertas < capacidade
│
└── Conversa            (1 thread com 1 contato)
    ├── canal           (qual canal recebeu)
    ├── fila            (NULL se nao foi roteada ainda)
    ├── equipe          (vem da fila)
    ├── agente          (NULL ate atribuicao)
    ├── status          (aberta | pendente | resolvida | arquivada)
    ├── modo_atendimento (bot | humano | finalizado_bot)
    ├── assumida        (boolean — se agente clicou em "Assumir")
    ├── realocacoes_count
    └── metadata        (flags volateis tipo alerta_inatividade_em)
```

### Nao existe "fila pessoal" por atendente

A "caixa do atendente" e apenas um **filtro de UI** sobre `Conversa.agente=eu`. Nao ha tabela separada. Tudo vive em `Conversa`. A diferenca entre "minha caixa", "fila pendente" e "outras conversas" e so query.

---

## 2. Estados da conversa

| Status | Descricao |
|---|---|
| **aberta** | Conversa ativa, com agente atribuido (assumida ou nao) |
| **pendente** | Aguardando agente — pode ser nova sem distribuicao OU liberada por realocacao |
| **resolvida** | Encerrada (humano resolveu / bot terminou / inatividade) |
| **arquivada** | Movida pra arquivo (nao aparece em listagens padrao) |

| modo_atendimento | Descricao |
|---|---|
| **bot** | Sob controle do flow (Vero N8N, Drawflow Hubtrix). NAO precisa de agente humano |
| **humano** | Transferida pra atendente. **Bot fica calado** (regra invariante desde 02/06/2026) |
| **finalizado_bot** | Bot terminou (despedida) mas conversa continua na lista — humano pode reabrir |

| Combo critico | Significado |
|---|---|
| `status=aberta + modo=bot + agente=NULL` | Vero atendendo, OK, nao precisa de agente |
| `status=aberta + modo=humano + agente=NULL` | **Problema** — bot transferiu mas nao atribuiu ninguem |
| `status=pendente + agente=NULL` | Na fila aguardando alguem pegar |
| `status=aberta + modo=humano + agente=X + assumida=False` | Atribuida mas atendente nao clicou em "Assumir" — alvo do cron Nivel A |
| `status=aberta + modo=humano + assumida=True` (sem resposta agente >Y min) | Alvo do cron Nivel B (alerta admin) |

---

## 3. Fluxo de distribuicao (conversa nova)

```
1. Webhook do canal recebe mensagem (uazapi -> Hubtrix, Widget -> Hubtrix, etc)
   │
2. inbox.services.receber_mensagem() cria/recupera Conversa
   │
3. distribuir_conversa(conversa, tenant):
   │
   ├─ 3a. determinar_fila() — itera RegraRoteamento por prioridade desc
   │     ├─ Filtros: canal, etiqueta, horario
   │     ├─ Retorna a primeira regra que casa
   │     └─ Se nenhuma regra: retorna None -> conversa fica SEM fila (orfa)
   │
   ├─ 3b. verificar_horario_fila() — se fora horario:
   │     ├─ envia fila.mensagem_fora_horario
   │     ├─ status=pendente
   │     └─ retorna (nao busca agente)
   │
   ├─ 3c. selecionar_agente(fila):
   │     ├─ Membros da equipe da fila (via MembroEquipeInbox)
   │     ├─ Filtra PerfilAgenteInbox: status=online E disponivel
   │     ├─ Aplica modo: round_robin (rotacao) OU menor_carga (min conv) OU manual (skip)
   │     └─ Retorna agente OU None
   │
   ├─ Atribuiu agente: conversa.agente=X, modo=humano, registra HistoricoTransferencia
   │
   └─ Nao atribuiu: status=pendente, agente=NULL, fila=X (fila pendente)
```

Trigger: chamado em:
- `receber_mensagem()` (WhatsApp via uazapi)
- `receber_mensagem_widget()` (Widget Chat)
- `transferir_conversa()` (transferir entre filas/equipes manualmente)
- Nodo `transferir_humano` do engine Drawflow

**Importante:** se o **Vero N8N (TR Carrion)** transfere pra humano via update direto no DB (sem chamar `distribuir_conversa` nem `transferir_conversa`), a conversa fica com `modo=humano + fila=NULL` — bug observado em prod (#169 e similares).

---

## 4. Atribuicao vs assumir

| Estado | Como acontece | UI bloqueio |
|---|---|---|
| Atribuida (`agente=X, assumida=False`) | Auto pela distribuicao OR manual (admin escolhe vendedor) | Vendedor ve conversa, pode visualizar mas o **input de envio fica desabilitado** |
| Assumida (`assumida=True`) | Vendedor clica em "Assumir esta conversa" | Input de envio liberado, vendedor responde |

Por que separamos: admin/supervisor podem **abrir** conversa atribuida a outra vendedora pra ver historico, sem **assumir** acidentalmente. Modo "visualizar" introduzido em commit `3fd307c` (07/06/2026).

---

## 5. Cron de inatividade (`cron_inatividade_atendente`)

CronJob #8 cadastrado em 2026-06-07. Schedule `*/5 * * * *` (a cada 5 minutos).

### Heartbeat (pre-condicao)

Antes dos niveis A/B, marca offline quem nao pinga ha >5min:

```
PerfilAgenteInbox.status=online
  + ultimo_heartbeat antigo OU NULL com ultimo_status_em antigo
  → status='offline'
```

Por que: a selecao de "outro agente online" no Nivel A precisa do status estar correto. Heartbeat vem do JS do navegador (`/inbox/heartbeat/` ou similar) enquanto a vendedora tem o Inbox aberto.

### Nivel A — Realocar atendente que nao assumiu

**Pre-requisitos:**
- `fila.realocar_inativo_ativo = True`
- `verificar_horario_fila(fila)` retorna True (dentro do horario)
- Conversa: `status in (aberta, pendente) + modo='humano' + agente NOT NULL + assumida=False`
- Tempo desde atribuicao > `fila.tempo_max_sem_assumir_min`
- `realocacoes_count < fila.max_realocacoes`

**Acao:**
1. Tenta selecionar OUTRO agente online (exclui o atual)
2. Achou: muda `agente=novo`, mantem `assumida=False`, registra HistoricoTransferencia(`tipo='realocar_inativo'`), msg sistema na conversa
3. Nao achou: **libera** — `agente=NULL`, `status=pendente`, msg sistema "liberada"
4. Em ambos: `realocacoes_count++`

**Limite:** apos `max_realocacoes` vezes, cron para de tocar nessa conversa. Vai pra fila pendente ate alguem clicar manualmente.

### Nivel B — Alertar admin quando atendente nao responde

**Pre-requisitos:**
- `fila.alerta_admin_inativo_ativo = True`
- Conversa: `status in (aberta, pendente) + modo='humano' + assumida=True`
- Ultima mensagem foi do **contato** ha > `fila.tempo_max_sem_responder_min`
- `metadata.alerta_inatividade_em` ainda nao setado (idempotencia)

**Acao:**
- Cria HistoricoTransferencia(`tipo='alerta_admin'`) (auditoria, sem mover)
- Notifica usuarios com permissao `inbox.gerenciar` via `notificacoes`
- Marca `metadata.alerta_inatividade_em` pra nao repetir

**Reset:** quando agente responder, cron limpa o flag e ciclo pode reabrir.

---

## 6. Encerramento por inatividade (`encerrar_inativos`)

CronJob #1, schedule `*/15 * * * *`. Independente do Nivel A/B.

**Critério:**
- `ConfiguracaoInbox.encerramento_auto_ativo=True`
- `status in (aberta, pendente) + modo='humano' + ultima_mensagem_em < agora - encerramento_auto_horas`

**Acao:**
- Marca `motivo_encerramento` = "Encerramento automatico" (seed)
- `status='resolvida'`
- Se `encerramento_auto_aviso_ativo`: envia `encerramento_auto_aviso_texto` pro contato
- Se `encerramento_auto_fecha_oportunidade=True`: move oportunidade pra estagio `is_final_perdido`

Hoje em prod:
- TR Carrion: ativo, 48h, nao fecha oportunidade
- Aurora-hq, Nuvyon, FATEPI: desativado

---

## 7. CronJobs ativos em prod (snapshot 2026-06-07)

| # | Nome | Schedule | O que faz |
|---|---|---|---|
| 1 | `encerrar_inativos` | `*/15 * * * *` | Encerra conv humanas sem msg ha N horas |
| 4 | `processar_pendentes_hubsoft` | `* * * * *` | Reprocessa leads com erro |
| 5 | `sincronizar_catalogos_hubsoft` | `0 6 * * *` | Cron diario de sync HubSoft |
| 6 | `sincronizar_clientes_hubsoft` | `* * * * *` | Sincroniza clientes |
| 7 | `monitor_sistema` | `*/5 * * * *` | Alertas (webhook 5xx, hubsoft errors, leads travados) |
| **8** | **`cron_inatividade_atendente`** | **`*/5 * * * *`** | **Marca offline + Nivel A realocar + Nivel B alertar** |

---

## 8. Configuracao TR Carrion (snapshot 2026-06-07)

```
Tenant: T R Carrion (slug=tr-carrion, id=11)

Canais:
  Canal #13 "Vero WhatsApp" tipo=whatsapp ativo=True

Equipes:
  Vendedores Vero (5 membros)
    - users: 20 (offline), 23, 24, 25, 26

Filas:
  #8 "Atendimento Vero"
     equipe = Vendedores Vero
     modo_distribuicao = round_robin
     prioridade = 10
     realocar_inativo_ativo = True
     tempo_max_sem_assumir_min = 10
     max_realocacoes = 2
     alerta_admin_inativo_ativo = True
     tempo_max_sem_responder_min = 30

RegrasRoteamento: ZERO  ⚠️  (causa raiz de conv orfas — ver secao 9)

ConfiguracaoInbox:
  encerramento_auto_ativo = True
  encerramento_auto_horas = 48
  encerramento_auto_fecha_oportunidade = False
```

---

## 9. Gaps conhecidos (2026-06-07)

### Gap 1 — TR Carrion sem RegraRoteamento

**Sintoma:** 52 conversas (de 178 totais — 29%) com `fila=NULL`.
**Causa:** `determinar_fila()` retorna None porque nao ha regra cadastrada pro canal Vero WhatsApp -> fila #8.
**Quem fica orfa de verdade:** conv com `modo=humano + fila=NULL` (ex.: #169) — bot transferiu pra humano mas nao chamou `distribuir_conversa()`.
**Conv em `modo=bot + fila=NULL` NAO sao problema** — Vero N8N esta atendendo, fila so importa quando vira humano.

**Fix:** criar RegraRoteamento(canal=#13, fila=#8, prioridade=10). Backfill seletivo so em `modo in (humano, finalizado_bot) + fila=NULL`.

### Gap 2 — Vero N8N transfere humano sem fila

**Sintoma:** conv #169 — `modo=humano + agente_id=23 + fila=NULL + equipe=NULL`.
**Causa:** o Vero workflow muda `modo='humano'` no DB sem chamar `transferir_conversa()` ou endpoint que invoque `distribuir_conversa()`.
**Impacto:** cron Nivel A nao pega (filtro exige `fila NOT NULL`). Conv fica perdida.

**Fix:** investigar nodos do workflow `Df1BgcXdg3HAUZwf`. Padronizar transferencia pra usar `/api/v1/n8n/conversa/transferir-fila/` ou similar.

### Gap 3 — Sem auto-distribuicao quando agente fica online

**Sintoma:** vendedora loga, status=online via heartbeat, mas conv pendente na fila nao e atribuida automaticamente. Ela tem que abrir manualmente o filtro "fila pendente" e clicar em "Pegar proxima".
**Causa:** nao ha signal `post_save` em PerfilAgenteInbox que olhe conv pendentes da equipe e atribua.

**Opcoes de fix:**
- **G3a:** signal pos-save agente online -> distribuir 1 conv pendente
- **G3b:** estender cron #8 pra distribuir pendentes alem de realocar
- **G3c:** apenas notificar a equipe (sem auto-atribuir)

### Gap 4 — Alerta admin com 0 destinatarios

**Sintoma:** dry-run mostrou "Alerta admin: conversa #X notificou 0 admin(s)" pra 4 conversas.
**Causa:** nenhum usuario TR Carrion tem permissao `inbox.gerenciar` (ou equivalente que `alertar_admin_inatividade()` consulta).

**Fix:** mapear quem deveria receber. Configurar permissao no User correto.

### Gap 5 — Heartbeat zerado pra todos

**Sintoma:** apos cron #8 ligar, 6 agentes marcados offline. Status atual: 0 online.
**Causa hipotetica:** heartbeat JS pode estar quebrado / endpoint nao acionado / vendedoras estavam offline mesmo.
**Investigar:** quando vendedora logar amanha (08/06/2026), verificar se `ultimo_heartbeat` atualiza.

---

## 10. Endpoints relevantes (resumo)

| Endpoint | Quem chama | O que faz |
|---|---|---|
| `/api/v1/n8n/inbox/mensagem-recebida/` | Vero N8N | Registra msg do cliente, chama `distribuir_conversa()` |
| `/api/v1/n8n/inbox/enviar/` | Vero N8N | Espelha msg saida do bot |
| `/api/v1/n8n/conversa/transferir-fila/` | Vero N8N (deveria) | Transfere conv pra fila X, chama `distribuir_conversa` |
| `/api/v1/inbox/conversa/<id>/assumir/` | Vendedor (UI) | Marca `assumida=True` |
| `/api/v1/inbox/heartbeat/` | UI (JS) | Atualiza `PerfilAgenteInbox.ultimo_heartbeat` |

Ver doc completa em [../../integracoes/apis/n8n-hubtrix/](../../integracoes/apis/n8n-hubtrix/README.md).

---

## 11. Como debugar uma conversa especifica

```python
from apps.inbox.models import Conversa, HistoricoTransferencia
c = Conversa.all_tenants.get(numero=169, tenant__slug='tr-carrion')
print(c.status, c.modo_atendimento, c.fila_id, c.equipe_id, c.agente_id, c.assumida)
print(c.realocacoes_count, c.data_abertura, c.ultima_mensagem_em)
print(c.metadata)

for h in c.transferencias.order_by('data'):
    print(f'{h.data:%Y-%m-%d %H:%M} {h.tipo} de={h.de_agente_id} para={h.para_agente_id} fila={h.para_fila_id} motivo={h.motivo}')
```

Pra rodar cron em dry-run:
```bash
python manage.py cron_inatividade_atendente --tenant tr-carrion --dry-run
```

Pra forcar uma execucao agora:
```bash
python manage.py cron_inatividade_atendente --tenant tr-carrion
```

---

## 12. Docs relacionadas

- [models.md](models.md) — campos completos dos modelos do Inbox
- [services.md](services.md) — funcoes de servico (`assumir_conversa`, `transferir_conversa`, etc)
- [distribuicao.md](distribuicao.md) — visao curta da engine
- [reatribuicao-inatividade.md](reatribuicao-inatividade.md) — detalhes Nivel A/B
- [assumir-conversa.md](assumir-conversa.md) — fluxo de assumir vs visualizar
- [interface.md](interface.md) — UI do inbox (filtros, badges, fila pendente)
- [websocket.md](websocket.md) — push real-time
- [apis.md](apis.md) — endpoints publicos do Inbox
