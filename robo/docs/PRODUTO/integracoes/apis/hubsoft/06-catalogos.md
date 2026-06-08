# HubSoft API — Catalogos (configuracao)

11 catalogos do HubSoft sincronizados localmente no Hubtrix (`IntegracaoAPI.configuracoes_extras['hubsoft']['cache']`). Cache reduz round-trips na hora de criar prospecto/contrato + popular dropdowns no painel.

## Como funciona o cache

- Cron `sincronizar_catalogo_hubsoft --apenas-automatico` roda 1x/dia
- Respeita `modos_sync` por feature (`automatico` / `manual` / `desativado`)
- Cada catalogo cacheado em `configuracoes_extras['hubsoft']['cache'][<chave>]` com `{ "items": [...], "atualizado_em": "..." }`
- Botao "Sincronizar tudo" no painel `/configuracoes/integracoes/<pk>/` -> aba **Catalogos** dispara manualmente

```bash
# sync de todos
python manage.py sincronizar_catalogo_hubsoft --categoria=todos --apenas-automatico

# sync de uma categoria especifica
python manage.py sincronizar_catalogo_hubsoft --categoria=servicos --tenant nuvyon

# dry-run
python manage.py sincronizar_catalogo_hubsoft --categoria=todos --dry-run
```

## Os 11 catalogos

### 1. Servicos / Planos

`GET /api/v1/integracao/configuracao/servico`

Lista planos comercializaveis. Mostrado em selects de cadastro.

Service: `HubsoftService.sincronizar_servicos_catalogo()`.

Modo sync: `sincronizar_planos`.

### 2. Vencimentos

`GET /api/v1/integracao/configuracao/vencimento`

Dias de vencimento aceitos. Usado pra restringir o dropdown "dia de vencimento" no cadastro do prospecto.

Service: `HubsoftService.sincronizar_vencimentos()`.

Modo sync: `sincronizar_vencimentos`.

### 3. Vendedores

`GET /api/v1/integracao/configuracao/vendedor`

Lista de vendedores do tenant. Usado pra atribuir prospecto ao vendedor correto via `id_vendedor`.

Service: `HubsoftService.sincronizar_catalogo_cacheado('vendedores')`.

Modo sync: `sincronizar_vendedores`.

### 4. Origens de cliente

`GET /api/v1/integracao/configuracao/origem_cliente`

Como o cliente chegou (Site, Indicacao, Anuncio, etc).

### 5. Origens de contato

`GET /api/v1/integracao/configuracao/origem_contato`

Canal especifico (WhatsApp, Email, Telefone, Loja Fisica).

### 6. Meios de pagamento

`GET /api/v1/integracao/configuracao/meio_pagamento`

Boleto, Pix, Cartao, etc. Usado em renegociacao (`id_meio_pagamento`).

### 7. Grupos de cliente

`GET /api/v1/integracao/configuracao/grupo_cliente`

Segmentacao (Residencial, Empresarial, VIP).

### 8. Motivos de contratacao

`GET /api/v1/integracao/configuracao/motivo_contratacao`

Por que contratou (mudou de provedor, primeira contratacao, etc).

### 9. Tipos de servico

`GET /api/v1/integracao/configuracao/tipo_servico`

Internet, Telefonia, TV, Combo.

### 10. Status de servico

`GET /api/v1/integracao/configuracao/servico_status`

Habilitado, Suspenso, Cancelado, etc.

### 11. Tecnologias de servico

`GET /api/v1/integracao/configuracao/servico_tecnologia`

Fibra, Radio, GPON, etc.

---

## Helper service

`HubsoftService.sincronizar_catalogo_cacheado(chave)` aceita as chaves:
`vendedores`, `origens_cliente`, `origens_contato`, `meios_pagamento`, `grupos_cliente`, `motivos_contratacao`, `tipos_servico`, `servico_status`, `servicos_tecnologia`.

`servicos` e `vencimentos` tem services dedicados (chamados de fora desse cache normal porque sao mais usados).

`HubsoftService.sincronizar_configuracoes()` dispara TODOS os 11 numa unica chamada (wrapper).

---

## Cron

Registrado em [apps/sistema/management/commands/sincronizar_catalogo_hubsoft.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/sistema/management/commands/sincronizar_catalogo_hubsoft.py).

Cron: 1x/dia as 3am (ver [../../../ops/02-CRON.md §3.1](../../../ops/02-CRON.md)).

Flag `--apenas-automatico` filtra so categorias com modo `automatico` no tenant — categorias em `manual` ou `desativado` sao puladas.

---

## UI no painel

`/configuracoes/integracoes/<pk>/` -> aba **Catalogos**

- Lista cada catalogo com: nome, qtd items cacheada, `atualizado_em`, botao "Sincronizar agora"
- Botao "Sincronizar tudo" no topo dispara `sincronizar_configuracoes()`
- Aba **Configuracao** consome o cache pra popular selects de defaults (plano padrao, vendedor padrao, vencimento padrao, etc)

---

## Quando o cache pode estar stale

- Catalogo no modo `manual` ou `desativado` — nunca atualiza automatico
- Cron quebrou por algum motivo (ver `monitor_sistema` cron)
- Tenant novo sem sync inicial — precisar rodar `sincronizar_catalogo_hubsoft` no setup

Sintoma comum: dropdown de plano no cadastro vem vazio ou desatualizado. Solucao: rodar `sincronizar_catalogo_hubsoft --categoria=servicos --tenant <slug>`.
