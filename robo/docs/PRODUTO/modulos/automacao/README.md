# Módulo: Automação (engine unificada)

> **Status:** Fase 0 (fundação) + runtime em memória. App greenfield `apps/automacao/`, isolado, sem editor/persistência (models)/triggers ainda. O motor já percorre um fluxo (grafo JSON) de ponta a ponta. Os três motores atuais (comercial, marketing, atendimento) seguem rodando intactos e convergem pra cá depois.

## Por que existe

Hoje há **três motores de automação separados** que divergem a cada hotfix:

- **Comercial** (`apps/comercial/crm/services/automacao_pipeline.py`): regra `condição→ação`, sem editor visual.
- **Marketing** (`apps/marketing/automacoes/`): grafo BFS fire-and-forget + Drawflow.
- **Atendimento** (`apps/comercial/atendimento/engine.py`): máquina de estado conversacional + Drawflow + IA.

Resultado: dois editores Drawflow duplicados, três catálogos de "ações" com forte sobreposição (`criar_oportunidade`, `webhook`, `mover_estagio`, `enviar_whatsapp`...), três runtimes. A engine unificada (estilo n8n) mata esse drift: **um** catálogo de nós, **um** runtime, **um** contrato de dados, com blocos habilitados **por tenant**.

## Contrato híbrido de dados

Duas camadas convivem:

- **Contexto global do fluxo** (`Contexto`, vive a execução inteira): `tenant` (obrigatório), `lead`, `oportunidade`, `conversa` + namespace `variaveis` que acumula + `nodes` (mapa `id_do_no → output`).
- **Output explícito por nó**: cada `executar()` devolve um `NodeResult` cujo `output` (JSON) fica endereçável por `{{nodes.<id>.<campo>}}`.

### Resolução de template `{{ ... }}`
Um resolvedor próprio (dot-notation), em `nodes/context.py`:

| Expressão | Resolve |
|---|---|
| `{{lead.nome}}`, `{{tenant.slug}}`, `{{oportunidade.titulo}}` | atributo da entidade no contexto global |
| `{{var.token}}` | namespace `variaveis` |
| `{{nodes.http_1.body.access_token}}` | output de um nó anterior (dict aninhado) |

Regras:
- **Full-match preserva o tipo.** Se o campo é exatamente `{{nodes.http_1.body}}`, devolve o **objeto** (dict/list/int), não a string. Permite passar estruturas entre nós.
- **Interpolação vira string.** Em texto misto (`"Oi {{lead.nome}}"`), cada token é convertido: dict/list → JSON, `None` → `''`, resto → `str()`.
- **Não resolvido fica literal.** `{{var.naoexiste}}` permanece `{{var.naoexiste}}` (não quebra o fluxo). Mesmo comportamento documentado no motor antigo (`fluxos/variaveis-contexto.md`).
- **Recorre em dict/list.** `resolver()` desce em `headers`/`body` resolvendo as folhas string.

> **Nota de namespace (migração futura):** este contrato é **dot-notation** (`{{lead.nome}}`). O motor antigo usa chave **achatada** (`{{lead_nome}}`). Ao migrar os motores, os templates antigos são reescritos. Não misturar.

### Ponte de promoção
Um nó com `salvar_em: "x"` devolve `NodeResult.promote = {"x": <output>}`. O runtime funde isso em `contexto.variaveis`, virando `{{var.x}}` daí pra frente.

### Injeção de entidade (`NodeResult.entidades`)
Um nó pode injetar uma entidade de domínio (`lead`/`oportunidade`/`conversa`) no meio do grafo devolvendo `NodeResult.entidades = {"lead": obj}`; `Contexto.aplicar_resultado` funde isso em `contexto.lead` (`Contexto.injetar_entidades`), passando a valer pros nós seguintes. Só sobrescreve quando o valor não é `None`. Mecanismo genérico (qualquer nó pode usar), criado pro nó `carregar_lead` fechar o gap do bot de vendas: o gatilho `webhook` só hidrata `{{var.payload}}`, nunca uma entidade — sem esse nó, `checklist_proximo_item`/`checklist_validar` falham com "Sem lead no contexto." em todo turno que vier via HTTP de verdade.

## Contrato de nó

Todo bloco implementa `BaseNode` (em `nodes/base.py`):

```python
@dataclass
class NodeResult:
    output: dict = {}            # JSON do nó (endereçável por {{nodes.id...}}); headers mascarados
    status: str = "ok"          # ok | erro | aguardando
    branch: str | None = None   # sucesso | erro | true | false | ...
    promote: dict | None = None # vars a fundir em contexto.variaveis (via salvar_em)
    entidades: dict | None = None  # {'lead'|'oportunidade'|'conversa': obj} a fundir em contexto.*
    erro: str | None = None

class BaseNode:
    tipo = ""            # slug único (chave do REGISTRY)
    label = ""
    icone = "bi-box"     # ícone (bi-*) no card/paleta
    categoria = "core"   # gating por tenant (futuro): core | comercial | marketing | atendimento
    grupo = "Core"       # categoria no menu (n8n-style); subgrupo = subcategoria
    saidas = ["sucesso"] # branches que o nó emite (portas no editor; valida o grafo)
    def validar_config(self, config) -> list[str]: ...   # lista de erros (vazia = ok)
    def campos_config(self) -> list: ...                 # schema do formulário do editor
    def executar(self, config, entrada, contexto) -> NodeResult: ...

# Identidade: o `id` do nó no grafo é o HANDLE (slug seguro, sem espaço/acento) e é
# o que `{{nodes.<handle>}}` referencia. O `nome` (em data.nome) é só exibição (livre).
# Runtime: exceção de nó vira NodeResult(erro) controlado — não derruba o fluxo.
```

Registro por decorator (`@registrar`), mesmo padrão de `apps/comercial/crm/services/automacao_condicoes.py`:

```python
@registrar
class HttpRequestNode(BaseNode):
    tipo = "http_request"
    categoria = "core"
    label = "HTTP Request"
    ...
```

`REGISTRY[tipo] = instância`. `tipo_por_slug(tipo)` recupera. `nodes/__init__.py` importa cada módulo de nó pra popular o registry; `apps.py.ready()` importa `nodes`.

## Runtime (o motor)

`apps/automacao/runtime.py` — o "andador do grafo". `executar_fluxo(fluxo, contexto)` percorre o grafo, executa cada nó, passa o output adiante e ramifica, até o fim, uma pausa ou um erro. **Python puro dentro do Django, síncrono** — sem fila. O despacho real-time virá de signals; a retoma de delays, de um cron (próxima fase, com persistência).

Formato do fluxo (em memória, sem DB ainda):
```json
{
  "inicio": "n1",
  "nodes": {
    "n1": {"tipo": "set_fields", "config": {...}},
    "n2": {"tipo": "http_request", "config": {...}}
  },
  "conexoes": [{"de": "n1", "para": "n2", "saida": "sucesso"}]
}
```

- **Handle do nó = identidade visível.** A **chave** do nó em `nodes` (ex: `n1`, ou um nome legível como `http_score`) é o seu handle: é o que se vê e o que `{{nodes.<handle>.campo}}` referencia. Resolve o problema de "não dá pra identificar o nó" — todo nó tem um identificador estável e único no fluxo.
- **Ramificação:** segue a aresta cuja `saida` casa com a `branch` que o nó devolveu (`sucesso`/`erro`/`true`/`false`); senão `default`; senão fim do caminho.
- **Erro não tratado:** nó devolve `erro` e não há aresta de tratamento → o fluxo encerra com motivo (não engole o erro).
- **Pausa/retoma:** nó devolve `status='aguardando'` → o motor para e devolve `Contexto.serializar()` + o handle de retoma. O cron (futuro) re-hidrata por id+tenant e continua do nó seguinte.
- **Anti-loop:** limite de passos por execução (`max_passos`).

Rodar um fluxo isolado no terminal: `python manage.py testar_fluxo --fluxo @fluxo.json --tenant <slug>`.

## Editor visual (ilha React, dev-only)

`apps/automacao/editor/` — editor estilo n8n em **React + @xyflow/react (React Flow) + Vite + TS**, isolado do resto do app. Produz/consome o **mesmo JSON de grafo** que o runtime roda; o backend só expõe 2 endpoints (`apps/automacao/views.py`):
- `GET /automacao/api/nodes/` — catálogo de nós (paleta).
- `POST /automacao/api/testar-fluxo/` — roda `executar_fluxo` no grafo postado e devolve o trace. `csrf_exempt` **DEV-ONLY** (endurecer antes de deploy).

O **handle do nó aparece em destaque no card** — resolve o "não dá pra ver qual é o nó". O **painel de nós abre por um botão** (＋ Adicionar nó), com busca e os nós **agrupados por categoria → subcategoria** (estilo n8n). Taxonomia no contrato de nó: `grupo` (categoria do menu, ex: `Core`, `Transformação`) + `subgrupo` (subcategoria, ex: `HTTP`, `Campos`). `categoria` segue sendo o domínio de gating por tenant (core/comercial/...), separado da taxonomia do menu.

**Dois modos** (ver `apps/automacao/editor/README.md`):
- **Uso (1 app):** `npm run build` → Django serve o bundle em **`/automacao/editor/`** (página `editor_page` + estáticos em `apps/automacao/static/automacao_editor/`). Mesmo login, mesmo domínio, sem segundo porto.
- **Dev da UI (2 portos):** Vite (5173, hot reload) + Django (8001) com proxy.

**Nada vai pro deploy ainda.** A decisão de como o build chega no deploy (commitar o bundle vs. `npm run build` no container EasyPanel) fica pra publicação.

## Gatilhos e execução persistida

- **Webhook:** cada fluxo pode ter um `webhook_token`. `POST /automacao/webhook/<token>/` dispara o fluxo; o corpo JSON vira `{{var.payload}}`. Público, autenticado pelo token secreto na URL. Ativado pelo editor (seção "Gatilho: Webhook").
- **Execução persistida:** `ExecucaoFluxo` (TenantMixin) guarda `estado` (= `Contexto.serializar()`), `status`, `retomar_em`, `agendado_para`, `trace`. `apps/automacao/execucao.py`:
  - `executar_e_persistir(fluxo, contexto)` — roda e grava; se `delay` pausa (`aguardando`), agenda a retoma.
  - `retomar_pendentes()` — re-hidrata e continua os vencidos. Roda via cron: `python manage.py automacao_retomar` (a cada minuto).
- **Próximo (convergência):** trigger por **evento do sistema** (lead criado, msg recebida) — toca os signals dos apps existentes; é o passo que aposenta os motores antigos.
- **Dívida:** webhook público sem rate-limit (DoS) — adicionar antes de deploy; CSRF dos endpoints do editor ainda `csrf_exempt` (DEV-ONLY).

## Checklist configurável (Fase 1 — models + service)

Roteiro de perguntas que um bot conversacional externo (Matrix) conduz no
WhatsApp pra preencher dados de uma entidade (lead, oportunidade...) passo a
passo, sem código — a cliente edita as perguntas numa tela. Fase 1 entrega só
a fonte das perguntas e o motor de elegibilidade/progresso; os endpoints que o
Matrix consome (Fase 2) ainda não existem.

Models em `apps/automacao/models.py` (ao lado do `Agente` — mesma natureza: peça
de configuração que alimenta a IA/bot), todos `TenantMixin`:
- **`Checklist`** — o roteiro (`contexto`, `modo_preenchimento`, `entidade_alvo`).
  `bloqueia_avanco` existe pronto pra v2 endurecer; v1 só sugere.
- **`ItemChecklist`** — uma pergunta (`ordem`, `chave`, `tipo_resposta`
  texto_livre/opcoes, `condicao` pra ramificar, `tipo_validacao`, `campo`
  opcional que espelha a resposta num `CampoCustomizado` do CRM). `ura_titulo`
  é uma lista **fechada** de 3 slugs (só os que o Matrix já conhece — cada um
  faz ele renderizar uma IMAGEM fixa de menu no WhatsApp; slug novo de verdade
  exige mudança nos DOIS sistemas). `clean()` protege o contrato com o Matrix:
  múltipla escolha só aceita **2 a 5 opções** (o flow dele só tem branch pronto
  pra esses tamanhos; 6+ cai no default e quebra em silêncio).
- **`RespostaChecklist`** — resposta de um item, ancorada em `entidade_tipo` +
  `entidade_id` (genérico: lead, oportunidade, o que vier depois, sem FK nova
  por entidade). 1 resposta corrente por item/entidade.

Motor puro em `apps/automacao/services/checklist.py` (sem HTTP, sem `request`):
`itens_elegiveis` (ordem + `condicao`, operadores `igual`/`diferente`/`existe`/
`nao_existe`), `proximo_item`, `respostas_da_entidade`, `registrar_resposta`
(idempotente; espelha em `dados_custom[campo.slug]` quando o item tem `campo`,
blindado — nunca derruba o registro da resposta), `progresso` (só obrigatórios
elegíveis).

## Princípios de design obrigatórios

1. **Tenant explícito sempre.** `Contexto.tenant` é obrigatório (a engine roda em cron/command/signal, **fora de request** — o thread-local do `TenantMiddleware` está vazio ou sujo). Todo nó que tocar o ORM usa `contexto.tenant` em `.all_tenants.filter(tenant=...)` / `.create(tenant=...)`. **Nenhum nó lê `get_current_tenant()`.**
2. **Serialização por id, não por objeto.** `Contexto` carrega objetos de domínio só por conveniência de templating. `Contexto.serializar()` devolve `tenant_id` + `variaveis` + `nodes` (JSON) + refs por id das entidades. Na retoma assíncrona (futura), re-hidrata por `(model, id, tenant)`. Mantém as portas abertas pra síncrono-em-cron ou fila.
3. **Secrets nunca em claro.** Output que tenha `headers` ou `auth` mascara `Authorization`/`Cookie`/`Set-Cookie` **antes** de qualquer print/log/persistência.
4. **Executor de domínio único.** Quando vierem nós de domínio (`criar_oportunidade`, `webhook`...), eles chamam **um service tenant-aware compartilhado**, nunca uma nova cópia. Hoje `_acao_criar_oportunidade` do atendimento está acoplado ao objeto `atendimento` — precisa ser extraído antes de virar nó.

## Roadmap de convergência (os três motores morrem)

1. **Marketing primeiro** (grafo BFS, menos crítico): eventos viram triggers; ações viram nós do service único.
2. **Atendimento depois** (paridade conversacional: IA/tools/validação/recontato).
3. **Comercial por último** (regra `condição→ação` vira fluxo trigger+condição+ação).

## Princípio do catálogo: propriedades vs comportamentos

Escrever **uma propriedade** de um recurso (um atributo, um par chave/valor) nunca gera um nó novo. Vira **uma entrada num registry** (`propriedades_oportunidade.py`, espelha `varreduras.py`) consumida por **um único nó genérico** (`definir_propriedade_oportunidade`) que escolhe a propriedade num dropdown. Motivo: sem essa regra, cada atributo escrevível (`motivo_perda`, `dados_custom[x]`, `valor_estimado`, o próximo que aparecer) vira um nó quase idêntico ao anterior, lotando a paleta do editor, cada um com sua própria cópia de validação.

Nó **dedicado** continua existindo, mas só pra **comportamento**: uma ação com lógica própria que não é "escrever um campo", como mover de estágio, reabrir, atribuir responsável, criar nota. Esses ficam nós à parte porque o verbo (mover, reabrir, atribuir) É a ação, não um par chave/valor plugável num registry.

Contrato do handler de propriedade (`fn(tenant, oportunidade, valor, *, chave='', somente_se_vazio=True) -> dict`): devolve `{'aplicado': bool, 'motivo_skip': str|None, 'detalhe': str}` e **nunca levanta exceção pra caso de negócio** (motivo fora do catálogo, condição de estado não satisfeita, valor inválido, campo já preenchido). `aplicado=False` é branch de **sucesso** no nó: skip não é erro, então nunca aciona retry. Achado do piloto real do fluxo 25 que motivou essa regra: o nó antigo `definir_motivo_perda` levantava `ValueError` quando um agente IA classificava a perda com um motivo fora do catálogo, um erro **determinístico** (a mesma config sempre falha do mesmo jeito) que o runtime tratava como falha transitória, gerando retries inúteis. O mesmo piloto também expôs que motivo de perda estava sendo aplicado em oportunidade fora de estágio `is_final_perdido` (poluição de dado); hoje é regra do handler, não do fluxo.

## Catálogo de nós

| tipo | grupo › subgrupo | label | status |
|---|---|---|---|
| `set_fields` | Transformação › Campos | Definir variáveis | ✅ (nó de referência) |
| `extrair_json` | Transformação › JSON | Extrair JSON | ✅ tarefas 180/181 (parseia JSON de texto livre; aceita cerca de código) |
| `http_request` | Core › HTTP | HTTP Request | ✅ (guard SSRF + mascaramento) |
| `if` | Fluxo › Lógica | Condição (If) | ✅ (saídas true/false) |
| `switch` | Fluxo › Roteamento | Switch (roteador) | ✅ **N saídas dinâmicas** — modelo "Rules" (n8n): regras `valor [operador] comparar → saída` (reusa operadores/`_comparar` do `if`); 1ª que casa ganha; resto → `default` |
| `delay` | Fluxo › Controle | Aguardar | ✅ (pausa; retoma via cron) |
| `webhook` | Gatilho › Entrada | Webhook | ✅ **trigger** (entrada do fluxo, sem porta de entrada); campo **`responder`** (modo n8n): `imediato` (ack) / `ultimo_no` (output do último nó) / `no_resposta` (usa o nó Responder ao Webhook) |
| `responder_webhook` | Core › Webhook | Responder ao Webhook | ✅ **"Respond to Webhook" (n8n)**: define `status`+`corpo` (aceita `{{...}}`) da resposta HTTP do fluxo via webhook; `webhook_receber` devolve isso em vez do `{execucao_id, status}` padrão |
| `evento` | Gatilho › Sistema | Evento do sistema | ✅ **trigger** (evento + filtros; wiring deferido via `on_evento`, kill-switch `AUTOMACAO_WIRING_ATIVO`) |
| `agenda` | Gatilho › Varredura | Agenda (varredura) | ✅ **trigger** (intervalo + `varredura`, registry em `varreduras.py`; cada item vira 1 execução). Dispatcher `gatilhos.despachar_agendas` (cron `automacao_despachar_agendas`, seed `ativo=False`), CAS em `Fluxo.agenda_ultima_rodada`, rodada sem freio (`max_por_lead`/`cooldown_horas`) é pulada com warning |
| `chat` | Gatilho › Teste | Chat (teste) | ✅ **trigger de teste** (estilo n8n): abre o painel "💬 Chat" no editor; cada mensagem roda o fluxo como `{{var.conteudo}}`. Caminho executado fica verde; INPUT/OUTPUT por nó. |
| `whatsapp_texto` | Integrações › WhatsApp · Uazapi | WhatsApp: enviar mensagem | ✅ (reusa `UazapiService`) |
| `whatsapp_midia` | Integrações › WhatsApp · Uazapi | WhatsApp: enviar mídia | ✅ (image/doc/audio/video) |
| `whatsapp_presenca` | Integrações › WhatsApp · Uazapi | WhatsApp: digitando/presença | ✅ |
| `whatsapp_pergunta` | Integrações › WhatsApp · Uazapi | WhatsApp: enviar e aguardar resposta | ✅ (pausa → retoma na resposta; saídas resposta/timeout) |
| `criar_tarefa` | Comercial › Tarefas | Criar tarefa (CRM) | ✅ **convergência marketing** (service de domínio `services/acoes.py`; saídas sucesso/erro) |
| `notificacao_sistema` | Notificações › Sistema | Notificar equipe (broadcast) | ✅ **convergência marketing** (reusa `notificacoes.criar_notificacao` via `acoes.notificar`) |
| `mover_estagio` | Comercial › Oportunidades | Mover de estágio | ✅ **convergência** (precisa de oportunidade no contexto) |
| `mover_para_perdido_sem_viabilidade` | Comercial › Oportunidades | Perder por viabilidade (motivo {cep}/{cidade}/{uf}) | ✅ **migração funil Fase 1** (porta `_acao_*` p/ `acoes.py`; motor antigo intocado) |
| `adicionar_item_oportunidade` | Comercial › Oportunidades | Vincular plano escolhido (lead.id_plano_rp → ProdutoServico) como item | ✅ **migração funil Fase 1** (porta `_acao_*` p/ `acoes.py`; motor antigo intocado) |
| `criar_oportunidade` | Comercial › Oportunidades | Criar oportunidade (CRM) | ✅ **convergência** (idempotente; pipeline/estágio padrão se vazios) |
| `criar_venda` | Comercial › Vendas | Criar venda | ✅ **convergência** (idempotente; status pendente-ERP) |
| `enviar_venda_whatsapp` | Comercial › Vendas | WhatsApp: enviar resumo da venda | ✅ **migração funil Fase 1** (porta p/ `services/whatsapp.enviar_venda`; idempotente; **picker uazapi**) |
| `gerar_contrato_hubsoft` | Comercial › Contrato | HubSoft: gerar contrato (criar→anexar→aceitar) | ✅ **migração funil Fase 1** 🔴 outbound real; porta p/ `services/contrato_hubsoft`; **picker HubSoft** |
| `assinar_contrato_hubsoft` | Comercial › Contrato | HubSoft: assinar contrato existente | ✅ **migração funil Fase 1** 🔴 outbound real; porta p/ `services/contrato_hubsoft`; **picker HubSoft** |
| `atribuir_responsavel` | Comercial › Oportunidades | Atribuir responsável | ✅ **convergência** (round-robin ou fixo por username) |
| `criar_nota` | Comercial › Oportunidades | Criar nota | ✅ tarefas 180/181 (autor: responsável da op → staff do tenant → superuser) |
| `reabrir_oportunidade` | Comercial › Oportunidades | Reabrir oportunidade | ✅ tarefas 180/181 (idempotente fora de estágio perdido; mantém motivo/responsável como auditoria) |
| `definir_propriedade_oportunidade` | Comercial › Oportunidades | Definir propriedade da oportunidade | ✅ **catálogo de propriedades** (`propriedades_oportunidade.py`, select: `motivo_perda`, `detalhe_perda`, `marcador`, `valor_estimado`), substitui os antigos `definir_motivo_perda`/`marcar_dados_custom`; `aplicado=False` no output é branch de **sucesso** (skip por regra de negócio nunca vira erro/retry) |
| `dar_pontos` | CS › Clube | Dar pontos (Clube) | ✅ **convergência** (CPF do config ou do lead; filtra por tenant) |
| `matrix_hsm` | Integrações › Matrix | Matrix: disparar HSM (WhatsApp) | ✅ **outbound real** (`MatrixBrasilService.enviar_hsm`; template HSM + variáveis) |
| `matrix_atendimento` | Integrações › Matrix | Matrix: transcript do atendimento | ✅ tarefas 180/181 (`MatrixBrasilService.consultar_atendimento`; anonimiza PII por padrão) |
| `hubsoft_sincronizar_prospecto` | Integrações › HubSoft | HubSoft: sincronizar prospecto | ✅ **outbound real** (cria rascunho/atualiza; converge a ação do marketing; precisa de lead) |
| `hubsoft_consultar_cliente` | Integrações › HubSoft | HubSoft: consultar cliente | ✅ read (por CPF/CNPJ; enriquecimento) |
| `hubsoft_listar_faturas` | Integrações › HubSoft | HubSoft: listar faturas | ✅ read (boletos por CPF/CNPJ; só pendentes opcional) |
| `hubsoft_planos_cep` | Integrações › HubSoft | HubSoft: planos por CEP | ✅ read (viabilidade comercial por CEP) |
| `hubsoft_*` (catálogo/cliente/globais/writes) | Integrações › HubSoft | +20 nós HubSoft | ✅ serviços, vencimentos, modelos contrato, viabilidade (endereço/coords), atendimentos/OS (cliente e todos), extrato conexão, renegociações (listar/simular/efetivar), clientes/atendimentos todos, horários agenda, criar/aceitar contrato, abrir/agendar OS. Base `HubsoftNode`; params do método espelhados. 🔴🔴 que afetam serviço ficaram de fora. **Todos os nós HubSoft têm seletor de credencial** (campo "Conta (HubSoft)", fonte `integracoes_hubsoft`; vazio = 1ª ativa). |
| `condicao_comercial` | Fluxo › Lógica | Condição comercial (CRM) | ✅ expõe as 12 condições do `automacao_condicoes` (select + operador + valor); true/false; sobre a oportunidade |
| `acao_comercial` | Comercial › Pipeline | Ação comercial (CRM) | ✅ expõe as 7 ações do `_EXECUTORES_ACAO` (select + params keyvalue); sobre a oportunidade |
| `ia_agente` | IA › Agente | Agente IA | ✅ **D2+D3+D4** referencia um `Agente` gerenciado (dropdown `fonte:agentes`); turno LLM com prompt + **memória configurável** (campo `Agente.memoria`; registry em `services/memoria.py`; 1º tipo `conversa` = mensagens da conversa atual — inbox em prod, turnos do chat no teste — **compartilhada** entre os agentes do fluxo, sem write-back) + **tools** do agente (loop via `chamar_llm_com_tools`) + **RAG** (tool `consultar_base_conhecimento`, base de conhecimento do Suporte com filtro por categoria); resposta em `output.resposta`. |
| `checklist_proximo_item` | Comercial › Checklist | Checklist: próximo item | ✅ ponte checklist→fluxo (bot de vendas vira grafo); acha o próximo item pendente via `services/checklist.proximo_item`; saídas `tem_item`/`completo`/`erro`; sem IA |
| `checklist_validar` | Comercial › Checklist | Checklist: validar resposta | ✅ ponte checklist→fluxo; roda a cascata determinística de `atendimento_ia/services/validacao.validar` (opções/cpf/cep/email/regex) e grava via `registrar_resposta` quando válida; saídas `valida`/`invalida`/`erro`; **nunca chama LLM diretamente** (julgamento semântico livre fica pro grafo encadear `ia_agente`) |
| `checklist_progresso` | Comercial › Checklist | Checklist: progresso | ✅ ponte checklist→fluxo; resumo via `services/checklist.progresso` (total/respondidos/faltando/percentual); saídas `completo`/`incompleto`/`erro`; sem IA |
| `carregar_lead` | Comercial › Leads | Carregar lead | ✅ fecha o gap de `contexto.lead` no caminho HTTP real (o `webhook` genérico não hidrata entidade nenhuma sozinho): resolve por `lead_id` (pk direto) ou `telefone` (só dígitos, tolerante a 55/DDD, sufixos de 8 a 13 dígitos); cria lead mínimo quando `criar_se_nao_existir`; injeta em `contexto.lead` via `NodeResult.entidades` (mecanismo genérico novo, ver `nodes/base.py`/`nodes/context.py`); saídas `encontrado`/`nao_encontrado`/`erro` |

**Modelos de execução (a "âncora"):** o mesmo runtime faz três comportamentos, decididos por como a execução pausa/ancora (`NodeResult.espera` + `ExecucaoFluxo`):
- **timer** (delay) → retoma por tempo (cron).
- **resposta** (whatsapp_pergunta) → pausa ancorada no contato (`chave`); retoma quando ele responde (signal do inbox → `retomar_por_resposta`) ou no timeout (cron → saída `timeout`). A resposta vira `{{var.resposta}}` / `{{nodes.<id>.resposta}}`.
- **lead** (futuro, jornada/enrollment) → execução ancorada no lead, 1 ativa por lead/fluxo, consultável por etapa.

**Nós de domínio (WhatsApp/Uazapi):** reusam `apps.integracoes.services.uazapi.UazapiService` via `apps/automacao/services/whatsapp.py` (`uazapi_do_tenant`) — credenciais por tenant (`IntegracaoAPI` tipo='uazapi'). Sem integração ativa no tenant → erro controlado. **Executor de domínio único** (não reimplementa Uazapi). Categoria `atendimento` (gating por tenant futuro). ⚠️ Enviam de verdade — testar com `--tenant` que tenha Uazapi.

**Nós de gatilho (trigger):** `is_trigger=True` no contrato → sem porta de entrada, são o **início** do fluxo, com forma/cor especial (Gatilho, laranja). `webhook`, `evento` e `agenda` (varredura) já existem. Próximo: **manual**. O token do webhook é gerado no save quando há um nó webhook no grafo; a URL aparece no painel do nó.

## Como testar um nó isolado

```bash
cd robo/dashboard_comercial/gerenciador_vendas
python manage.py testar_no --tipo <tipo> --tenant <slug> \
  --config '{...}' --contexto '{"variaveis": {...}, "nodes": {...}}' \
  --settings=gerenciador_vendas.settings_local
```

Testes unitários em `tests/test_automacao_*.py` (pytest).

## Dívida consciente (registrada, não-Fase 0)

- **HTTP/SSRF:** DNS-rebinding (pinning de IP validado), IPv4-mapped IPv6 (`::ffff:…`), allowlist de destino por tenant.
- **Nó `code`/expressão:** quando vier, **exige sandbox** (asteval/simpleeval) — nunca `eval()`.
- **Volume/runtime:** decidir síncrono-em-cron (modelo marketing) vs. fila dedicada antes de construir o runtime que percorre o grafo.

## Execution log
Ver `execution-log.md` nesta pasta.
