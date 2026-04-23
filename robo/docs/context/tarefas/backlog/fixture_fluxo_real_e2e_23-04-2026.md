---
name: "Fixture de fluxo real + teste E2E no CI"
description: "Exportar fluxo v3 FATEPI como fixture JSON, criar teste e2e que percorre todos os nodos no CI com LLM mockado"
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Fixture fluxo real E2E — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média (esforco ~1 dia, fecha maior lacuna de testes)
**Status:** ⏳ Pendente

---

## Descrição

Hoje os testes unit cobrem nodos isolados e mini fluxos de 3 nodos. **Nenhum teste percorre um fluxo real de 20+ nodos**. Bug de var.X ficou latente semanas porque nunca ninguem exercitou a cadeia entrada → questao IA → condicao → acao em um cenario realista.

## Proposta

1. Exportar fluxo v3 FATEPI como fixture JSON (via management command novo `exportar_fluxo`)
2. Criar `tests/test_fluxo_v3_fatepi_e2e.py`:
   - Setup: carrega fixture, cria fluxo em DB de teste via loaddata
   - Mock `_chamar_llm_simples` com respostas pre-determinadas por cenario
   - Testes parametrizados: percorrer cada caminho critico
     - Candidato com curso valido → chega em 530 (criar_oportunidade)
     - Candidato com curso invalido → cai em 529
     - Candidato com duvida no meio → cai em 524 → 525 → 527 → retorna a 523
     - Candidato responde ENEM → chega em 539 (PIX)
   - Validar nodo_atual a cada passo + variaveis do contexto
3. CI roda `pytest tests/test_fluxo_v3_fatepi_e2e.py` em ~5s

## Tarefas

- [ ] Management command `exportar_fluxo <fluxo_id>` → arquivo JSON em `tests/fixtures/`
- [ ] Executar em prod: `python manage.py exportar_fluxo 6 > tests/fixtures/fluxo_v3_fatepi.json`
- [ ] Criar `tests/test_fluxo_v3_fatepi_e2e.py` com 4+ cenarios parametrizados
- [ ] Helper `mock_llm_for_nodo(nodo_id, resposta)` pra tornar os mocks legiveis
- [ ] Validar no CI
- [ ] Documentar padrao em `engine.md` (como adicionar fixture de outro fluxo)

## Beneficio

- Regressao de roteamento (var.X, condicao, branch) pega imediata no CI
- Base pra qualquer fluxo futuro (Nuvyon, outros tenants): so exportar + escrever cenarios
- Tempo de setup do teste ~5s (LLM mockado); a suite inteira nao infla

## Relacionados

- Tarefa da deteccao do bug: [fix_resolver_campo_contextologado_23-04-2026.md](../finalizadas/fix_resolver_campo_contextologado_23-04-2026.md)
- Discussao de estrategia: conversa do dia 23/04/2026
