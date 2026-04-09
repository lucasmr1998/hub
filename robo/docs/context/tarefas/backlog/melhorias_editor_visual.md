---
name: "Melhorias Visuais Editor de Fluxos"
description: "Reimplementar features visuais do editor que foram revertidas + novas features estilo N8N"
prioridade: "🟡 Media"
responsavel: "Tech Lead"
---

# Melhorias Visuais do Editor de Fluxos

## Contexto

Na sessao de 08-09/04/2026, implementamos features visuais (indicadores de status, minimap, command palette, etc.) que quebraram o layout do Drawflow. Foram revertidas. Precisam ser reimplementadas com cuidado, testando cada mudanca individualmente.

## Features para Reimplementar (eram Fase 2 e 3)

### Prioridade Alta
- [ ] Indicadores de status nos nos (badges verde/amarelo/vermelho)
- [ ] Preview do conteudo no no (titulo da questao, estagio, etc.)
- [ ] Auto-save a cada 30 segundos

### Prioridade Media
- [ ] Minimap no canto do canvas
- [ ] Command palette (Ctrl+K) para busca global
- [ ] Historico de execucao por no (click no no na sessao visual)

### Prioridade Baixa (Fase 4)
- [ ] Multi-select e mover em grupo
- [ ] Notas/comentarios no canvas (sticky notes)
- [ ] Versionamento de fluxos
- [ ] Templates de fluxo (galeria)
- [ ] Teste/debug no editor (chat embutido)
- [ ] Variaveis globais do fluxo (painel)

## Regra de Implementacao

IMPORTANTE: cada feature deve ser testada individualmente antes de commitar.
O Drawflow e sensivel a mudancas no DOM dos nos. Especificamente:
- Nao modificar o DOM dos nos apos o Drawflow renderizar (addNode/import)
- Usar apenas CSS para mudancas visuais, nao JS que modifica innerHTML
- Testar com fluxos criados via script (sem fluxo_json) que usam reconstrucao do banco
- Testar que conexoes (linhas) aparecem corretamente apos carregar

## Arquivos
- `apps/comercial/atendimento/templates/comercial/atendimento/editor_fluxo.html`
- `apps/comercial/atendimento/templates/comercial/atendimento/sessao_fluxo_visual.html`
- `apps/comercial/atendimento/views.py`
