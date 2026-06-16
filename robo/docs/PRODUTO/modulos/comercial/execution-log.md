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

## 2026-06-15 — Redesign da página de detalhe da oportunidade (padrão HubSpot/RD)

- **Ações**: reformulação completa de `/crm/oportunidades/<id>/` em três frentes:
  - **Header**: stage progress bar horizontal com todos os estágios do pipeline (click move; final perdido abre modal); resumo numérico inline (valor editável, prob, dono, tempo); quick actions (Tarefa/Nota/WhatsApp/Conversa); **CTAs contextuais** (Avançar pra próximo · Marcar venda · Marcar perda) calculados pela view baseado no estágio atual e nos flags `is_final_ganho`/`is_final_perdido` do pipeline.
  - **Sidebar**: cards reorganizados na ordem Oportunidade → Bot → Lead → O.S. → Contratos → Documentos → Hubsoft. Cards Oportunidade e Dados do lead ganham botão "Editar" abrindo modal completo com todos os campos agrupados (Identificação, Endereço, Origem/qualificação, Observações). Novos cards: O.S. consolidando `OrdemServicoTentativa.filter(lead=...)`, Contratos consolidando `ContratoTentativa.filter(lead=...)`, Documentos consolidando `DocumentoLead` + anexos de `ContratoTentativa`.
  - **Timeline**: virou feed único filtrável (chips: Tudo/Notas/Conversas/Estagios/Tarefas/O.S./Contratos/Vendas/Automacoes). Eventos novos: tipo `os` (OrdemServicoTentativa), `contrato` (ContratoTentativa), `tarefa` (TarefaCRM), `nota` (NotaInterna), `automacao` (LogExecucao do motor de automação). Aba "Hist. estágios" removida (consolidada no chip "Estágios").
- **Modais novos**: Editar oportunidade completa, Editar lead completo, Nova tarefa.
- **API**: `api_editar_oportunidade` estendida pra aceitar `probabilidade`, `data_fechamento_previsto`, `origem_crm`, `rg`, `data_nascimento`, `origem`, `canal_entrada`, `score_qualificacao`.
- **Motivo**: tela antiga era um amontoado de cards sem hierarquia. User pediu paridade visual com HubSpot/RD pra dar visão completa da oportunidade (pré + pós-venda) sem o vendedor precisar sair pra outros módulos. Inspirado em opção C (híbrida) aprovada antes da implementação.
- **Validação**: `manage.py check` ok; render real da op #189 (nuvyon-dev) → HTTP 200, 164 KB. User logou em 15/06 e aprovou ("gostei mto da versão nova").
- **Arquivos**: `apps/comercial/crm/views.py`, `apps/comercial/crm/templates/crm/oportunidade_detalhe.html`, doc `crm/oportunidades.md`.
- **Status**: completed (código + doc + commit `7ac7fb0`); pending push pra origin/main e deploy prod.

## 2026-06-15 — Score externo como gate para HubSoft (Nuvyon)

- **Ações**: nova etapa "Análise — Doc & Score" no pipeline da Nuvyon ganha gating pra impedir contratos/OS pra leads sem score aprovado.
  - **Model**: `LeadProspecto` ganha `score_status` (choices `nao_consultado/pendente/aprovado/reprovado`, default `nao_consultado`, db_index), `score_atualizado_em`, `score_atualizado_por`. Migration `leads/0007`.
  - **UI**: secao "Score externo" no card "Dados do lead" do detalhe da oportunidade — chip de status + botoes Aprovar/Reprovar/Reabrir. Salva via `PUT /crm/oportunidades/<pk>/editar/`. Audit automatico em `score_atualizado_em/por` quando muda.
  - **Engine (nivel 1)**: tipo de condicao `score_externo` registrado em `automacao_condicoes.py` via decorator `@registrar` — entra automatico em `TIPOS_CONDICAO` (lazy registry).
  - **Executor (nivel 2 — defensivo)**: `_acao_gerar_contrato_hubsoft` e `_acao_assinar_contrato_hubsoft` retornam False se `lead.score_status != 'aprovado'`. Endpoint `/api/public/n8n/matrix/abrir-os/` (`views_matrix_os.abrir_os`) retorna **HTTP 409** com `motivo='score_bloqueado'` quando lead resolvido tem score nao-aprovado. Garante que retentativa manual, signals e chamadas diretas Matrix tambem sao bloqueadas.
  - **Migration A1**: `crm/0021_score_externo_gate_nuvyon.py` adiciona condicao `score_externo igual aprovado` em todas as regras ativas do tenant `nuvyon` que tenham acoes de contrato/OS HubSoft. Idempotente (nao duplica). Reversivel (`reverse_code` remove a condicao).
- **Motivo**: a engine hoje so olha pra documento; lead com doc valido mas score reprovado estaria gerando contrato HubSoft + agendamento de OS desnecessarios. Score eh marcado manualmente pelo operador (binario aprovado/reprovado). Decisao C (engine + executor) pra cobrir todos os caminhos. Decisao A1 (migration que adiciona nas regras existentes) pra subir ja operacional.
- **Validação**: `manage.py check` ok. Migration aplicada local. Smoke test do tipo de condicao: `avaliar(igual, aprovado)` retorna False com `score=nao_consultado` e True com `score=aprovado`. Template renderiza HTTP 200 com a secao Score visivel.
- **Arquivos**: `apps/comercial/leads/models.py` + migration 0007; `apps/comercial/crm/views.py`; `apps/comercial/crm/services/automacao_condicoes.py`; `apps/comercial/crm/services/automacao_pipeline.py`; `apps/integracoes/views_matrix_os.py`; `apps/comercial/crm/templates/crm/oportunidade_detalhe.html`; `apps/comercial/crm/migrations/0021_score_externo_gate_nuvyon.py`; doc `crm/oportunidades.md`.
- **Status**: completed (local); pending commit + push + deploy prod + smoke real com lead da Nuvyon.
