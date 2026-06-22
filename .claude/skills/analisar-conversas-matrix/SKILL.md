---
name: analisar-conversas-matrix
description: Analisa um JSON de historico de atendimentos Matrix (gerado pelo command `extrair_historico_matrix`) e produz relatorio markdown com top duvidas, objecoes, momentos de friccao e recomendacoes pro flow. Use quando o usuario pedir analise de conversas/atendimentos do Matrix, ou apos rodar `python manage.py extrair_historico_matrix`. Salva o relatorio em `_historicos/analise_<tenant>_<YYYYMMDD>.md` (gitignored).
---

# Analisar conversas Matrix

Analise estruturada de um historico de atendimentos Matrix anonimizado, extraindo padroes que ajudem a melhorar o bot/flow conversacional.

## Quando usar

- Usuario rodou `extrair_historico_matrix` e quer analise
- Usuario pede "analise as conversas da Nuvyon" / "extraia as principais duvidas"
- Pedido de melhoria do bot Matrix baseado em historico real

## 0. Localize o JSON de entrada

O command `extrair_historico_matrix` salva em `_historicos/matrix_<tenant>_<YYYYMMDD>.json` por padrao.

```bash
ls -lt _historicos/matrix_*.json | head -3
```

Pega o mais recente OU o path que o usuario passou como argumento.

## 1. Leia o arquivo e valide o formato

Use `Read` no path. O JSON tem:

```json
{
  "meta": {"tenant", "fila", "periodo", "total_listados", "total_com_mensagens", "anonimizado": true},
  "atendimentos": [
    {
      "cod", "data_entrada", "duracao_seg", "agente", "status", "humor",
      "qtd_cliente", "qtd_agente", "qtd_auto",
      "mensagens": [{"tipo": "cliente|agente|bot", "ts", "texto"}]
    }
  ]
}
```

**Sanity check:**
- `meta.anonimizado === true` (senao avise e PARE — risco LGPD).
- `len(atendimentos) > 0`
- Pelo menos alguns tem `mensagens` populadas.

Se o arquivo for muito grande pra ler de uma vez (> ~5 MB), use `Read` com `offset/limit` ou amostre.

## 2. Analise por estrutura

Pra cada atendimento (ou amostra representativa se forem muitos):

- **Intencao do cliente**: o que o cliente queria? (contratar, tirar duvida, reclamacao, mudar plano, financeiro, etc)
- **Duvidas/perguntas**: o que o cliente perguntou que o bot ou agente respondeu?
- **Objecoes**: o que travou o cliente? (preco, area sem cobertura, prazo, documentos, etc)
- **Friccao**: onde o cliente teve dificuldade? (entender mensagem do bot, mandar documento errado, esperar muito, etc)
- **Resultado**: virou venda? abandonou? transferiu pra humano? falha tecnica?

Para volumes grandes (>200 conversas), amostre estrategicamente:
- N=50 atendimentos aleatorios (representatividade)
- + atendimentos com `humor` negativo (sinaliza friccao)
- + atendimentos com transferencia pra humano (sinaliza limite do bot)

## 3. Agregue padroes

**Saida estruturada em markdown:**

```markdown
# Analise de conversas Matrix — <tenant> | <fila> | <periodo>

## Resumo
- Atendimentos analisados: N
- Conversao estimada: X% (atendimentos com sinais de venda fechada)
- Taxa de transferencia humano: X%
- Humor negativo: X%

## Top 10 duvidas/perguntas frequentes
1. **"<pergunta tipica>"** — N ocorrencias — *exemplo: "..."*
   - Resposta atual do bot: <citacao>
   - Sugestao de melhoria: <opcional>
2. ...

## Top 5 objecoes recorrentes
1. **<objecao>** — N — exemplo: "..."
2. ...

## Top 5 pontos de friccao
- ...

## Padroes de sucesso
- Atendimentos que converteram tem em comum: ...

## Padroes de falha
- Atendimentos que nao converteram tem em comum: ...

## Recomendacoes pro flow Matrix
1. <acao concreta>: <justificativa baseada em N ocorrencias>
2. ...
```

## 4. Salve o relatorio

```
_historicos/analise_<tenant>_<YYYYMMDD>.md
```

Use o mesmo `_historicos/` (gitignored pra mesma regra que o JSON cru).

Apresente ao usuario um **resumo executivo** (5-10 linhas) no chat E avise onde o relatorio completo foi salvo.

## 5. Cuidados LGPD

- O JSON ja vem anonimizado (`[NOME]`, `[CPF]`, `[TELEFONE]`, `[EMAIL]`). NUNCA tente "deanonimizar" inferindo identidade do cliente.
- NAO cite trechos longos no relatorio que possam ser reidentificaveis (ex: bairro+CEP+condominio especifico). Use exemplos curtos.
- Se notar PII vazado (anonimizador falhou), AVISE explicitamente no final do relatorio.

## 6. Se faltar dado

- `mensagens=[]` em todos: avisar que o `consultar_atendimento` nao retornou conteudo. Pode ser que aquela fila so tem metadados (atendimentos sem trocas reais).
- `total_com_mensagens` muito baixo: amostra pode nao ser representativa.

## Convencao

- Saida: portugues do Brasil
- Tom: relatorio executivo (direto, com numeros, sem viagem)
- Foco: acionavel (cada recomendacao deve ser concreta o suficiente pra editar o flow)
