# Fluxos — Editor Visual

**URL:** `/configuracoes/fluxos/<id>/editor/`
**Biblioteca:** Drawflow v0.0.59 (CDN)
**Layout:** Sidebar (paleta de nos) + Canvas (Drawflow) + Config Panel (direita)

---

## Sidebar

Todos colapsados por padrao. Grupos:

| Grupo | Nodos |
|-------|-------|
| **Entrada** | Inicio do Fluxo |
| **Interacao** (icone WhatsApp) | Texto, Selecao, Imagem, Pix |
| **Condicoes** | Verificar Campo, Verificar Resposta |
| **Acoes** | Criar Oportunidade, Mover Estagio, Criar Tarefa, Webhook, Notificacao |
| **Inteligencia Artificial** (icone brain, cor roxa) | Classificador, Extrator, Respondedor, Agente |
| **Controle** | Atraso, Finalizar Fluxo, Finalizar com Score, Transferir para Humano |

Detalhes de cada nodo em [nodos.md](nodos.md).

---

## Toolbar

- **Undo/Redo** (Ctrl+Z / Ctrl+Y)
- **Zoom +/- / Reset**
- **Recontato** (modal config — ver [atendimento/recontato-automatico.md](../atendimento/recontato-automatico.md))
- **Base Conhecimento** (toggle — ativa consulta automatica nos fallbacks, ver [integracao-ia.md](integracao-ia.md))
- **Salvar**
- **Desativar / Ativar**
- **Logs** (painel lateral com atendimentos e execucao passo a passo)
- **Testar** (simulador embutido — ver [atendimento/simulador.md](../atendimento/simulador.md))

---

## Salvar e carregar

**Salvar:** POST para `/api/fluxos/<id>/salvar-fluxo/` com `{drawflow_state, nodos[], conexoes[]}`.

**Carregar:** Importa de `fluxo_json` ou reconstroi do banco se nao houver JSON salvo.

---

## Debug visual

Cada card de nodo mostra o `#pk` do nodo no canto direito do titulo (cinza pequeno) para facilitar identificar nodos em warnings e logs.

**Painel de logs (botao "Logs"):**

- Lista atendimentos recentes deste fluxo
- Click em um atendimento → timeline de execucao de cada nodo
- Util para debug de prompts, condicoes e branches

---

## Validacao do fluxo ao salvar

O backend valida o fluxo antes de salvar:

- Nodo de entrada existe e e unico
- Todas as conexoes apontam para nodos existentes
- Tipos de saida validos (default / true / false / erro / categoria_*)
- Configuracao de IA aponta para integracao existente

Se qualquer validacao falha, retorna 400 com lista de warnings (sem salvar).
