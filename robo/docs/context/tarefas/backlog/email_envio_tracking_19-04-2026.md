---
name: "Envio real + tracking de e-mails (marketing)"
description: "Ligar o modulo de e-mails marketing ao envio real e capturar aberturas, cliques, bounces e erros"
prioridade: "🟡 Média"
responsavel: "Tech Lead"
---

# Envio real + tracking de e-mails (marketing) — 19/04/2026

**Data:** 19/04/2026
**Responsavel:** Tech Lead
**Prioridade:** 🟡 Média
**Status:** ⏳ Aguardando

---

## Descrição

O modulo `apps/marketing/emails/` tem schema de tracking pronto (`EnvioEmail` com status enviado/aberto/clicado/erro/bounce, `tracking_id` UUID, `aberto_em`, `clicado_em`, `erro_detalhe` e metodos `registrar_abertura()` / `registrar_clique()`), mas nao tem a infra que popula essa tabela:

- Nao ha codigo que dispare envio usando um template do modulo (hoje o SMTP do Gmail esta configurado em `settings_production.py` mas nao e chamado por nenhuma view do marketing).
- Nao ha pixel tracker (GIF 1x1) nem endpoint de redirect de clique que chamem os metodos de registro.
- Nao ha webhook de provider pra capturar bounces/erros.

**Consequencia:** a tabela `EnvioEmail` esta vazia, e qualquer KPI real (taxa de abertura, taxa de clique, volume enviado, bounces) retorna zero. A stats page da lista de e-mails foi mantida com contagem de templates (total/ativos/rascunhos) ate essa infra existir.

---

## Tarefas

- [ ] **Decidir provider de envio.** Gmail SMTP nao escala e nao da tracking nativo. Avaliar SendGrid, SES, Mailgun, Postmark (custo + taxa de entrega + features de webhook).
- [ ] **Criar servico de envio.** `apps/marketing/emails/services/envio.py` com funcao que recebe `template_pk + lead_pk`, renderiza via `renderer.py` (substituindo variaveis `{{lead.*}}`, `{{tenant.*}}`), cria `EnvioEmail`, dispara via provider e preenche status inicial.
- [ ] **Pixel tracker (abertura).** Endpoint `GET /api/emails/track/open/<tracking_id>/` que retorna GIF 1x1 e chama `EnvioEmail.registrar_abertura()`. O renderer injeta a tag `<img src="..." />` no rodape do HTML.
- [ ] **Redirect de clique.** Endpoint `GET /api/emails/track/click/<tracking_id>/?url=...` que chama `registrar_clique()` e redireciona. O renderer reescreve todos os `href` do HTML pra passar por esse endpoint.
- [ ] **Webhook de bounces/erros.** Endpoint `POST /api/emails/webhook/<provider>/` que processa eventos do provider (bounce, spam, unsubscribe) e atualiza `EnvioEmail.status` + `erro_detalhe`.
- [ ] **Disparo em escala.** Definir se envio e sincrono (ruim pra campanha com milhares) ou via fila (Celery/Django-Q). Provavelmente fila.
- [ ] **Link de descadastro (LGPD).** Endpoint `/api/emails/unsub/<tracking_id>/` que marca o lead como `opt_out` e exibe confirmacao. Ja tem flag `link_descadastro` no bloco rodape do editor — so falta ligar no render.
- [ ] **Atualizar stats da lista.** Quando `EnvioEmail` estiver populado, trocar os stat cards de "total de templates" por metricas acionaveis (enviados 30d, taxa media de abertura, taxa media de clique, bounces 30d).
- [ ] **Doc do modulo.** Atualizar `robo/docs/PRODUTO/modulos/marketing/` com o fluxo de envio + tracking.

---

## Contexto e referências

- Modelo atual: [apps/marketing/emails/models.py](robo/dashboard_comercial/gerenciador_vendas/apps/marketing/emails/models.py) — `EnvioEmail` linhas 122–186
- Renderer (template → HTML): [apps/marketing/emails/renderer.py](robo/dashboard_comercial/gerenciador_vendas/apps/marketing/emails/renderer.py)
- Settings SMTP atual: [settings_production.py:96-102](robo/dashboard_comercial/gerenciador_vendas/gerenciador_vendas/settings_production.py#L96-L102) — Gmail basico, trocar
- Tarefa anterior do modulo: [email_builder_06-04-2026.md](robo/docs/context/tarefas/email_builder_06-04-2026.md) — criou o editor visual
- Discussao stats cards: migracao DS marketing (19/04/2026) — decidiu manter cards de inventario ate ter dado real

---

## Resultado esperado

- Tenant consegue disparar template pra segmento / lead individual e ver na UI a taxa de abertura e cliques em tempo quase real.
- Lista de templates mostra KPIs acionaveis (enviados 30d, taxa de abertura media, bounces) em vez de contagem de inventario.
- Bounces e descadastros sao respeitados automaticamente (lead com `opt_out` nao recebe mais).
- LGPD coberta: descadastro em 1 clique, trilhado em `LogSistema`.
