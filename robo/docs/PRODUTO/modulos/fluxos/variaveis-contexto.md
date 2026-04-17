# Fluxos — Variaveis e Contexto

O engine constroi um `contexto` (dict) a cada execucao. Prompts e condicoes usam variaveis desse contexto via `{{nome}}`.

---

## Variaveis disponiveis

| Variavel | Origem |
|----------|--------|
| `lead_nome`, `lead_telefone`, `lead_email`, `lead_cidade`, etc. | Campos do lead |
| `lead_score`, `lead_origem`, `lead_valor` | Campos do lead |
| `ultima_resposta` | Ultima resposta do usuario |
| `resposta_nodo_<id>` | Resposta de um nodo especifico |
| `var.<nome>` | Variavel salva por ia_classificador / ia_extrator / classificar_extrair |
| `<nome>` | Mesma variavel (atalho sem prefixo `var.`) |
| `assistente_modo` | True quando e fluxo do Assistente CRM |
| `oport_dados_custom_<campo>` | Campo custom da oportunidade (setado pelo extrator) |
| `_base_conhecimento` | Artigos da base injetados automaticamente no fallback |

---

## Onde ficam armazenadas

As variaveis IA ficam em `atendimento.dados_respostas.variaveis`.

As respostas brutas de cada nodo ficam em `atendimento.dados_respostas.<nodo_id>`.

Ver estrutura completa em [atendimento/models.md](../atendimento/models.md#estrutura-do-dados_respostas).

---

## Interpolacao

Qualquer campo de texto no editor (titulo de questao, mensagem_final, system_prompt de IA) suporta interpolacao via `{{variavel}}`.

**Exemplos:**

```
Ola {{lead_nome}}! Vejo que voce e de {{lead_cidade}}.
Sua classificacao foi: {{classificacao}}
```

Variaveis nao resolvidas ficam como string literal `{{lead_nome}}` (nao quebram o fluxo).

---

## Contexto no runtime

Internamente, o engine usa `ContextoLogado` — um dict com log de eventos (set/get) que alimenta o debug de sessao. Ver [atendimento/sessoes.md](../atendimento/sessoes.md) para como visualizar.
