# Atendimento — Exemplo comentado de fluxo IA (FATEPI v3)

Este documento percorre um fluxo real de ponta a ponta para quem ja leu o [catalogo de tipos de nodo](tipos-de-nodo.md) e quer ver **como as pecas se encaixam em producao**.

Caso real: **fluxo v3 FATEPI** (tenant=7, fluxo=6, nome "FATEPI - IA v3 (com fallback)"). Usado pra captacao de candidatos de vestibular via WhatsApp.

> **Por que esse fluxo como exemplo:** combina questao + ia_classificador + condicao + acao (criar_oportunidade) + multiplos fallbacks ia_respondedor — cobre 80% dos padroes que voce vai montar.

---

## Panorama (24 nodos, 3 trilhos)

```
                           ENTRADA (520)
                                │
                                ▼
                         QUESTAO nome (521)
              valida=true │              │ valida=false
                          ▼              ▼
                  QUESTAO curso (523)   IA_RESPONDEDOR (522)
         curso_valido │        │ curso_invalido
                      ▼        ▼
         CONDICAO (528)      IA_CLASSIFICADOR (524)
        var.validacao         tipo_fallback?
        _curso == valido?    ┌─────┬─────┐
              │              │     │     │
         true │ false    duvida  outro (default)
              ▼      ▼        │     │
  ACAO criar_oport(530)  QUESTAO (529)  IA_RESPONDEDOR
              │         "nao temos esse"  527
              ▼
  ACAO mover_estagio(531)
              │
              ▼
  QUESTAO forma_ingresso (532)
         valida=true │
                     ▼
             ACAO mover (534)
                     │
                     ▼
             QUESTAO matricula (536) ← "quer fazer?"
                     │
                     ▼
            CONDICAO (537) var.decisao == sim?
                     │true          │false
                     ▼              ▼
             ACAO mover (538)   IA_RESPONDEDOR (542)
                     │              │
                     ▼              ▼
       QUESTAO PIX 539 "aqui vai codigo"  FINALIZACAO (543)
                     │                     "talvez outra hora"
                     ▼
             ACAO mover (540)
                     │
                     ▼
             FINALIZACAO sucesso (541)
```

**3 trilhos, do mais comum ao menos:**
1. **Trilho feliz:** nome → curso valido → forma de ingresso → decide matricular → PIX (nodo 541)
2. **Trilho curso invalido:** nome → "Medicina" → nodo 529 → re-pergunta curso
3. **Trilho duvida (fallback IA):** nome → "Voces tem EAD?" → ia_respondedor devolve info + repete pergunta do curso

---

## Jornada 1 — Lucas (caminho feliz)

### Mensagens trocadas

| Quem | Mensagem |
|---|---|
| Bot | *Ola! Sou o Pedro, consultor de ingresso da FATEPI/FAESPI. Para eu te passar os detalhes da bolsa, qual seu nome completo?* |
| Lucas | *Lucas Rodrigues Silva* |
| Bot | *Prazer! Qual curso voce tem interesse? Nossos cursos: Direito, Sistemas de Informacao, Psicologia, Enfermagem...* |
| Lucas | *Psicologia* |
| Bot | *Como voce pretende ingressar: ENEM, Prova Online ou Transferencia?* |
| Lucas | *ENEM* |
| Bot | *Quer garantir a vaga agora com a matricula promocional de R$ 49,99?* |
| Lucas | *Quero sim* |
| Bot | *Excelente! Para garantir sua vaga, realize o pagamento pelo PIX: [codigo]* |

### Nodos percorridos + estado a cada passo

| Passo | Nodo | Tipo | Acao interna | `dados_respostas.variaveis` |
|---|---|---|---|---|
| 0 | 520 | entrada | log "Fluxo iniciado", segue default | `{}` |
| 1 | 521 | questao (nome) | manda titulo, pausa esperando resposta | `{}` |
| 2 | 521 | questao (nome) | recebe "Lucas...", valida (texto ok), salva em `lead.nome_razaosocial`, branch **true** | `{}` |
| 3 | 523 | questao (curso) | manda titulo, pausa | `{}` |
| 4 | 523 | questao (curso) | recebe "Psicologia", roda `ia_acao=classificar_extrair`: extrai curso, classifica → `curso_valido`, salva em oportunidade. Branch **true** | `{validacao_curso: 'curso_valido', oport_dados_custom_curso_interesse: 'Psicologia'}` |
| 5 | 528 | condicao | avalia `var.validacao_curso == curso_valido` → **true** | `{...}` |
| 6 | 530 | acao | `criar_oportunidade` (lead+pipeline+estagio "novo"+dados_custom.curso_interesse=Psicologia) | `{...}` |
| 7 | 531 | acao | `mover_estagio` → "interessado" | `{...}` |
| 8 | 532 | questao (ingresso) | manda titulo, pausa | `{...}` |
| 9 | 532 | questao (ingresso) | recebe "ENEM", valida contra IA → `forma_ingresso=ENEM`, branch **true** | `{..., forma_ingresso: 'ENEM'}` |
| 10 | 534 | acao | `mover_estagio` → "qualificado" | |
| 11 | 536 | questao (matricula) | manda titulo, pausa | |
| 12 | 536 | questao (matricula) | recebe "Quero sim", IA classifica → `decisao_matricula=sim`, branch **true** | `{..., decisao_matricula: 'sim'}` |
| 13 | 537 | condicao | `var.decisao_matricula == sim` → **true** | |
| 14 | 538 | acao | `mover_estagio` → "proposta" | |
| 15 | 539 | questao | manda PIX, pausa (nao espera resposta util) | |
| 16 | 540 | acao | `mover_estagio` → "pagamento" | |
| 17 | 541 | finalizacao | `status='completado'`, `score=90`, `motivo='matricula_pix'` | |

**Oportunidade criada:** `OportunidadeVenda` com titulo "Lucas Rodrigues Silva — Psicologia", `dados_custom={curso_interesse: "Psicologia", forma_ingresso: "ENEM", decisao_matricula: "sim"}`, estagio final "pagamento".

---

## Jornada 2 — Fernanda (curso invalido)

Diferenca a partir do passo 4:

| Passo | Nodo | Acao |
|---|---|---|
| 4 | 523 | recebe "Medicina". IA classifica → `validacao_curso='curso_invalido'`. Branch **true** (validou, so classificou como invalido) |
| 5 | 528 | condicao `var.validacao_curso == curso_valido` → **false** |
| 6 | 529 | questao "Desculpe, nao temos esse curso. Nossos cursos: Direito..." (re-pergunta) |
| 7 | 529 | recebe "Enfermagem". Branch **true** → volta ao trilho feliz a partir de criar_oportunidade (nodo 530) |

Se Fernanda respondesse curso invalido de novo em 529, cairia no fallback ia_respondedor (527) e seria re-perguntada com informacoes extras.

---

## Jornada 3 — Joao (pergunta fora do esperado no meio)

Candidato responde o nome, mas em vez do curso pergunta **"Voces tem EAD?"**.

| Passo | Nodo | Acao |
|---|---|---|
| 4 | 523 | recebe "Voces tem EAD?". IA acha que nao eh curso claro → `validacao_curso='curso_invalido'`. Branch **true** |
| 5 | 528 | condicao → **false** (nao eh valido) |
| 6 | 529 | questao "Desculpe..." — mas Joao nao respondeu curso, respondeu pergunta. Branch **true** do 529 ⚠ |

Alternativa que o fluxo usa de verdade: branch **false** do 523 leva pra 524 (ia_classificador) → `tipo_fallback=duvida_valores/outro` → 525 (condicao) → 526 ou 527 (ia_respondedor).

**Prompt do nodo 527** (corrigido em 23/04/2026) **obriga a resposta a terminar com a pergunta de curso de volta**:

> Nossos cursos sao presenciais em Teresina. E ai, qual desses cursos te interessa: Direito, Psicologia, Enfermagem, ...?

Apos a resposta do ia_respondedor, o fluxo retorna pro nodo 523 via saida `default` e Joao tem nova chance de responder curso.

---

## Como debugar um atendimento que "parou"

### 1. Achar o atendimento

```python
from apps.comercial.atendimento.models import AtendimentoFluxo
at = AtendimentoFluxo.all_tenants.get(id=<ID>)
at.status              # 'iniciado' = ativo; 'abandonado' = zumbi; 'completado' = sucesso
at.nodo_atual_id       # onde parou
at.questoes_respondidas
at.dados_respostas     # todas as respostas + variaveis IA
```

### 2. Ver logs

```python
from apps.comercial.atendimento.models import LogFluxoAtendimento
LogFluxoAtendimento.all_tenants.filter(atendimento=at).order_by('-id')[:20]
```

Cada log tem `status` (`sucesso`, `erro`, `aguardando`, `fallback`, `llm`, `contexto`), `nodo_id`, `mensagem`, `dados` (JSON).

### 3. Distribuicao do tenant (identificar problema sistemico)

```sql
SELECT nodo_atual_id, COUNT(*)
FROM atendimentos_fluxo
WHERE tenant_id=<X> AND fluxo_id=<Y>
  AND data_inicio > NOW() - INTERVAL '48 hours'
GROUP BY nodo_atual_id
ORDER BY COUNT(*) DESC;
```

Nodos com muitos atendimentos parados sao candidatos a:
- Prompt ruim → ver `_log_llm_call` pra ver o que IA respondeu
- Branch errado → ver `dados_respostas.variaveis` e comparar com o que a condicao espera
- Nodo orfao (refactor pos-prod) → `nodo_atual_id NOT IN fluxo.nodos` (zumbi)

### 4. Simular novos prompts sem tocar em prod

Comando `simular_prompts_fatepi` (ver [simulador.md](simulador.md)) roda prompts ATUAL vs NOVO contra mesma `IntegracaoAPI` que producao, sem criar atendimento real.

---

## Armadilhas conhecidas

| Armadilha | Sintoma | Fix |
|---|---|---|
| Prompt de classificador minimalista ("Cursos validos: X, Y") | IA rejeita respostas validas tipo "PSICOLOGIA" como `curso_invalido` | Expandir prompt com regras explicitas (case, acentos, typos, perguntas indiretas) — ver [tarefa 23/04](../../../context/tarefas/finalizadas/fix_prompts_fatepi_v3_23-04-2026.md) |
| ia_respondedor responde conclusivamente sem repetir a pergunta | Candidato recebe "endereco eh X. Qualquer duvida..." e para de responder | system_prompt obriga "termine SEMPRE com a pergunta original" |
| Nodo deletado em refactor, atendimento ativo apontando pra ele | `nodo_atual_id IS NULL` ou FK orfa → engine nao roteia proxima msg | Antes de refatorar, `UPDATE atendimentos_fluxo SET status='abandonado' WHERE fluxo_id=X AND status='iniciado'` |
| Condicao `var.X` sempre retornando false | Engine deveria ir pro branch true mas vai pro false | Confirmar que `_resolver_campo_contexto` usa duck typing (fix de 23/04) — ver [engine.md](engine.md#contexto-e-resolucao-de-campos) |

---

## Relacionados

- [tipos-de-nodo.md](tipos-de-nodo.md) — contrato de cada tipo de nodo
- [engine.md](engine.md) — como o grafo eh percorrido
- [simulador.md](simulador.md) — como testar prompts e fluxos sem mexer em prod
- Tarefas do fix desse fluxo: [fix_prompts_fatepi_v3](../../../context/tarefas/finalizadas/fix_prompts_fatepi_v3_23-04-2026.md), [fix_resolver_campo_contextologado](../../../context/tarefas/finalizadas/fix_resolver_campo_contextologado_23-04-2026.md)
