# HubSoft API — Clientes e Contratos

## Prospecto (lead) — cadastrar

`POST /api/v1/integracao/prospecto`

Cria prospecto no HubSoft. Usado pelo signal `post_save` de `LeadProspecto` (status_api='pendente').

### Body principal

| Campo | Tipo | Descricao |
|---|---|---|
| `nome` | string | Nome completo |
| `cpf_cnpj` | string | So digitos |
| `telefone_celular` | string | DDD + numero |
| `email` | string | Email |
| `endereco` | obj | `cep`, `logradouro`, `numero`, `complemento`, `bairro`, `cidade`, `uf` |
| `id_plano` | int | ID do plano (catalogo) |
| `dia_vencimento` | int | Dia escolhido (5, 10, 15, etc — restrito por `dias_vencimento_permitidos_hubsoft`) |
| `id_vendedor` | int | Vendedor (catalogo) |
| `id_origem` | int | Origem do lead (catalogo) |

### Resposta

```json
{ "status": "success", "id_prospecto": 12345 }
```

Salvo em `LeadProspecto.id_hubsoft`. `status_api='processado'` no sucesso, `'erro'` em falha.

### Reprocessar leads com erro

```bash
python manage.py processar_pendentes
python manage.py processar_pendentes --lead-id 462 --dry-run
```

### Service

`HubsoftService.cadastrar_prospecto(lead)` em [apps/integracoes/services/hubsoft.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/hubsoft.py).

---

## Planos disponiveis por CEP

`GET /api/v1/integracao/prospecto/create?cep=<cep>`

Retorna planos ofertados na area do CEP. Usado em telas de cadastro pra preencher dropdown de planos.

Service: `HubsoftService.listar_planos_por_cep(cep)`.

---

## Cliente — consultar

`GET /api/v1/integracao/cliente?busca=cpf_cnpj&termo_busca=<cpf>`

Busca cliente por CPF/CNPJ. Outros campos disponiveis: `nome`, `id_cliente`, `telefone`, `email`.

### Resposta resumida

```json
{
  "status": "success",
  "clientes": [{
    "id_cliente": 100,
    "nome_razaosocial": "Joao Silva",
    "cpf_cnpj": "12345678900",
    "data_cadastro": "2025-01-15 10:00:00",
    "email": "joao@email.com",
    "telefone_primario": "5534999999999",
    "endereco_principal": { "cep": "...", "logradouro": "..." },
    "servicos": [
      {
        "id_cliente_servico": 57515,
        "id_servico": 12,
        "servico": "Plano 500MB",
        "status_prefixo": "servico_habilitado",
        "valor": 99.90,
        "habilitado_em": "2025-01-20",
        "cancelado_em": null,
        "id_contrato": 987
      }
    ]
  }]
}
```

### Sincronizacao no nosso lado

`HubsoftService.sincronizar_cliente(cpf_cnpj)` em [hubsoft.py](../../../../../dashboard_comercial/gerenciador_vendas/apps/integracoes/services/hubsoft.py).

Cria/atualiza `ClienteHubsoft` + lista `ServicoClienteHubsoft`. Detecta `houve_alteracao` comparando com snapshot anterior, gravando diff em `historico_alteracoes`.

### Sincronizar em massa

```bash
python manage.py sincronizar_clientes --todos
python manage.py sincronizar_clientes --lead-id 462
python manage.py sincronizar_clientes --tenant nuvyon
```

---

## Contrato — criar

`POST /api/v1/integracao/cliente/contrato/adicionar_contrato`

Cria contrato vinculado a um `id_cliente_servico` existente. Usado pelo handler `gerar_contrato_hubsoft` do engine de automacoes de pipeline (regra #19 da Nuvyon, ver [../../05-PIPELINE-HUBSOFT-NUVYON.md](../../05-PIPELINE-HUBSOFT-NUVYON.md)).

### Body

```json
{
  "id_cliente_servico": 57515,
  "id_contrato": 236,
  "id_empresa": 74,
  "autorizacao_nome": "Joao Silva",
  "autorizacao_cpf": "12345678900",
  "informacao_adicional": "Contrato gerado via Hubtrix."
}
```

Onde:
- `id_contrato` = ID do **modelo de contrato** (ver `configuracao/modelo_contrato`)
- `id_empresa` = ID da empresa contratante (ver `configuracao/empresa`)
- `autorizacao_cpf` = so digitos
- `informacao_adicional` = texto livre que aparece no contrato

### Resposta sucesso

```json
{ "status": "success", "contrato": { "id_contrato": 1010, "id_cliente_servico": 57515 } }
```

### Resposta "ja existe"

```json
{ "status": "error", "msg": "Ja existe contrato para o cliente servico informado." }
```

> **Borda nao tratada (2026-06-07):** quando o cliente ja tem contrato, o wrapper levanta `HubsoftServiceError`. Iteracao futura: detectar essa mensagem, consultar cliente, recuperar `id_contrato`, salvar em `ServicoClienteHubsoft.id_cliente_servico_contrato` e seguir pra anexar+aceitar.

### Service

`HubsoftService.criar_contrato(id_cliente_servico, id_contrato_modelo, id_empresa, autorizacao_nome, autorizacao_cpf, informacao_adicional, lead=None)`.

---

## Contrato — anexar arquivo

`POST /api/v1/integracao/cliente/contrato/adicionar_anexo_contrato/{id_contrato}`

Anexa arquivo (RG frente, RG verso, comprovante, PDF da conversa) ao contrato. Multipart.

### Form data

| Campo | Descricao |
|---|---|
| `arquivo` | Binario |
| `descricao` | Nome amigavel do anexo |

### Resposta

```json
{ "status": "success" }
```

### Service

`HubsoftService.anexar_arquivo_contrato(id_contrato, arquivo_bytes, nome, descricao)`.

Chamado dentro de `contrato_service.anexar_documentos_validados(lead)` que orquestra: validar imagens, baixar de `PrivateMidiaStorage`, gerar PDF da conversa via weasyprint, anexar tudo, chamar `aceitar_contrato`.

---

## Contrato — aceitar

`PUT /api/v1/integracao/cliente/contrato/aceitar_contrato`

Confirma aceite do contrato (apos anexar comprovantes). Necessario pra liberar instalacao.

### Body

```json
{ "id_contrato": 1010 }
```

### Resposta

```json
{ "status": "success" }
```

### Service

`HubsoftService.aceitar_contrato(id_contrato)`.

---

## Configuracao — modelos de contrato disponiveis

`GET /api/v1/integracao/configuracao/modelo_contrato`

Lista modelos cadastrados no HubSoft do tenant (`id_contrato_modelo` usado em `adicionar_contrato`).

### Resposta

```json
{
  "status": "success",
  "modelos_contrato": [
    { "id_contrato": 236, "descricao": "Contrato Residencial 24m" },
    { "id_contrato": 237, "descricao": "Contrato Empresarial 12m" }
  ]
}
```

### Service

`HubsoftService.listar_modelos_contrato()`.

---

## Configuracao — empresas

`GET /api/v1/integracao/configuracao/empresa`

Lista empresas (CNPJs) que o tenant opera (`id_empresa` usado em `adicionar_contrato`).

### Resposta

```json
{
  "status": "success",
  "empresas": [
    { "id_empresa": 74, "nome_fantasia": "Nuvyon Telecom", "cnpj": "..." }
  ]
}
```

---

## Fluxo end-to-end (lead -> cliente -> contrato anexado e aceito)

```
1. Lead chega (WhatsApp) -> LeadProspecto status_api=pendente
2. Signal -> POST /prospecto -> id_hubsoft salvo
3. Bot Selenium (web_driver_conversao_lead) converte prospecto em cliente
4. Cron sincronizar_clientes -> GET /cliente -> ClienteHubsoft + ServicoClienteHubsoft
5. Operador valida imagens (RG frente, RG verso, comprovante)
6. Todas imagens=documentos_validos -> engine pipeline avalia regra #19
7. Regra #19 dispara acao gerar_contrato_hubsoft:
   a. POST /contrato/adicionar_contrato -> id_contrato gerado
   b. Para cada imagem + PDF da conversa: POST /contrato/adicionar_anexo_contrato/{id}
   c. PUT /contrato/aceitar_contrato
8. Cliente liberado pra instalacao.
```
