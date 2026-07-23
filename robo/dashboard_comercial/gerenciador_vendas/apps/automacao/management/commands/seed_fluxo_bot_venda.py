"""Seed do BOT DE VENDAS por WhatsApp na engine de automação nova (React Flow).

Decisão de arquitetura (dono do produto): o bot externo (Matrix) conduz a venda
por WhatsApp chamando nossa API a cada turno, mas a LÓGICA da conversa não pode
ser serviço Python escondido — tem que ser um GRAFO visível e editável no
editor, montado com peças que já existem (`carregar_lead`, `switch`,
`checklist_proximo_item`, `checklist_progresso`, `checklist_validar`,
`ia_agente`, `extrair_json`, `webhook`/`responder_webhook`, `if`). A IA usa a
estrutura de `Agente` (prompt configurável na tela), nunca prompt cravado em
código.

UM FLUXO SÓ (revisão desta versão do seed): os 3 endpoints do contrato do
Matrix (`/ia/proximo-passo`, `/ia/validar`, `/ia/recontato`) viviam em 2
fluxos separados e o 3º (recontato) nunca tinha sido construído. O dono do
produto pediu **um fluxo único** com um `switch` na entrada que roteia por
`{{var.payload.acao}}` — "abro uma tela e vejo o bot inteiro". Este seed
SUBSTITUI os 2 fluxos antigos (deletados no fim de `handle`, com guard de
segurança — ver `_remover_fluxos_antigos`) pelo fluxo único abaixo.

Cria:
1. Agente "Validador de respostas" — segunda opinião semântica quando a
   cascata determinística do checklist reprova uma resposta. Prompt copiado
   (não importado) de `apps.comercial.atendimento_ia.services.validacao_ia`
   (`PROMPT_SISTEMA`), propositalmente DESACOPLADO do app legado: o app novo
   não deve depender do `atendimento_ia` (que é a implementação Python que
   este fluxo substitui). Se o prompt original mudar, reaplicar aqui e
   rerodar o seed.
2. Fluxo "[Bot] Venda de internet" — os 3 turnos do bot num grafo só:
   - `roteia` (switch por `{{var.payload.acao}}`) escolhe o ramo:
     `proximo_passo` (qual a próxima pergunta?), `validar` (a resposta do
     cliente serve?) ou `recontato` (cliente sumiu, insiste ou desiste?).
   - `proximo_passo`: só o `checklist_proximo_item` decide (sem IA nesta
     ponta). `status_lead` (0 int "inicia venda" vs "em_andamento") agora é
     DECISÃO DO GRAFO — `checklist_progresso` + `if` conferem se o lead já
     respondeu alguma coisa antes de montar a resposta (ver "CORREÇÃO 2"
     abaixo).
   - `validar`: o nó determinístico (`checklist_validar`) tenta primeiro; só
     quando reprova é que a IA entra como segunda opinião (nó `ia_agente` no
     PRÓPRIO GRAFO); o grafo decide o que fazer com a intenção detectada
     (aceitar, repetir a pergunta ou transbordar pra humano).
   - `recontato` (NOVO, nunca tinha sido construído): decide entre insistir
     ou encerrar por `{{var.payload.tentativa}}` (limite: 2 tentativas, mesmo
     valor de `LIMITE_TENTATIVAS_RECONTATO` do endpoint legado
     `atendimento_ia/views.py::recontato`). A engine nova não replica sessão
     persistida (mesma simplificação que o `proximo_passo` já assumia), então
     `tentativa` vem do PAYLOAD (quem chama controla a contagem), não de um
     contador salvo aqui — igual ao literal do desenho pedido.

O fluxo exige o `Checklist` de slug `venda-internet-bot` do tenant (ver
`seed_checklist_venda`) — o comando falha com erro claro se não achar.

CORREÇÃO 1 (`ura.total_opcoes` como INT, não string): `checklist_proximo_item`
já devolve `total_opcoes` como int no output (`len(item.opcoes or [])`), e
`responder_webhook._resolver_corpo` (patch recente, ver o node) resolve o
`corpo` como OBJETO JSON — quando o template é um dict/list válido, cada
FOLHA com um único token `{{...}}` é resolvida via `Contexto.resolver`, que
preserva o tipo bruto (não passa por interpolação de texto), e o resultado é
serializado de novo com `json.dumps` (não `str()`). Resultado: `total_opcoes`
sai como número no JSON final, sem aspas. Testado explicitamente em
`test_e2e_proximo_passo_...` via `json.loads` + `isinstance(..., int)` (não é
suposição — é o comportamento hoje, dado o corpo ser sempre um dict Python
serializado com `_corpo()`/`json.dumps`, nunca uma string montada à mão).

CORREÇÃO 2 (`status_lead` polimórfico): antes fixo em `"em_andamento"`
(string), o que nunca deixava o Matrix entrar no branch `0` (int, "iniciar
venda"). Agora é decisão do grafo: `checklist_progresso` conta quantas
respostas o lead já tem; um `if` (`{{nodes.progresso.respondidos}}` maior que
`0`) escolhe entre `CORPO_PROXIMO_PERGUNTA_EM_ANDAMENTO` (`status_lead =
"em_andamento"`, string) e `CORPO_PROXIMO_PERGUNTA_INICIO` (`status_lead = 0`,
int, sem aspas).

CORREÇÃO 4 (CLIENTE JÁ ASSINANTE, portado do N8N): assim que a resposta
validada é o CPF, o grafo consulta o HubSoft (`hubsoft_consultar_cliente`) e,
se a pessoa já for cliente, responde com `needsReception="true"` +
`isAClient=true` em vez de seguir vendendo. Era o que o fluxo N8N já fazia e o
nosso não: `isAClient` saía sempre `False` cravado, porque ninguém consultava
nada. Dois detalhes que valem lembrar:
- Cliente inexistente NÃO é erro no HubSoft: volta `status=success` com
  `clientes` vazio (verificado contra a conta da Nuvyon em 20/07). O desvio é
  por lista vazia (`if` com operador `nao_vazio`), não por branch de erro.
- A saída `erro` da consulta cai no MESMO `resp_ok` do caminho normal: HubSoft
  fora do ar não pode travar a venda. Perder a checagem é menos grave que
  perder o atendimento.
`status_lead="cliente_ativo"` (3º valor do contrato) segue fora de escopo no
ramo `proximo_passo`: a checagem acontece no ramo `validar`, que é onde o CPF
chega, e ali o campo do contrato é `isAClient`, não `status_lead`.

CORREÇÃO 3 (GAP DO LEAD): os nós de checklist exigem `contexto.lead` já
carregado; o gatilho `webhook` genérico só hidrata `{{var.payload}}`, nunca
uma entidade de domínio. O nó novo `carregar_lead` (logo depois do trigger)
resolve o `LeadProspecto` por `lead_id` ou `telefone` do payload (cria um
mínimo se não achar) e injeta em `contexto.lead` via `NodeResult.entidades`
(mecanismo genérico novo em `nodes/base.py`/`nodes/context.py` — ver os
módulos). Os 3 branches de `carregar_lead` (`encontrado`/`nao_encontrado`/
`erro`) alimentam `roteia` igualmente: se o lead não foi resolvido,
`contexto.lead` continua `None` e os próprios nós de checklist caem no branch
`erro` deles (que já tinham que existir de qualquer forma) — sem precisar de
tratamento duplicado aqui.

Idempotente por nome (fluxo) / nome (agente): rerodar ATUALIZA o grafo/prompt
em vez de duplicar, e PRESERVA o `ativo` de quem já existe (nunca liga nem
desliga nada sozinho, mesmo padrão de `seed_fluxos_recuperacao_analise`).
Tudo nasce INATIVO (`ativo=False`) — revisar no editor antes de ligar.

Uso:
    python manage.py seed_fluxo_bot_venda --tenant nuvyon \\
        --settings=gerenciador_vendas.settings_local
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.automacao.management.commands.seed_checklist_venda import SLUG_CHECKLIST
from apps.automacao.models import Agente, Checklist, Fluxo
from apps.automacao.runtime import validar_fluxo

NOME_AGENTE_VALIDADOR = 'Validador de respostas'
NOME_FLUXO = '[Bot] Venda de internet'

# Nomes dos 2 fluxos separados que este seed substitui (versão anterior).
# `_remover_fluxos_antigos` só apaga se estiverem inativos e sem execuções.
NOME_FLUXO_ANTIGO_PROXIMO = '[Bot] Venda de internet: próximo passo'
NOME_FLUXO_ANTIGO_VALIDAR = '[Bot] Venda de internet: validar resposta'
NOMES_FLUXOS_ANTIGOS = (NOME_FLUXO_ANTIGO_PROXIMO, NOME_FLUXO_ANTIGO_VALIDAR)

# Limite de tentativas de recontato (mesmo valor do endpoint legado
# `atendimento_ia/views.py::LIMITE_TENTATIVAS_RECONTATO`): a partir da
# tentativa seguinte a este número, o grafo encerra em vez de insistir de novo.
LIMITE_TENTATIVAS_RECONTATO = 2

# Chaves de item do checklist que disparam uma checagem externa no ramo
# "validar". Ficam aqui porque o grafo referencia as duas; no fluxo em si elas
# viram config de um nó `if`, editável no editor sem passar por deploy.
CHAVE_CPF = 'cpf_cnpj'
CHAVE_CEP = 'cep'
CHAVE_ENDERECO_CONFIRMADO = 'endereco_confirmado'

DESCRICAO_AGENTE = (
    'Segunda opinião semântica pras respostas do checklist de venda que a '
    'cascata determinística (`checklist_validar`) reprovou. Só entra quando o '
    f'ramo "validar" do fluxo "{NOME_FLUXO}" chama, nunca sozinho. Contrato de '
    'saída em JSON (valido, dados_extraidos, mensagem_bot, motivo_invalido, '
    'confianca, intencao_detectada). Nasce INATIVO.'
)

DESCRICAO_FLUXO = (
    'Bot de vendas por WhatsApp, fluxo ÚNICO: os 3 turnos que o Matrix chama '
    '(qual a próxima pergunta / a resposta serve / o cliente sumiu, insisto ou '
    'desisto) entram por um `switch` que roteia por `{{var.payload.acao}}` '
    '("proximo_passo" / "validar" / "recontato"). `carregar_lead` fecha o gap '
    'de `contexto.lead` logo após o trigger (o webhook genérico não hidrata '
    'entidade nenhuma sozinho). O determinístico (`checklist_validar`) tenta '
    'primeiro no ramo "validar"; só quando reprova é que o Agente IA '
    '"Validador de respostas" entra como segunda opinião, DENTRO do próprio '
    'grafo — nunca como serviço Python escondido. `status_lead` (0 int vs '
    '"em_andamento" string) é decisão do grafo via `checklist_progresso`. '
    'Corpo das respostas em JSON, campos e tipos seguindo '
    '`apps.comercial.atendimento_ia.services.contrato` (`payload_proximo_passo` '
    '/ `payload_validar` / `payload_recontato`; atenção: `needsReception` e '
    '`deve_transbordar` são STRING "true"/"false", não boolean). Nasce INATIVO.'
)

# ── Prompt do Agente "Validador de respostas" ───────────────────────────────
# Copiado (não importado) de
# apps/comercial/atendimento_ia/services/validacao_ia.py::PROMPT_SISTEMA —
# propositalmente desacoplado do app legado (ver docstring do módulo). Se o
# original mudar, replicar aqui e rerodar o seed.
_PLACEHOLDER_EMPRESA = '{{empresa}}'

_PROMPT_SISTEMA_VALIDADOR = (
    f'Voce e um atendente humano de um provedor de internet chamado {_PLACEHOLDER_EMPRESA}. '
    'Tom cordial e direto, como quem atende WhatsApp de verdade. Nunca revele que e uma IA.\n\n'
    'Sua tarefa e validar se a resposta do cliente serve pra pergunta feita. '
    'Responda SEMPRE e SOMENTE com um JSON valido, sem markdown, sem texto antes ou depois, '
    'no formato exato:\n'
    '{"valido": true ou false, "dados_extraidos": {}, "mensagem_bot": "", '
    '"motivo_invalido": "", "confianca": 0.0 a 1.0, "intencao_detectada": ""}\n\n'
    'Regras:\n'
    'valido = false quando a resposta nao serve pra pergunta (fora de contexto, incompleta, '
    'ambigua ou claramente errada).\n'
    'dados_extraidos: o dado que a pergunta pedia, ja normalizado (ex: nome, motivo, endereco). '
    'Vazio quando invalido.\n'
    'mensagem_bot: quando invalido, peca a informacao de novo de forma gentil e curta '
    '(1 a 2 frases, no maximo 1 emoji). Quando valido pode ficar vazio.\n'
    'motivo_invalido: motivo curto, poucas palavras, so quando invalido.\n'
    'confianca: o quanto voce tem certeza do julgamento, de 0.0 a 1.0.\n'
    'intencao_detectada: um destes valores. ok (resposta normal), duvida (cliente perguntou '
    'algo em vez de responder), desistir (cliente quer parar ou cancelar o atendimento), '
    'transferir_humano (cliente pede pra falar com atendente).'
)


def _system_prompt_validador(tenant):
    nome_tenant = getattr(tenant, 'nome', '') or 'a empresa'
    return _PROMPT_SISTEMA_VALIDADOR.replace(_PLACEHOLDER_EMPRESA, nome_tenant)


# ── Corpo dos `responder_webhook` ────────────────────────────────────────────
# Construído via `json.dumps` de um dict Python (nunca texto JSON escrito à
# mão): garante que o TEMPLATE em si é JSON válido. Cada valor dinâmico é um
# único token `{{...}}` (full match), que o `Contexto.resolver` devolve CRU
# (tipo preservado: bool/número/lista) — o `responder_webhook` resolve o
# objeto inteiro e serializa com `json.dumps`, escapando de verdade quebra de
# linha/aspas do texto da pergunta. Valores estáticos (sem `{{...}}`) passam
# direto — é assim que `status_lead=0` (int) e `status_lead='em_andamento'`
# (string) saem com o tipo certo no JSON final (ver CORREÇÃO 2 no topo do
# arquivo): o valor já nasce no tipo certo em Python, `json.dumps` cuida do
# resto.

def _corpo(template):
    return json.dumps(template, ensure_ascii=False)


# payload_proximo_passo (contrato: apps.comercial.atendimento_ia.services.contrato)
def _corpo_proxima_pergunta(status_lead):
    """`status_lead` decide o tipo no contrato: `0` (int, lead nunca respondeu
    nada — "iniciar venda") ou `'em_andamento'` (string, retomando). Builder
    único pros 2 casos pra não duplicar o resto do payload e correr risco de
    os dois corpos divergirem num campo que devia ser igual (a mesma armadilha
    da CORREÇÃO 1: um `{{...}}` diferente por engano vira bug silencioso)."""
    return _corpo({
        'lead_id': '{{lead.id}}',
        'status_lead': status_lead,
        'proximo_passo': 'seguir_pergunta',
        'proxima_pergunta_id': '{{nodes.proximo.item_id}}',
        'deve_perguntar': True,
        'deve_transbordar': 'false',
        'motivo': '',
        'intent_detectado': '',
        'mensagem_inicial': '{{nodes.proximo.pergunta}}',
        'ura': {
            'total_opcoes': '{{nodes.proximo.total_opcoes}}',
            'titulo': '{{nodes.proximo.ura_titulo}}',
            # Inclui `valor` além de `texto` (o contrato original só usa `texto`):
            # informação extra que o Matrix pode ignorar sem quebrar.
            'opcoes': '{{nodes.proximo.opcoes}}',
            'pergunta': '{{nodes.proximo.pergunta}}',
        },
    })


CORPO_PROXIMO_PERGUNTA_EM_ANDAMENTO = _corpo_proxima_pergunta('em_andamento')
CORPO_PROXIMO_PERGUNTA_INICIO = _corpo_proxima_pergunta(0)

CORPO_PROXIMO_ENCERRAR = _corpo({
    'lead_id': '{{lead.id}}',
    # Checklist completo implica que existe pelo menos uma resposta: nunca é 0.
    'status_lead': 'em_andamento',
    'proximo_passo': 'red_encerrar',
    'proxima_pergunta_id': 0,
    'deve_perguntar': False,
    'deve_transbordar': 'false',
    'motivo': '',
    'intent_detectado': '',
    'mensagem_inicial': '',
    'ura': {'total_opcoes': 0, 'titulo': '', 'opcoes': [], 'pergunta': ''},
})

# payload_validar (contrato: apps.comercial.atendimento_ia.services.contrato)
# Corpo de erro estrutural GENÉRICO: compartilhado pelos ramos "proximo_passo"
# e "validar" (e pelo `default` do switch de entrada) — mesmo node/handle
# reaproveitado a partir de várias origens, igual ao seed anterior já fazia
# dentro do ramo "validar". Fica no formato `payload_validar`; um chamador do
# ramo "proximo_passo" que caia aqui recebe campos fora do shape que ele
# esperava (`resposta_correta`/`needsReception` em vez de
# `proximo_passo`/`ura`) — aceito conscientemente: é sempre um caminho de
# ERRO estrutural (sem lead, checklist ausente, exceção), o Matrix já trata
# isso como falha e cai pro fallback dele; criar um 2º corpo de erro só pra
# manter o shape "puro" nesse caminho de exceção não pagava o custo extra de
# nó/manutenção pro benefício (documentado aqui pra próxima revisão avaliar).
_MSG_ERRO_ESTRUTURAL = (
    'Não consegui continuar o atendimento automático agora. Vou te transferir '
    'para um atendente.'
)

# ATENCAO ao campo `message`: o bot do Matrix envia esse texto direto no
# WhatsApp em DOIS ramos (`msg_resultado` no caminho valido e
# `msg_pre_transbordo` quando `needsReception="true"`). Mensagem vazia trava a
# conversa: o nó de envio dele não completa, então o fluxo nunca volta a
# perguntar e o cliente fica sem resposta. Achado no teste com o emulador em
# 19/07: o CPF gravava aqui e o bot emudecia lá. Nenhum `message` de ramo que
# o Matrix envia pode ficar em branco.
# NOTA de tipo (achado no teste com o emulador em 19/07): `resposta_correta` vai
# como TEXTO 'true'/'false', nao como booleano JSON. O bot do Matrix nao compara
# booleano cru: ele caia sempre no ramo do erro mesmo recebendo `true`. Os outros
# dois campos de sim/nao do contrato (`needsReception`, `deve_transbordar`) ja
# eram texto pelo mesmo motivo; este passou batido. A condicao do lado do Matrix
# compara com "false" ENTRE ASPAS.
CORPO_VALIDAR_OK = _corpo({
    'resposta_correta': 'true',
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '',
    'needsReception': 'false',
    'isAClient': False,
    'cancelado': False,
    'message': '{{nodes.validar.mensagem_sucesso}}',
})

CORPO_VALIDAR_ERRO = _corpo({
    'resposta_correta': 'false',
    'resposta_sem_erro_api': False,
    'retorno_erro_api': _MSG_ERRO_ESTRUTURAL,
    'needsReception': 'true',
    'isAClient': False,
    'cancelado': False,
    'message': _MSG_ERRO_ESTRUTURAL,
})

CORPO_VALIDAR_OK_IA = _corpo({
    'resposta_correta': 'true',
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '',
    'needsReception': 'false',
    'isAClient': False,
    'cancelado': False,
    'message': '{{nodes.json.mensagem_bot}}',
})

CORPO_VALIDAR_TRANSBORDO = _corpo({
    'resposta_correta': 'false',
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '{{nodes.json.mensagem_bot}}',
    'needsReception': 'true',
    'isAClient': False,
    'cancelado': False,
    # `needsReception=true` leva o Matrix pro `msg_pre_transbordo`, que envia
    # este campo (nao o `retorno_erro_api`), entao repete a mesma despedida.
    'message': '{{nodes.json.mensagem_bot}}',
})

CORPO_VALIDAR_REPERGUNTA = _corpo({
    'resposta_correta': 'false',
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '{{nodes.json.mensagem_bot}}',
    'needsReception': 'false',
    'isAClient': False,
    'cancelado': False,
    'message': '',
})

# Mensagem de quem JA e cliente. O bot nao deve tentar vender internet pra
# assinante: manda pro atendimento humano, que resolve o que a pessoa precisa.
MSG_JA_E_CLIENTE = (
    'Vi aqui que voce ja e nosso cliente ##1f60a## Vou te transferir para um '
    'atendente que cuida de quem ja esta com a gente.'
)

# Sem cobertura confirmada o bot NAO segue vendendo: decisao do dono do produto
# em 20/07 (transbordar em vez de encerrar ou registrar pra recontato). A
# mensagem serve pros tres desfechos que nao sao "atende" (fora de cobertura,
# pendente de revisao e erro), entao nao afirma que a regiao nao tem cobertura:
# em dois desses casos a gente simplesmente NAO SABE, e cravar isso pro cliente
# derruba venda boa.
MSG_SEM_VIABILIDADE = (
    'Preciso confirmar a disponibilidade no seu endereco ##1f4cd## Vou te '
    'transferir para um atendente que verifica isso pra voce.'
)

# CPF de quem JA e cliente HubSoft. A resposta do CPF e valida (o cliente
# digitou certo), mas a venda para aqui: `needsReception="true"` e o unico
# gatilho de transbordo que o flow do Matrix realmente avalia hoje. O campo
# `isAClient` tambem vai preenchido porque faz parte do contrato e o Matrix
# guarda o valor, mesmo sem ramificar por ele ainda.
CORPO_VALIDAR_JA_CLIENTE = _corpo({
    'resposta_correta': 'true',
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '',
    'needsReception': 'true',
    'isAClient': True,
    'cancelado': False,
    'message': MSG_JA_E_CLIENTE,
})

# Endereco sem cobertura confirmada. Igual ao caso do cliente: a resposta do
# cliente estava certa, o que muda e o destino do atendimento.
CORPO_VALIDAR_SEM_VIABILIDADE = _corpo({
    'resposta_correta': 'true',
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '',
    'needsReception': 'true',
    'isAClient': False,
    'cancelado': False,
    'message': MSG_SEM_VIABILIDADE,
})

# payload_recontato (contrato: apps.comercial.atendimento_ia.services.contrato)
# `pergunta_id`/`tentativa` ecoam o que o Matrix mandou: a engine nova não
# replica sessão persistida (mesma simplificação já assumida no ramo
# "proximo_passo"), então não há contador de tentativa nem "item atual"
# guardado aqui — quem chama controla a contagem. `resp_recontato_encerrar` é
# compartilhado entre "tentativas esgotadas" e "nada mais pendente" (fan-in,
# mesmo padrão do `resp_erro`); por isso não referencia texto de pergunta.
CORPO_RECONTATO_ENCERRAR = _corpo({
    'pergunta_id': '{{var.payload.pergunta_id}}',
    'acao': 'encerrar',
    'tentativa': '{{var.payload.tentativa}}',
    'reperguntar': False,
    'mensagem': '',
    'deve_transbordar': 'true',
})

CORPO_RECONTATO_INSISTIR = _corpo({
    'pergunta_id': '{{nodes.proximo_recontato.item_id}}',
    'acao': 'reperguntar',
    'tentativa': '{{var.payload.tentativa}}',
    'reperguntar': True,
    'mensagem': 'Ainda esta ai? {{nodes.proximo_recontato.pergunta}}',
    'deve_transbordar': 'false',
})

# Mensagem que o nó `ia_agente` manda pro LLM: pergunta original + resposta do
# cliente (o `checklist_validar` expõe `pergunta` no output pra isso, ver node).
MENSAGEM_AGENTE_VALIDADOR = (
    'Pergunta feita ao cliente: {{nodes.validar.pergunta}}\n'
    'Resposta do cliente: {{var.payload.answer}}'
)


def _grafo_bot_venda(agente_id):
    nodes = {
        # ── entrada + gap do lead ────────────────────────────────────────
        'trigger': {
            'tipo': 'webhook',
            'config': {'responder': 'no_resposta'},
            'pos': {'x': 0, 'y': 0},
            'label': 'Webhook: turno do bot (Matrix)',
        },
        'hidratar': {
            'tipo': 'carregar_lead',
            'config': {
                'telefone': '{{var.payload.cellphone}}',
                'lead_id': '{{var.payload.lead_id}}',
                'criar_se_nao_existir': True,
            },
            'pos': {'x': 300, 'y': 0},
            'label': 'Carregar lead (fecha o gap do contexto)',
        },
        'roteia': {
            'tipo': 'switch',
            'config': {'regras': [
                {'esquerda': '{{var.payload.acao}}', 'operador': 'igual',
                 'direita': 'proximo_passo', 'saida': 'proximo_passo'},
                {'esquerda': '{{var.payload.acao}}', 'operador': 'igual',
                 'direita': 'validar', 'saida': 'validar'},
                {'esquerda': '{{var.payload.acao}}', 'operador': 'igual',
                 'direita': 'recontato', 'saida': 'recontato'},
            ]},
            'pos': {'x': 600, 'y': 0},
            'label': 'Switch: {{var.payload.acao}}',
        },

        # ── ramo "proximo_passo" ─────────────────────────────────────────
        'proximo': {
            'tipo': 'checklist_proximo_item',
            'config': {'checklist': SLUG_CHECKLIST, 'entidade': 'lead'},
            'pos': {'x': 950, 'y': -520},
            'label': 'Checklist: próxima pergunta',
        },
        'resp_fim': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_PROXIMO_ENCERRAR},
            'pos': {'x': 1250, 'y': -760},
            'label': 'Responder: checklist completo (encerrar)',
        },
        'progresso': {
            'tipo': 'checklist_progresso',
            'config': {'checklist': SLUG_CHECKLIST, 'entidade': 'lead'},
            'pos': {'x': 1250, 'y': -520},
            'label': 'Checklist: progresso (decide status_lead)',
        },
        'ja_respondeu': {
            'tipo': 'if',
            'config': {'esquerda': '{{nodes.progresso.respondidos}}',
                       'operador': 'maior', 'direita': '0'},
            'pos': {'x': 1550, 'y': -520},
            'label': 'Lead já respondeu algo?',
        },
        'resp_pergunta': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_PROXIMO_PERGUNTA_EM_ANDAMENTO},
            'pos': {'x': 1850, 'y': -640},
            'label': 'Responder: próxima pergunta (em andamento)',
        },
        'resp_pergunta_inicio': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_PROXIMO_PERGUNTA_INICIO},
            'pos': {'x': 1850, 'y': -420},
            'label': 'Responder: próxima pergunta (status_lead=0, iniciar venda)',
        },

        # ── ramo "validar" ───────────────────────────────────────────────
        'validar': {
            'tipo': 'checklist_validar',
            'config': {
                'checklist': SLUG_CHECKLIST,
                'item_id': '{{var.payload.question_id}}',
                'resposta': '{{var.payload.answer}}',
                'entidade': 'lead',
            },
            'pos': {'x': 950, 'y': 40},
            'label': 'Checklist: validar resposta (determinístico)',
        },
        # Toda resposta valida tambem vai pra FICHA do lead, nao so pra tabela
        # de respostas do checklist. Sem isso a vendedora abria o lead e via
        # CPF, email e endereco vazios, mesmo o bot tendo coletado tudo.
        # UM no so: a chave do item tem o mesmo nome do campo do lead, entao
        # `{{nodes.validar.chave}}` resolve qual campo escrever em execucao.
        # Chave que nao e campo do lead (`tipo_imovel`, `plano_confirmado`)
        # cai em skip, que e o caso normal e nao interrompe nada.
        'grava_no_lead': {
            'tipo': 'definir_propriedade_lead',
            'config': {
                'propriedade': '{{nodes.validar.chave}}',
                'valor': '{{nodes.validar.valor_processado}}',
                # Nao sobrescreve o que ja tem valor: o cliente pode
                # reperguntar um item e um humano pode ter corrigido a ficha
                # no meio do caminho.
                'somente_se_vazio': True,
            },
            'pos': {'x': 1100, 'y': 40},
            'label': 'Gravar na ficha do lead',
        },
        # ── Checagem de cliente HubSoft, so quando a resposta validada e o CPF ──
        # Portado do que o N8N ja fazia: assim que o CPF chega, consulta o
        # HubSoft e, se a pessoa ja for assinante, transborda em vez de seguir
        # vendendo. Fecha o gap do `status_lead="cliente_ativo"`/`isAClient`,
        # que ate aqui saia sempre negativo porque ninguem consultava nada.
        'e_cpf': {
            'tipo': 'if',
            'config': {
                'esquerda': '{{nodes.validar.chave}}',
                'operador': 'igual',
                'direita': CHAVE_CPF,
            },
            'pos': {'x': 1250, 'y': 40},
            'label': 'A resposta era o CPF?',
        },
        'consultar_cliente': {
            'tipo': 'hubsoft_consultar_cliente',
            # `valor_processado` e o CPF ja normalizado pela cascata de
            # validacao (so digitos), que e o formato que o HubSoft espera.
            'config': {'cpf_cnpj': '{{nodes.validar.valor_processado}}'},
            'pos': {'x': 1550, 'y': -80},
            'label': 'HubSoft: já é cliente?',
        },
        'e_cliente': {
            'tipo': 'if',
            # Cliente inexistente NAO da erro no HubSoft: volta
            # `status=success` com `clientes` vazio (verificado contra a conta
            # da Nuvyon em 20/07). Por isso o teste e de lista vazia, nao de
            # branch de erro.
            'config': {
                'esquerda': '{{nodes.consultar_cliente.cliente.clientes}}',
                'operador': 'nao_vazio',
                'direita': '',
            },
            'pos': {'x': 1850, 'y': -80},
            'label': 'Achou cliente?',
        },
        'resp_ja_cliente': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_JA_CLIENTE},
            'pos': {'x': 2150, 'y': -200},
            'label': 'Responder: já é cliente, transborda',
        },
        # ── Checagem de cobertura, so quando o cliente confirma o endereco ──
        # Portado do N8N, que consulta viabilidade logo apos a confirmacao.
        # ── Endereco a partir do CEP, so quando a resposta validada e o CEP ──
        # O cliente digita so o CEP; a pergunta seguinte confirma o endereco
        # ("Confira: {rua}, {bairro}, {cidade}"). O ViaCEP busca esses campos e
        # grava no lead, pra que a pergunta de confirmacao (um turno depois)
        # ja encontre a ficha preenchida (`checklist_proximo_item` renderiza os
        # `{campo}`). Sem isso a confirmacao mostrava `{rua}` cru pro cliente.
        'e_cep': {
            'tipo': 'if',
            'config': {
                'esquerda': '{{nodes.validar.chave}}',
                'operador': 'igual',
                'direita': CHAVE_CEP,
            },
            'pos': {'x': 1250, 'y': 200},
            'label': 'A resposta era o CEP?',
        },
        'viacep_lookup': {
            'tipo': 'viacep',
            'config': {
                'cep': '{{nodes.validar.valor_processado}}',
                'gravar_no_lead': True,
            },
            'pos': {'x': 1550, 'y': 200},
            'label': 'ViaCEP: busca e grava o endereço',
        },
        'e_endereco': {
            'tipo': 'if',
            'config': {
                'esquerda': '{{nodes.validar.chave}}',
                'operador': 'igual',
                'direita': CHAVE_ENDERECO_CONFIRMADO,
            },
            'pos': {'x': 1250, 'y': 360},
            'label': 'Confirmou o endereço?',
        },
        # O endereco foi montado ao longo da conversa, em turnos anteriores.
        # `checklist_validar` so enxerga a resposta do turno corrente, dai o nó
        # que devolve TODAS as respostas ja dadas.
        'respostas': {
            'tipo': 'checklist_respostas',
            'config': {'checklist': SLUG_CHECKLIST, 'entidade': 'lead'},
            'pos': {'x': 1550, 'y': 200},
            'label': 'Respostas já dadas',
        },
        'viabilidade': {
            'tipo': 'viabilidade_consultar',
            'config': {
                'cep': '{{nodes.respostas.cep}}',
                'logradouro': '{{nodes.respostas.rua}}',
                'numero': '{{nodes.respostas.numero_residencia}}',
                'bairro': '{{nodes.respostas.bairro}}',
                'cidade': '{{nodes.respostas.cidade}}',
                'uf': '{{nodes.respostas.uf}}',
            },
            'pos': {'x': 1850, 'y': 200},
            'label': 'Tem cobertura?',
        },
        'resp_sem_viabilidade': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_SEM_VIABILIDADE},
            'pos': {'x': 2150, 'y': 320},
            'label': 'Responder: sem cobertura confirmada, transborda',
        },
        'resp_ok': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_OK},
            'pos': {'x': 2150, 'y': -80},
            'label': 'Responder: resposta válida',
        },
        'agente': {
            'tipo': 'ia_agente',
            'config': {'agente_id': str(agente_id), 'mensagem': MENSAGEM_AGENTE_VALIDADOR},
            'pos': {'x': 1250, 'y': 160},
            'label': 'Agente IA: segunda opinião (Validador de respostas)',
        },
        'json': {
            'tipo': 'extrair_json',
            'config': {'origem': '{{nodes.agente.resposta}}'},
            'pos': {'x': 1550, 'y': 160},
            'label': 'Extrair JSON da validação',
        },
        'se_valido': {
            'tipo': 'if',
            'config': {'esquerda': '{{nodes.json.valido}}', 'operador': 'igual', 'direita': 'True'},
            'pos': {'x': 1850, 'y': 160},
            'label': 'IA validou?',
        },
        'resp_ok_ia': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_OK_IA},
            'pos': {'x': 2150, 'y': 40},
            'label': 'Responder: aceita pela IA',
        },
        'se_desistiu': {
            'tipo': 'if',
            'config': {
                'esquerda': '{{nodes.json.intencao_detectada}}',
                'operador': 'igual', 'direita': 'desistir',
            },
            'pos': {'x': 2150, 'y': 300},
            'label': 'Cliente quer desistir?',
        },
        'resp_transbordo': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_TRANSBORDO},
            'pos': {'x': 2450, 'y': 200},
            'label': 'Responder: transbordo (desistência)',
        },
        'resp_repergunta': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_REPERGUNTA},
            'pos': {'x': 2450, 'y': 420},
            'label': 'Responder: repetir a pergunta',
        },

        # ── ramo "recontato" (novo) ──────────────────────────────────────
        # `proximo_recontato` é uma 2ª chamada a `checklist_proximo_item`
        # (não reaproveita o handle `proximo` do ramo "proximo_passo"): cada
        # nó só tem UM conjunto de arestas de saída por handle no grafo, e os
        # 2 ramos precisam rotear o `tem_item`/`completo` pra lugares
        # diferentes. É a fonte de verdade do texto da "pergunta atual" pro
        # "Ainda esta ai? <pergunta>" (server-side, não depende do Matrix
        # ecoar o texto de volta).
        'proximo_recontato': {
            'tipo': 'checklist_proximo_item',
            'config': {'checklist': SLUG_CHECKLIST, 'entidade': 'lead'},
            'pos': {'x': 950, 'y': 700},
            'label': 'Checklist: pergunta atual (recontato)',
        },
        'se_esgotou': {
            'tipo': 'if',
            'config': {'esquerda': '{{var.payload.tentativa}}',
                       'operador': 'maior', 'direita': str(LIMITE_TENTATIVAS_RECONTATO)},
            'pos': {'x': 1250, 'y': 700},
            'label': f'Esgotou tentativas (> {LIMITE_TENTATIVAS_RECONTATO})?',
        },
        'resp_recontato_encerrar': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_RECONTATO_ENCERRAR},
            'pos': {'x': 1550, 'y': 820},
            'label': 'Responder: encerrar recontato',
        },
        'resp_recontato_insistir': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_RECONTATO_INSISTIR},
            'pos': {'x': 1550, 'y': 600},
            'label': 'Responder: insistir (reperguntar)',
        },

        # ── erro estrutural compartilhado (fan-in: proximo_passo/validar/recontato/default) ──
        'resp_erro': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_ERRO},
            'pos': {'x': 1250, 'y': 1020},
            'label': 'Responder: erro estrutural (transbordo)',
        },
    }
    conexoes = [
        # entrada
        {'de': 'trigger', 'para': 'hidratar', 'saida': 'default'},
        {'de': 'hidratar', 'para': 'roteia', 'saida': 'encontrado'},
        {'de': 'hidratar', 'para': 'roteia', 'saida': 'nao_encontrado'},
        {'de': 'hidratar', 'para': 'roteia', 'saida': 'erro'},
        {'de': 'roteia', 'para': 'proximo', 'saida': 'proximo_passo'},
        {'de': 'roteia', 'para': 'validar', 'saida': 'validar'},
        {'de': 'roteia', 'para': 'proximo_recontato', 'saida': 'recontato'},
        {'de': 'roteia', 'para': 'resp_erro', 'saida': 'default'},

        # proximo_passo
        {'de': 'proximo', 'para': 'progresso', 'saida': 'tem_item'},
        {'de': 'proximo', 'para': 'resp_fim', 'saida': 'completo'},
        {'de': 'proximo', 'para': 'resp_erro', 'saida': 'erro'},
        {'de': 'progresso', 'para': 'ja_respondeu', 'saida': 'completo'},
        {'de': 'progresso', 'para': 'ja_respondeu', 'saida': 'incompleto'},
        {'de': 'progresso', 'para': 'resp_erro', 'saida': 'erro'},
        {'de': 'ja_respondeu', 'para': 'resp_pergunta', 'saida': 'true'},
        {'de': 'ja_respondeu', 'para': 'resp_pergunta_inicio', 'saida': 'false'},

        # validar
        # Resposta valida vai pra ficha do lead e so entao segue pras checagens.
        {'de': 'validar', 'para': 'grava_no_lead', 'saida': 'valida'},
        {'de': 'validar', 'para': 'resp_erro', 'saida': 'erro'},
        # Gravar na ficha nunca pode barrar o atendimento: os dois branches
        # seguem pro mesmo lugar. A resposta ja esta salva na tabela do
        # checklist de qualquer forma, a ficha e conveniencia pra vendedora.
        {'de': 'grava_no_lead', 'para': 'e_cpf', 'saida': 'sucesso'},
        {'de': 'grava_no_lead', 'para': 'e_cpf', 'saida': 'erro'},
        # So o CPF dispara a consulta de cliente; as demais seguem pra proxima
        # checagem (uma chamada de API por resposta seria desperdicio, e o bot
        # tem 45s de teto por turno).
        {'de': 'e_cpf', 'para': 'consultar_cliente', 'saida': 'true'},
        {'de': 'e_cpf', 'para': 'e_cep', 'saida': 'false'},
        # Era o CEP: busca o endereco e grava no lead, depois responde normal.
        # Os tres desfechos do ViaCEP (achou, nao achou, erro) seguem pro mesmo
        # `resp_ok`: a resposta do cliente (o CEP) estava valida de qualquer
        # forma, o enriquecimento e best effort e nunca barra a conversa.
        {'de': 'e_cep', 'para': 'viacep_lookup', 'saida': 'true'},
        {'de': 'e_cep', 'para': 'e_endereco', 'saida': 'false'},
        {'de': 'viacep_lookup', 'para': 'resp_ok', 'saida': 'encontrado'},
        {'de': 'viacep_lookup', 'para': 'resp_ok', 'saida': 'nao_encontrado'},
        {'de': 'viacep_lookup', 'para': 'resp_ok', 'saida': 'erro'},
        {'de': 'consultar_cliente', 'para': 'e_cliente', 'saida': 'sucesso'},
        # HubSoft fora do ar NAO pode travar a venda: segue o fluxo normal.
        # Perder a checagem de cliente e menos grave que perder o atendimento.
        {'de': 'consultar_cliente', 'para': 'resp_ok', 'saida': 'erro'},
        {'de': 'e_cliente', 'para': 'resp_ja_cliente', 'saida': 'true'},
        {'de': 'e_cliente', 'para': 'resp_ok', 'saida': 'false'},
        # Confirmou o endereco: checa cobertura antes de seguir vendendo.
        {'de': 'e_endereco', 'para': 'respostas', 'saida': 'true'},
        {'de': 'e_endereco', 'para': 'resp_ok', 'saida': 'false'},
        {'de': 'respostas', 'para': 'viabilidade', 'saida': 'sucesso'},
        # Sem nenhuma resposta guardada nao ha endereco pra consultar. Nao e
        # erro (pode ser conversa recomecando), so nao ha o que checar.
        {'de': 'respostas', 'para': 'resp_ok', 'saida': 'vazio'},
        {'de': 'respostas', 'para': 'resp_ok', 'saida': 'erro'},
        {'de': 'viabilidade', 'para': 'resp_ok', 'saida': 'cobertura_ok'},
        # Os TRES desfechos que nao sao "atende" transbordam (decisao do dono
        # do produto). `pendente_revisao` inclui resposta que a gente nao sabe
        # interpretar: cravar "sem cobertura" nesse caso derruba venda boa.
        {'de': 'viabilidade', 'para': 'resp_sem_viabilidade', 'saida': 'fora_cobertura'},
        {'de': 'viabilidade', 'para': 'resp_sem_viabilidade', 'saida': 'pendente_revisao'},
        {'de': 'viabilidade', 'para': 'resp_sem_viabilidade', 'saida': 'erro'},
        # Se a IA cair ou devolver algo que nao e JSON, o turno ainda responde
        # ao Matrix pelo caminho de erro, em vez de morrer sem resposta.
        {'de': 'agente', 'para': 'resp_erro', 'saida': 'erro'},
        {'de': 'json', 'para': 'resp_erro', 'saida': 'erro'},
        {'de': 'validar', 'para': 'agente', 'saida': 'invalida'},
        {'de': 'agente', 'para': 'json', 'saida': 'sucesso'},
        {'de': 'json', 'para': 'se_valido', 'saida': 'sucesso'},
        {'de': 'se_valido', 'para': 'resp_ok_ia', 'saida': 'true'},
        {'de': 'se_valido', 'para': 'se_desistiu', 'saida': 'false'},
        {'de': 'se_desistiu', 'para': 'resp_transbordo', 'saida': 'true'},
        {'de': 'se_desistiu', 'para': 'resp_repergunta', 'saida': 'false'},

        # recontato
        {'de': 'proximo_recontato', 'para': 'se_esgotou', 'saida': 'tem_item'},
        {'de': 'proximo_recontato', 'para': 'resp_recontato_encerrar', 'saida': 'completo'},
        {'de': 'proximo_recontato', 'para': 'resp_erro', 'saida': 'erro'},
        {'de': 'se_esgotou', 'para': 'resp_recontato_encerrar', 'saida': 'true'},
        {'de': 'se_esgotou', 'para': 'resp_recontato_insistir', 'saida': 'false'},
    ]
    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


class Command(BaseCommand):
    help = (
        f'Seed do bot de vendas por WhatsApp: Agente "Validador de respostas" + fluxo único '
        f'"{NOME_FLUXO}" (switch de entrada roteando proximo_passo/validar/recontato) na engine '
        'de automação nova. Idempotente por nome, tudo nasce INATIVO. Exige checklist '
        '"venda-internet-bot" (rodar seed_checklist_venda antes). Remove os 2 fluxos separados '
        'da versão anterior deste seed, se estiverem inativos e sem execuções.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant (obrigatório).')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant

        slug = (opts.get('tenant') or '').strip()
        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant '{slug}' não encontrado.")

        checklist = Checklist.all_tenants.filter(tenant=tenant, slug=SLUG_CHECKLIST).first()
        if checklist is None:
            raise CommandError(
                f"Tenant '{tenant.slug}' não tem o checklist '{SLUG_CHECKLIST}'. Rode "
                f"'python manage.py seed_checklist_venda --tenant {tenant.slug}' antes."
            )

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Seed bot de vendas, tenant: {tenant.slug}'))

        agente, agente_criado = self._upsert_agente(tenant)
        self.stdout.write(
            f'  {"criado" if agente_criado else "atualizado"}: agente "{agente.nome}" '
            f'(id={agente.pk}, ativo={agente.ativo})')

        grafo = _grafo_bot_venda(agente.pk)
        erros = validar_fluxo(grafo)
        if erros:
            raise CommandError(f'Grafo inválido para "{NOME_FLUXO}": {"; ".join(erros)}')

        fluxo, criado = self._upsert_fluxo(tenant, NOME_FLUXO, DESCRICAO_FLUXO, grafo)
        self.stdout.write(
            f'  {"criado" if criado else "atualizado"}: fluxo "{fluxo.nome}" '
            f'(id={fluxo.pk}, ativo={fluxo.ativo})')

        self._remover_fluxos_antigos(tenant)

        self.stdout.write(self.style.WARNING(
            '  lembrete: o agente usa a integração de IA default do tenant '
            '(integracao_ia=None) — sem uma IntegracaoAPI de IA ativa no tenant, a '
            'segunda opinião falha (branch "erro" do nó ia_agente).'))
        self.stdout.write(self.style.WARNING(
            '  checagem de cliente: o ramo "validar" consulta o HubSoft quando a resposta '
            'é o CPF e transborda se a pessoa já for assinante. Exige uma IntegracaoAPI '
            'HubSoft ativa no tenant; sem ela a consulta cai na saída "erro" e a venda '
            'segue normalmente (sem a checagem).'))
        self.stdout.write(self.style.SUCCESS(
            'Seed concluído. Tudo nasce INATIVO, revisar no editor antes de ativar.'))

    def _upsert_agente(self, tenant):
        agente = Agente.all_tenants.filter(tenant=tenant, nome=NOME_AGENTE_VALIDADOR).first()
        criado = agente is None
        if agente is None:
            agente = Agente(tenant=tenant, nome=NOME_AGENTE_VALIDADOR, ativo=False)
        agente.equipe = 'fluxo'
        agente.icone = 'bi-patch-check'
        agente.memoria = ''
        agente.tools = []
        agente.integracao_ia = None
        agente.descricao = DESCRICAO_AGENTE
        agente.system_prompt = _system_prompt_validador(tenant)
        agente.save()
        return agente, criado

    def _upsert_fluxo(self, tenant, nome, descricao, grafo):
        fluxo = Fluxo.all_tenants.filter(tenant=tenant, nome=nome).first()
        criado = fluxo is None
        if fluxo is None:
            fluxo = Fluxo.all_tenants.create(
                tenant=tenant, nome=nome, descricao=descricao, grafo=grafo, ativo=False,
            )
            return fluxo, criado
        fluxo.descricao = descricao
        fluxo.grafo = grafo
        fluxo.save()  # `ativo` propositalmente intocado (nunca liga/desliga num re-run)
        return fluxo, criado

    def _remover_fluxos_antigos(self, tenant):
        """Apaga os 2 fluxos separados da versão anterior deste seed, SÓ se
        estiverem inativos e sem execuções registradas (guard de segurança:
        nunca apaga histórico nem algo que alguém possa ter ativado)."""
        for nome in NOMES_FLUXOS_ANTIGOS:
            fluxo = Fluxo.all_tenants.filter(tenant=tenant, nome=nome).first()
            if fluxo is None:
                continue
            if fluxo.ativo:
                self.stdout.write(self.style.WARNING(
                    f'  fluxo antigo "{nome}" (id={fluxo.pk}) está ATIVO — não removido. '
                    f'Desative manualmente e rerode o seed pra limpar.'))
                continue
            if fluxo.execucoes.exists():
                self.stdout.write(self.style.WARNING(
                    f'  fluxo antigo "{nome}" (id={fluxo.pk}) tem execuções registradas — '
                    f'não removido (histórico preservado).'))
                continue
            fluxo_id = fluxo.pk
            fluxo.delete()
            self.stdout.write(
                f'  removido: fluxo antigo "{nome}" (id={fluxo_id}, inativo, sem execuções)')
