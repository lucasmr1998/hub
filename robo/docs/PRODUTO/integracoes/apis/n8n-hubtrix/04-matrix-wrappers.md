# Hubtrix N8N API — Wrappers Matrix (agendamento e OS HubSoft)

Endpoints consumidos pelo **bot Matrix Brasil** (Nuvyon, FATEPI futuro) pra delegar operacoes HubSoft ao Hubtrix. A logica de orquestracao (agenda, atendimento, OS) vive aqui, falando direto com HubSoft do tenant.

**Base path:** `/api/public/n8n/matrix/`

**Auth:** Bearer token da `IntegracaoAPI` tipo `n8n` ativa do tenant. Decorator `api_token_required` resolve `request.tenant` a partir do token.

Implementacao: [apps/integracoes/views_matrix_os.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/views_matrix_os.py).

## Configuracao por tenant

Cada tenant que usa Matrix precisa ter sua `IntegracaoAPI` HubSoft com o bloco `os_matrix` em `configuracoes_extras`:

```json
{
  "os_matrix": {
    "id_agenda_ordem_servico": 46,
    "id_tipo_atendimento": 281,
    "id_status_atendimento": 1,
    "id_tipo_os": 4,
    "status_os": "pendente",
    "id_usuario_responsavel": null
  }
}
```

Os IDs vem do painel HubSoft do cliente (agenda, tipos de atendimento, etc).

---

## `GET /matrix/datas-sem-domingo/`

Logica pura — **nao chama HubSoft**. Retorna proximas N datas a partir de uma referencia, pulando domingos.

### Query params

| Param | Default | Descricao |
|---|---|---|
| `data_referencia` | hoje | `DD/MM/YYYY` |
| `qtd` | 5 | Quantas datas retornar |
| `offset_dias` | 1 | Dias a partir da referencia |

### Exemplo

```bash
curl 'https://app.hubtrix.com.br/api/public/n8n/matrix/datas-sem-domingo/?data_referencia=01/06/2026&qtd=5' \
  -H 'Authorization: Bearer <token>'
```

### Resposta

```json
{
  "status": "success",
  "datas": ["02/06/2026", "03/06/2026", "04/06/2026", "05/06/2026", "06/06/2026"]
}
```

Matrix le `datas[0]/[1]/[2]` pra preencher `data_instalacao_1/2/3`.

---

## `GET /matrix/consultar-agenda/`

Horarios disponiveis na agenda configurada (`id_agenda_ordem_servico`) pra data/turno especifico.

### Query params

| Param | Descricao |
|---|---|
| `data_referencia` | `DD/MM/YYYY` |
| `turno` | `manha`, `tarde`, ou `noite` |

Faixas de turno: manha (0-12h), tarde (12-18h), noite (18-24h).

### Resposta

```json
{
  "status": "success",
  "dados": {
    "id_agenda_ordem_servico": 46,
    "disponibilidade_turno": [
      { "horario": "07:00:00", "tecnicos": [{"id": 258}, {"id": 132}] },
      { "horario": "08:00:00", "tecnicos": [{"id": 144}] }
    ]
  }
}
```

---

## `POST /matrix/abrir-atendimento/`

Abre atendimento no HubSoft (sem OS necessariamente). Pre-requisito pra abrir OS.

### Body

```json
{
  "id_cliente_servico": 12345,
  "nome": "Joao Silva",
  "telefone": "34999990000",
  "descricao": "Solicitacao via Matrix",
  "email": "joao@example.com"
}
```

`id_tipo_atendimento`, `id_atendimento_status`, `id_usuario_responsavel` vem do `os_matrix` config — nao precisa mandar no body.

### Resposta

```json
{
  "status": "success",
  "atendimento": {
    "id_atendimento": 9876,
    "protocolo": "...",
    "status": "Aberto"
  }
}
```

### Como funciona internamente

Chama `HubsoftService(integracao).abrir_atendimento_os(..., abrir_os=False)` — ver [../hubsoft/02-atendimento-os.md](../hubsoft/02-atendimento-os.md).

---

## `POST /matrix/abrir-os/`

Abre a OS a partir do atendimento + slot escolhido. Acao final do fluxo de instalacao.

### Body

```json
{
  "id_atendimento": 9876,
  "data_inicio_programado": "2026-06-05",
  "data_termino_programado": "2026-06-05",
  "hora_inicio_programado": "08:00:00",
  "hora_termino_programado": "09:00:00",
  "tecnicos": [258],
  "disponibilidade": ["manha"]
}
```

`id_tipo_ordem_servico`, `status` e `id_agenda_ordem_servico` vem do `os_matrix` config (com override pelo body).

### Resposta

```json
{ "status": "success", "ordem_servico": { "id_ordem_servico": 5555, ... } }
```

### Coercao de tipos

`tecnicos` e `disponibilidade` aceitam **lista, string ou int** — o view embrulha em lista antes de chamar HubSoft via `_coerce_lista()`:

```json
"tecnicos": [258]      // OK
"tecnicos": 258        // OK (coercao -> [258])
"disponibilidade": ["manha"]   // OK
"disponibilidade": "manha"     // OK (coercao -> ["manha"])
```

Sem isso, `enumerate('manha')` quebra a string char-por-char e HubSoft recebia `{"0":"m","1":"a","2":"n","3":"h","4":"a"}`. Bug historico que custou caro — coercao defensiva mantida.

---

## Codigos de erro

- **400** — erro de validacao local (`id_atendimento obrigatorio`, `Integracao HubSoft nao configurada`) **ou** erro do HubSoft repassado (permissao, payload invalido).
- **401** — token ausente/invalido.

### Por que 4xx mesmo pra erro HubSoft

> EasyPanel intercepta 5xx do backend e substitui body por HTML "Service is not reachable". Como Matrix espera JSON, todos catches de `HubsoftServiceError` retornam **400** com `{"status":"error","msg":...}` em vez de 5xx — body chega intacto.

---

## Permissoes HubSoft requeridas

A credencial HubSoft do tenant precisa ter as permissoes abaixo liberadas no **painel de Usuarios da API** do HubSoft:

- Consultar agenda de ordem de servico
- **Criar atendimento** (necessaria pra `/abrir-atendimento/`)
- **Abrir ordem de servico** (necessaria pra `/abrir-os/`)

Se faltar permissao, HubSoft retorna `403` com `"O Usuário não possui a permissão desejada!"` e nosso endpoint responde 400 com essa mensagem no `msg`.

---

## Logs

Cada chamada ao HubSoft gera 1 registro em `logs_integracao` com payload enviado e resposta crua — util pra debugar erros de permissao/payload. Filtrar por tenant + endpoint (`/api/v1/integracao/atendimento`, etc).

---

## Fluxo completo (Matrix Nuvyon agendando instalacao)

```
1. Cliente diz "quero contratar" -> Matrix coleta dados
2. Bot Selenium converte prospecto em cliente HubSoft
3. Hubtrix sincroniza cliente -> ServicoClienteHubsoft (id_cliente_servico=12345)
4. Matrix mostra opcoes de data:
   GET /matrix/datas-sem-domingo/  -> 5 datas (data1, data2, data3...)
5. Cliente escolhe data + turno
6. Matrix consulta agenda:
   GET /matrix/consultar-agenda/?data_referencia=05/06/2026&turno=manha
   -> horarios + tecnicos disponiveis
7. Cliente escolhe horario
8. Matrix abre atendimento:
   POST /matrix/abrir-atendimento/  -> id_atendimento=9876
9. Matrix abre OS com slot escolhido:
   POST /matrix/abrir-os/  -> id_ordem_servico=5555
10. Cliente recebe confirmacao via WhatsApp pela propria Matrix.
```

A regra do engine de automacao (`gerar_contrato_hubsoft`) roda em paralelo, sem precisar de chamada externa.
