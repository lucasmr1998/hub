# HubSoft API — Atendimento e Ordem de Servico

Endpoints usados pelo fluxo de abertura de OS (instalacao). Hoje sao chamados pelos endpoints wrapper Hubtrix `/api/public/n8n/matrix/*` que a Matrix da Nuvyon consome (ver [../n8n-hubtrix/](../n8n-hubtrix/README.md)).

## Abrir atendimento

`POST /api/v1/integracao/atendimento`

Cria atendimento (sem OS necessariamente). Pre-requisito pra abrir OS depois.

### Body

```json
{
  "id_cliente_servico": 12345,
  "id_tipo_atendimento": 281,
  "id_atendimento_status": 1,
  "descricao": "Solicitacao via Matrix",
  "nome": "Joao Silva",
  "telefone": "34999990000",
  "email": "joao@example.com",
  "id_usuario_responsavel": null,
  "abrir_os": false
}
```

| Campo | Origem |
|---|---|
| `id_cliente_servico` | Body do request da Matrix |
| `id_tipo_atendimento` | `configuracoes_extras['hubsoft']['os_matrix']['id_tipo_atendimento']` |
| `id_atendimento_status` | `os_matrix['id_status_atendimento']` |
| `id_usuario_responsavel` | `os_matrix['id_usuario_responsavel']` (opcional) |

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

### Service

`HubsoftService.abrir_atendimento_os(id_cliente_servico, descricao, nome, telefone, email, id_tipo_atendimento, id_atendimento_status, id_usuario_responsavel, abrir_os=False)`.

Wrapper Hubtrix: `POST /api/public/n8n/matrix/abrir-atendimento/` em [apps/integracoes/views_matrix_os.py:abrir_atendimento](../../../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/views_matrix_os.py).

---

## Abrir OS

`POST /api/v1/integracao/atendimento/ordem_servico` (ou variante por endpoint do HubSoft).

Cria a OS a partir do atendimento existente, com o slot de agenda escolhido pelo cliente.

### Body

```json
{
  "id_atendimento": 9876,
  "id_agenda_ordem_servico": 46,
  "id_tipo_ordem_servico": 4,
  "status": "pendente",
  "data_inicio_programado": "2026-06-05",
  "data_termino_programado": "2026-06-05",
  "hora_inicio_programado": "08:00:00",
  "hora_termino_programado": "09:00:00",
  "tecnicos": [258],
  "disponibilidade": ["manha"]
}
```

| Campo | Origem |
|---|---|
| `id_agenda_ordem_servico` | `os_matrix['id_agenda_ordem_servico']` (override pelo body) |
| `id_tipo_ordem_servico` | `os_matrix['id_tipo_os']` (override pelo body) |
| `status` | `os_matrix['status_os']` (default `pendente`) |
| `tecnicos` | Body (escolhido pelo cliente no Matrix). Aceita int ou array |
| `disponibilidade` | Body. Aceita string ou array (`['manha']` ou `'manha'`) |

### Resposta

```json
{ "status": "success", "ordem_servico": { "id_ordem_servico": 5555, ... } }
```

### Coercao de tipos (importante)

`tecnicos` e `disponibilidade` aceitam lista, string ou int — o view embrulha em lista antes de chamar HubSoft via `_coerce_lista()`. Sem isso, `enumerate('manha')` quebrava a string char-por-char e o HubSoft recebia `{"0":"m","1":"a","2":"n","3":"h","4":"a"}`. Ver [apps/integracoes/views_matrix_os.py:53](../../../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/views_matrix_os.py#L53).

### Service

`HubsoftService.abrir_os(id_atendimento, id_agenda_ordem_servico, id_tipo_ordem_servico, data_inicio_programado, data_termino_programado, hora_inicio_programado, hora_termino_programado, tecnicos, disponibilidade, status)`.

Wrapper Hubtrix: `POST /api/public/n8n/matrix/abrir-os/`.

---

## Consultar agenda — horarios disponiveis

`GET /api/v1/integracao/atendimento/ordem_servico/agenda?id_agenda_ordem_servico=46&data=2026-06-05`

Retorna horarios disponiveis na agenda do tecnico pra uma data. Wrapper Hubtrix aplica filtro de turno (manha/tarde/noite) e retorna so os slots relevantes.

### Resposta resumida

```json
{
  "status": "success",
  "agenda": {
    "id_agenda_ordem_servico": 46,
    "data": "2026-06-05",
    "disponibilidade": [
      { "horario": "07:00:00", "tecnicos": [{"id": 258}, {"id": 132}] },
      { "horario": "08:00:00", "tecnicos": [{"id": 144}] }
    ]
  }
}
```

### Wrapper Hubtrix

`GET /api/public/n8n/matrix/consultar-agenda/?data_referencia=DD/MM/YYYY&turno=manha|tarde|noite`

Filtros de turno: manha (0-12h), tarde (12-18h), noite (18-24h).

Service: `HubsoftService.consultar_agenda(id_agenda, data)`.

---

## Listar atendimentos do cliente

`GET /api/v1/integracao/cliente/atendimento?id_cliente_servico=<id>`

Lista atendimentos abertos/historico de um cliente.

Service: `HubsoftService.listar_atendimentos_cliente(id_cliente_servico, ...)`.

---

## Listar OS do cliente

`GET /api/v1/integracao/cliente/ordem_servico?id_cliente_servico=<id>`

Service: `HubsoftService.listar_os_cliente(id_cliente_servico, ...)`.

---

## Datas sem domingo (utilitario puro)

Wrapper Hubtrix puro — nao chama HubSoft, faz logica de calendario.

`GET /api/public/n8n/matrix/datas-sem-domingo/?data_referencia=DD/MM/YYYY&qtd=5&offset_dias=1`

Retorna proximas `qtd` datas a partir de `data_referencia + offset_dias`, pulando domingos.

```json
{ "status": "success", "datas": ["02/06/2026", "03/06/2026", "04/06/2026", "05/06/2026", "06/06/2026"] }
```

Util pro Matrix preencher `data_instalacao_1/2/3` em sequencia.

---

## Por que 4xx mesmo pra erro HubSoft

> **EasyPanel intercepta 5xx.** O proxy do EasyPanel substitui qualquer 5xx do backend pela propria pagina HTML "Service is not reachable". Como o cliente Matrix espera JSON, todos os catches de `HubsoftServiceError` no wrapper retornam **400** com `{"status":"error","msg":...}` em vez de 502/500 — body chega intacto.

Vale lembrar disso ao debugar: erro 400 que diz "Permissao negada" e do HubSoft, nao do nosso wrapper.

---

## Logs

Cada chamada gera 1 registro em `logs_integracao` com payload enviado + resposta crua (com `_payload_seguro` mascarando `password`/`client_secret`/`token`). Filtrar por tenant + endpoint pra debugar.
