"""
Requisicao de vaga com aprovacao (gap 16).

O PROBLEMA QUE ISTO RESOLVE: hoje quem tem `people.gerir_vagas` abre vaga
direto, sem registro de quem pediu nem por que. Numa rede de franquia (e num
grupo de provedores) e justamente o controle que o dono quer, porque cada vaga
aberta e custo recorrente aprovado por alguem.

O DESENHO, em uma linha: o gestor da loja SOLICITA com justificativa, o RH
APROVA ou REJEITA com motivo.

TRES DECISOES QUE MOLDAM ESTE MODULO:

1. APROVAR LEVA PRA RASCUNHO, e nao pra publicada. A requisicao do gestor chega
   crua ("preciso de 1 atendente na loja Centro"); o RH aprova o PEDIDO e depois
   arruma o ANUNCIO, que e o texto que o candidato le. Aprovar e publicar de uma
   vez tiraria a ultima conferencia de quem responde pela vaga.

2. REJEITADA VOLTA PRA FILA. O gestor corrige o que o RH apontou e reenvia, na
   mesma vaga. Sem essa aresta, corrigir exigiria abrir outra requisicao e o
   motivo da recusa se perderia, que e justamente o registro que da valor ao
   fluxo.

3. NINGUEM APROVA A PROPRIA REQUISICAO. Quem so tem `people.solicitar_vaga` nao
   decide; a decisao exige `people.gerir_vagas`. Sem essa separacao o fluxo vira
   burocracia decorativa, com o mesmo usuario nos dois lados.

O que NAO esta aqui: `justificativa` e `colaborador_substituido` ja existiam no
model desde o inicio, com CheckConstraint exigindo o substituido quando a
justificativa e substituicao. A requisicao so passou a EXIGIR o preenchimento; o
schema ja estava pronto pra isso.
"""
import logging

from django.db import transaction
from django.utils import timezone

from apps.people import estados_recrutamento as estados_rs
from apps.people.excecoes import PeopleError
from apps.people.models_recrutamento import JUSTIFICATIVA_SUBSTITUICAO
from apps.sistema.utils import registrar_acao

logger = logging.getLogger(__name__)


class RequisicaoInvalida(PeopleError):
    """Requisicao sem o que a governanca exige, ou decisao fora de ordem."""


def _exigir_justificativa(vaga):
    """
    A justificativa e o ponto da requisicao, entao e barrada aqui e nao so no
    form: o servico e chamado tambem por import e por tela futura, e regra que
    so vive no formulario e regra que vaza na primeira porta nova.
    """
    if not vaga.justificativa:
        raise RequisicaoInvalida(
            'Toda requisição precisa de justificativa: aumento de quadro ou '
            'substituição.')

    # A CheckConstraint do banco tambem garante isso. A checagem aqui existe pra
    # devolver frase legivel em vez de IntegrityError na cara do usuario.
    if (vaga.justificativa == JUSTIFICATIVA_SUBSTITUICAO
            and not vaga.colaborador_substituido_id):
        raise RequisicaoInvalida(
            'Substituição precisa apontar quem saiu. É o que liga a vaga ao '
            'Quadro da unidade.')


def solicitar(vaga, *, usuario=None, request=None):
    """
    Poe a vaga na fila de aprovacao.

    Serve pros dois caminhos: requisicao nova (criada ja em aguardando) e
    reenvio depois de rejeitada. A maquina de estados e que decide se a
    transicao vale, entao reenviar de um status que nao seja `rejeitada` e
    recusado sem este servico precisar saber a tabela toda.
    """
    _exigir_justificativa(vaga)

    with transaction.atomic():
        if vaga.status != estados_rs.STATUS_VAGA_AGUARDANDO:
            vaga.mudar_status(estados_rs.STATUS_VAGA_AGUARDANDO)

        # Decisao anterior sai do caminho: uma requisicao reenviada esta
        # esperando decisao NOVA, e deixar o carimbo velho faria a tela dizer
        # "rejeitada por Fulano" numa vaga que esta na fila.
        if vaga.aprovada_por_id or vaga.decidida_em:
            vaga.aprovada_por = None
            vaga.decidida_em = None
            vaga.save(update_fields=['aprovada_por', 'decidida_em',
                                     'atualizado_em'])

    registrar_acao('people', 'solicitar', 'vaga', vaga.pk,
                   f'Vaga "{vaga.nome_exibido}" solicitada '
                   f'({vaga.get_justificativa_display()}).',
                   request=request)
    return vaga


def aprovar(vaga, *, usuario, request=None):
    """
    Aprova a requisicao. A vaga vai pra RASCUNHO, e nao pro ar.

    Ver decisao 1 no topo: o RH aprova o pedido e depois revisa o anuncio.
    """
    if vaga.status != estados_rs.STATUS_VAGA_AGUARDANDO:
        raise RequisicaoInvalida(
            f'Só dá para aprovar requisição que está aguardando. Esta está em '
            f'"{estados_rs.rotulo_status_vaga(vaga.status)}".')

    with transaction.atomic():
        vaga.mudar_status(estados_rs.STATUS_VAGA_RASCUNHO)
        vaga.aprovada_por = usuario
        vaga.decidida_em = timezone.now()
        # O motivo da rejeicao anterior sai: mantê-lo faria a ficha de uma vaga
        # aprovada exibir o texto de quando ela foi recusada.
        vaga.motivo_rejeicao = ''
        vaga.save(update_fields=['aprovada_por', 'decidida_em',
                                 'motivo_rejeicao', 'atualizado_em'])

    registrar_acao('people', 'aprovar', 'vaga', vaga.pk,
                   f'Requisição da vaga "{vaga.nome_exibido}" aprovada. '
                   f'Vaga em rascunho, aguardando publicação.',
                   request=request)
    return vaga


def rejeitar(vaga, *, usuario, motivo, request=None):
    """
    Rejeita a requisicao, com motivo OBRIGATORIO.

    O motivo nao e formalidade: e o que o gestor le pra corrigir e reenviar.
    Rejeicao sem motivo devolve a pessoa pro mesmo erro, e ai o fluxo so
    adicionou atrito.
    """
    if vaga.status != estados_rs.STATUS_VAGA_AGUARDANDO:
        raise RequisicaoInvalida(
            f'Só dá para rejeitar requisição que está aguardando. Esta está em '
            f'"{estados_rs.rotulo_status_vaga(vaga.status)}".')

    motivo = (motivo or '').strip()
    if not motivo:
        raise RequisicaoInvalida(
            'Rejeição exige motivo: é o que o gestor lê para corrigir e '
            'reenviar.')

    with transaction.atomic():
        vaga.mudar_status(estados_rs.STATUS_VAGA_REJEITADA)
        vaga.aprovada_por = usuario
        vaga.decidida_em = timezone.now()
        vaga.motivo_rejeicao = motivo
        vaga.save(update_fields=['aprovada_por', 'decidida_em',
                                 'motivo_rejeicao', 'atualizado_em'])

    registrar_acao('people', 'rejeitar', 'vaga', vaga.pk,
                   f'Requisição da vaga "{vaga.nome_exibido}" rejeitada: '
                   f'{motivo[:120]}',
                   request=request)
    return vaga
