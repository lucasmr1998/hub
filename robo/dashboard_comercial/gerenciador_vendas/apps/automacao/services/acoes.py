"""
Executores de domínio compartilhados pela engine de automação.

São a **fonte única** de cada ação: o nó da engine nova chama daqui e, na
convergência, o `_acao_*` do motor de marketing passa a delegar pra cá também —
em vez de manter uma 2ª/3ª cópia da lógica.

Contrato: recebem parâmetros **já resolvidos** (templates interpolados pelo
chamador) + `tenant` explícito + as entidades (`lead`/`oportunidade`) como
objetos. Nunca tocam em `request`/thread-local (a engine roda em cron/signal).
"""
from datetime import timedelta

from django.utils import timezone


def criar_tarefa(tenant, *, titulo, tipo='followup', prioridade='normal',
                 lead=None, oportunidade=None, responsavel=None, prazo_dias=1):
    """Cria uma `TarefaCRM`. Se `responsavel` não vier, resolve um default
    (lead.responsavel → staff do tenant → superuser). Devolve a TarefaCRM.

    Levanta `ValueError` se não houver nenhum responsável possível (o campo é
    obrigatório no model).
    """
    from django.contrib.auth.models import User
    from apps.comercial.crm.models import TarefaCRM
    from apps.sistema.models import PerfilUsuario

    if responsavel is None and lead is not None:
        responsavel = getattr(lead, 'responsavel', None)
    if responsavel is None:
        perfil = PerfilUsuario.objects.filter(tenant=tenant, user__is_staff=True).first()
        responsavel = perfil.user if perfil else User.objects.filter(is_superuser=True).first()
    if responsavel is None:
        raise ValueError('Nenhum responsável disponível para a tarefa.')

    tarefa = TarefaCRM(
        tenant=tenant,
        titulo=titulo,
        tipo=tipo or 'followup',
        prioridade=prioridade or 'normal',
        status='pendente',
        lead=lead if (lead is not None and getattr(lead, 'pk', None)) else None,
        oportunidade=oportunidade if (oportunidade is not None and getattr(oportunidade, 'pk', None)) else None,
        responsavel=responsavel,
        data_vencimento=timezone.now() + timedelta(days=prazo_dias or 1),
    )
    tarefa.save()
    return tarefa


def notificar(tenant, *, titulo, mensagem, codigo_tipo='sistema_geral'):
    """Cria uma notificação **broadcast** (a equipe inteira do tenant vê).

    Reusa o service de domínio `apps.notificacoes.services.criar_notificacao`.
    Devolve a Notificacao, ou `None` se o tipo não estiver cadastrado pro tenant
    (nesse caso o chamador trata — ex: rodar `seedar_notificacoes`).
    """
    from apps.notificacoes.services import criar_notificacao
    return criar_notificacao(
        tenant=tenant, codigo_tipo=codigo_tipo,
        titulo=titulo, mensagem=mensagem, destinatario=None,
    )
