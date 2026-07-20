"""
Provisionamento do modulo People.

Um so hook por enquanto: quando o tenant PASSA A TER o modulo People, o
pipeline de recrutamento nasce com as sete etapas padrao.

Por que na ativacao do modulo e nao na criacao do tenant: tenant sem People
contratado nao deveria carregar tabela de recrutamento nenhuma. E por que nao
sob demanda, na primeira leitura: escrita escondida dentro de caminho de leitura
e o tipo de coisa que aparece como bug estranho seis meses depois, quando duas
requisicoes simultaneas caem no mesmo `if nao existe: cria`.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='sistema.Tenant')
def _lembrar_estado_anterior_do_modulo(sender, instance, **kwargs):
    """
    Guarda se o People JA estava ligado antes deste save.

    Sem isso nao da pra distinguir "acabou de ativar" de "salvou o tenant por
    qualquer outro motivo com o modulo ja ligado", e o seed rodaria de novo a
    cada edicao. O `semear_padrao` e idempotente, entao nao duplicaria, mas
    faria uma query a toa em todo save de tenant.
    """
    if not instance.pk:
        instance._people_estava_ligado = False
        return

    instance._people_estava_ligado = bool(
        sender.objects.filter(pk=instance.pk)
        .values_list('modulo_people', flat=True)
        .first()
    )


@receiver(post_save, sender='sistema.Tenant')
def provisionar_pipeline_de_recrutamento(sender, instance, created, **kwargs):
    """
    Semeia as sete etapas padrao quando o modulo e ativado.

    Roda so na transicao desligado para ligado (ou na criacao ja com o modulo
    ligado). Tenant que apagou as etapas de proposito nao as recebe de volta no
    proximo save, que seria desfazer uma decisao do cliente.
    """
    if not instance.modulo_people:
        return
    if not created and getattr(instance, '_people_estava_ligado', False):
        return

    try:
        from apps.people.models import EtapaPipeline

        criadas = EtapaPipeline.semear_padrao(instance)
        if criadas:
            logger.info(
                'Tenant %s: pipeline de recrutamento seedado com %d etapas',
                instance.slug, len(criadas),
            )
    except Exception as exc:
        # Nao derruba o save do tenant por causa do seed. Um pipeline vazio e
        # recuperavel (a tela de etapas resolve); um tenant que nao salva, nao.
        logger.exception(
            'Erro seedando pipeline de recrutamento do tenant %s: %s',
            instance.slug, exc,
        )
