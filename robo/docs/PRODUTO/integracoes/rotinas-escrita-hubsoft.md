# Rotinas de escrita no HubSoft (painel)

Rotinas configuraveis, por tenant, que executam no HubSoft as tres operacoes de
escrita que **nao tem API oficial**: conversao de prospecto em cliente, novo
servico e upgrade/migracao de plano. Sao fluxos da engine `apps/automacao` que
usam a **API interna do painel** (login de operador por Selenium -> JWT -> HTTP),
espelhando o que o robo_v2 (techub) fazia, mas multi-tenant e sem ID magico no
codigo.

## Peças

- **`IntegracaoAPI` tipo `hubsoft_painel`** — credencial do operador do painel
  (`base_url` = URL do painel, `client_id` = login, `client_secret` = senha
  encriptada). O JWT capturado fica cacheado em `configuracoes_extras.cache.painel_token`.
- **`PerfilConversaoHubsoft`** (`integracoes_perfil_conversao_hubsoft`) — concentra
  tudo que era ID magico da Megalink: `vendedor_id_conversao`/`_novo_servico`,
  `grupo_servico_obj`, `forma_cobranca_obj`, `status_servico_novo_id` (6) /
  `status_servico_migrado_id` (11), `vencimentos_map` (dia -> id do ERP),
  `validade_meses`, `tipo_cobranca`, `agrupamento_fatura`, e os **templates de
  payload** (`template_conversao`). Guard de seguranca: `dry_run_forcado` (nasce
  True) + `cpf_allowlist` — enquanto ligado, so os CPFs liberados escrevem de
  verdade; o resto simula.
- **Service `apps/integracoes/services/hubsoft_painel.py`** — `HubsoftPainelService`:
  login, leitura (`get_cliente`, `obter_servico_edit`, `buscar_cep`, `schema_cache`)
  e escrita (`montar_payload_conversao`, `criar_cliente`, `cpf_ja_cadastrado`,
  `montar_payload_adicionar_servico`, `adicionar_servico`, `buscar_plano_por_id`).
  Os `montar_payload_*` sao funcoes puras (golden testadas).
- **Nos** (`apps/automacao/nodes/`, subgrupo "HubSoft (painel)"):
  - `hubsoft_converter_prospecto` — POST /cliente com `id_prospecto`.
  - `hubsoft_adicionar_servico` — POST /cliente/servico (status novo = 6).
  - `hubsoft_migrar_plano` — POST /cliente/servico + campos de migracao (status 11).
  Todos: saidas `sucesso | erro | dry_run`, `retry_seguro=False`, guard de dry run
  do perfil, CPF mascarado no output.
- **Varredura `prospectos_por_criterio`** — o "start por vendedor/status": filtra
  `LeadProspecto` por vendedor, status_api, com_id_hubsoft, sem_marcador.
- **Seeds** — `python manage.py seed_fluxos_hubsoft_escrita --tenant <slug>` cria os
  3 fluxos INATIVOS e em dry run (idempotente por nome).

## Camadas de seguranca

1. **Idempotencia** — conversao checa status_api do lead, espelho ClienteHubsoft e
   `cpf_ja_cadastrado` no painel; novo servico/upgrade checam se o cliente ja tem o
   plano ativo. Qualquer uma verdadeira = no-op.
2. **Guard de dry run do perfil** — `dry_run_forcado=True` + allowlist; o no tambem
   tem o campo "Forcar simulacao" (padrao ligado). Dry run monta o payload real e
   para (saida `dry_run`).
3. **`retry_seguro=False`** — a engine nunca reexecuta o POST sozinha.
4. **Fluxos nascem INATIVOS.**

## Como ligar (por tenant)

1. Cadastrar a `IntegracaoAPI` tipo `hubsoft_painel` (credencial do operador).
2. Criar o `PerfilConversaoHubsoft` do tenant com os IDs do HubSoft dele.
3. **Capturar o `template_conversao`** uma vez naquele HubSoft. Use o comando
   `hubsoft_capturar_template --tenant <slug> --perfil <nome> --salvar-perfil`: ele
   abre o painel numa janela, faz login, e o operador converte um prospecto de TESTE
   no wizard; o comando fareja o POST /cliente, **neutraliza o PII** do prospecto de
   teste (cpf/nome/endereco viram vazio, so a estrutura + objetos da empresa ficam) e
   grava no perfil. Sem o template, o no de conversao sai por `erro` "sem template".
4. Rodar o seed, revisar os filtros da varredura e o `id_servico`/`id_servico_novo`
   nos nos de servico/upgrade.
5. Homologar com 1 CPF na `cpf_allowlist` (execucao real de 1 caso), conferir no
   painel, e so entao desligar o `dry_run_forcado`.

## Testes

`tests/test_hubsoft_painel_fundacao.py`, `tests/test_hubsoft_converter_prospecto.py`,
`tests/test_hubsoft_servico_upgrade.py` (38 no total): guard de dry run, varredura
com isolamento por tenant, golden dos 3 payloads, e fluxo/idempotencia dos 3 nos
com o service stubado (zero rede).

## Pendencias conhecidas

- Captura do `template_conversao` real da Nuvyon (demo-local ainda vazio).
- Acesso ao host da API interna (`api.<dominio>`) deu connect-timeout em 24/07
  (cara de allowlist de IP no HubSoft); o host do painel conecta.
- UI em `/configuracoes/integracoes/` pra editar perfil/credencial e colar o template
  (hoje so via admin).
- `buscar_plano_por_id` depende do painel responder `/servico/{id}`; sem DB fallback
  (o robo_v2 usava psycopg2 direto, descartado aqui).
