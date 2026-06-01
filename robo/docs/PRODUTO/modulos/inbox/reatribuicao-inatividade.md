# Inbox — Reatribuicao por inatividade do atendente (v3)

**Status:** v1 em validacao
**App:** `apps/inbox/`
**Cron:** `cron_inatividade_atendente` (sugestao: 1x a cada 5 min)
**Disponivel desde:** 01/06/2026

Quando atendente assume um lead e demora pra responder, hoje **a conversa fica no limbo** ate o encerramento automatico (48h). Essa feature endereca o problema em **2 niveis distintos**, escolhidos por fila.

## Niveis

| Nivel | Detecao | Acao | Default |
|---|---|---|---|
| **A — Nao assumiu** | `assumida=False` ha > X min apos atribuicao | **Realoca automaticamente** para outro agente online da mesma fila. Mensagem de sistema na conversa. Incrementa `realocacoes_count`. | 10 min, max 2 realocacoes |
| **B — Assumiu e parou** | `assumida=True` + ultima msg do contato ha > Y min sem resposta do agente | **Notifica admin** via sino interno. NAO toca na conversa. Idempotente (so 1x por ciclo). | 30 min |

### Por que essa divisao

- Nivel A trata "atendente nao pegou o caso" — realocar e seguro porque o cliente ainda nao tem vinculo com o agente.
- Nivel B trata "atendente engajou mas travou" — o cliente ja conhece o agente; realocar gera atrito. Melhor o admin decidir.

## Configuracao por fila

Em `/inbox/configuracoes/` aba **Filas**, cada fila ganhou bloco "Inatividade do atendente":

```
[ ] Realocar quando atendente nao assumir
    Minutos sem assumir: [ 10 ]
    Maximo de realocacoes: [ 2 ]

[ ] Notificar administrador quando atendente assumir e nao responder
    Minutos sem responder apos assumir: [ 30 ]
```

**Default: ambos desligados** — comportamento atual nao muda. Cliente liga manualmente.

## Pre-requisitos universais (ambos niveis)

O cron so age numa conversa se:
- `status` in `('aberta', 'pendente')`
- `modo_atendimento = 'humano'`
- `fila` nao-nula e fila tem a feature relevante ligada
- Esta dentro do horario de atendimento da fila
- Tem `agente_id` setado

## Modelos atualizados

### `Conversa`
- `data_assumida` (DateTime, nullable) — timestamp do momento que assumiu (clicou Assumir OU enviou primeira msg)
- `realocacoes_count` (PositiveInteger, default=0) — quantas vezes ja foi realocada por inatividade
- `metadata.alerta_inatividade_em` (ISO timestamp) — quando o admin foi alertado da ultima vez. Limpo quando agente responde.

### `FilaInbox` (5 campos novos)
- `realocar_inativo_ativo` (bool)
- `tempo_max_sem_assumir_min` (int, default 10)
- `max_realocacoes` (int, default 2)
- `alerta_admin_inativo_ativo` (bool)
- `tempo_max_sem_responder_min` (int, default 30)

### `HistoricoTransferencia` (campo novo)
- `tipo` (CharField com 5 choices):
  - `atribuicao_inicial` — distribuicao automatica (gerado em `distribuir_conversa`)
  - `transferir_manual` — botao Transferir (gerado em `transferir_conversa`)
  - `realocar_inativo` — realocacao por inatividade (v3, nivel A)
  - `alerta_admin` — alerta de inatividade (v3, nivel B, registro auditivo)
  - `liberar` — conversa liberada sem novo destino (raro)

Agora todo evento de atribuicao gera linha no historico — antes so transferencias manuais eram registradas. Permite reconstruir timeline completa da conversa.

## Fluxo do cron

```
cron_inatividade_atendente (5 min)
  ↓
foreach tenant ativo:
  foreach FilaInbox ativa do tenant:
    if !realocar_inativo_ativo && !alerta_admin_inativo_ativo: skip
    if !horario_fila: skip

    # Nivel A
    if realocar_inativo_ativo:
      conversas atribuidas, nao assumidas, dentro do limite de realocacoes
        if ultima_atribuicao < NOW - tempo_max_sem_assumir_min:
          → realocar_conversa_inativa()

    # Nivel B
    if alerta_admin_inativo_ativo:
      conversas assumidas, com ultima_msg = contato
        if ultima_msg < NOW - tempo_max_sem_responder_min:
          if !metadata.alerta_inatividade_em (idempotente):
            → alertar_admin_inatividade()
```

Idempotencia do nivel B: `metadata.alerta_inatividade_em` so e limpo quando agente responde (verifica na proxima rodada do cron). Sem isso o admin receberia notificacao a cada 5 min.

## UI no inbox

Conversas com `metadata.alerta_inatividade_em` setado recebem:
- **Borda esquerda vermelha** no card
- **Badge "Inativo"** na linha superior
- **Ponto pulsante** no canto direito

Some quando agente responde (cron limpa metadata).

## Auditoria

Toda acao do cron gera linha em `HistoricoTransferencia`:

| Acao | Tipo | Conteudo |
|---|---|---|
| Realocou pra outro agente | `realocar_inativo` | de_agente=X, para_agente=Y, motivo='auto: nao assumiu em 10min' |
| Realocou sem destino (todos offline) | `realocar_inativo` | de_agente=X, para_agente=NULL |
| Notificou admin | `alerta_admin` | de=para=X (nao muda), motivo='admin notificado: 30min sem responder' |

Consultavel via `Conversa.transferencias.all()` ou Django Admin > Inbox > Transferencias.

## Notificacao ao admin (nivel B)

Cria `Notificacao` via `apps.notificacoes`:
- `codigo_tipo='inatividade_atendente'` (TipoNotificacao seedado pela migration 0005)
- Destinatarios: users com permissao `inbox.gerenciar` ou superusers do tenant
- Prioridade: alta
- `url_acao`: `/inbox/?conversa=<id>` (abre diretamente)

## Comando management

```bash
# Roda normal
python manage.py cron_inatividade_atendente

# Simula
python manage.py cron_inatividade_atendente --dry-run

# So um tenant
python manage.py cron_inatividade_atendente --tenant tr-carrion

# So uma fila
python manage.py cron_inatividade_atendente --fila-id 5
```

## Limitacoes conhecidas

- **Sem detecao de presenca real do agente.** Se atendente fechou navegador sem mudar pra Offline, segue como Online — feature B nunca dispara porque ele "parece presente". Quick win paralelo: heartbeat baseado em `ultimo_status_em` (fora do escopo desta feature).
- **Sem escalonamento.** Notifica admin 1x. Se admin nao agir, conversa entra no fluxo normal de encerramento automatico (48h). Roadmap v3.1: escalonar pra 2a notificacao apos +Y min sem acao.
- **Sem WhatsApp/e-mail.** Notificacao so via sino interno. Admin precisa estar logado pra ver. v3.1: canal WhatsApp configuravel.
- **`Nivel B nao funciona em conversas onde agente assumiu mas cliente nao mandou mais nada.`** Se o ultimo movimento e do agente (ou nota de sistema) e o cliente sumiu, o agente nao tem nada pra responder. Feature so dispara quando cliente esta esperando ativamente.

## Esforco total

| Item | Status |
|---|---|
| Modelos + migration 0015 | ✅ |
| Service de realocacao + alerta | ✅ |
| Patch em distribuir/assumir/transferir | ✅ |
| Cron command + dry-run testado | ✅ |
| UI config por fila | ✅ |
| Badge no card + CSS pulsante | ✅ |
| TipoNotificacao seedado | ✅ migration 0005 |
| Doc | ✅ este arquivo |
| Cron deploy EasyPanel | ⏳ aguarda autorizacao |

## Roadmap

| Versao | Mudancas |
|---|---|
| **v3.1** | Heartbeat real de presenca + escalonamento de notificacoes admin |
| **v3.2** | Canal WhatsApp/E-mail pra notificacao admin urgente |
| **v3.3** | Dashboard de inatividade: "Atendentes que mais abandonam", "Tempo medio ate assumir por agente" |
