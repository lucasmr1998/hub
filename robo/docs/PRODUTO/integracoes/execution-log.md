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
