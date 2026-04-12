import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.comercial.leads.models import LeadProspecto

logger = logging.getLogger(__name__)


def _obter_integracao_hubsoft():
    from apps.integracoes.models import IntegracaoAPI
    return IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()


@receiver(post_save, sender=LeadProspecto)
def enviar_lead_para_integracao(sender, instance, **kwargs):
    """
    Envia lead para integracao configurada nas configuracoes da empresa.
    So envia se a config estiver ativa e a integracao selecionada.
    """
    if instance.id_hubsoft:
        return

    # Verificar config da empresa
    from apps.sistema.models import ConfiguracaoEmpresa
    config = ConfiguracaoEmpresa.objects.filter(ativo=True).first()
    if not config or not config.enviar_leads_integracao or not config.integracao_leads:
        return

    integracao = config.integracao_leads
    if not integracao.ativa:
        return

    # Somente HubSoft por enquanto
    if integracao.tipo != 'hubsoft':
        logger.debug("Integracao %s nao suportada para envio de leads.", integracao.tipo)
        return

    # Checar modo de sync: só executa se automatico
    if not integracao.sync_habilitado('enviar_lead'):
        logger.debug("Envio de lead desativado/manual para integracao %s.", integracao.nome)
        return

    if instance.status_api != 'pendente':
        return

    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

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
            logger.debug("Sem integração Hubsoft ativa. Lead pk=%s ignorado.", lead.pk)
            return None
        if not integracao.sync_permitido('sincronizar_cliente'):
            logger.debug("Sincronizacao de cliente desativada para integracao %s.", integracao.nome)
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


