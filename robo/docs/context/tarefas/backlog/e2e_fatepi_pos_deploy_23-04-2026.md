---
name: "Re-rodar teste e2e FATEPI v3 pos-deploy do fix var.X"
description: "Validar em prod que Psicologia agora avanca ate criar oportunidade + monitorar 48h a distribuicao de atendimentos"
prioridade: "🔴 Alta"
responsavel: "Tech Lead / Lucas"
---

# E2E FATEPI v3 pos-deploy — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Tech Lead / Lucas
**Prioridade:** 🔴 Alta
**Status:** ⏳ Aguardando deploy

---

## Descrição

Validar em producao que o fix var.X corrigiu o roteamento do fluxo v3 FATEPI. Pre-req: tarefa `deploy_fix_var_x_23-04-2026.md`.

## Tarefas

- [ ] Rodar `scripts/teste_e2e_fatepi_v3.py` contra container de prod
  (cria lead+atendimento temp, simula Psicologia, verifica nodo_atual pos-passo)
- [ ] Confirmar: apos "Psicologia", `nodo_atual=530` (acao criar_oportunidade), NAO `529` (curso invalido)
- [ ] Rodar query de distribuicao 1h pos-deploy:
  ```sql
  SELECT nodo_atual_id, COUNT(*) FROM atendimentos_fluxo
  WHERE tenant_id=7 AND fluxo_id=6
    AND data_inicio > NOW() - INTERVAL '1 hour'
  GROUP BY nodo_atual_id;
  ```
- [ ] Monitorar 48h: esperado zero atendimentos novos presos em 529; pelo menos 1 chegando em 539 (PIX) ou 541 (sucesso)

## Criterios de aceite

- Script `teste_e2e_fatepi_v3.py` passa com Psicologia → nodo 530
- Em 48h, taxa de conversao "curso valido → oportunidade criada" > 70% dos candidatos que respondem curso

## Referencias

- Tarefa irma: `deploy_fix_var_x_23-04-2026.md`
- Script: `scripts/teste_e2e_fatepi_v3.py`
