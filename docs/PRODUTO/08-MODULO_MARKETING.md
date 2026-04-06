# Módulo Marketing — AuroraISP

**Última atualização:** 04/04/2026
**Status:** 🔧 Em desenvolvimento
**Localização:** `apps/marketing/`

---

## Visão Geral

O módulo Marketing é o motor de automação e inteligência do hub. Cobre campanhas de tráfego pago com detecção automática por palavra-chave, segmentação dinâmica de leads e automações visuais com editor de fluxo (Drawflow). É composto por 3 sub-apps que se integram via signals, services e o engine de execução.

```
Lead chega (WhatsApp/Site/Instagram)
    │
    ▼
┌────────────┐     ┌────────────┐     ┌────────────────┐
│ CAMPANHAS  │────▶│ SEGMENTOS  │────▶│  AUTOMAÇÕES    │
│ Detecção   │     │ Agrupamento│     │  Editor Visual │
│ Atribuição │     │ Regras     │     │  Engine BFS    │
│ ROI        │     │ Preview    │     │  Ações + Delay │
└────────────┘     └────────────┘     └────────────────┘
       │                  │                    │
       ▼                  ▼                    ▼
   N8N / API        Disparo massa        WhatsApp, Email,
   Detecção         Avaliação auto       CRM, Pontos, Webhook
```

**Stack compartilhada:** TenantMixin (multi-tenancy), Django 5.2, DRF, PostgreSQL, Drawflow.js

---

## 1. Campanhas (`apps/marketing/campanhas/`)

### O que faz
Gerencia campanhas de tráfego pago com detecção automática de palavras-chave em mensagens de clientes. Identifica de qual campanha veio cada lead, calcula ROI, taxa de conversão e métricas por plataforma. Integração direta com N8N para detecção em tempo real.

### Models (2)

#### CampanhaTrafego
Tabela: `campanha_trafego` | Unique: (tenant, codigo)

| Grupo | Campos principais |
|-------|-------------------|
| **Identificação** | nome (200), codigo (50, unique/tenant), descricao |
| **Palavra-chave** | palavra_chave (200), tipo_match (exato/parcial/regex), case_sensitive (default False) |
| **Classificação** | plataforma (9 opções: google_ads, facebook_ads, instagram_ads, tiktok_ads, linkedin_ads, email, sms, whatsapp, outro), tipo_trafego (pago/organico/hibrido) |
| **Configuração** | prioridade (1-10, default 5), ativa (default True) |
| **Período** | data_inicio, data_fim (DateField, opcionais) |
| **Comercial** | url_destino (500), orcamento (Decimal 12,2), meta_leads |
| **Estatísticas** | contador_deteccoes (auto), ultima_deteccao (auto) |
| **Visual** | cor_identificacao (hex, default #667eea), ordem_exibicao |
| **Auditoria** | criado_por FK User, criado_em, atualizado_em |

**4 índices:** codigo, ativa, palavra_chave, plataforma

**Propriedades:**

| Propriedade | Retorno | Descrição |
|-------------|---------|-----------|
| `esta_no_periodo` | bool | Se está dentro das datas início/fim |
| `esta_ativa` | bool | Ativa AND dentro do período |
| `total_leads` | int | Count de LeadProspecto com campanha_origem=self |
| `total_conversoes` | int | Detecções com converteu_venda=True |
| `taxa_conversao` | float | (conversões / detecções) × 100 |
| `receita_total` | Decimal | Sum de valor_venda das detecções convertidas |
| `roi` | float | (receita - orçamento) / orçamento × 100 |

#### DeteccaoCampanha
Tabela: `deteccao_campanha`

Registra cada vez que uma palavra-chave de campanha é detectada em uma mensagem de cliente.

| Grupo | Campos principais |
|-------|-------------------|
| **Relacionamentos** | lead FK LeadProspecto, campanha FK CampanhaTrafego |
| **Mensagem** | telefone (20), mensagem_original, mensagem_normalizada (auto), tamanho_mensagem (auto) |
| **Detecção** | trecho_detectado (500), posicao_inicio, posicao_fim, metodo_deteccao (exato/parcial/regex), score_confianca (Decimal 0-100) |
| **Contexto** | eh_primeira_mensagem, origem (whatsapp/sms/email/chat/telefone), timestamp_mensagem |
| **Técnico** | ip_origem, user_agent (500), metadata (JSON) |
| **Validação** | aceita (default True), motivo_rejeicao, rejeitada_por FK User, data_rejeicao |
| **N8N** | processado_n8n, data_processamento_n8n, resposta_n8n (JSON) |
| **Conversão** | converteu_venda, data_conversao, valor_venda (Decimal 12,2) |
| **Auditoria** | detectado_em (auto) |

**6 índices:** telefone, lead, campanha, -detectado_em, aceita, converteu_venda

**`save()` override:**
1. Normaliza mensagem (NFKD, lowercase, remove acentos)
2. Calcula tamanho da mensagem
3. Atualiza contador_deteccoes da campanha

### APIs (4 endpoints)

| Endpoint | Método | Auth | Descrição |
|----------|--------|------|-----------|
| `/marketing/configuracoes/campanhas/` | GET | @login_required | Página de campanhas (template) |
| `/marketing/configuracoes/campanhas/deteccoes/` | GET | @login_required | Página de detecções com filtros |
| `/marketing/api/campanhas/` | GET/POST/PUT/DELETE | @login_required | CRUD completo de campanhas via JSON |
| `/marketing/api/campanhas/detectar/` | POST | @api_token_required | Detecção de campanha (N8N) |

#### API de Detecção (N8N)

Endpoint principal de integração. O N8N envia cada mensagem recebida no WhatsApp e a API detecta automaticamente a campanha de origem.

**Request:**
```json
{
    "telefone": "5589999999999",
    "mensagem": "vi o cupom50 no Instagram",
    "origem": "whatsapp",
    "timestamp": "2024-11-20 10:30:00"
}
```

**Algoritmo:**
1. Normaliza a mensagem (remove acentos, lowercase)
2. Itera campanhas ativas ordenadas por prioridade
3. Aplica método de detecção (exato → parcial → regex)
4. Calcula score de confiança (100% exato, 95% parcial, 90% regex)
5. Cria/vincula lead se não existe
6. Registra DeteccaoCampanha
7. Retorna campanha detectada com score

**Response:**
```json
{
    "success": true,
    "campanha_detectada": {
        "id": 5, "codigo": "CUPOM50", "nome": "Promo 50% OFF",
        "plataforma": "instagram_ads"
    },
    "deteccao": {
        "id": 12345, "trecho_detectado": "cupom50",
        "score_confianca": 95.5, "metodo": "parcial"
    },
    "lead_id": 123,
    "lead_criado": false
}
```

### Templates (1)

- `campanhas.html` — Grid 4 colunas de cards. KPIs no topo (total, ativas, detecções, leads). Modal de criação/edição. Cor fixa do sistema (--primary).

### Admin

**CampanhaTrafegoAdmin:** list com nome/codigo/plataforma/ativa/detecções. Filtros por ativa/plataforma/tipo_trafego. Fieldsets organizados por grupo. Custom method `estatisticas_display()` com tabela HTML de métricas.

**DeteccaoCampanhaAdmin:** list com campanha/telefone/score/origem/aceita. Filtros por aceita/converteu_venda/origem/método. Campos de mensagem e timestamps como readonly.

---

## 2. Segmentos (`apps/marketing/segmentos_urls.py` + `apps/comercial/crm/`)

### O que faz
Agrupa leads por critérios dinâmicos, manuais ou híbridos. Os segmentos são a ponte entre o CRM e as automações: permitem disparo em massa, preview em tempo real das regras, e avaliação automática quando um lead muda. Segmentos ficam no contexto de Marketing (URLs `/marketing/segmentos/`) mas o model vive no CRM.

### Model

#### SegmentoCRM
Tabela: `crm_segmentos` | Unique: (tenant, nome)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(100) | Nome do segmento |
| `descricao` | TextField | Descrição |
| `tipo` | CharField | dinamico, manual, hibrido |
| `regras_filtro` | JSONField | Regras para segmentos dinâmicos |
| `leads` | M2M via MembroSegmento | Leads do segmento |
| `cor_hex` | CharField(7, default #764ba2) | Cor visual |
| `icone_fa` | CharField(50, default fa-users) | Ícone FontAwesome |
| `ultima_atualizacao_dinamica` | DateTimeField | Último sync |
| `total_leads` | PositiveInteger | Cache do total |
| `criado_por` | FK User | Autor |
| `ativo` | BooleanField(True) | Status |

**MembroSegmento** — Through table: segmento FK, lead FK, adicionado_manualmente (bool), adicionado_por FK User.

**Formato das regras de filtro (JSON):**
```json
{
    "regras": [
        {"campo": "origem", "operador": "igual", "valor": "whatsapp"},
        {"campo": "score_qualificacao", "operador": "maior", "valor": "7"},
        {"campo": "cidade", "operador": "contem", "valor": "Teresina"},
        {"campo": "dias_cadastro", "operador": "menor", "valor": "30"}
    ]
}
```

**Campos disponíveis:** origem, score_qualificacao, cidade, estado, bairro, valor, status_api, dias_cadastro
**Operadores:** igual, diferente, contem, maior, menor, maior_igual, menor_igual

### Services (`apps/comercial/crm/services/segmentos.py`)

| Função | O que faz |
|--------|-----------|
| `filtrar_leads_por_regras(regras, queryset)` | Aplica regras ao queryset. Trata `dias_cadastro` como data relativa. Retorna QuerySet filtrado |
| `lead_atende_regras(lead, regras)` | Verifica se um lead atende TODAS as regras (sem query, avaliação in-memory) |
| `atualizar_membros_segmento(segmento)` | Sync completo: remove quem não atende mais (exceto manuais), adiciona novos. Atualiza total_leads e timestamp |
| `avaliar_lead_em_segmentos(lead)` | Avalia lead em TODOS os segmentos dinâmicos/híbridos do tenant. Retorna lista dos segmentos em que entrou |

### Signal

**`avaliar_segmentos_dinamicos`** (post_save LeadProspecto):
- Chama `avaliar_lead_em_segmentos()` a cada save de lead
- Para cada segmento que o lead entrou: dispara evento `lead_entrou_segmento` para o engine de automações
- Contexto inclui: lead, lead_nome, telefone, segmento, segmento_nome

### APIs (7 endpoints)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/marketing/segmentos/` | GET | Lista de segmentos (grid de cards) |
| `/marketing/segmentos/criar/` | GET | Página de criação com rule builder |
| `/marketing/segmentos/<pk>/` | GET | Detalhe com membros |
| `/marketing/segmentos/<pk>/editar/` | GET | Edição com regras |
| `/marketing/segmentos/salvar/` | POST | Salvar segmento (API JSON) |
| `/marketing/segmentos/preview/` | POST | Preview em tempo real (retorna count + amostra de leads) |
| `/marketing/segmentos/<pk>/buscar-leads/` | GET | Buscar leads para adicionar manualmente |
| `/marketing/segmentos/<pk>/adicionar-lead/` | POST | Adicionar lead manualmente |
| `/marketing/segmentos/<pk>/remover-membro/` | POST | Remover membro |
| `/marketing/segmentos/<pk>/disparar-campanha/` | POST | Disparo em massa para leads do segmento |

### Templates (3)

| Template | Descrição |
|----------|-----------|
| `segmentos_lista.html` | Grid de cards (nome, tipo badge, total_leads, ícone, cor) |
| `segmento_criar.html` | Formulário com builder de regras dinâmicas (campo + operador + valor) e preview em tempo real |
| `segmento_detalhe.html` | Lista de membros com ações (adicionar, remover, disparar campanha) |

---

## 3. Automações (`apps/marketing/automacoes/`)

### O que faz
Motor de automação do hub. Define regras que reagem a eventos do sistema (lead criado, venda aprovada, tarefa vencida, etc.) e executam ações automaticamente (enviar WhatsApp, criar tarefa CRM, dar pontos no clube, etc.). Suporta dois modos: legacy linear e editor visual com fluxograma Drawflow.

### Models (7)

#### RegraAutomacao (principal)
Tabela: `automacoes_regraautomacao`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(200) | Nome da automação |
| `descricao` | TextField | Descrição |
| `evento` | CharField(50, blank) | Gatilho (definido como nó no editor visual) |
| `ativa` | BooleanField(True) | Status (indexado) |
| `criado_por` | FK User | Autor |
| `data_criacao` / `data_atualizacao` | DateTime | Timestamps |
| `total_execucoes` / `total_sucesso` / `total_erro` | PositiveInteger | Contadores |
| `modo_fluxo` | BooleanField | True = editor visual, False = linear legado |
| `fluxo_json` | JSONField | Estado do Drawflow para re-import |
| `segmento` | FK SegmentoCRM | Para disparo em massa |
| `max_execucoes_por_lead` | PositiveInteger(0) | 0 = ilimitado |
| `cooldown_horas` | PositiveInteger(0) | Mínimo entre execuções por lead |
| `periodo_limite_horas` | PositiveInteger(24) | Janela de tempo para max_execucoes |

**14 eventos gatilho disponíveis:**

| Evento | Descrição |
|--------|-----------|
| `lead_criado` | Novo lead cadastrado no sistema |
| `lead_qualificado` | Score do lead atinge mínimo (≥ 7) |
| `lead_sem_contato` | Lead sem interação há X dias |
| `oportunidade_movida` | Oportunidade muda de estágio no pipeline |
| `venda_aprovada` | Contrato aprovado no HubSoft |
| `cliente_aniversario` | Cliente completa X dias/meses |
| `indicacao_convertida` | Indicação vira cliente |
| `tarefa_vencida` | Tarefa do CRM vence |
| `docs_validados` | Todos os docs do lead aprovados |
| `lead_entrou_segmento` | Lead entra em segmento dinâmico |
| `disparo_segmento` | Disparo em massa por segmento |
| `mensagem_recebida` | Mensagem recebida no inbox |
| `conversa_aberta` | Nova conversa no inbox |
| `conversa_resolvida` | Conversa resolvida no inbox |

**Propriedade:** `taxa_sucesso` → (total_sucesso / total_execucoes) × 100

#### CondicaoRegra (modo legado)
Tabela: `automacoes_condicaoregra`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra pai |
| `campo` | CharField(100) | Ex: lead.origem, crm.estagio |
| `operador` | CharField | igual, diferente, contem, maior, menor, maior_igual, menor_igual |
| `valor` | CharField(255) | Valor esperado |
| `ordem` | PositiveInteger | Ordem de avaliação |

**Método:** `avaliar(contexto)` — Resolve campo no contexto e compara.

#### AcaoRegra (modo legado)
Tabela: `automacoes_acaoregra`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra pai |
| `tipo` | CharField | 8 tipos de ação (ver tabela abaixo) |
| `configuracao` | TextField | Template com variáveis {{}} |
| `ordem` | PositiveInteger | Ordem de execução |
| `delay_ativo` | BooleanField | Se tem atraso |
| `delay_valor` | PositiveInteger | Valor do atraso |
| `delay_unidade` | CharField | minutos, horas, dias |

#### NodoFluxo (modo visual)
Tabela: `automacoes_nodofluxo`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra pai |
| `tipo` | CharField | trigger, condition, action, delay |
| `subtipo` | CharField(50) | Ex: lead_criado, enviar_whatsapp, campo_check |
| `configuracao` | JSONField | Config específica por tipo |
| `pos_x` / `pos_y` | Integer | Posição visual no canvas |
| `ordem` | PositiveInteger | Ordem de processamento |

#### ConexaoNodo (modo visual)
Tabela: `automacoes_conexaonodo` | Unique: (nodo_origem, nodo_destino, tipo_saida)

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra pai |
| `nodo_origem` | FK NodoFluxo | De onde sai |
| `nodo_destino` | FK NodoFluxo | Para onde vai |
| `tipo_saida` | CharField | default, true (sim), false (não) |

#### ExecucaoPendente
Tabela: `automacoes_execucaopendente`

Fila de ações aguardando execução (delays, agendamentos). Processada pelo cron.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra |
| `nodo` / `acao` | FK NodoFluxo / AcaoRegra | Nó ou ação a executar |
| `lead` | FK LeadProspecto | Lead alvo |
| `contexto_json` | JSONField | Contexto serializado |
| `data_agendada` | DateTimeField (indexado) | Quando executar |
| `status` | CharField | pendente, executado, cancelado, erro |
| `resultado` | TextField | Resultado da execução |

**Índices:** (status, data_agendada), (lead, status)

#### ControleExecucao
Tabela: `automacoes_controleexecucao` | Unique: (lead, regra)

Rate limiting por lead por regra. Controla max_execucoes e cooldown.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead |
| `regra` | FK RegraAutomacao | Regra |
| `total_execucoes_periodo` | PositiveInteger | Execuções na janela |
| `primeira_execucao_periodo` | DateTime | Início da janela |
| `ultima_execucao` | DateTime | Última execução |

#### LogExecucao
Tabela: `automacoes_logexecucao`

Registro de cada execução de automação. Usado no dashboard e na timeline do lead.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `regra` | FK RegraAutomacao | Regra |
| `acao` / `nodo` | FK AcaoRegra / NodoFluxo | O que foi executado |
| `lead` | FK LeadProspecto (indexado) | Lead afetado |
| `status` | CharField | sucesso, erro, agendado, cancelado |
| `evento_dados` | JSONField | Contexto do evento |
| `resultado` | TextField(500) | Mensagem de resultado |
| `data_execucao` | DateTime (auto) | Quando executou |
| `data_agendada` | DateTime | Se foi agendado |

### Engine (`automacoes/engine.py`)

O engine é o coração do módulo. Processa eventos em dois modos: linear legado e BFS em grafo visual.

#### Fluxo de execução

```
Signal dispara evento
    │
    ▼
disparar_evento(evento, contexto, tenant)
    │
    ├── Busca regras ativas para o evento
    ├── Para cada regra:
    │       ├── _verificar_controles() → rate limit / cooldown
    │       ├── Se modo_fluxo=True:
    │       │       └── _processar_fluxo() → BFS no grafo
    │       └── Se modo_fluxo=False:
    │               └── _processar_regra_legacy() → linear
    │
    └── Atualiza contadores (sucesso/erro)
```

#### Modo visual (BFS)

```
Trigger Node (0 inputs, 1 output)
    │ default
    ▼
Condition Node (1 input, 2 outputs)
    ├── true → Action Node → ...
    └── false → Action Node → ...
         │
    Delay Node → ExecucaoPendente → cron retoma
```

`_executar_nodo_e_seguir(regra, nodo, contexto, lead)`:
- **trigger:** passa para saída default
- **condition:** avalia campo/operador/valor, segue true ou false
- **delay:** cria ExecucaoPendente com data_agendada, para (cron retoma)
- **action:** executa, segue para saída default

#### Modo legado (linear)

1. Avalia TODAS as condições (lógica AND)
2. Se alguma falha, interrompe
3. Executa ações sequencialmente
4. Se ação tem delay, agenda via ExecucaoPendente

#### 8 tipos de ação

| Tipo | O que faz | Config |
|------|-----------|--------|
| `enviar_whatsapp` | Envia WhatsApp via N8N webhook | Template com {{variáveis}} |
| `enviar_email` | Envia e-mail via N8N | Assunto + corpo com {{variáveis}} |
| `notificacao_sistema` | Cria notificação no painel | Mensagem |
| `criar_tarefa` | Cria TarefaCRM | Título, tipo, prioridade |
| `mover_estagio` | Move OportunidadeVenda | Pipeline slug + estágio slug |
| `atribuir_responsavel` | Atribui vendedor | Responsável (auto round-robin) |
| `dar_pontos` | Dá pontos no Clube de Benefícios | Pontos + motivo |
| `webhook` | Chama webhook externo | URL, método (GET/POST), headers |

Todas as ações suportam variáveis de contexto: `{{lead_nome}}`, `{{lead_telefone}}`, `{{oportunidade_titulo}}`, etc.

### Signals (`automacoes/signals.py`)

| Signal | Modelo | Evento disparado | Condição |
|--------|--------|-------------------|----------|
| `on_lead_criado` | LeadProspecto (post_save, created) | `lead_criado` | Sempre |
| `on_lead_qualificado` | LeadProspecto (post_save, not created) | `lead_qualificado` | score_qualificacao ≥ 7 |
| `on_oportunidade_movida` | OportunidadeVenda (post_save) | `oportunidade_movida` | Sempre |
| `on_docs_validados` | ImagemLeadProspecto (post_save, status=validado) | `docs_validados` | TODOS os docs validados |
| `on_indicacao_convertida` | Indicacao (post_save, status=convertido) | `indicacao_convertida` | Sempre |

**Contexto disponível nos signals:**

| Variável | Disponível em |
|----------|---------------|
| `lead`, `lead_nome`, `lead_telefone`, `lead_email` | Todos |
| `lead_origem`, `lead_score`, `lead_valor` | lead_criado |
| `oportunidade`, `oportunidade_titulo`, `estagio`, `pipeline`, `responsavel` | oportunidade_movida |
| `indicacao`, `nome_indicado`, `telefone_indicado`, `membro_indicador` | indicacao_convertida |
| `segmento`, `segmento_nome` | lead_entrou_segmento |

### Management Command

**`executar_automacoes_cron`**

```bash
python manage.py executar_automacoes_cron --settings=gerenciador_vendas.settings_local
python manage.py executar_automacoes_cron --dry-run  # apenas simula
python manage.py executar_automacoes_cron --tenant megalink  # tenant específico
```

**Executado a cada 5 minutos.** Responsabilidades:

1. **Processar delays:** busca ExecucaoPendente com status=pendente e data_agendada ≤ now, retoma execução
2. **Lead sem contato:** busca leads sem HistoricoContato há X dias, dispara `lead_sem_contato`
3. **Tarefa vencida:** busca TarefaCRM pendente/em_andamento com data_vencimento vencida, dispara `tarefa_vencida`
4. **Disparo por segmento:** busca regras com segmento vinculado, aplica regras_filtro, dispara `disparo_segmento` para cada lead

### APIs (11 endpoints)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/marketing/automacoes/` | GET | Lista de automações |
| `/marketing/automacoes/criar/` | GET/POST | Criar (nome/desc) → redireciona para editor visual |
| `/marketing/automacoes/dashboard/` | GET | Dashboard central com KPIs e gráfico 30 dias |
| `/marketing/automacoes/<pk>/editar/` | GET/POST | Editar nome/descrição |
| `/marketing/automacoes/<pk>/fluxo/` | GET | Editor visual Drawflow |
| `/marketing/automacoes/<pk>/salvar-fluxo/` | POST | Salvar fluxograma (nodos + conexões) |
| `/marketing/automacoes/<pk>/toggle/` | POST | Ativar/desativar |
| `/marketing/automacoes/<pk>/excluir/` | POST | Excluir |
| `/marketing/automacoes/<pk>/historico/` | GET | Histórico de execuções |
| `/marketing/automacoes/api/lead/<pk>/timeline/` | GET | Timeline de automações do lead (JSON) |

### Templates (5)

| Template | Descrição |
|----------|-----------|
| `lista.html` | Lista com filtros (ativas/pausadas), search, KPIs, cards por regra |
| `criar.html` | Formulário simples (nome + descrição) + aviso do editor visual |
| `editor_fluxo.html` | Editor visual Drawflow. Sidebar com paleta de nós (11 gatilhos, 1 condição, 7 ações, 1 delay). Canvas drag & drop. Painel de configuração lateral. Salva via AJAX |
| `dashboard.html` | Dashboard com Chart.js (execuções 30 dias), top regras, erros recentes, log completo |
| `historico.html` | Tabela de execuções por regra (status, lead, resultado, timestamp) |

### Editor Visual (Drawflow)

O editor visual é o principal diferencial do módulo. Permite montar automações como fluxogramas, similar ao N8N/Zapier.

**Tipos de nó na paleta:**

| Categoria | Nós disponíveis | Inputs/Outputs |
|-----------|-----------------|----------------|
| **Gatilhos** | 11 eventos (lead_criado, venda_aprovada, etc.) | 0 in / 1 out |
| **Condições** | Verificar Campo (campo + operador + valor) | 1 in / 2 out (sim/não) |
| **Ações** | WhatsApp, E-mail, Notificação, Criar Tarefa, Mover Estágio, Dar Pontos, Webhook | 1 in / 1 out |
| **Controle** | Atraso (minutos/horas/dias) | 1 in / 1 out |

**Painel de configuração (abre ao selecionar nó):**
- **Condição:** campo (select com optgroups Lead/CRM), operador, valor
- **Ação:** textarea com template e {{variáveis}}
- **Delay:** número + unidade (minutos/horas/dias)
- **Gatilho:** informativo (sem config)
- Todos: botão "Remover nó"

**Persistência:** estado do Drawflow salvo como JSON em `regra.fluxo_json`. Nodos e conexões persistidos como records no banco (NodoFluxo, ConexaoNodo) para o engine processar.

### Admin

**RegraAutomacaoAdmin:** list com nome/evento/ativa/execuções/taxa_sucesso. Inlines: CondicaoInline, AcaoInline (TabularInline).

**LogExecucaoAdmin:** list com regra/ação/status/data. Readonly fields. Filtros por status e regra.

---

## Integrações entre Submódulos

```
Campanhas ──detecção──▶ Leads (campanha_origem FK)
Campanhas ──N8N API──▶ N8N (mensagem recebida → detecta campanha)
Segmentos ──signal──▶ Automações (lead_entrou_segmento)
Segmentos ──service──▶ Leads (filtrar, avaliar, atualizar membros)
Automações ──signal──▶ Leads (lead_criado, lead_qualificado)
Automações ──signal──▶ CRM (oportunidade_movida, tarefa_vencida)
Automações ──signal──▶ CS (indicacao_convertida)
Automações ──ação──▶ WhatsApp (via N8N webhook)
Automações ──ação──▶ CRM (criar_tarefa, mover_estagio)
Automações ──ação──▶ CS/Clube (dar_pontos)
Automações ──cron──▶ ExecucaoPendente (delays, temporal events)
Automações ──timeline──▶ CRM/Lead (api_lead_timeline)
```

---

## Dependências externas

| Serviço | Uso | Integração |
|---------|-----|------------|
| **N8N** | Envio de WhatsApp e e-mail, detecção de campanha | Webhook POST |
| **Drawflow.js** | Editor visual de fluxo | CDN v0.0.59 |
| **Chart.js** | Gráfico de execuções no dashboard | CDN |

---

## Estatísticas do Módulo

| Métrica | Valor |
|---------|-------|
| **Sub-apps** | 3 (campanhas, automacoes, segmentos) |
| **Models** | 11 (2 campanhas + 7 automações + 2 segmentos) |
| **Views** | 22 funções |
| **Templates** | 9 |
| **APIs** | 22 endpoints |
| **Signals** | 6 |
| **Testes** | 60+ (test_automacoes.py) |
| **Linhas de código** | ~4.500+ (models + views + engine + services) |
