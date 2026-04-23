# Guia — Integrar um novo ERP ao Hubtrix

> **Quando usar este documento:** novo provedor entrou e usa um ERP diferente dos que ja suportamos (HubSoft). Este guia eh o **manual de desenvolvedor** pra planejar e executar a integracao, usando o HubSoft como referencia concreta.

**Pre-requisitos:** ler [01-HUBSOFT.md](01-HUBSOFT.md) (caso concreto em producao) e [02-INTEGRACOES.md](02-INTEGRACOES.md) (mapa dos 35 pontos de integracao).

---

## 1. O que o Hubtrix precisa do ERP

O Hubtrix nao eh um ERP. Ele depende de um ERP de provedor ISP pra duas coisas: **ler** (consumir dados de cliente/contrato/financeiro) e **escrever** (devolver leads/prospectos/documentos). Sem ERP integrado, modulos **Comercial, Cadastro, CS/Clube e Marketing** ficam parcialmente operantes.

### 1.1 Matriz de necessidade por modulo

| Modulo | Precisa de ERP? | Operacoes |
|---|---|---|
| Atendimento (engine) | ❌ Opcional | Fluxos rodam sem ERP |
| Inbox | ❌ Nao | Plataforma de atendimento (Matrix/Uazapi/Evolution), nao ERP |
| Comercial — Leads | ⚠ Parcial | Lead existe sem ERP, mas vira prospecto no ERP quando qualifica |
| Comercial — Cadastro publico | ✅ Obrigatorio | Cria prospecto + anexa docs + aceita contrato |
| Comercial — CRM | ❌ Nao direto | Usa dados sincronizados via `ClienteHubsoft` |
| CS — Clube | ✅ Obrigatorio | Pontuacao automatica precisa consultar pagamento/recorrencia/app |
| CS — Carteirinha | ⚠ Parcial | Dados basicos do cliente via ERP |
| Marketing — Automacoes | ⚠ Parcial | Condicoes tipo `cliente.plano` dependem de dados sincronizados |
| Suporte | ❌ Nao | Independente do ERP |
| Assistente CRM | ⚠ Parcial | Melhora quando tem dados do ERP |

### 1.2 Operacoes que o ERP precisa expor

Interface minima abstrata — qualquer ERP novo (Gigamax ou outro) precisa suportar:

```
# Leitura
GET  /clientes?cpf={cpf}              → {id, nome, email, telefone, endereco, cidade, status}
GET  /clientes/{id}/contratos         → [{id, plano, status, data_inicio, data_fim, valor}]
GET  /clientes/{id}/financeiro        → {inadimplente, recorrencia, adiantado}
GET  /planos                          → [{id, nome, velocidade_down, velocidade_up, valor}]

# Escrita
POST /prospectos                      → Criar prospecto com dados do lead
POST /prospectos/{id}/documentos      → Enviar documentos (base64 ou URL)
POST /prospectos/{id}/contrato/aceitar → Aceite de contrato
```

Se o ERP **nao expoe** alguma dessas operacoes via API, ha alternativas (ver secao 3).

---

## 2. Arquitetura de integracao (visao geral)

```
┌──────────────────────────────────────────────────────────────┐
│ Hubtrix                                                      │
│                                                              │
│  ┌──────────────┐    credenciais    ┌─────────────────────┐ │
│  │ IntegracaoAPI│◄──────────────────│ Admin UI /          │ │
│  │ (tenant)     │                   │ setup_<erp> command │ │
│  └──────┬───────┘                   └─────────────────────┘ │
│         │                                                    │
│         │ injetada em                                        │
│         ▼                                                    │
│  ┌──────────────────┐    chama     ┌──────────────────────┐ │
│  │ <Erp>Service     │─────────────►│ API do ERP externo   │ │
│  │ (adapter)        │◄─────────────│ (REST / banco / N8N) │ │
│  └──────┬───────────┘              └──────────────────────┘ │
│         │                                                    │
│         │ escreve/espelha                                    │
│         ▼                                                    │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ ClienteHubsoft   │  │ LogIntegracao    │                 │
│  │ ServicoHubsoft   │  │ (audit trail)    │                 │
│  │ (espelho local)  │  │                  │                 │
│  └──────────────────┘  └──────────────────┘                 │
│                                                              │
│  ┌──────────────────┐                                        │
│  │ signals.py       │ trigger automatico (lead salvo, etc)  │
│  └──────────────────┘                                        │
└──────────────────────────────────────────────────────────────┘
```

### 2.1 Pecas fixas

| Peca | Papel | Localizacao |
|---|---|---|
| `IntegracaoAPI` | Model multi-tenant com credenciais (OAuth, API key, etc) + URL base + cache de token | `apps/integracoes/models.py` |
| `LogIntegracao` | Registro de toda chamada (endpoint, payload, response, status, tempo_ms) | idem |
| `<Erp>Service` | Adapter — classe que encapsula as chamadas e mapeia para domino Hubtrix | `apps/integracoes/services/<erp>.py` |
| `signals.py` | Triggers automaticos (lead salvo → cadastra prospecto, doc validado → anexa contrato) | `apps/integracoes/signals.py` |
| Management commands | Operacoes manuais/cron (setup, sincronizar em massa, processar pendentes, retry) | `apps/integracoes/management/commands/` |

### 2.2 Pecas variaveis (mudam por ERP)

| Peca | O que muda |
|---|---|
| Tipo em `IntegracaoAPI.TIPO_CHOICES` | Adicionar `('gigamax', 'Gigamax')` |
| Adapter `<Erp>Service` | Metodos nao mudam de nome (obter_token, cadastrar_prospecto, consultar_cliente, sincronizar_cliente), implementacao muda |
| Models de espelho | Talvez reaproveite `ClienteHubsoft` (renomear pra `ClienteERPExterno` no futuro), ou cria especifico se dados sao muito diferentes |
| Command de setup | `setup_<erp>` pergunta credenciais especificas |

---

## 3. Os 4 padroes de integracao

Dependendo do que o ERP expoe, usamos um ou mais destes padroes:

### 3.1 API REST direta (preferencial)

HubSoft usa OAuth2 password grant. Adapter chama com `requests`, cacheia token em `IntegracaoAPI.access_token`, renova quando expira. Todo log vai pra `LogIntegracao`.

**Quando usar:** ERP tem API REST documentada com endpoints suficientes.

**Exemplo:** ver `apps/integracoes/services/hubsoft.py::HubsoftService.cadastrar_prospecto()`.

### 3.2 Banco direto (psycopg2)

HubSoft faz quando API nao expoe (dados de pagamento, recorrencia, app instalado). Conexao read-only via usuario `mega_leitura`. Funciona porque HubSoft eh PostgreSQL self-hosted.

**Quando usar (ultima opcao):**
- Dado essencial nao esta na API
- Provedor autoriza acesso de leitura no DB
- DB nao vai ser virtualizado/migrado em breve

**Riscos:**
- Depende de IP do servidor ERP estar acessivel ao Hubtrix
- Schema interno do ERP pode mudar sem aviso
- Nao funciona se o ERP for SaaS fechado

### 3.3 Via N8N (intermediado)

Hubtrix chama webhook N8N; N8N faz a chamada efetiva no ERP. Uma camada de indirecao.

**Quando usar:**
- Cliente ja tem N8N rodando pra orquestrar fluxos
- Chamada precisa de transformacao complexa (ex: juntar 3 APIs pra montar resposta)
- Queremos deixar o cliente donar a logica de integracao

**Exemplo:** Clube consulta cliente via `POST /webhook/roletaconsultarcliente` no N8N do cliente.

### 3.4 Webhook reverso (ERP → Hubtrix)

ERP chama o Hubtrix quando algo acontece do lado dele (contrato aprovado, pagamento confirmado, cancelamento). Usa endpoints do Hubtrix protegidos por `api_token`.

**Quando usar:**
- Hubtrix precisa reagir a eventos do ERP (nao so consumir sob demanda)
- ERP tem feature de webhook (HubSoft hoje nao tem — limitante conhecido)

**Exemplo:** `/api/v1/venda/aprovar/` eh chamado pelo N8N quando HubSoft aprova venda.

### 3.5 Arvore de decisao

```
ERP expoe o dado que preciso via API REST?
├─ Sim  →  3.1 API direta
└─ Nao  →  ERP permite acesso ao banco (self-hosted)?
           ├─ Sim  →  3.2 Banco direto (so pra leitura critica)
           └─ Nao  →  Tem N8N disponivel e cliente quer manter logica la?
                     ├─ Sim  →  3.3 N8N intermediado
                     └─ Nao  →  Pedir ao ERP pra implementar / solucao manual
```

---

## 4. Contrato minimo do adapter

Qualquer `<Erp>Service` novo deve implementar **no minimo** estas operacoes pra cobrir Comercial e Cadastro. Ver `hubsoft.py` como referencia.

```python
class GigamaxService:
    def __init__(self, integracao: IntegracaoAPI):
        if integracao.tipo != 'gigamax':
            raise GigamaxServiceError(...)
        self.integracao = integracao

    # --- Autenticacao ---
    def obter_token(self) -> str:
        """Retorna token valido (renova se preciso, cacheia em IntegracaoAPI)."""

    # --- Escrita (lead -> ERP) ---
    def cadastrar_prospecto(self, lead) -> dict:
        """POST prospecto. Retorna {id_prospecto, ...}.
        Atualiza lead.id_<erp>, lead.status_api."""

    # --- Leitura (ERP -> Hubtrix) ---
    def consultar_cliente(self, cpf_cnpj: str, lead=None) -> dict:
        """GET cliente por CPF/CNPJ. Retorna dados brutos do ERP."""

    def sincronizar_cliente(self, lead) -> ClienteERPExterno | None:
        """Consulta + upsert em ClienteERPExterno + ServicoClienteERPExterno."""

    # --- Privados ---
    def _registrar_log(self, *, endpoint, metodo, payload, resposta, status_code, sucesso, tempo_ms, erro=''):
        """Grava LogIntegracao. Obrigatorio em toda chamada externa."""
```

**Opcional (se modulos adicionais ativos):**

```python
# Cadastro publico (anexar docs + aceitar contrato)
def anexar_documento_contrato(self, contrato_id: str, arquivo_base64: str) -> dict:
def aceitar_contrato(self, contrato_id: str) -> dict:

# CS / Clube
def checar_pontos_extras_cpf(self, cpf: str) -> dict:
def consultar_cidade_cliente_cpf(self, cpf: str) -> str | None:
```

---

## 5. Passo-a-passo pra integrar novo ERP

### Passo 1 — Discovery (meio dia)

- [ ] Conversar com equipe tecnica do ERP
- [ ] Obter **documentacao da API** (Postman collection, Swagger, PDF)
- [ ] Confirmar metodo de auth (OAuth2 / API Key / Bearer / Basic)
- [ ] Mapear **os 7 endpoints minimos** (secao 1.2) — ver o que existe, o que falta
- [ ] Decidir padroes por operacao (arvore 3.5)

Saida: documento em `docs/PRODUTO/integracoes/<erp>.md` com mapa concreto.

### Passo 2 — Setup (1h)

- [ ] Adicionar `('gigamax', 'Gigamax')` em `IntegracaoAPI.TIPO_CHOICES`
- [ ] Migration: `makemigrations integracoes`
- [ ] Criar `apps/integracoes/management/commands/setup_gigamax.py` (copia `setup_hubsoft.py`, ajusta campos)

### Passo 3 — Adapter (2-3 dias)

- [ ] Criar `apps/integracoes/services/gigamax.py` com esqueleto do `GigamaxService`
- [ ] Implementar `obter_token` primeiro (auth eh base de tudo)
- [ ] Implementar `cadastrar_prospecto`
- [ ] Implementar `consultar_cliente`
- [ ] Implementar `sincronizar_cliente` (incluindo servicos/planos)
- [ ] Garantir que **toda chamada passa por `_registrar_log`** — sem isso, debug futuro eh cego

### Passo 4 — Integracao com signals existentes (meio dia)

- [ ] Em `apps/integracoes/signals.py`, branch por `tipo`:
  ```python
  if integracao.tipo == 'hubsoft':
      service = HubsoftService(integracao)
  elif integracao.tipo == 'gigamax':
      service = GigamaxService(integracao)
  service.cadastrar_prospecto(lead)
  ```
- [ ] Evitar factory se for apenas 2 adaptadores. Se virar 4+, abstrair via `get_service_for_integracao()`

### Passo 5 — Testes (1 dia)

- [ ] Testes unitarios da classe `GigamaxService` com `requests_mock`
- [ ] Teste de integracao end-to-end (cria lead → signal → cadastrar_prospecto → verifica log)
- [ ] Teste de auth expirado (renova automaticamente)
- [ ] Teste de erro de rede (grava log com status_code=0)

### Passo 6 — Homologacao em ambiente do cliente (1-2 dias)

- [ ] Config ambiente teste/sandbox do ERP
- [ ] Rodar `setup_gigamax` com credenciais reais
- [ ] Enviar lead de teste: `python manage.py processar_pendentes --lead-id X --dry-run`
- [ ] Conferir resultado no ERP
- [ ] Ajustar mapeamentos (IDs de origem, vendedor padrao, plano) ate bater 100%

### Passo 7 — Go-live

- [ ] Migrar para credenciais de producao
- [ ] Monitorar `LogIntegracao` por 48h
- [ ] Documentar IDs especificos do cliente em `clientes/<tenant>/integracoes.md`

---

## 6. Pontos ja integrados hoje (referencia HubSoft)

Resumo dos 13 pontos de integracao com ERP que ja funcionam com HubSoft. Serve de **benchmark** — uma nova integracao provavelmente precisa cobrir o mesmo conjunto.

| # | Operacao | Metodo usado | Criticidade | Doc |
|---|---|---|---|---|
| 1 | Obter token OAuth | API REST POST | Alta | [01-HUBSOFT.md §2](01-HUBSOFT.md) |
| 2 | Cadastrar prospecto | API REST POST | Alta | idem |
| 3 | Consultar cliente por CPF | API REST GET | Alta | idem |
| 4 | Sincronizar cliente (upsert local) | API REST GET | Alta | idem |
| 5 | Sincronizar servicos/planos | Dentro de #4 | Alta | idem |
| 6 | Consultar cliente (Clube) | Webhook N8N | Media | idem |
| 7 | Checar pontos extras (recorrencia/adiantado/app) | Banco direto | Media | idem |
| 8 | Consultar cidade do cliente | Banco direto | Baixa | idem |
| 9 | Listar clientes por cidade | Banco direto | Baixa | idem |
| 10 | Buscar contrato | API REST GET | Alta | idem |
| 11 | Criar contrato | API REST POST | Alta | idem |
| 12 | Atualizar contrato | API REST PUT | Alta | idem |
| 13 | Download contrato PDF | API REST GET | Media | idem |

**Pontos onde HubSoft forcou banco direto (#7, #8, #9)** sao os mais fragies e dependem de acesso IP + schema. Se o Gigamax nao tiver o equivalente em API, vale pressionar por endpoint oficial.

---

## 7. Checklist de entrega (considerado "feito")

- [ ] `TIPO_CHOICES` atualizado e migration aplicada
- [ ] `<Erp>Service` implementado com os 4 metodos minimos
- [ ] Toda chamada externa grava `LogIntegracao`
- [ ] Token cacheado e renovado automaticamente
- [ ] `setup_<erp>` management command criado
- [ ] Signals `post_save` em `LeadProspecto` e `ImagemLeadProspecto` cobrindo o novo tipo
- [ ] Testes unitarios + integracao (mockados) passando
- [ ] Lead de teste enviado em homologacao do ERP com sucesso
- [ ] Doc `docs/PRODUTO/integracoes/<erp>.md` criada (mesmo formato que [01-HUBSOFT.md](01-HUBSOFT.md))
- [ ] IDs especificos do cliente registrados em `docs/context/clientes/<tenant>/integracoes.md`
- [ ] `python manage.py check` limpo
- [ ] Monitorar `LogIntegracao` em prod por 48h

---

## 8. Armadilhas conhecidas

| Armadilha | Sintoma | Prevencao |
|---|---|---|
| ERP retorna `200 OK` com `erro` no body | `LogIntegracao.sucesso=True` mas dado nao foi salvo | Validar **shape** da resposta alem do status_code — nao assumir que 200 = ok |
| Token OAuth expira antes da expiracao declarada | Chamadas falham com 401 perto do limite | Renovar com 5min de folga antes do `expires_in` |
| Mapeamento de IDs do cliente diferente entre ambientes | Homologacao funciona, producao quebra | Sempre usar `IntegracaoAPI.configuracoes_extras` (JSONField) pra IDs custom (id_origem, id_vendedor, id_servico_padrao) — nunca hardcoded |
| Schema do banco do ERP muda sem aviso (quando via banco direto) | Query quebra em producao sem mudanca no codigo | Acompanhar release notes do ERP; ter monitoramento de queries que retornam 0 linhas onde deveria retornar >0 |
| Sem log em erro de rede (timeout) | Ninguem sabe que chamada aconteceu | `_registrar_log` com `status_code=0` mesmo em `RequestException` — HubSoft ja faz assim |
| Signal dispara em lote (import, seed) | ERP recebe milhares de chamadas em segundos | `_skip_automacao=True` ou `signal.disconnect()` temporario em operacoes em massa |
| Credencial trocada no ERP | Hubtrix para de funcionar sem aviso | Alarme externo que checa `LogIntegracao.filter(status_code=401, data__gt=now-10min)` — escalar se > N |

---

## 9. Relacionados

- [01-HUBSOFT.md](01-HUBSOFT.md) — Implementacao atual (referencia concreta)
- [02-INTEGRACOES.md](02-INTEGRACOES.md) — Mapa dos 35 pontos de integracao total (ERP + atendimento + N8N + externos)
- [03-APIS_N8N.md](03-APIS_N8N.md) — APIs do Hubtrix consumidas pelo N8N
- `apps/integracoes/services/hubsoft.py` — Codigo do adapter de referencia
- `apps/integracoes/models.py` — `IntegracaoAPI`, `LogIntegracao`, `ClienteHubsoft`, `ServicoClienteHubsoft`

---

## 10. Proximos passos (quando Gigamax entrar)

1. Criar `docs/context/clientes/gigamax/README.md` (dados da empresa, contatos)
2. Agendar discovery tecnico com time da Gigamax (identificar ERP)
3. Aplicar passo-a-passo da secao 5 deste documento
4. Documento especifico da integracao em `docs/PRODUTO/integracoes/05-<ERP_DA_GIGAMAX>.md`
