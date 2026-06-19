# Execution Log — TR Carrion

> Trilha cronológica do que foi implementado/decidido pra TR Carrion. Append no fim, entrada mais nova embaixo. Formato: `## YYYY-MM-DD — título`.
>
> Arquitetura TR Carrion: WhatsApp → Vero (bot N8N do Hubtrix) → Hubtrix Inbox → atendente humano. **NÃO usa HubSoft** (não há ERP integrado hoje).
> Tenant slug: `tr-carrion` (id=11). Integração N8N (Vero) id varia.

---

## Estado atual (snapshot 2026-06-19)

**Em produção:**

- ✅ Inbox WhatsApp via uazapi/Vero (bot N8N processa conversa)
- ✅ Webhook N8N (`POST /api/public/n8n/inbox/mensagem/`) cria/atualiza Lead + Conversa + Mensagem
- ✅ Pipeline CRM próprio (slug `vendas-b2c`, pipeline id=13) com 7 estágios
- ✅ Regra de transferência por cidade (ex: Palhoça → Flavia)
- ✅ Distribuição round-robin como fallback
- ✅ Webhook auto-promove conversa `bot → humano` quando recebe msg com `remetente_tipo='agente'` (fix 2026-06-19)

**⚠️ Pendências/atenção:**
- Validar que flow N8N do Vero está enviando `modo_atendimento='humano'` no payload sempre que transfere pra humano. Sem isso, conversa fica órfã em `bot` se atendente não responder
- Mapear conversas em modo `bot` há > X min sem msg do bot (indicador de transferência sem flag) — análise não rodada ainda

---

## 2026-06-01 — Onboarding inicial TR Carrion + bot Vero

- Acao: Cadastro tenant `tr-carrion` (id=11). IntegracaoAPI N8N (Vero) configurada. Pipeline `vendas-b2c` criado.
- Decisao: TR Carrion usa Vero (bot N8N), não HubSoft (não tem ERP integrado). Conversas WhatsApp via uazapi.
- Status: completed

## 2026-06-01 — Bugs corrigidos: regra Docs→Criar Venda

- Acao: Regra de pipeline "documentos validados → cria Venda" ajustada. Vários bugs corrigidos durante semana.
- Status: completed

## 2026-06-02 — Incidente Michele: bot regredindo modo humano → bot

- Acao: Caso reportado: Kelle (atendente) assumiu conversa Michele, bot mandou 4 msgs por cima depois.
- Decisao: Bloqueio implementado no webhook N8N — não permite regredir `humano → bot` se já tem agente_id atribuído. Linha 680-696 de `views_n8n_webhook.py`.
- How to apply: Mudanças no webhook de inbox precisam preservar essa proteção. NUNCA permitir que payload do N8N rebaixe modo de conversa com agente atribuído.
- Output: commit (anterior ao histórico atual)
- Status: completed

## 2026-06-19 — Bug Anderson: bot e atendente respondendo paralelo (caso 99708-1320)

- Acao: Conversa pk=500 do lead Anderson (telefone 5531981167572) ficou com bot Vero disparando paralelo às respostas da atendente Thais. 3 mensagens do mesmo template ("Pra continuar preciso do verso do RG") repetidas.
- Decisao: Atendente respondeu pelo telefone diretamente (WhatsApp Web/celular), não pelo Inbox Hubtrix. Webhook N8N entregou msg como `remetente_tipo='agente'` mas conversa ficou em `modo='bot'` (nunca foi promovida). Bot continuou rodando.
- Output: Fix imediato: UPDATE manual conv pk=500 → `modo=humano, assumida=True, agente_id=25` (herdado da conv 480 anterior). Fix permanente: webhook auto-promove modo quando msg `remetente_tipo='agente'` chega em conversa `modo='bot'` + tenta herdar agente_id da última conversa resolvida do mesmo lead. Commit `a81edb9`.
- Why: Atendentes que respondem fora do Inbox (no telefone) precisam que o sistema detecte automaticamente. Não dá pra confiar só na UI.
- How to apply: Sempre que adicionar nova fonte de mensagem (novo provider, novo canal), garantir que o gate "msg de agente → promover modo" funcione lá também.
- Smoke test em prod (2026-06-19 10:59): conversa nova criada pelo webhook foi promovida automaticamente pra `humano + assumida=True`. Cleanup completo.
- Status: completed

---

## Bloqueios e pendências

### Pendente — validar flow N8N TR Carrion envia `modo_atendimento='humano'` na transferência
Quando bot transfere atendimento pra humano (cliente pede, ou flow termina), N8N **deveria** enviar `modo_atendimento='humano'` no payload do webhook `/api/public/n8n/inbox/mensagem/`. Webhook respeita isso (linhas 685-704) e distribui pra fila.

Se N8N não enviar, conversa fica em `bot` zumbi se atendente nunca responder. Vale auditar conversas em `modo=bot` sem msg do bot há > 1h pra identificar se isso está acontecendo.

### Pendente — caso Michele (02/06) revisar
Verificar se o bloqueio anti-regressão de modo continua robusto após mudanças do webhook em 19/06.
