# Fluxos — Endpoints

## Paginas (HTML)

| URL | Descricao |
|-----|-----------|
| `/configuracoes/fluxos/` | Gerenciamento de fluxos (CRUD + botoes Editor Visual, Ativos, Questoes) |
| `/configuracoes/fluxos/<id>/editor/` | Editor visual Drawflow |
| `/configuracoes/sessoes/` | Acompanhamento de sessoes ativas (ver [atendimento/sessoes.md](../atendimento/sessoes.md)) |
| `/configuracoes/sessoes/<id>/` | Detalhe da sessao com logs |
| `/configuracoes/sessoes/<id>/fluxo/` | Visualizacao do fluxo ao vivo (nodo atual pulsando) |

---

## APIs

| Metodo | URL | Descricao |
|--------|-----|-----------|
| GET | `/api/fluxos/` | Listar fluxos |
| POST | `/api/fluxos/criar/` | Criar fluxo |
| PUT | `/api/fluxos/<id>/atualizar/` | Atualizar fluxo |
| DELETE | `/api/fluxos/<id>/deletar/` | Deletar fluxo |
| POST | `/api/fluxos/<id>/salvar-fluxo/` | Salvar editor visual |
| POST | `/api/fluxos/<id>/toggle/` | Ativar/desativar + toggle `base_conhecimento_ativa` |
| POST | `/api/fluxos/<id>/simular/` | Simulador de teste embutido |

APIs N8N dual-mode (runtime dos fluxos) estao documentadas em [atendimento/endpoints.md](../atendimento/endpoints.md).
