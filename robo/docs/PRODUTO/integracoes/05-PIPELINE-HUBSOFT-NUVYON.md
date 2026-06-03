# Pipeline HubSoft (Nuvyon)

Documento do fluxo end-to-end de **Lead Matrix -> Prospect HubSoft -> Cliente HubSoft** pra Nuvyon. Atualizado 03/06/2026.

> **Escopo:** hoje a Nuvyon e a UNICA empresa em prod usando HubSoft. Toda regra desse doc se aplica so a `tenant=nuvyon`. Outros clientes (TR Carrion via Vero, FATEPI editor nativo) NAO entram aqui.

---

## Visao geral

```
Matrix (sistema externo Nuvyon)
        |
        v  webhook
Hubtrix /api/public/n8n/inbox/mensagem/    (cria LeadProspecto, tenant=nuvyon)
        |
        v
LeadProspecto criado com status_api='pendente' (ou 'sem_integracao' se tenant sem HubSoft)
        |
        v  cron processar_pendentes
[PRE-FLIGHT] validar_lead_pronto_para_prospect(lead, integracao)
        |
        +-- falhou: status_api='incompleto'/'cpf_invalido'/'duplicado_no_tenant'/'vendedor_invalido'
        |           + motivo_rejeicao explicativo. Operador corrige no admin.
        |
        v  passou
HubsoftService.cadastrar_prospecto(lead) -> API HubSoft
        |
        +-- erro: categoriza (cpf_invalido/vendedor_invalido/regra_negocio/erro)
        |         + motivo_rejeicao = mensagem completa do HubSoft.
        |
        v  sucesso
LeadProspecto.id_hubsoft setado + status_api='processado'
        |
        v  cron bot Selenium (futuro - depende de modos_sync.converter_prospect_cliente='ativado')
Bot UI Selenium navega wizard 7-steps Adicionar Cliente
        |
        v  step7 SALVAR
Cliente final no HubSoft + prospectos.status='finalizado' no Hubtrix
```

---

## Configuracao por tenant

3 niveis de flag (todos precisam estar OK pra Nuvyon processar):

### 1. `ConfiguracaoEmpresa.enviar_leads_integracao` (global)
- Tabela: `vendas_web_configuracaoempresa`
- Tipo: BooleanField
- Hoje: Nuvyon = `True`, todos os outros = `False`

### 2. `ConfiguracaoEmpresa.integracao_leads_id` (aponta integracao)
- FK pra `IntegracaoAPI`
- Hoje: Nuvyon = `18` (`IntegracaoAPI #18`, tipo=hubsoft, ativa=True)

### 3. `IntegracaoAPI.configuracoes_extras.modos_sync` (granular, JSONB)
- Sub-flags possiveis:
  ```json
  {
    "enviar_lead": "ativado",
    "converter_prospect_cliente": "ativado",
    "aceitar_contrato": "desativado",
    "sincronizar_planos": "desativado",
    "sincronizar_cliente": "desativado",
    "sincronizar_servicos": "desativado",
    "sincronizar_vendedores": "desativado",
    "sincronizar_vencimentos": "desativado",
    "anexar_documentos_contrato": "desativado"
  }
  ```
- **`enviar_lead`** controla `processar_pendentes` (cadastrar_prospecto API). Default `ativado` se sub-flag ausente. Lido por `utils.integracao_envia_lead()`.
- **`converter_prospect_cliente`** controla o bot Selenium (etapa 2). Default `desativado` (precisa explicito porque UI scraping pode regredir). Lido por `utils.integracao_converte_prospect_em_cliente()`.

---

## Pre-flight validation

Implementado em `apps/comercial/leads/utils.py::validar_lead_pronto_para_prospect(lead, integracao)`. Retorna `(status_api, motivo)`. Roda ANTES de cada `cadastrar_prospecto` no `processar_pendentes`.

| Status devolvido | Motivo |
|------------------|--------|
| `pendente` | Tudo OK, pode chamar API |
| `incompleto` | `campos faltando: rg, email, ...` |
| `cpf_invalido` | CPF nao passa no checksum brasileiro |
| `duplicado_no_tenant` | Mesmo CPF ja virou prospect (ja tem `id_hubsoft`) |
| `vendedor_invalido` | `id_vendedor_rp` fora do catalogo cacheado |

**Campos obrigatorios validados:** `nome_razaosocial`, `cpf_cnpj`, `telefone`, `email`, `cep`, `numero_residencia`, `rg`, `data_nascimento`.

> **Importante:** `rg` e obrigatorio no HubSoft Nuvyon. Matrix nao manda RG hoje — operador completa via admin do Hubtrix antes do cron processar.

---

## Catalogo HubSoft cacheado

`IntegracaoAPI.configuracoes_extras.cache` guarda snapshots dos catalogos do HubSoft (vendedores, origens, etc) pra:
- Pre-flight validar IDs sem chamar API
- Guard rail no `HubsoftService._mapear_lead_para_hubsoft` substituir ID invalido pelo `vendedor_id_padrao`

Sincronizado por `python manage.py sincronizar_catalogos_hubsoft [--tenant=X] [--dry-run]`. Registrar como CronJob diario (`0 6 * * *`).

Detecta diff: se vendedor sumiu entre rodadas, loga warning + conta leads pendentes afetados (que ficarao `vendedor_invalido` no pre-flight).

---

## Erros estruturados do HubSoft

`processar_pendentes` categoriza `HubsoftServiceError` pelo conteudo da mensagem:

| `status_api` | Trigger | Acao |
|--------------|---------|------|
| `cpf_invalido` | msg contem "cpf" + "invalido" | Operador corrige CPF |
| `vendedor_invalido` | msg contem "vendedor" + "invalido" | Sincronizar catalogo via `sincronizar_catalogos_hubsoft` |
| `regra_negocio` | msg contem "plano"/"unidade"/"cidade"/"origem" | Ajustar plano/UN compativel |
| `erro` (generico) | qualquer outro | Investigacao manual |

`motivo_rejeicao` recebe a mensagem completa pra inspecao no admin.

---

## Bot Selenium (etapa 2)

`web_driver_conversao_lead/main_refatorado.py` (multi-tenant, le config do Hubtrix via psycopg2 + decrypt Fernet/SECRET_KEY).

```bash
python main_refatorado.py \
  --tenant nuvyon \
  --nome "NOME DO LEAD" \
  --id-prospecto 22651 \
  --no-headless          # opcional, debug
  --dry-run              # opcional, nao clica SALVAR
```

Wizard Nuvyon = 7 steps (`<li name='step1..step7'>`):

| Step | O que faz |
|------|-----------|
| 1 Cadastro | Preenche rg, marca grupo_cliente=RESIDENCIAL, genero=MASCULINO |
| 2 Endereco | Avanca (pre-preenchido pelo CEP) |
| 3 Plano | Click no endereco_instalacao (dispara `vm.carregaUnidadeNegocio()`), vendedor=hubtrix, data_venda=hoje |
| 4 Contrato | Avanca (sem campos) |
| 5 Cobranca | Forma=SICREDI - NUVYON (polling DOM ate md-list-item aparecer, click via ActionChains), vencimento=9, tipo=Postecipada |
| 6 Pacotes | Avanca (sem campos) |
| 7 OS | Click SALVAR |

> **Por que `<hubsoft-select-virtual-repeat>` precisou polling DOM:** componente Angular custom tem isolated scope e usa `md-virtual-repeat-container` com lazy load via `md-on-open="vm.fnOnOpen()"`. Setar via `scope.vm.unidade_negocio.formas_cobranca` nao funciona (path errado). Estrategia que funciona: abrir, esperar `<md-list-item>` aparecer no DOM, clicar via ActionChains (mouse real — disparar ng-click nativo).

---

## Status reais hoje (03/06/2026)

| Item | Status |
|------|--------|
| `ConfiguracaoEmpresa.enviar_leads_integracao` Nuvyon | True ✓ |
| `extras.modos_sync.enviar_lead` Nuvyon | `ativado` ✓ (atualizado 03/06 antes do deploy do pre-flight) |
| `extras.modos_sync.converter_prospect_cliente` Nuvyon | NAO setado (bot roda manual ainda) |
| `extras.cache.vendedores` Nuvyon | 77 itens sincronizados |
| `extras.vendedor_id_padrao` Nuvyon | 743 (hubtrix) |
| `extras.id_origem_padrao` Nuvyon | 15 |
| Cron `processar_pendentes` | Existe, precisa cadastrar como CronJob |
| Cron `sincronizar_catalogos_hubsoft` | Codigo pronto, precisa cadastrar como CronJob (sugestao: `0 6 * * *`) |

---

## Operacao

### Diagnosticar lead que nao virou prospect

```sql
SELECT id, nome_razaosocial, cpf_cnpj, status_api, motivo_rejeicao,
       id_vendedor_rp, rg, data_atualizacao
FROM leads_prospectos
WHERE tenant_id = (SELECT id FROM sistema_tenant WHERE slug='nuvyon')
  AND status_api NOT IN ('processado','sucesso')
ORDER BY data_atualizacao DESC LIMIT 20;
```

### Forcar re-processamento de lead corrigido

```python
LeadProspecto.all_tenants.filter(pk=N).update(
    status_api='pendente', motivo_rejeicao=None,
)
# rodar:  python manage.py processar_pendentes --tenant=nuvyon --lead-id=N
```

### Sincronizar catalogo HubSoft fora do cron

```bash
python manage.py sincronizar_catalogos_hubsoft --tenant=nuvyon
```

### Ativar bot Selenium pra Nuvyon (futuro)

```python
i = IntegracaoAPI.all_tenants.get(pk=18)
extras = dict(i.configuracoes_extras or {})
modos = dict(extras.get('modos_sync') or {})
modos['converter_prospect_cliente'] = 'ativado'
extras['modos_sync'] = modos
i.configuracoes_extras = extras
i.save(update_fields=['configuracoes_extras'])
```
