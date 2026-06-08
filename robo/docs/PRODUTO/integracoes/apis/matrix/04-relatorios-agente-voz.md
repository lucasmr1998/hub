# Matrix API — Relatorios, Agente, Voz, Catalogo

Agrupa endpoints "complementares": gestao de agentes, relatorios analiticos, integracao voz, catalogo de produtos, consultas genericas.

## Agentes

### Criar

`POST /rest/v1/agente` ou `POST /rest/v2/agente`

```json
{
  "nome_agente": "Maria",
  "login": "maria123",
  "nom_senha": "segredo12//",
  "email": "maria@exemplo.com",
  "cod_grupo_horario": 2
}
```

Resposta: `{ "cod_agente": 123, "msg": "Agente inserido com sucesso" }`

### Obter ID do agente por login

`GET /rest/v1/agente/{login}` ou `GET /rest/v2/agente/{login}`

Retorna `{ "cod_agente": 123 }`.

### Resetar senha

`PUT /rest/v1/agenteResetSenha` ou `PUT /rest/v2/agenteResetSenha`

```json
{ "nom_login": "maria123", "nom_senha": "novaSenha123//" }
```

### Adicionar/remover servicos do agente

`POST /rest/v1/agente/servico/{agenteId}` ou `POST /rest/v2/agente/servico/{agenteId}`

```json
{
  "cod_servico": [22, 23],
  "num_prioridade": [9, 10],
  "del_cod_servico": [20]
}
```

### Deslogar agente

`POST /rest/v1/deslogarAgente` ou `POST /rest/v2/deslogarAgente`

Body: `{ "id_agente": 1 }`.

### Listar agentes online

`GET /rest/v1/agentesOnline` ou `GET /rest/v2/agentesOnline`

Query `agente={id}` opcional pra filtrar. Retorna lista com `nom_agente`, `status`, `dat_login`, `tempo_logado`, `nom_pausa`.

### Listar agentes (com filtros)

`GET /rest/v1/agentes` ou `GET /rest/v2/agentes`

Filtros: `cod_agente`, `nome_agente`, `data_cadastro`, `login`, `suspenso` (0/1), `bol_cancelado` (0/1), `data_cancelamento_inicio/fim`, `page`, `limit`.

Paginacao no formato: `{ "page": N, "rows": N, "total": N, "result": [...] }`.

---

## Conta

### Dados de conta/servico/canal

`GET /rest/v1/getDataContaServCanal?data_inicial=...&data_final=...`

Retorna estrutura aninhada com volumes de atendimento por conta -> servico -> canal -> data, com metricas TMI/TME e classificacao por tipo de finalizacao.

---

## Canais

`GET /rest/v2/canais`

Retorna lista de canais habilitados na conta com `id_canal` e nome.

## Status de atendimento

`GET /rest/v2/statusAtendimentos`

Retorna lista de status com IDs. Ver tabela em [README.md](README.md#status-de-atendimento).

---

## Destino

`POST /rest/v2/destino`

Define destino (servico ou flow) pra um canal de uma conta.

```json
{ "id_conta": 1, "id_canal": "2", "tipo_destino": "servico", "id_destino": "1" }
```

---

## Relatorios

Todos paginados via `page`+`limit` (max 300). Datas no formato `YYYY-MM-DD` (alguns usam `YYYY-MM-DD HH:MM:SS`).

### Atendimentos analitico

`GET /rest/v1/relAtAnalitico` ou `GET /rest/v2/relAtAnalitico`

Filtros: `data_inicial`, `data_final`, `id_conta`, `cod_atendimento`, `tipo[]`, `canal[]`, `status[]`, `servico`. Retorna linha por atendimento com todas as datas (entrada, fila, termino), tempos (fila, atendimento, pendencia, TMIC, TMIA), contato, agente, servico, classificacao.

### Estatistico

`GET /rest/v2/relAtEstatistico`

Filtros: + `agrupador` (dia/hora/mes/agente/canal/tag/ano/dia_da_semana/ativo_receptivo/conta/status/classificacao/servico) + `classificacao`, `entrante`. Retorna metricas agregadas por agrupador (TE, TME, TA, TMA, TP, TMP, TMIC, TMIA, qtd 20s, qtd 60s).

### Estatistico de tags

`GET /rest/v1/relEstatisticoTags` ou `GET /rest/v2/relEstatisticoTags`

Como o estatistico mas com 2 agrupadores (`agrupador_1`, `agrupador_2`).

### Login de agentes

`GET /rest/v1/relAgenteLogin` ou `GET /rest/v2/relAgenteLogin`

Filtros: `data_inicial`, `data_final`, `agente`. Retorna sessoes de login/logout com `seg_logado` e `tempo_logado`.

### Pausa de agentes

`GET /rest/v1/relAgentePausa` ou `GET /rest/v2/relAgentePausa`

Filtros: `dat_inicial`, `dat_final`, `pagina`, `cod_agente`, `cod_pausa`.

### Pausas agendadas

`GET /rest/v1/relPausasAgendadas` ou `GET /rest/v2/relPausasAgendadas`

### Produtividade

`GET /rest/v1/relProdutividadePorData` ou `GET /rest/v2/relProdutividadePorData`

Por agente/data: total logado, total pausado, total produtividade, % produtividade.

### Atendimento analitico para exportacao

`GET /rest/v1/relAtendimentoAnaliticoExportacao` ou `GET /rest/v2/relAtendimentoAnaliticoExportacao`

Similar ao analitico mas otimizado pra dump em massa.

### Retencao analitico

`GET /rest/v1/relAnaliticoRetencao` ou `GET /rest/v2/relAnaliticoRetencao`

### Pesquisa (NPS/satisfacao) analitico

`GET /rest/v1/RelPesqAnalitico` ou `GET /rest/v2/RelPesqAnalitico`

Filtros: + `pesquisa` (cod pesquisa). Retorna respostas por pergunta + sintetico (qtd por valor).

### Pesquisa (resumo)

`GET /rest/v1/relPesquisa` ou `GET /rest/v2/relPesquisa`

Resumos: pesquisas enviadas, perguntas respondidas.

### Monitoramento de palavras

`GET /rest/v1/relAtendimentoMonitoramentoPalavra` ou `GET /rest/v2/relAtendimentoMonitoramentoPalavra`

Filtro `palavra=palavra1%26palavra2` (separador `&` URL-encoded). Lista atendimentos onde a palavra foi mencionada.

### Contatos analitico

`GET /rest/v1/relAnaliticoContatos` ou `GET /rest/v2/relAnaliticoContatos`

Dump de contatos cadastrados no periodo (com todos campos: classificacao, redes sociais, telefones, IDs externos).

### Flow analitico

`GET /rest/v1/relFlowAnalitico` ou `GET /rest/v2/relFlowAnalitico`

Eventos detalhados de execucao de flow por atendimento (qual no foi acessado, qual aresta, qual resposta).

### Curadoria analitico

`GET /rest/v1/relCuradoriaAnalitico` ou `GET /rest/v2/relCuradoriaAnalitico`

Eventos de curadoria de intencoes (revisao de classificacao IA).

### TME (Tempo Medio de Espera)

`GET /rest/v1/tme` ou `GET /rest/v2/tme`

Query: `servico`, `conta`, `horas`. Retorna `{ "tme": "00:01:23" }`.

`GET /rest/v1/tmeAtendimento` ou `GET /rest/v2/tmeAtendimento` — TME especifico de um atendimento, retorna tambem `posicao_fila`.

### Eventos analiticos de mensagens

`GET /rest/v2/reportEventosAnaliticoMensagens`

Status detalhado de mensagens disparadas (envio, entrega, leitura). Ver [02-disparos.md](02-disparos.md).

### Requisicoes HTTP feitas pelo flow

`GET /rest/v2/RelRequisicoes`

Log de requisicoes externas feitas pelos flows (debug).

### Variaveis de atendimento

`GET /rest/v2/RelVariaveisAtendimento`

Lista valores de variaveis do flow por atendimento. Util pra reconciliar dado coletado no atendimento com nosso DB (preencher campos do lead).

### Logs de exportacao

`GET /rest/v1/logsExportacao` ou `GET /rest/v2/logsExportacao`

Logs de chamadas a API de exportacao.

---

## Voz

### Atualizar status de chamada de voz

`POST /rest/v2/atualizaStatusChamadaVoz`

```json
{
  "codigo_atendimento": 12345,
  "codigo_agente": 10,
  "status": 1,
  "telefone": "5511999993333",
  "ramal": "1000"
}
```

### Subir gravacao de voz

`POST /rest/v2/gravacoesVoz`

```json
{
  "codigo_atendimento": 12345,
  "url_arquivo": "https://...",
  "nome_arquivo": "call.mp3",
  "base64_arquivo": "<base64>"
}
```

---

## Catalogo

### Listar catalogos

`GET /rest/v2/catalogo?catalogo=Nome&limit=100&page=1`

Retorna catalogos cadastrados (integracao com Facebook Catalog).

### Listar itens de catalogo

`GET /rest/v2/itensCatalogo?item=...&catalogo=...&retailer_id[]=...&limit=100&page=1`

---

## Grupos (WhatsApp Business / Workplace)

`POST /rest/v2/msgGrupo`

```json
{ "cod_grupo": 10, "mensagem": "bom dia grupo" }
```

`POST /rest/v2/workplaceGroup`

```json
{
  "accessToken": "<workplace-token>",
  "groupId": 101851389829103,
  "message": "Hello world!"
}
```

---

## Tabela generica

`GET /rest/v1/tablegeneric?{coluna}=valor&page=1` (v1) ou `GET /rest/v2/tablegeneric?page=1` (v2 — sem filtro por coluna)

Endpoint usado pra consultar tabelas customizadas que o cliente cadastra na Matrix. Util quando o flow precisa olhar uma base interna mantida na Matrix.

---

## Flow — utilitarios

- `POST /rest/v2/checaTrocaSenha` — verifica dias desde ultima troca de senha de usuario (input: `usuario`).
- `POST /rest/v2/checaUltimoLogin` — dias desde ultimo atendimento (input: `telefone`). Ver tambem em [01-atendimento-mensagens.md](01-atendimento-mensagens.md).
- `POST /rest/v2/alteraSenhaFlow` — altera senha via flow.
- `POST /rest/v2/callbackFlowMsg` — envia msg em atendimento via flow (ver [01-atendimento-mensagens.md](01-atendimento-mensagens.md)).
- `GET /rest/v2/AlertaAtivo?cod_conta=N` — alerta ativo na conta (mensagem geral pro flow exibir).

---

## Autenticacao (v2)

`POST /rest/v2/authuser`

```json
{ "login": "seuusuario", "chave": "chavedeautenticacao" }
```

Resposta:

```json
{
  "success": true,
  "message": "autorizado",
  "result": {
    "token": "eyJ0eXAi...",
    "expiry": "2023-06-01 12:10:01",
    "infoUser": { "cod_usuario": 1, "num_permissao": 15 }
  }
}
```

Token expira (geralmente em 1h). Cachear ate `expiry - 60s` e renovar.
