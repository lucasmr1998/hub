# Atendimento — Models

Os models do atendimento guardam o estado das sessoes ativas e o historico de execucao.

---

## AtendimentoFluxo

Sessao ativa de um lead (ou usuario) em um fluxo.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| lead | FK → LeadProspecto | Lead sendo atendido (nullable — Assistente CRM usa usuario) |
| fluxo | FK → FluxoAtendimento | Fluxo utilizado |
| historico_contato | FK → HistoricoContato | Historico vinculado (opcional) |
| nodo_atual | FK → NodoFluxoAtendimento | Posicao atual no grafo (nullable quando finaliza) |
| status | CharField(30) | iniciado, em_andamento, pausado, completado, abandonado, erro, cancelado |
| questao_atual | PositiveInteger | Indice da questao atual (legado) |
| total_questoes | PositiveInteger | Total de questoes/nodos tipo questao |
| questoes_respondidas | PositiveInteger | Quantas foram respondidas |
| dados_respostas | JSONField | Respostas + variaveis + historico IA + contexto assistente |
| motivo_finalizacao | CharField(30) | completado, sem_resposta, abandonado_usuario, transferido, cancelado_atendente, cancelado_sistema, tempo_limite |
| recontato_tentativas | PositiveInteger | Tentativas de recontato feitas |
| recontato_proximo_em | DateTime | Quando executar proximo recontato |
| score_qualificacao | Integer(1-10) | Score calculado ao finalizar |
| tempo_total | PositiveInteger | Duracao em segundos |

**Tabela:** `atendimentos_fluxo`

### Estrutura do `dados_respostas`

```json
{
    "<nodo_id>": {"resposta": "...", "data_resposta": "...", "titulo": "..."},
    "variaveis": {"classificacao": "...", "curso_interesse": "..."},
    "ia_agente_<nodo_id>": {"messages": [...], "turnos": N},
    "ia_historico_<nodo_id>": [mensagens de um ia_respondedor],
    "_ultima_mensagem": "ultima mensagem do lead",
    "_assistente_usuario_id": <user_id>,
    "_assistente_tenant_id": <tenant_id>,
    "_conversa_id": <conversa_id>
}
```

---

## LogFluxoAtendimento

Registro de cada passo executado no fluxo visual (util para debug e auditoria).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| atendimento | FK → AtendimentoFluxo | Sessao |
| nodo | FK → NodoFluxoAtendimento | Nodo executado (nullable) |
| lead | FK → LeadProspecto | Lead (indexed) |
| tipo_nodo | CharField(30) | Tipo do nodo executado |
| subtipo_nodo | CharField(50) | Subtipo do nodo |
| status | CharField(20) | sucesso, erro, aguardando, agendado, fallback |
| mensagem | TextField | Descricao legivel do que aconteceu |
| dados | JSONField | Dados extras (resposta, branch, score, variaveis) |
| data_execucao | DateTime | Quando executou |

**Tabela:** `atendimento_log_fluxo`

---

## ExecucaoFluxoAtendimento

Fila de execucoes pendentes (delays agendados).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| atendimento | FK → AtendimentoFluxo | Sessao |
| nodo | FK → NodoFluxoAtendimento | Nodo de delay |
| contexto_json | JSONField | Contexto serializado |
| data_agendada | DateTime | Quando executar |
| status | CharField(20) | pendente, executado, cancelado, erro |

**Tabela:** `atendimento_execucao_pendente`

---

## Tabelas (resumo)

| Model | Tabela |
|-------|--------|
| AtendimentoFluxo | `atendimentos_fluxo` |
| NodoFluxoAtendimento | `atendimento_nodofluxo` |
| ConexaoNodoAtendimento | `atendimento_conexaonodo` |
| ExecucaoFluxoAtendimento | `atendimento_execucao_pendente` |
| LogFluxoAtendimento | `atendimento_log_fluxo` |
| RespostaQuestao | `respostas_questao` (legado) |
| TentativaResposta | `tentativas_resposta` (legado) |

Os models `NodoFluxoAtendimento` e `ConexaoNodoAtendimento` sao definidos e usados pelo modulo [Fluxos](../fluxos/).
