# Inbox — APIs

---

## API Webhook (N8N / externos)

**Autenticacao:** `APITokenAuthentication` (Bearer token)
**Arquivo:** `apps/inbox/views_n8n.py`

| URL | Metodo | Descricao |
|-----|--------|-----------|
| `/api/v1/n8n/inbox/mensagem-recebida/` | POST | Recebe mensagem de contato (WhatsApp) |
| `/api/v1/n8n/inbox/status-mensagem/` | POST | Callback de delivery/leitura |

---

## APIs internas (painel)

**Auth:** `@login_required`
**Arquivo:** `apps/inbox/views.py`

| URL | Metodo | Descricao |
|-----|--------|-----------|
| `/inbox/` | GET | Inbox three-panel |
| `/inbox/dashboard/` | GET | Dashboard de metricas |
| `/inbox/configuracoes/` | GET/POST | Configuracoes (equipes, filas, FAQ, widget) |
| `/inbox/api/conversas/` | GET | Lista com filtros (status, agente, canal, busca) |
| `/inbox/api/conversas/<pk>/` | GET | Detalhe com contexto (lead, CRM, notas) |
| `/inbox/api/conversas/<pk>/mensagens/` | GET | Mensagens paginadas |
| `/inbox/api/conversas/<pk>/enviar/` | POST | Agente envia mensagem |
| `/inbox/api/conversas/<pk>/atribuir/` | POST | Atribuir agente |
| `/inbox/api/conversas/<pk>/resolver/` | POST | Resolver conversa |
| `/inbox/api/conversas/<pk>/reabrir/` | POST | Reabrir conversa |
| `/inbox/api/conversas/<pk>/transferir/` | POST | Transferir para agente/equipe/fila |
| `/inbox/api/conversas/<pk>/ticket/` | POST | Criar ticket de suporte |
| `/inbox/api/conversas/<pk>/etiquetas/` | POST | Atualizar etiquetas |
| `/inbox/api/conversas/<pk>/notas/` | POST | Adicionar nota interna |
| `/inbox/api/agente/status/` | POST | Atualizar status do agente (online/ausente/offline) |
| `/inbox/api/respostas-rapidas/` | GET | Listar respostas rapidas |
| `/inbox/api/etiquetas/` | GET | Listar etiquetas |

---

## API publica (widget — sem login)

**Auth:** `token` publico UUID no query param. CORS manual.
**Arquivo:** `apps/inbox/views_public.py`

| URL | Metodo | Descricao |
|-----|--------|-----------|
| `/api/public/widget/config/?token=X` | GET | Config do widget + categorias FAQ |
| `/api/public/widget/faq/?token=X&categoria=slug` | GET | Artigos de uma categoria |
| `/api/public/widget/faq/buscar/?token=X&q=texto` | GET | Busca artigos por titulo/conteudo |
| `/api/public/widget/conversa/iniciar/` | POST | Inicia conversa (visitor_id, nome, email, mensagem) |
| `/api/public/widget/conversa/<id>/mensagens/?token=X&visitor_id=Y` | GET | Mensagens da conversa |
| `/api/public/widget/conversa/<id>/enviar/` | POST | Visitante envia mensagem |
| `/api/public/widget/conversas/?token=X&visitor_id=Y` | GET | Lista conversas do visitante |

### Seguranca

- `@csrf_exempt`
- Validacao de `Origin` contra `dominios_permitidos`
- Nao expoe notas internas, sobrenome do agente, dados do lead ou mensagens de sistema de atribuicao
