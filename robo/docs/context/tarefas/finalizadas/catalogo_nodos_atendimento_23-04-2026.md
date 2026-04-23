---
name: "Catalogo de tipos de nodo do atendimento"
description: "Documentar todos os tipos de nodo do engine de atendimento (entrada, questao, ia_*, condicao, acao, delay, finalizacao) com campos aceitos, saidas e exemplo mínimo"
prioridade: "🟡 Média"
responsavel: "PM"
---

# Catalogo de tipos de nodo — atendimento — 23/04/2026

**Data:** 23/04/2026
**Responsável:** PM
**Prioridade:** 🟡 Média
**Status:** ✅ Concluída

---

## Descrição

Engine de atendimento tem 10+ tipos de nodo (entrada, questao, ia_respondedor, ia_classificador, ia_extrator, ia_agente, condicao, acao, delay, finalizacao, transferir_humano), cada um com subtipos, config propria e saidas diferentes (default/true/false/erro/categoria_*). Hoje essa informacao so existe no codigo (`engine.py::_executar_nodo` + submetodos). Consequencia: consultor/dev montando fluxo no editor nao sabe contrato, dev debugando bug (tipo var.X de 23/04) precisa ler 2500 linhas de engine.

## Tarefas

- [x] Mapear cada tipo+subtipo + campos aceitos a partir de `engine.py`
- [x] Criar `docs/PRODUTO/modulos/atendimento/tipos-de-nodo.md` com tabela/secao por tipo
- [x] Cada secao: campos obrigatorios, opcionais, saidas possiveis, exemplo JSON minimo
- [x] Linkar no `atendimento/README.md`
- [x] Regerar hub

## Resultado esperado

- Um dev/consultor abrindo o editor visual sabe sem ler codigo: "nodo condicao aceita campo/operador/valor; saidas: true/false"
- Bug proximo desse tipo e encontrado em minutos, nao horas
- Base para onboarding de novos clientes (ex: Nuvyon)
