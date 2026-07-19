# Documentacao Completa do CRM — Megalink

> Documento gerado em 30/03/2026. Reflete o estado atual do codigo em producao.

---

## Sumario

1. [Visao Geral](#1-visao-geral)
2. [Modelos de Dados](#2-modelos-de-dados)
3. [Pipeline — Estagios Padrao](#3-pipeline--estagios-padrao)
4. [APIs / Endpoints](#4-apis--endpoints)
5. [Automacoes e Signals](#5-automacoes-e-signals)
6. [Management Commands](#6-management-commands)
7. [Regras de Negocio Consolidadas](#7-regras-de-negocio-consolidadas)
8. [Webhooks N8N](#8-webhooks-n8n)
9. [Permissoes e Visibilidade](#9-permissoes-e-visibilidade)
10. [Fluxo Completo de Vida de um Lead](#10-fluxo-completo-de-vida-de-um-lead)

---

## 1. Visao Geral

O CRM e um app Django (`crm/`) que gerencia o pipeline comercial da Megalink. Ele se integra com:

- **vendas_web** — app de captacao de leads (`LeadProspecto`)
- **integracoes** — conexao com a API Hubsoft (`ClienteHubsoft`, `ServicoClienteHubsoft`)
- **N8N** — webhooks para automacoes externas (notificacoes, WhatsApp, etc.)

**Arquivo de configuracao:** `crm/models.py > ConfiguracaoCRM` (singleton)

---

## 2. Modelos de Dados

### 2.1 PipelineEstagio
Representa uma coluna do Kanban.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| nome | CharField(100) | Nome exibido |
| slug | SlugField (unique) | Identificador URL |
| ordem | PositiveIntegerField | Posicao no Kanban |
| tipo | CharField | `novo`, `qualificacao`, `negociacao`, `fechamento`, `cliente`, `retencao`, `perdido` |
| cor_hex | CharField(7) | Cor HEX |
| icone_fa | CharField(50) | Icone FontAwesome |
| is_final_ganho | Boolean | Estagio de fechamento positivo |
| is_final_perdido | Boolean | Estagio de perda |
| probabilidade_padrao | Integer | % padrao ao entrar no estagio |
| sla_horas | PositiveInteger (null) | SLA em horas |
| ativo | Boolean | Se esta ativo |

### 2.2 OportunidadeVenda (modelo central)
Vincula um lead a um estagio do pipeline.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| lead | OneToOne → LeadProspecto | Lead associado |
| estagio | FK → PipelineEstagio | Estagio atual |
| responsavel | FK → User (null) | Vendedor responsavel |
| criado_por | FK → User (null) | Quem criou |
| titulo | CharField(255) | Titulo da oportunidade |
| valor_estimado | Decimal(12,2) | Valor estimado R$ |
| probabilidade | Integer | % de fechamento |
| data_fechamento_previsto | DateField (null) | Previsao de fechamento |
| data_fechamento_real | DateTimeField (null) | Data real de fechamento |
| plano_interesse | FK → PlanoInternet (null) | Plano de interesse |
| origem_crm | CharField | `automatico`, `manual`, `importacao` |
| prioridade | CharField | `baixa`, `normal`, `alta`, `urgente` |
| tags | M2M → TagCRM | Tags associadas |
| data_entrada_estagio | DateTimeField | Quando entrou no estagio atual |
| motivo_perda | TextField (null) | Motivo de perda |
| concorrente_perdido | CharField(100) (null) | Concorrente que ganhou |
| contrato_hubsoft_id | CharField(100) (null) | ID do contrato Hubsoft |
| churn_risk_score | Integer (null) | Score de risco de churn 0-100 |
| ativo | Boolean | Se esta ativo |

**Propriedades:**
- `dias_no_estagio` — dias no estagio atual
- `sla_vencido` — `True` se ultrapassou o SLA

### 2.3 HistoricoPipelineEstagio
Auditoria de toda movimentacao entre estagios.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| oportunidade | FK → OportunidadeVenda | Oportunidade |
| estagio_anterior | FK → PipelineEstagio (null) | De onde veio |
| estagio_novo | FK → PipelineEstagio | Para onde foi |
| movido_por | FK → User (null) | Quem moveu |
| motivo | TextField | Motivo da movimentacao |
| tempo_no_estagio_horas | Decimal(8,2) | Horas no estagio anterior |
| data_transicao | DateTimeField (auto) | Quando ocorreu |

### 2.4 TarefaCRM

| Campo | Tipo | Descricao |
|-------|------|-----------|
| oportunidade | FK → OportunidadeVenda (null) | Vinculo com oportunidade |
| lead | FK → LeadProspecto (null) | Vinculo direto com lead |
| responsavel | FK → User | Quem deve executar |
| tipo | CharField | `ligacao`, `whatsapp`, `email`, `visita`, `followup`, `proposta`, `instalacao`, `suporte`, `outro` |
| titulo | CharField(255) | Titulo |
| status | CharField | `pendente`, `em_andamento`, `concluida`, `cancelada`, `vencida` |
| prioridade | CharField | `baixa`, `normal`, `alta`, `urgente` |
| data_vencimento | DateTimeField (null) | Prazo |
| data_conclusao | DateTimeField (null) | Quando concluiu |
| resultado | TextField | Resultado registrado |

**Logica no save():** se `data_vencimento` passou e status ainda e `pendente`, muda automaticamente para `vencida`.

### 2.5 NotaInterna

| Campo | Tipo | Descricao |
|-------|------|-----------|
| oportunidade | FK (null) | Oportunidade |
| lead | FK (null) | Lead |
| autor | FK → User | Quem escreveu |
| mencoes | M2M → User | @mencoes |
| conteudo | TextField | Corpo da nota |
| tipo | CharField | `geral`, `reuniao`, `ligacao`, `email`, `importante`, `alerta` |
| is_fixada | Boolean | Fixada no topo |

### 2.6 MetaVendas

| Campo | Tipo | Descricao |
|-------|------|-----------|
| tipo | CharField | `individual` ou `equipe` |
| vendedor | FK → User (null) | Vendedor alvo |
| equipe | FK → EquipeVendas (null) | Equipe alvo |
| periodo | CharField | `diario`, `semanal`, `mensal`, `trimestral` |
| data_inicio / data_fim | DateField | Periodo da meta |
| meta_vendas_quantidade | Integer | Meta de quantidade |
| meta_vendas_valor | Decimal | Meta de valor R$ |
| meta_leads_qualificados | Integer | Meta de leads qualificados |
| realizado_vendas_quantidade | Integer | Realizado quantidade |
| realizado_vendas_valor | Decimal | Realizado valor R$ |

**Propriedades:** `percentual_quantidade`, `percentual_valor`

### 2.7 SegmentoCRM + MembroSegmento

| Campo | Tipo | Descricao |
|-------|------|-----------|
| nome | CharField(100) | Nome do segmento |
| tipo | CharField | `dinamico`, `manual`, `hibrido` |
| regras_filtro | JSONField | Regras de filtro automatico |
| leads | M2M through MembroSegmento | Leads membros |
| total_leads | Integer | Contagem de membros |

### 2.8 AlertaRetencao

| Campo | Tipo | Descricao |
|-------|------|-----------|
| cliente_hubsoft | FK → ClienteHubsoft | Cliente |
| lead | FK (null) | Lead relacionado |
| tipo_alerta | CharField | `contrato_expirando`, `inadimplencia`, `plano_downgradado`, `sem_uso`, `reclamacao`, `upgrade_disponivel`, `aniversario_contrato` |
| nivel_risco | CharField | `baixo`, `medio`, `alto`, `critico` |
| score_churn | Integer | Score 0-100 |
| status | CharField | `novo`, `em_tratamento`, `resolvido`, `perdido` |
| data_expiracao_contrato | DateField (null) | Vencimento do contrato |
| acoes_tomadas | TextField | O que foi feito |

### 2.9 EquipeVendas / PerfilVendedor / TagCRM / ConfiguracaoCRM

- **EquipeVendas** — times de vendas com lider
- **PerfilVendedor** — OneToOne com User, vinculo com equipe, cargo, id_vendedor_hubsoft
- **TagCRM** — tags coloridas para oportunidades (Comercial, Endereco, Documental, etc.)
- **ConfiguracaoCRM** — singleton de configuracao (ver secao 7)

---

## 3. Pipeline — Estagios Padrao

| Ordem | Nome | Slug | Tipo | Prob. | SLA | Final? | Cor |
|-------|------|------|------|-------|-----|--------|-----|
| 1 | Novo Lead | novo | novo | 10% | 24h | - | #667eea |
| 2 | Em Qualificacao | qualificacao | qualificacao | 30% | 48h | - | #764ba2 |
| 3 | Proposta Enviada | proposta | negociacao | 60% | 72h | - | #f39c12 |
| 4 | Aguardando Instalacao | instalacao | fechamento | 85% | 120h | - | #0ea5e9 |
| 5 | Cliente Ativo | ativo | cliente | 100% | - | Ganho | #059669 |
| 6 | Perdido | perdido | perdido | 0% | - | Perdido | #e74c3c |

---

## 4. APIs / Endpoints

Todas as URLs tem prefixo `/crm/`. App name: `crm`.

### 4.1 Pipeline / Kanban

| Metodo | URL | View | Descricao |
|--------|-----|------|-----------|
| GET | `/` | `pipeline_view` | Renderiza o Kanban |
| GET | `/pipeline/` | `pipeline_view` | Alias do Kanban |
| GET | `/pipeline/dados/` | `api_pipeline_dados` | JSON com oportunidades agrupadas por estagio |
| POST | `/pipeline/mover/` | `api_mover_oportunidade` | Move oportunidade entre estagios |

**`api_pipeline_dados`** — Filtros aceitos via query string:
- `responsavel` — ID do vendedor
- `prioridade` — baixa/normal/alta/urgente
- `search` — busca por nome do lead

**Regra de visibilidade:** superuser ve tudo; usuario normal ve apenas suas oportunidades + as sem responsavel.

**`api_mover_oportunidade`** — Body JSON:
```json
{
  "oportunidade_id": 123,
  "estagio_id": 4,
  "motivo": "texto opcional"
}
```

**Validacoes ao mover:**
- Permissao: so o responsavel ou superuser pode mover
- **Para estagio tipo `fechamento` (Aguardando Instalacao):** exige que o lead tenha `ServicoClienteHubsoft` com `status_prefixo='aguardando_instalacao'` E `documentacao_validada=True`
- Se estagio destino e `is_final_ganho`: preenche `data_fechamento_real` e atualiza `MetaVendas`
- Cria `HistoricoPipelineEstagio` com tempo no estagio anterior
- Dispara webhook N8N `webhook_n8n_mudanca_estagio`

### 4.2 Oportunidades

| Metodo | URL | View | Descricao |
|--------|-----|------|-----------|
| GET | `/oportunidades/` | `oportunidades_lista` | Lista agrupada por estagio |
| GET | `/oportunidades/<pk>/` | `oportunidade_detalhe` | Detalhe com historico, contatos, Hubsoft |
| POST | `/oportunidades/<pk>/atribuir/` | `api_atribuir_responsavel` | Atribuir vendedor |
| GET/POST | `/oportunidades/<pk>/notas/` | `api_notas_oportunidade` | Listar/criar notas |
| GET/POST | `/oportunidades/<pk>/tarefas/` | `api_tarefas_oportunidade` | Listar/criar tarefas |

**`api_atribuir_responsavel`** — Body JSON:
```json
{ "responsavel_id": 5 }
```
Se `responsavel_id` nao informado ou null, remove atribuicao.

### 4.3 Tarefas

| Metodo | URL | View | Descricao |
|--------|-----|------|-----------|
| GET | `/tarefas/` | `tarefas_lista` | Lista de tarefas do usuario logado |
| POST | `/tarefas/criar/` | `api_tarefa_criar` | Criar tarefa avulsa |
| POST | `/tarefas/<pk>/concluir/` | `api_tarefa_concluir` | Marcar como concluida |

**`api_tarefa_concluir`** — Body JSON (opcional):
```json
{ "resultado": "texto com resultado" }
```

### 4.4 Notas

| Metodo | URL | View | Descricao |
|--------|-----|------|-----------|
| POST | `/notas/criar/` | `api_nota_criar` | Criar nota avulsa |
| POST | `/notas/<pk>/fixar/` | `api_nota_fixar` | Fixar/desfixar nota |
| POST | `/notas/<pk>/deletar/` | `api_nota_deletar` | Deletar (so o autor) |

### 4.5 Desempenho e Metas

| Metodo | URL | View | Descricao |
|--------|-----|------|-----------|
| GET | `/desempenho/` | `desempenho_view` | Dashboard de desempenho |
| GET | `/desempenho/dados/` | `api_desempenho_dados` | JSON com metricas por vendedor |
| GET | `/metas/` | `metas_view` | Pagina de metas |
| POST | `/metas/criar/` | `api_meta_criar` | Criar meta (JSON) |
| POST | `/metas/salvar/` | `api_meta_salvar` | Criar/editar meta (FormData) |
| POST | `/metas/<pk>/excluir/` | `api_meta_excluir` | Deletar meta |

**`api_desempenho_dados`** — Filtros via query string:
- `periodo` — `semana`, `mes` (padrao), `trimestre`
- Retorna: vendas fechadas, valores, funil por estagio, meta individual

### 4.6 Retencao

| Metodo | URL | View | Descricao |
|--------|-----|------|-----------|
| GET | `/retencao/` | `retencao_view` | Pagina de alertas de retencao |
| POST | `/retencao/scanner/` | `api_scanner_retencao` | Escanear contratos e gerar alertas |
| POST | `/retencao/alertas/<pk>/tratar/` | `api_tratar_alerta` | Marcar alerta como em tratamento |
| POST | `/retencao/alertas/<pk>/resolver/` | `api_resolver_alerta` | Resolver alerta |

**`api_scanner_retencao`** — Logica de score de churn:

| Dias para vencimento | Nivel | Score base |
|---------------------|-------|------------|
| <= 30 dias | critico | 90 |
| 31-60 dias | alto | 70 |
| 61-90 dias | medio | 50 |

Score final = `score_base - dias_restantes`

**`api_resolver_alerta`** — Body JSON:
```json
{ "acoes_tomadas": "descricao das acoes realizadas" }
```

### 4.7 Segmentos

| Metodo | URL | View | Descricao |
|--------|-----|------|-----------|
| GET | `/segmentos/` | `segmentos_lista` | Lista de segmentos |
| GET | `/segmentos/<pk>/` | `segmento_detalhe` | Detalhe com membros |
| POST | `/segmentos/salvar/` | `api_segmento_salvar` | Criar/editar segmento |
| GET | `/segmentos/<pk>/buscar-leads/` | `api_segmento_buscar_leads` | Buscar leads para adicionar |
| POST | `/segmentos/<pk>/adicionar-lead/` | `api_segmento_adicionar_lead` | Adicionar lead ao segmento |
| POST | `/segmentos/<pk>/remover-membro/` | `api_segmento_remover_membro` | Remover membro |
| POST | `/segmentos/<pk>/disparar-campanha/` | `api_segmento_disparar_campanha` | Disparar campanha via webhook N8N |

**`api_segmento_buscar_leads`** — Query string `?q=texto` (minimo 2 caracteres). Busca por nome ou telefone, exclui membros existentes, retorna ate 20 resultados.

**`api_segmento_disparar_campanha`** — Coleta telefones de todos os membros e envia para webhook N8N com: nome do segmento, contagem de leads e lista de telefones.

### 4.8 Configuracoes (somente superuser)

| Metodo | URL | View | Descricao |
|--------|-----|------|-----------|
| GET | `/configuracoes/` | `configuracoes_crm` | Pagina de config |
| POST | `/configuracoes/salvar/` | `api_salvar_config` | Salvar configuracoes |
| POST | `/configuracoes/estagios/reordenar/` | `api_reordenar_estagios` | Reordenar estagios |
| POST | `/configuracoes/estagios/criar/` | `api_criar_estagio` | Criar/editar estagio |
| GET | `/configuracoes/estagios/<pk>/` | `api_estagio_detalhe` | Detalhe do estagio (JSON) |
| POST | `/configuracoes/estagios/<pk>/excluir/` | `api_excluir_estagio` | Deletar estagio |
| POST | `/configuracoes/equipes/criar/` | `api_criar_equipe` | Criar/editar equipe |

**`api_excluir_estagio`** — Impede exclusao se houver oportunidades vinculadas (retorna erro com contagem).

### 4.9 Webhooks Inbound

| Metodo | URL | View | Descricao |
|--------|-----|------|-----------|
| POST | `/webhook/hubsoft/contrato/` | `webhook_hubsoft_contrato` | Recebe confirmacao de contrato do Hubsoft |

**`webhook_hubsoft_contrato`** — CSRF exempt. Recebe `contrato_id`, localiza a oportunidade com `contrato_hubsoft_id` correspondente, move para estagio `is_final_ganho`, registra historico e `data_fechamento_real`.

---

## 5. Automacoes e Signals

### 5.1 Signal: Criar Oportunidade Automatica

**Arquivo:** `crm/signals.py`
**Evento:** `post_save` em `LeadProspecto`
**Quando dispara:** toda vez que um LeadProspecto e salvo

**Condicoes (todas precisam ser verdadeiras):**
1. Flag `_skip_crm_signal` NAO esta setada no lead
2. NAO existe `OportunidadeVenda` para este lead ainda
3. `ConfiguracaoCRM.criar_oportunidade_automatico == True`
4. `ConfiguracaoCRM.estagio_inicial_padrao` existe
5. **Criterio de qualificacao** (pelo menos UM):
   - `lead.score_qualificacao >= ConfiguracaoCRM.score_minimo_auto_criacao` (padrao: 7)
   - OU `lead.status_api == 'sucesso'`

**Acao:**
- Cria `OportunidadeVenda` com:
  - `estagio` = estagio_inicial_padrao (padrao: "Novo Lead")
  - `valor_estimado` = lead.valor
  - `origem_crm` = `'automatico'`
  - `probabilidade` = probabilidade padrao do estagio

---

### 5.2 Signal: Conversao por Historico de Contato (IVR)

**Arquivo:** `crm/signals.py`
**Evento:** `post_save` em `HistoricoContato` (somente criacao)
**Quando dispara:** quando um novo HistoricoContato e criado

**Condicoes:**
1. E um registro **novo** (`created=True`)
2. `HistoricoContato.converteu_venda == True`
3. Existe um lead vinculado
4. Existe `OportunidadeVenda` ativa para o lead
5. A oportunidade **NAO** esta em estagio `is_final_ganho`
6. Existe um estagio com `is_final_ganho=True` e `ativo=True`

**Acoes:**
- Cria `HistoricoPipelineEstagio` (motivo: `"Conversao automatica via IVR/atendimento"`)
- Move oportunidade para estagio "Cliente Ativo"
- Preenche `data_fechamento_real = agora`
- Se `HistoricoContato.valor_venda` existir: atualiza `valor_estimado`

---

### 5.3 Signal: Validar Estagio Aguardando Instalacao

**Arquivo:** `crm/signals.py`
**Evento:** `post_save` em `ServicoClienteHubsoft`
**Quando dispara:** toda vez que um servico do Hubsoft e salvo/atualizado

**Pre-condicoes:**
- O servico tem um `cliente` com `lead_id` preenchido
- Existe `OportunidadeVenda` ativa para esse lead

**Logica (avaliada em ordem de prioridade):**

**CASO 1 — Servico habilitado → Cliente Ativo**
- Condicao: existe `ServicoClienteHubsoft` com `status_prefixo='servico_habilitado'` para o lead E oportunidade NAO esta em estagio `is_final_ganho`
- Acao: move para estagio tipo `cliente` (`is_final_ganho=True`)
- Motivo registrado: `"Servico habilitado no Hubsoft — cliente ativado automaticamente"`
- **Para aqui** (nao avalia os proximos casos)

**CASO 2 — Em Aguardando Instalacao sem requisitos → Volta para Negociacao**
- Condicao: estagio atual e `tipo='fechamento'` E (NAO tem servico `aguardando_instalacao` OU `documentacao_validada=False`)
- Acao: move para estagio tipo `negociacao` (Proposta Enviada)
- Motivo registrado: `"Lead removido de Aguardando Instalacao: [sem servico aguardando_instalacao no Hubsoft], [documentacao nao validada]"`
- **Para aqui**

**CASO 3 — Tem servico aguardando + doc validada mas esta em estagio anterior → Avanca**
- Condicao: existe servico `aguardando_instalacao` E `documentacao_validada=True` E estagio atual NAO e `fechamento`, `cliente` ou `perdido`
- Acao: move para estagio tipo `fechamento` (Aguardando Instalacao)
- Motivo registrado: `"Servico aguardando instalacao detectado no Hubsoft com documentacao validada"`

---

### 5.4 Signal: Enviar Lead para Hubsoft

**Arquivo:** `integracoes/signals.py`
**Evento:** `post_save` em `LeadProspecto`
**Quando dispara:** toda vez que um LeadProspecto e salvo

**Condicoes:**
1. `lead.status_api == 'pendente'`
2. Lead NAO tem `id_hubsoft` preenchido
3. Existe `IntegracaoAPI` com `tipo='hubsoft'` e `ativa=True`

**Acoes:**
1. Chama `HubsoftService.cadastrar_prospecto(lead)` — envia para API Hubsoft
2. Atualiza lead: `status_api = 'processado'`, `id_hubsoft = id_prospecto` (se retornado)
3. Chama `_sincronizar_cliente_hubsoft()` — busca e sincroniza dados do cliente no Hubsoft

**Em caso de erro:**
- Atualiza lead: `status_api = 'erro'`

---

## 6. Management Commands

### 6.1 `popular_crm`

**Uso:** `python manage.py popular_crm [--dry-run] [--limpar] [--criar-perfis]`
**Proposito:** Importa leads existentes para o CRM com mapeamento automatico de estagios.

**Mapeamento por prioridade:**

| Prioridade | Condicao | Estagio Destino |
|-----------|----------|-----------------|
| P1 | Lead tem servico `status_prefixo='servico_habilitado'` | Cliente Ativo |
| P2 | Lead tem servico `status_prefixo='aguardando_instalacao'` **E** `documentacao_validada=True` | Aguardando Instalacao |
| P3 | `documentacao_validada=True` (sem servico aguardando) | Proposta Enviada |
| P4 | `status_api='processado'` (sem documentacao validada) | Proposta Enviada |
| P5 | `status_api='processamento_manual'` | Em Qualificacao |
| P6 | Todos os demais | Novo Lead |

**Flags:**
- `--dry-run` — simula sem gravar
- `--limpar` — apaga OportunidadeVenda existentes antes de popular
- `--criar-perfis` — cria PerfilVendedor para usuarios ativos sem perfil

---

### 6.2 `mover_perdidos`

**Uso:** `python manage.py mover_perdidos [--dry-run] [--horas N]`
**Proposito:** Move para "Perdido" oportunidades estagnadas em "Em Qualificacao".

**Condicoes para mover:**
1. Estagio atual: `tipo='qualificacao'`
2. `ativo=True`
3. `data_entrada_estagio` <= agora - N horas (padrao: **48 horas**)
4. `lead.documentacao_validada == False`

**Acao:** Move em lote para estagio `tipo='perdido'` com historico e motivo automatico.

---

### 6.3 `validar_aguardando_instalacao`

**Uso:** `python manage.py validar_aguardando_instalacao [--dry-run]`
**Proposito:** Garante que so ficam em "Aguardando Instalacao" os leads que atendem os criterios.

**Criterios para PERMANECER no estagio:**
1. Lead tem `ServicoClienteHubsoft` com `status_prefixo='aguardando_instalacao'`
2. `lead.documentacao_validada == True`

**Se NAO atende:**
- Tem servico `servico_habilitado` → move para **Cliente Ativo**
- Caso contrario → move para **Proposta Enviada** (negociacao)

---

### 6.4 `taguear_leads`

**Uso:** `python manage.py taguear_leads [--dry-run] [--resetar] [--estagio TIPO]`
**Proposito:** Atribui tags automaticas baseadas na completude de dados do lead.

**Tags e criterios:**

| Tag | Cor | Criterio de atribuicao |
|-----|-----|----------------------|
| **Comercial** | #667eea | `lead.id_plano_rp is not None` OU `lead.id_dia_vencimento is not None` |
| **Endereco** | #f39c12 | Todos preenchidos: `rua`, `numero_residencia`, `bairro`, `cep` |
| **Documental** | #0ea5e9 | `lead.cpf_cnpj` preenchido OU `documentacao_completa=True` OU `documentacao_validada=True` |

**Flags:**
- `--resetar` — remove as 3 tags gerenciadas antes de reaplicar
- `--estagio TIPO` — filtra por tipo de estagio (ex: `--estagio novo`)

---

## 7. Regras de Negocio Consolidadas

### 7.1 Configuracao do CRM (ConfiguracaoCRM — singleton)

| Parametro | Padrao | Descricao |
|-----------|--------|-----------|
| `criar_oportunidade_automatico` | True | Criar oportunidade automaticamente ao qualificar lead |
| `score_minimo_auto_criacao` | 7 | Score minimo para auto-criacao (0-100) |
| `estagio_inicial_padrao` | "Novo Lead" | Estagio onde oportunidades automaticas comecam |
| `sla_alerta_horas_padrao` | 48 | SLA padrao para alertas |
| `notificar_responsavel_nova_oportunidade` | True | Notificar vendedor sobre nova oportunidade |
| `notificar_sla_breach` | True | Notificar sobre SLA vencido |
| `webhook_n8n_nova_oportunidade` | null | URL do webhook N8N |
| `webhook_n8n_mudanca_estagio` | null | URL do webhook N8N |
| `webhook_n8n_tarefa_vencida` | null | URL do webhook N8N |

### 7.2 Regra: Quem pode ficar em "Aguardando Instalacao"

**Condicao obrigatoria (AMBAS):**
1. Lead possui `ServicoClienteHubsoft` com `status_prefixo='aguardando_instalacao'`
2. Lead possui `documentacao_validada=True`

**Onde e validado:**
- `api_mover_oportunidade` — bloqueia movimentacao manual
- Signal `validar_estagio_aguardando_instalacao` — move automaticamente ao salvar servico
- Command `validar_aguardando_instalacao` — limpeza periodica
- Command `popular_crm` — importacao inicial (P2)

### 7.3 Regra: Mover para Perdido automaticamente

**Condicao:** oportunidade em `qualificacao` ha mais de 48h com `documentacao_validada=False`
**Executado por:** `python manage.py mover_perdidos`

### 7.4 Regra: Atualizacao de MetaVendas

**Quando:** oportunidade move para estagio `is_final_ganho=True`
**Acao:** incrementa `realizado_vendas_quantidade += 1` e `realizado_vendas_valor += valor_estimado` na meta individual ativa do vendedor responsavel.

### 7.5 Regra: Conversao automatica via IVR

**Quando:** `HistoricoContato` criado com `converteu_venda=True`
**Acao:** move oportunidade diretamente para "Cliente Ativo", preenche `data_fechamento_real`.

### 7.6 Regra: Envio automatico para Hubsoft

**Quando:** `LeadProspecto` salvo com `status_api='pendente'` e sem `id_hubsoft`
**Acao:** envia como prospecto via API Hubsoft, atualiza `status_api` e sincroniza cliente.

---

## 8. Webhooks N8N

Configurados em `ConfiguracaoCRM`. Disparo via POST com JSON.

### 8.1 `webhook_n8n_mudanca_estagio`

**Dispara quando:** oportunidade muda de estagio via `api_mover_oportunidade`

**Payload:**
```json
{
  "oportunidade_id": 123,
  "lead_nome": "Joao Silva",
  "lead_telefone": "62999001234",
  "estagio_anterior": "Novo Lead",
  "estagio_novo": "Em Qualificacao",
  "responsavel_nome": "Maria Vendedora"
}
```

### 8.2 `webhook_n8n_nova_oportunidade`

**Configuravel** — URL armazenada mas o disparo depende da implementacao.

### 8.3 `webhook_n8n_tarefa_vencida`

**Configuravel** — URL armazenada mas o disparo depende da implementacao.

### 8.4 Webhook de Campanha (Segmentos)

**Dispara quando:** `api_segmento_disparar_campanha` e chamado

**Payload:** nome do segmento, contagem de leads, lista de telefones.

---

## 9. Permissoes e Visibilidade

| Contexto | Superuser | Usuario normal |
|----------|-----------|---------------|
| Kanban / Lista | Ve todas as oportunidades | Ve apenas as suas + sem responsavel |
| Mover oportunidade | Pode mover qualquer uma | So as suas |
| Tarefas | Ve todas | Ve apenas as atribuidas a ele |
| Configuracoes | Acesso total | Redirecionado para pipeline |
| Deletar nota | Qualquer nota | Apenas as que ele criou |

---

## 10. Fluxo Completo de Vida de um Lead

```
                         CAPTACAO
                            |
                 LeadProspecto criado
                   status_api='pendente'
                            |
                  [Signal integracoes]
                  Envia para Hubsoft API
                  status_api='processado'
                  Sincroniza ClienteHubsoft
                            |
                  [Signal crm]
                  score >= 7 OU status='sucesso'?
                     |               |
                    SIM             NAO
                     |               |
              Cria OportunidadeVenda  (nada)
              estagio: "Novo Lead"
                     |
          +---------+---------+
          |                   |
   Qualificacao          Sem atividade
   (vendedor atua)       > 48h sem doc
          |                   |
   doc_validada?      [mover_perdidos]
          |             → "Perdido"
         SIM
          |
   "Proposta Enviada"
          |
   Hubsoft cria servico
   status_prefixo='aguardando_instalacao'
          |
   [Signal ServicoClienteHubsoft]
   doc_validada + servico aguardando?
          |
         SIM → "Aguardando Instalacao"
          |
   Instalacao concluida
   status_prefixo='servico_habilitado'
          |
   [Signal ServicoClienteHubsoft]
   → "Cliente Ativo" (is_final_ganho)
     data_fechamento_real = agora
     MetaVendas atualizada
```

**Caminhos alternativos:**
- **IVR/Atendimento:** `HistoricoContato.converteu_venda=True` → direto para "Cliente Ativo"
- **Webhook Hubsoft:** `webhook_hubsoft_contrato` com `contrato_id` → direto para "Cliente Ativo"
- **Manual:** vendedor move via Kanban (com validacoes)

---

## Resumo de Automacoes por Trigger

| Trigger | Arquivo | Acao |
|---------|---------|------|
| LeadProspecto salvo | `crm/signals.py` | Cria OportunidadeVenda se qualificado |
| LeadProspecto salvo (status=pendente) | `integracoes/signals.py` | Envia para Hubsoft e sincroniza |
| HistoricoContato criado (converteu=True) | `crm/signals.py` | Move para Cliente Ativo |
| ServicoClienteHubsoft salvo | `crm/signals.py` | Valida/move estagio baseado no status do servico + doc |
| Webhook POST contrato | `crm/views.py` | Move para Cliente Ativo |
| Cron `mover_perdidos` | `crm/management/` | Qualificacao > 48h sem doc → Perdido |
| Cron `validar_aguardando_instalacao` | `crm/management/` | Remove de Aguardando quem nao atende criterios |
| Cron `taguear_leads` | `crm/management/` | Aplica tags Comercial/Endereco/Documental |
| Manual `popular_crm` | `crm/management/` | Importacao inicial com mapeamento por prioridade |
