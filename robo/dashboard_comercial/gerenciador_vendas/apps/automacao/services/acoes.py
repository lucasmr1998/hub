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


def mover_estagio(tenant, *, oportunidade, estagio_slug):
    """Move a `oportunidade` pro estágio (slug) dentro do pipeline dela. Devolve o estágio."""
    from apps.comercial.crm.models import PipelineEstagio
    if oportunidade is None:
        raise ValueError('Sem oportunidade para mover.')
    if not (estagio_slug or '').strip():
        raise ValueError('Estágio não especificado.')
    estagio = PipelineEstagio.all_tenants.filter(
        tenant=tenant, pipeline=oportunidade.pipeline, slug=estagio_slug.strip(),
    ).first()
    if estagio is None:
        raise ValueError(f'Estágio "{estagio_slug}" não encontrado no pipeline.')
    oportunidade.estagio = estagio
    oportunidade.save(update_fields=['estagio'])
    return estagio


def criar_oportunidade(tenant, *, lead, titulo=None, pipeline_slug='', estagio_slug=''):
    """Cria uma OportunidadeVenda pro lead. Idempotente (não duplica). Devolve (oport, criada)."""
    from apps.comercial.crm.models import OportunidadeVenda, Pipeline, PipelineEstagio
    if lead is None or not getattr(lead, 'pk', None):
        raise ValueError('Lead não encontrado.')

    existente = OportunidadeVenda.all_tenants.filter(tenant=tenant, lead=lead).first()
    if existente:
        return existente, False

    pipeline = None
    if (pipeline_slug or '').strip():
        pipeline = Pipeline.all_tenants.filter(tenant=tenant, slug=pipeline_slug.strip()).first()
    if pipeline is None:
        pipeline = (Pipeline.all_tenants.filter(tenant=tenant, padrao=True).first()
                    or Pipeline.all_tenants.filter(tenant=tenant).first())
    if pipeline is None:
        raise ValueError('Nenhum pipeline encontrado pro tenant.')

    estagio = None
    if (estagio_slug or '').strip():
        estagio = PipelineEstagio.all_tenants.filter(
            tenant=tenant, pipeline=pipeline, slug=estagio_slug.strip()).first()
    if estagio is None:
        estagio = PipelineEstagio.all_tenants.filter(
            tenant=tenant, pipeline=pipeline).order_by('ordem').first()
    if estagio is None:
        raise ValueError('Nenhum estágio encontrado no pipeline.')

    oport = OportunidadeVenda(
        tenant=tenant, lead=lead, pipeline=pipeline, estagio=estagio,
        titulo=(titulo or '').strip() or getattr(lead, 'nome', '') or 'Oportunidade',
        valor_estimado=getattr(lead, 'valor', None),
        origem_crm='automatico',
    )
    oport.save()
    return oport, True


def criar_venda(tenant, *, lead):
    """Cria uma Venda pendente-ERP pro lead. Idempotente. Devolve (venda, criada)."""
    from apps.comercial.crm.models import OportunidadeVenda, Venda
    if lead is None or not getattr(lead, 'pk', None):
        raise ValueError('Lead não encontrado.')

    existente = Venda.all_tenants.filter(tenant=tenant, lead=lead).first()
    if existente:
        return existente, False

    oport = OportunidadeVenda.all_tenants.filter(tenant=tenant, lead=lead).first()
    venda = Venda(
        tenant=tenant, lead=lead, oportunidade=oport,
        plano=oport.plano_interesse if oport else None,
        valor=oport.valor_estimado if oport else None,
        status=Venda.STATUS_PENDENTE_ERP,
    )
    venda.save()
    return venda, True


def dar_pontos(tenant, *, cpf, pontos, motivo=''):
    """Soma `pontos` ao saldo do MembroClube com aquele CPF (do tenant). Devolve o membro."""
    from apps.cs.clube.models import MembroClube
    cpf_limpo = (cpf or '').replace('.', '').replace('-', '').replace('/', '').strip()[:14]
    if not cpf_limpo:
        raise ValueError('CPF não informado.')
    membro = MembroClube.all_tenants.filter(tenant=tenant, cpf=cpf_limpo).first()
    if membro is None:
        raise ValueError(f'Membro do clube não encontrado para o CPF {cpf}.')
    membro.saldo = (membro.saldo or 0) + int(pontos)
    membro.save(update_fields=['saldo'])
    return membro


def atribuir_responsavel(tenant, *, oportunidade=None, lead=None, modo='round-robin', username=''):
    """Atribui responsável à oportunidade. `modo`='round-robin' (menos carregado) ou
    'fixo' (username). Devolve o User atribuído."""
    from django.contrib.auth.models import User
    from apps.comercial.crm.models import OportunidadeVenda
    from apps.sistema.models import PerfilUsuario

    if oportunidade is None and lead is not None and getattr(lead, 'pk', None):
        oportunidade = OportunidadeVenda.all_tenants.filter(tenant=tenant, lead=lead).first()
    if oportunidade is None:
        raise ValueError('Sem oportunidade para atribuir.')

    if modo == 'fixo':
        responsavel = (User.objects.filter(
            is_staff=True, username__icontains=(username or '').strip()).first()
            if (username or '').strip() else None)
        if responsavel is None:
            raise ValueError(f'Responsável não encontrado: {username}')
    else:
        perfis = PerfilUsuario.objects.filter(
            tenant=tenant, user__is_staff=True, user__is_active=True).select_related('user')
        if not perfis.exists():
            raise ValueError('Nenhum agente disponível para round-robin.')
        counts = {
            p.user_id: OportunidadeVenda.all_tenants.filter(
                tenant=tenant, responsavel=p.user, ativo=True).count()
            for p in perfis
        }
        responsavel = User.objects.get(pk=min(counts, key=counts.get))

    oportunidade.responsavel = responsavel
    oportunidade.save(update_fields=['responsavel'])
    return responsavel
