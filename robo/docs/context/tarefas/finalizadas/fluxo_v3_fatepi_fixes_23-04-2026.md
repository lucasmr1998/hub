---
name: "FATEPI fluxo v3 — 5 fixes pós-diagnóstico"
description: "34 atendimentos iniciados no fluxo v3 da FATEPI, 0 matriculas fechadas. Diagnostico identificou 5 problemas que em conjunto derrubam a conversao a zero. Este backlog agrupa os 5 pra execucao coordenada."
prioridade: "🔴 Alta"
responsavel: "Tech"
---

# FATEPI — fixes do fluxo v3 — 23/04/2026

**Cliente:** FATEPI/FAESPI (tenant_id=7)
**Fluxo:** `FATEPI - IA v3 (com fallback)` (fluxo_id=6)
**Data do diagnostico:** 23/04/2026
**Status:** ⏳ 5 fixes pendentes

---

## Contexto

Diagnostico direto no banco de producao (read-only) apontou que:
- 34 atendimentos iniciados em ~6 dias
- 0 matriculas fechadas (ninguem chegou no PIX)
- Gargalos concentrados em 5 causas raiz

## Fix #1 — Classificador de curso (nodo 523) rejeita cursos validos 🔴

**Evidencia:** 10+ leads escreveram "Psicologia", "PSICOLOGIA", "Fonoaudiologia", "Queria saber de fonoaudiologa" — todos classificados como `curso_invalido`. Psicologia e Fonoaudiologia estao na lista oficial.

**Raiz:** `prompt_validacao` no nodo 523 muito minimalista. Sem instrucao de normalizacao/tolerancia, gpt-4o-mini classifica literalmente.

**Fix:** substituir o `prompt_validacao` por versao com regras explicitas de tolerancia (caixa, acentos, typos, perguntas indiretas).

**Onde:** editor de fluxos Matrix → nodo 523 → campo `prompt_validacao`. Nao precisa de deploy de codigo.

## Fix #2 — ia_respondedor nao avanca apos 2a mensagem do candidato 🔴

**Evidencia:** 12 leads parados em nodos 522/527/533 (fallbacks IA). Topologia de conexao esta correta (522→521, 527→523, 533→532). Mas candidato responde apos fallback e fica preso.

**Hipotese:** engine consome proxima mensagem no proprio ia_respondedor em vez de rotear pro `default` apos 1 turno.

**Fix:** auditar `apps/comercial/atendimento/engine.py` funcao que processa `ia_respondedor` pra garantir que apos `max_turnos` esgotar, segue pra conexao `default`.

## Fix #3 — 5 atendimentos zumbis (nodo_atual=None) 🟡

**Evidencia:** 5 atendimentos em 15-16/04 tem `nodo_atual_id=None`. Todos respondem a nodos antigos (473, 475, 484) que foram substituidos por 521, 523, 532 na refatoracao.

**Fix:** migration que mapeia IDs antigos → novos e atualiza `nodo_atual_id`. Ou simplesmente finaliza com `motivo_finalizacao='fluxo_refatorado'`.

## Fix #4 — Campo `questao_atual` nao atualizado 🟡

**Evidencia:** todos os 34 atendimentos tem `questao_atual=1` fixo. Campo usado em relatorios esta morto.

**Fix:** engine precisa incrementar esse campo a cada vez que passa pra um nodo tipo `questao`.

## Fix #5 — Validador de nome aceita qualquer coisa 🟡

**Evidencia:** lead "Iracema Santos" respondeu "Pos-graduacao" como nome — foi salvo em `nome_razaosocial`.

**Fix:** reforcar prompt do nodo 521 pra rejeitar entradas que nao parecem um nome de pessoa.

---

## Ordem de execucao

1. **Fix #1** (classificador curso) — impacto maior, mais rapido (5min no editor)
2. **Fix #5** (validador nome) — aproveitar janela no editor, mesmo padrao
3. **Fix #3** (zumbis) — limpeza de DB, SQL pontual
4. **Fix #2** (ia_respondedor loop) — requer investigacao em engine.py
5. **Fix #4** (questao_atual) — code change, impacto so em analytics

---

## Metricas de sucesso

Apos todos os fixes, rodar novamente analise em 7 dias:
- Candidatos que param em 527/522/533 → deve cair pra < 10%
- Atendimentos em estagio "Ganho" → pelo menos 1 matricula fechada
- Zero atendimentos com `nodo_atual=None`
- `questao_atual` distribuido entre 1-6 (nao mais fixo em 1)

---

## Referencias

- Doc do fluxo esperado: [robo/docs/context/clientes/fatepi/implementacoes/fluxo_atendimento_v3.md](../../clientes/fatepi/implementacoes/fluxo_atendimento_v3.md)
- Diagnostico completo: sessao de 23/04/2026 (este chat)
- Credenciais banco prod: `.env.prod_readonly` (local, ignorado no git)
