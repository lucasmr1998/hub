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
- **Apagar manual no painel HubSoft:** prospectos 22936 (Eva), 22994 (teste antigo), 22996 (Pedro / cliente 60151)
- CRM Nuvyon zerado em 2026-06-21 — validar proxima esteira end-to-end

> Backfill viabilidade foi removido do backlog em 2026-06-21: nao ha mais leads Nuvyon historicos pra processar (CRM zerado no cleanup do dia). Reativar caso entre re-importacao do Matrix ou bootstrap traga leads antigos com CEP.

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

### ~~Pendente — backfill viabilidade~~ (encerrado 2026-06-21)
Removido do backlog: cleanup do dia zerou os leads Nuvyon historicos, nao ha mais o que processar. Reativar se entrarem leads antigos com CEP via re-importacao do Matrix.

### ~~Pendente — desativar signal envio direto HubSoft~~ (concluido 2026-06-21)
Resolvido: `IntegracaoAPI #18` (HubSoft Nuvyon) com `modos_sync.enviar_lead='desativado'` em prod. Regra 23 do motor CRM e caminho unico de criacao de prospecto.

### Pendente — Gabi confirma defaults
- `plano_id_padrao = 1236` — qual plano oficial Nuvyon usa pra rascunho?
- `dia_vencimento_id_padrao = 4` — qual dia oficial?
- `cep_default = 13730000` — Mococa-SP centro — confirmar

---

## 2026-07-01 — Fix HubSoft rejeitando `id_origem_servico`

- Ação: HubSoft rejeitava `POST /prospecto` com "O valor selecionado para o campo id origem servico é inválido". Descoberto que o nome correto do campo na API HubSoft é `id_origem_contato`, não `id_origem_servico`. Trocado em `hubsoft.py` (linhas ~1836 do POST + sanitizador). Testado direto contra HubSoft em prod: `id_origem_contato=18` aceito.
- Decisão: Manter o dropdown do modal com os 4 valores de `origens_contato` (Facebook/Whatsapp/Telefone/Presencial) e renomear label pra "Origem do contato".
- Output: `fix(crm): trocar id_origem_servico por id_origem_contato` — 3 arquivos (hubsoft.py + 2 templates).
- Status: completed

## 2026-07-01 — Vendedora comum não vê ops sem responsável

- Ação: Removido `| Q(responsavel__isnull=True)` no filtro de visibilidade em `views.py:300` (kanban) e `views.py:556` (listagem). Vendedora sem funcionalidade `comercial.ver_todas_oportunidades` só vê `responsavel=request.user`.
- Why: Ops órfãs virando "pool livre" gerava confusão de quem devia pegar. Admin/gerente continuam vendo tudo, então ops órfãs não ficam invisíveis no sistema.
- How to apply: Cron `sync_vendedores_matrix_nuvyon` atribui responsável em 30-60s. Janela curta durante a qual vendedora dona ainda não vê — aceito.
- Output: commit `82c8674`.
- Status: completed

## 2026-07-01 — Redirect ao criar op + permissão excluir op pra Admin

- Ação (1): Modal "Nova oportunidade" ao criar redireciona pra `/crm/oportunidades/<id>/` (era ficar no pipeline). Commit `b8f0efd`.
- Ação (2): Perfil "Admin" (id=89) da Nuvyon ganhou funcionalidade `comercial.excluir_oportunidade` via INSERT em `sistema_perfil_permissao_funcionalidades (89, 46)`. Gabi/Danielle/admin_nuvyon veem botão de excluir op.
- Status: completed

## 2026-07-01 — Resumo diário WhatsApp pra Gabi (código pronto, cron pendente)

- Ação: Feature de resumo diário comercial via WhatsApp. Novo `TipoNotificacao('resumo_diario_comercial')` + `apps/comercial/crm/services/resumo_diario.py` + `apps/notificacoes/services/enviar_whatsapp_aurora.py` + management command. Uazapi da Aurora HQ (tenant 3, id=7) faz o envio. Gabi cadastrada em `PerfilUsuario.telefone` = `5519994576319`. Teste real chegou no WhatsApp.
- Decisão: Enviar às 8h BRT — framing "Como ontem fechou + Pipeline agora". Danielle NÃO recebe (só Gabi).
- Pendência: Ajuste do command pra respeitar `PreferenciaNotificacao.horario_inicio` (Gabi vira dona do horário via UI) + cadastrar cron. Ficou pausado.
- Output: commit `fc946ac`. Migration 0006 aplicada em prod.
- Status: pending (falta ajuste + cron)

## 2026-07-01 — Fix parser viabilidade HubSoft (falsos negativos)

- Ação: HubSoft mudou o schema do `/mapeamento/viabilidade/consultar` — retorna `{"origem":"mapeamento_local","projetos":[{"busca":{"elementos":{"data":[{"caixa":"...","disponiveis":N}]}}}]}` em vez do `{"viabilidade":{"atende":bool}}` antigo. Parser em `apps/comercial/viabilidade/services.py:_tentar_hubsoft` procurava a chave antiga; `bool(None)=False` → marcava TUDO como `fora_cobertura`. Regra "Sem viabilidade → Perdido" descartava leads viáveis silenciosamente. Ex: op #2059 (NALBER, CEP 13734-274 Mococa) foi movida pra Perdido apesar de 4 portas livres a 61m; escapou porque alguém moveu manualmente.
- Fix: Parser passa a ler `projetos[].busca.elementos.data[]` e considera `atende=True` se ≥1 caixa com `disponiveis > 0`. Fallback pro schema antigo mantido.
- Validado: 4 CEPs Mococa que antes davam `fora_cobertura` agora retornam `cobertura_ok`.
- Output: commit `b4274ad`.
- Status: completed

## 2026-07-01 — Cleanup de 7 ops/leads de teste

- Ação: Removidos 7 leads + 7 ops de teste via ORM. Total 51 objetos com CASCADE (histórico, tags, vendas legado). Nenhum `ClienteHubsoft` associado, seguro.
- Pendente manual: Apagar prospectos HubSoft órfãos 23419, 23391, 23389, 23334, 23173, 676576, 676577 (HubSoft não expõe DELETE via API — Gabi/Bianca no painel).
- Status: completed (Hubtrix); pending (HubSoft)

## 2026-07-01 — Dropdown vencimento com 3 opções (10/20/30)

- Ação: Modal "Completar dados" mostrava só Dia 5/10/15/20 hardcoded em `views.py:3945`. Populado `IntegracaoAPI 18.configuracoes_extras.dias_vencimento_disponiveis` com `[{dia:10,id_hubsoft:4},{dia:20,id_hubsoft:6},{dia:30,id_hubsoft:10}]`. Sem deploy — código já lia esse override.
- Detalhe: HubSoft não tem "dia 30" nativo — usa `id_vencimento=10` (último dia do mês, 28/29/30/31). Time comercial precisa saber.
- Status: completed

---

## 2026-07-03 — Integração Talk (matrixdobrasil.ai) end-to-end

- Ação: Nova integração completa com a plataforma **Talk** (softphone/PABX) que a Nuvyon usa pra chamadas de voz. Documento dedicado: [`integracao-talk.md`](./integracao-talk.md).
- Componentes: Service `apps/integracoes/services/talk.py`, importador de prospects (`importador_prospects_talk.py` + command + cron `* * * * *`), sync de vendedores (fase 2 do `sync_vendedores_matrix`), campo `PerfilUsuario.cod_talk` (migration 0014), tipo `talk` no `IntegracaoAPI` (migration 0018).
- Estado: IntegracaoAPI Talk pk=25 criada em prod; 13 vendedoras com `cod_talk` populado; 8 ops importadas + atribuídas em 03/07.
- Pendências: Andressa, Nicoly e as 3 "Mega" (Ryan/Vilhena/Bianca) sem `cod_talk` — Gabi validar. 1.186 prospects Talk antigos no HubSoft não removidos.
- Output: commits `bd6c3ef` (importador), `70c30e2` (sync Talk), `326d09c` (fix filtro 2 passos), `785bff0` (não chamar distribuir_oportunidade no importador).
- Status: completed

## 2026-07-03 — Fixes de UI/UX no detalhe da op

- Ação (1) Badge HubSoft no header: verde `☁️✓ HubSoft #NNNNN` quando lead tem `id_hubsoft`, amarelo `☁️⊘ Sem HubSoft` quando não. Commit `eddf2f7`.
- Ação (2) Truncar nome do lead com line-clamp 2 + max-width 640px, evitar que nomes longos empurrem botões. Commit `8d3dacd`.
- Status: completed

## 2026-07-03 — Timeline finalmente mostra atribuições (bug oculto)

- Ação: `select_related('usuario')` em `LogSistema.objects.filter(...)` na view do detalhe da op lançava `FieldError` porque `usuario` é CharField (não FK). O `try/except: pass` engolia a exceção — logs de atribuição nunca entravam no `timeline_items`. Bug silencioso desde o dia que foi escrito.
- Fix (1): Removido `.select_related('usuario')` + template ajustado pra ler `item.obj.usuario` como string. Commit `6885de4`.
- Fix (2) `registrar_acao`: adicionado kwarg `tenant` explícito + fallback automático (se sem tenant e `entidade in ('oportunidade','lead')`, busca via entidade_id). Sync Talk/Matrix passa `tenant=tenant` explícito. Commit `a1a54cf`.
- Backfill: 698 logs de `entidade='oportunidade'` sem tenant → populados via `UPDATE log_sistema SET tenant_id = o.tenant_id FROM crm_oportunidades o WHERE ...`. 47 restantes são de ops deletadas.
- Efeito: Timeline volta a mostrar "Responsável atribuído" (Matrix + Talk) em todas as ops antigas + novas.
- Status: completed

## 2026-07-03 — Log detalhado quando flow externo envia JSON inválido

- Ação: Flow Matrix envia `"busca": ,` e `"lead_id": ,` (variáveis undefined serializadas sem valor). Endpoints `atualizar_lead_api` e `registrar_historico_api` retornavam 400 sem contexto suficiente. Nova utility `_diagnosticar_json_invalido()` usa regex pra detectar campos com valor faltando + reporta linha/coluna/excerpt do erro. Body armazenado no `log_sistema.dados_extras` aumentado de 500 → 1500 chars. Resposta HTTP passa a devolver `campos_com_valor_faltando` pro caller.
- Pendência: Descobrir qual node do flow Matrix está com variável quebrada — precisa acesso ao painel. Cliente afetado tem protocolo `6249000001051212`, telefone `5511975630697`.
- Output: commit `2b7f556`.
- Status: partial (log implementado; fix real no flow depende de acesso Matrix)

## 2026-07-04 — Painel único de relatórios + fix data_fechamento_real

- Ação (1) Limpeza: deletados os 14 dashboards seed antigos do tenant Nuvyon (ids 1-14) + 59 widgets. Backup JSON no scratchpad da sessão (`backup_dashboards_nuvyon_20260704.json`). Único painel de trabalho agora é o **#15 "Painel Comercial"** (criado pela Gabi, compartilhado).
- Ação (2) Data source: `oportunidade` ganhou 3 campos novos — `motivo_perda_ref__nome` (FK pro catálogo real de motivos, antes só existia `motivo_perda_categoria` que estava NULL em 211/217 perdidas), `estagio__is_final_perdido` e `estagio__is_final_ganho`. Query builder ganhou operador `ultimos_dias` (filtro de data relativa). Commit `c8f6424`.
- Ação (3) Widgets novos no dash #15: **Oportunidades por origem** (pizza, `lead__origem`, últimos 30d — whatsapp 359 / manual 20 / telefone 11) e **Motivos de perda** (barra, `motivo_perda_ref__nome`, perdidas últimos 30d). Funil da Gabi reposicionado pro topo (largura cheia).
- Ação (4) Bug crítico descoberto e corrigido: `data_fechamento_real` só era carimbado em estágio GANHO — os 2 caminhos (UI `api_mover_estagio` e motor `automacao_pipeline`) ignoravam PERDIDO. 210 de 217 perdidas estavam com data NULL e relatórios de perda por período mostravam quase nada. Fix nos 2 caminhos (commit `fe48a28`) + backfill das 210 ops via data da transição no `crm_historico_estagio` (100% recuperado, zero fallback).
- Ação (5) Motivos de perda padronizados a pedido da Gabi: renomeados #46 "Prazo de instalação"→"Prazo" e #34 "Sumiu / sem resposta"→"Sem retorno" (FKs preservadas); criados #49 "Condições" e #50 "Fidelidade atual". Total 12 motivos ativos.
- Validação: os 3 widgets renderizando com dados reais via WidgetQueryBuilder em prod (funil 390→289 + Contratação 78/Perdido 230; origem 391 ops; motivos 217 perdas).
- Status: completed

## 2026-07-07 — Fix estrutural do bug plano x cidade (retry em 2 fases no HubSoft)

- Contexto: HubSoft valida o plano do payload contra a cidade ATUAL do prospecto. Prospect nasce com CEP default Mococa e, quando o endereço real chega junto do plano no mesmo PUT, o plano novo é rejeitado contra a cidade velha (ciclo vicioso). 3ª ocorrência reportada pelo time (Gabriela teste 30/06, Reinaldo 01/07 alerta #4010, Juliana 07/07). Impacto medido em prod: 82 chamadas rejeitadas, 13 leads afetados desde 25/06 (~40 rejeições/semana), 63 no PUT editar e 19 no POST create. Toda ocorrência virava correção manual do time no painel.
- Fix `hubsoft.py`: detector `_eh_erro_plano_cidade()` (substring "permitido ser vendido na cidade" na msg de erro). No PUT (`editar_prospecto`), aciona `_editar_em_duas_fases()`: fase 1 reenvia payload sem `prospecto_servico` (endereço/cidade entram), fase 2 reenvia só o serviço (validado contra a cidade nova). No POST (`cadastrar_prospecto`), aciona `_cadastrar_sem_servico()`: recria sem o serviço (rascunho nasce), plano entra no próximo update via Regra 24. Sem loop: retry é 1x, chamadas diretas em `_put`/`_post`. Se a fase 2 falhar, o plano é genuinamente inválido pra cidade real e o erro sobe pra decisão humana.
- Riscos avaliados: chamadas extras só na ocorrência do erro (~80/semana, irrelevante); mudança de texto do erro pelo HubSoft degrada pro comportamento atual (nunca piora); estado parcial (fase 1 ok, fase 2 falha) é melhor que hoje (nada entrava) e loga explicitamente.
- Validação: cenários testados com mock (detector, caminho feliz 2 fases, fase 2 falhando, create sem serviço). `manage.py check` limpo.
- Pendência: parte 2 preventiva (`cep_default_por_empresa`) vira otimização opcional; Tarefa #168 do backlog cobre este fix.
- Status: completed (aguardando deploy)
