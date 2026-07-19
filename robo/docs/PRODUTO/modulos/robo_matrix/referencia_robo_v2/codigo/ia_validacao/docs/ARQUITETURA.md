# 🏗️ Arquitetura

## Visão geral

Sistema de validação dinâmica em 3 camadas:

1. **Camada local (regex/parse)** — extractors em `src/extractors/`
2. **Camada semântica (OpenAI)** — `src/ia/`
3. **Camada de contexto (memória de conversa)** — `src/contexto/`

## Fluxo de uma requisição

```
1. Matrix envia POST /validar
   ↓
2. Carrega contexto da conversa (histórico, dados já extraídos)
   ↓
3. Carrega definição da etapa do YAML
   ↓
4. Tenta extractor local (regex/parse)
   - Se SUCESSO claro → retorna sem IA
   - Se inconclusivo → continua para IA
   ↓
5. Chama OpenAI com:
   - System prompt (persona Aurora)
   - User prompt (etapa + pergunta + resposta + contexto + histórico)
   - Force JSON response
   ↓
6. Atualiza contexto (salva dados extraídos, incrementa tentativas)
   ↓
7. Retorna JSON estruturado para Matrix
```

## Decisões de design

### Por que extractors locais antes da IA?

**Economia de custos** (70% das requisições não precisam de IA):
- CPF: regex + algoritmo de validação
- CEP: regex + consulta ViaCEP
- Telefone: regex
- Nome: regex + heurística

A IA só entra quando:
- Resposta ambígua
- Cliente respondeu fora do esperado
- Necessita interpretação semântica (intenções)

### Por que YAML para fluxos?

- Editável por não-programadores
- Versionável no git
- Pode ter múltiplos fluxos para diferentes cenários
- Hot-reload (LRU cache invalidado ao alterar)

### Por que persona "Aurora"?

- Nome neutro, fácil de pronunciar
- Aurora = nascer do sol → conotação positiva
- Já era usado no `webhook_aurora` do flow original

### Persistência

**Fase 1 (atual):** memória RAM com TTL de 1h.

**Fase 2:** Redis para:
- Histórico de conversa (TTL ajustável)
- Rate limiting por telefone
- Cache de respostas IA para perguntas idênticas

**Fase 3:** PostgreSQL (compartilhar com Robo Vendas) para:
- Log de toda interação
- Analytics
- Auditoria

### Por que FastAPI?

- Validação automática com Pydantic
- OpenAPI/Swagger auto-gerado em `/docs`
- Performance (async)
- Type hints nativos

## Endpoints

| Método | Path | Descrição |
|--------|------|-----------|
| GET | `/` | Health check |
| POST | `/validar` | Endpoint principal (recomendado para uso novo) |
| POST | `/validar/matrix` | Compatível com payload N8N atual |
| GET | `/contexto/{telefone}` | Estado da conversa |
| DELETE | `/contexto/{telefone}` | Reset contexto (testes) |
| GET | `/fluxos` | Lista fluxos disponíveis |
| GET | `/fluxos/{nome}` | Detalhes de um fluxo |
| GET | `/docs` | Swagger UI |

## Segurança

**Fase 1:** API aberta (atrás do firewall do servidor).

**Fase 2:**
- API key obrigatória no header
- Rate limit por telefone (max 30 req/min)
- HMAC signature do Matrix
- HTTPS via nginx

## Escalabilidade

Para alto volume:
- Stateless workers (uvicorn --workers N)
- Redis para contexto compartilhado entre workers
- Cache de prompts (mesmo prompt → mesma resposta) com TTL 1h
- OpenAI batch API para casos não-tempo-real

## Custos esperados (OpenAI GPT-4o-mini)

| Métrica | Estimativa |
|---------|-----------|
| Tokens médios/validação | ~600 input + 200 output |
| Custo/validação | $0.00021 (~R$ 0.001) |
| Validações típicas/conversa | ~15 |
| Custo/conversa | $0.003 (~R$ 0.015) |
| Conversas/dia (atual) | ~50 |
| **Custo/mês estimado** | **~R$ 22,50** |

Com 70% extraído localmente sem IA, cai para ~R$ 7/mês.
