import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.comercial.leads.models import LeadProspecto

logger = logging.getLogger(__name__)


def _obter_integracao_hubsoft():
    from apps.integracoes.models import IntegracaoAPI
    return IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()


@receiver(post_save, sender=LeadProspecto)
def enviar_lead_pendente_para_hubsoft(sender, instance, **kwargs):
    """
    Sempre que um LeadProspecto ficar com status_api='pendente' e ainda
    não possuir id_hubsoft, envia-o automaticamente para o Hubsoft como
    prospecto via API.
    """
    if instance.status_api != 'pendente':
        return

    if instance.id_hubsoft:
        return

    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

    integracao = _obter_integracao_hubsoft()
    if not integracao:
        logger.warning(
            "Nenhuma integração Hubsoft ativa encontrada. "
            "Lead %s (pk=%s) não foi enviado.",
            instance.nome_razaosocial, instance.pk,
        )
        return

    try:
        service = HubsoftService(integracao)
        resposta = service.cadastrar_prospecto(instance)

        id_prospecto = (
            resposta.get('prospecto', {}).get('id_prospecto')
        )

        campos_update = {'status_api': 'processado'}
        if id_prospecto:
            campos_update['id_hubsoft'] = str(id_prospecto)

        LeadProspecto.objects.filter(pk=instance.pk).update(**campos_update)

        logger.info(
            "Lead '%s' (pk=%s) cadastrado no Hubsoft com id_prospecto=%s",
            instance.nome_razaosocial, instance.pk, id_prospecto,
        )

        _sincronizar_cliente_hubsoft(instance, service)

    except HubsoftServiceError as exc:
        LeadProspecto.objects.filter(pk=instance.pk).update(status_api='erro')
        logger.error(
            "Erro ao enviar lead '%s' (pk=%s) para Hubsoft: %s",
            instance.nome_razaosocial, instance.pk, exc,
        )
    except Exception as exc:
        LeadProspecto.objects.filter(pk=instance.pk).update(status_api='erro')
        logger.exception(
            "Erro inesperado ao enviar lead '%s' (pk=%s) para Hubsoft: %s",
            instance.nome_razaosocial, instance.pk, exc,
        )


def _sincronizar_cliente_hubsoft(lead, service=None):
    """
    Consulta e sincroniza os dados do cliente no Hubsoft a partir
    do CPF/CNPJ do lead. Pode ser chamada standalone ou após cadastro.
    """
    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

    if service is None:
        integracao = _obter_integracao_hubsoft()
        if not integracao:
            logger.warning("Nenhuma integração Hubsoft ativa para sincronizar cliente do lead pk=%s.", lead.pk)
            return None
        service = HubsoftService(integracao)

    try:
        cliente = service.sincronizar_cliente(lead)
        if cliente:
            logger.info(
                "Cliente Hubsoft sincronizado para lead pk=%s: %s (id_cliente=%s)",
                lead.pk, cliente.nome_razaosocial, cliente.id_cliente,
            )
        return cliente
    except HubsoftServiceError as exc:
        logger.error(
            "Erro ao sincronizar cliente Hubsoft para lead pk=%s: %s",
            lead.pk, exc,
        )
    except Exception as exc:
        logger.exception(
            "Erro inesperado ao sincronizar cliente Hubsoft para lead pk=%s: %s",
            lead.pk, exc,
        )
    return None


