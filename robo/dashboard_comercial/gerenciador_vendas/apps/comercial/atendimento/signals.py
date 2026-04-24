"""
Signals do modulo de atendimento.

Objetivo principal: prevenir zumbis (AtendimentoFluxo com nodo_atual_id
apontando pra nodo deletado). Quando isso acontece, engine nao sabe
rotear proxima mensagem do lead.
"""
from django.db.models import ProtectedError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import NodoFluxoAtendimento, AtendimentoFluxo

STATUS_ATIVOS = ('iniciado', 'em_andamento', 'pausado', 'aguardando_validacao')


@receiver(pre_delete, sender=NodoFluxoAtendimento)
def bloquear_delete_de_nodo_com_atendimento_ativo(sender, instance, **kwargs):
    """Impede delete de NodoFluxoAtendimento que tenha atendimento ativo
    apontando pra ele via nodo_atual.

    Sem isso, deletar nodo no editor (ou em refactor de fluxo) cria
    zumbi: o atendimento perde a referencia de onde esta, nao consegue
    processar proxima mensagem do lead.

    Para forcar o delete sabendo do efeito, migrar os atendimentos
    primeiro:

        AtendimentoFluxo.objects.filter(nodo_atual=nodo).update(status='abandonado', nodo_atual=None)

    Atendimentos ja finalizados ('completado', 'abandonado', etc) nao
    bloqueiam — o nodo_atual deles ja nao sera percorrido.
    """
    ativos = AtendimentoFluxo.all_tenants.filter(
        nodo_atual=instance,
        status__in=STATUS_ATIVOS,
    )
    count = ativos.count()
    if count > 0:
        ids_preview = list(ativos.values_list('id', flat=True)[:5])
        raise ProtectedError(
            f"Nodo id={instance.pk} ({instance.tipo}/{instance.subtipo or '-'}) "
            f"nao pode ser deletado: {count} atendimento(s) ativo(s) "
            f"apontando pra ele (exemplos: {ids_preview}). "
            f"Encerre ou migre esses atendimentos antes.",
            ativos,
        )
