# Execution log — Integrações (HubSoft / Matrix)

Registro cronológico do que foi executado no módulo de integrações (ação, decisão, output, status). **Append no fim** (entrada mais nova embaixo). Status: `completed` / `pending` / `blocked`.

---

## 2026-06-09 — Pipeline Nuvyon (HubSoft): correções do funil lead→prospecto→cliente

- **Ações**: rg=cpf automático (signal `apps/integracoes/signals.py`, só tenants com HubSoft ativo); reconciliação Venda↔prospecto; diagnóstico do bot Selenium (DRY_RUN=1 travava a conversão — mascarava como "Selenium pendurado"); fix vencimento (bot lia dia 9 fixo → lê `id_dia_vencimento`); fix `salvar_prospecto` (jsonb/prioridade).
- **PRs**: parte dos #1–#8 (merged). Itens de UI (status_ciclo, token, pdf) logados em `comercial`.
- **Prova**: lead 544 convertido em cliente real no HubSoft (cliente 60005, vencimento dia 10).
- **Status**: completed (merged). Redeploy do bot + flow vivo (`id_origem_servico` 16→74) = pending no lado do Lucas.

## 2026-06-09 — Disparos de teste Matrix (flows)

- **Ações**: disparos via API Matrix (artelecomprovedor); padrão = finaliza atendimento aberto → inicia flow.
- **Aprendizado**: **flow 113 cria lead de venda** (lead 547 "Danielle", com rg=cpf OK). A "pesquisa de satisfação" que aparecia era **CSAT de atendimento anterior finalizando**, não do flow. "Transferido" no Matrix = estado já FECHADO.
- **Status**: completed.

## 2026-06-09 — Abertura de OS: investigação + decisão (manter Matrix)

- **Investigação**: OS orquestrada pelo flow Matrix (turno/data) chamando wrappers Hubtrix (`views_matrix_os.py`) → HubSoft. Backend (wrappers + `HubsoftService` + config `os_matrix`) 100% pronto; só a camada conversacional vive no Matrix.
- **Decisão (Lucas)**: **manter o Matrix orquestrando** (migrar a conversa pro Inbox foi despriorizado — reunião de paridade 27/04).
- **Gate de instalação** (polling ~30min): `eh_cliente_hubsoft` + `documentacao_validada` (campo do lead) + `doc_rejeitado=0`. Só **1/12** leads recentes passam (upstream vaza). Lead 544 passa os 3 gates (`id_cliente_servico` 108931), mas a OS é bloqueada pelo contrato (ver abaixo).
- **Gaps**: não guarda `id_ordem_servico`; sem sync de status; sem remarcar.
- **Status**: completed (investigação). Tracking de OS = pending.

## 2026-06-09 — Sandbox de contrato (PRs #9, #10)

- **Ação**: ações novas no `api_integracao_financeiro_sandbox` (`/configuracoes/integracoes/18/` → aba Sandbox): `consultar_cliente`, `listar_modelos_contrato`, `criar_contrato`, `aceitar_contrato`. UI com botões + confirmação nos writes.
- **Motivo**: aceite de contrato é **100% Hubtrix** (sem Matrix; chama o HubSoft direto). Sandbox permite testar pela UI (login).
- **PRs**: #9 (consultar + aceitar), #10 (listar modelos + criar). Merged na main.
- **Arquivos**: `apps/integracoes/views.py`, `apps/integracoes/templates/integracoes/integracao_detalhe.html`.
- **Status**: completed (deployado; consultar + listar modelos validados).

## 2026-06-10 — Aceite de contrato HubSoft: BLOQUEADO na API do fornecedor

- **Contexto**: pra abrir OS, o serviço precisa sair de "Aguardando Assinatura de Contrato" (= contrato aceito). Lead 544 / cliente 60005 / serviço 108931.
- **Descoberta**: o contrato **já existe** ("Já existe o contrato '(NUVYON) TERMO DE ADESAO...' ativo"), mas **nenhuma API HubSoft retorna o `id_cliente_servico_contrato`**: `GET /cliente` → `contratos: []`; `POST adicionar_contrato` → "já existe" sem id; `PUT aceitar_contrato` exige o id que não há como obter. (modelo testado = 236, empresa = 74.)
- **Decisão (Lucas)**: **abrir chamado com a HubSoft** (como pegar o id de contrato existente — param `relacionamentos[]`? endpoint dedicado?).
- **Pendência**: trocar `status=502` por `400` no `api_integracao_financeiro_sandbox` (EasyPanel troca 5xx por HTML → "Unexpected token '<'" no front). Atualizar doc de integrações.
- **Status**: **blocked** (aguardando HubSoft). Memória: `hubsoft-aceite-contrato-bloqueio.md`.

## 2026-06-10 — Aceite de contrato DESBLOQUEADO: param `incluir_contrato`

- **Achado (Lucas, na doc HubSoft)**: a consulta de cliente aceita **`incluir_contrato=sim`**, que traz os contratos do serviço (com o `id_cliente_servico_contrato`). Era o que faltava; não depende mais da HubSoft.
- **Ação**: `HubsoftService.consultar_cliente(..., incluir_contrato=True)` manda `incluir_contrato=sim`; a ação `consultar_cliente` do sandbox passa o param. Corrigido também o handler do sandbox de `502` para `400` (+ catch genérico) — erros viram JSON, não HTML (acaba o "Unexpected token '<'").
- **Arquivos**: `apps/integracoes/services/hubsoft.py`, `apps/integracoes/views.py`.
- **Próximo**: deploy → Sandbox → "Consultar cliente" (vem o id do contrato) → "Aceitar contrato" → abrir OS no 544.
- **Status**: completed (código); pending deploy + teste 544.

## 2026-06-11 — OS abre end-to-end (gabriela); nó do 544; bugs do bot

- **WIN — abertura de OS funciona de ponta a ponta**: pro gabriela (lead 548, cliente 60035, serviço 109047), `abrir-atendimento` + `abrir-os` via wrappers (token) → **OS 245261 criada** ("ATIVACAO RES FIBRA", status pendente, agendada 12/06 07:00, técnico 221). Confirma que a camada de OS funciona quando o serviço está em "Aguardando Instalação". (OS é real — cancelar no painel se for só teste.)
- **Nó do 544 (ainda aberto)**: serviço 108931 preso em "Aguardando Assinatura de Contrato" → OS trava. O contrato foi **aceito via API** (`aceitar_contrato` 178542, "1 contrato aceito com sucesso"), mas **o aceite via API NÃO move o status do serviço**. Curioso: gabriela tem `contrato_aceito=False` (local) e a OS abriu; 544 tem `contrato_aceito=True` e trava → quem decide é o **status do serviço no HubSoft**, não o flag local. Hipótese: assinar o contrato na conversão (wizard) move o serviço; aceitar via API depois, não. Pendente: confirmar como o gabriela foi convertido (bot só? manual?) + achar o que transiciona o serviço (assinar no step 4? "Ativar/Habilitar serviço"? painel?).
- **Bug bot — falso sucesso**: `web_driver_conversao_lead/main_refatorado.py:839-845` clica SALVAR + `time.sleep(5)` + declara "✨ SUCESSO" **sem verificar** se o HubSoft converteu. Lead 548 ficou "Não convertido" no HubSoft mas o bot reportou sucesso. Fix: verificar a conversão real pós-SALVAR (capturar erro/modal + confirmar) antes de marcar sucesso.
- **Bot não redeployado (PR #7)**: erros `null value in column prioridade` + `invalid input syntax for type json ('sucesso')` no `salvar_prospecto`. O código atual TEM o fix (prioridade=1 linha 233, `Json()` linhas 197/232), mas o `hubtrix_bot_nuvyion` roda versão antiga. **Falta redeploy do bot.**
- **Status stale no /vendas/**: `_status_ciclo` (dashboard/views.py:405) lê `servico.status_prefixo` (espelho local), congelado em 09/06 (`sincronizar_servicos` off) → mostra "instalação" quando o real é "assinatura". A tela de lead mostra o real. Fix: ligar/rodar `sincronizar_servicos` ou unificar a fonte.
- **Status**: OS = completed (validado no gabriela). Nó 544 + bugs do bot + sync stale = pending.

## 2026-06-12 — BUG raiz: polling do gate (hubsoft-status) caía na página de login

- **Sintoma (Lucas)**: mesmo um lead que passa o gate no banco (Joao Henrique 550 — cliente 60050, docs 3/3, contrato aceito) **não é redirecionado pro turno** no flow Matrix. A etapa de agendamento de OS nunca surgia pela conversa.
- **Diagnóstico**: o nó de polling do flow (`api_21`) chama `{#url_api}/integracoes/api/lead/hubsoft-status/`. Essa rota está no mount `/configuracoes/integracoes/` (**protegido por login**), então a chamada **retorna a página de LOGIN (HTML), não o JSON**. Prova: `GET /api/consultar/leads/` (mesmo flow, mount `/api/`, token-auth) → JSON ok; `GET /integracoes/api/lead/hubsoft-status/` (com token) → HTML/login. Sem o JSON, o flow não lê `eh_cliente_hubsoft`/`documentacao_validada` → o gate (dec_16/19/20) **nunca passa** → nunca avança pro turno. Explica por que a OS sempre foi aberta manual (via token + wrappers), nunca pela conversa.
- **Fix**: expor a **mesma view** (`api_lead_hubsoft_status`, que já tem `@api_token_required`) no mount **token-auth** `/api/public/n8n/` → nova rota `GET /api/public/n8n/lead/hubsoft-status/?lead_id=<id>`. Não mexe na rota antiga (o UI logado segue usando). Arquivo: `apps/integracoes/urls_n8n_public.py`.
- **Lado Matrix (Lucas)**: trocar a URL do `api_21` no flow de `{#url_api}/integracoes/api/lead/hubsoft-status/?lead_id={#id_lead}` para `{#url_api}/api/public/n8n/lead/hubsoft-status/?lead_id={#id_lead}`.
- **Status**: completed (código + doc); pending deploy + trocar URL no flow + teste e2e (o flow avançar pro turno).

## 2026-06-14 — Painel de Ordens de Serviço (Nuvyon)

- **Ações**: Criado painel `/configuracoes/integracoes/ordens-servico/` que registra cada tentativa de `abrir-os/` via Matrix com payload + resposta HubSoft + motivo de falha categorizado. Lista paginada com filtros (status, cidade, técnico, datas), KPIs do dia (total/sucesso/falha/taxa/top 3 motivos), detalhe agrupado por `id_atendimento_hubsoft` com histórico de tentativas, botão "Re-tentar" com modal (ajusta slot/técnico).
- **Motivação**: `abrir-os/` com 71% de erro (5 falhas / 2 sucessos em 7d) sem visibilidade. Resolve o gargalo + habilita evolução futura (conciliação automática).
- **Arquivos novos**: `apps/integracoes/models_os.py` (model `OrdemServicoTentativa`), `migrations/0015_ordemservicotentativa.py`, `services/hubsoft_errors.py` (categorizador regex), `views_ordens_servico.py` (lista/detalhe/retentar), 2 templates, 2 funcionalidades novas em `seed_funcionalidades.py`.
- **Patch**: `views_matrix_os.abrir_os` agora persiste tentativa antes/depois da chamada HubSoft. Resposta JSON pro Matrix **inalterada** (contrato preservado). Categorização cobre `tecnico_ocupado`/`slot_indisponivel`/`data_invalida`/`id_invalido`/`outro`.
- **Permissões**: `integracoes.ver_ordens_servico` (atendente) e `integracoes.gerenciar_ordens_servico` (gerente/admin para re-tentar).
- **Doc**: [07-ORDENS-SERVICO.md](07-ORDENS-SERVICO.md). Sub-nav provisório em Sistema/Integrações (localização final pendente decisão).
- **Status**: completed local. **Pending**: deploy prod, rodar `seed_funcionalidades` em prod, atribuir funcionalidades aos perfis do tenant Nuvyon.

## 2026-06-14 — Painel de Contratos (Nuvyon)

- **Ações**: Painel `/configuracoes/integracoes/contratos/` espelha o de OS, agora pra tentativas de **criar/aceitar contrato HubSoft** via engine de automação. Captura cada execução das ações `_acao_gerar_contrato_hubsoft` (cria + anexa docs + aceita) e `_acao_assinar_contrato_hubsoft` (só aceita) — payload, resposta HubSoft, motivo de falha categorizado, qual etapa parou (criar/anexar/aceitar).
- **Modelo + migration**: `ContratoTentativa(TenantMixin)` em `apps/integracoes/models_contrato.py` + migration `0016_contratotentativa.py`. Granularidade: 1 tentativa = 1 execução de ação. Campos: grupo_id (UUID), tentativa_numero, ação (`gerar`/`assinar`), etapa (`criar`/`anexar`/`aceitar`/`completo`), status (`sucesso`/`falha`/`pendente`/`pulado_idempotente`), motivo categoria + 8 categorias específicas de contrato.
- **Patches engine**: `_acao_gerar_contrato_hubsoft` e `_acao_assinar_contrato_hubsoft` em `automacao_pipeline.py` agora usam helpers de tracking (`services/contrato_tracking.py`). Cada subtarefa do `gerar` (criar/anexar/aceitar) marca a etapa correta. Anexos guardam snapshot de metadados (nome/tamanho/mime).
- **Categorizador**: estendido `services/hubsoft_errors.py` com `categorizar_falha_contrato` (8 categorias: `contrato_ja_existe`, `cliente_sem_servico`, `modelo_nao_encontrado`, `documento_rejeitado`, `dados_invalidos`, `token_expirado`, `cliente_inexistente`, `outro`).
- **Views/URLs**: `views_contratos_tentativas.py` com lista + KPIs + detalhe + retentar. URLs em `/configuracoes/integracoes/contratos/`. Retentar delega pra própria ação do engine (mantém idempotência: se lead já tem `contrato_aceito=True`, retorna sem chamar HubSoft).
- **Templates**: 2 novos (lista + detalhe), reusam design system.
- **Permissões**: `integracoes.ver_contratos` (atendente) + `integracoes.gerenciar_contratos` (gerente/admin para re-tentar). Adicionadas em `seed_funcionalidades.py`.
- **Sub-nav**: entrada "Contratos" ao lado de "Ordens de Serviço" em Sistema/Integrações.
- **Doc**: [08-CONTRATOS.md](08-CONTRATOS.md). README atualizado.
- **Status**: completed local. **Pending**: deploy prod, `seed_funcionalidades` em prod, atribuir funcionalidades aos perfis.

## 2026-07-11 — Anonimizador de PII extraído pra módulo compartilhado

- **Ação**: a lógica de mascaramento de PII (nome/CPF/CNPJ/telefone/email) que vivia dentro do command `extrair_historico_matrix.py` (função `_build_anonimizador`) foi extraída pra `apps/integracoes/services/anonimizador.py` — `construir_anonimizador(contato)` (mesma factory, comportamento idêntico) + atalho novo `anonimizar_texto(texto, contato=None)` pra uso avulso sem manter a closure.
- **Motivo**: a engine de automação precisava da mesma lógica no nó `matrix_atendimento` (transcript de atendimento) sem duplicar regex/regras. O command passou a importar do módulo novo; comportamento verificado idêntico (import roda limpo via `manage shell -c "from ... import Command"`).
- **Arquivos**: `apps/integracoes/services/anonimizador.py` (novo), `apps/integracoes/management/commands/extrair_historico_matrix.py` (import trocado, função local removida).
- **Status**: completed (local). NÃO commitado, NÃO deployado.

## 2026-07-13 — Espelho HubSoft congelava no status da venda (KPI "Instalacoes pendentes" inflado)

- **Contexto**: o dono estranhou "de 124 vendas, 100 instalacoes pendentes?" no painel de relatorios. Investigacao em prod (read-only) provou que o numero e artefato, nao realidade.
- **Causa raiz**: o cron `sincronizar_clientes` consulta cada cliente UMA unica vez (no momento em que a venda e processada) e depois o exclui das proximas rodadas (`qs.exclude(pk__in=ids_ja_sincronizados)`). Naquele instante o servico esta sempre "Aguardando Instalacao", porque acabou de ser vendido. Quando o tecnico instala, o HubSoft muda e o espelho NAO fica sabendo. O `sync_base_clientes_hubsoft` (que varreria `/cliente/todos` e reatualizaria todo mundo) NAO esta no cron: zero chamadas em 14 dias no LogIntegracao; so rodou uma vez, no bootstrap de 17/06 (998 clientes).
- **Evidencia (prod, nuvyon)**: 1101 de 1130 clientes NUNCA foram reatualizados desde que entraram. Dos 100 "aguardando instalacao", 93 sao vendas do funil. Dos 124 clientes vindos do funil, so 25 aparecem habilitados — e 19 desses so porque foram reconsultados por acaso. Zero clientes com `ativo=False` e zero servicos cancelados: o espelho nunca ve ninguem cancelar.
- **Efeito colateral no CS**: o modulo de sucesso do cliente le esse espelho. Churn/suspensao/cancelamento sao invisiveis enquanto o status congelar.
- **PERIGO ENCONTRADO (o motivo do comando novo)**: `ServicoClienteHubsoft` tem post_save em dois lugares (`crm/signals.py` -> engine de regras do pipeline; `automacao/signals_dominio.py` -> evento de dominio). A engine do CRM tem regras ATIVAS na nuvyon que ESCREVEM NO HUBSOFT (#23 criar prospecto, #24 atualizar prospecto, #19 gerar contrato) e movem oportunidade (#22 -> Perdido). Rodar o `sync_base_clientes_hubsoft --full` salvaria ~1460 servicos via ORM e acordaria a engine uma vez por servico. Ela TEM trava de idempotencia, mas o risco (contrato reemitido pro cliente) nao compensa por um card de dashboard.
- **Acao**: command novo `atualizar_status_servicos_hubsoft`. Consulta a API (GET), compara e grava com `queryset.update()`, que NAO dispara signals. `--dry-run` so relata a defasagem; `--escopo pendentes` (default) so os `aguardando_*` (os que congelam); `--escopo todos` varre a base pra pegar cancelado/suspenso (util pro CS). Sem PII no output.
- **Nota**: o lote de 998 clientes de 17/06 esta CORRETO e nao contamina o painel comercial (17 dos 18 widgets leem `oportunidade`/`lead`; so o #74 le HubSoft). A hipotese inicial de "limpar os clientes importados" foi descartada: apagar daria trabalho e nao corrigiria nada.
- **Status**: comando pronto e `check` limpo. PENDENTE: deploy + rodar `--dry-run` em prod (o dono nao tem shell aqui; roda no console do EasyPanel), depois aplicar e agendar no cron (senao congela de novo amanha).

## 2026-07-13 — Reconciliacao aplicada em prod (nuvyon): card de instalacoes cai de 100 pra 56

- **Acao**: `atualizar_status_servicos_hubsoft --tenant nuvyon` (escopo pendentes) rodado em prod via SSH, com autorizacao nominal do dono. Antes, `--dry-run` provou a defasagem sem gravar.
- **Output**: 117 servicos verificados, **57 defasados corrigidos**, 0 erros de API. Transicoes: 34x aguardando_instalacao -> servico_habilitado, 13x aguardando_instalacao -> aguardando_assinatura_contrato, 9x aguardando_assinatura_contrato -> servico_habilitado, 1x aguardando_migracao -> servico_habilitado.
- **Efeito**: KPI "Instalacoes pendentes" (widget #74, dash #15) caiu de **100 pra 56** — quase metade era fantasma. Servicos ativos subiram de 1312 pra 1356. Backlog real de venda nao entregue: 73 (56 instalacao + 17 assinatura), nao 114.
- **Confirmado**: a engine de regras NAO foi acordada (gravacao via `queryset.update()`), nenhum contrato reemitido, nenhuma oportunidade movida.
- **PENDENTE (senao volta a congelar)**:
  1. `--escopo todos` (1130 clientes, ~6-10 min de API): o escopo `pendentes` nao olha os habilitados, entao **cancelamento e suspensao seguem invisiveis** (o banco ainda diz 0 clientes inativos, o que e falso). E o que destrava o modulo de CS pra enxergar churn.
  2. **Agendar no cron** (delta diario + full semanal). Sem isso o espelho congela de novo a partir de amanha.
  3. Widgets #87 (Cancelados) e #88 (Suspensos) do dash #17 filtram valores que nao existem (`servico_cancelado`/`servico_suspenso`); os reais sao `suspenso_debito` (11) e `suspenso_pedido_cliente` (3). Hoje mostram 0.
- **Status**: completed (reconciliacao dos pendentes). Itens 1-3 pendentes.

## 2026-07-14 — Atribuicao por telefone (Talk): match resistente, alerta e auditoria

- **Como o dono chegou aqui**: "esse caiu no telefone pra Flavia e nao atribuiu pra ela". A op #2628 ESTAVA com ela — foi atribuida 7 min depois da criacao (o sync roda a cada minuto e a chamada demora a aparecer no Talk). O dono viu a tela na janela em que a oportunidade ainda estava orfa. **Nao era bug.**
- **O que a investigacao achou de verdade** (3 coisas):
  1. **A chamada do Talk NAO traz `cod_agente`** — so `nom_agente`, e com prefixo: `"1- Flavia"`. Entao o match e por TEXTO contra o catalogo (`listar_agentes`), que aí sim tem o codigo, e esse codigo cruza com `PerfilUsuario.cod_talk`. Ponte de 2 saltos apoiada num nome livre digitado do lado deles: **se renomearem o agente, a atribuicao para em silencio**.
  2. **As oportunidades orfas de verdade sao ligacoes NAO ATENDIDAS**: o Talk devolve `nom_resposta='Ocupado'` e agente vazio. Nao ha a quem atribuir — o sistema esta certo. Mas elas ficam invisiveis, e sao **cliente que ligou e ninguem atendeu**, parado ha dias.
  3. **Ligacao ATENDIDA sem match morria num contador** (`sem_agente_atendeu=7`), que juntava 3 falhas diferentes.
- **Feito**:
  1. **Match em 2 niveis**: exato (normalizado) e, se falhar, por PRIMEIRO NOME ignorando prefixo numerico e pontuacao (`"1- Flavia"`, `"01 - Flavia"`, `"Flavia Almeida"`, `"FLAVIA"` -> todos casam). Se o primeiro nome for AMBIGUO (duas "Ana"), **nao atribui**: chutar vendedora e pior que nao atribuir.
  2. **Alerta novo `agente_sem_match`**: ligacao atendida cuja vendedora nao conseguimos identificar vira ALERTA (com dedup por oportunidade — o cron roda a cada minuto), com o motivo e o conserto na mensagem. Antes so aparecia se alguem fosse investigar na mao.
  3. **Comando `auditar_agentes_talk --tenant <slug>`**: mostra agente do Talk SEM usuario aqui (vai gerar orfa) e `cod_talk` cadastrado aqui que nao existe mais la (cadastro morto). Hoje sao 13 usuarios com cod_talk de 27 — ninguem sabia quem faltava.
- **Migration**: `sistema.0015_alter_alertasistema_tipo` (so acrescenta o tipo de alerta ao choices; nao toca dado).
- **Diagnostico util no caminho**: `consultar_chamadas_talk --tenant <slug> [--telefone|--oportunidade] [--dias N]` mostra a resposta CRUA da API e testa variacoes do numero (sem 9o digito, com DDI) e dias anteriores.
- **PENDENTE (decisao do dono)**: o que fazer com as oportunidades de **ligacao nao atendida** (Ocupado). Hoje ficam orfas e invisiveis. Proposta: distribuir automaticamente pra alguem retornar o contato — cada uma e um cliente que quis comprar e nao conseguiu falar com ninguem.
- **Status**: completed (dev). Deploy pendente.

## 2026-07-15 — Ligacao do Talk vira contato na timeline da oportunidade (tarefa #199)

- **Pedido do dono**: a ligacao nao ficava no historico da oportunidade e deveria ficar. Tarefa criada ANTES do codigo (dessa vez).
- **Causa**: o importador do Talk cria lead + oportunidade mas NAO registra HistoricoContato. A timeline JA sabe mostrar contato (tipo 'contato', de HistoricoContato) — faltava so criar o registro. Os dados vem do endpoint listar_chamadas_por_telefone (o mesmo do sync_vendedores_matrix).
- **Feito**:
  - Status novo `ligacao_atendida` em HistoricoContato.STATUS_CHOICES (o campo e CharField SEM choices, entao NAO precisou migration; a lista e so pra exibicao). Usar esse rotulo em vez de reaproveitar 'fluxo_inicializado' (que apareceria como 'Fluxo Inicializado' pra uma ligacao, confuso pra Gabi).
  - `services/registrar_ligacoes_talk.py` + comando `registrar_ligacoes_talk --tenant <slug> [--dias N] [--dry-run]`. Cria 1 HistoricoContato por ligacao, idempotente por cod_cdr (guardado em dados_extras). Separado da atribuicao de proposito: logar a ligacao vale pra TODA oportunidade, nao so as sem dono. Serve de cron (--dias curto) e de backfill (--dias grande).
  - Mapa de status: Atendida->ligacao_atendida, Ocupado->ocupado, resto->nao_atendeu. Guarda duracao (num_seg_bilhetado), agente, e o nom_arquivo da gravacao em dados_extras.
  - funil_macro passa a contar `status__in=['fluxo_inicializado','ligacao_atendida']` como atendimento (antes subcontava as vendas que entram por telefone).
- **BONUS resolvido junto**: o card "leads sem contato" para de marcar como nunca-contatado quem chegou por ligacao; ligacao NAO atendida (Ocupado) tambem vira registro visivel.
- **Validado (dev, com API do Talk injetada)**: funcoes puras; cria 2 contatos e a 2a rodada cria 0 (idempotente); timeline vai de 0->1; funil atendimentos 272->273; card sem-contato deixa de contar o lead.
- **RESSALVA**: guardamos o nome do arquivo da gravacao, mas TOCAR o audio depende do endpoint de download do Talk (pendente com a Matrix do Brasil) — fast-follow.
- **PENDENTE**: rodar o backfill (--dias grande, 1x) pras ligacoes ja importadas; agendar no cron (--dias curto). Deploy pendente.
- **Status**: completed (dev).

## 2026-07-22 — Pagina de reconciliacao Hubtrix x HubSoft (tarefa 219)

- **Acao:** criar `/configuracoes/integracoes/reconciliacao/`, pagina recorrente
  que compara o funil do Hubtrix com o que veio do HubSoft.
- **Motivacao:** a Nuvyon questionou varios numeros em sequencia (276 vendas no
  HubSoft x 240 no painel, 1226 leads x 1111, "Mococa tem 2") e **cada resposta
  exigiu investigacao manual no banco**. A pagina troca isso por uma tela.
- **Decisao de arquitetura:** le **so dado local**. O HubSoft tem timeout de 30s
  com ate 3 tentativas (pior caso ~94s), o que tornaria a pagina inutilizavel.
  Como contrapartida obrigatoria, `confiabilidade_espelho()` mede o quanto o
  espelho esta defasado e a tela mostra isso **antes** dos numeros: sem esse
  aviso a pagina passaria a impressao de que o lado HubSoft esta completo,
  quando lead parado em rascunho nunca chega la.
- **Onde ficou:** irma de `/integracoes/saude/`. Aquela olha a saude das
  CHAMADAS (latencia, taxa de sucesso); esta olha a consistencia dos DADOS.
- **Output:**
  - `apps/integracoes/services/reconciliacao.py`: dataclass `Divergencia` +
    `comparar_vendas`, `comparar_leads`, `comparar_espelho`, `qualidade_campos`,
    `confiabilidade_espelho` e `montar_reconciliacao`.
  - `apps/integracoes/views.py`: `reconciliacao_view`, com janela de dias
    saneada (1 a 365, lixo cai no default 30).
  - `apps/integracoes/templates/integracoes/reconciliacao.html`.
  - `tests/test_integracoes_reconciliacao.py`.
- **Dois bugs meus, achados rodando contra os dados reais antes de commitar:**
  1. `comparar_espelho` usava o total do espelho como intersecao. Como o espelho
     tambem recebe cliente da sync em massa (1006 orfaos sem lead), a intersecao
     ficava MAIOR que um dos lados e a tela exibia "so nossos: **-153**". Passou
     a contar so cliente com lead vinculado, e o dataclass ganhou um
     `__post_init__` que **levanta ValueError** se a intersecao for incoerente:
     falhar e melhor que exibir numero impossivel.
  2. `qualidade_campos` media "vendas ganhas sem plano" contra o total de LEADS.
     Dava 3,1%, um numero bonito e errado. Cada linha passou a ter seu proprio
     denominador (`base` + `universo`); o valor certo e **11,9%**, que bate com a
     estimativa de 12 a 14% de receita subcontada apurada em 21/07.
- **Numeros reais da Nuvyon no dia da entrega (22/07):** espelho `incompleto`,
  843 leads presos em rascunho, 1236 clientes espelhados. Vendas 30d: 312 ganhas
  no CRM x 207 clientes novos, com intersecao de apenas 166. Espelho: 1083 leads
  enviados x 230 que viraram cliente. Qualidade: 69,5% sem cidade, 52,2% sem CPF,
  11,9% das vendas sem plano.
- **Status:** completed

### Adendo: as duas paginas estavam inalcancaveis

Ao ser perguntado "como eu acesso essa pagina?", descobri que tinha construido a
reconciliacao **sem nenhuma entrada de navegacao apontando pra ela** — so por
URL digitada. E pior: a pagina de **saude das integracoes ja estava assim havia
meses**, tambem sem link nenhum, provavelmente nunca usada.

Os dois botoes entraram no cabecalho de `/configuracoes/integracoes/`, com
comentario no template explicando por que estao ali.

Fica a licao pro checklist de feature (secao 14): **pagina sem rota de navegacao
nao esta entregue**, mesmo com view, template e teste prontos.

### Correcao imediata: o guard pegou um bug meu ja deployado

Commitei e deployei o `4c45e033` com 18 testes verdes e a pagina renderizando
200, mas **sem esperar a suite fechar**. Ela fechou depois do push, com 1 falha
que era do codigo de producao, nao do teste:

```
ValueError: Espelho de clientes: intersecao (1) maior que um dos lados (nossos=0, deles=1)
```

`comparar_espelho` contava "leads enviados ao HubSoft" por uma whitelist de
status (`processado` + `rascunho_hubsoft`). Só que **quando o lead vira cliente o
sync troca o status pra `convertido_cliente`** (`hubsoft.py:271`). Esses saiam do
lado "nossos" e continuavam no lado "viraram cliente", violando a invariante e
derrubando a pagina com 500.

Nao quebrava na Nuvyon (968 enviados x 230 clientes, a desigualdade nao dispara),
mas quebraria em qualquer tenant com poucos leads e a maioria ja convertida.

**Fix:** "chegou ao HubSoft" passou a ser `tem id_hubsoft OU ja tem cliente
espelhado OU esta em rascunho`. A clausula do cliente garante **por construcao**
que a intersecao seja subconjunto. Severidade passou a comparar presos contra o
total enviado, em vez de contra `processados`, que deixou de existir.

Dois testes novos travam o cenario, incluindo o exato que quebrou.

**Licao:** evidencia boa nao e evidencia completa. O unico teste que faltava era
justamente o que pegou o bug. Nao pushar antes da suite fechar.

## 2026-07-22 — Reconhecer prospecto ja convertido em cliente (tarefa 220)

- **Acao:** parar de travar o lead exigindo os 8 campos do pre-flight quando o
  prospecto **ja virou cliente** no HubSoft.
- **Causa:** o pre-flight roda antes de tudo e bloqueia por campo faltando. Mas
  ele existe pra proteger a EDICAO do prospecto, e prospecto convertido nao pode
  mais ser editado: o HubSoft recusa com *"Prospecto foi convertido para o
  cliente. Nao e possivel alterar"*. A trava estava no lugar errado da ordem.
  O `editar_prospecto` ja tinha guard parecido, mas so olhava o espelho LOCAL —
  se o cliente ainda nao tinha sido espelhado, o guard nao via.
- **Diagnostico que levou ate aqui (medido em prod, planilha da Gabi 01/07-20/07):**
  - 270 clientes compraram; 144 no nosso espelho; **126 fora**.
  - Dos 126, consultando o HubSoft por `codigo_cliente` pra obter o CPF:
    **54 JA ERAM LEAD NOSSO**, 70 sao cliente antigo recontratando, 2 erro.
  - Dos 54: 30 travaram por falta de dado (nascimento 28, email 23, numero 18,
    cep 12, rg 3) e 24 estavam completos.
  - O endpoint `/cliente` do HubSoft **nao devolve endereco**, entao nem daria
    pra preencher CEP e numero a partir dele. Reconhecer a conversao e o unico
    caminho que resolve os 30.
- **Taxa de espelhamento por status (a causa estrutural):** `processado` 226/246
  (92%), `convertido_cliente` 5/12 (42%), `rascunho_hubsoft` 0/851 (0%),
  `pendente` 1/63 (2%). O sistema tem uma porta so, e **todo status que nao seja
  `processado` e terminal** — nao ha varredura, retry nem fila de recuperacao.
- **Output:** `_reconhecer_cliente_existente()` em
  `apps/integracoes/services/hubsoft_prospecto_rascunho.py`, chamado **antes** do
  gate do pre-flight. Se o lead ja tem cliente espelhado, resolve local sem API.
- **Duas salvaguardas, decididas com o dono:**
  1. **So age com resposta real da API.** Erro de consulta devolve `None` e segue
     o fluxo normal, falhando visivelmente. Nunca deduz por texto de mensagem.
  2. **Confere que o CPF devolvido bate com o perguntado.** O `clientes[0]` da API
     e pego sem validacao; amostra de 20 deu zero divergencia, mas depender disso
     vincularia a pessoa errada no dia em que o HubSoft mudar a busca.
- **Aceito pelo dono:** o lead reconhecido por esse caminho fica com campos vazios.
  Vira cliente com cadastro incompleto, e isso passa a ser visivel na pagina de
  reconciliacao em vez de escondido.
- **Testes:** `tests/test_integracoes_prospecto_ja_cliente.py`, 8 casos, com o peso
  nas salvaguardas (CPF divergente nao vincula e mantem o status intacto, erro de
  API segue o fluxo, lead sem CPF nem consulta, CPF pontuado bate com o limpo).
- **Dry-run em prod antes de aplicar:** 54 leads seriam reconhecidos (48 com venda
  ganha), **zero bloqueados pela salvaguarda de CPF**, 54 `ClienteHubsoft` criados.
  Cobertura da planilha da Gabi sairia de 53% para 73%.
- **Status:** completed

## 2026-07-22 — Reconciliacao de julho aplicada em prod (tarefas 219, 220)

Investigacao longa a partir de duas planilhas exportadas pela Gabi (Nuvyon).
Resultado da reconciliacao das vendas de 01/07 a 20/07:

| | Antes | Depois |
|---|---|---|
| Clientes da planilha no nosso espelho | 144/270 | **219/270** |
| Com venda ganha no CRM | 138 | **214** |
| Leads com CPF preenchido | 517 | **607** |
| Presos em `rascunho_hubsoft` | 851 | **799** |

**O que foi aplicado:**
1. Fix da tarefa 220 nos 54 leads que ja eram cliente no HubSoft: 54/54
   reconhecidos, zero pulados pela salvaguarda de CPF, zero erros.
2. 21 clientes vinculados por match de telefone + nome, com o CPF preenchido a
   partir do cliente (era a ausencia de CPF que impedia o match automatico).
3. 12 oportunidades movidas pro estagio de Ganho. **11 vinham de "Perdido"** e
   4 seriam bloqueadas pelo gate de campos obrigatorios; o dono autorizou
   contornar. Cada movimentacao ficou no `LogSistema` com o estagio anterior.

**Erro meu, registrado:** eu disse ao dono que seriam 5 ou 6 movimentacoes e
foram **12**. Contei so as que vinham dos 54 recem-espelhados, mas o script
identificou pelo conjunto todo da planilha. A trava que coloquei ("abortar se
passar de 12") bateu exatamente no limite e nao protegeu.

**Diagnostico das 51 que continuaram fora** (consultando `origem_cliente` na API):

| Origem | Qtd | Natureza |
|---|---|---|
| WHATSAPP ATIVO | 16 | vendedora inicia do numero dela, sem passar pelo bot |
| (origem em branco) | 11 | cadastro apressado |
| INDICACAO / PRESENCIAL / LIGACAO | 15 | nunca teve conversa digital |
| WHATSAPP EMPRESA (MATRIX) | 5 | **anomalia: canal integrado que escapou** |
| SITE / Vendedor Externo | 2 | |

Comparando com quem ESTA no funil: WhatsApp Empresa e 57% dos capturados e so
10% dos perdidos; WhatsApp Ativo e o inverso, 11% contra 33%. **O Matrix
funciona; o problema sao os canais que ele nao cobre.**

**19 das 51 sao de vendedoras sem usuario no sistema** (Nicoly 7, Trainee 3,
Damaris 3, Flavia 2...). Nao e indisciplina: elas provavelmente nao tem login.

**Comparacao funil x funil** (planilha de CRM, 842 cartoes x 872 nossos, mesma
janela ate 21/07 08:38): 758 casados por `id_prospecto`, **90% de cobertura**,
concordancia de 72%. A divergencia dominante sao **166 casos em que eles estao
negociando e nos ja demos como perdido** (135 deles em "Assuntos Comerciais").
Nossa taxa de perda e 68% contra 47% deles. Suspeita nao confirmada: automacao
de inatividade fechando cedo demais.

**Dos 84 cartoes que so existem la: 53 sao prospecto DUPLICADO** — ids quase
consecutivos (cartao 24210 x nosso 24211), criados com minutos de diferenca. O
bot cria e a vendedora cria de novo porque nao ve o primeiro.

**Achados de metodo:**
- `id_prospecto` e a melhor chave de reconciliacao: casou 763 contra 232 do CPF,
  porque so 22% dos cartoes tem documento.
- Existe `/api/v1/integracao/crm/all` (catalogo de funis), que nao estava
  mapeado. **Nao existe endpoint de cartoes** — a comparacao de funil depende do
  export manual.
- O CPF da Angelica (lead 2520), que eu vinha tratando como "faltando", estava
  **digitado errado**. O vinculo por telefone corrigiu.
- Leads nomeados `"(60365) LUIZ GUSTAVO"`: as vendedoras colam o codigo do
  cliente no campo nome porque nao tem como ligar as duas pontas. E pedido de
  feature disfarcado.

## 2026-07-22 — Pagina de inconsistencias (tarefa 221)

- **Acao:** `/configuracoes/integracoes/inconsistencias/`, operacional, lista
  caso a caso as vendas que existem no HubSoft e nunca viraram lead aqui.
- **Diferenca pra pagina de reconciliacao:** aquela resume numeros (diagnostico),
  esta lista pra alguem agir.
- **Restricoes do dono, respeitadas:** sem mexer em cron ou servico (busca sob
  demanda, por botao); escopo do mes corrente, nao da base inteira; v1 so lista,
  sem acao de escrita nos casos.
- **Agrupamento por origem**, com **anomalia primeiro**: origem que passa pelo
  canal integrado ("WhatsApp Empresa (Matrix)") ganha destaque, porque venda que
  entra por ali e nao vira lead e falha nossa. Presencial e indicacao ficam
  abaixo, sem alarme, porque sao canais descobertos.
- **O estado do espelho aparece ANTES da lista.** Sem isso, lista vazia pareceria
  "esta tudo certo" quando o real e "nao perguntei" — exatamente o caso da
  Nuvyon, onde `/cliente/todos` **nunca tinha sido chamado em prod** e os 1006
  clientes sem lead vieram de uma carga unica entre 03/06 e 18/06.
- **O botao grava, e avisa.** Usa `sincronizar_base_clientes` com
  `modificados_desde` no inicio do mes (~3 paginas de 100, em vez de ~13 da base
  inteira). O `confirm()` diz que vai gravar no espelho.
- **Testes:** 15 casos, com peso no agrupamento (origem vazia com rotulo proprio,
  anomalia marcada e ordenada primeiro, isolamento por tenant) e no aviso de
  espelho desatualizado.
- **Pendente:** bloco 2 (leads duplicados no HubSoft). Precisa consultar
  prospecto por telefone lead a lead, entao vai com limite explicito por
  execucao, nao num clique so.
- **Status:** completed (bloco 1); pending (bloco 2)

### Reescrita: o criterio certo pra "venda do HubSoft" (tarefa 221)

A primeira versao da pagina lia o espelho local e mostrava zero, porque a
reconciliacao do dia tinha vinculado todos os clientes orfaos de julho. Pior: o
botao "Buscar no HubSoft" chamava `sincronizar_base_clientes` com
`modificados_desde`, que filtra por data de MODIFICACAO — trouxe a base
historica inteira e o espelho saltou de 1236 para 4931 clientes. **Eu tinha
afirmado ao dono que traria "so o periodo", sem ter testado.** Revertido:
3612 clientes e 3821 servicos removidos, preservando os 90 com lead vinculado.

**Tres criterios testados ate achar o certo:**

| Criterio | Resultado | Por que falha |
|---|---|---|
| `data_cadastro_cliente` | 3838 em julho | cliente antigo tem o cadastro atualizado por migracao de plano e recadastro |
| `servico.id_prospecto` | sempre `None` | o HubSoft nao preenche o campo, nem em venda vinda do nosso funil |
| **`servico.data_venda`** | **311** | e o mesmo criterio do relatorio que a Nuvyon usa |

**Correcao levantada pela Gabi:** ela disse que o relatorio dela tinha 337
vendas e nos tinhamos 311. Ela estava certa. A API filtra por **cadastro do
cliente**, entao cliente que virou cliente em marco e contratou outro servico em
julho tem a venda em julho mas o cadastro em marco — e escapava do recorte.

    janela de cadastro so julho .... 311 vendas (39 paginas)
    janela desde 01/01 do ano ...... 348 vendas (59 paginas)

As 37 de diferenca sao exatamente clientes cadastrados de janeiro a junho. A
busca passou a usar a janela do ano corrente.

**Limite que fica, e a tela declara:** cliente cadastrado antes do ano corrente
que compre hoje ainda escapa. Cobrir 2024 em diante custaria 165 paginas (~4
min). Preferimos numero levemente incompleto e declarado a numero completo e
inutilizavel.

**O que a pagina mostra** (medido em 22/07, janela so de julho):

    311 vendas no HubSoft
    ├── 230 tem lead E venda ganha aqui        [certo]
    ├──  17 tem lead (CPF), sem venda marcada  [recuperavel]
    ├──   3 tem lead (casou por telefone)      [recuperavel]
    └──  61 nao existe no CRM                  [fora]

Os 61 por origem: WhatsApp Ativo 15, sem origem 15, **transferencia de
titularidade 13**, presencial 6, indicacao 5, ligacao 4, WhatsApp Empresa 3.

**Transferencia de titularidade nao e venda** — e troca de titular num contrato
existente, e entrava no relatorio do HubSoft como se fosse venda nova. A pagina
separa isso e mostra "venda real fora do funil: 48", nao 61.

**Ordem dos grupos carrega significado:** anomalia (canal integrado que escapou)
primeiro, titularidade por ultimo e esmaecida.

**Cache de 30 min**, porque sao ~59 chamadas de API por leitura. Link
`?atualizar=1` forca. Diferente da primeira versao, **esta nao grava nada**: le
e compara em memoria.

## 2026-07-22 — Pagina de inconsistencias: grupos viram datatable filtravel

- **Acao:** os N grupos por origem da pagina de inconsistencias viraram **uma
  tabela unica** com busca, ordenacao por coluna, paginacao e export CSV. As
  origens viraram **chips de filtro** que escrevem no campo de busca da propria
  datatable (um caminho de filtro so, entao contador/paginacao/CSV saem sempre
  coerentes com o chip ativo). Cada linha ganhou coluna **Origem** e
  **Classificacao** (falha nossa / nao e venda / canal fora do funil).
- **Decisao:** criei componente de DS `templates/components/datatable.html` em
  vez de biblioteca externa. Progressive enhancement sobre uma `<table>` normal,
  entao celula continua com link/badge/formatacao livres. O `.table` do DS so
  desenha a setinha `.is-sortable` mas nao ordena nada; a datatable acrescenta o
  comportamento, nao duplica. Registrado no showcase `/design-system/componentes/`.
- **Motivo:** com tabela unica da pra ordenar por data, buscar por nome e
  exportar o conjunto inteiro, o que a versao agrupada nao permitia. Pedido do
  dono ("transforme isso numa datatable").
- **Servico:** `inconsistencias.py` ganhou `Venda.anomalia/nao_e_venda/tipo_label`
  (a etiqueta que antes so existia no cabecalho do grupo agora resolve por
  linha, porque a tabela e plana). Helpers `_e_anomalia`/`_nao_e_venda`
  compartilhados entre `Venda` e `GrupoOrigem` pra as duas nunca divergirem.
- **Output:** `manage.py check` limpo; render das duas telas ok; 22 testes
  passando (2 novos cobrindo etiqueta por linha e concordancia com o grupo).
- **Achado de lado:** a suite estava levando 3m54 nao por lentidao de teste, e
  sim porque cada rodada recriava o banco de teste do zero (todas as migrations).
  Com `--reuse-db` cai pra ~17s. `pytest.ini` do projeto nao tem `--reuse-db`.
- **Status:** completed

## 2026-07-22 — Aba Oportunidades: matriz funil x funil por upload de planilha

- **Acao:** a pagina de inconsistencias virou duas abas. "Vendas" e a datatable
  de antes. "Oportunidades" e nova: compara nossas OportunidadeVenda com os
  cards do CRM do HubSoft, cruzando por id_prospecto, e mostra cobertura,
  matriz de concordancia 3x3, duplicados e o que so existe de um lado.
- **Fonte do dado deles:** upload manual do export .xlsx do CRM. Confirmado por
  probe que NAO existe API de cards: /crm/all so lista os 43 boards, todo drill
  (crm/4, crm/cards, crm/prospecto) da 404. A planilha e a unica fonte.
- **Chave de cruzamento:** `id_prospecto` do card x **`id_hubsoft` do nosso
  lead** (o id_hubsoft do lead E o id do prospecto que criamos). Primeira
  tentativa usei `id_prospecto_hubsoft` e deu 0 casados: o campo esta vazio em
  prod. Peguei o bug validando o service READ-ONLY contra prod antes do deploy.
- **Validacao contra prod (read-only, sem escrita):** o service reproduz a
  analise da sessao anterior: 764 casados (era 758), concordancia 73% (era 72%),
  deles ABERTO / nos PERDIDO = **166** (identico), duplicados 49 (era 53). As
  diferencas sao exatamente as 34 oportunidades movidas pra Ganho e os leads
  vinculados hoje: o nosso lado e recalculado ao vivo, so o lado deles depende
  do upload.
- **Componentes:** model `ImportacaoCRMHubsoft` (JSONField com os cards,
  migration 0019); service `oportunidades.py` (parse_planilha, situacao_deles,
  montar_aba); openpyxl no requirements; view com abas + POST de upload; template
  reusando o componente datatable e o tabs do DS.
- **Mapa etapa deles -> situacao:** CADASTRO APROVADO=ganho; DESIST* / CREDITO
  NEGADO / VIABILIDADE NEGATIVA=perdido; o resto=aberto (negociacao viva).
- **Output:** `manage.py check` limpo; 26 testes novos + 22 de inconsistencias,
  48 passando; render das duas abas validado.
- **Escopo declarado na tela:** a aba reflete a planilha enviada COMO ESTA (sem
  filtro de data). O export da Gabi de 21/07 tem 1226 cards de todas as datas
  (cobertura 62%); so a janela de julho dava 90%. Quem define o recorte e o
  export.
- **Status:** completed

## 2026-07-22 — Aba Oportunidades: bucket "sem prospecto vinculado" (id=0)

- **Acao:** os cards com `id_prospecto = 0` viraram bucket proprio e filtravel na
  aba Oportunidades, com KPI e datatable (busca por equipe/vendedor + CSV).
- **Motivo:** na planilha de 21/07 sao **382 dos 1226**. Sao cards abertos direto
  no CRM sem nunca linkar prospecto (CPF "Nao Possui", sem telefone), quase todos
  em VENDAS EQUIPE MOCOCA / ASSUNTOS COMERCIAIS. Nao tem chave pra casar.
- **Correcao junto:** antes eles caiam em "so existem la" (inflava de ~31 pra 413)
  e derrubavam a cobertura (1226 no denominador = 62%). Agora saem da matriz e da
  cobertura, que passa a ser sobre os 844 com prospecto (~91%, bate com os 90% da
  sessao anterior).
- **Prod:** o Lucas ja subiu a planilha em prod (admin_nuvyon, 22/07 23:07, 1226
  cards, 382 com id=0). A feature rodou ponta a ponta.
- **Output:** 27 testes (1 novo cobrindo o bucket); render das abas ok.
- **Status:** completed

## 2026-07-22 — Aba Oportunidades: tabela unica com chips (paridade com Vendas)

- **Acao:** as 4 tabelas empilhadas da aba Oportunidades (Divergencias,
  Duplicados, So existem la, Sem prospecto) viraram UMA datatable com chips de
  categoria em cima, mesmo padrao da aba Vendas (chips de origem).
- **Motivo:** pedido do dono ("oportunidades deveria utilizar o mesmo datatable
  de vendas"). Um caminho de filtro so: contador, paginacao e CSV saem coerentes
  com o chip ativo.
- **Como:** service ganhou `_unificar` que achata os quatro baldes numa lista
  `problemas`, cada linha com `categoria` e um campo `detalhe` que carrega o que
  e especifico (nosso estagio / nosso lead / telefone / equipe). O JS dos chips
  virou funcao `ligarChips` reusada nas duas abas.
- **Output:** 27 testes (1 checando a lista unificada e as categorias); render ok.
- **Status:** completed

## 2026-07-22 — Aba Oportunidades: remove matriz funil x funil (Nuvyon migrou pro nosso CRM)

- **Contexto:** o dono avisou que a Nuvyon **nao usa mais o CRM do HubSoft**,
  opera no nosso. Com isso o card do HubSoft virou retrato congelado e
  "divergencia" (situacao deles x nossa) deixou de significar discordancia,
  virou defasagem.
- **Acao:** removida a comparacao de situacao inteira: matriz funil x funil, KPI
  de concordancia, KPI "eles negociando / nos perdido", categoria Divergencia da
  tabela. Codigo morto apagado (`_matriz_para_template`, `_situacao_nossa`,
  `_ROTULO`, import Counter, CSS `.mtx`).
- **Ficou** o que independe de qual CRM usam: **cobertura de captura** (quantos
  cards estao aqui) e **qualidade de dado** (Duplicado, So existe la, Sem
  prospecto). A aba agora tem 3 chips em vez de 4.
- **Pendencia de escopo (aberta):** se o HubSoft CRM esta 100% morto, a aba vira
  reconciliacao unica daquele export (nao ha planilha nova). Decidir se aposenta
  a aba depende de: a Nuvyon ainda cria prospecto no HubSoft (camada ERP)?
- **Output:** 27 testes (ajustados: matriz/divergencia fora), ruff limpo, render ok.
- **Status:** completed

## 2026-07-24 — Fundacao das rotinas de escrita HubSoft (conversao/novo servico/upgrade)

- **Contexto:** as 3 operacoes de escrita no HubSoft (converter prospecto em
  cliente, novo servico, upgrade de plano) NAO tem API oficial. So existem no
  painel do operador (o robo_v2 fazia via API interna scrapeada + Selenium). Vamos
  reconstruir como rotinas configuraveis na engine de automacao, tudo parametrizado
  por tenant (outros tenants terao outros HubSofts). Confirmado ao vivo na Nuvyon:
  catalogo tem 80 vendedores, 503 planos, grupos/status/formas proprios.
- **Decisao:** as 3 operacoes pelo mesmo caminho (painel), um service
  `hubsoft_painel.py` tenant-aware. Config por tenant num model tipado (nao em
  configuracoes_extras), com guard de dry run por tenant (allowlist de CPF).
- **Acao (Fase 1, fundacao):**
  - Model `PerfilConversaoHubsoft(TenantMixin)`: vendedor/grupo/status/forma/
    vencimentos_map/id_empresa por tenant + `dry_run_forcado` (default True) +
    `cpf_allowlist`. Metodos `dry_run_efetivo` (porte do guard do robo_v2) e
    `id_vencimento`. Migration 0020.
  - Novo tipo `hubsoft_painel` em `IntegracaoAPI.TIPO_CHOICES` (credencial do
    operador; senha em EncryptedCharField; token JWT cacheado em
    configuracoes_extras.cache.painel_token com exp).
  - Varredura `prospectos_por_criterio` (por vendedor/status/marcador/com_id_hubsoft)
    em `apps/automacao/varreduras.py` = o "start por vendedor ou por status".
  - Service `apps/integracoes/services/hubsoft_painel.py`: login Selenium headless
    (email/Validar/senha/Entrar) capturando cookies+JWT, cache de token, `_get/_post`
    com LogIntegracao. Fase 1 so leitura (schema_cache, get_cliente, obter_servico_edit,
    buscar_cep). Factory `hubsoft_painel_do_tenant`.
  - Fontes de opcoes `perfis_conversao_hubsoft` e `integracoes_hubsoft_painel` em
    `apps/automacao/opcoes.py`. Registro do model no admin.
- **Output:** `manage.py check` ok, 12 testes passando (`tests/test_hubsoft_painel_fundacao.py`:
  dry_run_efetivo, id_vencimento, varredura com isolamento por tenant, helpers do painel).
- **Pendente:** spike de login real no painel da Nuvyon (Selenium vs prod, precisa Chrome);
  UI em /configuracoes/integracoes/ pra editar perfil+credencial (por ora so admin);
  Fases 2 a 4 (escritas: conversao, novo servico, upgrade) + nos + seeds.
- **Status:** completed (fundacao); proximo: spike de login e Fase 2 (conversao).

## 2026-07-24 — Rotina de conversao de prospecto (Fase 2)
- **Acao:** primeira rotina de escrita completa (prospecto -> cliente) via API interna
  do painel, ponta a ponta no codigo.
  - `PerfilConversaoHubsoft.template_conversao` (JSONField, migration 0021): o payload
    do POST /api/v1/cliente e gigante e cheio de dados da empresa (servico, contratos,
    forma_cobranca, empresa/CNPJ). Vira template capturado UMA vez por HubSoft e mora
    no perfil, nao no codigo. Decisao de arquitetura: nada de ID magico da Megalink;
    cada tenant captura o seu (alinhado ao plano "templates versionados por perfil").
  - `hubsoft_painel.py`: `montar_payload_conversao` (deepcopy do template + overlay so
    dos campos do lead: identidade, endereco, vencimento, plano opcional, vendedor;
    funcao pura, golden testada). Helpers de escrita `cpf_ja_cadastrado` (pre-check),
    `criar_cliente` (POST /cliente), `buscar_plano_por_id` (so API do painel, sem o
    fallback psycopg2 do robo_v2).
  - Nos: base `HubsoftPainelNode` (saidas sucesso/erro/dry_run, `retry_seguro=False`)
    + `hubsoft_converter_prospecto`. Idempotencia tripla (status_api do lead,
    espelho ClienteHubsoft, cpf_ja_cadastrado no painel) + guard de dry run do perfil
    (so allowlist escreve) + CPF mascarado no output (LGPD).
- **Output:** `manage.py check` ok, 28 testes passando
  (`test_hubsoft_painel_fundacao.py`: +8 do payload; `test_hubsoft_converter_prospecto.py`:
  8 de fluxo/idempotencia/dry-run com service stubado). 2 commits (2a payload+helpers,
  2b no+testes).
- **Bloqueio p/ validacao real:** (1) `template_conversao` do perfil demo-local ainda
  vazio -> conversao real precisa capturar o template daquele HubSoft uma vez (sem
  isso o no sai por `erro` "sem template", que e o comportamento correto); (2) host da
  API interna `api.artelecom.hubsoft.com.br` deu connect-timeout em 24/07 (o host do
  painel conecta; cara de allowlist de IP no lado HubSoft). Login+leitura ja foram
  provados na Fase 1.
- **Status:** completed (codigo + testes da conversao); pendente validacao live
  (captura de template + acesso ao host da API). Proximo: Fase 3 (novo servico) e
  Fase 4 (upgrade), depois seeds dos 3 fluxos.

## 2026-07-24 — Novo servico, upgrade e seeds dos 3 fluxos (Fases 3 a 5)
- **Acao:** completou o motor de escrita no painel.
  - Fase 3/4: builder compartilhado `montar_payload_adicionar_servico` (POST
    /cliente/servico) serve novo servico E upgrade; upgrade so acrescenta os campos
    de migracao (id_cliente_servico_antigo, executar_migracao_imediata, status
    habilitado 11) via param `migracao`. IDs magicos saem do perfil; servico/forma/
    endereco resolvidos pelo no. Novo campo `forma_cobranca_obj` no perfil (migration
    0022) com fallback pelo schema do painel. Nos `hubsoft_adicionar_servico` e
    `hubsoft_migrar_plano` (id_cliente pelo espelho ClienteHubsoft, endereco cadastral
    via get_cliente, idempotencia por plano ativo, dry run, retry_seguro=False).
  - Fase 5: `seed_fluxos_hubsoft_escrita` cria os 3 fluxos (conversao/novo servico/
    upgrade) INATIVOS e em dry run, padrao varredura prospectos_por_criterio -> no ->
    marcador/tarefa/nota. Idempotente por nome. Doc `rotinas-escrita-hubsoft.md`.
- **Output:** 38 testes passando (fundacao + conversao + servico/upgrade), golden dos
  3 payloads. Seed rodado no demo-local: 3 fluxos validados (validar_fluxo) e
  idempotentes (ids 2/3/4, ativo=False). 2 commits (nos 3/4; seed+doc).
- **Pendente:** captura do template_conversao real, acesso ao host da API interna,
  UI de perfil/credencial (hoje admin). Homologar com 1 CPF na allowlist quando os
  dois primeiros destravarem.
- **Status:** completed (Fases 1 a 5, motor completo com testes). Falta validacao
  live e UI.

## 2026-07-24 — Captura real do template_conversao (destrava os 2 bloqueios da Fase 2)

- **Bug achado e corrigido:** `hubsoft_capturar_template.py::_navegar_ate_converter`
  buscava o prospecto pelo id_prospecto no campo de busca do painel HubSoft, mas
  esse campo nao indexa por id, so por nome (nome_razaosocial). A busca sempre
  voltava vazia, entao a captura nunca chegava no wizard. Fix: `_navegar_ate_converter`
  agora recebe `nome_busca` e digita o nome no lugar do id; o `Command.handle` resolve
  o nome via `LeadProspecto.id_hubsoft` (ou aceita `--nome-prospecto` direto). Achado
  um segundo bug no mesmo fluxo: o clique em "Acoes" acertava o CABECALHO da coluna
  "Acoes" da tabela (mesmo texto do botao da linha) em vez do botao real, porque
  `_clicar_texto` nao tinha escopo. Fix: novo param `escopo_xpath` em `_clicar_texto`,
  usado com `//tbody//...` nesse clique especifico pra restringir a linha de resultado.
- **Segundo achado:** a API de cadastro de prospecto (`cadastrar_prospecto` /
  `POST /api/v1/integracao/prospecto`) aceita `data_nascimento`, mas NAO aceita
  `genero` nem `grupo_cliente` — esses dois so existem no wizard de conversao
  (`POST /api/v1/cliente`). Ou seja, pra minimizar campo obrigatorio vazio no wizard,
  o prospecto de teste precisa nascer com `data_nascimento` preenchida (evita ter que
  navegar o date picker Angular Material, que nao aceita digitacao direta, so
  selecao via calendario) — genero/grupo continuam manuais.
- **Acao:** criado prospecto de teste completo (`id_prospecto` 24597, tenant
  demo-local) via `criar_prospecto_para_lead` (mesmo caminho de producao), com
  todos os campos que a API aceita preenchidos (endereco, rg, data_nascimento,
  plano, vencimento). Rodado o comando corrigido contra o painel REAL da Nuvyon
  (`HubSoft Painel Nuvyon (local)`, `api.artelecom.hubsoft.com.br`); conversao
  concluida manualmente no wizard (genero + grupo_cliente + Plano/Contrato/
  Cobranca/Pacotes/OS preenchidos por humano) e o `POST /api/v1/cliente` (30102b,
  26 chaves) capturado com sucesso via CDP performance log.
- **Output:** `PerfilConversaoHubsoft` (tenant demo-local, perfil "padrao") agora
  tem `template_conversao` preenchido (antes vazio, era o 1o bloqueio registrado na
  entrada anterior). O 2o bloqueio (connect timeout no host `api.artelecom.hubsoft.com.br`
  em 24/06) nao se repetiu hoje — o host respondeu normalmente tanto pro cadastro de
  prospecto via API quanto pro painel via Selenium.
- **Nota lateral:** durante a investigacao, tambem corrigido bug nao relacionado no
  CRM (modulo `comercial`, ver execution-log de la): busca de leads em Segmentos
  usava campo inexistente `nome_completo` em vez de `nome_razaosocial`.
- **Validacao do node (via API interna, sem navegador):** com o template capturado,
  rodado `HubsoftConverterProspectoNode.executar()` de verdade (mesmo lead 24597,
  `Contexto(tenant=demo-local, lead=lead)`, `perfil='padrao'`) — a mesma acao que a
  engine de automacao dispara num fluxo real. Resultado: `branch='dry_run'` (perfil
  com `dry_run_forcado=True` e allowlist vazia, entao nao escreve de verdade),
  payload montado por `montar_payload_conversao` batendo com o que foi capturado
  manualmente (nome, cpf, data_nascimento, genero, grupo RESIDENCIAL, endereco
  resolvido via `buscar_cep` real, servico NUVYON 100MB, contrato, forma_cobranca,
  vencimento). Confirma que o caminho de producao (node da engine, sem Selenium
  clicando em nada, so login via token cacheado) esta pronto pra uso real; falta
  so decidir quando tirar `dry_run_forcado` ou adicionar CPF na allowlist pra
  validar uma escrita de verdade.
- **Status:** completed. `hubsoft_capturar_template.py` corrigido; template de
  conversao do demo-local capturado e validado ponta a ponta contra o HubSoft real
  da Nuvyon, tanto via wizard manual quanto via node da engine em dry run. Falta:
  abrir tarefa correspondente no Workspace (prod), decidir sobre cleanup do
  prospecto/cliente de teste 24597 na Nuvyon.

## 2026-07-24 — Validacao de escrita real (node via editor) + seed do fluxo de teste

- **Bug de config descoberto no proprio teste:** o campo "Forcar simulacao" do no
  `hubsoft_converter_prospecto` nasce ligado por padrao (`dry_run` ausente no config
  do no => `flag(None, True)` => `dry_run_pedido=True`), o que faz
  `PerfilConversaoHubsoft.dry_run_efetivo` retornar `True` **antes** de checar a
  allowlist. Ou seja: adicionar o CPF na allowlist do perfil nao basta sozinho pra
  liberar escrita real num fluxo do editor; o no tambem precisa `dry_run: 'false'`
  explicito no config. Isso nao e bug de produto (e uma segunda trava de seguranca
  deliberada, dupla: perfil + no), so nao documentada onde alguem for montar um
  fluxo de teste do zero. Vale um aviso no editor futuramente.
- **Acao:** criado um segundo lead de teste completo (`id_prospecto` 24598, CPF
  valido gerado, mesmos dados do 24597) via API de cadastro; montado fluxo minimo
  `Carregar lead -> hubsoft_converter_prospecto` no editor de automacao; CPF do lead
  liberado pontualmente na allowlist do perfil `padrao`; `dry_run: 'false'` setado
  no no; clicado "Testar" no editor local (`/automacao/editor/`). Rodou de verdade.
- **Resultado real confirmado via `LogIntegracao`:** `POST /api/v1/cliente` (200,
  sucesso) criou o cliente **(64250) [TESTE HUB] CONVERSAO REAL PRODUCAO** na
  Nuvyon, grupo RESIDENCIAL, com endereco/servico/contrato/forma_cobranca corretos
  (o mesmo template capturado na entrada anterior). Confirma o node da engine
  funcional ponta a ponta em producao, disparado 100% pela UI do proprio Hubtrix
  (sem Selenium clicando em nada — so a chamada de API, com login cacheado).
  Allowlist e o `ativo` do fluxo revertidos pro estado seguro logo em seguida.
- **Nota sobre "Execucoes":** clique manual em "Testar" no editor NUNCA persiste em
  `ExecucaoFluxo` (so gatilho real — agenda/webhook/evento). Pra um registro
  persistido seria preciso `executar_e_persistir()` via um gatilho de verdade
  (ex: webhook), que ficou fora do escopo desta sessao (ação bloqueada pelo
  classificador de seguranca do proprio Claude Code por envolver escrita real via
  endpoint publico).
- **Seed novo:** `seed_fluxo_demo_conversao_hubsoft` (management command,
  `apps/automacao`), idempotente por nome, cria o fluxo minimo de 2 nos pra
  qualquer `--tenant`/`--lead-id`/`--perfil`. Nasce inativo, sem override de
  `dry_run` no perfil (so no no, se quem chamar decidir setar via `--nome`/edicao
  manual depois). Fluxo de teste local recriado via esse seed (id=7, lead 24598).
- **Checkout mixup encontrado e corrigido:** o fix de busca do CRM (Segmentos,
  entrada anterior no execution-log de `comercial`) tinha sido aplicado em
  `/hub/` (branch `feat/robo-matrix-venda-automatica`, checkout separado), nao em
  `/hub-main/` (branch `main`, onde todo o resto deste trabalho vive). Reaplicado
  em `hub-main` nesta entrada pra ir junto no mesmo commit/branch.
- **Status:** completed. Falta: cleanup do cliente de teste 64250 na Nuvyon
  (usuario vai cancelar manualmente), tarefa no Workspace (prod), e decidir a
  estrategia de merge dessa branch pra `main`.
