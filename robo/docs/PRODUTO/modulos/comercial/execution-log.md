# Execution log — Comercial (leads / CRM / cadastro)

Registro cronológico do que foi executado no módulo comercial (ação, decisão, output, status). **Append no fim** (entrada mais nova embaixo). Status: `completed` / `pending` / `blocked`.

---

## 2026-06-09 — /vendas/ unificada: status de ciclo + reconciliação (PRs #3, #4)

- **Ações**: estado `status_ciclo` "Prospecto criado no ERP" na página `/vendas/` unificada (badge amarelo); reconciliação automática Venda↔prospecto (quando o prospecto registra, a Venda sai de erro/pendente).
- **Arquivos**: `apps/dashboard/views.py` + template `vendas_crm.html`.
- **Status**: completed (merged).

## 2026-06-09 — Fixes de UI no detalhe do lead (PRs #6, #8)

- **Ações**: "Aprovar documento" dava "Token obrigatório" → `validar_imagem_api` aceita sessão (`@api_token_or_login_required`); PDF e imagens de validação apontavam pro domínio Matrix errado (megalink) → reescreve host pro Matrix do tenant (`_matrix_base_url`/`_reescrever_host_matrix`) + backfill de URLs antigas.
- **Arquivos**: `apps/comercial/leads/views.py`, `apps/comercial/leads/models.py`.
- **Status**: completed (merged + backfill em prod).

## 2026-06-09 — Notificação de venda por WhatsApp (TR Carrion): não entrega de verdade

- **Investigação**: feature existe (signal "docs validados" → uazapi), gated `tr-carrion`, tenant tem Uazapi ativo. MAS: (1) destino **chumbado** no número de teste do Lucas; (2) `ok=True` só checa HTTP 200, **não confirma entrega**; (3) os 36 registros "enviada" são **backfill anti-spam** (0 têm `telefone_destino`), não envios reais.
- **Conclusão**: a feature **nunca entregou de verdade**. Não apresentar como pronta pra TR Carrion.
- **Arquivos**: `apps/comercial/leads/services_whatsapp_venda.py`, `apps/comercial/cadastro/signals.py`.
- **Status**: completed (diagnóstico). Correções (validar entrega real, destino configurável) = pending.

## 2026-06-11 — Ação de automação: assinar contrato HubSoft

- **Ação**: nova ação de pipeline `assinar_contrato_hubsoft` (`automacao_pipeline.py`) — aceita o contrato **já existente** do lead no HubSoft (consulta com `incluir_contrato=sim` → pega o `id_cliente_servico_contrato` → `aceitar_contrato`). **Não cria** contrato (no Nuvyon ele é auto-criado). Flag opcional `ativar_servico_apos_aceite` (chama `ativar_servico` pra testar destravar a OS). Registrada no dispatcher `_EXECUTORES_ACAO` + na lista `ACOES_DISPONIVEIS` (crm/views.py) — aparece sozinha no form de regras.
- **Motivo**: automatizar a assinatura do contrato (100% Hubtrix, sem sandbox/manual). A `gerar_contrato_hubsoft` existente não serve (tenta CRIAR → "já existe" no Nuvyon).
- **Trigger**: regra com condição `imagem_status / todas_iguais / documentos_validos` → ação `assinar_contrato_hubsoft`. Disparada pelo signal `post_save ImagemLeadProspecto`. **A regra é criada pelo usuário na UI** (`/crm/automacoes-pipeline/`).
- **Risco aberto**: aceitar o contrato pode não mover o serviço de "aguardando assinatura" (lead 544). O flag `ativar_servico` é experimental (é "pós-instalação", pode não ser o passo certo). A transição assinatura→instalação no HubSoft segue a confirmar.
- **Arquivos**: `apps/comercial/crm/services/automacao_pipeline.py`, `apps/comercial/crm/views.py`, doc `automacoes-pipeline.md`.
- **Status**: completed (código + doc); pending deploy + criar a regra na UI + teste e2e.
