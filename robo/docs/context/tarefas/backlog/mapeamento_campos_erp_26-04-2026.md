---
name: "Mapeamento de campos ERP <-> Hubtrix via CampoCustomizado"
description: "Pontes configuraveis entre campos do HubSoft/SGP e os CampoCustomizado do tenant, evitando hardcoded em cada provedor novo. Abordagem hibrida: core hardcoded + extensao via CampoCustomizado."
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Mapeamento de campos ERP <-> Hubtrix — 26/04/2026

**Data:** 26/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando (executar depois do H4 da paridade HubSoft)

---

## Descrição

Hoje a sincronização de cliente HubSoft/SGP para o Hubtrix tem **~30 campos hardcoded** em `_sincronizar_dados_cliente` (HubSoft) e `sincronizar_cliente` (SGP). Cada provedor novo (Inovax, Voalle, MK, Gigamax, etc) exige código novo. Pior: campos `CampoCustomizado` criados pelo cliente no Hubtrix **não conversam** com o ERP — se a equipe FATEPI cria um campo "interesse_principal", ele fica preso no Hubtrix.

**Objetivo:** criar uma ponte configurável entre os campos do ERP e os `CampoCustomizado` do tenant, sem virar um motor de transformação genérico (over-engineering).

---

## Abordagem aprovada — Híbrida

**Camada 1 — Core hardcoded (universal, todo provedor tem):**
- nome_razaosocial, cpf_cnpj, email, telefone, endereço, data_nascimento, ativo, id_externo
- Continua como está. Não precisa configurar.

**Camada 2 — Extensão via `CampoCustomizado` (configurável por tenant):**
- Cliente cria `CampoCustomizado(slug='motivo_contratacao')` na tela de configuração já existente.
- Adiciona `mapeamento_erp` (JSONField) e `direcao_sync` (choice) ao model.
- Sync de cliente HubSoft/SGP popula `dados_custom` automaticamente lendo o mapeamento.
- Cadastro de prospecto envia `dados_custom` pro ERP automaticamente quando `direcao_sync in (saida, ambas)`.

**Camada 3 — Fallback:**
- O que não está mapeado fica em `dados_completos` JSONField como hoje. Sem perda.

---

## Tarefas

### Modelo + migration

- [ ] Adicionar campo `mapeamento_erp` (JSONField, default=dict, blank=True) em `apps.comercial.leads.models.CampoCustomizado`. Estrutura esperada: `{"hubsoft": "id_origem_cliente", "sgp": "origem_id"}`.
- [ ] Adicionar campo `direcao_sync` (CharField com choices: `entrada`, `saida`, `ambas`, `nenhuma`, default=`nenhuma`) em `CampoCustomizado`.
- [ ] Migration de schema (sem backfill — defaults seguros).

### Helper compartilhado

- [ ] Criar `apps.integracoes.utils.mapeamento.aplicar_mapeamento_entrada(tenant, dados_erp, provedor) -> dict` que retorna `{slug: valor}` para popular `lead.dados_custom`.
- [ ] Criar `apps.integracoes.utils.mapeamento.aplicar_mapeamento_saida(tenant, lead, provedor) -> dict` que retorna `{campo_erp: valor}` para injetar no payload de prospecto.

### Integração nos services

- [ ] `HubsoftService._sincronizar_dados_cliente`: depois de preencher os campos core, chamar `aplicar_mapeamento_entrada` e atualizar `lead.dados_custom` (se houver lead vinculado) ou um espelho similar em `ClienteHubsoft.dados_custom_extras` (decidir na implementação).
- [ ] `HubsoftService._mapear_lead_para_hubsoft`: depois de montar payload core, chamar `aplicar_mapeamento_saida` e merge no payload.
- [ ] Mesma coisa no `SGPService.sincronizar_cliente` e `SGPService.cadastrar_prospecto_para_lead`.

### UI

- [ ] Em `/comercial/configuracoes/campos-leads/`, cada `CampoCustomizado` ganha:
  - Select "Direção do sync" (entrada / saída / ambas / nenhuma)
  - Quando direção != nenhuma, campos condicionais "Campo no HubSoft" e "Campo no SGP" — autocomplete alimentado pelo cache de catálogos sincronizado em H2 (lista de chaves possíveis dos `dados_completos` retornados nos últimos syncs OU lista fixa documentada).
- [ ] Tela mostra preview: "Quando o cliente vier do HubSoft, o campo `Motivo de Contratação` vai ser preenchido com `id_origem_cliente`."

### Documentação

- [ ] Criar `robo/docs/PRODUTO/integracoes/06-MAPEAMENTO-ERP.md` explicando:
  - Como criar um campo customizado e mapear pra ERP
  - Lista dos campos disponíveis no HubSoft e SGP (referência)
  - Casos de uso típicos (motivo_contratacao, origem, profissão, dados de PJ)
  - Limitações (sem transformações, sem mapeamento N:1)

### Permissões

- [ ] Mapeamento de campos é configuração sensível (afeta dados que vão pro ERP). Restringir tela de gerência a `permissao.config.campos_custom.editar`.

---

## O que **NÃO** faz parte deste escopo

- Motor de transformação (regex, conversão de formato, derivação)
- Tabelas de domínio (ex: "origem 'Instagram' do ERP A = origem 5 do ERP B")
- Sincronização bidirecional contínua (webhooks ERP → Hubtrix em tempo real)

Cada um desses pode virar tarefa própria se um cliente real demandar.

---

## Resultado esperado

- Adicionar provedor ERP novo (Inovax, Voalle, MK) deixa de exigir mexer no service para campos não-core. Só configurar mapeamento via UI.
- Cliente FATEPI consegue rastrear `motivo_contratacao` do HubSoft no `CampoCustomizado` próprio, sem PR.
- Cliente que captura `interesse_principal` no fluxo Hubtrix consegue mandar pra HubSoft via mapeamento de saída.

---

## Contexto e referências

- Pré-requisito: H1, H2, H3, H4 da paridade HubSoft (`paridade_integracao_hubsoft_26-04-2026.md`)
- Sucessor: H5 (viabilidade) e H6 (atendimento bidirecional) — ambos vão precisar desse mapeamento.
- Modelos atuais:
  - `apps.comercial.leads.models.CampoCustomizado` (já tem `entidade`, `tipo`, `slug`, `opcoes`, `obrigatorio`)
  - `LeadProspecto.dados_custom` (JSONField, já existe)
  - `Oportunidade.dados_custom` (JSONField, já existe)
- Services:
  - `apps.integracoes.services.hubsoft.HubsoftService`
  - `apps.integracoes.services.sgp.SGPService`
- Tela atual: `/comercial/configuracoes/campos-leads/` (`apps.comercial.leads.views.campos_custom_view`)
