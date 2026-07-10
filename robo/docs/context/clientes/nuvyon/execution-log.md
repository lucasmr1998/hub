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

## 2026-07-07 — Deploy do retry plano x cidade + caso Misael Silva (gate de sync)

- Deploy: fix do retry em 2 fases (commits `c4dad49` + `a868d37`) publicado em prod e confirmado no container. Validação ao vivo pendente: aguardando primeiro caso orgânico cair no retry (monitorar marcador `retry_plano_cidade` nos logs de integração). Isabella (1840) saiu da lista de teste: prospect virou cliente 60382, guard convertido_cliente pula corretamente. Ivanildo (1969), Pedro Henrique (1901) e Cleber (1690) seguem travados com dados de Mococa no HubSoft, reprocesso não autorizado ainda.
- Investigação Misael Silva (lead 2067, prospect 23699): card em Endereço Validado com a Lavínia, mas prospect no HubSoft ainda como "Magda Santos" com endereço "A confirmar". NÃO é o bug plano x cidade: a Regra 24 disparou 2x às 13:12, porém o gate `validar_lead_pronto_para_prospect` bloqueou o PUT com `campos faltando: email, data_nascimento` (status_api=incompleto). Mesma assinatura do caso Ana Vitória. Nenhuma chamada saiu pro HubSoft.
- Decisão: evoluir pra sync incremental (PUT parcial a cada edição do lead, gate de 8 campos vira informativo, validação por campo pra CPF e serviço). Riscos avaliados com o Lucas (dado provisório espelhando cedo, CPF sem checksum fora do payload, CRM afirmado como fonte da verdade do prospect, volume trivial). Implementação ADIADA por decisão do usuário.
- Output: Tarefa Workspace #172 criada com objetivo, passos e critérios de aceite; log da Tarefa #168 atualizado com o deploy do fix. Destravar o Misael hoje é operacional: preencher email + data de nascimento no card que a Regra 24 sincroniza sozinha.
- Status: pending (tarefa #172 no backlog; validação do retry em prod pendente)

## 2026-07-08 — Relatorio Executivo da Gabi: receita, ticket, lider, canal, parados + backfill de valor

- Contexto: Gabi definiu o Relatorio Executivo como prioridade (leads/vendas do mes, conversao, receita, ticket, CAC, sem atendimento, parados, instalacoes pendentes, consultora lider, gargalo, conversao por canal). Checklist de viabilidade feito: 5 metricas ja existiam, CAC bloqueado por falta do dado de investimento.
- Widgets novos no dash #15: w#66 Receita gerada (soma lead__valor das ganhas), w#67 Ticket medio (media com filtro valor>0), w#68 Consultora lider (Thais 24, Vilhena 15, Flavia 13), w#69 Vendas por canal (whatsapp 85 / manual 9 / telefone 2), w#70 Leads parados 7+ dias no estagio (27 ops). Grid: faixa de 3 cards numericos no topo. Todos respondem aos filtros globais de Periodo e Fonte.
- Backfill de valor nas vendas: 22 das 97 ganhas estavam com valor 0 (padrao: op manual ou Talk fecha sem valor). Preenchidas TODAS com valor real: 13 via HubSoft por CPF (espelho + API), 3 via busca por telefone com match de nome, 1 desambiguada por data da venda (Escritorio Contabil Uniao, 3 clientes no mesmo telefone), 5 por preco fixo do plano. Receita do painel: R$ 7.921 -> R$ 10.198. Ticket: 81 -> 105.
- Fix estrutural (commit 440e11b): LeadProspecto.save() preenche valor com o preco tipico do plano (mode entre leads do tenant com mesmo id_plano_rp e valor>0) quando id_plano_rp existe e valor esta vazio. Nao sobrescreve valor preenchido, respeita update_fields. Testado com mock + integracao dev + inferencia em prod (plano 1260 -> 119.90).
- Engine de relatorios (commit 9ba54e7): campo lead__valor exposto no data source oportunidade (valor_estimado da op e property, nao coluna) e operador ha_mais_de_dias (data mais antiga que N dias).
- Achados de dado: 1 lead com origem suja ("Ja e cliente" no campo origem); HubSoft mostra status de instalacao (Aguardando Instalacao) utilizavel pra metrica de instalacoes pendentes.
- Pendencias: definicao da Gabi pra "leads sem atendimento" (Novo Lead=37 vs sem responsavel=12) e "instalacoes pendentes" (HubSoft vs estagio CRM); transforms de conversao geral/por canal e pior gargalo; CAC aguardando fonte do investimento (campo manual vs API Meta).
- Status: partial (5 de 12 metricas novas entregues; tarefa Workspace #173)

## 2026-07-08 — Transforms de conversao e gargalo (relatorio executivo, bloco 2)

- Engine (commit bcda76b): 3 transforms novos no query builder. `conversao_geral` (numero unico, vendas do periodo / leads do periodo, atalho no build sem exigir dimensao), `conversao_por_canal` (% por campo do lead da dimensao, corta canal com menos de 3 leads) e `gargalo_funil` (% de passagem entre etapas consecutivas reusando o funil cumulativo, pior gargalo no transform_meta). Helper `_janela_e_fonte` compartilha a logica de overrides de periodo/fonte entre os transforms cross-modelo.
- Widgets no dash #15: w#71 Conversao geral (19,6% em 30d; Meta Ads 9,5% vs organico 21,3%), w#72 Conversao por canal (manual 30%, whatsapp 19,1%, telefone 11,1%), w#73 Gargalos do funil. Faixa de numeros do topo agora com 4 cards (receita, ticket, parados, conversao).
- Achado de negocio: o funil passa 91-100% em todas as etapas de atendimento, e o PIOR gargalo e o final: Contrato Assinado -> Contratacao com 28,6% de passagem nas ops dos ultimos 30d. Leitura: o atendimento converte bem; o represamento esta na ativacao/instalacao (parte das ops recentes ainda esta em transito, o numero tende a subir um pouco, mas o padrao e claro).
- Gotcha de infra: script remoto via base64 pro shell do container NAO pode ter f-string com sequencia de escape dentro (SyntaxError na compilacao); usar print("") pra linha em branco.
- Status: completed (itens 3, 11 e 12 do relatorio executivo fechados; restam sem atendimento e instalacoes pendentes aguardando definicao da Gabi, e CAC aguardando fonte de investimento)

## 2026-07-08 — CORRECAO: bug no funil cumulativo invalidava a leitura dos gargalos

- Usuario desconfiou dos numeros do w#73 e estava certo. Bug herdado do transform `funil_cumulativo`: o estagio Perdido tem a maior `ordem` do pipeline (10), e o calculo de alcance (`ordem_max`) contava op perdida em qualquer ponto como se tivesse atravessado o funil inteiro. As 266 perdidas de 30d inflavam todas as passagens intermediarias pra ~90% e esmagavam a final (28,6% falso).
- Fix (commit 2441c71): Perdido nao avanca o alcance da op (vale o ultimo estagio real por onde passou); ganho conta como funil completo. Numeros validados contra SQL direto no `crm_historico_estagio` antes e depois do deploy.
- LEITURA DE NEGOCIO INVERTIDA: o gargalo NAO e instalacao (Contrato -> Contratacao passa 92,9%, saudavel). Os gargalos reais sao no meio do funil: Plano Escolhido -> Endereco Validado (64,4%, pior), Em Atendimento -> Plano Escolhido (68,0%) e Analises -> Contrato Assinado (68,7%). Viabilidade de endereco e escolha de plano e onde a Nuvyon mais perde oportunidade. A entrada anterior deste log (bloco 2) esta SUPERSEDIDA neste ponto.
- Status: completed

## 2026-07-08 — Caso Jose Walace (op 2255): campos obrigatorios no modal + fix do retry que era codigo morto

- Caso: prospect 23728 defasado no HubSoft. Cronologia completa: (1) 09:13/09:15 Thais salvou o modal sem email, gate bloqueou (mesmo padrao Misael); (2) 09:26 preencheu o email, gate passou, PUT saiu e HubSoft rejeitou plano x cidade (650MB PRIME Ribeirao x prospect ainda Mococa) e o retry em 2 fases NAO acionou; (3) 09:36 Thais corrigiu a cidade manualmente no painel HubSoft; (4) 09:38 re-sync via helper passou limpo (cidade ja certa) e lead ficou processado.
- Bug do retry (fix ebb21a4): o `_request` LEVANTA HubsoftServiceError quando o HubSoft responde HTTP 200 + status error, entao `_put`/`_post` nunca retornam dict de erro. A deteccao de negocio (plano x cidade, convertido pra cliente, CPF ja cadastrado) testava o dict de retorno = codigo morto. Movida pro `except` nos dois caminhos; fases do retry tambem capturam excecao. Licao: os mocks da validacao de ontem retornavam dict em vez de levantar, validaram o comportamento errado. Retestado com a mensagem real do caso.
- Prevencao (0425a64): modal de cadastro completo agora exige email, origem do cliente e origem do contato. Validacao dupla: front (toast + contador 15 campos) e backend pelo ESTADO FINAL do lead (campo ja preenchido nao precisa ser reenviado). Label "Origem do servico" renomeada pra "Origem do contato".
- Achado colateral: chamadas HubSoft feitas via manage.py shell NAO geram LogIntegracao (TenantManager sem tenant no thread-local, create falha e o `_registrar_log` engole). Explica os PUTs sem log de hoje e de casos manuais anteriores. Fix sugerido: passar tenant explicito no create do log.
- Status: completed (prospect 23728 correto e lead processado; retry corrigido em prod aguardando caso organico; Misael 2067 segue incompleto ate alguem editar o card, o modal agora vai exigir o email)

## 2026-07-08 — Filtro "Sem responsavel" + widget Leads sem atendimento (pergunta da Gabi)

- Gabi recebeu o resumo diario e perguntou onde ve as ops "sem responsavel". Nao tinha como: o filtro de Responsavel do kanban/lista so aceitava pessoa especifica.
- Entrega (commit 8c7efee): opcao "— Sem responsavel —" no dropdown das duas telas (valor especial `sem` -> `responsavel__isnull=True`); alerta do resumo diario ganhou link direto "Ver e atribuir" pra lista filtrada; SITE_URL default corrigido do dominio megalink antigo pra app.hubtrix.com.br (sem uso em codigo, agora usado no resumo).
- Widget w#75 "Leads sem atendimento (sem responsavel)" no dash #15 (12 ops ativas sem dono) — fecha o item 7 do relatorio executivo com a leitura confirmada pela propria Gabi (ops sem dono, nao ops em Novo Lead).
- Placar do relatorio executivo: 11 de 12 no ar. Falta so CAC (decisao da fonte de investimento) e a ativacao do cron horario do resumo (INSERT aguardando confirmacao).
- Status: completed

## 2026-07-08 — Diagnostico dos "sem responsavel" + fix do default na criacao manual

- Diagnostico das 14 ops ativas sem responsavel, 3 grupos: (1) 9 criadas MANUALMENTE com campo responsavel vazio (Thais 7, Bianca 1, Victoria 1) — a distribuicao automatica nao cobria e o card sumia da visao da propria criadora (op sem dono so aparece pra admin); (2) 2 orfas do Talk (ligacoes nao atendidas, sem cod_agente — legitimas, decisao da Gabi: redistribuir ou descartar); (3) 3 recem-chegadas do bot no dia (transitorio, sync do Matrix atribui quando atendente humano assume).
- Fix (commit 293ef81): na criacao manual, quem cria vira responsavel default (escolher outra pessoa no form segue valendo) + log de atribuicao na timeline. Mata o grupo 1 na raiz.
- Pendente: backfill das 9 orfas existentes pro respectivo criador (aguardando confirmacao).
- Status: completed (fix em prod)

## 2026-07-08 — Pedidos da Gabi: icone de explicacao nos widgets + leads/vendas por cidade

- Icone "?" em cada widget do painel abre modal com explicacao em linguagem de negocio (commits 1f87e99 + fix 2f66aaa: a funcao tinha ficado no bloco do modo edicao e nao existia no modo consulta). Campo Widget.descricao ja existia, sem migration; os 15 widgets do dash #15 ganharam texto.
- Pedidos novos da Gabi (17:14): origem pre-WhatsApp (ja coberto pelo rastreamento Meta Ads, com ressalvas: nao separa Face/Insta e import do CSV ainda manual), funil com viabilidade (pendente, dev pequeno), leads e vendas por cidade (entregues).
- Transform `normalizar_cidade` (98d6cff): agrupa variantes de grafia (ribeirao preto tinha 5 formas), remove sufixo /UF, title case com conectivos minusculos, descarta vazios. Widgets w#76 Leads por cidade (154 em 30d: Salto 41, Mococa 30, Ribeirao Preto 17...) e w#77 Vendas por cidade (Salto 30, Mococa 20, Mogi Mirim 12...), ambos com a ressalva de cobertura na explicacao (71% dos leads ainda sem cidade ate a etapa de endereco).
- Painel da Gabi agora com 17 widgets. Pendentes dela: funil de viabilidade (item 2) e CAC; pendencias de infra: cron do resumo diario (INSERT aguardando confirmacao) e cron do true-up de instalacoes.
- Status: completed

## 2026-07-10 — Funil de viabilidade (pedido da Gabi, item que faltava)

- Investigacao: o marcador formal de viabilidade quase nao existe (7 leads marcados vs ~130 vendas em 30d). As consultas reais rodam via Matrix/N8N so com CEP, sem identificar o lead (173 chamadas N8N todas do tr-carrion; 60 consultas HubSoft da Nuvyon sem vinculo). Funil literal sairia enganoso.
- Solucao (caf8dbe): transform `funil_viabilidade` com a etapa do meio sendo o estagio alcancado "Endereco Validado" (proxy fiel: so e alcancado quando o CEP passou na cobertura dentro do fluxo), reusando o calculo cumulativo corrigido. Etapa configuravel via agrupamento.etapa_viabilidade. Widget w#78 no dash #15.
- Numeros (30d): Leads 574 -> Endereco Validado 228 (39,7%) -> Vendas 133 (58,3%). So Meta Ads: 74 -> 34 (45,9%) -> 8 (23,5%): lead de ads valida endereco bem mas fecha muito pior pos-viabilidade.
- Gotcha: Widget.descricao e varchar(255), INSERT falhou com texto longo na primeira tentativa.
- Melhoria registrada: instrumentar o endpoint N8N de viabilidade pra aceitar telefone e carimbar o lead (funil literal vira opcao depois).
- Status: completed

## 2026-07-10 — Resumo diario da Gabi ATIVADO (cron #19)

- Cron `resumo_diario_comercial` (#19) cadastrado: roda de hora em hora (`0 * * * *`), o command envia apenas quando a hora BRT bate com o `horario_inicio` da PreferenciaNotificacao (Gabi: 8h) e ha dedup por Notificacao enviada no dia. Validado em prod: rodada as 10h pulou com "fora do horario", zero envios.
- A partir de amanha a Gabi recebe o resumo automatico as 8h, no formato aprovado pelo Lucas (novas oportunidades, vendas CRM, fluxo do dia, pipeline, ranking sem robos, alertas com link "Ver e atribuir").
- Status: completed

## 2026-07-10 — Caso Jefferson/Itu (alerta #4108) + prevencao plano x regiao no modal

- Alerta #4108: prospecto 23831 (Jefferson, lead 2212) travado no HubSoft. Historia: PUT das 12:33 gravou endereco de Itu + plano NUVYON 1GIGA (na hora validou contra a cidade antiga); depois disso TODA edicao e rejeitada porque o HubSoft valida o plano ARMAZENADO contra a cidade em qualquer PUT — ate a fase 1 do retry (sem servico) falha. Aprendizado: plano invalido gravado = prospecto em deadlock; retry nao resolve por design (decisao humana). Destravar = trocar o plano no card pra um da unidade Meganet (time avisado via Lucas).
- Prevencao (847bbfe), fluxo sugerido pelo Lucas: no modal de cadastro completo, preencheu o CEP -> o dropdown de planos recarrega so com os planos vendaveis na regiao (proxy do listar_planos_por_cep com cache 10min); selecao invalida e limpa com aviso; save bloqueia plano fora do catalogo do CEP (fail-open se HubSoft indisponivel). Validado em prod: CEP de Itu retorna 91 planos SEM o 1260; CEP de Caconde retorna 119 planos COM o 1260.
- Tambem hoje: resumo diario dividido em dois (geral sem ranking + vendedoras 1 linha por pessoa com recebeu/fechou/perdeu/sem retorno/carteira/paradas, formato compacto aprovado em preview no WhatsApp do Lucas). Cron #19 DESATIVADO a pedido ate aprovacao final; ativacao pendente: TipoNotificacao resumo_diario_vendedoras + preferencia da Gabi + religar cron.
- Status: completed (prevencao no ar) / pending (ativacao dos resumos, plano do Jefferson)

## 2026-07-10 — Resumos diarios ATIVADOS (tarefa #174 concluida)

- Ativacao completa: TipoNotificacao `resumo_diario_vendedoras` (#86, tenant 12) + PreferenciaNotificacao da Gabi (8h, whatsapp, todos os dias) + cron #20 (vendedoras) criado + cron #19 (geral) religado + fix de plural nos alertas (4fb506e).
- Validado pos-deploy: os 2 commands montam o resumo e pulam fora do horario (gate 8h + dedup). Primeiro envio automatico: 11/07 as 8h, duas mensagens pra Gabi.
- Gerenciavel em Configuracoes > Notificacoes (ligar/desligar tipo, destinatarios, horario, canal) — o cron e so o tick horario.
- Status: completed
