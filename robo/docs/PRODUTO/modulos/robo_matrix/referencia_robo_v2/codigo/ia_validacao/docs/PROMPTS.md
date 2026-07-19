# 💬 Engenharia de Prompts

Documentação dos prompts utilizados pela Aurora, persona da Megalink.

## Princípios

1. **Indistinguível de humano** — A Aurora nunca admite ser IA, mesmo se perguntada diretamente. Se pressionada, responde como uma atendente real ("sou a Aurora, atendente da Megalink").
2. **Regional, mas sutil** — Tom piauiense natural ("vamos lá", "ta certo?", "pode mandar"), sem caricatura.
3. **Curto** — Mensagens de 1-2 frases. WhatsApp não é e-mail.
4. **JSON-only output** — Toda resposta da IA volta como JSON estruturado para o validador processar.
5. **Reset de tom em falha** — Se o cliente errar, a Aurora não repete "desculpe, não entendi" robotizado; varia ("hum, não peguei direito", "pode mandar de novo?", "deu uma falha aqui").

## System Prompt (persona base)

Definido em [src/ia/prompts.py](../src/ia/prompts.py) na constante `PERSONA_SYSTEM`. Contém:

- **Identidade**: nome, empresa, região, papel
- **7 regras de comportamento** (tom, formato, limites)
- **Contexto técnico** (o que ela está fazendo)
- **Formato obrigatório de resposta JSON**

A persona é parametrizada via `.env`:
- `PERSONA_NOME` (default: `Aurora`)
- `PERSONA_EMPRESA` (default: `Megalink`)

## User Prompt (por etapa)

`prompt_validar_etapa()` monta dinamicamente:

```
ETAPA ATUAL: coleta_cpf

CONTEXTO DO CLIENTE:
  - nome: João Silva
  - cidade: Teresina
  - cep: 64000000

HISTORICO RECENTE:
  bot: Qual seu nome completo?
  cliente: João Silva
  bot: Agora me passa seu CPF, por favor.

INSTRUCOES ESPECIFICAS DA ETAPA:
{texto do campo `instrucoes_ia` do YAML}

PERGUNTA QUE VOCE FEZ: "Agora me passa seu CPF, por favor."

RESPOSTA DO CLIENTE: "12345678900"

Analise a resposta e retorne JSON conforme o formato definido.
```

### Campos injetados

| Campo | Origem |
|-------|--------|
| `ETAPA ATUAL` | id da etapa do YAML |
| `CONTEXTO DO CLIENTE` | `dados_extraidos` acumulados na conversa |
| `HISTORICO RECENTE` | últimas 5 mensagens (turnos cliente/bot) |
| `INSTRUCOES ESPECIFICAS` | bloco `instrucoes_ia` do YAML da etapa |
| `PERGUNTA QUE VOCE FEZ` | `pergunta` do YAML (ou override do Matrix) |
| `RESPOSTA DO CLIENTE` | input do `answer` da request |

## Formato de resposta esperado

```json
{
  "valido": true,
  "dados_extraidos": {"cpf": "12345678900"},
  "mensagem_bot": "Show, peguei aqui! Vamos seguir.",
  "motivo_invalido": "",
  "confianca": 0.95,
  "intencao_detectada": ""
}
```

### Campo `intencao_detectada`

Sinais de intenção que disparam saídas especiais do fluxo:

| Valor | Significado | Ação no validador |
|-------|-------------|-------------------|
| `transferir_humano` | Cliente pediu atendente | `proxima_etapa = transbordo_humano` |
| `desistir` | Cliente disse "não quero" | Encerra ou oferece registro pra contato futuro |
| `duvida` | Cliente perguntou sobre algo | Aurora responde inline antes de seguir |
| `suporte` | Problema técnico (não vendas) | Transbordo pro suporte |
| `cancelar` | Quer cancelar contrato | Transbordo pra retenção |
| `sem_viabilidade` | Cidade fora da cobertura | Fluxo de captura para fila futura |
| `ok` | Confirmação positiva | Segue o fluxo normalmente |

## Humanização adicional (opcional)

`prompt_humanizar_mensagem()` permite reescrever mensagens estáticas (ex: do YAML) com variação leve. Útil pra evitar que clientes recorrentes vejam exatamente as mesmas frases.

Custo extra: 1 chamada OpenAI por mensagem. Use com moderação ou em cache (mesma mensagem base + mesmo contexto resumido = mesma saída por 1h).

## Estratégia de economia de tokens

1. **Extractor local primeiro** — Se a etapa tem `extractor: cpf|cep|nome|telefone|data_nascimento`, tenta extrair sem chamar IA. Custo zero quando a resposta é "limpa".
2. **Histórico truncado** — Apenas as últimas 5 mensagens vão no prompt. Conversa de 30 turnos não vai inflar tokens.
3. **`dados_extraidos` filtrado** — Só campos não-vazios entram no contexto.
4. **`max_tokens=400`** na saída — Suficiente pro JSON, evita respostas longas indesejadas.
5. **Temperatura 0.4** — Variação suficiente pra parecer humano, baixa o suficiente pra estabilidade do JSON.

## Como ajustar o tom

Para mudar a persona (ex: criar uma "Marina" do suporte):

1. Adicionar novo bloco `persona:` no YAML do fluxo
2. Sobrescrever `PERSONA_SYSTEM` no momento do `validar()` (passar persona como parâmetro — TODO Fase 5)

Por enquanto, edite diretamente [src/ia/prompts.py](../src/ia/prompts.py).

## Testes de qualidade

Antes de produção, valide os prompts com casos reais:

- Cliente respondendo CPF formatado (`123.456.789-00`) vs sem formatação
- Cliente respondendo "joao" sem sobrenome no campo nome
- Cliente pedindo "atendente humano" no meio do fluxo
- Cliente perguntando "qual o preço?" em vez de responder a pergunta atual
- Cliente respondendo de forma confusa ("eh sim moça né") — não pode dar falso positivo

Salve esses casos em `tests/casos_reais.yaml` (TODO Fase 4).
