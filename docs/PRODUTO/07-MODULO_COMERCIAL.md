# Módulo Comercial — AuroraISP

**Última atualização:** 04/04/2026
**Status:** ✅ Em produção
**Localização:** `apps/comercial/`

---

## Visão Geral

O módulo Comercial cobre todo o funil de vendas do provedor: da captação do lead até o contrato ativado no HubSoft. É composto por 5 sub-apps independentes que se integram via ForeignKeys e signals.

```
Lead chega (WhatsApp/Site/Instagram)
    │
    ▼
┌─────────┐     ┌──────────────┐     ┌──────────┐     ┌──────────────┐
│  LEADS  │────▶│ ATENDIMENTO  │────▶│ CADASTRO │────▶│ VIABILIDADE  │
│ Captura │     │ Bot N8N      │     │ Registro │     │ Cobertura    │
└────┬────┘     └──────────────┘     └──────────┘     └──────────────┘
     │
     ▼
┌─────────┐
│   CRM   │  Pipeline Kanban, Tarefas, Metas, Segmentos, Retenção
└─────────┘
```

**Stack compartilhada:** TenantMixin (multi-tenancy), Django 5.2, DRF, PostgreSQL

---

## 1. Leads (`apps/comercial/leads/`)

### O que faz
Captura, armazena e qualifica leads de qualquer canal (WhatsApp, site, Instagram, Facebook, telefone). Gerencia documentos (selfie, RG frente/verso) e histórico de contatos do bot.

### Models (4)

#### LeadProspecto
Tabela: `leads_prospectos` | 60+ campos

| Grupo | Campos principais |
|-------|-------------------|
| **Identificação** | nome_razaosocial, email (unique), telefone (validado, regex), cpf_cnpj, rg, data_nascimento |
| **Endereço** | rua, numero_residencia, bairro, cidade, estado, cep, ponto_referencia |
| **Comercial** | valor (DecimalField 12,2), origem (site/facebook/instagram/google/whatsapp/indicacao/telefone/email/outros), score_qualificacao (1-10), empresa |
| **Status** | status_api (pendente/processado/erro/sucesso/rejeitado/aguardando_retry), ativo |
| **Documentação** | documentacao_completa, documentacao_validada, contrato_aceito, anexos_contrato_enviados, ip_aceite_contrato |
| **Conversas** | url_pdf_conversa, html_conversa_path, data_geracao_pdf, data_geracao_html |
| **Contato** | tentativas_contato, data_ultimo_contato, motivo_rejeicao, canal_entrada, tipo_entrada |
| **Campanhas** | campanha_origem FK, campanha_conversao FK, total_campanhas_detectadas, metadata_campanhas (JSON) |
| **IDs externos** | id_hubsoft, id_origem, id_origem_servico, id_plano_rp, id_dia_vencimento, id_vendedor_rp |

**14 índices** incluindo compostos: `(canal_entrada, data_cadastro)`, `(score_qualificacao, status_api)`, `(tipo_entrada, ativo)`

**Métodos principais:**
- `calcular_score_qualificacao()` → score 1-10 baseado em dados preenchidos
- `validar_documentacao_completa()` → verifica selfie + doc_frente + doc_verso
- `aceitar_contrato(ip_address)` → marca contrato aceito com IP e timestamp
- `gerar_url_pdf()` → gera URL do PDF da conversa
- `get_historico_contatos_relacionados()` → contatos por lead ou telefone
- `get_taxa_sucesso_contatos()` → % de contatos bem-sucedidos
- `get_documentos_por_tipo()` → organiza documentos por tipo

#### ImagemLeadProspecto
Tabela: `imagens_lead_prospecto`

Armazena URLs de imagens externas (documentos do lead). Status: pendente, documentos_validos, documentos_rejeitados.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead pai |
| `link_url` | URLField(1024) | URL da imagem |
| `descricao` | CharField(255) | Descrição |
| `status_validacao` | CharField(30) | pendente/documentos_validos/documentos_rejeitados |
| `observacao_validacao` | TextField | Observações |
| `validado_por` | CharField(150) | Username do validador |

#### Prospecto
Tabela: `prospectos`

Representa o prospecto no HubSoft. Vinculado ao lead via FK. Controla o processamento de envio para o ERP.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead pai (opcional) |
| `nome_prospecto` | CharField(255) | Nome |
| `id_prospecto_hubsoft` | CharField(100, unique) | ID no HubSoft |
| `status` | CharField(20) | pendente/processando/processado/erro/finalizado/cancelado/aguardando_validacao/validacao_aprovada/validacao_rejeitada |
| `tentativas_processamento` | PositiveInteger | Tentativas |
| `tempo_processamento` | Decimal(10,3) | Tempo em segundos |
| `dados_processamento` / `resultado_processamento` | JSONField | Input/output do processamento |
| `score_conversao` | Decimal(5,2) | Score 0-100 de probabilidade de conversão |

**Métodos:** `iniciar_processamento()`, `finalizar_processamento()`, `calcular_score_conversao_automatico()`

#### HistoricoContato
Tabela: `historico_contato`

Registra cada interação do bot ou agente com o contato. Usado para funil de conversão e métricas.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead (opcional) |
| `telefone` | CharField(17) | Telefone do contato |
| `status` | CharField(30) | 14 status possíveis (fluxo_inicializado, venda_confirmada, etc.) |
| `duracao_segundos` | PositiveInteger | Duração da chamada |
| `transcricao` | TextField | Transcrição |
| `sucesso` | BooleanField | Se o contato foi bem-sucedido |
| `converteu_lead` / `converteu_venda` | BooleanField | Flags de conversão |
| `valor_venda` | Decimal(12,2) | Valor da venda (se converteu) |
| `protocolo_atendimento` / `codigo_atendimento` | CharField(100) | IDs do atendimento |
| `id_conta` / `numero_conta` | CharField(100) | IDs da conta no ERP |

**15 índices** para performance em relatórios de funil.

### APIs (20 endpoints)

| Grupo | Endpoints | Auth |
|-------|-----------|------|
| **Lead CRUD** | registrar, atualizar, consultar | @api_token_required |
| **Imagens** | registrar, listar, deletar, validar, por-cliente | @api_token_required |
| **Prospectos** | registrar, atualizar | @api_token_required |
| **Histórico** | registrar, atualizar, consultar | @api_token_required |
| **Vendas** | aprovar, rejeitar | @api_token_required |
| **Consulta** | leads (paginado), históricos (paginado) | Público |
| **Página** | leads (lista no painel) | @login_required |

### Signals (2)

1. **relate_prospecto_when_lead_has_hubsoft** — Quando lead salvo com id_hubsoft, vincula prospectos com mesmo id_prospecto_hubsoft
2. **relate_lead_when_prospecto_has_hubsoft** — Quando prospecto salvo com id_prospecto_hubsoft sem lead, vincula ao lead

### Template

`leads.html` — Página de gestão de leads com filtros (origem, status, ativo), cards de estatísticas (total, valor, erros, hoje, semana), tabela com ações.

---

## 2. Atendimento (`apps/comercial/atendimento/`)

### O que faz
Motor de fluxos automatizados (bot conversacional). Define fluxos com questões sequenciais que o N8N executa via WhatsApp. Suporta validação IA, roteamento inteligente, opções dinâmicas e webhooks N8N.

### Models (5)

#### FluxoAtendimento
Tabela: `fluxos_atendimento`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(255) | Nome do fluxo |
| `tipo_fluxo` | CharField | qualificacao/vendas/suporte/onboarding/pesquisa/customizado |
| `status` | CharField | ativo/inativo/rascunho/teste |
| `max_tentativas` | PositiveInteger(3) | Máximo de tentativas por questão |
| `tempo_limite_minutos` | PositiveInteger | Tempo limite do atendimento |
| `permite_pular_questoes` | BooleanField(False) | Permite pular |

**Métodos:** `get_questoes_ordenadas()`, `get_estatisticas()`, `pode_ser_usado()`

#### QuestaoFluxo
Tabela: `questoes_fluxo` | Unique: (fluxo, indice)

Campo mais complexo do sistema. 20+ tipos de questão, validação IA, roteamento inteligente.

| Grupo | Campos |
|-------|--------|
| **Básico** | titulo, descricao, indice (ordem), ativo |
| **Tipo** | tipo_questao (20 choices: texto, numero, email, cpf_cnpj, cep, select, multiselect, boolean, escala, planos_internet, vencimentos, ia_validacao, condicional_complexa...) |
| **Validação** | tipo_validacao (obrigatoria/opcional/condicional/ia_assistida/validacao_customizada), regex_validacao, tamanho_minimo/maximo, valor_minimo/maximo |
| **Dependências** | questao_dependencia (self FK), valor_dependencia |
| **Roteamento** | roteamento_respostas (JSON), questao_padrao_proxima (self FK) |
| **IA** | prompt_ia_validacao, criterios_ia (JSON) |
| **Erro** | max_tentativas, estrategia_erro (repetir/pular/redirecionar/finalizar/escalar_humano), mensagem_erro_padrao |
| **N8N** | webhook_n8n_validacao, webhook_n8n_pos_resposta (URLs) |
| **Opções dinâmicas** | opcoes_dinamicas_fonte (planos_internet/opcoes_vencimento/api_externa/query_customizada), query_opcoes_dinamicas |
| **Template** | variaveis_contexto (JSON), template_questao |

**Métodos:** `validar_resposta()`, `get_proxima_questao_inteligente()`, `deve_ser_exibida()`, `aplicar_estrategia_erro()`

#### AtendimentoFluxo
Tabela: `atendimentos_fluxo`

Controla uma sessão de atendimento. Liga lead + fluxo + progresso.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead atendido |
| `fluxo` | FK FluxoAtendimento | Fluxo usado |
| `status` | CharField | iniciado/em_andamento/pausado/completado/abandonado/erro/cancelado/aguardando_validacao/validado/rejeitado |
| `questao_atual` / `total_questoes` / `questoes_respondidas` | Inteiros | Progresso |
| `dados_respostas` | JSONField | Todas as respostas |
| `score_qualificacao` | Integer(1-10) | Score calculado |
| `resultado_final` | JSONField | Resultado do atendimento |

**Métodos:** `responder_questao_inteligente()`, `avancar_questao()`, `finalizar_atendimento()`, `calcular_score_qualificacao()`

#### RespostaQuestao e TentativaResposta
Armazenam respostas individuais e tentativas (com resultado IA, webhook, confiança).

### APIs (34 endpoints)

| Grupo | Endpoints | Descrição |
|-------|-----------|-----------|
| **CRUD Fluxos** | 4 (GET/POST/PUT/DELETE) | Gerenciar fluxos |
| **CRUD Questões** | 4 (GET/POST/PUT/DELETE) | Gerenciar questões |
| **Atendimentos** | 5 (GET/POST/PUT/responder/finalizar) | Operar atendimentos |
| **N8N** | 14 endpoints dedicados | iniciar, consultar, responder, avançar, finalizar, pausar, retomar, buscar lead, criar lead, listar fluxos, obter questão, tentativas, estatísticas inteligentes |
| **Config** | 5 (fluxos/questões CRUD + duplicar) | Configurar via painel |
| **Legacy** | 4 endpoints de compatibilidade | Rotas antigas |

### Services

`atendimento_service.py` — Busca dados de atendimento da API Matrix, gera HTML formatado da conversa, salva em disco.

### Templates (2)

- `fluxos.html` — Grid de cards dos fluxos (nome, tipo, status, stats)
- `questoes.html` — Gerenciamento de questões por fluxo

---

## 3. Cadastro (`apps/comercial/cadastro/`)

### O que faz
Página pública de auto-cadastro para o site do provedor. O visitante preenche dados pessoais, endereço, seleciona plano/vencimento, envia documentos e aceita contrato. Gera lead automaticamente.

### Models (5)

#### ConfiguracaoCadastro
Tabela: `configuracoes_cadastro` | Singleton por tenant

Configuração completa da landing page de cadastro. 40+ campos.

| Grupo | Campos |
|-------|--------|
| **Visual** | empresa, titulo_pagina, subtitulo_pagina, logo_url, background_type (gradient/solid/image), cores (primary, secondary, success, error) |
| **Contato** | telefone_suporte, whatsapp_suporte, email_suporte |
| **Planos** | mostrar_selecao_plano, plano_padrao FK |
| **Campos** | cpf_obrigatorio, email_obrigatorio, telefone_obrigatorio, endereco_obrigatorio |
| **Validações** | validar_cep (ViaCEP), validar_cpf |
| **Documentação** | solicitar_documentacao, texto_instrucao_selfie/doc_frente/doc_verso, tamanho_max_arquivo_mb, formatos_aceitos |
| **Contrato** | exibir_contrato, titulo_contrato, texto_contrato, tempo_minimo_leitura_segundos, texto_aceite_contrato |
| **Fluxo** | criar_lead_automatico, numero_etapas, mostrar_progress_bar |
| **Integração** | id_origem, id_origem_servico, id_vendedor (IDs externos), origem_lead_padrao |
| **Mensagens** | mensagem_sucesso, instrucoes_pos_cadastro |
| **Segurança** | captcha_obrigatorio, limite_tentativas_dia |

#### PlanoInternet
Tabela: `planos_internet`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(100) | Ex: "Fibra 400MB" |
| `velocidade_download` / `velocidade_upload` | PositiveInteger | Mbps |
| `valor_mensal` | Decimal(8,2) | Preço mensal |
| `wifi_6` / `suporte_prioritario` / `suporte_24h` / `upload_simetrico` | BooleanField | Features |
| `destaque` | CharField | popular/premium/economico/recomendado (badge) |
| `ordem_exibicao` | PositiveInteger | Ordem na lista |
| `id_sistema_externo` | CharField(50) | ID no ERP |

**Métodos:** `get_valor_formatado()` → "R$ 99,90", `get_velocidade_formatada()` → "400MB" ou "1GB"

#### OpcaoVencimento
Tabela: `opcoes_vencimento`

Dias de vencimento disponíveis (ex: dia 5, dia 10, dia 20).

#### DocumentoLead
Tabela: `documentos_lead`

Documentos enviados durante o cadastro. Base64 encoded.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead |
| `tipo_documento` | CharField | selfie/doc_frente/doc_verso/comprovante_residencia/contrato_assinado/outro |
| `arquivo_base64` | TextField | Imagem em base64 |
| `status` | CharField | pendente/aprovado/rejeitado/em_analise |
| `nome_arquivo` / `tamanho_arquivo` / `formato_arquivo` | Metadados | Info do arquivo |

#### CadastroCliente
Tabela: `cadastros_clientes`

Registra cada sessão de cadastro (mesmo incompleto). Status em 8 etapas.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| **Pessoal** | nome_completo, cpf, rg, email, telefone, data_nascimento |
| **Endereço** | cep, endereco, numero, bairro, cidade, estado |
| **Comercial** | plano_selecionado FK, vencimento_selecionado FK |
| **Status** | status (iniciado/dados_pessoais/endereco/documentacao/contrato/finalizado/erro/cancelado) |
| **Auditoria** | ip_cliente, user_agent, origem_cadastro, tempo_total_cadastro, tentativas_etapa (JSON), erros_validacao (JSON) |
| **Contrato** | contrato_aceito, tempo_leitura_contrato, ip_aceite_contrato |

**Métodos:** `finalizar_cadastro()`, `gerar_lead()`, `get_progresso_percentual()`, `validar_dados_pessoais()`, `validar_endereco()`

### APIs (12 endpoints)

| Grupo | Endpoints | Descrição |
|-------|-----------|-----------|
| **Público** | cadastro/cliente (POST), planos (GET), vencimentos (GET), cep (GET) | Auto-cadastro + consultas |
| **Config** | 3 páginas + 3 APIs CRUD | Gerenciar config, planos, vencimentos |

### Consulta CEP

Multi-source com fallback automático: ViaCEP → CepAPI → BrasilAPI → Postmon → OpenCEP. Primeira resposta válida retorna. Inclui headers CORS.

### Templates (4)

- `cadastro.html` — Landing page pública de auto-cadastro (multi-step form)
- `configuracoes/cadastro.html` — Config da landing page
- `configuracoes/planos.html` — CRUD de planos
- `configuracoes/vencimentos.html` — CRUD de vencimentos

---

## 4. Viabilidade (`apps/comercial/viabilidade/`)

### O que faz
Verifica se o provedor tem cobertura técnica (fibra óptica) na região do cliente. Consultado durante o cadastro e pelo bot de atendimento.

### Model (1)

#### CidadeViabilidade
Tabela: auto-gerada

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cidade` | CharField(120) | Nome da cidade |
| `estado` | CharField(2) | UF (27 estados brasileiros) |
| `cep` | CharField(9) | CEP específico (opcional, regex `^\d{5}-?\d{3}$`) |
| `bairro` | CharField(120) | Bairro (opcional) |
| `observacao` | TextField | Informações sobre a região |
| `ativo` | BooleanField | Status |

Se `cep` não informado, a cidade inteira é considerada viável. `save()` normaliza CEP (insere hífen) e capitaliza nome da cidade.

### API (1 endpoint)

`GET /api/viabilidade/?cep=64000000` ou `?cidade=Teresina&uf=PI`

**Lógica de busca por CEP:**
1. Busca direta no banco por CEP exato
2. Consulta ViaCEP para descobrir cidade/estado do CEP
3. Busca cidade na lista de viabilidade
4. Retorna `viavel_pelo_cep` e/ou `viavel_pela_cidade`

### Template

Nenhum. Módulo é API-only.

---

## 5. CRM (`apps/comercial/crm/`)

### O que faz
CRM Kanban completo para gestão do funil de vendas. Pipeline visual com drag-and-drop, tarefas, metas, segmentos dinâmicos, retenção/churn e integração com automações e HubSoft.

**Disponível apenas no plano Pro.**

### Models (13)

#### Pipeline e Estágios

**Pipeline** — Tabela: `crm_pipelines`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` / `slug` | CharField/Slug | Identificação |
| `tipo` | CharField | vendas/suporte/onboarding/custom |
| `cor_hex` / `icone_fa` | Char | Visual |
| `padrao` | BooleanField | Pipeline padrão para auto-criação |

**PipelineEstagio** — Tabela: `crm_pipeline_estagios`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `pipeline` | FK Pipeline | Pipeline pai |
| `nome` / `slug` / `ordem` | Identificação | Ordem no Kanban |
| `tipo` | CharField | novo/qualificacao/negociacao/fechamento/cliente/retencao/perdido |
| `is_final_ganho` / `is_final_perdido` | BooleanField | Flags de encerramento |
| `probabilidade_padrao` | Integer(50) | % padrão de probabilidade |
| `sla_horas` | PositiveInteger | SLA em horas |

#### Oportunidade de Venda

**OportunidadeVenda** — Tabela: `crm_oportunidades`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `pipeline` | FK Pipeline | Pipeline |
| `lead` | OneToOne LeadProspecto | Lead (1:1) |
| `estagio` | FK PipelineEstagio | Estágio atual |
| `responsavel` | FK User | Vendedor responsável |
| `titulo` | CharField(255) | Título da oportunidade |
| `valor_estimado` | Decimal(12,2) | Valor estimado |
| `probabilidade` | Integer(50) | % de probabilidade |
| `prioridade` | CharField | baixa/normal/alta/urgente |
| `tags` | M2M TagCRM | Tags visuais |
| `plano_interesse` | FK PlanoInternet | Plano de interesse |
| `origem_crm` | CharField | automatico/manual/importacao |
| `data_entrada_estagio` | DateTime | Para cálculo de SLA |
| `motivo_perda` / `concorrente_perdido` | Text/Char | Se perdeu |
| `contrato_hubsoft_id` | CharField(100) | ID do contrato no HubSoft |
| `churn_risk_score` | Integer(0-100) | Score de risco de churn |

**Propriedades:** `dias_no_estagio`, `sla_vencido`
**Índices:** (estagio, ativo), (responsavel, estagio), (data_fechamento_previsto), (churn_risk_score)

**HistoricoPipelineEstagio** — Tabela: `crm_historico_estagio`

Log de cada movimentação de estágio: oportunidade, estágio anterior/novo, movido_por, motivo, tempo_no_estagio_horas.

#### Tarefas e Notas

**TarefaCRM** — Tabela: `crm_tarefas`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `oportunidade` / `lead` | FK | Vinculado a oportunidade ou lead |
| `responsavel` | FK User | Quem deve executar |
| `tipo` | CharField | ligacao/whatsapp/email/visita/followup/proposta/instalacao/suporte/outro |
| `titulo` / `descricao` | Char/Text | Descrição |
| `status` | CharField | pendente/em_andamento/concluida/cancelada/vencida |
| `prioridade` | CharField | baixa/normal/alta/urgente |
| `data_vencimento` | DateTime | Prazo |
| `lembrete_em` | DateTime | Lembrete automático |

`save()` auto-marca como `vencida` se prazo venceu.

**NotaInterna** — Tabela: `crm_notas_internas`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `oportunidade` / `lead` | FK | Contexto |
| `autor` | FK User | Quem escreveu |
| `mencoes` | M2M User | Menções (@usuario) |
| `conteudo` | TextField | Texto |
| `tipo` | CharField | geral/reuniao/ligacao/email/importante/alerta |
| `is_fixada` | BooleanField | Fixada no topo |

#### Equipes e Perfis

**EquipeVendas** — Tabela: `crm_equipes`

Nome, líder (FK User), descrição, cor_hex, ativo.

**PerfilVendedor** — Tabela: `crm_perfis_vendedor`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `user` | OneToOne User | Usuário |
| `equipe` | FK EquipeVendas | Equipe (1:1) |
| `cargo` | CharField | vendedor/supervisor/gerente/diretor/outro |
| `telefone_direto` / `whatsapp` | CharField | Contato |
| `id_vendedor_hubsoft` | Integer | ID no HubSoft |

#### Metas

**MetaVendas** — Tabela: `crm_metas_vendas`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tipo` | CharField | individual/equipe |
| `vendedor` / `equipe` | FK | Quem tem a meta |
| `periodo` | CharField | diario/semanal/mensal/trimestral |
| `data_inicio` / `data_fim` | DateField | Período |
| `meta_vendas_quantidade` / `meta_vendas_valor` / `meta_leads_qualificados` / `meta_contatos` | Numéricos | Metas |
| `realizado_vendas_quantidade` / `realizado_vendas_valor` / `realizado_leads` | Numéricos | Realizado |

**Propriedades:** `percentual_quantidade`, `percentual_valor`

#### Segmentos

**SegmentoCRM** — Tabela: `crm_segmentos`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField(100) | Nome do segmento |
| `tipo` | CharField | dinamico/manual/hibrido |
| `regras_filtro` | JSONField | Regras de filtragem para segmentos dinâmicos |
| `leads` | M2M via MembroSegmento | Leads do segmento |
| `cor_hex` / `icone_fa` | Char | Visual |
| `total_leads` | PositiveInteger | Cache do total |

**Regras de filtro (JSON):**
```json
[
    {"campo": "origem", "operador": "igual", "valor": "whatsapp"},
    {"campo": "score_qualificacao", "operador": "maior", "valor": "7"},
    {"campo": "cidade", "operador": "contem", "valor": "Teresina"}
]
```

Campos disponíveis: origem, score_qualificacao, cidade, estado, bairro, valor, status_api, dias_cadastro
Operadores: igual, diferente, contem, maior, menor, maior_igual, menor_igual

**MembroSegmento** — Tabela: `crm_membros_segmento`

Through table: segmento FK, lead FK, adicionado_manualmente, adicionado_por.

#### Retenção

**AlertaRetencao** — Tabela: `crm_alertas_retencao`

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cliente_hubsoft` | FK ClienteHubsoft | Cliente |
| `lead` / `oportunidade` | FK | Contexto |
| `tipo_alerta` | CharField | contrato_expirando/inadimplencia/plano_downgradado/sem_uso/reclamacao/upgrade_disponivel/aniversario_contrato |
| `nivel_risco` | CharField | baixo/medio/alto/critico |
| `score_churn` | Integer(0-100) | Score de risco |
| `status` | CharField | novo/em_tratamento/resolvido/perdido |

**Scanner automático:** analisa contratos do HubSoft, cria alertas baseado em dias restantes (≤30 = crítico/90, ≤60 = alto/70, ≤90 = médio/50).

#### Configuração

**ConfiguracaoCRM** — Tabela: `crm_configuracao` | Singleton por tenant

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `sla_alerta_horas_padrao` | PositiveInteger(48) | SLA padrão em horas |
| `criar_oportunidade_automatico` | BooleanField(True) | Auto-criar oportunidade quando lead qualificado |
| `score_minimo_auto_criacao` | Integer(7) | Score mínimo para auto-criação |
| `pipeline_padrao` / `estagio_inicial_padrao` | FK | Pipeline e estágio padrão |
| `notificar_responsavel_nova_oportunidade` / `notificar_sla_breach` | BooleanField | Notificações |
| `webhook_n8n_nova_oportunidade` / `mudanca_estagio` / `tarefa_vencida` | URLField | Webhooks N8N |

### Services

**segmentos.py** (4 funções):

| Função | O que faz |
|--------|-----------|
| `filtrar_leads_por_regras(regras, queryset)` | Aplica regras de filtro dinâmico ao queryset de leads |
| `lead_atende_regras(lead, regras)` | Verifica se um lead específico atende todas as regras (sem query) |
| `atualizar_membros_segmento(segmento)` | Sync completo: remove quem não atende, adiciona quem atende |
| `avaliar_lead_em_segmentos(lead)` | Avalia lead em TODOS os segmentos dinâmicos/híbridos do tenant |

### Signals (3)

1. **criar_oportunidade_automatica** (post_save LeadProspecto) — Cria OportunidadeVenda quando lead atinge score mínimo ou status_api='sucesso'
2. **verificar_conversao_historico** (post_save HistoricoContato) — Move oportunidade para estágio ganho quando converteu_venda=True
3. **avaliar_segmentos_dinamicos** (post_save LeadProspecto) — Avalia lead em segmentos dinâmicos, dispara evento `lead_entrou_segmento` para automações

### Views (40+ funções)

| Área | Views | Descrição |
|------|-------|-----------|
| **Pipeline** | pipeline_view, api_pipeline_dados, api_mover_oportunidade | Kanban com drag-drop, filtros, movimentação |
| **Oportunidades** | oportunidades_lista, oportunidade_detalhe, api_atribuir, api_notas, api_tarefas | CRUD de oportunidades com contexto rico |
| **Tarefas** | tarefas_lista, api_tarefa_concluir, api_tarefa_criar | Gestão de tarefas agrupadas (hoje/semana/vencidas/concluídas) |
| **Notas** | api_nota_criar, api_nota_fixar, api_nota_deletar | Notas internas com fixar/desfixar |
| **Desempenho** | desempenho_view, api_desempenho_dados | Dashboard de performance por vendedor |
| **Metas** | metas_view, api_meta_criar, api_meta_salvar, api_meta_excluir | CRUD de metas individuais/equipe |
| **Retenção** | retencao_view, api_tratar_alerta, api_resolver_alerta, api_scanner_retencao | Gestão de alertas de churn |
| **Segmentos** | segmentos_lista, segmento_detalhe, api_segmento_salvar, api_preview_regras, api_adicionar_lead, api_remover_membro, api_disparar_campanha | Segmentação dinâmica com regras |
| **Configurações** | configuracoes_crm, api_salvar_config, api_criar_estagio, api_reordenar_estagios, api_excluir_estagio | Config do CRM (pipelines, estágios, webhooks) |
| **Equipes** | equipes_view, api_criar_equipe | Gestão de equipes de vendas |
| **Webhook** | webhook_hubsoft_contrato | Recebe confirmação de contrato do HubSoft |

**Visibilidade:** vendedores não-superuser veem apenas suas oportunidades + não atribuídas.

### Templates (13)

| Template | Descrição |
|----------|-----------|
| `pipeline.html` | Kanban drag-drop (990 linhas) |
| `oportunidades_lista.html` | Lista de oportunidades com filtros |
| `oportunidade_detalhe.html` | Detalhe com notas, tarefas, histórico, HubSoft |
| `tarefas_lista.html` | Tarefas agrupadas com tabs |
| `metas.html` | Metas com progress bars |
| `desempenho.html` | Dashboard de performance |
| `retencao.html` | Alertas de churn por nível de risco |
| `segmentos_lista.html` | Grid de segmentos |
| `segmento_detalhe.html` | Membros do segmento |
| `segmento_criar.html` | Criar/editar segmento com rule builder |
| `equipes.html` | Gestão de equipes |
| `configuracoes_crm.html` | Config (pipelines, estágios, webhooks) |
| `_tarefa_card.html` | Componente reutilizável de card de tarefa |

---

## Integrações entre Submódulos

```
Leads ──signal──▶ CRM (auto-cria oportunidade quando score >= 7)
Leads ──signal──▶ CRM/Segmentos (avalia segmentos dinâmicos)
Atendimento ──FK──▶ Leads (AtendimentoFluxo.lead)
Cadastro ──gera──▶ Leads (CadastroCliente.gerar_lead())
Viabilidade ──consulta──▶ Cadastro (verificação de cobertura)
HistoricoContato ──signal──▶ CRM (conversão automática)
CRM ──webhook──▶ HubSoft (confirmação de contrato)
CRM ──webhook──▶ N8N (nova oportunidade, mudança de estágio, tarefa vencida)
CRM/Segmentos ──event──▶ Automações (lead_entrou_segmento)
```

---

## Estatísticas do Módulo

| Métrica | Valor |
|---------|-------|
| **Sub-apps** | 5 (leads, atendimento, cadastro, viabilidade, crm) |
| **Models** | 28 |
| **Views** | 80+ funções |
| **Templates** | 22 |
| **APIs** | 70+ endpoints |
| **Signals** | 7 |
| **Índices** | 50+ |
| **Linhas de código** | ~8.000+ (models + views + services) |
