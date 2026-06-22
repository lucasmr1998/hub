# Execution Log — Nuvyon

> Trilha cronológica do que foi implementado/decidido pra Nuvyon. Append no fim, entrada mais nova embaixo. Formato: `## YYYY-MM-DD — título`.
>
> Arquitetura Nuvyon: Matrix → Hubtrix → HubSoft (cadastrar_prospecto API) → bot Selenium (`hubtrix-bot-nuvyon`) converte em cliente.
> Tenant slug: `nuvyon` (id=12). Integração HubSoft id=18.

---

## Estado atual (snapshot 2026-06-21)

**Em produção:**

- ✅ Sistema de relatórios self-service (dashboards estilo HubSpot)
- ✅ 14 dashboards seed criados (12 do briefing + Demo + HubSoft Visão 360)
- ✅ Dashboards organizados por setor (Comercial, Atendimento, Marketing, CS, Financeiro, Técnico, Executivo)
- ✅ Visualizações ECharts com paleta pastel ISP-friendly (label sobre barra, donut com leader lines)
- ✅ Espelho HubSoft de cliente/serviço via API (`sincronizar_clientes` cron 1min)
- ✅ Bot Selenium `hubtrix-bot-nuvyon` em container EasyPanel converte prospect → cliente
- ✅ Webhook N8N do Matrix cria Lead + OportunidadeVenda direto no pipeline "Atendimento Bot (Nuvyon)"
- ✅ Pipeline 10 estágios: novo_lead → em_atendimento → endereco_validado → plano_escolhido → dados-completos → aguardando_documentos → analises-doc-score → contrato_assinado → ativacao_confirmada (ganho) / perdido
- ✅ Prospecto rascunho HubSoft via motor CRM (Regras 23 e 24) — ativo
- ✅ Pre-flight `validar_lead_pronto_para_prospect` no caminho update (Regra 24)
- ✅ Mapper editar usa formato aninhado (`prospecto_endereco`/`prospecto_servico`)

**Crons ativos (HubSoft):**
- `sincronizar_catalogos_hubsoft` (3:00 diário) — sync de planos/vendedores/origens
- `sincronizar_clientes_hubsoft` (1min) — atualiza ClienteHubsoft local

**Crons DESATIVADOS (substituídos pelas Regras 23/24):**
- `processar_pendentes_hubsoft` (id=4)
- `criar_prospectos_crm` (id=10)

**Defaults IntegracaoAPI HubSoft Nuvyon (configuracoes_extras):**
- `plano_id_padrao = 1236` (mais usado em leads históricos, 3x)
- `dia_vencimento_id_padrao = 4` (único valor já usado em leads)
- `cep_default = 13730000` (Mococa-SP centro — fallback hardcoded no helper)
- `vendedor_id_padrao = 743`
- `id_origem_padrao = 15`

**⚠️ Pendências:**
- Gabi deve revisar os 3 defaults acima e confirmar com plano/vencimento oficiais
- Bootstrap full Nuvyon (`sync_base_clientes_hubsoft --tenant nuvyon --full`, ~15min) não rodado
- Backfill viabilidade (`backfill_viabilidade --tenant nuvyon`, ~10min, ~500 leads) não rodado
- **Apagar manual no painel HubSoft:** prospectos 22936 (Eva), 22994 (teste antigo), 22996 (Pedro / cliente 60151)
- CRM Nuvyon zerado em 2026-06-21 — validar proxima esteira end-to-end

---

## 2026-04-27 — Onboarding inicial Nuvyon

- Acao: Provisionado tenant `nuvyon` em dev + cadastro IntegracaoAPI HubSoft
- Decisao: Arquitetura Matrix → Hubtrix → HubSoft. Nuvyon NÃO usa Vero. Bot Selenium roda em container separado.
- Output: tenant id=12, IntegracaoAPI id=18
- Status: completed

## 2026-04-26 — Paridade HubSoft/SGP (H1-H7)

- Acao: Concluída paridade `HubsoftService` × SGP nos blocos H1-H7
- Output: ~32/185 endpoints HubSoft mapeados + 41 testes
- Status: completed

## 2026-06-17 — Sistema de relatórios self-service + 14 dashboards Nuvyon

- Acao: Implementadas as 3 PRs (espelhos HubSoft + app relatorios + UI builder). 14 dashboards Nuvyon criados (12 briefing + Demo + HubSoft Visão 360)
- Decisao: Dashboards estilo HubSpot. Drag-drop GridStack.js + Chart.js (depois trocado por ECharts). Multi-tenant via TenantMixin.
- Output: app `relatorios`, model `Dashboard` + `Widget`, registry de Data Sources (11 fontes)
- Status: completed

## 2026-06-17 — Sprint 3 Nuvyon: campos pra relatórios cat B

- Acao: Campo `LeadProspecto.atendido_em` + signal post_save `HistoricoContato` preenche no primeiro contato. Campo `ConfiguracaoCRM.estagio_proposta_slug`. Command `backfill_viabilidade` pros leads históricos.
- Status: completed

## 2026-06-18 — Refactor visual ECharts + paleta pastel ISP

- Acao: Migrado renderWidget Chart.js → ECharts. Label sobre barra/ponto. Donut com leader lines. Paleta pastel cobalto+menta+burnt sienna (8 cores).
- Decisao: Padrão visual inspirado em HubSpot (UI) + Analitica 3M (linguagem ISP). Headline narrativa nos seeds.
- Output: commit `4c79f6a`
- Status: completed

## 2026-06-18 — Dashboards organizados por setor

- Acao: Campo `Dashboard.setor` + migration 0024. 7 setores choices. Lista agrupada com chips de filtro. Data migration atribuiu setor inicial aos 14 dashboards Nuvyon.
- Output: commit `ae0e0c6`
- Status: completed

## 2026-06-18 — Prospecto rascunho HubSoft via motor CRM

- Acao: Implementado fluxo "criar rascunho cedo + atualizar quando completo" via Regras 23 e 24 no motor `RegraPipelineEstagio`. Helper `sincronizar_prospecto_hubsoft` com placeholders. Pre-flight `validar_lead_pronto_para_prospect` no update.
- Decisao: 100% via motor de automação do CRM (não código hardcoded por tenant). Configurável por tenant — outro cliente HubSoft ativa em 2min.
- Why: Pedido Gabi pra fechar o mês com funil completo no HubSoft (incluindo leads abandonados).
- How to apply: Em qualquer mudança no fluxo de prospecto/cliente HubSoft Nuvyon, lembrar que o fluxo OFICIAL agora é via Regras CRM 23/24 — não via signal `enviar_lead_para_integracao` nem crons antigos.
- Output: commits `a31975e` (implementação), `565f9a2` (revert flag is_rascunho desnecessária), `3ed9ce4` (UI form), `29bd6c3` (CEP fallback Mococa), `3da91d9` (pre-flight update), `4cbfed5` (mapper aninhado)
- Status: completed

## 2026-06-18 — Desativados crons antigos de prospecto

- Acao: `processar_pendentes_hubsoft` (id=4) e `criar_prospectos_crm` (id=10) desativados via UPDATE em prod
- Why: Substituídos pelas Regras 23 e 24. Manter ambos rodando criaria duplicação/race condition.
- Status: completed

## 2026-06-18 — Bug descoberto: mapper editar usa dotnotation flat (HubSoft ignorava)

- Acao: HubSoft retornava `success` mas IGNORAVA silenciosamente `prospecto_endereco.cep` (formato flat). Endereço e plano não chegavam no cliente final. Corrigido pra objeto aninhado.
- Output: Cliente 60151 (Pedro) ficou com endereço placeholder "A CONFIRMAR S/N, A CONFIRMAR, MOCOCA/SP, CEP 13730000". Próximos leads vão funcionar.
- How to apply: HubSoft tem comportamento traiçoeiro — retorna sucesso silencioso pra campos não reconhecidos. Sempre validar visualmente no painel HubSoft depois de qualquer mudança no payload.
- Status: completed (fix), pending (correção manual do cliente 60151 no painel)

## 2026-06-21 — Signal enviar_lead_para_integracao desativado pra Nuvyon

- Acao: `IntegracaoAPI #18` (Nuvyon HubSoft) `configuracoes_extras.modos_sync.enviar_lead` mudado de `automatico` pra `desativado` via UPDATE direto em prod.
- Why: era o ultimo caminho redundante criando prospecto HubSoft em paralelo com a Regra 23 do motor CRM. Race condition real — signal + motor competiam pelo mesmo lead, podendo criar 2 prospectos (ex: 22994 orfao). Signal nao tem placeholders Mococa, nao tem update tardio, nao tem visibilidade na UI.
- Efeito: signal para no `if not integracao.sync_habilitado('enviar_lead'): return`. Regra 23 ("HubSoft - Criar rascunho ao receber lead") vira caminho unico de criacao. Regra 24 cuida do update tardio.
- How to apply: pra reativar (caso ache que motor nao da conta), trocar `enviar_lead` de volta pra `automatico` via UI da integracao OU UPDATE jsonb_set inverso. Outras integracoes preservadas (`sincronizar_cliente=automatico` segue rodando, eh o cron de espelho).
- Outras integracoes HubSoft: nenhuma — Nuvyon eh a unica com HubSoft ATIVO em prod (TR Carrion = Vero, FATEPI = editor nativo). Quando entrar segundo tenant HubSoft, configurar a mesma flag.
- Status: completed

## 2026-06-21 — Cleanup CRM Nuvyon em prod

- Acao: Apagados 13 leads + 13 oportunidades + filhas (220 linhas em 11 tabelas) em transacao atomica. Backup JSON local em `_backup_nuvyon_cleanup_20260621_1500.json` (gitignored).
- Decisao: Limpar so CRM (leads/oportunidades/historico/vendas/contratos). NAO tocar espelhos HubSoft (1.006 clientes + 1.308 servicos preservados). `clientes_hubsoft.lead_id` zerado pros 2 espelhos linkados (eva 22936, pedro 22996) — espelho fica intacto, so perde vinculo com lead deletado.
- Why: Comecar a esteira do zero pra validar as Regras 23/24 e o pipeline atual com dados limpos.
- How to apply: Proximos leads via webhook Matrix vao testar o fluxo end-to-end. Backup local serve pra reverter se necessario (script de restore JSON nao implementado — usar INSERT manual ou pedir).
- Pendencia manual: apagar prospectos 22936, 22994, 22996 no painel HubSoft (acesso humano necessario).
- Status: completed

---

## Bloqueios e pendências

### Pendente — bootstrap full sync Nuvyon
Rodar `python manage.py sync_base_clientes_hubsoft --tenant nuvyon --full` (1x, ~15min, 24.560 clientes). Habilita dashboards CS completos.

### Pendente — backfill viabilidade
Rodar `python manage.py backfill_viabilidade --tenant nuvyon` (~10min, ~500 leads históricos sem viabilidade gravada). Habilita relatório #9 do briefing.

### Pendente — desativar signal envio direto HubSoft
Signal `enviar_lead_para_integracao` em `apps/integracoes/signals.py:47` ainda ativo. Bypassa Regras 23/24, pode criar prospecto sem placeholders quando lead completo de cara. Desativar via `IntegracaoAPI.configuracoes_extras.modos_sync.enviar_lead='desativado'` ou `ConfiguracaoEmpresa.enviar_leads_integracao=False`.

### Pendente — Gabi confirma defaults
- `plano_id_padrao = 1236` — qual plano oficial Nuvyon usa pra rascunho?
- `dia_vencimento_id_padrao = 4` — qual dia oficial?
- `cep_default = 13730000` — Mococa-SP centro — confirmar
