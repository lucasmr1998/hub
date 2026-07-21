# Contrato pros fluxos: checagem de CPF e consulta de viabilidade

Contexto pra quem constroi fluxo no N8N/Matrix. Levantado em 21/07/2026 lendo o
codigo e conferindo os dados em prod.

> **ANTES DE USAR:** a checagem de CPF tem um bug ativo que derruba a resposta
> exatamente no caso "ja e cliente". Ver a secao [Bug ativo](#bug-ativo-eh_cliente-quebra-em-500).

---

## 1. "Esse CPF ja e cliente?"

### Chamada

```
GET https://app.hubtrix.com.br/api/leads/consultar-cpf/?cpf=12345678900
Authorization: Bearer <IntegracaoAPI.api_token do tenant>
```

- **So GET.** Outro metodo devolve `405 {"error": "Use GET"}`.
- View: `apps/comercial/leads/views.py:536` (`consultar_cpf_api`), rota em
  `apps/comercial/leads/urls.py:26`.
- O parametro aceita `cpf` ou `cpf_cnpj`, com ou sem pontuacao (a view tira tudo
  que nao e digito). Precisa de 11+ digitos. Nao valida digito verificador, e
  CNPJ (14 digitos) passa.

### Autenticacao, e o detalhe que derruba fluxo novo

O decorator e `api_token_required` (`apps/sistema/decorators.py:38`). Ele aceita
tres tokens, mas **so um serve aqui**:

| Token | Resolve tenant? | Serve? |
|---|---|---|
| `IntegracaoAPI.api_token` (por tenant) | Sim | **Use este** |
| env `N8N_API_TOKEN` (global) | Nao | Nao. Cai em `400 Tenant nao identificado` |
| env `WEBHOOK_SECRET_TOKEN` (global) | Nao | Nao. Mesmo erro |

O tenant sai **do token**, nao de subdominio nem header. Sem o token por tenant
a view autentica e falha logo depois.

### Resposta

```json
{
  "eh_cliente": false,
  "tem_lead_ativo": false,
  "lead_id": null,
  "oportunidade_id": null,
  "estagio_lead": null,
  "cliente_hubsoft_id": null,
  "nome": null,
  "deve_abrir_cartao": true,
  "mensagem": "CPF novo — pode abrir cartao no CRM normalmente."
}
```

- `eh_cliente` — existe `ClienteHubsoft` com esse CPF no tenant.
- `tem_lead_ativo` — existe `LeadProspecto` com `ativo=True` e esse CPF.
- **`deve_abrir_cartao` = `not (eh_cliente or tem_lead_ativo)`.** E o campo que o
  fluxo deve ler. `false` significa mandar pro SAC em vez de seguir o comercial.
- `estagio_lead` — nome do estagio no pipeline, quando ha oportunidade.

### De onde vem o dado

**So do banco local.** A view le a tabela espelho `ClienteHubsoft` e a
`LeadProspecto`. **Nunca chama a API do HubSoft ao vivo.**

Consequencia: cliente que ainda nao foi sincronizado aparece como "CPF novo". O
espelho e populado pelo cron `sincronizar_clientes`, que hoje so processa lead
com `status_api='processado'` — hoje sao 754 leads da Nuvyon presos em
`rascunho_hubsoft` que nunca entram nessa fila.

### Erros

| Situacao | Status | Corpo |
|---|---|---|
| Metodo != GET | 405 | `{"error": "Use GET"}` |
| Sem header `Authorization: Bearer` | 401 | `{"error": "Token obrigatorio"}` |
| Token desconhecido | 401 | `{"error": "Token invalido"}` |
| CPF vazio ou com menos de 11 digitos | 400 | `{"error": "CPF invalido (esperado 11+ digitos)"}` |
| Token global, sem tenant | 400 | `{"error": "Tenant nao identificado"}` |
| Tenant sem integracao HubSoft | 200 | responde normal, lendo so o espelho local |

Nao ha try/except na view: qualquer excecao vira **500 com HTML**, nao JSON.

### Bug ativo: `eh_cliente` quebra em 500

A view acessa `cliente.id_cliente_hubsoft` em `views.py:579` e `:592`, mas o
model `ClienteHubsoft` chama esse campo de **`id_cliente`**
(`apps/integracoes/models.py:389`). Nao existe property com o nome antigo.

Efeito: **quando o CPF E de um cliente, a view levanta `AttributeError` e
devolve 500.** Ou seja, hoje ela nunca consegue responder `eh_cliente: true`. O
mesmo acesso quebrado esta em `views.py:650` e `:656`, dentro do
`registrar_lead_api`.

**Enquanto nao for corrigido:** o fluxo NAO pode tratar 500 como "pode abrir
cartao". Trate como indeterminado e nao abra cartao as cegas, senao vai abrir
cartao comercial pra quem ja e cliente.

### Sobre a normalizacao do CPF (conferido em prod, nao e o que parecia)

Ha um risco teorico de o filtro comparar CPF so-digitos contra dado gravado com
pontuacao. **Conferido nos dados de prod da Nuvyon em 21/07:**

| Tabela | So numeros | Com pontuacao | Vazio |
|---|---|---|---|
| `clientes_hubsoft` | 1219 | **0** | 0 |
| `leads_prospectos` | 517 | **28** | 598 |

Ou seja: pro lado do **cliente o risco nao se materializa** (todos os 1219 estao
so com numeros). Pro lado do **lead ha 28 registros pontuados** que o
`tem_lead_ativo` nao acha. E pequeno, mas existe.

O que merece mais atencao e o campo vazio: **598 leads sem CPF nenhum**, que
nunca vao casar por esse caminho.

---

## 2. Consulta de viabilidade

Aqui a coisa e menos direta: **nao existe endpoint com Bearer token que consulte
a viabilidade do HubSoft ao vivo.** Sao caminhos diferentes com coberturas
diferentes.

### Caminho A, o unico feito pra N8N (mas so consulta cidade local)

```
POST https://app.hubtrix.com.br/api/public/n8n/viabilidade/
X-N8N-Webhook-Secret: <env N8N_WEBHOOK_SECRET>
Content-Type: application/json

{"tenant_slug": "nuvyon", "cidade": "Mococa", "estado": "SP", "cep": "13730-000"}
```

- View: `apps/integracoes/views_n8n_webhook.py:404` (`viabilidade_check`).
- **Auth por header proprio, nao Bearer.** Se `N8N_WEBHOOK_SECRET` nao estiver
  setada no ambiente, rejeita tudo com 401.
- **So consulta a tabela local `CidadeViabilidade`.** Nao chama HubSoft, nao
  chama ViaCEP.
- Obrigatorios: `tenant_slug` e `cidade`.

Resposta:

```json
{"sucesso": true, "tenant": "nuvyon", "atendido": true,
 "cidade_match": "Mococa", "estado": "SP", "cep_match": true}
```

Quando `atendido: false`, vem junto `cidades_atendidas` com ate 50 cidades.
Repare que aqui a chave e **`atendido` (bool)**, vocabulario diferente do
`status` usado no resto do sistema.

Erros: `400` sem tenant_slug/cidade ou JSON invalido, `401` secret errado,
`404` tenant inexistente.

### Caminho B, consulta real no HubSoft, via engine de automacao

```
POST https://app.hubtrix.com.br/automacao/webhook/<webhook_token>/
Content-Type: application/json

{ ...qualquer JSON, vira {{var.payload}} no fluxo... }
```

O fluxo precisa ter um dos nos:

| No | tipo | Campos obrigatorios |
|---|---|---|
| Viabilidade por endereco | `hubsoft_viabilidade_endereco` | `endereco`, `numero`, `bairro`, `cidade`, `estado` |
| Viabilidade por coordenadas | `hubsoft_viabilidade_coords` | `latitude`, `longitude` |

Opcionais nos dois: `raio` (default 250), `detalhar_portas`, `integracao_id`.

- Auth e o proprio `webhook_token` na URL, sem header.
- Limites: 256 KB de body (413), 60 req por 60s por token (429).
- Saidas do no: `sucesso` / `erro`. Output em `{"viabilidade": <resposta crua>}`.
- **O no NAO persiste nada no lead.** So devolve o resultado.
- Resposta padrao do webhook: `{"execucao_id": ..., "status": ...}`. Pra receber
  o resultado, use `ultimo_no` ou um no "Responder ao Webhook".

**O HubSoft nao recebe CEP nessa consulta.** O payload e endereco estruturado ou
lat/lng. O CEP so serve, do lado do Hubtrix, pra descobrir cidade/UF no ViaCEP.

### Caminho C, o CRM (sessao logada, nao serve pra fluxo)

`PUT /crm/oportunidades/<pk>/editar/` dispara a consulta completa e **persiste**
no lead, mas exige sessao Django (`@login_required`). So dispara quando algum
campo de endereco muda: `cep`, `rua`, `numero_residencia`, `bairro`, `cidade`,
`estado`.

### Status possiveis

Definidos em `apps/comercial/viabilidade/services.py`, como strings literais
(nao sao choices de model):

| Status | Significado |
|---|---|
| `cobertura_ok` | atende |
| `fora_cobertura` | nao atende |
| `pendente_revisao` | HubSoft negou mas a cidade esta na whitelist do tenant, **ou** a resposta nao foi reconhecida. **Exige validacao humana. O lead NAO deve ir pra Perdido** |
| `endereco_incompleto` | falta cidade/UF pra consultar |
| `nao_consultado` | tenant sem nenhuma fonte de viabilidade |
| `erro` | CEP invalido ou falha do HubSoft |

A regra de decisao do HubSoft: **atende se houver ao menos uma caixa optica com
`disponiveis > 0`**.

Decisao de projeto importante: resposta nao reconhecida vira `pendente_revisao`,
nunca `fora_cobertura`, pra nao matar lead calado.

### Onde o resultado fica gravado

Campo **`LeadProspecto.dados_custom['viabilidade']`** (no lead, nao na
oportunidade):

```json
{
  "status": "cobertura_ok",
  "cep_consultado": "13730-000",
  "cidade": "Mococa",
  "uf": "SP",
  "fonte": "hubsoft",
  "detalhes": {"origem": "mapeamento_local", "projetos": 2,
               "caixas_com_portas_livres": 1, "portas_disponiveis": 4,
               "caixa_mais_proxima": "CTO-12"},
  "consultado_em": "2026-07-21T12:34:56.789012+00:00",
  "auto_preenchido": {"logradouro": "...", "bairro": "...", "cidade": "...", "uf": "..."}
}
```

Quando um humano valida pela automacao, entram tres subcampos a mais:
`origem_status` (hoje so o valor `validacao_humana`), `validado_em` e
`status_anterior`. Gravados por `apps/automacao/propriedades_oportunidade.py:152`.

### Cache e timeout

- **Nao ha cache, dedupe nem TTL** na consulta de viabilidade. Cada chamada bate
  na API.
- O unico gating existente e no CRM: so consulta se o endereco realmente mudou.
- Timeout do HubSoft: 30s por tentativa, ate 3 tentativas com backoff
  (1,5s e 3s). **Pior caso ~94s.** Dimensione o timeout do fluxo com folga.
- O que e cacheado e so o token OAuth do HubSoft.

---

## 3. Resumo pra quem monta o fluxo

1. **CPF:** `GET /api/leads/consultar-cpf/?cpf=<numeros>` com Bearer do token
   **por tenant**. Decida por `deve_abrir_cartao`. Trate 400/401/500 como
   indeterminado.
2. **Nao confie em `eh_cliente: true` ainda** — hoje esse ramo devolve 500.
3. **Viabilidade por cidade (rapido, local):** `POST /api/public/n8n/viabilidade/`
   com `X-N8N-Webhook-Secret`. Responde `atendido: bool`.
4. **Viabilidade real no HubSoft:** unico caminho pra fluxo e o webhook da engine
   de automacao com os nos `hubsoft_viabilidade_*`. Precisa de endereco
   estruturado, nao CEP. Pode levar ate ~94s no pior caso.
5. **`pendente_revisao` nao e "nao atende".** Manda pra fila humana.
