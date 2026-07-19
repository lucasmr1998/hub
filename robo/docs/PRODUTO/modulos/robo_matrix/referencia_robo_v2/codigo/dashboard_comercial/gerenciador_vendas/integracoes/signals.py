import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from vendas_web.models import LeadProspecto, HistoricoStatusLead

logger = logging.getLogger(__name__)


def _obter_integracao_hubsoft():
    from integracoes.models import IntegracaoAPI
    return IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()


def _registrar_historico_status(lead_id, status_anterior, status_novo, observacao=''):
    """Registra histórico manualmente para os `.update()` em massa deste
    módulo — eles bypassam o `pre_save` signal de `vendas_web/signals.py`."""
    try:
        HistoricoStatusLead.objects.create(
            lead_id=lead_id, status_anterior=status_anterior,
            status_novo=status_novo, origem='hubsoft_sync',
            observacao=observacao or None,
        )
    except Exception:
        logger.exception(
            'Falha ao registrar histórico de status_api do lead %s (%s → %s)',
            lead_id, status_anterior, status_novo,
        )


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

    from integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

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

        # Verificar se CPF já existe no Hubsoft antes de tentar cadastrar
        if instance.cpf_cnpj:
            try:
                resp_consulta = service.consultar_cliente(instance.cpf_cnpj, lead=instance)
                dados_cliente = resp_consulta.get('dados') or resp_consulta
                clientes = dados_cliente.get('clientes', [dados_cliente]) if isinstance(dados_cliente, dict) else []
                if not isinstance(clientes, list):
                    clientes = [clientes]
                cliente_encontrado = next((c for c in clientes if isinstance(c, dict) and c.get('id_cliente')), None)

                if cliente_encontrado:
                    # CPF já existe — apenas sincronizar sem tentar cadastrar
                    logger.info(
                        "Lead '%s' (pk=%s) já existe no Hubsoft (id_cliente=%s). Sincronizando.",
                        instance.nome_razaosocial, instance.pk, cliente_encontrado.get('id_cliente'),
                    )
                    LeadProspecto.objects.filter(pk=instance.pk).update(status_api='processado')
                    _registrar_historico_status(instance.pk, 'pendente', 'processado',
                                                 'CPF já existia no Hubsoft (consulta prévia)')
                    _sincronizar_cliente_hubsoft(instance, service)
                    return
            except Exception:
                pass  # Falha na consulta: tenta cadastrar normalmente

        resposta = service.cadastrar_prospecto(instance)

        id_prospecto = (
            resposta.get('prospecto', {}).get('id_prospecto')
        )

        campos_update = {'status_api': 'processado'}
        if id_prospecto:
            campos_update['id_hubsoft'] = str(id_prospecto)

        LeadProspecto.objects.filter(pk=instance.pk).update(**campos_update)
        _registrar_historico_status(instance.pk, 'pendente', 'processado',
                                     'Cadastrado como prospecto no Hubsoft')

        logger.info(
            "Lead '%s' (pk=%s) cadastrado no Hubsoft com id_prospecto=%s",
            instance.nome_razaosocial, instance.pk, id_prospecto,
        )

        _sincronizar_cliente_hubsoft(instance, service)

    except HubsoftServiceError as exc:
        msg = str(exc)
        # Se o erro for CPF já cadastrado, considerar como processado e sincronizar
        if 'já foi cadastrado' in msg or 'CPF' in msg or 'CNPJ' in msg:
            logger.info(
                "Lead '%s' (pk=%s) já existe no Hubsoft (detectado no cadastro). Sincronizando.",
                instance.nome_razaosocial, instance.pk,
            )
            LeadProspecto.objects.filter(pk=instance.pk).update(status_api='processado')
            _registrar_historico_status(instance.pk, 'pendente', 'processado',
                                         'CPF já cadastrado (detectado no erro de cadastro)')
            _sincronizar_cliente_hubsoft(instance)
        else:
            LeadProspecto.objects.filter(pk=instance.pk).update(status_api='erro')
            _registrar_historico_status(instance.pk, 'pendente', 'erro', str(exc)[:255])
            logger.error(
                "Erro ao enviar lead '%s' (pk=%s) para Hubsoft: %s",
                instance.nome_razaosocial, instance.pk, exc,
            )
    except Exception as exc:
        LeadProspecto.objects.filter(pk=instance.pk).update(status_api='erro')
        _registrar_historico_status(instance.pk, 'pendente', 'erro', str(exc)[:255])
        logger.exception(
            "Erro inesperado ao enviar lead '%s' (pk=%s) para Hubsoft: %s",
            instance.nome_razaosocial, instance.pk, exc,
        )


def _sincronizar_cliente_hubsoft(lead, service=None):
    """
    Consulta e sincroniza os dados do cliente no Hubsoft a partir
    do CPF/CNPJ do lead. Pode ser chamada standalone ou após cadastro.
    """
    from integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

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


