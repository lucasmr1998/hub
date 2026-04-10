"""
Engine de distribuicao automatica do Inbox.

Determina fila, seleciona agente e atribui conversas automaticamente.
Chamado por services.receber_mensagem() quando nova conversa e criada.
"""

import logging
from datetime import datetime

from django.utils import timezone

from .models import (
    Conversa, Mensagem, FilaInbox, RegraRoteamento,
    PerfilAgenteInbox, MembroEquipeInbox, HorarioAtendimento,
    ConfiguracaoInbox,
)

logger = logging.getLogger(__name__)


def verificar_horario_atendimento(tenant):
    """
    Verifica se o momento atual esta dentro do horario de atendimento GLOBAL.
    Se nao ha horarios cadastrados, assume sempre aberto (backward compatible).
    Usado como fallback quando a fila nao tem horarios proprios.
    """
    horarios = HorarioAtendimento.all_tenants.filter(tenant=tenant, fila__isnull=True, ativo=True)
    if not horarios.exists():
        return True

    agora = timezone.localtime()
    dia_semana = agora.weekday()
    hora_atual = agora.time()

    horario = horarios.filter(dia_semana=dia_semana).first()
    if not horario:
        return False

    return horario.hora_inicio <= hora_atual <= horario.hora_fim


def verificar_horario_fila(fila):
    """
    Verifica se a fila esta dentro do horario de atendimento.
    Se a fila nao tem horarios proprios, retorna True (sempre aberta).
    """
    horarios = fila.horarios.filter(ativo=True)
    if not horarios.exists():
        return True

    agora = timezone.localtime()
    horario = horarios.filter(dia_semana=agora.weekday()).first()
    if not horario:
        return False

    return horario.hora_inicio <= agora.time() <= horario.hora_fim


def determinar_fila(conversa, tenant):
    """
    Determina a fila para uma conversa baseado nas regras de roteamento.
    Itera regras por prioridade (maior primeiro), retorna a fila da primeira match.
    Retorna None se nenhuma regra bate.
    """
    regras = RegraRoteamento.all_tenants.filter(
        tenant=tenant, ativo=True, fila__ativo=True
    ).select_related('fila', 'fila__equipe', 'canal', 'etiqueta').order_by('-prioridade')

    agora = timezone.localtime()

    for regra in regras:
        if regra.tipo == 'canal':
            if regra.canal_id and conversa.canal_id == regra.canal_id:
                return regra.fila

        elif regra.tipo == 'etiqueta':
            if regra.etiqueta_id and conversa.etiquetas.filter(id=regra.etiqueta_id).exists():
                return regra.fila

        elif regra.tipo == 'horario':
            if regra.horario_inicio and regra.horario_fim:
                hora_atual = agora.time()
                dia_atual = str(agora.weekday())
                dias = [d.strip() for d in regra.dias_semana.split(',') if d.strip()]

                if (not dias or dia_atual in dias) and regra.horario_inicio <= hora_atual <= regra.horario_fim:
                    return regra.fila

    return None


def selecionar_agente(fila, tenant):
    """
    Seleciona o proximo agente disponivel para a fila.

    Modos:
    - manual: retorna None (conversa fica sem agente, espera atribuicao manual)
    - round_robin: proximo agente em ciclo circular
    - menor_carga: agente com menos conversas abertas

    Verifica: status=online e capacidade disponivel.
    """
    if fila.modo_distribuicao == 'manual':
        return None

    # Buscar membros da equipe da fila que estao online e com capacidade
    membros = MembroEquipeInbox.all_tenants.filter(
        tenant=tenant,
        equipe=fila.equipe,
    ).select_related('user').values_list('user_id', flat=True)

    if not membros:
        return None

    # Filtrar agentes disponiveis (online + com capacidade)
    perfis = PerfilAgenteInbox.all_tenants.filter(
        tenant=tenant,
        user_id__in=membros,
        status='online',
    ).select_related('user')

    disponiveis = []
    for perfil in perfis:
        if perfil.disponivel:
            disponiveis.append(perfil)

    if not disponiveis:
        return None

    if fila.modo_distribuicao == 'round_robin':
        return _round_robin(fila, disponiveis)
    elif fila.modo_distribuicao == 'menor_carga':
        return _menor_carga(disponiveis)

    return None


def _round_robin(fila, disponiveis):
    """Seleciona proximo agente em ciclo circular."""
    user_ids = [p.user_id for p in disponiveis]

    ultimo_id = fila.ultimo_agente_id
    if ultimo_id and ultimo_id in user_ids:
        idx = user_ids.index(ultimo_id)
        proximo_idx = (idx + 1) % len(user_ids)
    else:
        proximo_idx = 0

    agente_id = user_ids[proximo_idx]

    # Atualizar estado do round-robin
    FilaInbox.all_tenants.filter(pk=fila.pk).update(ultimo_agente_id=agente_id)

    perfil = next(p for p in disponiveis if p.user_id == agente_id)
    return perfil.user


def _menor_carga(disponiveis):
    """Seleciona agente com menos conversas abertas."""
    menor = min(disponiveis, key=lambda p: p.conversas_abertas_count)
    return menor.user


def distribuir_conversa(conversa, tenant):
    """
    Orquestrador principal: determina fila e seleciona agente.

    1. Determina fila via regras de roteamento (se nao tem fila definida)
    2. Verifica horario da fila
    3. Atribui equipe e fila a conversa
    4. Seleciona agente disponivel
    5. Cria mensagem de sistema se atribuiu
    """
    from .signals import _enviar_mensagens_bot

    fila = conversa.fila or determinar_fila(conversa, tenant)

    if fila:
        # Verificar horario da fila
        if not verificar_horario_fila(fila):
            msg = fila.mensagem_fora_horario or 'Estamos fora do horario de atendimento. Responderemos assim que possivel.'
            _enviar_mensagens_bot(tenant, conversa, msg, 'Aurora')
            conversa.fila = fila
            conversa.equipe = fila.equipe
            conversa.status = 'pendente'
            conversa.save(update_fields=['fila', 'equipe', 'status'])
            logger.info("Distribuicao: conversa #%s → fila %s (fora do horario)",
                        conversa.numero, fila.nome)
            return conversa

        conversa.fila = fila
        conversa.equipe = fila.equipe

        agente = selecionar_agente(fila, tenant)
        if agente:
            conversa.agente = agente
            conversa.save(update_fields=['fila', 'equipe', 'agente'])

            # Vincular agente como responsavel da oportunidade do lead
            from .services import _vincular_agente_oportunidade
            _vincular_agente_oportunidade(conversa, agente)

            nome = agente.get_full_name() or agente.username
            Mensagem(
                tenant=tenant,
                conversa=conversa,
                remetente_tipo='sistema',
                remetente_nome='Sistema',
                tipo_conteudo='sistema',
                conteudo=f"Conversa atribuida automaticamente a {nome} ({fila.equipe.nome})",
            ).save()

            logger.info("Distribuicao: conversa #%s → %s (fila: %s, modo: %s)",
                        conversa.numero, nome, fila.nome, fila.modo_distribuicao)
        else:
            conversa.save(update_fields=['fila', 'equipe'])
            logger.info("Distribuicao: conversa #%s → fila %s (sem agente disponivel)",
                        conversa.numero, fila.nome)
    else:
        # Sem fila = sem distribuicao automatica
        logger.debug("Distribuicao: conversa #%s sem fila correspondente", conversa.numero)

    return conversa
