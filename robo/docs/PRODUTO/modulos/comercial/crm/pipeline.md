# CRM — Pipeline e Estagios

## Pipeline

**Tabela:** `crm_pipelines`

Configura cada funil de vendas do tenant. Um tenant pode ter varios pipelines (vendas, suporte, onboarding).

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `nome` / `slug` | CharField / Slug | Identificacao |
| `tipo` | CharField | vendas / suporte / onboarding / custom |
| `cor_hex` / `icone_fa` | Char | Visual |
| `padrao` | BooleanField | Pipeline padrao para auto-criacao |

---

## PipelineEstagio

**Tabela:** `crm_pipeline_estagios`

Cada coluna do Kanban.

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `pipeline` | FK Pipeline | Pipeline pai |
| `nome` / `slug` / `ordem` | Identificacao | Ordem no Kanban |
| `tipo` | CharField | novo / qualificacao / negociacao / fechamento / cliente / retencao / perdido |
| `is_final_ganho` / `is_final_perdido` | BooleanField | Flags de encerramento |
| `probabilidade_padrao` | Integer(50) | % padrao de probabilidade |
| `sla_horas` | PositiveInteger | SLA em horas |

**SLA:** quando uma oportunidade fica no estagio por mais tempo que `sla_horas`, e marcada como vencida.

---

## HistoricoPipelineEstagio

**Tabela:** `crm_historico_estagio`

Log de cada movimentacao de estagio:

- `oportunidade` FK
- `estagio_anterior` / `estagio_novo` FK
- `movido_por` FK User
- `motivo` TextField
- `tempo_no_estagio_horas` Decimal

Usado para analise de ciclo de venda e gargalos no pipeline.

---

## Campos obrigatorios pra entrar em um estagio (16/06/2026)

`PipelineEstagio.campos_obrigatorios` (JSONField, lista) — codigos de campos que devem estar preenchidos para a oportunidade poder avancar pra esse estagio.

**Formato**: `["lead.cpf_cnpj", "lead.cep", "oportunidade.valor_estimado"]`

**Campos disponiveis** (lista em `apps/comercial/crm/services/requisitos_estagio.py:CAMPOS_DISPONIVEIS`) — agrupados em 5 categorias:
- **Lead — identificacao**: nome_razaosocial, email, telefone, cpf_cnpj, rg, data_nascimento
- **Endereco**: cep, rua, numero_residencia, bairro, cidade, estado
- **Qualificacao**: empresa, score_qualificacao
- **Gate externo**: score_status_aprovado (resolvido como `score_status == 'aprovado'`), documentacao_validada, contrato_aceito
- **Oportunidade**: valor_estimado, probabilidade, data_fechamento_previsto, responsavel

**Validacao em 2 caminhos**:
1. **`api_mover_oportunidade`** (mover manual via UI ou API): retorna `HTTP 400` com `{codigo: 'campos_obrigatorios_faltando', campos_faltando: [{codigo, label}]}`. Frontend (detalhe da oportunidade) mostra toast "Bloqueado: Faltam campos: X, Y, Z" tanto no modal `Mover estagio` quanto nos CTAs rapidos.
2. **Engine de automacao** (`_mover_por_regra` em `automacao_pipeline.py`): silenciosamente nao move a oportunidade se faltarem campos — regra pode bater de novo quando lead completar (sem log de erro alto-volume).

**Configuracao via UI** — modal "Editar estagio" em `/crm/configuracoes/` ganha secao "Campos obrigatorios pra entrar neste estagio" com checkboxes agrupados por modulo. Persistido via endpoint dedicado `POST /configuracoes/estagios/<pk>/campos-obrigatorios/`.

**Substitui regras antigas** baseadas so em tag — antes a regra #11 da Nuvyon checava so `tag=Comercial` pra mover pra "Dados Completos", o que permitia avancar sem CPF/CEP/email. Agora a logica vive no proprio estagio.

Migration: `crm/0022_pipelineestagio_campos_obrigatorios`.
