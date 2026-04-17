# Atendimento — Endpoints

## Paginas

| URL | Descricao |
|-----|-----------|
| `/configuracoes/sessoes/` | Lista de sessoes |
| `/configuracoes/sessoes/<id>/` | Detalhe com logs |
| `/configuracoes/sessoes/<id>/fluxo/` | Visualizacao ao vivo |

Detalhes das telas em [sessoes.md](sessoes.md).

---

## APIs (dual-mode: legado + visual)

Todas as APIs N8N detectam automaticamente o modo do fluxo (legado/visual) e despacham para o handler correto.

| Metodo | URL | Descricao |
|--------|-----|-----------|
| POST | `/api/n8n/atendimento/iniciar/` | Iniciar atendimento (detecta modo_fluxo) |
| POST | `/api/n8n/atendimento/<id>/responder/` | Responder (detecta modo_fluxo) |
| POST | `/api/n8n/atendimento/<id>/finalizar/` | Finalizar |
| POST | `/api/n8n/atendimento/<id>/pausar/` | Pausar |
| POST | `/api/n8n/atendimento/<id>/retomar/` | Retomar |

Para a API do simulador (`/api/fluxos/<id>/simular/`), ver [simulador.md](simulador.md).
