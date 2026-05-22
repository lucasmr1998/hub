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

## Webhook publico do orquestrador N8N (Vero/TR Carrion)

**Auth:** header `X-N8N-Webhook-Secret`
**Arquivo:** `apps/integracoes/views_n8n_webhook.py` -> `inbox_mensagem`
**URL:** `POST /api/public/n8n/inbox/mensagem/`

Registra mensagem no Inbox e garante Conversa + Lead + Oportunidade. Campos:
`tenant_slug`, `telefone`, `conteudo`, `direcao`, `tipo_conteudo`, `arquivo_url`,
`arquivo_nome`, `modo_atendimento`, `dados_lead`, `msg_id_externo`.

**Midia:** se o `conteudo` chegar como o objeto de midia do WhatsApp serializado
em JSON (acontece quando o fluxo N8N pega `message.content` em vez de
`message.text`), `_sanitizar_conteudo_midia` extrai `mimetype`/`title`/`URL` e
grava um conteudo legivel (`📷 Imagem`, `📎 <arquivo>`) + `tipo_conteudo`.
Defesa em profundidade: o fluxo N8N ja manda `conteudo_inbox` limpo, mas a
sanitizacao garante que nenhum JSON cru vaze pro balao.

**Armazenamento da midia (RG/CNH/comprovantes):**

1. O fluxo N8N envia `msg_id_externo` (o `messageid` do WhatsApp).
2. Pra mensagens de midia, `_baixar_midia_uazapi` chama
   `POST /message/download` no Uazapi (que descriptografa e hospeda o arquivo),
   baixa os bytes e salva no campo `Mensagem.arquivo`.
3. `Mensagem.arquivo` usa `PrivateMidiaStorage` — fica em `private_media/`,
   **fora de `MEDIA_ROOT`**, entao a rota aberta `/media/` nao serve esses
   arquivos. Acesso so via `GET /inbox/api/conversas/<pk>/midia/<msg_id>/`
   (`@login_required` + escopo de tenant). LGPD: documento de identidade e
   dado pessoal, nunca em URL publica.
4. `MensagemOutputSerializer.arquivo_url` aponta pra essa view quando ha
   `arquivo`; o Inbox renderiza imagem/PDF inline.

> URLs `.enc` do WhatsApp sao criptografadas e expiram. Por isso a midia e
> baixada no momento do recebimento, nao sob demanda.
>
> **Infra:** `private_media/` precisa de volume persistente em producao, senao
> os arquivos somem no rebuild. Backfill de mensagens antigas:
> `python manage.py recuperar_midia_inbox`.

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
| `/inbox/api/conversas/<pk>/midia/<msg_id>/` | GET | Serve a midia (imagem/PDF/audio) — auth + escopo de tenant |
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
