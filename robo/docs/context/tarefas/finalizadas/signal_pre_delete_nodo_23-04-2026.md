---
name: "Signal pre_delete em NodoFluxoAtendimento (prevencao de zumbi)"
description: "Bloqueia delete de nodo com AtendimentoFluxo ativo apontando pra ele. Previne zumbis como os 5 encontrados no fluxo v3 FATEPI"
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Signal pre_delete NodoFluxoAtendimento — 23/04/2026

**Data:** 23/04/2026
**Responsável:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** ✅ Concluída

---

## Descrição

Em 23/04/2026 encontramos 5 atendimentos zumbis no fluxo v3 FATEPI: `nodo_atual_id` apontando pra nodos deletados no refactor. Engine nao conseguia rotear proxima mensagem. Previne: signal pre_delete em `NodoFluxoAtendimento` levanta `ProtectedError` quando algum `AtendimentoFluxo` com status ativo (iniciado/em_andamento/pausado/aguardando_validacao) ainda aponta pro nodo.

Atendimentos finalizados (completado, abandonado, erro, cancelado) nao bloqueiam — o nodo_atual deles nao sera mais percorrido.

## Tarefas

- [x] Criar `apps/comercial/atendimento/signals.py` com handler
- [x] Ativar em `apps.py::ready()`
- [x] Adicionar 5 testes em `test_engine_nodos.py::TestPreDeleteNodoSemZumbi`
- [x] Suite completa passa sem regressao

## Como fazer delete quando necessario

Antes de deletar o nodo, migrar os atendimentos ativos:

```python
AtendimentoFluxo.objects.filter(nodo_atual=nodo).update(
    status='abandonado', nodo_atual=None
)
nodo.delete()
```

## Referencias

- Incidente original: [encerrar_zumbis_v3_fatepi_23-04-2026.md](encerrar_zumbis_v3_fatepi_23-04-2026.md)
