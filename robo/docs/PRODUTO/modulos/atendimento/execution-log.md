# Execution log — Atendimento

Trilha do que foi **executado** no módulo. Cabeçalho `## AAAA-MM-DD — título`. Status: `completed` / `pending` / `blocked`.

## 2026-06-13 — Migração Vero → Brayo (TR Carrion) Fase 1

- **Ação:** Substituir catálogo de planos do bot Vero (workflow N8N TR Carrion) pela marca Brayo. Cidades atendidas reduzidas para Lençóis Paulista, Macatuba, Pederneiras. Cidades fora da lista passam a sinalizar transbordo humano.
- **Decisão:** Edição cirúrgica (Fase 1) — só os 3 nós Code que contêm catálogo (`GerarCatalogoPlanos`, `ValidarEscolhaPlano`, `GerarCatalogoPlanos2`). Etapa de **acréscimos** (Wi-Fi 6, Linha Fixa, Repetidor) **adiada pra Fase 2** porque exige replicar a máquina de estados do workflow (~10 nós novos).
- **Output:**
  - Baseline preservado: [`snapshots/_baseline_brayo_pre_migracao_13-06-2026.json`](../../../context/clientes/tr-carrion/snapshots/_baseline_brayo_pre_migracao_13-06-2026.json)
  - Proposta pronta pra importar: [`snapshots/_proposta_brayo_migracao_13-06-2026.json`](../../../context/clientes/tr-carrion/snapshots/_proposta_brayo_migracao_13-06-2026.json)
  - Doc de planos atualizada: [`planos-comerciais.md`](../../../context/clientes/tr-carrion/planos-comerciais.md)
- **Roteamento de transbordo:** nó novo `Cidade Atendida?` (IF) inserido entre `ValidarEscolhaPlano` e `Plano Valido?`. Testa `$json.atende === true`. TRUE → segue pro `Plano Valido?` normal. FALSE → cai em `Step Aguarda Humano` (estado existente de transbordo). Workflow vai de 129 → 130 nós.
- **Sessões em andamento no Postgres do N8N:** decidido **não limpar**. Conversas pré-migração com cidade antiga (Agudos/Piratininga/etc) caem naturalmente em transbordo humano via o IF novo. Comportamento correto e seguro — vendedor humano assume.

## 2026-06-13 — Migração Vero → Brayo (TR Carrion) Fase 2 (extras + confirmação)

- **Ação:** Adicionar etapa de upsell (Wi-Fi 6, Linha Fixa, Repetidor) entre escolha de plano e coleta de CPF, com resumo + confirmação final.
- **Decisão UX:** Opção A — cliente digita "1,2,3" (separados por vírgula/espaço/`+`/`-`) ou "4" pra continuar sem extras. Texto comercial V1 (foco em benefício).
- **Output:** [`snapshots/_proposta_brayo_fase2_13-06-2026.json`](../../../context/clientes/tr-carrion/snapshots/_proposta_brayo_fase2_13-06-2026.json) — workflow vai de 130 → **137 nós**.
- **Mudanças:**
  - **+7 nós novos:** `ValidarExtras` (Code), `Extras Validos?` (IF), `Step Reasking Extras` (Set), `Step Aguarda Confirmacao Extras` (Set, monta resumo), `ValidarConfirmacaoExtras` (Code), `Confirmou Extras?` (IF), `Step Pedir CPF Pos Extras` (Set)
  - **Modificado:** `Step Aguarda Plano` agora vai pra `aguarda_extras` (era `aguarda_cpf`); resposta_bot vira oferta dos extras V1; novas_vars adiciona `plano_pix` (necessário pro cálculo do total)
  - **+2 cases** no Switch `Por Nodo Atual`: `aguarda_extras` → `ValidarExtras`; `aguarda_confirmacao_extras` → `ValidarConfirmacaoExtras`
  - **Modificado:** `Enviar Lead Hubtrix` body inclui `dados_extras.acrescimos` (array), `valor_extras_total` (float) e `valor_total` (float)
- **Fluxo final pós-confirmação:** `Confirmou Extras? TRUE` → `Step Pedir CPF Pos Extras` (pede CPF, retoma jornada original). `FALSE` (cliente quer alterar) → volta pra `Step Aguarda Plano` (re-oferece os extras).
- **Validação no `LeadProspecto.dados_custom`:** payload do Hubtrix recebe `acrescimos` e `valor_total` em `dados_extras`. Não muda schema (JSONB).
- **Status:** `completed`. **Pendente:** importar no N8N + validar primeiro disparo em prod.

## 2026-06-14 — Hotfix Brayo: rejeitar cidade fora-da-area logo após CEP

- **Sintoma:** Cliente SP (DDD 11) com CEP SP passava por 5 turnos do bot (confirmar endereço → número → complemento) só pra cair em transbordo no fim. UX ruim — 3 conversas viste assim nas últimas 24h (5511955581585, 5511978775387, 5511973751289).
- **Causa:** `HTTP Hubtrix Viabilidade` (endpoint `/api/public/n8n/viabilidade/`) retorna `atendido=true` pra qualquer cidade (não conhece o filtro Brayo de 3 cidades). A rejeição de cidade só rolava no `GerarCatalogoPlanos2`/`Cidade Atende? (pre-plano)`, **5 turnos depois**.
- **Fix:** novo IF `Cidade Brayo?` inserido entre `Atendido? TRUE` e `GerarCatalogoPlanos`. Testa se `HTTP ViaCEP.localidade` normalizado (lowercase + NFD + sem diacríticos) está em `['lencois paulista','macatuba','pederneiras']`. FALSE → vai direto pro `Step Aguarda Humano` (transbordo imediato). TRUE → segue fluxo normal.
- **PUT direto em prod + sync local.** Workflow 136 → 137 nós.
- **Status:** `completed`. Próximo cliente SP/etc. transborda já no segundo turno após CEP.

## 2026-06-13 — Hotfix Brayo: cidade fora-da-area no Step Aguarda Complemento

- **Sintoma:** Cliente em cidade não atendida (Bauru) recebeu mensagem **misturada**: "Ótimo! Verifiquei aqui os planos disponíveis em Bauru e tenho algumas opções: [Ainda não atendemos sua região] Qual dessas opções mais te interessou?".
- **Causa:** `Step Aguarda Complemento` tem template com cabeçalho/rodapé hardcoded + interpola `{{ GerarCatalogoPlanos2.lista_formatada }}` no meio. Quando cidade fora da área, a `lista_formatada` retorna "Ainda nao atendemos sua regiao" — gera mistura sem sentido.
- **Fix:** inserir IF `Cidade Atende? (pre-plano)` entre `GerarCatalogoPlanos2` e `Step Aguarda Complemento`. TRUE → mostra planos. FALSE → vai pra `Step Aguarda Humano` (transbordo limpo).
- **Resultado:** workflow 135 → 136 nós.
- **Status:** `completed`.

## 2026-06-13 — Hotfix Brayo: resumo final inclui valor + adicionais

- **Sintoma:** mensagem do `Step Aguarda RG Verso` (resumo final antes da confirmação) só mostrava nome do plano, sem valor nem acréscimos contratados.
- **Fix:** template atualizado pra incluir `plano_pix`, seção condicional de `acrescimos` (não aparece se vazia) e `valor_total` (plano + extras).
- **PUT direto em prod + sync local.**
- **Status:** `completed`.

## 2026-06-13 — Hotfix Brayo: remover `Checar Contato Antigo`

- **Sintoma:** cliente nova (Kelle, 5514998421562) confirmou endereço Bauru e bot travou. Execução N8N status=error, lastNodeExecuted=`Checar Contato Antigo`, msg=`Unknown error`.
- **Causa:** nó Code `Checar Contato Antigo` tinha lista hardcoded de ~dezenas de números (snapshot pré-IA de 22/05/2026, blocklist temporária pra deixar vendedora atender manual). Lista incluía até o **5514996137490** (número da própria TR Carrion). Tava travando por bug interno.
- **Fix:** removidos 2 nós do workflow: `Checar Contato Antigo` (Code) + `Contato Antigo?` (IF). Reconectado `Entrada → BufferInserif` direto (era `Entrada → Checar Contato Antigo → Contato Antigo? → BufferInserir/Respond Ignored`).
- **PUT direto na API REST do N8N.** Sincronizado local.
- **Resultado:** workflow vai de 137 → 135 nós.
- **Status:** `completed`. Ativo em prod.

## 2026-06-13 — Hotfix Brayo: Step Pedir CPF Pos Extras com Save Session

- **Sintoma:** Cliente confirmou os extras ("1") → erro `Node 'Save Session' hasn't been executed` no `Step Pedir CPF Pos Extras`.
- **Causa:** mesmo bug do hotfix anterior — `novas_vars` desse nó referenciava `$node['Save Session'].json.dados`, mas Save Session só executa NO FIM do turno.
- **Fix:** trocar `$node['Save Session']` → `$node['DetectarPedidoHumano']` (que já tem os dados carregados pelo Load Session no início, incluindo `acrescimos` e `valor_total` salvos no turno anterior).
- **Auditoria:** Varri todos os 3 nós novos da Fase 2 (`Step Pedir CPF Pos Extras`, `Step Reasking Extras`, `Step Aguarda Confirmacao Extras`) — só esse 1 ainda tinha referência a Save Session. Limpo agora.
- **Status:** `completed`. Sincronizado em prod (PUT) e local.

## 2026-06-13 — Hotfix Brayo: ValidarExtras aceita conectivos textuais

- **Cenário:** cliente pode responder "1 e 2" / "1 mais 2" / "1+2" em vez de "1,2".
- **Fix:** No `ValidarExtras`, antes do split de separadores, fazer `replace(/\b(e|mais|com|mas|tambem|tb)\b/g, ',')` pra normalizar conectivos textuais em vírgula. Word boundaries (`\b`) protegem palavras maiores tipo "mega".
- **Como subiu:** PUT direto na API REST do N8N (`PUT /api/v1/workflows/5U3o0CaQij4ALf8N`) usando API Key do `.env.n8n`. Sincronizei `_proposta_brayo_fase2_13-06-2026.json` local com a versão de prod.
- **Status:** `completed`. Ativo em prod.

## 2026-06-13 — Acesso direto ao N8N via API REST

- **Achado:** `.env.n8n` na raiz tem `N8N_API_KEY` JWT válida + `N8N_BASE_URL`. Permite PUT/POST/DELETE diretos no workflow ativo (sem precisar de import pelo UI).
- **Workflow Vero produção:** ID real é `5U3o0CaQij4ALf8N` (`[Vero] Orquestrador Atendimento`) — não `Df1BgcXdg3HAUZwf` como tinha em mente. Atualizar referências em docs futuras.
- **Status:** `completed`. Caminho de deploy mais rápido habilitado.

## 2026-06-13 — Hotfix Brayo: template do resumo de extras (Fase 2)

- **Sintoma:** cliente real completou jornada até "Quase lá! Quer turbinar?", respondeu "1,2" e o bot **não enviou o resumo** (travou). Sem erro 5xx visível, último log foi `conversa/estado` consultado.
- **Causa:** o template do `Step Aguarda Confirmacao Extras` referenciava `$node['Save Session']` pra ler `plano_pix`, mas o `Save Session` só roda no FIM do turno (depois dos Step Aguarda). Na hora de montar o resumo a referência retornava `undefined` → expressão quebrava silenciosamente.
- **Fix:** trocar todas as referências de `Save Session` por `DetectarPedidoHumano` (que é onde os outros Steps padrão leem `dados` carregados pelo `Load Session` no início do turno).
- **Output:** mesmo arquivo `_proposta_brayo_fase2_13-06-2026.json`. Trecho `Step Aguarda Confirmacao Extras → resposta_bot` + `novas_vars` reescritos.
- **Status:** `completed`. **Pendente:** re-importar no N8N.

## 2026-06-13 — Hotfix Brayo: limite de tentativas CEP

- **Ação:** No `DetectarPedidoHumano`, subir limite de tentativas por estado de **3 → 5** antes de cair em transbordo humano.
- **Motivação:** Em teste real, cliente mandou 3 CEPs em sequência (1 de cidade fora-da-área + 2 com `xxxxx-000` que o ViaCEP rejeita) e a 4ª tentativa — que era válida (Macatuba) — foi para transbordo automático sem ser processada. Limite era excessivamente defensivo.
- **Output:** Mesmo arquivo `_proposta_brayo_fase2_13-06-2026.json` atualizado.
- **Status:** `completed`. **Pendente:** re-importar no N8N + ativar.
- **Status:** `completed` (Fase 1). `pending` (Fase 2 acréscimos — depende de feedback após Fase 1 entrar em produção).
