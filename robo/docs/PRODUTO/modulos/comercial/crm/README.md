# Comercial — CRM

**App:** `apps/comercial/crm/`

CRM Kanban completo para gestao do funil de vendas. Pipeline visual com drag-and-drop, tarefas, metas, segmentos dinamicos, retencao/churn e integracao com automacoes e HubSoft.

> **Disponivel apenas no plano Pro.**

---

## Indice

| Arquivo | Conteudo |
|---------|----------|
| [pipeline.md](pipeline.md) | Pipeline, PipelineEstagio, HistoricoPipelineEstagio |
| [oportunidades.md](oportunidades.md) | OportunidadeVenda e ItemOportunidade |
| [produtos.md](produtos.md) | ProdutoServico (catalogo generico) |
| [tarefas-notas.md](tarefas-notas.md) | TarefaCRM e NotaInterna |
| [equipes.md](equipes.md) | EquipeVendas e PerfilVendedor |
| [metas.md](metas.md) | MetaVendas individuais e de equipe |
| [segmentos.md](segmentos.md) | SegmentoCRM (dinamico/manual/hibrido) + services |
| [retencao.md](retencao.md) | AlertaRetencao e scanner de churn |

---

## Visao geral

13 models organizados em 8 areas:

1. **Pipeline** — configuracao de funis e estagios por tenant
2. **Oportunidade** — a entidade central do CRM (1:1 com Lead)
3. **Produtos** — catalogo + vinculo com oportunidades
4. **Tarefas e Notas** — acoes e anotacoes por oportunidade
5. **Equipes** — agrupamento de vendedores
6. **Metas** — objetivos por periodo (individual ou equipe)
7. **Segmentos** — filtragem dinamica de leads para campanhas
8. **Retencao** — alertas de churn baseados em contratos HubSoft

---

## Configuracao

**ConfiguracaoCRM** — Singleton por tenant (tabela `crm_configuracao`).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `sla_alerta_horas_padrao` | PositiveInteger(48) | SLA padrao em horas |
| `criar_oportunidade_automatico` | BooleanField(True) | Auto-criar oportunidade quando lead qualificado |
| `score_minimo_auto_criacao` | Integer(7) | Score minimo para auto-criacao |
| `pipeline_padrao` / `estagio_inicial_padrao` | FK | Pipeline e estagio padrao |
| `notificar_responsavel_nova_oportunidade` / `notificar_sla_breach` | BooleanField | Notificacoes |
| `webhook_n8n_nova_oportunidade` / `mudanca_estagio` / `tarefa_vencida` | URLField | Webhooks N8N |

---

## Signals (3)

1. **criar_oportunidade_automatica** (post_save LeadProspecto) — Cria OportunidadeVenda quando lead atinge score minimo ou `status_api='sucesso'`
2. **verificar_conversao_historico** (post_save HistoricoContato) — Move oportunidade para estagio ganho quando `converteu_venda=True`
3. **avaliar_segmentos_dinamicos** (post_save LeadProspecto) — Avalia lead em segmentos dinamicos, dispara evento `lead_entrou_segmento` para automacoes

---

## Visibilidade

Vendedores nao-superuser veem apenas suas oportunidades + nao atribuidas.

---

## Views (40+ funcoes)

| Area | Views | Descricao |
|------|-------|-----------|
| **Pipeline** | pipeline_view, api_pipeline_dados, api_mover_oportunidade | Kanban com drag-drop, filtros, movimentacao |
| **Oportunidades** | oportunidades_lista, oportunidade_detalhe, api_atribuir, api_notas, api_tarefas | CRUD de oportunidades com contexto rico |
| **Tarefas** | tarefas_lista, api_tarefa_concluir, api_tarefa_criar | Gestao de tarefas agrupadas (hoje/semana/vencidas/concluidas) |
| **Notas** | api_nota_criar, api_nota_fixar, api_nota_deletar | Notas internas com fixar/desfixar |
| **Desempenho** | desempenho_view, api_desempenho_dados | Dashboard de performance por vendedor |
| **Metas** | metas_view, api_meta_criar, api_meta_salvar, api_meta_excluir | CRUD de metas individuais/equipe |
| **Retencao** | retencao_view, api_tratar_alerta, api_resolver_alerta, api_scanner_retencao | Gestao de alertas de churn |
| **Segmentos** | segmentos_lista, segmento_detalhe, api_segmento_salvar, api_preview_regras, api_adicionar_lead, api_remover_membro, api_disparar_campanha | Segmentacao dinamica com regras |
| **Configuracoes** | configuracoes_crm, api_salvar_config, api_criar_estagio, api_reordenar_estagios, api_excluir_estagio | Config do CRM (pipelines, estagios, webhooks) |
| **Equipes** | equipes_view, api_criar_equipe | Gestao de equipes de vendas |
| **Webhook** | webhook_hubsoft_contrato | Recebe confirmacao de contrato do HubSoft |

---

## Templates (13)

| Template | Descricao |
|----------|-----------|
| `pipeline.html` | Kanban drag-drop (990 linhas) |
| `oportunidades_lista.html` | Lista de oportunidades com filtros |
| `oportunidade_detalhe.html` | Detalhe com notas, tarefas, historico, HubSoft |
| `tarefas_lista.html` | Tarefas agrupadas com tabs |
| `metas.html` | Metas com progress bars |
| `desempenho.html` | Dashboard de performance |
| `retencao.html` | Alertas de churn por nivel de risco |
| `segmentos_lista.html` | Grid de segmentos |
| `segmento_detalhe.html` | Membros do segmento |
| `segmento_criar.html` | Criar/editar segmento com rule builder |
| `equipes.html` | Gestao de equipes |
| `configuracoes_crm.html` | Config (pipelines, estagios, webhooks) |
| `_tarefa_card.html` | Componente reutilizavel de card de tarefa |
