---
name: "Fluxo Matrix ↔ Hubtrix — Guia de Configuração (Nuvyon)"
description: "Guia definitivo pra configurar o fluxo Matrix da Nuvyon consumindo APIs do Hubtrix multi-tenant. Adaptado do fluxo Megalink que hoje roda no sistema legado robovendas."
---

# Fluxo Matrix ↔ Hubtrix — Guia de Configuração (Nuvyon)

**Cliente:** Nuvyon
**Referência funcional:** fluxo Megalink em produção (`new_flow_comercial v7`) — **porém rodando no sistema legado `robovendas`**
**Destino da Nuvyon:** Hubtrix novo (multi-tenant)

---

## 0. Diferença crítica vs Megalink

A Megalink hoje roda num sistema antigo (`robovendas.megalinkpiaui.com.br`) que é single-tenant. O fluxo dela foi a **inspiração funcional**, mas os endpoints apontam pra uma stack diferente da que a Nuvyon vai usar.

A Nuvyon consome o **Hubtrix novo** (multi-tenant, mesmo código em `robo/dashboard_comercial/`). Bom e mau:
- ✅ Tenancy nativo via token Bearer (cada tenant tem seu próprio token)
- ✅ 6 dos 7 endpoints do fluxo Megalink já existem com payloads equivalentes
- ❌ `POST /api/leads/tags/` **não existe no Hubtrix** — precisa ser criado ou pulado
- ❌ Formato de autenticação é diferente: o fluxo Megalink não manda Bearer; no Hubtrix **todo endpoint exige**

---

## 1. Arquitetura

```
Consumidor (WhatsApp)
    │
    ▼
Matrix (front, bot, URAs, fluxo)
    │
    ├─── APIs Hubtrix (Bearer token)  → leads, imagens, histórico, HubSoft-status
    ├─── Aurora/N8N (sem auth ou token próprio)  → validação CEP, classificação resposta
    └─── APIs Matrix (auth própria do Matrix)  → agenda, atendimento, OS
```

O Matrix orquestra. Hubtrix é backend de dados + ponte com HubSoft. Aurora/N8N valida entradas do usuário.

---

## 2. Pré-requisitos no Hubtrix (fazer ANTES de ligar o fluxo)

### 2.1 Criar tenant Nuvyon
- Acessar `/aurora-admin/`
- Cadastrar tenant com módulos contratados (CRM, Marketing PRO, Clube)
- Registrar identidade visual (logo, cores)

### 2.2 Gerar token de API pro Matrix
- Criar `IntegracaoAPI` vinculado ao tenant Nuvyon
- Gerar `api_token` único
- Marcar `ativa=True`
- **Esse token vai no header `Authorization: Bearer <token>` de TODA chamada do Matrix**

### 2.3 Endpoint `/api/leads/tags/`

**Decisão: criar.** Endpoint vai ser implementado antes do go-live da Nuvyon. Tarefa no backlog: [api_leads_tags_21-04-2026.md](../../tarefas/backlog/api_leads_tags_21-04-2026.md).

---

## 3. Autenticação

**Toda chamada às APIs Hubtrix exige:**

```http
Authorization: Bearer <api_token_da_integracao_nuvyon>
```

O decorator `api_token_required` (em `apps/sistema/decorators.py`) faz 3 tentativas em ordem:
1. Busca token em `IntegracaoAPI` — se achar, injeta `request.tenant` automaticamente
2. Fallback: compara com env `N8N_API_TOKEN` (token global)
3. Fallback: compara com env `WEBHOOK_SECRET_TOKEN`

Pra Nuvyon, usar SEMPRE o token específico do tenant (caminho 1). **Não usar tokens globais** — eles ignoram isolamento de tenant.

### 3.1 Gap no fluxo Megalink

O fluxo Megalink atual **não envia header de autenticação em nenhum nó de API** — bate direto no `robovendas` que é aberto. Ao portar pro Matrix da Nuvyon, **todos os nós que chamam o Hubtrix precisam ganhar o header Bearer**.

### 3.2 Como adicionar o header no Matrix

No componente de API do Matrix (código 9 no JSON do fluxo), a estrutura de headers já existe:

```json
"headers": {
  "key": ["Authorization"],
  "value": ["Bearer {#api_token_nuvyon}"]
}
```

Criar uma variável global `api_token_nuvyon` no fluxo com o valor do token gerado na `IntegracaoAPI` (seção 2.2).

### 3.3 Nós que precisam ganhar o header Bearer

Lista completa dos nós de API no fluxo Megalink referência que batem no Hubtrix e portanto precisam do header:

| Identifier no fluxo | Endpoint chamado |
|---|---|
| `api_14` | `GET /api/consultar/leads/` |
| `api_8` | `POST /api/leads/registrar/` |
| `api_9`, `api_10`, `api_11`, `api_email_nas_ven`, `api_finaliza_lead` | `POST /api/leads/atualizar/` |
| `api_18`, `api_19`, `api_20` | `POST /api/leads/imagens/registrar/` |
| `api_26`, `api_27`, `api_28` | `POST /api/leads/tags/` *(só se endpoint for criado — seção 2.3)* |
| `api_2`, `api_7`, `api_13`, `api_17`, `api_fluxo_finalizado` | `POST /api/historicos/registrar/` |
| `api_21` (aparece em 2 lugares) | `GET /integracoes/api/lead/hubsoft-status/` |

**Nós que NÃO precisam** (não batem no Hubtrix, mantêm auth própria):
- `api_15`, `api_16` → N8N/Aurora (auth interna deles)
- `api_22`, `api_23`, `api_24`, `api_25` → Matrix API (auth interna do Matrix)

### 3.4 Alternativa: header global no fluxo

Se o Matrix permitir configurar header padrão no nível do fluxo (não nó a nó), isso reduz erro de configuração. Confirmar se o Matrix da Nuvyon suporta. Se não, fica nó a nó mesmo.

---

## 4. Sequência lógica do fluxo

### 4.1 Entrada
1. Saudação + coleta do nome
2. `GET /api/consultar/leads/` busca por telefone
3. Se não existe → `POST /api/leads/registrar/`
4. `POST /api/historicos/registrar/` com `status="fluxo_inicializado"`

### 4.2 Qualificação
5. URA casa ou empresa
   - Empresa → transbordo humano
   - Casa → URA oferta de plano

### 4.3 Venda automática
6. Coleta CEP → Aurora valida viabilidade
7. Confirma endereço
8. Coleta dados pessoais (número, ponto referência, nome, CPF, email, nasc.)
9. URA dia de vencimento
10. `POST /api/leads/atualizar/` com dados coletados
11. Confirmação resumo em URA
12. 3 imagens (selfie + doc frente + verso) → cada uma `POST /api/leads/imagens/registrar/`
13. `POST /api/leads/atualizar/` com `status_api="aguardando_assinatura"`
14. `POST /api/leads/tags/` tag "Assinado" *(depende da opção 2.3)*
15. `POST /api/leads/atualizar/` finaliza com `status_api="pendente"`

### 4.4 Pós-contratação (HubSoft)
16. Polling `GET /integracoes/api/lead/hubsoft-status/?lead_id=X`
    - Intervalo: 20s
    - Máximo: 90 tentativas (~30 min)
17. Avança quando `eh_cliente_hubsoft=true` E `documentacao_validada=true`
18. Se `total_doc_rejeitado > 0` → transborda

### 4.5 Instalação
19. URA turno (manhã/tarde)
20. `GET {matrix}/consultar_datas_sem_domingo`
21. URA escolha de data
22. `GET {matrix}/consultar_agenda` confirma vaga
23. `POST {matrix}/abrir_atendimento`
24. `POST {matrix}/abrir_os`
25. Mensagem de sucesso + finalização

---

## 5. Endpoints Hubtrix — especificação completa

Base: `https://app.hubtrix.com.br` (host único para todos os tenants)
Auth: `Authorization: Bearer <token_nuvyon>` em TODAS as chamadas abaixo. O token identifica o tenant automaticamente — não existe URL por cliente.

### 5.1 Consultar lead por telefone ✅

```http
GET /api/consultar/leads/?search={telefone}&origem=whatsapp&ativo=true&page=1
Authorization: Bearer {token}
```

Retorno (extrair): `results[0].id` → `{#result_get_leads}`

---

### 5.2 Registrar novo lead ✅

```http
POST /api/leads/registrar/
Authorization: Bearer {token}
Content-Type: application/json

{
  "nome_razaosocial": "{#CONTATO.NOME}",
  "telefone": "{#CONTATO.TELEFONE}",
  "origem": "whatsapp",
  "canal_entrada": "whatsapp",
  "tipo_entrada": "contato_whatsapp",
  "status_api": "processamento_manual",
  "id_vendedor_rp": <id_vendedor_nuvyon>,
  "id_origem": "<id_origem_nuvyon>",
  "id_origem_servico": "<id_origem_servico_nuvyon>"
}
```

**Campos obrigatórios:** `nome_razaosocial`, `telefone`.
**Retorno:** `{ "success": true, "id": <lead_id>, "lead": {...} }` → grava `id` em `{#id_lead}`.
**Multi-tenant:** o lead é criado automaticamente vinculado ao tenant do token.

---

### 5.3 Atualizar lead ✅

```http
POST /api/leads/atualizar/
Authorization: Bearer {token}
Content-Type: application/json

{
  "termo_busca": "id",
  "busca": {id_lead},
  "<campo1>": "<valor1>",
  "<campo2>": "<valor2>",
  ...
}
```

**Obrigatórios:** `termo_busca` + `busca` (identificam o lead).
**Importante:** só aceita campos que existem no modelo `LeadProspecto` — os demais são ignorados.

Campos atualizados ao longo do fluxo:
- Plano: `id_plano_rp`, `valor`
- Endereço: `bairro`, `cidade`, `rua`, `cep`, `estado`, `endereco`, `cpf_cnpj`
- Dados: `numero_residencia`, `nome_razaosocial`, `ponto_referencia`, `rg`, `email`, `data_nascimento`, `id_dia_vencimento`
- Finalização: `empresa`, `status_api`, `observacoes`

Valores de `status_api` usados:
- `"aguardando_assinatura"` — após imagens
- `"pendente"` — finalização

---

### 5.4 Registrar imagem ✅

```http
POST /api/leads/imagens/registrar/
Authorization: Bearer {token}
Content-Type: application/json

{
  "lead_id": {id_lead},
  "link_url": "<url_publica>",
  "descricao": "selfie_com_doc" | "frente_doc" | "verso_doc"
}
```

**Também aceita lote:**

```json
{
  "lead_id": 123,
  "imagens": [
    {"link_url": "...", "descricao": "selfie_com_doc"},
    {"link_url": "...", "descricao": "frente_doc"},
    {"link_url": "...", "descricao": "verso_doc"}
  ]
}
```

**URL da imagem:** o Matrix hospeda as imagens no próprio storage. Na Megalink é `matrixdobrasil.ai/public/imagens/uploads/msgs/YYYY/MM/<nome>`. Pra Nuvyon, **confirmar o domínio do Matrix deles** e montar o template.

---

### 5.5 Registrar histórico ✅

```http
POST /api/historicos/registrar/
Authorization: Bearer {token}
Content-Type: application/json

{
  "telefone": "{#CONTATO.TELEFONE}",
  "status": "fluxo_inicializado",
  "nome_contato": "{#CONTATO.NOME}",
  "origem_contato": "whatsapp",
  "observacoes": "<detalhes>",
  "lead_id": {id_lead},
  "numero_conta": "{#NOME_CONTA}",
  "protocolo_atendimento": "{#PROTOCOLO}",
  "id_conta": {#CODIGO_CONTA},
  "ultima_mensagem": "{#MENSAGEM}",
  "codigo_atendimento": "{#CODIGO_ATENDIMENTO}"
}
```

**Obrigatórios:** `telefone`, `status`.
Valores de `status` usados no fluxo Megalink:
- `fluxo_inicializado`
- `resposta`
- `transferido_humano`
- `fluxo_finalizado`

---

### 5.6 Status HubSoft ✅

```http
GET /integracoes/api/lead/hubsoft-status/?lead_id={id_lead}
Authorization: Bearer {token}
```

Retorna (extrair):
- `eh_cliente_hubsoft` (bool)
- `servicos[0].id_cliente_servico`
- `lead.nome_razaosocial`
- `lead.documentacao_validada` (bool)
- `cliente_hubsoft.lead.docs.rejeitados` (int)

Chamar a cada 20s, máximo 90 vezes (~30min). Se timeout sem `eh_cliente_hubsoft=true` → transborda.

---

### 5.7 Adicionar/remover tags ❌ (depende da opção 2.3)

**Se optarmos por criar (recomendado):**

```http
POST /api/leads/tags/
Authorization: Bearer {token}
Content-Type: application/json

{
  "lead_id": {id_lead},
  "tags_add": ["Comercial" | "Endereço" | "Assinado"],
  "tags_remove": []
}
```

Chamado em 3 pontos do fluxo.

**Se optarmos por pular:** remover os 3 nós de `api_26/27/28` e `api_finaliza_lead` do fluxo importado.

---

## 6. APIs auxiliares (não-Hubtrix)

### 6.1 Aurora / N8N

Autenticação: a Nuvyon pode reusar a instância Aurora da Megalink ou ter própria. Confirmar no kickoff.

**Validação de CEP + viabilidade:**

```http
POST {webhook_aurora}
Content-Type: application/json

{
  "question": "Você pode me passar o CEP do local?",
  "answer": "{cep_informado}",
  "cellphone": "{telefone}"
}
```

Retorna `answerIsCorrect`, `cep`, `bairro`, `localidade`, `uf`, `logradouro`, `needsReception`, `time`, `givesServiceToCity`.

**Classificação de resposta dinâmica:** mesmo endpoint com `question` variável. Retorna `answerIsCorrect`, `needsReception`, `hasCancelledService`, `isAClient`.

### 6.2 Matrix API (agenda, atendimento, OS)

Consumida pelo próprio fluxo Matrix. Auth cuidada pelo Matrix internamente — não depende do Hubtrix.

- `GET {matrix}/consultar_datas_sem_domingo?data_referencia=DD/MM/YYYY`
- `GET {matrix}/consultar_agenda?cidade=X&data_referencia=Y&turno=manha&qtd_vagas=1`
- `POST {matrix}/abrir_atendimento` (payload: id_cliente_servico, id_tipo_atendimento_instalacao, etc.)
- `POST {matrix}/abrir_os` (payload: id_atendimento, id_tipo_os, id_agenda_os, etc.)

---

## 7. Variáveis a parametrizar no fluxo Nuvyon

### 7.1 Hubtrix
| Variável | Valor |
|---|---|
| `url_api` | `https://app.hubtrix.com.br` (fixo pra todos os tenants) |
| `api_token_nuvyon` | Token Bearer gerado na seção 2.2 |
| `id_vendedor_rp` | ID de vendedor padrão no Hubtrix/RP da Nuvyon |
| `id_origem` | Código de origem "whatsapp" |
| `id_origem_servico` | Código de serviço de origem |
| `nome_empresa_api` | Slug da empresa (ex: `nuvyon`) |

### 7.2 Matrix
| Variável | Valor |
|---|---|
| `url_api_matrix` | URL base da Matrix API da Nuvyon |
| `id_tipo_atendimento_instalacao` | ID "Instalação" no Matrix deles |
| `id_status_atendimento` | ID status inicial |
| `id_user_responsavel` | Usuário responsável padrão |
| `id_tipo_os` | ID tipo OS "Instalação" |
| `status_os_api` | Status inicial (`pendente`) |
| `duracao` | Duração OS (`01:30:00`) |

### 7.3 Aurora
| Variável | Valor |
|---|---|
| `webhook_aurora` | URL do Aurora/N8N pra validação |

### 7.4 Planos
Pra cada plano ofertado:
- `id_plano_prospecto` (ID no Hubtrix/RP)
- `valor_plano_prospecto`
- `prospecto_titulo_plano`

### 7.5 Vencimentos
Mapeamento dia → id no HubSoft da Nuvyon. **IDs variam por tenant**, pedir no kickoff.

### 7.6 Mensagens da marca
Textos do fluxo pra adaptar:
- Saudação
- Descrições de plano
- Mensagens de confirmação e sucesso
- Link alternativo de contratação (se existir)

### 7.7 Nome da empresa
- `nome_empresa` (aparece pro cliente: "Nuvyon Internet")
- `nome_empresa_api` (slug nas APIs: `nuvyon`)

---

## 8. Pontos de atenção

### 8.1 Storage de imagens
Matrix hospeda imagens em domínio próprio — o cliente controla a infraestrutura Matrix. Pedir pra Nuvyon informar o domínio e ajustar template da URL (coletado no [checklist_fluxo_atendimento.md](checklist_fluxo_atendimento.md) item 5).

### 8.2 Polling HubSoft
30min é teto. Se HubSoft da Nuvyon demorar mais, considerar aumentar ou migrar pra webhook push (HubSoft → Hubtrix → Matrix).

### 8.3 Transbordo
Pontos de transbordo pra humano:
- Escolha "falar com consultor"
- Aurora `needsReception=true`
- Doc HubSoft rejeitado
- Timeout polling HubSoft
- Inatividade > `tempo_de_inatividade`
- Planos específicos (ex: Megalink Energia — remover no fluxo Nuvyon)

Confirmar filas/serviços de transbordo no Matrix da Nuvyon.

### 8.4 Horário de atendimento
Componente `hor_1` com schedule específico. Confirmar horário comercial Nuvyon.

### 8.5 Validação de documentos
Precisa estar habilitada no HubSoft da Nuvyon. Se não tiver, definir fallback (validação manual via humano).

### 8.6 Multi-tenancy no Hubtrix
Cada chamada com token Nuvyon cria/atualiza dados **somente no tenant Nuvyon**. Impossível vazar dado entre tenants — o middleware filtra automaticamente. Mas **nunca usar tokens globais** (N8N_API_TOKEN, WEBHOOK_SECRET_TOKEN) no fluxo da Nuvyon.

---

## 9. Checklist de go-live

Ordem de execução sugerida:

- [ ] Tenant Nuvyon criado no aurora-admin (com módulos contratados)
- [ ] `IntegracaoAPI` criada e token gerado
- [ ] Decisão sobre `/api/leads/tags/` (criar ou pular)
- [ ] URLs Aurora/N8N e Matrix API da Nuvyon coletadas
- [ ] Variáveis da seção 7 preenchidas
- [ ] Fluxo Megalink clonado e editado no Matrix da Nuvyon
- [ ] Testes em homologação:
  - [ ] Criar lead via telefone novo
  - [ ] Passar por todas as URAs
  - [ ] Confirmar Hubtrix recebeu lead (checar em `/leads/` filtrado pelo tenant)
  - [ ] Confirmar imagens registradas
  - [ ] Confirmar polling HubSoft
  - [ ] Confirmar abertura de atendimento + OS no Matrix
- [ ] Dry run com equipe interna (funcionário da Nuvyon fazendo papel de cliente)
- [ ] Go-live com monitoramento nas primeiras 48h

---

## 10. Referências

- Fluxo Megalink referência: `new_flow_comercial v7` (JSON exportado)
- Checklist de onboarding Nuvyon: [checklist_onboarding.md](checklist_onboarding.md)
- Decorator de auth: `apps/sistema/decorators.py` (`api_token_required`)
- Endpoints Hubtrix: `apps/comercial/leads/views.py` + `apps/comercial/leads/urls.py`
- Status HubSoft: `apps/integracoes/urls.py` + `apps/integracoes/views.py`
