# 🗺️ Roadmap — API IA Validação

## Análise do estado atual (11/05/2026)

### O que o fluxo Matrix atual faz

Fluxo `flow.json` com **538 nós** e **156 variáveis**:
- 39 mensagens do bot (`msg_*`)
- 21 solicitações de input (`sol_*`)
- 28 chamadas de API (`api_*`)
- 130 redirecionamentos (`red_*`)
- 14 decisões (`dec_*`)

### Os 2 webhooks N8N a substituir

| Identificador | URL | Função |
|---------------|-----|--------|
| `api_15` | `automation-n8n.v4riem.easypanel.host/webhook/matrix` | Validação geral de respostas (chamado quando o cliente diz "oi") |
| `api_16` | `automation-n8n.v4riem.easypanel.host/webhook/...DynamicValidator` | **Validador dinâmico** — recebe pergunta + resposta e retorna validade |

**Payload atual do api_16 (DynamicValidator)**:
```json
{
  "question": "{#pergunta_cliente}",
  "answer": "{#resposta_cliente}",
  "telefone": "{#CONTATO.TELEFONE}"
}
```

### Problemas identificados

1. **Resposta do N8N não está sendo armazenada** (`store.filter=0`)
2. **Validação genérica** sem contexto da etapa do fluxo
3. **Falta persona** — bot soa robótico, cliente percebe IA
4. **N8N é caixa-preta** — sem logs centralizados
5. **N8N depende de servidor externo** (`automation-n8n.v4riem.easypanel.host`)

### Por que parou em 05/05?

Análise de leads identificou:
- Bot do N8N **parou de qualificar leads desde 05/05**
- Todos os 156 leads de maio estão com `status_api='processamento_manual'`
- Nomes com "?" indicam que o N8N não consegue extrair dados

**Conclusão:** alguma alteração no N8N quebrou o fluxo. Migrar para API própria elimina essa dependência.

---

## Fases do desenvolvimento

### 🟢 Fase 1 — Fundação (Concluída agora)
- [x] Estrutura de diretórios
- [x] FastAPI base com endpoint `/validar`
- [x] Cliente OpenAI configurável via `.env`
- [x] Persona "Aurora" humanizada
- [x] Validação dinâmica baseada em contexto
- [x] Extractors básicos: CPF, CEP, nome, data, telefone
- [x] Sistema de fluxos em YAML (fácil de editar)
- [x] Documentação inicial

### 🟡 Fase 2 — Adaptação para o fluxo Megalink (próxima)
- [ ] Mapear as 21 `sol_*` do flow.json em etapas YAML
- [ ] Definir as validações por etapa (CPF válido, CEP existe, nome completo, etc)
- [ ] Implementar fallback inteligente quando IA não entende
- [ ] Persistir histórico de conversa por telefone (Redis ou DB)
- [ ] Endpoint `/contexto/<telefone>` para Matrix consultar estado
- [ ] Logs estruturados de cada chamada à IA

### 🟡 Fase 3 — Integração com Matrix
- [ ] Modificar `flow.json` substituindo URL N8N pela nossa
- [ ] Adicionar variáveis de contexto: `etapa_atual`, `intencao_detectada`
- [ ] Configurar `store.filter` para capturar resposta da IA
- [ ] Adicionar nós de decisão baseados em retorno da IA
- [ ] Importar fluxo atualizado no Matrix
- [ ] Teste end-to-end com número de teste

### 🟡 Fase 4 — IA conversacional humanizada
- [ ] Prompt sistema com persona Aurora (treinada com vocabulário Megalink)
- [ ] Variações naturais de mensagens (3-5 por etapa)
- [ ] Detectar emoção do cliente (irritado, confuso, satisfeito) e adaptar tom
- [ ] Gírias regionais piauienses opcionais
- [ ] Memória curta da conversa (lembra o que cliente falou nas últimas 5 msgs)
- [ ] Reduzir latência (cache de prompts, streaming opcional)

### 🟡 Fase 5 — Refinamentos e analytics
- [ ] Dashboard de performance (taxa de qualificação, tempo médio, custo OpenAI)
- [ ] A/B testing de prompts
- [ ] Detecção de spam/automatizado
- [ ] Auto-aprendizado: salvar conversas problemáticas para análise
- [ ] Webhook reverso: notificar Robo Vendas quando lead é qualificado

### 🟡 Fase 6 — Generalização
- [ ] Multi-tenant (1 API serve vários provedores)
- [ ] Editor visual de fluxos YAML
- [ ] Templates de fluxos (vendas, suporte, retenção, cobrança)
- [ ] SDK para outros sistemas (não só Matrix)

---

## Arquitetura de componentes

```
                    ┌─────────────────────┐
                    │   Matrix (Hubsoft)   │
                    │   flow.json (bot)    │
                    └──────────┬──────────┘
                               │ POST /validar
                               ▼
            ┌────────────────────────────────────┐
            │       API IA Validação              │
            │                                      │
            │  ┌────────────────────────────────┐ │
            │  │ Endpoint /validar              │ │
            │  │  - Recebe: pergunta, resposta, │ │
            │  │    telefone, etapa             │ │
            │  └──────────┬─────────────────────┘ │
            │             ▼                        │
            │  ┌──────────────────────────────┐   │
            │  │ Contexto da conversa         │   │
            │  │  - Carrega histórico do tel  │   │
            │  │  - Carrega fluxo YAML        │   │
            │  └──────────┬───────────────────┘   │
            │             ▼                        │
            │  ┌──────────────────────────────┐   │
            │  │ Validador                     │   │
            │  │  1. Extractor (regex/parse)  │   │
            │  │  2. OpenAI (se ambíguo)      │   │
            │  │  3. Persona humaniza resposta│   │
            │  └──────────┬───────────────────┘   │
            │             ▼                        │
            │  ┌──────────────────────────────┐   │
            │  │ Resposta JSON estruturada    │   │
            │  │  - valido: bool              │   │
            │  │  - dados_extraidos: {}       │   │
            │  │  - mensagem_bot: str         │   │
            │  │  - proxima_etapa: str        │   │
            │  └──────────────────────────────┘   │
            └─────────────┬──────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   OpenAI API (GPT)    │
              └───────────────────────┘
```

---

## Especificação da API

### POST `/validar`

**Request:**
```json
{
  "telefone": "5589994010767",
  "etapa": "coleta_cpf",
  "pergunta": "Pode me informar seu CPF?",
  "resposta": "11526411318",
  "contexto": {
    "nome": "Darlan",
    "cidade_lead": "Amarante-PI"
  }
}
```

**Response (sucesso):**
```json
{
  "valido": true,
  "dados_extraidos": {
    "cpf": "115.264.113-18"
  },
  "mensagem_bot": "Obrigada, Darlan! Agora preciso saber seu nome completo, por favor.",
  "proxima_etapa": "coleta_nome",
  "confianca": 0.98,
  "usou_ia": false
}
```

**Response (inválido):**
```json
{
  "valido": false,
  "motivo": "cpf_invalido",
  "mensagem_bot": "Hum, esse CPF parece estar incorreto. Pode conferir e digitar novamente?",
  "tentativas": 1,
  "proxima_etapa": "coleta_cpf"
}
```

**Response (não entendeu):**
```json
{
  "valido": false,
  "motivo": "nao_entendi",
  "mensagem_bot": "Desculpe, não consegui entender. Você poderia me enviar o CPF do titular? Pode ser só números mesmo, como 11122233344.",
  "tentativas": 2,
  "proxima_etapa": "coleta_cpf"
}
```

---

## Definição de fluxo em YAML

Exemplo (`fluxos/vendas_megalink.yaml`):
```yaml
nome: "Vendas Megalink Internet"
persona:
  nome: "Aurora"
  tom: "amigavel_profissional"
  regiao: "piaui"

etapas:
  - id: coleta_nome
    pergunta: "Para começar, qual é o seu nome completo?"
    extractor: nome
    validacao:
      min_palavras: 2
    proxima: coleta_cpf
    on_invalid: "Preciso do seu nome completo, com sobrenome. Pode digitar novamente?"

  - id: coleta_cpf
    pergunta: "Agora, me passa seu CPF?"
    extractor: cpf
    validacao:
      algoritmo: cpf
    proxima: coleta_cep
    on_invalid: "Esse CPF está incorreto. Pode conferir e mandar de novo?"
    max_tentativas: 3

  - id: coleta_cep
    pergunta: "Qual o CEP da sua residência?"
    extractor: cep
    api_validacao: "https://viacep.com.br/ws/{cep}/json/"
    proxima: confirmacao
```

---

## Tecnologias

| Componente | Escolha | Por quê |
|------------|---------|---------|
| Framework | **FastAPI** | Performance, type hints, OpenAPI automático |
| IA | **OpenAI GPT-4o-mini** | Custo/qualidade equilibrado, latência baixa |
| Cache | **Redis** (opcional fase 2) | Histórico de conversa, rate limit |
| Persistência | **PostgreSQL** (compartilhar com Robo Vendas) | Logs, sessões |
| Deploy | **Docker** | Reprodutível, escalável |
| Proxy | Mesmo Nginx do robovendas | Único ponto de entrada |

---

## Estimativa de custo OpenAI

Usando GPT-4o-mini:
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens

Estimativa por conversa típica (10 turnos de validação):
- ~5K tokens input + 1K output = $0.001/conversa
- 100 conversas/dia ≈ $0.10/dia ≈ **R$ 18/mês**

Com cache + extração local (regex) antes de chamar IA, dá para reduzir ~70% dos custos.

---

## Métricas de sucesso

- ✅ Taxa de qualificação ≥ 80% (vs ~3-5% atual com N8N quebrado)
- ✅ Tempo médio de resposta ≤ 2s
- ✅ Custo OpenAI ≤ R$ 50/mês
- ✅ Zero dependências externas além da OpenAI
- ✅ Cliente não identifica que está conversando com IA em 90% dos casos

---

## Próximos passos imediatos

1. **Você fornece**: chave OpenAI (`OPENAI_API_KEY=sk-...`)
2. **Eu termino**: implementação completa da Fase 2
3. **Testamos**: número de teste com fluxo modificado
4. **Migramos**: importar `flow_megalink_v2.json` no Matrix
5. **Monitoramos**: acompanhar primeiros dias de operação
