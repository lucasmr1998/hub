# Módulo de Automações — AuroraISP

**Última atualização:** 03/04/2026
**Status:** ✅ Implementado (Phase 1 a 7 concluídas)
**Localização:** `apps/marketing/automacoes/`

---

## Visão Geral

O módulo de Automações é o motor central do Marketing da AuroraISP. Permite que provedores criem regras visuais do tipo "Quando X acontecer, se Y, então faça Z" com fluxos condicionais (if/else), delays, ações encadeadas e integração com segmentos.

**Dois modos de operação:**
- **Legacy (linear):** evento → condições AND → ações sequenciais (compatibilidade com regras antigas)
- **Fluxo visual (grafo):** editor drag & drop com nós conectáveis, branching if/else, delays reais

---

## Arquitetura

### Models

| Model | Tabela | Descrição |
|-------|--------|-----------|
| `RegraAutomacao` | `automacoes_regraautomacao` | Regra principal: nome, evento, ativa, contadores, modo (legacy/fluxo), controles |
| `CondicaoRegra` | `automacoes_condicaoregra` | Condição do modo legacy: campo + operador + valor |
| `AcaoRegra` | `automacoes_acaoregra` | Ação do modo legacy: tipo + configuração + delay |
| `NodoFluxo` | `automacoes_nodofluxo` | Nó do fluxograma: trigger, condition, action ou delay |
| `ConexaoNodo` | `automacoes_conexaonodo` | Aresta entre dois nós: default, true ou false |
| `ExecucaoPendente` | `automacoes_execucaopendente` | Fila de ações com delay aguardando execução |
| `ControleExecucao` | `automacoes_controleexecucao` | Rate limiting por lead por regra |
| `LogExecucao` | `automacoes_logexecucao` | Registro de cada execução com FK para lead e nodo |

### Campos importantes de `RegraAutomacao`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField | Nome da regra |
| `evento` | CharField (choices) | Evento gatilho (ver lista abaixo) |
| `ativa` | BooleanField | Liga/desliga a regra |
| `modo_fluxo` | BooleanField | `False` = legacy linear, `True` = fluxograma visual |
| `fluxo_json` | JSONField | Estado salvo do editor Drawflow para re-import |
| `segmento` | FK → SegmentoCRM | Segmento para disparo em massa (opcional) |
| `max_execucoes_por_lead` | int | Máximo de execuções por lead no período (0 = ilimitado) |
| `cooldown_horas` | int | Horas mínimas entre execuções para o mesmo lead |
| `periodo_limite_horas` | int | Janela de tempo para o max_execucoes (default 24h) |
| `total_execucoes` | int | Contador total de execuções |
| `total_sucesso` | int | Contador de sucesso |
| `total_erro` | int | Contador de erros |

---

## Eventos Disponíveis

### Via Signal (tempo real)

| Evento | Código | Signal | Quando dispara |
|--------|--------|--------|----------------|
| Novo lead criado | `lead_criado` | `post_save` LeadProspecto (created=True) | Lead entra no sistema via WhatsApp/site |
| Lead qualificado | `lead_qualificado` | `post_save` LeadProspecto (score >= 7) | Score do lead muda para >= 7 |
| Oportunidade movida | `oportunidade_movida` | `post_save` OportunidadeVenda (created=False) | Card arrastado no Kanban |
| Documentos validados | `docs_validados` | `post_save` ImagemLeadProspecto (status=validado) | Todos os docs do lead aprovados |
| Indicação convertida | `indicacao_convertida` | `post_save` Indicacao (status=convertido) | Indicação vira cliente |
| Lead entrou em segmento | `lead_entrou_segmento` | Disparado pelo signal de segmentos dinâmicos | Lead atende regras de um segmento |

### Via Cron (management command)

| Evento | Código | Quando verifica |
|--------|--------|-----------------|
| Lead sem contato | `lead_sem_contato` | Lead sem histórico de contato há X dias |
| Tarefa vencida | `tarefa_vencida` | TarefaCRM com status pendente e data_vencimento < agora |
| Venda aprovada | `venda_aprovada` | Não implementado (precisa webhook HubSoft) |
| Aniversário de cliente | `cliente_aniversario` | Não implementado |
| Disparo por segmento | `disparo_segmento` | Para todos os leads de um segmento (massa) |

### Flag de skip

Cada signal verifica `getattr(instance, '_skip_automacao', False)` antes de disparar. Para importação em massa, setar `lead._skip_automacao = True` antes do save.

---

## Engine de Execução

### Arquivo: `apps/marketing/automacoes/engine.py`

### Fluxo principal

```
disparar_evento(evento, contexto, tenant)
  ├── Busca regras ativas para o evento no tenant
  ├── Para cada regra:
  │   ├── Verifica controles (max_execucoes, cooldown)
  │   ├── Se modo_fluxo=False: _processar_regra_legacy()
  │   │   ├── Avalia condições (AND)
  │   │   └── Executa ações sequenciais
  │   └── Se modo_fluxo=True: _processar_fluxo()
  │       ├── Encontra nodo trigger
  │       └── BFS no grafo: _executar_nodo_e_seguir()
  │           ├── trigger → segue conexões default
  │           ├── condition → avalia → segue 'true' ou 'false'
  │           ├── delay → cria ExecucaoPendente → para
  │           └── action → executa → segue conexões default
  └── Registra log em LogExecucao
```

### Adaptador NodoFluxo → AcaoRegra

A classe `_NodoAcaoAdapter` converte a config JSON do `NodoFluxo` para a interface texto que os executores existentes esperam. Isso permite reutilizar os 6 executores sem duplicação.

### Controles de execução

```python
_verificar_controles(regra, lead)
```

1. Se `max_execucoes_por_lead == 0` e `cooldown_horas == 0`: sempre passa
2. Busca/cria `ControleExecucao` para o par (lead, regra)
3. Se período expirou: reseta contadores
4. Verifica max execuções no período
5. Verifica cooldown desde última execução
6. Atualiza contadores

### Executar pendentes (delays)

```python
executar_pendentes(tenant=None)
```

Chamado pelo cron. Busca `ExecucaoPendente` com `status=pendente` e `data_agendada <= agora`. Para cada:
- Se tem `nodo`: retoma o grafo a partir das conexões de saída do nodo de delay
- Se tem `acao` (legacy): executa a ação diretamente
- Atualiza status para `executado` ou `erro`

---

## Ações Implementadas

| Tipo | Código | O que faz | Config esperada |
|------|--------|-----------|-----------------|
| WhatsApp | `enviar_whatsapp` | POST para webhook N8N | Mensagem com `{{variáveis}}` |
| Notificação | `notificacao_sistema` | Cria Notificacao no sistema | Mensagem com `{{variáveis}}` |
| Criar Tarefa | `criar_tarefa` | Cria TarefaCRM | `Título: ...\nTipo: ligacao\nPrioridade: alta` |
| Mover Estágio | `mover_estagio` | Move OportunidadeVenda | `Estágio: slug-do-estagio` |
| Dar Pontos | `dar_pontos` | Adiciona saldo ao MembroClube | `Pontos: 50\nMotivo: ...` |
| Webhook | `webhook` | Chama URL externa | `URL: https://...\nMétodo: POST` |
| E-mail | `enviar_email` | Não implementado | — |
| Atribuir Responsável | `atribuir_responsavel` | Não implementado | — |

### Substituição de variáveis

O template de mensagem suporta `{{variável}}`. Variáveis disponíveis dependem do evento:

| Variável | Origem |
|----------|--------|
| `{{nome}}` | `contexto['nome']` (alias para nome do lead) |
| `{{telefone}}` | `contexto['telefone']` |
| `{{lead_nome}}` | `lead.nome_razaosocial` |
| `{{lead_email}}` | `lead.email` |
| `{{lead_telefone}}` | `lead.telefone` |
| `{{lead_score}}` | `lead.score_qualificacao` |
| `{{lead_origem}}` | `lead.origem` |
| `{{lead_valor}}` | `lead.valor` |
| `{{segmento_nome}}` | `segmento.nome` (quando evento = lead_entrou_segmento) |

---

## Editor Visual (Drawflow)

### Biblioteca

**Drawflow** (vanilla JS, 12KB, zero dependências, MIT)
- CDN: `https://cdn.jsdelivr.net/gh/jerosoler/Drawflow@0.0.59/dist/drawflow.min.js`
- Docs: https://github.com/jerosoler/Drawflow

### Layout do editor

```
┌─────────────────────────────────────────────────────────┐
│ ← Nome da Regra                    [Ativa] [Salvar]    │
├──────────┬────────────────────────────┬─────────────────┤
│ PALETA   │                            │ CONFIG PANEL    │
│          │                            │ (aparece ao     │
│ Gatilhos │     CANVAS DRAWFLOW        │  clicar num nó) │
│ Condições│                            │                 │
│ Ações    │     (drag & drop)          │ Campo: [...]    │
│ Controle │                            │ Operador: [..] │
│          │                            │ Valor: [...]    │
└──────────┴────────────────────────────┴─────────────────┘
```

### Paleta de nós (sidebar esquerda)

| Categoria | Nós |
|-----------|-----|
| **Gatilhos** | O evento da regra (definido na criação) |
| **Condições** | Verificar Campo (if/else com 2 saídas) |
| **Ações** | WhatsApp, E-mail, Notificação, Criar Tarefa, Mover Estágio, Dar Pontos, Webhook |
| **Controle** | Atraso (delay em minutos/horas/dias) |

### Tipos de nó

| Tipo | Inputs | Outputs | Comportamento |
|------|--------|---------|---------------|
| `trigger` | 0 | 1 (default) | Ponto de entrada do fluxo |
| `condition` | 1 | 2 (true/false) | Avalia campo+operador+valor, segue branch |
| `action` | 1 | 1 (default) | Executa ação, segue para o próximo |
| `delay` | 1 | 1 (default) | Cria ExecucaoPendente, para execução (retoma via cron) |

### Configuração por tipo de nó (painel direito)

**Condição:**
- Campo (select): lead.origem, lead.score_qualificacao, lead.cidade, lead.estado, lead.valor, estagio
- Operador (select): igual, diferente, contém, maior, menor
- Valor (text)

**Ação:**
- Mensagem/Config (textarea): template com `{{variáveis}}`

**Delay:**
- Tempo (number) + Unidade (minutos/horas/dias)

### Serialização

**Salvar:** `editor.export()` → JSON → POST `/marketing/automacoes/<pk>/salvar-fluxo/`

O backend recebe:
```json
{
  "drawflow_state": { /* estado bruto do Drawflow para re-import */ },
  "nodos": [
    {"id_temp": "1", "tipo": "trigger", "subtipo": "lead_criado", "config": {}, "pos_x": 100, "pos_y": 200},
    {"id_temp": "2", "tipo": "condition", "subtipo": "campo_check", "config": {"campo": "lead.origem", "operador": "igual", "valor": "whatsapp"}, "pos_x": 300, "pos_y": 200}
  ],
  "conexoes": [
    {"origem": "1", "destino": "2", "tipo_saida": "default"}
  ]
}
```

**Carregar:** view passa `regra.fluxo_json` → `editor.import(data)` no JS.

---

## Management Command (Cron)

### Arquivo: `apps/marketing/automacoes/management/commands/executar_automacoes_cron.py`

### Uso

```bash
# Execução normal (todos os tenants)
python manage.py executar_automacoes_cron --settings=gerenciador_vendas.settings

# Simulação (não executa, só mostra)
python manage.py executar_automacoes_cron --dry-run

# Tenant específico
python manage.py executar_automacoes_cron --tenant megalink
```

### Configuração crontab

```
*/5 * * * * cd /path/to/project && python manage.py executar_automacoes_cron --settings=gerenciador_vendas.settings >> /var/log/automacoes.log 2>&1
```

### O que faz (por tenant)

1. **Executa pendentes:** busca `ExecucaoPendente` com `data_agendada <= agora` e executa
2. **Lead sem contato:** detecta leads com último histórico > X dias e dispara `lead_sem_contato`
3. **Tarefa vencida:** detecta tarefas pendentes com `data_vencimento < agora` e dispara `tarefa_vencida`
4. **Disparo por segmento:** para regras com `evento=disparo_segmento` e segmento associado, itera leads do segmento

### Proteção contra duplicatas

Para `lead_sem_contato`: verifica se já existe `LogExecucao` para o lead nessa regra dentro do período, evitando disparar repetidamente.

---

## Dashboard Central

### URL: `/marketing/automacoes/dashboard/`

### Conteúdo

| Seção | Dados |
|-------|-------|
| **KPIs** (4 cards) | Execuções hoje, Taxa de sucesso, Regras ativas, Pendentes (delay) |
| **Gráfico** | Linha: execuções nos últimos 30 dias (Chart.js) |
| **Top Regras** | 10 regras mais executadas |
| **Erros Recentes** | 10 últimos logs com status=erro |
| **Histórico** | Tabela com últimos 100 logs (data, regra, ação, lead, status, resultado) |

---

## Timeline no Lead

### Integração

No detalhe da oportunidade (`apps/comercial/crm/views.py` → `oportunidade_detalhe`), a view consulta:

```python
LogExecucao.all_tenants.filter(tenant=request.tenant, lead=lead)
```

E passa `logs_automacao` no contexto. Isso é possível graças ao FK `LogExecucao.lead` que foi adicionado na refatoração.

### API

```
GET /marketing/automacoes/api/lead/<lead_pk>/timeline/
```

Retorna JSON:
```json
{
  "logs": [
    {"id": 1, "regra": "Boas vindas", "acao": "Enviar WhatsApp", "status": "sucesso", "resultado": "OK", "data": "03/04/2026 14:30"}
  ]
}
```

---

## Integração com Segmentos

### Evento `lead_entrou_segmento`

Quando o signal `avaliar_segmentos_dinamicos` (em `apps/comercial/crm/signals.py`) adiciona um lead a um segmento dinâmico, ele dispara:

```python
disparar_evento('lead_entrou_segmento', {
    'lead': instance,
    'segmento': seg,
    'segmento_nome': seg.nome,
}, tenant=instance.tenant)
```

Isso permite criar regras como: "Quando lead entrar no segmento 'Leads Quentes', enviar WhatsApp de boas vindas."

### Disparo em massa por segmento

Regras com `evento=disparo_segmento` e `segmento` FK preenchido são processadas pelo cron. Para cada lead do segmento, o cron dispara a automação (respeitando controles de rate limit e cooldown).

### Serviço compartilhado

O `apps/comercial/crm/services/segmentos.py` contém funções reutilizadas:
- `filtrar_leads_por_regras(regras)` — filtra queryset por campo/operador/valor
- `lead_atende_regras(lead, regras)` — avalia sem query (usado nos signals)
- `avaliar_lead_em_segmentos(lead)` — retorna lista de segmentos adicionados
- `atualizar_membros_segmento(segmento)` — sync completo de membros

---

## URLs

| URL | View | Método | Descrição |
|-----|------|--------|-----------|
| `/marketing/automacoes/` | `lista_automacoes` | GET | Lista de regras |
| `/marketing/automacoes/criar/` | `criar_automacao` | GET/POST | Criar regra (modo legacy) |
| `/marketing/automacoes/dashboard/` | `dashboard_automacoes` | GET | Dashboard central |
| `/marketing/automacoes/<pk>/editar/` | `editar_automacao` | GET/POST | Editar regra (modo legacy) |
| `/marketing/automacoes/<pk>/fluxo/` | `editor_fluxo` | GET | Editor visual Drawflow |
| `/marketing/automacoes/<pk>/salvar-fluxo/` | `salvar_fluxo` | POST | Salvar fluxograma |
| `/marketing/automacoes/<pk>/toggle/` | `toggle_automacao` | POST | Ativar/desativar (AJAX) |
| `/marketing/automacoes/<pk>/excluir/` | `excluir_automacao` | POST | Excluir regra |
| `/marketing/automacoes/<pk>/historico/` | `historico_automacao` | GET | Logs de uma regra |
| `/marketing/automacoes/api/lead/<pk>/timeline/` | `api_lead_timeline` | GET | Timeline de automações para um lead |

---

## Signals

### Arquivo: `apps/marketing/automacoes/signals.py`

| Signal | Sender | Condição | Skip flag |
|--------|--------|----------|-----------|
| `on_lead_criado` | `leads.LeadProspecto` | `created=True` | `_skip_automacao` |
| `on_lead_qualificado` | `leads.LeadProspecto` | `created=False` AND `score >= 7` | `_skip_automacao` |
| `on_oportunidade_movida` | `crm.OportunidadeVenda` | `created=False` | `_skip_automacao` |
| `on_docs_validados` | `leads.ImagemLeadProspecto` | `status=validado` AND todos docs validados | `_skip_automacao` |
| `on_indicacao_convertida` | `indicacoes.Indicacao` | `status=convertido` | `_skip_automacao` |

### Arquivo: `apps/comercial/crm/signals.py`

| Signal | Sender | O que faz |
|--------|--------|-----------|
| `avaliar_segmentos_dinamicos` | `leads.LeadProspecto` | Avalia segmentos + dispara `lead_entrou_segmento` |

---

## Testes

### Arquivo: `tests/test_automacoes.py`

**60 testes passando** cobrindo:

| Classe | Testes | O que cobre |
|--------|--------|-------------|
| `RegraAutomacaoModelTest` | 4 | CRUD, taxa_sucesso, str |
| `CondicaoRegraModelTest` | 7 | Avaliação: igual, maior, contém, aninhado, inexistente, menor_igual, diferente |
| `AcaoRegraModelTest` | 6 | Delay timedelta (minutos, horas, dias), str |
| `EngineSubstituirVariaveisTest` | 3 | Substituição de variáveis em templates |
| `EngineDispararEventoTest` | 14 | Evento sem regras, com/sem condições, inativa, múltiplas AND, delay, notificação, WhatsApp (mock), webhook (mock), criar tarefa, dar pontos, sem tenant |
| `AutomacoesTenantIsolationTest` | 1 | Regras isoladas por tenant |
| `AutomacoesViewsTest` | 12 | Lista, criar GET/POST, editar, toggle, excluir, histórico, sem login, editor_fluxo, dashboard, timeline, salvar_fluxo |
| `FluxoEngineTest` | 5 | Fluxo linear, condição true/false, delay, legacy não afetado |
| `ControleExecucaoTest` | 3 | Max execuções bloqueia, cooldown bloqueia, sem controles passa |
| `ExecucaoPendenteTest` | 2 | Executa pendentes vencidos, não executa futuros |
| `NovasViewsTest` | 3 | Editor fluxo, dashboard, timeline lead |

### Factories

```python
RegraAutomacaoFactory   # evento='lead_criado', ativa=True
CondicaoRegraFactory    # campo='lead.origem', operador='igual', valor='whatsapp'
AcaoRegraFactory        # tipo='notificacao_sistema', configuracao='Novo lead: {{nome}}'
LogExecucaoFactory      # status='sucesso'
NodoFluxoFactory        # tipo='action', subtipo='enviar_whatsapp'
ConexaoNodoFactory      # tipo_saida='default'
ExecucaoPendenteFactory # status='pendente'
```

---

## Limitações conhecidas

1. **Sem Celery:** delays usam tabela `ExecucaoPendente` + cron (latência máxima = intervalo do cron, ex: 5 min)
2. **Ações não implementadas:** `enviar_email` e `atribuir_responsavel` existem como opção mas não têm executor
3. **Eventos não implementados:** `venda_aprovada` (precisa webhook HubSoft) e `cliente_aniversario` (precisa campo data_nascimento)
4. **Webhook WhatsApp hardcoded:** URL do N8N está fixa no código, deveria ser configurável por tenant
5. **Sem deduplicação de ações:** se 2 regras mandam WhatsApp para o mesmo lead no mesmo minuto, manda 2x (usar `max_execucoes_por_lead` para controlar)
6. **Editor visual:** painel de config abre ao clicar no nó. Se não abrir, verificar console do browser

---

## Exemplo de uso

### Criar automação: "Boas vindas ao novo lead via WhatsApp"

1. Acesse `/marketing/automacoes/criar/`
2. Nome: "Boas vindas WhatsApp"
3. Evento: "Novo lead criado"
4. Salvar → vai para a lista
5. Clique no ícone de fluxograma (📊) → abre editor visual
6. Arraste "Venda aprovada" (trigger) para o canvas (já vem com o evento da regra)
7. Arraste "Verificar Campo" → configure: Campo=lead.origem, Operador=igual, Valor=whatsapp
8. Arraste "Enviar WhatsApp" → configure: "Olá {{nome}}, obrigado pelo interesse!"
9. Conecte: trigger → condição (saída default), condição → whatsapp (saída true)
10. Clique "Salvar"

Agora todo lead que chegar via WhatsApp recebe a mensagem automaticamente.

### Criar automação com delay: "Followup 2 dias após cadastro"

1. Criar regra com evento "Novo lead criado"
2. No editor: trigger → delay (2 dias) → criar tarefa ("Contatar {{nome}}")
3. Salvar

O lead é criado, o delay é agendado, e 2 dias depois o cron executa e cria a tarefa.
