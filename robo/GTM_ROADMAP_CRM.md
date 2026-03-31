# TecHub CRM — Plano de Implementação

> Roadmap detalhado para implementar o módulo CRM com pipelines e kanban descrito no documento `TecHub_CRM_Banco_de_Dados.pdf`.
> Este documento é o plano de execução — do banco de dados ao frontend.

---

## 1. Visão do que vamos construir

O módulo CRM transforma o sistema de "rastreador de leads" em uma plataforma comercial completa. O time de vendas terá um **kanban** onde cada lead é um card que se move entre etapas (Novo lead → Primeiro contato → Proposta → Documentação → Ativado).

```
ANTES (hoje):        DEPOIS (com CRM):
Página de Leads  →   Kanban visual por pipeline
Lista sem gestão →   Cards movendo entre etapas
Sem tarefas      →   Atividades: ligar, enviar proposta, followup
Sem contexto     →   Notas livres por cliente
Sem histórico    →   Rastro de cada movimentação com tempo
Sem automação    →   Regras: "se deal parar 3 dias → criar atividade"
```

---

## 2. Tabelas que precisam ser criadas

### Status atual do banco: 27 tabelas, migration 0027

### Novas tabelas (6)

#### `pipelines` — os funis de venda
```sql
id              bigint PK
nome            varchar NOT NULL       -- "Prospecção Fibra", "Retenção"
descricao       text
ordem_exibicao  integer
ativo           boolean DEFAULT true
criado_em       timestamp DEFAULT now()
```

#### `pipeline_etapas` — colunas do kanban
```sql
id              bigint PK
pipeline_id     bigint FK (pipelines)
nome            varchar NOT NULL       -- "Novo lead", "Proposta enviada"
cor             varchar               -- "#3B6D11"
ordem           integer NOT NULL
etapa_ganha     boolean DEFAULT false  -- deal fechado positivo
etapa_perdida   boolean DEFAULT false  -- deal fechado negativo
probabilidade_pct integer             -- 0-100%
```

#### `deals` — os cards do kanban
```sql
id                        bigint PK
pipeline_id               bigint FK
etapa_id                  bigint FK
lead_id                   bigint FK (leads_prospectos)  ← âncora
responsavel_id            bigint FK (auth_user)
titulo                    varchar NOT NULL
valor                     numeric
data_prevista_fechamento  date
status                    varchar DEFAULT 'aberto'      -- aberto|ganho|perdido|pausado
observacoes               text
criado_em                 timestamp DEFAULT now()
atualizado_em             timestamp
```

#### `deal_historico_etapas` — rastro imutável
```sql
id                       bigint PK
deal_id                  bigint FK
etapa_origem_id          bigint FK (null = entrada inicial)
etapa_destino_id         bigint FK NOT NULL
movido_por               bigint FK (auth_user)
tempo_na_etapa_segundos  integer    -- calculado na movimentação
movido_em                timestamp DEFAULT now()
```

#### `deal_automacoes` — regras sem código
```sql
id                bigint PK
pipeline_id       bigint FK
nome              varchar NOT NULL
gatilho           varchar              -- stage_changed|time_in_stage|deal_created|deal_won|deal_lost
etapa_gatilho_id  bigint FK (opcional)
acao_tipo         varchar              -- webhook|notificacao|mover_etapa|criar_atividade|atribuir_responsavel
acao_config       jsonb NOT NULL       -- {url, method, mensagem, etapa_destino_id, ...}
ativo             boolean DEFAULT true
criado_em         timestamp DEFAULT now()
```

#### `atividades` — to-do list do time
```sql
id              bigint PK
lead_id         bigint FK NOT NULL    ← âncora
deal_id         bigint FK (opcional)
responsavel_id  bigint FK NOT NULL
tipo            varchar               -- ligacao|email|whatsapp|visita|tarefa|reuniao
assunto         varchar NOT NULL
descricao       text
agendado_para   timestamp
concluido_em    timestamp
concluida       boolean DEFAULT false
criado_em       timestamp DEFAULT now()
```

#### `notas` — texto livre
```sql
id             bigint PK
lead_id        bigint FK NOT NULL    ← âncora
deal_id        bigint FK (opcional)
autor_id       bigint FK NOT NULL
conteudo       text NOT NULL
criado_em      timestamp DEFAULT now()
atualizado_em  timestamp
```

---

## 3. Índices recomendados

```sql
CREATE INDEX idx_deals_lead_id ON deals(lead_id);
CREATE INDEX idx_deals_etapa_pipeline ON deals(pipeline_id, etapa_id);
CREATE INDEX idx_deals_status ON deals(status) WHERE status = 'aberto';
CREATE INDEX idx_atividades_lead_id ON atividades(lead_id);
CREATE INDEX idx_atividades_vencidas ON atividades(agendado_para) WHERE concluida = false;
CREATE INDEX idx_deal_hist_deal ON deal_historico_etapas(deal_id);
CREATE INDEX idx_notas_lead ON notas(lead_id);
```

---

## 4. Models Django correspondentes

### Observação: atualizar CLAUDE.md antes de iniciar

Antes de criar os models, atualizar o `CLAUDE.md` para permitir:
- ✅ Criar novos models (CRM apenas)
- ✅ Criar novas migrations
- ✅ Criar views POST/PUT para o módulo CRM
- ❌ Continua proibido: alterar models existentes, alterar banco de leads/vendas

---

## 5. Fases de implementação

### Fase 1 — Base do banco (estimativa: 1-2 dias)
- [ ] Criar models Django (Pipeline, PipelineEtapa, Deal, DealHistoricoEtapa, DealAutomacao, Atividade, Nota)
- [ ] Criar e aplicar migration 0028
- [ ] Registrar models no admin Django (para configuração inicial)
- [ ] Criar dados iniciais: 1 pipeline padrão "Prospecção" com 7 etapas

### Fase 2 — APIs de leitura (1 dia)
- [ ] `GET /crm/pipelines/` — lista pipelines ativos
- [ ] `GET /crm/pipelines/<id>/kanban/` — retorna etapas + deals agrupados
- [ ] `GET /crm/leads/<id>/timeline/` — histórico completo do lead (deals + atividades + notas + historico_contato)
- [ ] `GET /crm/atividades/pendentes/` — atividades vencidas ou próximas (painel do agente)

### Fase 3 — APIs de escrita (2-3 dias)
- [ ] `POST /crm/deals/` — criar deal
- [ ] `PUT /crm/deals/<id>/mover/` — mover deal de etapa (registra historico automaticamente)
- [ ] `PUT /crm/deals/<id>/status/` — marcar como ganho/perdido/pausado
- [ ] `POST /crm/atividades/` — criar atividade
- [ ] `PUT /crm/atividades/<id>/concluir/` — marcar atividade como concluída
- [ ] `POST /crm/notas/` — adicionar nota
- [ ] `DELETE /crm/notas/<id>/` — remover nota

### Fase 4 — Frontend: Kanban (3-4 dias)
- [ ] Nova página `crm.html` no módulo Comercial (sidebar: Kanban)
- [ ] Layout kanban: colunas como etapas, cards arrastáveis (drag & drop)
- [ ] Card mostra: nome do lead (2 palavras), valor, responsável, dias na etapa
- [ ] Badge de urgência quando deal parado há mais de X dias
- [ ] Abrir card → slide panel com timeline do lead
- [ ] Filtros: por responsável, por data de criação

### Fase 5 — Frontend: Painel do agente (1-2 dias)
- [ ] Widget "Minhas Atividades" no Dashboard (tarefas vencidas em destaque)
- [ ] Página de atividades com filtro por tipo, data, status
- [ ] Notificação interna quando atividade vencer

### Fase 6 — Automações (2-3 dias)
- [ ] Engine que roda a cada 5 minutos (cron/management command)
- [ ] Avalia `deal_automacoes` contra deals abertos
- [ ] Dispara: webhook, cria atividade, move etapa, notifica
- [ ] Log de execução (tabela `deal_automacoes_log` — adicionar)

---

## 6. Pipelines padrão para primeira instalação

### Pipeline 1 — Prospecção Fibra
| Ordem | Etapa | Cor | Prob% |
|-------|-------|-----|-------|
| 1 | Novo lead | #94a3b8 | 5% |
| 2 | Primeiro contato | #60a5fa | 20% |
| 3 | Interesse confirmado | #34d399 | 40% |
| 4 | Proposta enviada | #f59e0b | 60% |
| 5 | Aguardando documentação | #f97316 | 75% |
| 6 | Contrato assinado | #8b5cf6 | 90% |
| 7 | Ativado ✓ | #10b981 | 100% (etapa_ganha) |
| 8 | Perdido ✗ | #ef4444 | 0% (etapa_perdida) |

### Pipeline 2 — Retenção
| Ordem | Etapa | Cor | Prob% |
|-------|-------|-----|-------|
| 1 | Em risco | #ef4444 | 30% |
| 2 | Contato realizado | #f59e0b | 50% |
| 3 | Proposta de upgrade | #60a5fa | 70% |
| 4 | Retido ✓ | #10b981 | 100% (etapa_ganha) |
| 5 | Cancelou ✗ | #64748b | 0% (etapa_perdida) |

---

## 7. Métricas que o CRM vai habilitar

Com os dados do `deal_historico_etapas`, será possível calcular:

| Métrica | Como calcular |
|---------|--------------|
| Taxa de conversão por etapa | deals que saíram / deals que entraram em cada etapa |
| Tempo médio por etapa | média de `tempo_na_etapa_segundos` por etapa |
| Velocidade do ciclo de venda | tempo da etapa 1 até etapa_ganha |
| Gargalos do funil | etapas com maior tempo médio ou maior drop-off |
| Valor no funil | SUM(deals.valor * etapa.probabilidade_pct / 100) |
| Forecast de receita | deals abertos com data_prevista_fechamento no próximo mês |
| Ranking de vendedores | deals ganhos por responsavel_id |

Essas métricas alimentam novas páginas em Relatórios.

---

## 8. Integração com o sistema existente

### Quando lead converte (hoje):
- `LeadProspecto.status_api = 'sucesso'`
- Signal dispara envio de documentos ao HubSoft

### Com o CRM:
- Quando `deal.status = 'ganho'` → trigger que pode disparar N8N (webhook)
- Deal em etapa "Ativado" → conecta com `clientes_hubsoft` via `lead_id`
- Atividade de followup criada automaticamente quando lead fica parado

### Criação automática de deal:
- Quando novo lead entra via bot → `POST /crm/deals/` com pipeline padrão automaticamente
- Responsável = usuário configurado como padrão do pipeline

---

## 9. Gaps técnicos identificados no documento original

| Gap | Solução proposta |
|-----|-----------------|
| `deals` sem `data_entrada_etapa` | Adicionar campo `data_entrada_etapa timestamp` ao model Deal |
| `responsavel_id` sem referência clara | FK para `auth_user` do Django |
| Sem log de execução das automações | Criar `deal_automacoes_log` na Fase 6 |
| `etapa.cor` sem validação | Validar formato hex no clean() do Django |
| Sem permissão por pipeline | Implementar na Fase 7 (pós-MVP) |

---

## 10. Impacto no GTM

O módulo CRM é o maior diferencial competitivo frente a planilhas e CRMs genéricos. Antes do go-to-market, é o item de maior prioridade porque:

1. **Diferencia do WhatsApp Business** — que não tem kanban nem histórico de etapas
2. **Diferencia do Pipedrive/RD Station** — que não têm integração HubSoft, bot de qualificação, nem coleta de documentos
3. **Justifica o preço** — um CRM completo integrado ao ERP do ISP vale mais que uma ferramenta genérica
4. **Gera dado para relatório** — tempo médio de conversão, taxa por etapa → prova de valor mensurável para o cliente

**Meta:** ter o CRM funcionando antes do primeiro cliente beta pagar.
