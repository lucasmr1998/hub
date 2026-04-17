# Fluxo de Atendimento FATEPI — v3 (com fallback IA)

**Fluxo:** FATEPI - IA v3 (com fallback)
**PK:** 6
**Canal:** WhatsApp
**Max tentativas:** 3
**Integracao IA:** OpenAI (pk=4, gpt-4o-mini)
**Total de nodos:** 24

---

## Objetivo

Qualificar leads interessados nos cursos da FATEPI/FAESPI via WhatsApp. O fluxo coleta nome, curso de interesse, forma de ingresso, apresenta valores com bolsas progressivas e tenta fechar a matricula.

## Diferencial da v3

Cada questao com IA tem um **ia_respondedor como fallback** que responde duvidas e retoma a pergunta. Na v2, o fallback era um ia_agente generico. Na v3, cada fallback e contextualizado (sabe em que ponto do fluxo o candidato esta).

---

## Estrutura do Fluxo

```
entrada (472)
  |
  v
[QUESTAO] "Qual seu nome completo?" (473)
  | espera=True, ia_acao=extrair, salvar_em=nome_razaosocial, pular_se_preenchido=True
  |
  |-- true --> Pergunta curso (475)
  |-- false --> ia_respondedor fallback nome (474)
                  "nao parece ser um nome, responde duvida e repede"
                  --> volta para (473)

[QUESTAO] "Qual curso voce tem interesse?" (475)
  | espera=True, ia_acao=classificar_extrair
  | categorias: [curso_valido, curso_invalido]
  | extrai: oport.dados_custom.curso_interesse
  |
  |-- true --> condicao curso valido? (480)
  |-- false --> ia_classificador tipo_fallback (476)
                  --> condicao: tipo_fallback = duvida_valores? (477)
                      |-- true --> ia_respondedor valores (478)
                      |                "responde com tabela de valores por curso"
                      |                --> volta para (475)
                      |-- false --> ia_respondedor geral (479)
                                     "responde duvida geral, info localizacao, contato"
                                     --> volta para (475)

[CONDICAO] curso valido? (480)
  | var.validacao_curso == curso_valido
  |
  |-- true --> criar oportunidade (482)
  |-- false --> "nao temos esse curso, repete" (481)
                  --> volta para condicao (480)

[ACAO] Criar oportunidade (482)
  | titulo: {{lead_nome}} - {{curso_interesse}}
  |
  v
[ACAO] Mover estagio: qualificacao (483)
  |
  v
[QUESTAO] "Como pretende ingressar: ENEM, Prova Online ou Transferencia?" (484)
  | espera=True, ia_acao=extrair
  | extrai: oport.dados_custom.forma_ingresso
  |
  |-- true --> mover estagio qualificado (486)
  |-- false --> ia_respondedor fallback ingresso (485)
                  "responde duvida sobre forma de ingresso"
                  --> volta para (484)

[ACAO] Mover estagio: qualificado (486)
  |
  v
[IA RESPONDEDOR] Apresentar valores (487)
  | Prompt: apresenta valores do curso escolhido
  | Valores por curso, matricula promocional R$49,99
  | Bolsas progressivas: 65% (2026.1), 60% (2026.2), 55% (2027.1), 50% (2027.2+)
  | Pergunta: "Se garantirmos essa condicao, voce consegue finalizar?"
  |
  v
[QUESTAO] Classificar decisao (488)
  | espera=False, ia_acao=classificar
  | categorias: [sim, nao, duvida]
  | variavel: decisao_matricula
  |
  |-- true --> condicao decisao=sim? (489)
  |-- false --> ia_respondedor rejeicao (494)

[CONDICAO] decisao_matricula == sim? (489)
  |
  |-- true --> mover estagio: agendado (490)
  |              |
  |              v
  |            [QUESTAO] Pagamento PIX (491)
  |              | espera=True
  |              | Mostra chave PIX e instrucoes
  |              |
  |              v
  |            [ACAO] Mover estagio: matriculado (492)
  |              |
  |              v
  |            [FINALIZACAO] "Bem-vindo a FATEPI!" (493) score=10
  |
  |-- false --> ia_respondedor rejeicao (494)
                  "candidato nao quis matricular ou tem duvidas"
                  "oferece contato (86) 2107-2200, WhatsApp"
                  |
                  v
                [FINALIZACAO] "Ate logo!" (495)
```

---

## Estagios do Pipeline usados

| Estagio | Quando |
|---------|--------|
| (inicial) | Lead criado pelo sinal |
| qualificacao | Apos escolher curso valido + criar oportunidade |
| qualificado | Apos informar forma de ingresso |
| agendado | Apos aceitar matricula (decisao=sim) |
| matriculado | Apos enviar comprovante de pagamento |

---

## Fallbacks inteligentes

| Nodo | Contexto | Comportamento |
|------|----------|--------------|
| 474 | Nome nao extraido | Responde duvida, pede nome novamente |
| 476+477+478 | Curso nao extraido + pergunta sobre valores | Responde com tabela de valores por curso, volta pra pergunta |
| 476+477+479 | Curso nao extraido + duvida geral | Responde com info geral (localizacao, contato), volta pra pergunta |
| 485 | Forma ingresso nao extraida | Responde duvida sobre ingresso, volta pra pergunta |
| 494 | Nao quis matricular | Oferece alternativas, finaliza cordialmente |

Todos os fallbacks de questao voltam para a mesma questao (loop), permitindo que o candidato tire duvidas sem perder o progresso.

---

## Valores dos cursos (no prompt do nodo 487)

| Curso | Mensalidade |
|-------|-------------|
| Direito | R$ 525/mes |
| Enfermagem | R$ 483/mes |
| Psicologia | R$ 570,50/mes |
| Sistemas de Informacao | R$ 350/mes |
| Fisioterapia | R$ 570,50/mes |
| Administracao | R$ 350/mes |
| Ciencias Contabeis | R$ 350/mes |
| Pedagogia | R$ 350/mes |
| Fonoaudiologia | R$ 570,50/mes |
| Educacao Fisica | R$ 350/mes |
| Servico Social | R$ 350/mes |

- Matricula promocional: R$ 49,99
- Bolsas progressivas: 65% → 60% → 55% → 50%

---

## Observacoes tecnicas

- `pular_se_preenchido=True` no nome: se o lead ja tem nome (veio do WhatsApp pushName), pula a pergunta
- O classificador de fallback (476) usa `ia_classificador` para categorizar o tipo de duvida antes de rotear
- A questao de decisao (488) tem `espera_resposta=False`: nao envia mensagem, apenas classifica a ultima resposta do candidato
- Todos os ia_respondedor de fallback tem `max_turnos` vazio (1 turno default), respondem e voltam ao loop
