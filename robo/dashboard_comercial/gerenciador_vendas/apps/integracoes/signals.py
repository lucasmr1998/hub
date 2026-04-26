import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.comercial.leads.models import LeadProspecto

logger = logging.getLogger(__name__)


def _obter_integracao_hubsoft():
    from apps.integracoes.models import IntegracaoAPI
    return IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()


def _obter_integracao_sgp(tenant):
    from apps.integracoes.models import IntegracaoAPI
    return IntegracaoAPI.objects.filter(tipo='sgp', ativa=True, tenant=tenant).first()


@receiver(post_save, sender=LeadProspecto)
def enviar_lead_para_integracao(sender, instance, **kwargs):
    """
    Envia lead pra integracao configurada nas configuracoes da empresa.
    Suporta HubSoft e SGP. So envia se a config estiver ativa e modo de
    sync de `enviar_lead` for automatico.
    """
    if instance.id_hubsoft:
        return

    from apps.sistema.models import ConfiguracaoEmpresa
    config = ConfiguracaoEmpresa.objects.filter(
        tenant=instance.tenant, ativo=True,
    ).first()
    if not config or not config.enviar_leads_integracao or not config.integracao_leads:
        return

    integracao = config.integracao_leads
    if not integracao.ativa:
        return
    if not integracao.sync_habilitado('enviar_lead'):
        logger.debug('Envio de lead desativado/manual para integracao %s.', integracao.nome)
        return
    if instance.status_api != 'pendente':
        return

    if integracao.tipo == 'hubsoft':
        _enviar_lead_hubsoft(instance, integracao)
    elif integracao.tipo == 'sgp':
        _enviar_lead_sgp(instance, integracao)
    else:
        logger.debug('Integracao %s nao suportada para envio de leads.', integracao.tipo)


def _enviar_lead_hubsoft(instance, integracao):
    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
    try:
        service = HubsoftService(integracao)
        resposta = service.cadastrar_prospecto(instance)
        id_prospecto = resposta.get('prospecto', {}).get('id_prospecto')

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


def _enviar_lead_sgp(instance, integracao):
    from apps.integracoes.services.sgp import SGPService, SGPServiceError
    try:
        service = SGPService(integracao)
        resposta = service.cadastrar_prospecto_para_lead(instance)
        new_cliente_id = resposta.get('new_cliente_id')

        campos_update = {'status_api': 'processado'}
        if new_cliente_id:
            # id_hubsoft virou de fato um id_externo_erp generico hoje (single-ERP-per-tenant).
            campos_update['id_hubsoft'] = str(new_cliente_id)
        LeadProspecto.objects.filter(pk=instance.pk).update(**campos_update)

        logger.info(
            "Lead '%s' (pk=%s) cadastrado no SGP: precadastro_id=%s new_cliente_id=%s",
            instance.nome_razaosocial, instance.pk,
            resposta.get('precadastro_id'), new_cliente_id,
        )

        # Sincroniza cliente local imediatamente, ja que temos o id.
        if integracao.sync_permitido('sincronizar_cliente'):
            _sincronizar_cliente_sgp(instance, service, precadastro_id=resposta.get('precadastro_id'))
    except SGPServiceError as exc:
        LeadProspecto.objects.filter(pk=instance.pk).update(status_api='erro')
        logger.error(
            "Erro ao enviar lead '%s' (pk=%s) para SGP: %s",
            instance.nome_razaosocial, instance.pk, exc,
        )
    except Exception as exc:
        LeadProspecto.objects.filter(pk=instance.pk).update(status_api='erro')
        logger.exception(
            "Erro inesperado ao enviar lead '%s' (pk=%s) para SGP: %s",
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
        logger.error("Erro ao sincronizar cliente Hubsoft para lead pk=%s: %s", lead.pk, exc)
    except Exception as exc:
        logger.exception("Erro inesperado ao sincronizar cliente Hubsoft para lead pk=%s: %s", lead.pk, exc)
    return None


def _sincronizar_cliente_sgp(lead, service=None, *, precadastro_id=None):
    """Mesmo papel do helper hubsoft, pra SGP. Persiste precadastro_id se informado."""
    from apps.integracoes.services.sgp import SGPService, SGPServiceError

    if service is None:
        integracao = _obter_integracao_sgp(lead.tenant)
        if not integracao:
            logger.debug('Sem integracao SGP ativa pro tenant. Lead pk=%s ignorado.', lead.pk)
            return None
        if not integracao.sync_permitido('sincronizar_cliente'):
            logger.debug('Sincronizacao de cliente desativada para integracao %s.', integracao.nome)
            return None
        service = SGPService(integracao)

    try:
        cliente = service.sincronizar_cliente(lead)
        if cliente and precadastro_id and cliente.precadastro_id != precadastro_id:
            cliente.precadastro_id = precadastro_id
            cliente.save(update_fields=['precadastro_id'])
        if cliente:
            logger.info(
                'Cliente SGP sincronizado para lead pk=%s: %s (id_sgp=%s)',
                lead.pk, cliente.nome, cliente.id_cliente_sgp,
            )
        return cliente
    except SGPServiceError as exc:
        logger.error('Erro ao sincronizar cliente SGP para lead pk=%s: %s', lead.pk, exc)
    except Exception as exc:
        logger.exception('Erro inesperado ao sincronizar cliente SGP para lead pk=%s: %s', lead.pk, exc)
    return None
