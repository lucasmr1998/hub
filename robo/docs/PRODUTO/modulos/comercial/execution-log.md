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

## 2026-06-15 — Tela /crm/automacoes-pipeline/ alinhada ao padrao DS

Cinco commits em sequencia que padronizam visualmente a tela com /vendas/, /crm/tarefas/ e demais telas:

- **`f2a8a85` Quick wins**: caixa "Como funciona" colapsa em `<details>`; estagios finais (`is_final_ganho/perdido`) ficam acinzentados (opacity 0.55) sem o botao "+ Criar regra aqui" — engine pula esses; stat cards ganham cores distintas (primary/success/info/warning).
- **`d937bc2` Fundo card**: `.pipeline-accordion` agora tem background bg + border + radius + sombra leve, virando card padrao do DS. Antes ficava solto sobre fundo cinza, quebrando consistencia.
- **`890b63a` Popover de ajuda**: "Como funciona" sai do corpo e vira popover ancorado no botao `?` do header (junto com "Configuracoes CRM" / "Nova regra"). Recupera ~50px de espaco; click fora fecha.
- **`f762b18` Filtros padrao DS**: substitui o card solto com select Pipeline pelo `components/list_filters.html` MODO B colapsado, com campos Pipeline + Status (todas/ativas/inativas) + Buscar (nome da regra). View aceita `?pipeline=&status=&q=`. Aplica em regras agrupadas E em regras de acao pura.

Motivo: usuario apontou que a tela parecia "diferente das outras" — analise mostrou: card solto de filtro fora do `list_filters`, accordion sem fundo card, falta busca/status, caixa "Como funciona" ocupando espaco primario. Tudo isso foi alinhado.

Itens nao implementados (evolucao futura): view alternada "lista plana paginada" (`data-table` por regra individual sem agrupamento por pipeline); templates de regra pre-prontos no modal "Nova regra"; health indicators (verde/amarelo/vermelho por taxa de falha).

Arquivos: `apps/comercial/crm/templates/crm/automacoes_pipeline.html`; `apps/comercial/crm/views.py:automacoes_pipeline_view`; doc `crm/automacoes-pipeline.md`.

Status: completed + deployado em prod.

## 2026-06-16 — Lote de melhorias UX/UI atrasadas

Commit `<TBD>` agrega 5 frentes pequenas de melhoria:

1. **Stage bar responsiva** — `@media (max-width: 1200px / 900px)` no `.op-stage-step`. Em telas estreitas o atual destaca via `flex: 2.5` e a barra ganha `overflow-x: auto` no mobile. Resolve "estoura com pipeline 8+ estagios".

2. **Permissao granular pra editar valor estimado** — funcionalidade nova `comercial.editar_valor_oportunidade` (categoria comercial, ordem 13). `api_editar_oportunidade` so aceita `valor_estimado`/`probabilidade` se o usuario tiver a permissao OU for superuser. Template gate-eia o `.editable` no header summary + card Oportunidade (mostra cadeado se nao puder editar). Falta rodar `seed_funcionalidades` em prod + atribuir aos perfis que precisam.

3. **Health indicators nas regras** — `_health_regra(regra)` em `automacoes_pipeline_view`. Calcula `verde / amarelo / vermelho / nodata / off` baseado em `total_disparos`, `total_acoes_efetivas` e `ultima_execucao` (janela 30d). Renderiza como dot colorido ao lado do status. Vermelho pulsa pra chamar atencao (regra que avalia mas nunca executa = condicao quebrada).

4. **View alternada "Lista plana"** — toggle `?view=pipeline|lista`. Vista lista mostra `data-table` com TODAS as regras (incluindo regras de acao pura) ordenadas por health (criticas primeiro) e total de disparos. Util pra auditoria quando crescer pra 50+ regras.

5. **Templates de regra pre-prontos** — galeria visivel em `/crm/automacoes-pipeline/nova/` (6 templates: Docs validados → Assinar, Docs validados → Gerar, Lead respondeu, Venda pos-venda WhatsApp, Sem contato 72h, Em branco). Click leva pra `?template=<slug>` que pre-popula nome + condicoes + acoes via JS no DOMContentLoaded. User edita marginalmente em vez de comecar do zero.

Arquivos:
- `apps/comercial/leads/...` (sem mudancas — Empresa entity nao foi implementada nessa rodada — ver abaixo)
- `apps/comercial/crm/views.py` (api_editar_oportunidade, automacoes_pipeline_view, regra_pipeline_criar)
- `apps/comercial/crm/templates/crm/oportunidade_detalhe.html` (stage bar media queries, cadeado no Valor)
- `apps/comercial/crm/templates/crm/automacoes_pipeline.html` (view toggle, health dot, lista plana)
- `apps/comercial/crm/templates/crm/regra_form.html` (galeria templates + auto-popular)
- `apps/sistema/management/commands/seed_funcionalidades.py` (nova funcionalidade)

Status: completed (local + checks). Pending: rodar `seed_funcionalidades` em prod; commit + push + deploy.

## 2026-06-16 — Evolucao em backlog: Empresa como entity propria

**Decisao**: deixar pra sprint dedicada. Refactor estrutural grande, arrisca quebrar producao se feito junto com outras coisas.

Hoje `LeadProspecto.empresa` eh um `CharField` solto — duas oportunidades da mesma empresa nao se conhecem; sem agrupamento; sem CNPJ separado; sem visao consolidada de receita por empresa.

Proposta de design (pra futura sessao):
- **Model novo** `Conta` em `apps.comercial.contas` — campos: `cnpj` (unique by tenant), `razao_social`, `nome_fantasia`, `segmento`, `tamanho` (pequena/media/grande), `dono` (FK User), `ativo`, observacao, dados_extras.
- **FK em LeadProspecto** `conta` (nullable, on_delete=SET_NULL) — migrar dados do CharField pra normalizar (1 conta por empresa unica detectada).
- **UI nova** `/comercial/contas/` (lista plana com filtros) + `/comercial/contas/<id>/` (detalhe com oportunidades agrupadas).
- **Sidebar do lead detalhe** ganha card "Conta" com link.
- **Detalhe da oportunidade** ganha card "Outras oportunidades da mesma conta".

Estimativa: ~6-8h de trabalho. Riscos: migracao de dados existentes (precisa heuristica de deduplicacao); impactar templates que usam `lead.empresa` direto.

## 2026-06-16 — Sessao Nuvyon: gate de campos obrigatorios por estagio + sync vendedor Matrix Brasil

Sessao longa entregando 4 grandes features pra Nuvyon. Resumo das entregas:

### 1. Campos obrigatorios por estagio (Feature 1)

- **Model**: `PipelineEstagio.campos_obrigatorios` (JSONField list) — migration `crm/0022`
- **Helper**: `services/requisitos_estagio.py` com `CAMPOS_DISPONIVEIS` (20 campos do Lead+Oportunidade agrupados em 5 modulos) e `campos_faltando(oport, estagio)`
- **Gate API**: `api_mover_oportunidade` retorna `HTTP 400` com `{codigo: 'campos_obrigatorios_faltando', campos_faltando: [{codigo, label}]}`
- **Gate Engine**: `_mover_por_regra` silenciosamente nao move quando faltam campos (regra pode bater de novo depois)
- **UI**: modal Editar Estagio em `/crm/configuracoes/` ganha secao com checkboxes agrupados por modulo. Persistido via `POST /configuracoes/estagios/<pk>/campos-obrigatorios/`
- **Feedback no detalhe da oportunidade**: toast `Bloqueado: Faltam campos: X, Y, Z` no modal Mover + CTAs rapidos

Substitui a regra antiga `tag=Comercial` que deixava Eva avancar pra "Dados Completos" sem CPF/CEP/email. Doc atualizada em `crm/pipeline.md`.

### 2. Permissao granular de edicao de valor estimado

- Nova funcionalidade `comercial.editar_valor_oportunidade` (seed atualizado, rodado em prod via `manage.py seed_funcionalidades`)
- `api_editar_oportunidade` so aceita `valor_estimado` e `probabilidade` se user tem permissao ou eh superuser
- Template gateia o `.editable` + adiciona icone de cadeado quando bloqueado
- Aplicado tanto no header summary quanto no card Oportunidade da sidebar

### 3. Stage bar responsiva (detalhe da oportunidade)

- Media queries em 1200px (estagio atual ganha `flex: 2.5` pra destacar quando ha muitos estagios) e 900px (`overflow-x: auto` + min-width fixo por step → scroll horizontal no mobile)

### 4. Sync de vendedor Matrix Brasil → Hubtrix

- `MatrixBrasilService` em `apps/integracoes/services/matrix_brasil.py` (v1 raw token)
- Campo `PerfilUsuario.login_matrix` (migration `sistema/0012`) — match por string contra `login_agente` retornado pelo Matrix
- Management command `sync_vendedores_matrix --tenant=nuvyon`: filtra leads com `dados_custom['id_atendimento_matrix']`, sem responsavel, ultimos 7d; consulta Matrix; atribui automaticamente
- `registrar_historico_api` agora salva `codigo_atendimento` do payload no `OportunidadeVenda.dados_custom['id_atendimento_matrix']` — eh o link Hubtrix↔Matrix
- UI: campo "Login Matrix Brasil" no modal de Editar Usuario em `/configuracoes/usuarios/`
- CronJob `sync_vendedores_matrix_nuvyon` ativo, schedule `* * * * *` (cada 1min), timeout 300s
- 11 vendedores Nuvyon mapeados (3 ainda aguardam email institucional pra serem criados como User Hubtrix)
- Validacao em prod: op 761 (Kamily, sem responsavel) atribuida automatic pra `victoria.schiavelli` via login `filialcb`. Op 759 (Jose Carlos) ja tinha `flavia.almeida` manualmente — sync respeitou.

Detalhamento em [`docs/context/clientes/nuvyon/sync-vendedor-matrix.md`](../../../context/clientes/nuvyon/sync-vendedor-matrix.md). Doc da API Matrix em `docs/PRODUTO/integracoes/apis/matrix/`.

### 5. Tela de automacoes pipeline — refinamentos (sessao anterior, finalizada hoje)

- Health indicators por regra (verde / amarelo / vermelho / nodata / off baseado em janela 30d)
- View alternada "Lista plana" via toggle `?view=lista` — `data-table` com todas as regras ordenadas por health critico
- Templates de regra pre-prontos (6 modelos: Docs validados→Assinar, Docs validados→Gerar, Lead respondeu, Venda pos-venda WhatsApp, Sem contato 72h, Em branco) — JS pre-popula campos
- Filtros migrados pro `list_filters` padrao DS

### Limpeza de dados Nuvyon

- 16 leads de teste (id<591, exceto Eva e Bruno) deletados em transacao atomica via Django ORM — 392 registros relacionados foram em cascade. Eva (591) e Bruno (589) preservados.
- Token Matrix Brasil atualizado em `IntegracaoAPI #20` (armazenado encriptado Fernet)

### 12 vendedores Nuvyon criados via SSH+Django shell

Senha temporaria padrao `Nuvyon@2026` (com `senha_temporaria=True`). Danielle Akemy como Admin, demais como Vendedor. Mapeamento `login_matrix` ja populado pra 11 (Danielle eh admin e nao atende).

Pendencias: 3 logins Matrix (Letícia/`caconde`, Nicole/`nicole`, Nicoly/`nicolyaraujo`) aguardam email institucional Nuvyon pra User Hubtrix ser criado. Feature 2 (criar prospecto HubSoft + converter) ainda na fila.

Status: completed + deployado em prod (commits `d4cbd3c`, `88dd40d`, `e3f2de0`, `805e7bd`).

---

## 2026-06-21 — Historico de disparos das regras de automacao pipeline

- **Acao**: Botao "Historico" (icone `bi-clock-history`) em cada linha da tabela em `/crm/automacoes-pipeline/`. Click abre modal com os ultimos 50 disparos da regra: timestamp, oportunidade + lead, mudanca de estagio ou chips de acoes executadas, e badge `efetiva` / `idempotente`.
- **Implementacao**: motor `automacao_pipeline.py` agora enriquece `dados_extras` do `LogSistema` central com `regra_id`, `estagio_anterior_id/nome`, `estagio_destino_id/nome`, `lead_id`, `acoes_executadas`, `houve_efetiva`, `horas_no_estagio_anterior`. Nova view `regra_pipeline_historico` filtra `LogSistema` por `dados_extras__regra_id=pk`. Zero migration (reusa `log_sistema`).
- **Decisao**: NAO criar tabela `crm_log_regra_execucao` propria — `LogSistema` central ja existe, ja recebe os eventos do motor (`registrar_acao('crm','mover_regra',...)`). Mais barato e mais alinhado com o padrao do produto (toda acao deveria ir pra `log_sistema`).
- **Why**: usuario pediu "quero ver os logs das regras direto por ali" — descoberto que motor so contabilizava `total_disparos` mas nao expunha timeline. Bug de produto.
- **How to apply**: ao criar outra acao no motor que dispare regra, garantir que `registrar_acao` seja chamado com `dados_extras={'regra_id': ..., ...}` pra aparecer no historico. Logs sem `dados_extras.regra_id` ficam invisiveis no botao.
- **Output**: commit `d749c80`. Doc completa em [`crm/automacoes-pipeline.md`](crm/automacoes-pipeline.md#historico-de-execucao).
- **Pendencia**: 116 logs antigos Nuvyon (pre-feature) foram apagados no cleanup do dia em prod — nao tinham `dados_extras.regra_id` populado, ficariam invisiveis no botao. Outros tenants: logs antigos ficam de fora dos modais ate logs novos serem gerados.
- **Status**: completed + deployado em prod.

## 2026-06-21 — Fix webhook N8N: canais WhatsApp + telefone VARCHAR(32)

- **Acao**: Webhook `/api/public/n8n/inbox/mensagem/` ignora canais/newsletters/broadcasts do WhatsApp + 2 colunas `*.telefone` VARCHAR(17) alargadas pra VARCHAR(32).
- **Causa raiz**: numero `120363426906258649` (canal WhatsApp newsletter do Mercado Livre, ofertas) chegava como mensagem normal no TR Carrion via Uazapi. Tem 18 digitos, estourava as 2 ultimas colunas VARCHAR(17) defasadas do schema (resto ja era VARCHAR(20) pelo commit `247123a`). Resultado: HTTP 500 a cada ~5min em prod, alerta disparando.
- **Fix A — filtro de canal**: no `inbox_mensagem`, telefones com prefixo `120363` ou mais de 15 digitos retornam `200 {ignored:true, motivo:'canal_whatsapp_broadcast'}`. Evita criar Lead/Conversa pra canal de ofertas e impede o bot Vero de responder "vou anotar suas informacoes" pra cada produto do ML.
- **Fix B — alarga schema**: migrations `inbox.0017_alter_conversa_contato_telefone` e `leads.0009_alter_historicocontato_telefone` levam `inbox_conversas.contato_telefone` e `historico_contato.telefone` pra VARCHAR(32). Defense in depth pra qualquer ID grande futuro (grupos WhatsApp, broadcasts, listas).
- **How to apply**: padrao "telefone" no schema deve ser VARCHAR >= 20. Se ID `120363...` voltar a aparecer em outro tenant, ja esta blindado. Pra debugar webhooks futuros, `integracoes_log_webhook_n8n` tem `body_preview` + `status_code` por chamada (consultar via SQL).
- **Output**: commit `570ef8c`.
- **Status**: completed + deployado em prod.

## 2026-07-08 a 2026-07-10 — CRM: obrigatorios no cadastro, sem responsavel, prevencao plano x regiao

- Modal cadastro completo: email, origem do cliente e origem do contato obrigatorios (validacao front + backend pelo ESTADO FINAL do lead); label "Origem do servico" renomeada pra "Origem do contato". Commit 0425a64.
- Criacao manual de oportunidade: criador vira responsavel default (9 ops orfas eram desse caminho; distribuicao automatica nao cobria) + log de atribuicao na timeline. Commit 293ef81. Backfill das orfas pro criador executado em prod.
- Filtro "— Sem responsavel —" no kanban e na lista (`?responsavel=sem`); resumo diario aponta link direto. Commit 8c7efee.
- Prevencao plano x regiao: dropdown de planos do modal recarrega pelos planos vendaveis no CEP (proxy listar_planos_por_cep, cache 10min) + save bloqueia plano fora do catalogo do CEP, fail-open. Motivo: plano de unidade errada gravado no HubSoft trava o prospecto (deadlock, caso Jefferson/Itu). Commit 847bbfe.
- Leads: valor autopreenchido com o preco tipico do plano quando vem zerado (22 vendas sem receita; backfill com valor real do HubSoft executado). Commit 440e11b.
- Status: completed

## 2026-07-10 — Ajuste: dropdown de planos = catalogo curado x CEP (intersecao)

- Acao: o filtro por CEP mostrava a lista bruta do HubSoft (91 itens em Itu, com variantes MIG/rural/PJ). Pergunta do Lucas ("vamos mostrar todos os ativos?") levou ao desenho final: intersecao entre o catalogo de Produtos do CRM (39 planos curados, gerenciaveis em /crm/produtos/) e os planos validos no CEP. Fallback pra lista completa do CEP quando o catalogo nao cobre a regiao. A trava do save segue validando contra a lista bruta. Commit 8c79b98.
- Nota: o catalogo curado NAO e hardcoded — vem de crm_produtos (ja foi lista fixa de 5 no passado e virou gerenciavel).
- Status: completed

## 2026-07-15 — Filtros do Pipeline em DRAWER (modelo RD Station)

- **Pedido do dono**: tirar a barra de filtros fixa e transformar num botao "Filtros" (junto de "Personalizar card"), abrindo um painel deslizante da DIREITA — modelo RD Station/HubSpot.
- **Reuso**: o DS ja tem `.modal-drawer` (desliza da direita). Novo modo `drawer=True` no componente compartilhado `components/list_filters.html` (opt-in): botao na toolbar + drawer com os campos empilhados + Filtrar/Limpar no rodape.
- **Sem quebrar o filtro existente**: a form do drawer mantem a classe `.list-filters-grid` e os mesmos `name=`, entao o JS de cada tela (change -> recarrega, submit -> intercepta) continua funcionando sem tocar.
- **Ligado so no Pipeline por enquanto.** O componente e usado em 8 telas (pipeline, oportunidades, tarefas, vendas, contratos, OS, tickets, automacoes); as outras 7 seguem com a barra colapsavel ate o dono validar e mandar rolar.
- **BUG MEU, 3a vez na sessao**: comentario Django multi-linha `{# #}` (so vale 1 linha) vazou como texto atras do drawer. Corrigido com `{% comment %}`. Peguei olhando o screenshot.
- **Validado (dev, Playwright)**: botao na toolbar; drawer abre da direita (480px, campos empilhados); mudar filtro chama carregarPipeline; Filtrar fecha o drawer; sem vazamento de comentario; 0 erros de console.
- **Arquivos**: `components/list_filters.html`, `partials/_components_styles.html`, `crm/pipeline.html`.
- **Status**: completed (dev, so pipeline). Deploy + rollout pras outras 7 telas pendentes.

## 2026-07-15 — Drawer de filtros: layout 2 colunas + 3 filtros novos

- **Pedido do dono**: mais opcoes de filtro no drawer + Canal/Fonte/Campanha paravam de ocupar uma linha cada.
- **Layout**: os campos do drawer viraram grade de 2 COLUNAS (`.list-filters-drawer` grid 1fr/1fr); Buscar ocupa a linha inteira. Multiselect (Canal/Fonte/Campanha) encolhia porque o `.multiselect-wrap` do meio nao tinha width — estiquei os tres niveis. Agora todos preenchem a celula.
- **Filtros novos**: Estagio (backend novo: estagio_id), Prioridade (backend JA existia, so faltava a UI — filtro de graca), Criada em / Periodo (backend novo: data_criacao >= now-Nd). Deixei Cidade DE FORA de proposito: 37 grafias sujas em prod (caconde/Caconde, RIBEIRAO PRETO/SP...), viraria dropdown bagunçado — depende da normalizacao antes.
- **BUG ANTIGO achado no caminho**: o `carregarPipeline` montava a query a mao com so 4 campos (search/responsavel/tag/valor), entao os multiselect Canal/Fonte/Campanha ja existentes **nunca chegavam ao backend no kanban** — filtros mortos. Trocado por `new URLSearchParams(new FormData(form))`, que envia TODOS os campos. Conserta os 3 antigos + os 3 novos. Change-listener ampliado pra todos os selects do form.
- **Validado (dev)**: drawer com 10 filtros em 2 colunas; multiselect 100% da celula; backend recorta (Periodo 7d=8 <= 30d=69 <= 167 total; Estagio/Prioridade aplicam subset); 0 erros de console.
- **Arquivos**: `components/list_filters.html`, `partials/_components_styles.html`, `crm/views.py`, `crm/pipeline.html`.
- **Status**: completed (dev). Deploy pendente.

## 2026-07-16 — Viabilidade: nao decidir fora_cobertura em resposta indeterminada

- **Gatilho:** Lucas perguntou se o CEP 13308-200 realmente nao tinha viabilidade
  (op 2793, foi pra Perdido). Investigacao em prod:
  - o CEP TEM viabilidade comercial: 91 planos (unidade Salto);
  - a API tecnica (mapeamento/viabilidade/consultar) responde
    `{"projetos": "Nenhum Projeto foi compativel com a localizacao.", ...}` —
    ou seja, `projetos` vem como STRING, nao lista;
  - o codigo fazia isinstance(projetos, list) -> caia no fallback legado -> lia
    `atende` (inexistente) -> bool(None)=False -> fora_cobertura, gravando um
    enganoso `detalhes: {"planos": 0}`. Veredito certo por acidente, razao perdida,
    e fail-closed pra qualquer resposta inesperada.
  - agravante: o endereco da op esta embaralhado (numero = nome da rua, bairro =
    "14") e o CEP (Rodovia Waldomiro Correa de Camargo) nao bate com a rua
    informada (Cristovao Martinelli). Veredito em cima de dado furado.
- **Fix (A+B):** _tentar_hubsoft passou a tratar 4 casos: lista de projetos
  (decide por portas livres), `projetos` como STRING (nao atende, guardando o
  motivo real da API), schema legado (`atende`), e resposta NAO reconhecida ->
  `pendente_revisao` (nunca mais fora_cobertura em cima de indeterminado; o lead
  vai pra validacao humana em vez de Perdido calado).
- **Validacao:** 4 ramos testados com resposta mockada; comportamento antigo
  (cobertura_ok / fora_cobertura por portas) preservado.
- **Pendente (C):** o bot esta embaralhando os campos de endereco. Tarefa a parte.
- **Status:** completed (codigo, dev). Deploy em prod.

---

## 2026-07-16 — Auditoria da regra "Sem viabilidade -> Perdido" e mudanca de acao

- **Gatilho:** a op 2793 nao saia do Perdido. Historico mostrou LOOP: usuario tira
  do Perdido -> regra 8 ("Lead respondeu o bot") puxa pra Em Atendimento -> regra
  22 ("Sem viabilidade -> Perdido", SEM gatilho de estagio, dispara de qualquer
  lugar) devolve pro Perdido no mesmo segundo. 3 tentativas humanas revertidas.
- **Destrave (autorizado):** lead 2634 teve viabilidade.status trocado de
  fora_cobertura -> pendente_revisao (desarma a regra 22, arma a regra 26 que cria
  tarefa de validacao) e a op 2793 foi movida pra Analise de Viabilidade. Confirmado
  que nao volta.
- **Auditoria (18 ops distintas atingidas pela regra 22):**
  - **11 estao hoje em "Ativacao Confirmada"** — ou seja, o veredito "sem
    viabilidade" estava ERRADO em 61% dos casos; foram resgatadas na mao e viraram
    clientes.
  - 6 seguem em Perdido (1645, 1652, 1687, 1759, 1838, 1863) — candidatas a perda
    falsa nunca resgatada. Revisao pendente com o Lucas.
  - 3 tinham endereco comprovadamente trocado (numero/bairro).
- **Mudanca (autorizada):** regra 22 deixou de perder lead automaticamente. Nome ->
  "Sem viabilidade -> validar cobertura (tarefa)"; acao ->
  mover_para_perdido_sem_viabilidade **substituida por** criar_tarefa
  ("⚠️ Validar cobertura — {cidade}"). Condicao (fora_cobertura) inalterada, regra
  segue ativa. Junto com o fix A+B do service (commit 6313cd1), o sistema para de
  descartar lead com base em veredito de endereco furado.
- **Status:** completed. Raiz (bot embaralhando endereco) na tarefa #201.

---

## 2026-07-20 — Respostas do bot no detalhe do lead

- **Acao:** secao "Respostas do bot" no `lead_detail.html`, alimentada por
  `_respostas_checklist_do_lead` em `apps/comercial/leads/views.py`.
- **Motivacao:** o bot de venda por WhatsApp (tarefa 204) coleta CPF, nome,
  nascimento, email e o resto do roteiro, mas a vendedora que pegasse a
  conversa no meio nao tinha como ver nada disso. Contraparte da tela de
  acompanhamento criada no Workspace (ver execution-log do modulo workspace).
- **O que mostra:** pergunta, o que o cliente respondeu e o valor normalizado
  quando difere do bruto (ex: CPF gravado sem pontuacao, data em ISO). Agrupado
  por checklist, na ordem dos itens. A secao NAO renderiza quando o lead nao
  tem resposta nenhuma, pra nao deixar bloco vazio na pagina.
- **Desempenho:** uma query so, com `select_related` de checklist e item; o
  agrupamento por checklist e feito em memoria.
- **Limitacao conhecida (nao resolvida aqui):** o espelho da resposta em
  `LeadProspecto.dados_custom` so acontece quando o item do checklist esta
  ligado a um `CampoCustomizado`. As 22 perguntas semeadas pro bot da Nuvyon
  nasceram sem essa ligacao, entao hoje o dado vive so na tabela de respostas
  do checklist e NAO aparece nos campos do cadastro. Ligar os itens aos campos
  e trabalho separado.
- **Status:** completed
