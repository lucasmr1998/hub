"""
Distribuição automática de oportunidades no CRM.
Round robin entre membros ativos da equipe configurada.
"""
import logging

from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


def distribuir_oportunidade(oportunidade):
    """
    Atribui responsável a uma oportunidade via round robin.
    Só atribui se:
    - Oportunidade não tem responsável
    - ConfiguracaoCRM tem distribuição ativada
    - Equipe configurada tem membros ativos
    """
    if oportunidade.responsavel:
        return None

    from .models import ConfiguracaoCRM, PerfilVendedor

    try:
        config = ConfiguracaoCRM.all_tenants.filter(tenant=oportunidade.tenant).first()
        if not config:
            return None

        if config.distribuicao_modo != 'round_robin':
            return None

        equipe = config.distribuicao_equipe
        if not equipe:
            logger.debug("[CRM Distrib] Sem equipe configurada para distribuição")
            return None

        # Buscar membros ativos da equipe
        membros = PerfilVendedor.all_tenants.filter(
            tenant=oportunidade.tenant,
            equipe=equipe,
            ativo=True,
            user__is_active=True,
        ).select_related('user').order_by('user__first_name')

        if not membros.exists():
            logger.debug("[CRM Distrib] Equipe %s sem membros ativos", equipe.nome)
            return None

        user_ids = [m.user_id for m in membros]

        # Round robin
        ultimo_id = config.distribuicao_ultimo_vendedor_id
        if ultimo_id and ultimo_id in user_ids:
            idx = user_ids.index(ultimo_id)
            proximo_idx = (idx + 1) % len(user_ids)
        else:
            proximo_idx = 0

        vendedor_id = user_ids[proximo_idx]
        vendedor = User.objects.get(pk=vendedor_id)

        # Atribuir
        oportunidade.responsavel = vendedor
        oportunidade.save(update_fields=['responsavel'])

        # Atualizar estado do round robin
        ConfiguracaoCRM.all_tenants.filter(pk=config.pk).update(
            distribuicao_ultimo_vendedor_id=vendedor_id
        )

        logger.info(
            "[CRM Distrib] Oportunidade #%s atribuída a %s (equipe: %s, round robin)",
            oportunidade.pk, vendedor.get_full_name() or vendedor.username, equipe.nome
        )
        return vendedor

    except Exception as e:
        logger.error("[CRM Distrib] Erro ao distribuir oportunidade #%s: %s", oportunidade.pk, e)
        return None
