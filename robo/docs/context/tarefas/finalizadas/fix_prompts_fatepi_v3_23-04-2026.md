---
name: "Fix prompts FATEPI fluxo v3 (classificador + fallbacks IA)"
description: "Aplicar prompts corrigidos nos nodos 521, 522, 523, 527, 533 do fluxo v3 da FATEPI para parar classificacao errada de cursos e fallbacks conclusivos"
prioridade: "🔴 Alta"
responsavel: "Tech Lead"
---

# Fix prompts FATEPI fluxo v3 — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🔴 Alta
**Status:** ✅ Concluída

---

## Descrição

Fluxo v3 da FATEPI em produção (tenant=7, fluxo=6) acumulou 34 atendimentos e 0 matrículas desde 21/04. Diagnóstico do banco + simulação com `gpt-4o-mini` identificou 2 causas dominantes:

1. **Classificador de curso (nodo 523) rejeitando respostas válidas.** Prompt original era minimalista ("Cursos validos: Direito, Psicologia, Fonoaudiologia..."), e o LLM interpretava "Psicologia" isolado como pergunta informativa → respondia "curso_invalido" em 100% dos casos testados (0/13 no simulador). Candidatos caíam em nodo 529 (loop de curso inválido) e largavam.
2. **Fallbacks IA (nodos 522, 527, 533) respondiam conclusivamente sem devolver a pergunta.** Candidato pergunta "onde fica?" → bot responde o endereço e para. Sem loop de volta à pergunta original, candidato não sabe que ainda precisa responder.

Adicional:
3. Validador de nome (nodo 521) não distinguia "Pós-graduação" de nome de pessoa.

---

## Tarefas

- [x] Ler conversas reais em produção (read-only) para mapear onde os atendimentos param
- [x] Criar management command `simular_prompts_fatepi` que compara ATUAL vs NOVO sem expor api_key
- [x] Validar que NOVO passa em 13/13 e fallbacks sempre terminam com pergunta
- [x] Backup dos 5 nodos em `.backup_nodos_v3_2026-04-23.json`
- [x] UPDATE transacional dos 5 nodos via `scripts/update_nodos_fatepi_v3.py` (psycopg2, porta 5433)
- [x] Rodar simulador em prod após UPDATE: **classificador 13/13 ✅, fallback 527 4/4 ✅**
- [x] Registrar tarefa finalizada
- [ ] Monitorar 48h: query `SELECT nodo_atual_id, COUNT(*) FROM atendimentos_fluxo WHERE tenant_id=7 AND fluxo_id=6 AND data_inicio > NOW() - INTERVAL '48 hours' GROUP BY nodo_atual_id` — esperado zero presos em 529 e pelo menos 1 atendimento em 539 (PIX) ou 541 (sucesso)

---

## Contexto e referências

- Prompts corrigidos: [prompts_corrigidos_23-04-2026.md](../../clientes/fatepi/implementacoes/prompts_corrigidos_23-04-2026.md)
- Script de UPDATE: [scripts/update_nodos_fatepi_v3.py](../../../../../scripts/update_nodos_fatepi_v3.py)
- Management command: `apps/comercial/atendimento/management/commands/simular_prompts_fatepi.py`
- Backup: `.backup_nodos_v3_2026-04-23.json` (raiz do repo, gitignored)
- Nodos afetados (tenant=7, fluxo=6):
  - 521 (questao nome) → `prompt_validacao`
  - 522 (ia_respondedor fallback nome) → `system_prompt`
  - 523 (questao curso) → `prompt_validacao`
  - 527 (ia_respondedor fallback curso) → `system_prompt`
  - 533 (ia_respondedor fallback ingresso) → `system_prompt`

---

## Resultado esperado

Candidato responde "Psicologia" → classifica como curso_valido, segue pro nodo de forma de ingresso.
Candidato pergunta "onde fica?" no meio do fluxo → bot responde endereço + termina "qual curso você tem interesse?".
Ao menos 1 atendimento chega ao nodo 539 (PIX de matrícula) ou 541 (sucesso) nas próximas 48h.

## Validação pós-fix (em produção, 23/04/2026 após COMMIT)

```
A. CLASSIFICADOR DE CURSO
>> Placar: ATUAL 0/13  |  NOVO 13/13

B. FALLBACK 527 (termina com pergunta de curso?)
4/4 OK (EAD, valor, onde fica, propaganda)
```
