"""Nó `carregar_lead`: resolve (ou opcionalmente cria) o `LeadProspecto` que os
nós `checklist_proximo_item` / `checklist_validar` / `checklist_progresso`
exigem em `contexto.lead`.

GAP que este nó fecha (ver seed do bot de vendas, `seed_fluxo_bot_venda.py`):
o gatilho `webhook` genérico só hidrata `{{var.payload}}` no `Contexto`
(`Contexto(tenant=fluxo.tenant, variaveis={'payload': payload})`, ver
`views.webhook_receber`) — nenhuma entidade de domínio entra sozinha. Sem
este nó (ou outro equivalente) logo depois do trigger, os nós de checklist
falham com "Sem lead no contexto." em todo turno que vier via HTTP de
verdade; isso não aparecia nos testes porque eles montavam o `Contexto` já
com `lead=` (atalho que não existe no caminho HTTP real).

Resolve por `lead_id` (quando vier, direto por pk — ignora telefone) ou por
`telefone` (só dígitos; casa primeiro exato, senão pelos últimos dígitos do
telefone salvo, do sufixo mais específico pro menos — tolera o telefone
chegar com ou sem código do país `55` e/ou DDD na frente; mesmo espírito de
`apps.inbox.services.buscar_lead_por_telefone`, reimplementado aqui
propositalmente desacoplado: aquele é do domínio de Inbox, este nó é
`comercial`/`automacao`, e a faixa de sufixos tentada aqui é mais ampla —
inclui o número local sem DDD — porque o payload do bot às vezes manda só
isso). Injeta o resultado em `contexto.lead` via `NodeResult.entidades`
(mecanismo genérico, ver `nodes/base.py` + `nodes/context.py`) — qualquer nó
depois deste no grafo já enxerga `contexto.lead` preenchido.
"""
import re

from .base import BaseNode, NodeResult, registrar

# Mesmo padrão de nome/origem que `apps.comercial.atendimento_ia.services.sessao`
# usa pro lead mínimo do endpoint legado que este fluxo substitui — copiado
# (não importado), propositalmente desacoplado do app legado (mesmo critério
# já usado pro prompt do Agente Validador em `seed_fluxo_bot_venda.py`).
NOME_LEAD_SEM_IDENTIFICACAO = 'Lead WhatsApp'
ORIGEM_LEAD_BOT = 'whatsapp'

# Tamanhos de sufixo tentados, do mais específico pro menos: "55"+DDD+9 dígitos
# (13) até só o número local sem DDD (8). Times de sufixo maior primeiro reduz
# colisão (um sufixo de 8 dígitos é bem menos exclusivo que um de 13).
_TAMANHOS_SUFIXO = (13, 12, 11, 10, 9, 8)

# Chaves comuns de nome que um payload de webhook pode trazer. O bot de vendas
# real (Matrix) não manda nome nesta ponta — só telefone; o nome vem depois via
# item do checklist. Isto é só um bônus tolerante pra quando outro chamador do
# mesmo nó mandar nome de cara.
_CHAVES_NOME_PAYLOAD = ('nome', 'name', 'pushName', 'nome_razaosocial')


def _so_digitos(valor):
    return re.sub(r'\D', '', str(valor or ''))


# `Contexto.resolver` distingue "chave ausente no payload" (sentinel interno,
# devolve o texto `{{...}}` LITERAL) de "chave presente com valor None"
# (devolve `None` de verdade) — ver `Contexto._passo`. Pra um campo opcional
# como `lead_id`, as duas situações significam a mesma coisa ("não veio"); sem
# este filtro, um payload real que simplesmente não manda `lead_id` faria o
# nó tentar buscar por um pk literal `"{{var.payload.lead_id}}"` (não é dígito,
# cai discretamente pro branch errado) em vez de cair pro caminho por telefone.
def _resolvido_ou_vazio(valor):
    if valor is None:
        return ''
    texto = str(valor)
    if texto.startswith('{{') and texto.endswith('}}'):
        return ''
    return texto


def _nome_do_payload(contexto):
    payload = (contexto.variaveis or {}).get('payload')
    if not isinstance(payload, dict):
        return ''
    for chave in _CHAVES_NOME_PAYLOAD:
        valor = str(payload.get(chave) or '').strip()
        if valor:
            return valor
    return ''


@registrar
class CarregarLeadNode(BaseNode):
    tipo = "carregar_lead"
    label = "Carregar lead"
    icone = "bi-person-vcard"
    categoria = "comercial"
    grupo = "Comercial"
    subgrupo = "Leads"
    saidas = ["encontrado", "nao_encontrado", "erro"]

    def campos_config(self) -> list:
        return [
            {'nome': 'telefone', 'label': 'Telefone', 'tipo': 'texto',
             'placeholder': '{{var.payload.cellphone}}',
             'ajuda': 'Aceita {{...}}. Normalizado (só dígitos) e comparado pelos últimos '
                      'dígitos do telefone salvo (tolera código do país/DDD na frente). '
                      'Ignorado quando `lead_id` resolve pra um valor.'},
            {'nome': 'lead_id', 'label': 'Lead (id)', 'tipo': 'texto',
             'placeholder': '{{var.payload.lead_id}}',
             'ajuda': 'Opcional. Quando resolver pra um valor não vazio, busca por pk direto '
                      '(ignora o telefone). Vazio cai pro telefone.'},
            {'nome': 'criar_se_nao_existir', 'label': 'Criar quando não existir', 'tipo': 'booleano',
             'ajuda': 'Padrão desligado. Só vale pro caminho por telefone (criar a partir de um '
                      'lead_id que não bateu não faria sentido: sem telefone não há o que ancorar '
                      'um lead novo). Cria um lead mínimo: nome do payload se houver (senão '
                      '"Lead WhatsApp <telefone>"), telefone, origem "whatsapp".'},
        ]

    def validar_config(self, config) -> list:
        tem_telefone = bool(str(config.get('telefone') or '').strip())
        tem_lead_id = bool(str(config.get('lead_id') or '').strip())
        if not tem_telefone and not tem_lead_id:
            return ['Informe `telefone` ou `lead_id`.']
        return []

    def executar(self, config, entrada, contexto) -> NodeResult:
        from apps.comercial.leads.models import LeadProspecto

        lead_id = _resolvido_ou_vazio(contexto.resolver(config.get('lead_id', ''))).strip()
        if lead_id:
            lead = None
            if lead_id.isdigit():
                lead = LeadProspecto.all_tenants.filter(tenant=contexto.tenant, pk=lead_id).first()
            if lead is not None:
                return self._achado(lead, criado=False)
            # lead_id veio mas não achou: o grafo pediu um lead específico, não cai
            # pro telefone (evita ancorar a conversa num lead errado em silêncio).
            return self._nao_achado()

        telefone = _so_digitos(_resolvido_ou_vazio(contexto.resolver(config.get('telefone', ''))))
        if not telefone:
            return NodeResult(status='erro', branch='erro',
                               erro='`telefone`/`lead_id` vazios depois de resolver o template.')

        lead = self._buscar_por_telefone(contexto.tenant, telefone)
        if lead is not None:
            return self._achado(lead, criado=False)

        if not bool(config.get('criar_se_nao_existir')):
            return self._nao_achado()

        nome = _nome_do_payload(contexto) or f'{NOME_LEAD_SEM_IDENTIFICACAO} {telefone}'.strip()
        try:
            lead = LeadProspecto.all_tenants.create(
                tenant=contexto.tenant, nome_razaosocial=nome, telefone=telefone,
                origem=ORIGEM_LEAD_BOT, status_api=LeadProspecto.status_api_inicial(contexto.tenant),
            )
        except Exception as exc:  # noqa: BLE001 — falha de criação vira branch erro, não exceção crua
            return NodeResult(status='erro', branch='erro', erro=f'falha ao criar lead: {exc}')
        return self._achado(lead, criado=True)

    @staticmethod
    def _achado(lead, *, criado):
        return NodeResult(
            output={'lead_id': lead.pk, 'nome': lead.nome_razaosocial, 'telefone': lead.telefone,
                     'criado': criado},
            entidades={'lead': lead},
            branch='encontrado',
        )

    @staticmethod
    def _nao_achado():
        return NodeResult(output={'lead_id': None, 'nome': '', 'telefone': '', 'criado': False},
                           branch='nao_encontrado')

    @staticmethod
    def _buscar_por_telefone(tenant, telefone):
        from apps.comercial.leads.models import LeadProspecto
        base = LeadProspecto.all_tenants.filter(tenant=tenant)
        lead = base.filter(telefone=telefone).first()
        if lead is not None:
            return lead
        for tamanho in _TAMANHOS_SUFIXO:
            if len(telefone) < tamanho:
                continue
            lead = base.filter(telefone__endswith=telefone[-tamanho:]).first()
            if lead is not None:
                return lead
        return None
