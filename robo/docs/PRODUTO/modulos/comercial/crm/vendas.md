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

---

## PROPOSTA DE DESIGN — Venda unificada (Venda como fonte da verdade + sync HubSoft opcional)

> **Status:** proposta (08/06/2026). Ainda não implementado. Decisões em aberto marcadas com **[DECIDIR]**.
> **Origem:** investigação do lead 541/opp 705 (Nuvyon) — ver [[automacoes-pipeline]]. Hoje existem **duas páginas** de "vendas" que confundem: `/vendas/` (espelho HubSoft) e `/vendas/crm/` (`crm_vendas`). Para a Nuvyon, a venda só aparecia no espelho HubSoft (cliente cod 59955, lead 463) e **não havia `Venda` em `crm_vendas`** — porque a Nuvyon não tem a regra `criar_venda` configurada.

### Problema

São **dois estágios da mesma jornada** tratados como entidades separadas:

| | `/vendas/crm/` (`crm_vendas`) | `/vendas/` (HubSoft) |
|---|---|---|
| Representa | venda registrada no nosso funil | cliente efetivado no ERP (pós-conversão) |
| Fonte da verdade | Hubtrix | HubSoft (espelho via `sincronizar_cliente`) |
| Quem usa hoje | TR Carrion (sem HubSoft) | Nuvyon (pipeline HubSoft) |

Resultado: a mesma "venda" cai em páginas diferentes dependendo do tenant, e nenhuma das duas mostra o ciclo completo.

### Modelo-alvo

`Venda` (`crm_vendas`) vira **fonte única da verdade**; HubSoft vira **downstream opcional por tenant**:

```
Venda confirmada (gatilho canônico — ver [DECIDIR #1])
   │
   ├─ SEMPRE cria Venda no crm_vendas            ← fonte da verdade (todos os tenants)
   │
   └─ SE IntegracaoAPI HubSoft/SGP ativa no tenant:
        ├─ push pro ERP (cadastrar_prospecto / contrato)
        ├─ status: pendente_erp → enviado_erp
        └─ reconciliação (sync ERP → Venda): enviado_erp → ativo | erro_erp
```

A página `/vendas/` passa a ser **uma só**: lista `crm_vendas` e, quando há integração, enriquece com o status do HubSoft (`clientes_hubsoft`/`servicos_cliente_hubsoft`, ligados por `lead_id`). O model `Venda` **já foi desenhado pra isso** — o enum `status` (`pendente_erp/enviado_erp/ativo/erro_erp`) comprova a intenção de "criar local → sincronizar com ERP".

### O que já existe vs o que falta

| Peça | Estado |
|---|---|
| Model `Venda` com status de ERP | ✅ existe |
| Ação `criar_venda` (cria em `pendente_erp`) | ✅ existe |
| `api_enviar_venda_erp` (push manual ao ERP) | ✅ existe |
| `cadastrar_prospecto` / `sincronizar_cliente` HubSoft | ✅ existe (hoje por signal no lead, **soltos** da `Venda`) |
| **`Venda` orquestrar o push pro ERP** (pendente_erp → enviado_erp automático) | ❌ falta |
| **Reconciliação ERP → Venda** (sync atualiza `Venda.status`, não só `clientes_hubsoft`) | ❌ falta |
| **Gatilho único de "venda confirmada"** consistente entre tenants | ❌ falta (TR Carrion usa `imagem existe`, frouxo; Nuvyon não tem) |
| Página `/vendas/` unificada (LEFT JOIN Venda ↔ cliente HubSoft) | ❌ falta |

> **Divergência doc↔prod observada:** esta doc dizia que `criar_venda` dispara em `docs_validados` (todas as imagens válidas). Em produção, a regra do TR Carrion (#7) dispara em `imagem_status existe` (qualquer imagem) — frouxo demais (1278 disparos, 2 efetivas). O gatilho canônico precisa ser redefinido (DECIDIR #1).

### Decisões em aberto

- **[DECIDIDO 08/06] Gatilho canônico = finalização do atendimento** ("finalizamos sua contratação").
  - **Mapeamento técnico:** `HistoricoContato.status = 'fluxo_finalizado'` — gravado pelo fluxo Matrix via `POST /api/historicos/registrar/` ao finalizar a contratação. Há tipo de condição `historico_status` no motor.
  - **Guard recomendado:** combinar com `id_plano_rp existe` (ou plano definido) pra não criar venda em fluxo finalizado sem contratação real.
  - **Side-benefit:** desacopla a venda da tag "Assinado" (que hoje quebra por nó mal configurado na Matrix apontando pra `/api/leads/atualizar/`). O lead 541 teve `fluxo_finalizado` (histórico #409) — com este gatilho, **teria gerado venda apesar do 400**.
  - Descartadas: (b) estágio `is_final_ganho` e (c) `docs_validados`. Abandonar o `imagem existe` atual do TR Carrion.
- **[DECIDIR #2]** A `Venda` orquestra o push pro HubSoft (criar Venda → dispara prospecto/contrato), ou mantém `cadastrar_prospecto` por signal e só **vincula**? *Recomendação:* Venda orquestra, pra ter um dono único do fluxo.
- **[DECIDIR #3]** Tenants **sem** ERP (TR Carrion): status local sem estados de ERP (ex: `concluida`) ou reaproveitar `ativo`?
- **[DECIDIR #4]** Backfill: criar `Venda` retroativa para clientes HubSoft já existentes sem `Venda` (ex: cod 59955 / lead 463, Nuvyon) pra a página unificada ficar consistente com o histórico.

### Página unificada (esboço)

Uma `/vendas/` única, por lead/oportunidade, com **status de ciclo de vida** derivado das duas fontes:

```
Venda registrada → Contrato assinado → OS aberta (instalação) → Cliente ativo
 (fluxo_finalizado)    (pós-venda)          (pós-venda)           (servico ATIVO via sync)
```

> **Ordenação do ciclo (decidido 08/06):** a **Venda** é registrada no "finalizamos sua contratação" (`fluxo_finalizado`). **Contrato assinado** e **abertura de OS/instalação** são etapas **PÓS-venda** (downstream) — **nunca** pré-condição pra criar a Venda. Por isso o gate atual da Nuvyon (regra #19 exigindo "docs validados" antes da venda) está **invertido**: documentos/contrato/OS vêm depois. No modelo unificado, esses passos só **avançam o status** de uma Venda que já existe; não a criam.

- LEFT JOIN `crm_vendas` ↔ `clientes_hubsoft` em `lead_id` (e `servicos_cliente_hubsoft` p/ status do serviço).
- Trata os dois lados como opcionais: mostra o que existir (tenant sem ERP só tem o lado CRM; cliente que veio direto do ERP ganha `Venda` via backfill).
- Colunas: Cliente, Contato, Plano, Valor, **Status (ciclo de vida)**, Documentação, Data, Ação.

### Fases de implementação (sugerida)

1. **Gatilho canônico** (DECIDIR #1) — uma regra/sinal único de "venda confirmada" cria a `Venda`.
2. **Orquestração do push** (DECIDIR #2) — `Venda` em `pendente_erp` + tenant com ERP ativo → envia; status → `enviado_erp`.
3. **Reconciliação** — `sincronizar_cliente` (ou cron) atualiza `Venda.status` → `ativo`/`erro_erp` a partir do HubSoft.
4. **Página unificada** — junta as duas views numa só com o status de ciclo de vida.
5. **Backfill** (DECIDIR #4) — `Venda` retroativa pros clientes HubSoft órfãos.

### Página unificada — especificação (decidido 09/06)

**Decisão de espinha:** **(A) `Venda` é a espinha**; a página faz LEFT JOIN com HubSoft por `lead_id`. Backfill cria `Venda` retroativa pros clientes HubSoft órfãos.

- **Escopo do backfill (prod, 09/06):** clientes HubSoft sem `Venda` = **21** → **`nuvyon`: 1** (real, cod 59955 / lead 463) + **`demo`: 20** (tenant de teste). Ou seja, **1 registro real**. Trivial.

**Views atuais (a unificar):**
- `vendas_crm_view` → `dashboard/vendas_crm.html`, dados via `api_oportunidades_vendas` (lista `Venda`). Docstring já diz *"fonte da verdade: model Venda"*.
- `vendas_view` → `dashboard/vendas.html`, lista `ClienteHubsoft`/`ServicoClienteHubsoft`.

**Plano:** `/vendas/` passa a ser a página unificada (template novo); `/vendas/crm/` **redireciona** pra `/vendas/`. Uma view, um template, um endpoint AJAX.

**Contrato da API unificada** (evolução de `api_oportunidades_vendas`): por `Venda`, retornar também o bloco HubSoft quando `ClienteHubsoft`/`ServicoClienteHubsoft` existir pro mesmo `lead_id`:
```
{
  venda: { id, lead, oportunidade, plano, valor, status, data_venda, criado_por },
  hubsoft: {            # null se tenant sem integração ou sem cliente ainda
    cliente: { codigo_cliente, ativo },
    servico: { id_cliente_servico, status, status_prefixo, valor }
  },
  status_ciclo: "<derivado>"   # ver tabela abaixo
}
```

**Status de ciclo de vida** — derivado do **estado REAL no HubSoft** (`lead.id_hubsoft` / `ClienteHubsoft` / serviço), com `Venda.status` como **fallback**. Implementado em `_status_ciclo` (`dashboard/views.py`). A prioridade pelo estado real é proposital: a `Venda.status` pode estar **defasada** (ex: `erro_erp` antigo mesmo após o prospecto já ter sido criado num reprocessamento — lead 542).

| Prioridade | Condição | status_ciclo |
|---|---|---|
| 1 | serviço `servico_habilitado` | **Ativo / Instalado** |
| 2 | serviço `aguardando_instalacao` | **Aguardando instalação** |
| 3 | serviço `cancel*` / `suspen*` | **Cancelado / Suspenso** |
| 4 | `ClienteHubsoft` existe | **Cliente criado no ERP** |
| 5 | **`lead.id_hubsoft` setado** (prospecto criado) | **Prospecto criado no ERP** ← sobrepõe `Venda.status` defasada |
| 6 | `Venda.status = erro_erp` (e sem `id_hubsoft`) | **Erro no ERP** |
| 7 | `Venda.status = enviado_erp` | **Enviada ao ERP** |
| 8 | resto (`pendente_erp`) | **Registrada** |

> Tenant **sem** integração ERP (ex: TR Carrion): `hubsoft` null e `lead.id_hubsoft` vazio → cai pra `Venda.status` (ver DECIDIR #3).

### Reconciliação Venda ↔ HubSoft (Fase 2 — implementado 09/06)

**Problema observado (09/06, lead 542):** a `Venda` (id 40) ficou `erro_erp` (do 1º disparo, que falhou no `id_origem_servico`) mesmo **após o prospecto ser criado com sucesso** (`id_hubsoft=22758`) num reprocessamento. O reprocessamento atualizou o **lead** (`status_api`, `id_hubsoft`), **não a Venda** — não há reconciliação.

A regra de `status_ciclo` (#5 acima) **já contorna isso na LEITURA** (deriva de `lead.id_hubsoft`), mas a **fonte** (`Venda.status`) continua errada.

**Fix da fonte (implementado):** helper `_reconciliar_venda_com_prospecto(lead_id, tenant_id)` em `apps/integracoes/signals.py` — quando o prospecto é criado (`lead.id_hubsoft` setado), avança a `Venda` do lead de `pendente_erp`/`erro_erp` → **`enviado_erp`** + `enviado_erp_em`. Chamado em `_enviar_lead_hubsoft` (signal) e em `processar_pendentes` (cron), logo após gravar o `id_hubsoft`. Idempotente (só toca `pendente_erp`/`erro_erp`). **Pendente:** avançar pra `ativo` quando o `ClienteHubsoft` é sincronizado (fica pro `sincronizar_cliente`).

**Colunas da página:** Cliente · Contato · Plano · Valor · **Status (ciclo)** · Documentação · Data · Ação.

**Ordem de implementação da página:** (1) endpoint unificado com o JOIN + `status_ciclo`; (2) template novo reaproveitando os cards/tabela; (3) redirect de `/vendas/crm/`; (4) remover o template/endpoint antigo do espelho HubSoft.
