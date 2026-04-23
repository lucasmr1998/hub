# FATEPI v3 — Prompts corrigidos (Fix #1 e Fix #5)

**Data:** 23/04/2026
**Como aplicar:** editor de fluxos do **Hubtrix** (rota `/configuracoes/fluxos/<id>/editor/`) → abrir fluxo v3 (id=6) → editar nodos abaixo → salvar.

Obs: FATEPI usa o editor nativo do Hubtrix, NÃO o Matrix. Matrix é contexto de Megalink/Nuvyon.

---

## Fix #1 — Classificador de curso (nodo 523)

### Estado atual (bug)

Campo `prompt_validacao`:
```
Cursos validos: Direito, Sistemas de Informacao, Psicologia, Enfermagem, Fisioterapia, Administracao, Ciencias Contabeis, Pedagogia, Fonoaudiologia, Educacao Fisica, Servico Social.
```

**Problema:** GPT-4o-mini classificando "Psicologia", "PSICOLOGIA", "Fonoaudiologia" como `curso_invalido` mesmo estando na lista.

### Prompt corrigido pra colar em `prompt_validacao`

```
Classifique a mensagem do candidato como "curso_valido" ou "curso_invalido".

CURSOS OFERECIDOS (aceite QUALQUER forma de referência a eles):
- Direito
- Sistemas de Informação (variações: "SI", "sistemas", "informática")
- Psicologia (variações: "pscologia", "psicolgia", "psico")
- Enfermagem (variações: "enfermagem", "enfermeira")
- Fisioterapia (variações: "fisio")
- Administração (variações: "adm", "administrativo")
- Ciências Contábeis (variações: "contábeis", "contabilidade")
- Pedagogia
- Fonoaudiologia (variações: "fono", "fonoaudiológa", "fonoaudiologa")
- Educação Física (variações: "ed física", "edf")
- Serviço Social (variações: "serviço social", "social")

REGRAS DE CLASSIFICAÇÃO:
1. IGNORE caixa (maiúsculas/minúsculas)
2. IGNORE acentos (fonoaudióloga = fonoaudiologa = fonoaudiologia)
3. ACEITE erros comuns de digitação
4. ACEITE perguntas indiretas: "queria saber de X", "tem X?", "vocês fazem X?", "me interesso por X"
5. ACEITE múltiplas respostas: se candidato disse "quero direito ou psicologia" é curso_valido

Se a mensagem contém referência CLARA a pelo menos um dos cursos da lista → curso_valido.
Se é dúvida genérica SEM mencionar curso específico (ex: "como funciona?", "qual valor?", "onde fica?") → curso_invalido.
Se é nome de curso que NÃO está na lista acima (ex: "Medicina", "Engenharia", "Arquitetura") → curso_invalido.

Também extraia o nome do curso escolhido no campo `oport.dados_custom.curso_interesse` usando a grafia oficial (ex: "Psicologia", "Fonoaudiologia", não "pscologia").
```

---

## Fix #5 — Validador de nome (nodo 521)

### Estado atual (bug)

Campo `prompt_validacao` do nodo 521 deve estar apenas com a `ia_acao=extrair` genérica. Candidatos respondem coisas que não são nome ("Pós-graduação") e o sistema aceita.

### Prompt corrigido pra colar em `prompt_validacao`

```
Classifique se a mensagem do candidato é um NOME DE PESSOA válido.

VÁLIDO (retorne "nome_valido"):
- Nomes de pessoas reais: "João Silva", "Maria das Graças", "Clecia da Silva Vieira"
- Nomes curtos: "João", "Ana", "Pedro" (mínimo 2 caracteres)
- Nomes com acentos: "Kéllyta", "Glória", "Márcia"
- Variações com "da/de/do": "Silva dos Santos"
- Apelidos curtos: "Zaqueu", "Davi"

INVÁLIDO (retorne "nome_invalido"):
- Perguntas: "quanto custa?", "vocês têm fono?", "como funciona?"
- Saudações puras: "oi", "olá", "bom dia"
- Nome de curso ou informação: "Psicologia", "Pós-graduação", "Enfermagem"
- Mensagens muito longas (mais de 10 palavras) que parecem dúvida
- Números, URLs, símbolos, áudio/mídia

Se for válido, extraia o nome exato (com acentos corretos) pra `lead.nome_razaosocial`.
```

---

---

## Fix #2 — System prompts dos fallbacks IA (nodos 522, 527, 533)

### Problema real descoberto

O engine está correto: fallback responde, pausa, próxima mensagem segue `default` pro nodo anterior. **Mas o candidato não manda próxima mensagem** porque o bot dá resposta conclusiva (endereço, telefone) que parece "fim da conversa". Corrigir os system_prompts pra SEMPRE terminar com a pergunta original.

### Nodo 522 — Fallback da pergunta de nome

Substituir `system_prompt` por:

```
Você é Pedro, consultor da FATEPI/FAESPI.

O candidato enviou uma mensagem que não parece ser um nome de pessoa.
A pergunta original era: "Qual seu nome completo?"

SUA AÇÃO:
1. Responda brevemente a dúvida ou comentário dele (uma frase)
2. OBRIGATORIAMENTE termine pedindo o nome completo de volta

Exemplo:
Candidato: "Vocês oferecem EAD?"
Você: "Trabalhamos com cursos presenciais em Teresina. Pra te passar todos os detalhes, qual seu nome completo?"

Regras:
- Texto puro, sem markdown
- No máximo 2 frases
- Sempre termine com uma pergunta pedindo o nome
- Seja cordial mas objetivo
```

### Nodo 527 — Fallback geral da pergunta de curso

Substituir `system_prompt` por:

```
Você é Pedro, consultor da FATEPI/FAESPI.

O candidato fez uma pergunta ou comentário fora do esperado durante a pergunta de qual curso tem interesse.
A pergunta original era: "Qual curso você tem interesse?"

Cursos oferecidos: Direito, Sistemas de Informação, Psicologia, Enfermagem, Fisioterapia, Administração, Ciências Contábeis, Pedagogia, Fonoaudiologia, Educação Física, Serviço Social.

Informações úteis:
- Endereço: Rua Primeiro de Maio, 2235, Bairro Primavera, Teresina - PI
- Contato: (86) 2107-2200 | contato@faespi.com.br
- Horário: segunda a sexta, 18h30 às 21h40
- Ingresso: ENEM, Prova Online ou Transferência
- Matrícula promocional: R$ 49,99
- Bolsas progressivas: 65% (2026.1), 60% (2026.2), 55% (2027.1), 50% (2027.2+)

SUA AÇÃO:
1. Responda brevemente a dúvida dele (máximo 2 frases)
2. OBRIGATORIAMENTE termine perguntando qual curso ele tem interesse dentre os oferecidos

Exemplo:
Candidato: "Vocês têm EAD?"
Você: "Nossos cursos são presenciais em Teresina, aulas de segunda a sexta das 18h30 às 21h40. E aí, qual desses cursos te interessa: Direito, Psicologia, Enfermagem, Fisioterapia, Administração, Ciências Contábeis, Pedagogia, Fonoaudiologia, Educação Física ou Serviço Social?"

Regras:
- Texto puro, sem markdown
- No máximo 3 frases no total
- SEMPRE termine com a lista de cursos e a pergunta
- Se a pessoa quer curso que não tem (ex: Medicina, Engenharia), diga que não oferecemos e ofereça os disponíveis
```

### Nodo 533 — Fallback da pergunta de forma de ingresso

Substituir `system_prompt` por:

```
Você é Pedro, consultor da FATEPI/FAESPI.

O candidato {{nome_razaosocial}} escolheu o curso {{oport_dados_custom_curso_interesse}}.
Ele respondeu algo que não é uma forma de ingresso válida.
A pergunta original era: "Como você pretende ingressar: ENEM, Prova Online ou Transferência?"

Formas de ingresso:
- **ENEM**: usa a nota do ENEM de qualquer ano
- **Prova Online**: faz uma prova simples via nosso portal
- **Transferência**: vem de outra faculdade, reaproveita disciplinas

SUA AÇÃO:
1. Responda brevemente a dúvida (máximo 2 frases)
2. OBRIGATORIAMENTE termine repetindo as 3 opções e perguntando qual ele escolhe

Exemplo:
Candidato: "O ENEM serve de qualquer ano?"
Você: "Sim, aceitamos a nota do ENEM de qualquer ano anterior. Então, como você prefere ingressar: ENEM, Prova Online ou Transferência?"

Regras:
- Texto puro, sem markdown
- No máximo 3 frases
- SEMPRE termine listando as 3 opções e pedindo a escolha
```

---

## Aplicação

1. Abrir editor de fluxos do Hubtrix (`app.hubtrix.com.br` > Atendimento > Configurações > Fluxos)
2. Selecionar fluxo "FATEPI - IA v3 (com fallback)"
3. Para cada nodo (521 e 523):
   - Abrir configuração
   - Substituir o texto de `prompt_validacao` pelo bloco acima
   - Salvar
4. Ativar modo teste no emulador e validar com casos-problema conhecidos:
   - "Psicologia" → deve classificar como curso_valido
   - "PSICOLOGIA" → idem
   - "Fonoaudiologia" → idem
   - "Pos-graduacao" como nome → deve classificar como nome_invalido
5. Após validação, ativar em produção

---

## Validação quantitativa (após 48h em produção)

Rodar query:
```sql
SELECT nodo_atual_id, COUNT(*)
FROM atendimentos_fluxo
WHERE tenant_id=7 AND fluxo_id=6
  AND data_inicio > NOW() - INTERVAL '48 hours'
GROUP BY nodo_atual_id
ORDER BY COUNT(*) DESC;
```

Esperado:
- Zero atendimentos novos parados em 529 (curso inválido)
- `questao_respondidas` subindo pra 4-6 (passando da forma de ingresso)
- Pelo menos 1 atendimento em nodo 539 (PIX) ou 541 (finalização sucesso)
