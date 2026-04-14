"""
Tools do Assistente CRM.
Cada tool recebe (tenant, usuario, argumentos) e retorna string com resultado.
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_LISTA = 10


def consultar_lead(tenant, usuario, args):
    """Busca lead por nome ou telefone."""
    from django.db.models import Q
    from apps.comercial.leads.models import LeadProspecto

    busca = args.get('busca', '').strip()
    if not busca:
        return 'Informe o nome ou telefone do lead.'

    leads = LeadProspecto.objects.filter(
        Q(nome_razaosocial__icontains=busca) | Q(telefone__icontains=busca)
    )[:5]

    if not leads:
        return f'Nenhum lead encontrado com "{busca}".'

    if leads.count() > 1:
        resultado = f'Encontrei {leads.count()} leads:\n'
        for l in leads:
            resultado += f'- {l.nome_razaosocial} ({l.telefone})\n'
        resultado += 'Qual deles?'
        return resultado

    l = leads[0]
    oport = getattr(l, 'oportunidade_crm', None)
    resultado = f'Lead: {l.nome_razaosocial}\n'
    resultado += f'Telefone: {l.telefone}\n'
    resultado += f'Email: {l.email or "N/A"}\n'
    resultado += f'Score: {l.score_qualificacao or 0}/10\n'
    resultado += f'Origem: {l.origem or "N/A"}\n'
    if oport:
        resultado += f'Oportunidade: {oport.estagio.nome} (R$ {oport.valor_estimado or 0})\n'
    return resultado


def listar_oportunidades(tenant, usuario, args):
    """Lista oportunidades do vendedor com filtro opcional."""
    from apps.comercial.crm.models import OportunidadeVenda

    estagio = args.get('estagio', '').strip()
    todas = args.get('todas', False)

    qs = OportunidadeVenda.objects.filter(ativo=True).select_related('lead', 'estagio', 'responsavel')

    if not todas:
        qs = qs.filter(responsavel=usuario)

    if estagio:
        qs = qs.filter(estagio__nome__icontains=estagio)

    total = qs.count()
    oports = qs.order_by('-data_criacao')[:MAX_LISTA]

    if not oports:
        return 'Nenhuma oportunidade encontrada.'

    resultado = f'{total} oportunidade(s)'
    if total > MAX_LISTA:
        resultado += f' (mostrando {MAX_LISTA})'
    resultado += ':\n\n'

    for o in oports:
        nome = o.titulo or o.lead.nome_razaosocial
        valor = f'R$ {o.valor_estimado}' if o.valor_estimado else 'sem valor'
        resultado += f'- {nome} | {o.estagio.nome} | {valor}\n'

    return resultado


def mover_oportunidade(tenant, usuario, args):
    """Move oportunidade para outro estagio."""
    from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio, HistoricoPipelineEstagio
    from django.db.models import Q

    lead_busca = args.get('lead', '').strip()
    estagio_destino = args.get('estagio', '').strip()

    if not lead_busca or not estagio_destino:
        return 'Informe o lead e o estagio de destino.'

    oport = OportunidadeVenda.objects.filter(
        ativo=True
    ).filter(
        Q(lead__nome_razaosocial__icontains=lead_busca) | Q(titulo__icontains=lead_busca)
    ).select_related('estagio', 'lead').first()

    if not oport:
        return f'Nenhuma oportunidade encontrada para "{lead_busca}".'

    estagio_novo = PipelineEstagio.objects.filter(nome__icontains=estagio_destino, ativo=True).first()
    if not estagio_novo:
        estagios = PipelineEstagio.objects.filter(ativo=True).values_list('nome', flat=True)
        return f'Estagio "{estagio_destino}" nao encontrado. Estagios disponiveis: {", ".join(estagios)}'

    estagio_anterior = oport.estagio
    if estagio_anterior.pk == estagio_novo.pk:
        return f'Oportunidade ja esta no estagio "{estagio_novo.nome}".'

    horas = (timezone.now() - oport.data_entrada_estagio).total_seconds() / 3600
    HistoricoPipelineEstagio.objects.create(
        tenant=tenant,
        oportunidade=oport,
        estagio_anterior=estagio_anterior,
        estagio_novo=estagio_novo,
        movido_por=usuario,
        motivo='Via Assistente CRM WhatsApp',
        tempo_no_estagio_horas=round(horas, 2),
    )

    oport.estagio = estagio_novo
    oport.data_entrada_estagio = timezone.now()
    oport.save(update_fields=['estagio', 'data_entrada_estagio'])

    nome = oport.titulo or oport.lead.nome_razaosocial
    return f'Oportunidade "{nome}" movida de "{estagio_anterior.nome}" para "{estagio_novo.nome}".'


def criar_nota(tenant, usuario, args):
    """Cria nota interna na oportunidade."""
    from apps.comercial.crm.models import OportunidadeVenda, NotaInterna
    from django.db.models import Q

    lead_busca = args.get('lead', '').strip()
    texto = args.get('texto', '').strip()

    if not lead_busca or not texto:
        return 'Informe o lead e o texto da nota.'

    oport = OportunidadeVenda.objects.filter(
        ativo=True
    ).filter(
        Q(lead__nome_razaosocial__icontains=lead_busca) | Q(titulo__icontains=lead_busca)
    ).first()

    if not oport:
        return f'Nenhuma oportunidade encontrada para "{lead_busca}".'

    NotaInterna.objects.create(
        tenant=tenant,
        oportunidade=oport,
        autor=usuario,
        conteudo=texto,
        tipo='geral',
    )

    nome = oport.titulo or oport.lead.nome_razaosocial
    return f'Nota salva na oportunidade de {nome}.'


def criar_tarefa(tenant, usuario, args):
    """Cria tarefa no CRM."""
    from apps.comercial.crm.models import OportunidadeVenda, TarefaCRM
    from django.db.models import Q

    lead_busca = args.get('lead', '').strip()
    titulo = args.get('titulo', '').strip()
    vencimento_str = args.get('vencimento', '').strip()

    if not titulo:
        return 'Informe o titulo da tarefa.'

    oport = None
    lead = None
    if lead_busca:
        oport = OportunidadeVenda.objects.filter(
            ativo=True
        ).filter(
            Q(lead__nome_razaosocial__icontains=lead_busca) | Q(titulo__icontains=lead_busca)
        ).select_related('lead').first()
        if oport:
            lead = oport.lead

    # Calcular vencimento
    data_vencimento = timezone.now() + timedelta(days=1)  # default: amanha
    if 'hoje' in vencimento_str.lower():
        data_vencimento = timezone.now()
    elif 'amanha' in vencimento_str.lower() or 'amanhã' in vencimento_str.lower():
        data_vencimento = timezone.now() + timedelta(days=1)
    elif 'semana' in vencimento_str.lower():
        data_vencimento = timezone.now() + timedelta(days=7)

    tarefa = TarefaCRM.objects.create(
        tenant=tenant,
        oportunidade=oport,
        lead=lead,
        responsavel=usuario,
        criado_por=usuario,
        titulo=titulo,
        status='pendente',
        prioridade='normal',
        data_vencimento=data_vencimento,
    )

    nome_lead = lead.nome_razaosocial if lead else 'sem lead'
    return f'Tarefa criada: "{titulo}" para {nome_lead}, vencimento {data_vencimento.strftime("%d/%m/%Y %H:%M")}.'


def atualizar_lead(tenant, usuario, args):
    """Atualiza campo do lead."""
    from apps.comercial.leads.models import LeadProspecto
    from django.db.models import Q

    lead_busca = args.get('lead', '').strip()
    campo = args.get('campo', '').strip()
    valor = args.get('valor', '').strip()

    if not lead_busca or not campo or not valor:
        return 'Informe o lead, o campo e o novo valor.'

    lead = LeadProspecto.objects.filter(
        Q(nome_razaosocial__icontains=lead_busca) | Q(telefone__icontains=lead_busca)
    ).first()

    if not lead:
        return f'Lead "{lead_busca}" nao encontrado.'

    campos_permitidos = ['email', 'telefone', 'empresa', 'observacoes', 'cidade', 'estado', 'bairro', 'cep']
    if campo not in campos_permitidos:
        return f'Campo "{campo}" nao pode ser atualizado. Campos permitidos: {", ".join(campos_permitidos)}'

    setattr(lead, campo, valor)
    lead.save(update_fields=[campo])

    return f'Lead {lead.nome_razaosocial}: {campo} atualizado para "{valor}".'


def resumo_pipeline(tenant, usuario, args):
    """Retorna metricas do pipeline."""
    from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio
    from django.db.models import Count, Sum

    qs = OportunidadeVenda.objects.filter(ativo=True)

    total = qs.count()
    valor_total = qs.aggregate(total=Sum('valor_estimado'))['total'] or 0

    por_estagio = qs.values('estagio__nome').annotate(
        qtd=Count('id'), valor=Sum('valor_estimado')
    ).order_by('estagio__ordem')

    resultado = f'Pipeline: {total} oportunidades, R$ {valor_total:.2f} total\n\n'
    for e in por_estagio:
        valor = e['valor'] or 0
        resultado += f'- {e["estagio__nome"]}: {e["qtd"]} (R$ {valor:.2f})\n'

    return resultado


def listar_tarefas(tenant, usuario, args):
    """Lista tarefas do vendedor."""
    from apps.comercial.crm.models import TarefaCRM

    filtro = args.get('filtro', 'hoje').strip().lower()

    qs = TarefaCRM.objects.filter(
        responsavel=usuario,
        status__in=['pendente', 'em_andamento'],
    ).select_related('lead', 'oportunidade').order_by('data_vencimento')

    if 'hoje' in filtro:
        hoje = timezone.now().date()
        qs = qs.filter(data_vencimento__date=hoje)
    elif 'semana' in filtro:
        qs = qs.filter(data_vencimento__date__lte=timezone.now().date() + timedelta(days=7))
    elif 'vencida' in filtro or 'atrasada' in filtro:
        qs = qs.filter(data_vencimento__lt=timezone.now())

    total = qs.count()
    tarefas = qs[:MAX_LISTA]

    if not tarefas:
        return f'Nenhuma tarefa {filtro} encontrada.'

    resultado = f'{total} tarefa(s)'
    if total > MAX_LISTA:
        resultado += f' (mostrando {MAX_LISTA})'
    resultado += ':\n\n'

    for t in tarefas:
        nome_lead = t.lead.nome_razaosocial if t.lead else 'sem lead'
        venc = t.data_vencimento.strftime('%d/%m %H:%M') if t.data_vencimento else 'sem prazo'
        resultado += f'- {t.titulo} | {nome_lead} | {venc}\n'

    return resultado


def proxima_tarefa(tenant, usuario, args):
    """Retorna a proxima tarefa a vencer."""
    from apps.comercial.crm.models import TarefaCRM

    tarefa = TarefaCRM.objects.filter(
        responsavel=usuario,
        status__in=['pendente', 'em_andamento'],
        data_vencimento__gte=timezone.now(),
    ).select_related('lead', 'oportunidade').order_by('data_vencimento').first()

    if not tarefa:
        # Tentar pegar atrasadas
        tarefa = TarefaCRM.objects.filter(
            responsavel=usuario,
            status__in=['pendente', 'em_andamento'],
        ).select_related('lead', 'oportunidade').order_by('data_vencimento').first()

    if not tarefa:
        return 'Nenhuma tarefa pendente.'

    nome_lead = tarefa.lead.nome_razaosocial if tarefa.lead else 'sem lead'
    venc = tarefa.data_vencimento.strftime('%d/%m/%Y %H:%M') if tarefa.data_vencimento else 'sem prazo'
    atrasada = ' (ATRASADA!)' if tarefa.data_vencimento and tarefa.data_vencimento < timezone.now() else ''

    return f'Proxima tarefa: "{tarefa.titulo}"\nLead: {nome_lead}\nVencimento: {venc}{atrasada}\nPrioridade: {tarefa.prioridade}'


# Registro de todas as tools
TOOLS_ASSISTENTE = {
    'consultar_lead': {
        'func': consultar_lead,
        'description': 'Busca um lead por nome ou telefone e retorna seus dados',
        'parameters': {
            'type': 'object',
            'properties': {
                'busca': {'type': 'string', 'description': 'Nome ou telefone do lead'},
            },
            'required': ['busca'],
        },
    },
    'listar_oportunidades': {
        'func': listar_oportunidades,
        'description': 'Lista as oportunidades do vendedor no pipeline, com filtro opcional por estagio',
        'parameters': {
            'type': 'object',
            'properties': {
                'estagio': {'type': 'string', 'description': 'Filtrar por nome do estagio (opcional)'},
                'todas': {'type': 'boolean', 'description': 'Se true, lista de todos os vendedores'},
            },
            'required': [],
        },
    },
    'mover_oportunidade': {
        'func': mover_oportunidade,
        'description': 'Move uma oportunidade para outro estagio do pipeline',
        'parameters': {
            'type': 'object',
            'properties': {
                'lead': {'type': 'string', 'description': 'Nome do lead ou oportunidade'},
                'estagio': {'type': 'string', 'description': 'Nome do estagio de destino'},
            },
            'required': ['lead', 'estagio'],
        },
    },
    'criar_nota': {
        'func': criar_nota,
        'description': 'Cria uma nota interna na oportunidade de um lead',
        'parameters': {
            'type': 'object',
            'properties': {
                'lead': {'type': 'string', 'description': 'Nome do lead'},
                'texto': {'type': 'string', 'description': 'Texto da nota'},
            },
            'required': ['lead', 'texto'],
        },
    },
    'criar_tarefa': {
        'func': criar_tarefa,
        'description': 'Cria uma tarefa no CRM vinculada a um lead',
        'parameters': {
            'type': 'object',
            'properties': {
                'lead': {'type': 'string', 'description': 'Nome do lead (opcional)'},
                'titulo': {'type': 'string', 'description': 'Titulo da tarefa'},
                'vencimento': {'type': 'string', 'description': 'Quando vence: hoje, amanha, semana (opcional)'},
            },
            'required': ['titulo'],
        },
    },
    'atualizar_lead': {
        'func': atualizar_lead,
        'description': 'Atualiza um campo do lead (email, telefone, empresa, observacoes, cidade, estado, bairro, cep)',
        'parameters': {
            'type': 'object',
            'properties': {
                'lead': {'type': 'string', 'description': 'Nome ou telefone do lead'},
                'campo': {'type': 'string', 'description': 'Nome do campo a atualizar'},
                'valor': {'type': 'string', 'description': 'Novo valor'},
            },
            'required': ['lead', 'campo', 'valor'],
        },
    },
    'resumo_pipeline': {
        'func': resumo_pipeline,
        'description': 'Retorna um resumo do pipeline com total de oportunidades e valor por estagio',
        'parameters': {
            'type': 'object',
            'properties': {},
            'required': [],
        },
    },
    'listar_tarefas': {
        'func': listar_tarefas,
        'description': 'Lista tarefas do vendedor com filtro: hoje, semana, vencidas',
        'parameters': {
            'type': 'object',
            'properties': {
                'filtro': {'type': 'string', 'description': 'Filtro: hoje, semana, vencidas, todas (default: hoje)'},
            },
            'required': [],
        },
    },
    'proxima_tarefa': {
        'func': proxima_tarefa,
        'description': 'Retorna a proxima tarefa pendente a vencer do vendedor',
        'parameters': {
            'type': 'object',
            'properties': {},
            'required': [],
        },
    },
}
