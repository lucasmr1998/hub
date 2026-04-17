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
Motor de automação do hub. Define regras que reagem a eventos do sistema e executam ações automaticamente. Os eventos são disparados de duas formas: **signals** (tempo real, quando algo acontece no sistema) e **cron** (periódico, a cada 5 minutos).

### Como funciona (arquitetura)

```
═══════════════════════════════════════════════════════════════
  TEMPO REAL (Signals Django — post_save)
═══════════════════════════════════════════════════════════════

  Lead salvo (created=True)
      │  signal: on_lead_criado
      ▼
  engine.disparar_evento('lead_criado', contexto, tenant)
      │
      ├── Busca regras ativas com evento='lead_criado'
      ├── Para cada regra:
      │       ├── Verifica controles (rate limit, cooldown)
      │       └── _processar_fluxo() → BFS no grafo Drawflow
      │               │
      │               ├── Trigger Node → segue default
      │               ├── Condition Node → avalia campo/operador/valor
      │               │       ├── true → segue saída 1
      │               │       └── false → segue saída 2
      │               ├── Action Node → executa ação
      │               │       ├── notificacao_sistema → cria Notificacao
      │               │       ├── criar_tarefa → cria TarefaCRM
      │               │       ├── mover_estagio → move OportunidadeVenda
      │               │       ├── atribuir_responsavel → round-robin
      │               │       ├── dar_pontos → MembroClube.saldo
      │               │       └── webhook → POST externo
      │               └── Delay Node → cria ExecucaoPendente (cron retoma)
      │
      └── Registra LogExecucao + atualiza contadores


  Oportunidade salva (created=False)
      │  signal: on_oportunidade_movida
      ▼
  engine.disparar_evento('oportunidade_movida', {estagio: 'demo-agendada', ...})
      │
      └── Mesmo fluxo acima (busca regras, processa grafo)


  Lead salvo (created=False, score >= 7)
      │  signal: on_lead_qualificado
      ▼
  engine.disparar_evento('lead_qualificado', ...)


  Todos os docs do lead validados
      │  signal: on_docs_validados
      ▼
  engine.disparar_evento('docs_validados', ...)


  Indicação convertida
      │  signal: on_indicacao_convertida
      ▼
  engine.disparar_evento('indicacao_convertida', ...)


  Lead entrou em segmento dinâmico
      │  signal: avaliar_segmentos_dinamicos (apps/comercial/crm/signals.py)
      ▼
  engine.disparar_evento('lead_entrou_segmento', ...)


═══════════════════════════════════════════════════════════════
  PERIÓDICO (Cron — executar_automacoes_cron, a cada 5 min)
═══════════════════════════════════════════════════════════════

  python manage.py executar_automacoes_cron
      │
      ├── 1. Processar delays pendentes
      │       Busca ExecucaoPendente com data_agendada <= now
      │       Retoma execução do nodo onde parou
      │
      ├── 2. Lead sem contato
      │       Para cada regra com evento='lead_sem_contato':
      │           Extrai dias da condição (ex: 2 dias)
      │           Busca leads com último HistoricoContato antes do limite
      │           Exclui leads já disparados no período
      │           Dispara: engine.disparar_evento('lead_sem_contato', {
      │               dias_sem_contato: 2, lead: ..., lead_nome: ...
      │           })
      │
      ├── 3. Tarefa vencida
      │       Busca TarefaCRM pendente/em_andamento com data_vencimento vencida
      │       Dispara: engine.disparar_evento('tarefa_vencida', ...)
      │
      └── 4. Disparo por segmento
              Para cada regra com segmento vinculado:
              Aplica regras_filtro do segmento
              Dispara evento para cada lead do segmento


═══════════════════════════════════════════════════════════════
  RESUMO: Quem dispara o quê
═══════════════════════════════════════════════════════════════

  ┌─────────────────────────┬──────────────┬────────────────────────────┐
  │ Evento                  │ Disparado por│ Quando                     │
  ├─────────────────────────┼──────────────┼────────────────────────────┤
  │ lead_criado             │ Signal       │ Lead salvo (created=True)  │
  │ lead_qualificado        │ Signal       │ Lead score >= 7            │
  │ oportunidade_movida     │ Signal       │ Oportunidade salva         │
  │ docs_validados          │ Signal       │ Todos docs status=validado │
  │ indicacao_convertida    │ Signal       │ Indicação status=convertido│
  │ lead_entrou_segmento    │ Signal       │ Lead avaliado em segmento  │
  │ mensagem_recebida       │ Signal       │ Mensagem tipo=contato      │
  │ conversa_aberta         │ Signal       │ Conversa criada            │
  │ conversa_resolvida      │ Signal       │ Conversa status=resolvida  │
  ├─────────────────────────┼──────────────┼────────────────────────────┤
  │ lead_sem_contato        │ Cron (5min)  │ Lead sem HistoricoContato  │
  │ tarefa_vencida          │ Cron (5min)  │ TarefaCRM data vencida     │
  │ disparo_segmento        │ Cron (5min)  │ Regra com segmento FK      │
  ├─────────────────────────┼──────────────┼────────────────────────────┤
  │ venda_aprovada          │ Signal*      │ *Pendente implementação    │
  │ cliente_aniversario     │ Cron*        │ *Pendente implementação    │
  └─────────────────────────┴──────────────┴────────────────────────────┘

  * = evento definido no model mas signal/cron ainda não implementado
```

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

**Contexto disponível nos signals (variáveis que podem ser usadas nas condições e templates):**

| Variável | Tipo | Disponível em |
|----------|------|---------------|
| `lead` | Objeto LeadProspecto | Todos (exceto indicacao) |
| `lead_nome` | String | Todos |
| `lead_telefone` | String | lead_criado, lead_sem_contato |
| `lead_email` | String | lead_criado |
| `lead_origem` | String | lead_criado |
| `lead_score` | Integer | lead_criado, lead_qualificado |
| `lead_valor` | String | lead_criado |
| `telefone` | String (alias) | Todos |
| `nome` | String (alias) | Todos |
| `estagio` | String (**slug** do estágio) | oportunidade_movida |
| `estagio_nome` | String (nome amigável) | oportunidade_movida |
| `pipeline` | String (slug) | oportunidade_movida |
| `pipeline_nome` | String (nome amigável) | oportunidade_movida |
| `oportunidade` | Objeto | oportunidade_movida |
| `oportunidade_titulo` | String | oportunidade_movida |
| `responsavel` | String (nome completo) | oportunidade_movida |
| `dias_sem_contato` | Integer | lead_sem_contato (cron) |
| `indicacao` | Objeto | indicacao_convertida |
| `nome_indicado` | String | indicacao_convertida |
| `telefone_indicado` | String | indicacao_convertida |
| `membro_indicador` | String | indicacao_convertida |
| `segmento` | Objeto | lead_entrou_segmento |
| `segmento_nome` | String | lead_entrou_segmento |

**Campos disponíveis para condições no editor visual:**

| Campo | Chave no contexto | Quando usar |
|-------|-------------------|-------------|
| Origem | `lead.origem` | lead_criado |
| Score | `lead.score_qualificacao` | lead_criado, lead_qualificado |
| Cidade | `lead.cidade` | lead_criado |
| Estado | `lead.estado` | lead_criado |
| Valor | `lead.valor` | lead_criado |
| Campanha | `lead.campanha` | lead_criado |
| Estágio | `estagio` | oportunidade_movida (slug: "demo-agendada") |
| Estágio (CRM) | `crm.estagio` | Alias, resolve para estagio |
| Pipeline | `crm.pipeline` | oportunidade_movida |
| Responsável | `crm.responsavel` | oportunidade_movida |
| Dias sem contato | `dias_sem_contato` | lead_sem_contato (cron) |
| Dias como cliente | `cliente.dias_ativo` | cliente_aniversario |
| Plano | `cliente.plano` | venda_aprovada |

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

O editor visual e o principal diferencial do modulo. Permite montar automacoes como fluxogramas, similar ao N8N/Zapier.

**Tipos de no na paleta:**

| Categoria | Nos disponiveis | Inputs/Outputs |
|-----------|-----------------|----------------|
| **Gatilhos** | 11 eventos (lead_criado, venda_aprovada, etc.) | 0 in / 1 out |
| **Condicoes** | Verificar Campo (campo + operador + valor) | 1 in / 2 out (sim/nao) |
| **Acoes** | WhatsApp, E-mail, Notificacao, Criar Tarefa, Mover Estagio, Atribuir Responsavel, Dar Pontos, Webhook | 1 in / 1 out |
| **Controle** | Atraso (minutos/horas/dias) | 1 in / 1 out |

**Painel de configuracao especifica por tipo (abre ao selecionar no):**

Gatilhos:
- **Oportunidade movida:** Pipeline (select), estagio de (select filtrado), estagio para (select filtrado)
- **Lead sem contato:** Dias sem contato (numero)
- **Entrou em segmento:** Segmento (select com segmentos do CRM)
- **Mensagem recebida:** Canal (select: WhatsApp/Email/Widget)
- Outros gatilhos: informativo (disparam sempre)

Condicoes:
- **Campo:** select com optgroups (Lead: origem/score/cidade/estado/valor/status/email/cpf | CRM: estagio/pipeline/responsavel | Temporal: dias sem contato)
- **Operador:** igual, diferente, contem, maior, menor, maior ou igual, menor ou igual
- **Valor:** campo dinamico que muda conforme o campo selecionado:
  - Origem → select com origens (site, facebook, whatsapp...)
  - Status → select com status do lead
  - Estagio → select com estagios de todos os pipelines
  - Pipeline → select com pipelines
  - Responsavel → select com usuarios staff
  - Estado → select com UFs
  - Demais → input texto livre

Acoes:
- **Enviar WhatsApp:** Mensagem com variaveis {{lead_nome}}, {{lead_telefone}}...
- **Enviar Email:** Assunto + corpo com variaveis
- **Notificacao:** Titulo + mensagem
- **Criar Tarefa:** Titulo, tipo (select: ligacao/followup/visita/whatsapp/email), prioridade (select: baixa/normal/alta/urgente)
- **Mover Estagio:** Pipeline (select), estagio destino (select filtrado por pipeline)
- **Atribuir Responsavel:** Modo (round-robin/fixo), responsavel (select com usuarios staff)
- **Dar Pontos:** Quantidade + motivo
- **Webhook:** URL, metodo (POST/GET), payload JSON

Controle:
- **Atraso:** Tempo + unidade (minutos/horas/dias)

Todos os nos: botao "Remover no"

**Persistencia:** estado do Drawflow salvo como JSON em `regra.fluxo_json`. Nodos e conexoes persistidos como records no banco (NodoFluxo, ConexaoNodo) para o engine processar. Se `fluxo_json` estiver vazio mas existirem nodos no banco, o editor reconstroi o grafo automaticamente.

### Testes E2E

Management command `testar_automacoes` valida todos os componentes end-to-end:

```bash
python manage.py testar_automacoes --settings=gerenciador_vendas.settings_local
```

18 testes cobrindo:
- **T1:** Gatilho via signal real (cria lead → dispara → verifica notificacao no banco + lead no log)
- **T2:** Condicao com branching (score > 5 → branch TRUE executa, FALSE nao)
- **T3:** Acao notificacao (verifica criacao no banco com variaveis substituidas)
- **T4:** Acao criar tarefa (verifica no CRM: titulo, lead, responsavel)
- **T5:** Delay + pendentes (cria pendente → verifica que acao NAO executa → simula tempo → executa → verifica resultado)
- **T6:** Rate limit (2 permitidas, 3a bloqueada)
- **T7:** Fluxo completo E2E (trigger → condicao cidade=Recife → TRUE cria tarefa → FALSE nao executa)
- **T8:** Substituicao de variaveis (simples e de objeto)

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
