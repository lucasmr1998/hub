# Automacoes — Models

7 models organizados em 3 grupos: regra principal, grafo visual, execucao e logs.

---

## RegraAutomacao (principal)

**Tabela:** `automacoes_regraautomacao`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` | CharField(200) | Nome da automacao |
| `descricao` | TextField | Descricao |
| `evento` | CharField(50, blank) | Gatilho (definido como no no editor visual) |
| `ativa` | BooleanField(True) | Status (indexado) |
| `criado_por` | FK User | Autor |
| `data_criacao` / `data_atualizacao` | DateTime | Timestamps |
| `total_execucoes` / `total_sucesso` / `total_erro` | PositiveInteger | Contadores |
| `modo_fluxo` | BooleanField | True = editor visual, False = linear legado |
| `fluxo_json` | JSONField | Estado do Drawflow para re-import |
| `segmento` | FK SegmentoCRM | Para disparo em massa |
| `max_execucoes_por_lead` | PositiveInteger(0) | 0 = ilimitado |
| `cooldown_horas` | PositiveInteger(0) | Minimo entre execucoes por lead |
| `periodo_limite_horas` | PositiveInteger(24) | Janela de tempo para max_execucoes |

**Propriedade:** `taxa_sucesso` → (`total_sucesso` / `total_execucoes`) × 100

---

## 14 eventos gatilho disponiveis

| Evento | Descricao |
|--------|-----------|
| `lead_criado` | Novo lead cadastrado |
| `lead_qualificado` | Score do lead atinge minimo (≥ 7) |
| `lead_sem_contato` | Lead sem interacao ha X dias |
| `oportunidade_movida` | Oportunidade muda de estagio no pipeline |
| `venda_aprovada` | Contrato aprovado no HubSoft |
| `cliente_aniversario` | Cliente completa X dias/meses |
| `indicacao_convertida` | Indicacao vira cliente |
| `tarefa_vencida` | Tarefa do CRM vence |
| `docs_validados` | Todos os docs do lead aprovados |
| `lead_entrou_segmento` | Lead entra em segmento dinamico |
| `disparo_segmento` | Disparo em massa por segmento |
| `mensagem_recebida` | Mensagem recebida no inbox |
| `conversa_aberta` | Nova conversa no inbox |
| `conversa_resolvida` | Conversa resolvida no inbox |

---

## Grafo visual

### NodoFluxo

**Tabela:** `automacoes_nodofluxo`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra pai |
| `tipo` | CharField | trigger / condition / action / delay |
| `subtipo` | CharField(50) | Ex: lead_criado, enviar_whatsapp, campo_check |
| `configuracao` | JSONField | Config especifica por tipo |
| `pos_x` / `pos_y` | Integer | Posicao visual no canvas |
| `ordem` | PositiveInteger | Ordem de processamento |

### ConexaoNodo

**Tabela:** `automacoes_conexaonodo` | **Unique:** `(nodo_origem, nodo_destino, tipo_saida)`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra pai |
| `nodo_origem` | FK NodoFluxo | De onde sai |
| `nodo_destino` | FK NodoFluxo | Para onde vai |
| `tipo_saida` | CharField | default / true (sim) / false (nao) |

---

## Modo legado

### CondicaoRegra

**Tabela:** `automacoes_condicaoregra`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra pai |
| `campo` | CharField(100) | Ex: lead.origem, crm.estagio |
| `operador` | CharField | igual / diferente / contem / maior / menor / maior_igual / menor_igual |
| `valor` | CharField(255) | Valor esperado |
| `ordem` | PositiveInteger | Ordem de avaliacao |

**Metodo:** `avaliar(contexto)` — Resolve campo no contexto e compara.

### AcaoRegra

**Tabela:** `automacoes_acaoregra`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra pai |
| `tipo` | CharField | 8 tipos de acao (ver [engine.md](engine.md)) |
| `configuracao` | TextField | Template com variaveis `{{}}` |
| `ordem` | PositiveInteger | Ordem de execucao |
| `delay_ativo` | BooleanField | Se tem atraso |
| `delay_valor` | PositiveInteger | Valor do atraso |
| `delay_unidade` | CharField | minutos / horas / dias |

---

## Execucao e logs

### ExecucaoPendente

**Tabela:** `automacoes_execucaopendente`

Fila de acoes aguardando execucao (delays, agendamentos). Processada pelo cron.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra |
| `nodo` / `acao` | FK NodoFluxo / AcaoRegra | No ou acao a executar |
| `lead` | FK LeadProspecto | Lead alvo |
| `contexto_json` | JSONField | Contexto serializado |
| `data_agendada` | DateTimeField (indexado) | Quando executar |
| `status` | CharField | pendente / executado / cancelado / erro |
| `resultado` | TextField | Resultado da execucao |

**Indices:** `(status, data_agendada)`, `(lead, status)`

### ControleExecucao

**Tabela:** `automacoes_controleexecucao` | **Unique:** `(lead, regra)`

Rate limiting por lead por regra. Controla `max_execucoes` e cooldown.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead |
| `regra` | FK RegraAutomacao | Regra |
| `total_execucoes_periodo` | PositiveInteger | Execucoes na janela |
| `primeira_execucao_periodo` | DateTime | Inicio da janela |
| `ultima_execucao` | DateTime | Ultima execucao |

### LogExecucao

**Tabela:** `automacoes_logexecucao`

Registro de cada execucao de automacao. Usado no dashboard e na timeline do lead.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra |
| `acao` / `nodo` | FK AcaoRegra / NodoFluxo | O que foi executado |
| `lead` | FK LeadProspecto (indexado) | Lead afetado |
| `status` | CharField | sucesso / erro / agendado / cancelado |
| `evento_dados` | JSONField | Contexto do evento |
| `resultado` | TextField(500) | Mensagem de resultado |
| `data_execucao` | DateTime (auto) | Quando executou |
| `data_agendada` | DateTime | Se foi agendado |
