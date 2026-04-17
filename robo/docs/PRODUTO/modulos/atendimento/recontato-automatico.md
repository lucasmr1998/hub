# Atendimento — Recontato Automatico

Quando o lead para de responder no meio do fluxo, o sistema envia mensagens automaticas para retomar o contato.

---

## Configuracao (por fluxo)

Cada fluxo tem `recontato_ativo` (bool) e `recontato_config` (JSON):

- **tentativas**: lista com `tempo_minutos` e `mensagem` para cada tentativa
- **usar_ia**: se true, gera mensagem com IA baseada no contexto
- **acao_final**: `abandonar` (finaliza) ou `transferir_humano` (envia para fila)

Exemplo:

```json
{
  "tentativas": [
    {"tempo_minutos": 30, "mensagem": "Oi! Ainda esta ai?"},
    {"tempo_minutos": 120, "mensagem": "So conferindo se recebeu a ultima mensagem."},
    {"tempo_minutos": 1440, "mensagem": "Vou encerrar por aqui, qualquer coisa chama."}
  ],
  "usar_ia": false,
  "acao_final": "abandonar"
}
```

---

## Campos no AtendimentoFluxo

- `motivo_finalizacao`: completado, sem_resposta, abandonado_usuario, transferido, cancelado_atendente, cancelado_sistema, tempo_limite
- `recontato_tentativas`: contador de tentativas enviadas
- `recontato_proximo_em`: datetime do proximo recontato agendado

---

## Cron

```
python manage.py executar_recontato
```

Roda a cada 5 minutos. Detecta atendimentos parados (nodo que pausa e sem resposta), envia mensagem, incrementa tentativa, ou finaliza se esgotou.

Ver detalhes no modulo [ops/02-CRON.md](../../ops/02-CRON.md).

---

## Retomada

Quando o lead responde apos recontato, o signal reseta `recontato_tentativas` e retoma o fluxo automaticamente de onde parou.
