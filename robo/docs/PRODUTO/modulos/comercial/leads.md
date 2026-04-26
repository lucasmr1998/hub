# Comercial — Leads

**App:** `apps/comercial/leads/`

Captura, armazena e qualifica leads de qualquer canal (WhatsApp, site, Instagram, Facebook, telefone). Gerencia documentos (selfie, RG frente/verso) e historico de contatos do bot.

---

## Models (4)

### LeadProspecto

**Tabela:** `leads_prospectos` | 60+ campos

| Grupo | Campos principais |
|-------|-------------------|
| **Identificacao** | nome_razaosocial, email (unique), telefone (validado, regex), cpf_cnpj, rg, data_nascimento |
| **Endereco** | rua, numero_residencia, bairro, cidade, estado, cep, ponto_referencia |
| **Comercial** | valor (Decimal 12,2), origem (site/facebook/instagram/google/whatsapp/indicacao/telefone/email/outros), score_qualificacao (1-10), empresa |
| **Status** | status_api (pendente/processado/erro/sucesso/rejeitado/aguardando_retry), ativo |
| **Documentacao** | documentacao_completa, documentacao_validada, contrato_aceito, anexos_contrato_enviados, ip_aceite_contrato |
| **Conversas** | url_pdf_conversa, html_conversa_path, data_geracao_pdf, data_geracao_html |
| **Contato** | tentativas_contato, data_ultimo_contato, motivo_rejeicao, canal_entrada, tipo_entrada |
| **Campanhas** | campanha_origem FK, campanha_conversao FK, total_campanhas_detectadas, metadata_campanhas (JSON) |
| **IDs externos** | id_hubsoft, id_origem, id_origem_servico, id_plano_rp, id_dia_vencimento, id_vendedor_rp |

**14 indices** incluindo compostos: `(canal_entrada, data_cadastro)`, `(score_qualificacao, status_api)`, `(tipo_entrada, ativo)`

**Metodos principais:**

- `calcular_score_qualificacao()` → score 1-10 baseado em dados preenchidos
- `validar_documentacao_completa()` → verifica selfie + doc_frente + doc_verso
- `aceitar_contrato(ip_address)` → marca contrato aceito com IP e timestamp
- `gerar_url_pdf()` → gera URL do PDF da conversa
- `get_historico_contatos_relacionados()` → contatos por lead ou telefone
- `get_taxa_sucesso_contatos()` → % de contatos bem-sucedidos
- `get_documentos_por_tipo()` → organiza documentos por tipo

### ImagemLeadProspecto

**Tabela:** `imagens_lead_prospecto`

Armazena URLs de imagens externas (documentos do lead).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead pai |
| `link_url` | URLField(1024) | URL da imagem |
| `descricao` | CharField(255) | Descricao |
| `status_validacao` | CharField(30) | pendente / documentos_validos / documentos_rejeitados |
| `observacao_validacao` | TextField | Observacoes |
| `validado_por` | CharField(150) | Username do validador |

### Prospecto

**Tabela:** `prospectos`

Representa o prospecto no HubSoft. Vinculado ao lead via FK. Controla o processamento de envio para o ERP.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead pai (opcional) |
| `nome_prospecto` | CharField(255) | Nome |
| `id_prospecto_hubsoft` | CharField(100, unique) | ID no HubSoft |
| `status` | CharField(20) | pendente / processando / processado / erro / finalizado / cancelado / aguardando_validacao / validacao_aprovada / validacao_rejeitada |
| `tentativas_processamento` | PositiveInteger | Tentativas |
| `tempo_processamento` | Decimal(10,3) | Tempo em segundos |
| `dados_processamento` / `resultado_processamento` | JSONField | Input/output do processamento |
| `score_conversao` | Decimal(5,2) | Score 0-100 de probabilidade de conversao |

**Metodos:** `iniciar_processamento()`, `finalizar_processamento()`, `calcular_score_conversao_automatico()`

### HistoricoContato

**Tabela:** `historico_contato`

Registra cada interacao do bot ou agente com o contato. Usado para funil de conversao e metricas.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `lead` | FK LeadProspecto | Lead (opcional) |
| `telefone` | CharField(17) | Telefone do contato |
| `status` | CharField(30) | 14 status possiveis (fluxo_inicializado, venda_confirmada, etc.) |
| `duracao_segundos` | PositiveInteger | Duracao da chamada |
| `transcricao` | TextField | Transcricao |
| `sucesso` | BooleanField | Se o contato foi bem-sucedido |
| `converteu_lead` / `converteu_venda` | BooleanField | Flags de conversao |
| `valor_venda` | Decimal(12,2) | Valor da venda (se converteu) |
| `protocolo_atendimento` / `codigo_atendimento` | CharField(100) | IDs do atendimento |
| `id_conta` / `numero_conta` | CharField(100) | IDs da conta no ERP |

**15 indices** para performance em relatorios de funil.

---

## APIs (20 endpoints)

| Grupo | Endpoints | Auth |
|-------|-----------|------|
| **Lead CRUD** | registrar, atualizar, consultar | `@api_token_required` |
| **Imagens** | registrar, listar, deletar, validar, por-cliente | `@api_token_required` |
| **Prospectos** | registrar, atualizar | `@api_token_required` |
| **Historico** | registrar, atualizar, consultar | `@api_token_required` |
| **Vendas** | aprovar, rejeitar | `@api_token_required` |
| **Consulta** | leads (paginado), historicos (paginado) | Publico |
| **Pagina** | leads (lista no painel) | `@login_required` |

---

## Signals (3)

1. **relate_prospecto_when_lead_has_hubsoft** — Quando lead salvo com `id_hubsoft`, vincula prospectos com mesmo `id_prospecto_hubsoft`
2. **relate_lead_when_prospecto_has_hubsoft** — Quando prospecto salvo com `id_prospecto_hubsoft` sem lead, vincula ao lead
3. **enviar_lead_para_integracao** (em `apps/integracoes/signals.py`) — Quando lead criado com `status_api='pendente'` e `ConfiguracaoEmpresa.enviar_leads_integracao=True`, dispara cadastro automatico no ERP da empresa. Roteia por tipo: HubSoft -> `cadastrar_prospecto`, SGP -> `cadastrar_prospecto_para_lead`. Sincroniza cliente apos cadastro se `sincronizar_cliente` em modo automatico. Persiste `new_cliente_id` em `LeadProspecto.id_hubsoft`.

---

## Template

`leads.html` — Pagina de gestao de leads com filtros (origem, status, ativo), cards de estatisticas (total, valor, erros, hoje, semana), tabela com acoes.
