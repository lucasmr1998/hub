"""Seed do BOT DE VENDAS por WhatsApp na engine de automação nova (React Flow).

Decisão de arquitetura (dono do produto): o bot externo (Matrix) conduz a venda
por WhatsApp chamando nossa API a cada turno, mas a LÓGICA da conversa não pode
ser serviço Python escondido — tem que ser um GRAFO visível e editável no
editor, montado com peças que já existem (`checklist_proximo_item`,
`checklist_validar`, `ia_agente`, `extrair_json`, `webhook`/`responder_webhook`,
`if`). A IA usa a estrutura de `Agente` (prompt configurável na tela), nunca
prompt cravado em código.

Cria:
1. Agente "Validador de respostas" — segunda opinião semântica quando a
   cascata determinística do checklist reprova uma resposta. Prompt copiado
   (não importado) de `apps.comercial.atendimento_ia.services.validacao_ia`
   (`PROMPT_SISTEMA`), propositalmente DESACOPLADO do app legado: o app novo
   não deve depender do `atendimento_ia` (que é a implementação Python que
   este fluxo substitui). Se o prompt original mudar, reaplicar aqui e
   rerodar o seed.
2. Fluxo "[Bot] Venda de internet: próximo passo" — responde "qual a próxima
   pergunta?" pro Matrix.
3. Fluxo "[Bot] Venda de internet: validar resposta" — valida a resposta do
   cliente: o nó determinístico (`checklist_validar`) tenta primeiro; só
   quando reprova é que a IA entra como segunda opinião (nó `ia_agente` no
   PRÓPRIO GRAFO); o grafo decide o que fazer com a intenção detectada
   (aceitar, repetir a pergunta ou transbordar pra humano).

Os dois fluxos exigem o `Checklist` de slug `venda-internet-bot` do tenant
(ver `seed_checklist_venda`) — o comando falha com erro claro se não achar.

Idempotente por nome (fluxo) / nome (agente): rerodar ATUALIZA o grafo/prompt
em vez de duplicar, e PRESERVA o `ativo` de quem já existe (nunca liga nem
desliga nada sozinho, mesmo padrão de `seed_fluxos_recuperacao_analise`).
Tudo nasce INATIVO (`ativo=False`) — revisar no editor antes de ligar.

GAP CONHECIDO (documentar antes de ativar em produção, não resolvido aqui de
propósito — foge do escopo deste seed): `checklist_proximo_item` e
`checklist_validar` precisam de `contexto.lead` (um Lead de verdade) já
carregado. O gatilho `webhook` genérico usado aqui NÃO hidrata isso sozinho —
`Contexto(tenant=..., variaveis={'payload': payload})` na view
`webhook_receber` não recebe `lead=`. Antes de ligar este fluxo pra valer,
falta uma peça que carregue o Lead de `payload.lead_id` pro `contexto.lead`
(um nó novo, ou uma hidratação na própria view). Os testes deste seed chamam
`executar_fluxo` direto com o `Contexto` já montado (`lead=...`), que é como
o editor/chat de teste também operam — não cobrem o caminho HTTP real.

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
NOME_FLUXO_PROXIMO = '[Bot] Venda de internet: próximo passo'
NOME_FLUXO_VALIDAR = '[Bot] Venda de internet: validar resposta'

DESCRICAO_AGENTE = (
    'Segunda opinião semântica pras respostas do checklist de venda que a '
    'cascata determinística (`checklist_validar`) reprovou. Só entra quando o '
    'grafo do fluxo "validar resposta" chama, nunca sozinho. Contrato de saída '
    'em JSON (valido, dados_extraidos, mensagem_bot, motivo_invalido, '
    'confianca, intencao_detectada). Nasce INATIVO.'
)

DESCRICAO_FLUXO_PROXIMO = (
    'Responde "qual a próxima pergunta do roteiro de venda?" pro bot externo '
    '(Matrix), a cada turno da conversa. Só o nó `checklist_proximo_item` '
    'decide (sem IA nesta ponta) — o checklist usado é o de slug '
    f'"{SLUG_CHECKLIST}" do tenant. Corpo da resposta em JSON, campos e tipos '
    'seguindo `apps.comercial.atendimento_ia.services.contrato.payload_proximo_passo`. '
    'Nasce INATIVO.'
)

DESCRICAO_FLUXO_VALIDAR = (
    'Valida a resposta que o cliente mandou pro bot externo (Matrix). O '
    'determinístico (`checklist_validar`) tenta primeiro; só quando reprova '
    '("invalida") é que entra o Agente IA "Validador de respostas" como '
    'segunda opinião, DENTRO do próprio grafo — nunca como serviço Python '
    'escondido. O grafo decide o que fazer com a intenção detectada pela IA '
    '(aceitar / repetir a pergunta / transbordar pra humano). Corpo da '
    'resposta em JSON, campos e tipos seguindo '
    '`apps.comercial.atendimento_ia.services.contrato.payload_validar` '
    '(atenção: `needsReception` é STRING "true"/"false", não boolean). '
    'Nasce INATIVO.'
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
# (tipo preservado: bool/número/lista) — o `responder_webhook` (ver node,
# patch desta mesma tarefa) resolve o objeto inteiro e serializa com
# `json.dumps`, escapando de verdade quebra de linha/aspas do texto da
# pergunta. Valores estáticos (sem `{{...}}`) só passam direto.

def _corpo(template):
    return json.dumps(template, ensure_ascii=False)


# payload_proximo_passo (contrato: apps.comercial.atendimento_ia.services.contrato)
CORPO_PROXIMO_PERGUNTA = _corpo({
    'lead_id': '{{lead.id}}',
    # Simplificação: este grafo não replica o rastreio de sessão do endpoint
    # legado (/ia/proximo-passo); sempre "em_andamento". Ver descrição do fluxo.
    'status_lead': 'em_andamento',
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

CORPO_PROXIMO_ENCERRAR = _corpo({
    'lead_id': '{{lead.id}}',
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
_MSG_ERRO_ESTRUTURAL = (
    'Não consegui continuar o atendimento automático agora. Vou te transferir '
    'para um atendente.'
)

CORPO_VALIDAR_OK = _corpo({
    'resposta_correta': True,
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '',
    'needsReception': 'false',
    'isAClient': False,
    'cancelado': False,
    'message': '',
})

CORPO_VALIDAR_ERRO = _corpo({
    'resposta_correta': False,
    'resposta_sem_erro_api': False,
    'retorno_erro_api': _MSG_ERRO_ESTRUTURAL,
    'needsReception': 'true',
    'isAClient': False,
    'cancelado': False,
    'message': '',
})

CORPO_VALIDAR_OK_IA = _corpo({
    'resposta_correta': True,
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '',
    'needsReception': 'false',
    'isAClient': False,
    'cancelado': False,
    'message': '{{nodes.json.mensagem_bot}}',
})

CORPO_VALIDAR_TRANSBORDO = _corpo({
    'resposta_correta': False,
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '{{nodes.json.mensagem_bot}}',
    'needsReception': 'true',
    'isAClient': False,
    'cancelado': False,
    'message': '',
})

CORPO_VALIDAR_REPERGUNTA = _corpo({
    'resposta_correta': False,
    'resposta_sem_erro_api': True,
    'retorno_erro_api': '{{nodes.json.mensagem_bot}}',
    'needsReception': 'false',
    'isAClient': False,
    'cancelado': False,
    'message': '',
})

# Mensagem que o nó `ia_agente` manda pro LLM: pergunta original + resposta do
# cliente (o `checklist_validar` expõe `pergunta` no output pra isso, ver node).
MENSAGEM_AGENTE_VALIDADOR = (
    'Pergunta feita ao cliente: {{nodes.validar.pergunta}}\n'
    'Resposta do cliente: {{var.payload.answer}}'
)


def _grafo_proximo_passo():
    nodes = {
        'trigger': {
            'tipo': 'webhook',
            'config': {'responder': 'no_resposta'},
            'pos': {'x': 0, 'y': 0},
            'label': 'Webhook: turno do bot (Matrix)',
        },
        'proximo': {
            'tipo': 'checklist_proximo_item',
            'config': {'checklist': SLUG_CHECKLIST, 'entidade': 'lead'},
            'pos': {'x': 280, 'y': 0},
            'label': 'Checklist: próxima pergunta',
        },
        'resp_fim': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_PROXIMO_ENCERRAR},
            'pos': {'x': 560, 'y': -140},
            'label': 'Responder: checklist completo (encerrar)',
        },
        'resp_pergunta': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_PROXIMO_PERGUNTA},
            'pos': {'x': 560, 'y': 140},
            'label': 'Responder: próxima pergunta',
        },
    }
    conexoes = [
        {'de': 'trigger', 'para': 'proximo', 'saida': 'default'},
        {'de': 'proximo', 'para': 'resp_fim', 'saida': 'completo'},
        {'de': 'proximo', 'para': 'resp_pergunta', 'saida': 'tem_item'},
    ]
    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


def _grafo_validar(agente_id):
    nodes = {
        'trigger': {
            'tipo': 'webhook',
            'config': {'responder': 'no_resposta'},
            'pos': {'x': 0, 'y': 0},
            'label': 'Webhook: turno do bot (Matrix)',
        },
        'validar': {
            'tipo': 'checklist_validar',
            'config': {
                'checklist': SLUG_CHECKLIST,
                'item_id': '{{var.payload.question_id}}',
                'resposta': '{{var.payload.answer}}',
                'entidade': 'lead',
            },
            'pos': {'x': 280, 'y': 0},
            'label': 'Checklist: validar resposta (determinístico)',
        },
        'resp_ok': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_OK},
            'pos': {'x': 560, 'y': -260},
            'label': 'Responder: resposta válida',
        },
        'resp_erro': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_ERRO},
            'pos': {'x': 560, 'y': 260},
            'label': 'Responder: erro estrutural (transbordo)',
        },
        'agente': {
            'tipo': 'ia_agente',
            'config': {'agente_id': str(agente_id), 'mensagem': MENSAGEM_AGENTE_VALIDADOR},
            'pos': {'x': 560, 'y': 0},
            'label': 'Agente IA: segunda opinião (Validador de respostas)',
        },
        'json': {
            'tipo': 'extrair_json',
            'config': {'origem': '{{nodes.agente.resposta}}'},
            'pos': {'x': 840, 'y': 0},
            'label': 'Extrair JSON da validação',
        },
        'se_valido': {
            'tipo': 'if',
            'config': {'esquerda': '{{nodes.json.valido}}', 'operador': 'igual', 'direita': 'True'},
            'pos': {'x': 1120, 'y': 0},
            'label': 'IA validou?',
        },
        'resp_ok_ia': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_OK_IA},
            'pos': {'x': 1400, 'y': -140},
            'label': 'Responder: aceita pela IA',
        },
        'se_desistiu': {
            'tipo': 'if',
            'config': {
                'esquerda': '{{nodes.json.intencao_detectada}}',
                'operador': 'igual', 'direita': 'desistir',
            },
            'pos': {'x': 1400, 'y': 140},
            'label': 'Cliente quer desistir?',
        },
        'resp_transbordo': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_TRANSBORDO},
            'pos': {'x': 1680, 'y': 0},
            'label': 'Responder: transbordo (desistência)',
        },
        'resp_repergunta': {
            'tipo': 'responder_webhook',
            'config': {'status': 200, 'corpo': CORPO_VALIDAR_REPERGUNTA},
            'pos': {'x': 1680, 'y': 260},
            'label': 'Responder: repetir a pergunta',
        },
    }
    conexoes = [
        {'de': 'trigger', 'para': 'validar', 'saida': 'default'},
        {'de': 'validar', 'para': 'resp_ok', 'saida': 'valida'},
        {'de': 'validar', 'para': 'resp_erro', 'saida': 'erro'},
        {'de': 'validar', 'para': 'agente', 'saida': 'invalida'},
        {'de': 'agente', 'para': 'json', 'saida': 'sucesso'},
        {'de': 'json', 'para': 'se_valido', 'saida': 'sucesso'},
        {'de': 'se_valido', 'para': 'resp_ok_ia', 'saida': 'true'},
        {'de': 'se_valido', 'para': 'se_desistiu', 'saida': 'false'},
        {'de': 'se_desistiu', 'para': 'resp_transbordo', 'saida': 'true'},
        {'de': 'se_desistiu', 'para': 'resp_repergunta', 'saida': 'false'},
    ]
    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


class Command(BaseCommand):
    help = (
        'Seed do bot de vendas por WhatsApp (Agente "Validador de respostas" + fluxos '
        '"próximo passo"/"validar resposta") na engine de automação nova. Idempotente '
        'por nome, tudo nasce INATIVO. Exige checklist "venda-internet-bot" (rodar '
        'seed_checklist_venda antes).'
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

        grafos = {
            NOME_FLUXO_PROXIMO: (_grafo_proximo_passo(), DESCRICAO_FLUXO_PROXIMO),
            NOME_FLUXO_VALIDAR: (_grafo_validar(agente.pk), DESCRICAO_FLUXO_VALIDAR),
        }

        # Falha cedo: nenhum fluxo é escrito se algum grafo for estruturalmente inválido.
        for nome, (grafo, _descricao) in grafos.items():
            erros = validar_fluxo(grafo)
            if erros:
                raise CommandError(f'Grafo inválido para "{nome}": {"; ".join(erros)}')

        for nome, (grafo, descricao) in grafos.items():
            fluxo, criado = self._upsert_fluxo(tenant, nome, descricao, grafo)
            self.stdout.write(
                f'  {"criado" if criado else "atualizado"}: fluxo "{fluxo.nome}" '
                f'(id={fluxo.pk}, ativo={fluxo.ativo})')

        self.stdout.write(self.style.WARNING(
            '  lembrete: o agente usa a integração de IA default do tenant '
            '(integracao_ia=None) — sem uma IntegracaoAPI de IA ativa no tenant, a '
            'segunda opinião falha (branch "erro" do nó ia_agente).'))
        self.stdout.write(self.style.WARNING(
            '  gap conhecido: checklist_proximo_item/checklist_validar exigem '
            'contexto.lead já carregado; o gatilho webhook genérico não hidrata isso '
            'sozinho (ver docstring do módulo) — resolver antes de ligar em produção.'))
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
