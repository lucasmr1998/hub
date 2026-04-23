---
name: "Encerrar atendimentos zumbis do fluxo v3 FATEPI"
description: "Marcar como 'abandonado' os 5 atendimentos do fluxo 6 cujo nodo_atual_id ficou orfao apos refactor do fluxo v3"
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Encerrar zumbis fluxo v3 FATEPI — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** ✅ Concluída

---

## Descrição

Refactor do fluxo v3 FATEPI (tenant=7, fluxo=6) trocou os IDs dos nodos. Atendimentos iniciados antes do refactor ficaram com `nodo_atual_id` apontando pra nodos que foram deletados, resultando em `nodo_atual_id=NULL` e `status='iniciado'` eterno. Se o candidato voltasse a mandar mensagem, engine nao saberia pra onde rotear.

Optado por encerrar (status='abandonado') em vez de ressuscitar, porque:
- Atendimentos de 15-16/04, ja frios (mais de 7 dias)
- Risco de mandar mensagem duplicada se ressuscitasse
- 3 dos 5 nao responderam nem a primeira pergunta

---

## Tarefas

- [x] Identificar zumbis via `scripts/listar_zumbis_v3.py` (read-only)
- [x] Confirmar com usuario os 5 IDs antes do UPDATE
- [x] UPDATE transacional via `scripts/encerrar_zumbis_v3.py`
- [x] Verificar status='abandonado' nos 5

---

## Atendimentos encerrados

| ID | Lead | Data inicio | Quest. respondidas |
|---|---|---|---|
| 136 | 190 | 16/04 10:06 | 2 |
| 135 | 189 | 16/04 09:31 | 0 |
| 134 | 188 | 15/04 22:58 | 1 |
| 133 | 187 | 15/04 21:32 | 0 |
| 132 | 186 | 15/04 20:45 | 0 |

---

## Contexto e referências

- Causa raiz: fluxo v3 foi refeito (nodos antigos 473/475/484 → novos 521/523/532). Zumbis precedem o refactor.
- Tarefa irma aplicada no mesmo dia: [fix_prompts_fatepi_v3_23-04-2026.md](fix_prompts_fatepi_v3_23-04-2026.md)
- Lead: os 5 leads (186-190) continuam no CRM; so o AtendimentoFluxo ficou como 'abandonado'. Se voltarem a mandar mensagem, engine abre atendimento novo.

---

## Prevencao futura

Quando refatorar fluxo em producao:
- Antes de deletar nodos antigos, rodar `UPDATE atendimentos_fluxo SET status='abandonado' WHERE fluxo_id=X AND status='iniciado'` OU migrar `nodo_atual_id` pro equivalente novo.
- Considerar adicionar validacao no signal de delete de `NodoFluxo` que avise se tem `AtendimentoFluxo` ativo apontando pra ele.
