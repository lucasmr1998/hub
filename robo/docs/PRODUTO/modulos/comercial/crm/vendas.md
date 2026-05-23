# CRM — Vendas (Módulo Nativo)

## Contexto

`Venda` é a entidade que representa uma venda concretizada dentro do Hubtrix, **sem dependência de ERP**. A `/vendas/crm/` é a fonte da verdade; o envio para o ERP é uma ação opcional e manual (ou automática, dependendo das configurações de integração).

**Fluxo:**
```
Bot finaliza coleta de documentos
  → sinal docs_validados (signal engine_apos_imagem)
  → automação CRM com evento docs_validados → action criar_venda
  → Venda criada em status pendente_erp
  → vendedor gerencia em /vendas/crm/
  → (opcional) clique em "Enviar ao ERP" → HubSoftService ou SGPService
```

---

## Model Venda

**Tabela:** `crm_vendas`

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `lead` | FK LeadProspecto CASCADE | Lead da venda (obrigatorio) |
| `oportunidade` | FK OportunidadeVenda null SET_NULL | Oportunidade associada (opcional) |
| `plano` | FK PlanoInternet null SET_NULL | Plano contratado |
| `valor` | Decimal(12,2) null | Valor da venda |
| `status` | CharField(20) | pendente_erp / enviado_erp / ativo / erro_erp |
| `data_venda` | DateTimeField auto_now_add | Data da criacao da venda |
| `enviado_erp_em` | DateTimeField null | Data do envio ao ERP |
| `erro_erp_msg` | TextField blank | Mensagem de erro do ultimo envio |
| `criado_por` | FK User null SET_NULL | Quem criou (null = automação) |

**Ordering:** `-data_venda`

---

## Criação automática

**Como ativar:**
1. Acessar `/automacoes/` → criar nova regra
2. Evento: `Documentos validados` (`docs_validados`)
3. Ação: `Criar venda` (`criar_venda`)

**Idempotência:** `_acao_criar_venda` verifica se já existe `Venda` para o lead antes de criar. Sem duplicatas.

**Signal responsável:** `engine_apos_imagem` em `apps/comercial/crm/signals.py`. Dispara `docs_validados` quando TODOS os documentos do lead estão com `status_validacao = 'documentos_validos'`.

---

## Envio ao ERP

**View:** `api_enviar_venda_erp` (`POST /api/vendas/crm/<pk>/enviar-erp/`)

- Busca integração ativa do tenant (tipo `hubsoft` ou `sgp`)
- Verifica se `enviar_lead` não está `desativado` nas config de sync
- Chama `HubSoftService.cadastrar_prospecto(lead)` ou `SGPService.cadastrar_prospecto_para_lead(lead)`
- Atualiza `status → enviado_erp` e registra `enviado_erp_em`
- Em caso de erro: `status → erro_erp` + salva `erro_erp_msg`

O botão "Enviar ao ERP" aparece na tabela e no modal somente se o tenant tiver integração ERP ativa (`tem_integracao_erp` passado no contexto de `vendas_crm_view`).

---

## Página /vendas/crm/

**View:** `vendas_crm_view` + `api_oportunidades_vendas`

**Filtros disponíveis:** pipeline, status ERP, status de documentação, busca por nome/CPF/telefone

**Stats:** total de vendas, pendente ERP, enviado ERP, valor total

**Colunas:** Cliente, Telefone, Plano, Pipeline/Estágio, Responsável, Valor, Data, Status ERP, Documentação, Ação

---

## Observações

- `Venda` usa `TenantMixin` — `TenantManager` filtra por tenant automaticamente
- A `api_oportunidades_vendas` continua com o mesmo nome de URL por compatibilidade com o template
- `OportunidadeVenda` continua existindo e sendo gerenciada separadamente no pipeline CRM
- A `/vendas/` (sem `/crm/`) é a página legada que espelha o HubSoft — mantida para tenants com integração ativa que precisam ver clientes já cadastrados no ERP
