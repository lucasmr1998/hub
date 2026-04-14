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


def agendar_followup(tenant, usuario, args):
    """Cria tarefa de follow-up com lembrete."""
    from apps.comercial.crm.models import OportunidadeVenda, TarefaCRM
    from django.db.models import Q
    from datetime import datetime

    lead_busca = args.get('lead', '').strip()
    quando = args.get('quando', '').strip()
    observacao = args.get('observacao', '').strip()

    if not lead_busca:
        return 'Informe o nome do lead para o follow-up.'

    oport = OportunidadeVenda.objects.filter(
        ativo=True
    ).filter(
        Q(lead__nome_razaosocial__icontains=lead_busca) | Q(titulo__icontains=lead_busca)
    ).select_related('lead').first()

    lead = oport.lead if oport else None

    # Calcular data
    data_vencimento = timezone.now() + timedelta(days=1)
    quando_lower = quando.lower()
    if 'hoje' in quando_lower:
        data_vencimento = timezone.now() + timedelta(hours=2)
    elif 'amanha' in quando_lower or 'amanhã' in quando_lower:
        data_vencimento = timezone.now() + timedelta(days=1)
    elif 'sexta' in quando_lower:
        dias_ate_sexta = (4 - timezone.now().weekday()) % 7 or 7
        data_vencimento = timezone.now() + timedelta(days=dias_ate_sexta)
    elif 'segunda' in quando_lower:
        dias_ate_segunda = (0 - timezone.now().weekday()) % 7 or 7
        data_vencimento = timezone.now() + timedelta(days=dias_ate_segunda)
    elif 'semana' in quando_lower:
        data_vencimento = timezone.now() + timedelta(days=7)

    # Extrair horario se mencionado
    import re
    hora_match = re.search(r'(\d{1,2})[h:](\d{0,2})', quando)
    if hora_match:
        hora = int(hora_match.group(1))
        minuto = int(hora_match.group(2)) if hora_match.group(2) else 0
        data_vencimento = data_vencimento.replace(hour=hora, minute=minuto, second=0)

    titulo = f'Follow-up: {lead.nome_razaosocial if lead else lead_busca}'
    if observacao:
        titulo += f' - {observacao}'

    TarefaCRM.objects.create(
        tenant=tenant,
        oportunidade=oport,
        lead=lead,
        responsavel=usuario,
        criado_por=usuario,
        titulo=titulo,
        tipo='followup',
        status='pendente',
        prioridade='normal',
        data_vencimento=data_vencimento,
    )

    nome = lead.nome_razaosocial if lead else lead_busca
    return f'Follow-up agendado: {nome} em {data_vencimento.strftime("%d/%m/%Y %H:%M")}.'


def buscar_historico(tenant, usuario, args):
    """Ultimas interacoes e notas de um lead."""
    from apps.comercial.crm.models import OportunidadeVenda, NotaInterna, TarefaCRM
    from django.db.models import Q

    lead_busca = args.get('lead', '').strip()
    if not lead_busca:
        return 'Informe o nome do lead.'

    oport = OportunidadeVenda.objects.filter(
        ativo=True
    ).filter(
        Q(lead__nome_razaosocial__icontains=lead_busca) | Q(titulo__icontains=lead_busca)
    ).select_related('lead', 'estagio').first()

    if not oport:
        return f'Nenhuma oportunidade encontrada para "{lead_busca}".'

    nome = oport.titulo or oport.lead.nome_razaosocial
    resultado = f'Historico de {nome}:\n'
    resultado += f'Estagio atual: {oport.estagio.nome}\n'
    resultado += f'Valor: R$ {oport.valor_estimado or 0}\n\n'

    # Ultimas notas
    notas = NotaInterna.objects.filter(oportunidade=oport).order_by('-data_criacao')[:5]
    if notas:
        resultado += 'Ultimas notas:\n'
        for n in notas:
            data = n.data_criacao.strftime('%d/%m %H:%M')
            autor = n.autor.get_full_name() if n.autor else 'Sistema'
            resultado += f'- [{data}] {autor}: {n.conteudo[:80]}\n'
    else:
        resultado += 'Sem notas.\n'

    # Ultimas tarefas
    tarefas = TarefaCRM.objects.filter(oportunidade=oport).order_by('-data_criacao')[:5]
    if tarefas:
        resultado += '\nUltimas tarefas:\n'
        for t in tarefas:
            status_icon = 'V' if t.status == 'concluida' else 'O'
            resultado += f'- [{status_icon}] {t.titulo} ({t.status})\n'

    return resultado


def marcar_perda(tenant, usuario, args):
    """Move oportunidade para estagio final Perdido com motivo."""
    from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio, HistoricoPipelineEstagio
    from django.db.models import Q

    lead_busca = args.get('lead', '').strip()
    motivo = args.get('motivo', '').strip()

    if not lead_busca:
        return 'Informe o nome do lead.'

    oport = OportunidadeVenda.objects.filter(
        ativo=True
    ).filter(
        Q(lead__nome_razaosocial__icontains=lead_busca) | Q(titulo__icontains=lead_busca)
    ).select_related('estagio', 'lead').first()

    if not oport:
        return f'Nenhuma oportunidade encontrada para "{lead_busca}".'

    estagio_perdido = PipelineEstagio.objects.filter(
        is_final_perdido=True, ativo=True
    ).first()

    if not estagio_perdido:
        return 'Nenhum estagio de perda configurado no pipeline.'

    estagio_anterior = oport.estagio
    horas = (timezone.now() - oport.data_entrada_estagio).total_seconds() / 3600

    HistoricoPipelineEstagio.objects.create(
        tenant=tenant,
        oportunidade=oport,
        estagio_anterior=estagio_anterior,
        estagio_novo=estagio_perdido,
        movido_por=usuario,
        motivo=motivo or 'Perda registrada via Assistente CRM',
        tempo_no_estagio_horas=round(horas, 2),
    )

    oport.estagio = estagio_perdido
    oport.data_entrada_estagio = timezone.now()
    oport.motivo_perda = motivo
    oport.data_fechamento_real = timezone.now()
    oport.save(update_fields=['estagio', 'data_entrada_estagio', 'motivo_perda', 'data_fechamento_real'])

    nome = oport.titulo or oport.lead.nome_razaosocial
    return f'Oportunidade "{nome}" marcada como perdida. Motivo: {motivo or "nao informado"}.'


def marcar_ganho(tenant, usuario, args):
    """Move oportunidade para estagio final Ganho."""
    from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio, HistoricoPipelineEstagio
    from django.db.models import Q

    lead_busca = args.get('lead', '').strip()

    if not lead_busca:
        return 'Informe o nome do lead.'

    oport = OportunidadeVenda.objects.filter(
        ativo=True
    ).filter(
        Q(lead__nome_razaosocial__icontains=lead_busca) | Q(titulo__icontains=lead_busca)
    ).select_related('estagio', 'lead').first()

    if not oport:
        return f'Nenhuma oportunidade encontrada para "{lead_busca}".'

    estagio_ganho = PipelineEstagio.objects.filter(
        is_final_ganho=True, ativo=True
    ).first()

    if not estagio_ganho:
        return 'Nenhum estagio de ganho configurado no pipeline.'

    estagio_anterior = oport.estagio
    horas = (timezone.now() - oport.data_entrada_estagio).total_seconds() / 3600

    HistoricoPipelineEstagio.objects.create(
        tenant=tenant,
        oportunidade=oport,
        estagio_anterior=estagio_anterior,
        estagio_novo=estagio_ganho,
        movido_por=usuario,
        motivo='Venda fechada via Assistente CRM',
        tempo_no_estagio_horas=round(horas, 2),
    )

    oport.estagio = estagio_ganho
    oport.data_entrada_estagio = timezone.now()
    oport.data_fechamento_real = timezone.now()
    oport.save(update_fields=['estagio', 'data_entrada_estagio', 'data_fechamento_real'])

    nome = oport.titulo or oport.lead.nome_razaosocial
    return f'Parabens! Oportunidade "{nome}" marcada como GANHA!'


def agenda_do_dia(tenant, usuario, args):
    """Resumo completo do dia: tarefas + oportunidades paradas."""
    from apps.comercial.crm.models import TarefaCRM, OportunidadeVenda

    hoje = timezone.now().date()
    resultado = ''

    # Tarefas de hoje
    tarefas_hoje = TarefaCRM.objects.filter(
        responsavel=usuario,
        status__in=['pendente', 'em_andamento'],
        data_vencimento__date=hoje,
    ).select_related('lead').order_by('data_vencimento')[:10]

    if tarefas_hoje:
        resultado += f'Tarefas para hoje ({tarefas_hoje.count()}):\n'
        for t in tarefas_hoje:
            nome = t.lead.nome_razaosocial if t.lead else ''
            hora = t.data_vencimento.strftime('%H:%M') if t.data_vencimento else ''
            resultado += f'  - {t.titulo} {nome} ({hora})\n'
    else:
        resultado += 'Nenhuma tarefa para hoje.\n'

    # Tarefas atrasadas
    atrasadas = TarefaCRM.objects.filter(
        responsavel=usuario,
        status__in=['pendente', 'em_andamento'],
        data_vencimento__lt=timezone.now(),
    ).exclude(data_vencimento__date=hoje).select_related('lead').order_by('data_vencimento')[:5]

    if atrasadas:
        resultado += f'\nTarefas atrasadas ({atrasadas.count()}):\n'
        for t in atrasadas:
            nome = t.lead.nome_razaosocial if t.lead else ''
            dias = (hoje - t.data_vencimento.date()).days
            resultado += f'  - {t.titulo} {nome} ({dias} dia(s) de atraso)\n'

    # Oportunidades paradas (sem acao ha 3+ dias)
    limite = timezone.now() - timedelta(days=3)
    paradas = OportunidadeVenda.objects.filter(
        responsavel=usuario,
        ativo=True,
        data_entrada_estagio__lt=limite,
    ).exclude(
        estagio__is_final_ganho=True
    ).exclude(
        estagio__is_final_perdido=True
    ).select_related('estagio', 'lead').order_by('data_entrada_estagio')[:5]

    if paradas:
        resultado += f'\nOportunidades paradas (3+ dias sem acao):\n'
        for o in paradas:
            nome = o.titulo or o.lead.nome_razaosocial
            dias = (timezone.now() - o.data_entrada_estagio).days
            resultado += f'  - {nome} ({o.estagio.nome}, {dias} dias)\n'

    if not resultado.strip():
        resultado = 'Dia tranquilo! Nenhuma tarefa, atraso ou oportunidade parada.'

    return resultado


def ver_comandos(tenant, usuario, args):
    """Lista todos os comandos disponiveis do assistente."""
    return """Comandos disponiveis:

1. Consultar lead - "Busca o lead Maria"
2. Listar oportunidades - "Minhas oportunidades" ou "Oportunidades em negociacao"
3. Mover oportunidade - "Move Maria para Proposta Enviada"
4. Criar nota - "Anota no Joao: cliente pediu desconto"
5. Criar tarefa - "Cria tarefa: ligar pro Joao amanha"
6. Atualizar lead - "Atualiza email do Joao para joao@email.com"
7. Resumo pipeline - "Como esta meu pipeline?"
8. Listar tarefas - "Minhas tarefas de hoje" ou "Tarefas da semana"
9. Proxima tarefa - "Qual minha proxima tarefa?"
10. Agendar follow-up - "Me lembra de ligar pro Joao sexta 14h"
11. Ver historico - "O que rolou com a Maria?"
12. Marcar perda - "Perdi o Joao, foi pro concorrente"
13. Marcar ganho - "Fechei a Maria!"
14. Agenda do dia - "Como esta meu dia?"
15. Ver comandos - "Quais comandos tenho?"

Dica: voce pode falar naturalmente, nao precisa usar os comandos exatos."""


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
    'agendar_followup': {
        'func': agendar_followup,
        'description': 'Agenda um follow-up (tarefa de retorno) para um lead com data e horario',
        'parameters': {
            'type': 'object',
            'properties': {
                'lead': {'type': 'string', 'description': 'Nome do lead'},
                'quando': {'type': 'string', 'description': 'Quando: hoje, amanha, sexta, segunda, semana. Pode incluir horario (ex: sexta 14h)'},
                'observacao': {'type': 'string', 'description': 'Observacao sobre o follow-up (opcional)'},
            },
            'required': ['lead', 'quando'],
        },
    },
    'buscar_historico': {
        'func': buscar_historico,
        'description': 'Mostra o historico de um lead: estagio atual, ultimas notas e tarefas',
        'parameters': {
            'type': 'object',
            'properties': {
                'lead': {'type': 'string', 'description': 'Nome do lead'},
            },
            'required': ['lead'],
        },
    },
    'marcar_perda': {
        'func': marcar_perda,
        'description': 'Marca uma oportunidade como perdida com motivo',
        'parameters': {
            'type': 'object',
            'properties': {
                'lead': {'type': 'string', 'description': 'Nome do lead'},
                'motivo': {'type': 'string', 'description': 'Motivo da perda (ex: foi pro concorrente, sem budget)'},
            },
            'required': ['lead'],
        },
    },
    'marcar_ganho': {
        'func': marcar_ganho,
        'description': 'Marca uma oportunidade como ganha (venda fechada)',
        'parameters': {
            'type': 'object',
            'properties': {
                'lead': {'type': 'string', 'description': 'Nome do lead'},
            },
            'required': ['lead'],
        },
    },
    'agenda_do_dia': {
        'func': agenda_do_dia,
        'description': 'Resumo completo do dia do vendedor: tarefas de hoje, tarefas atrasadas e oportunidades paradas ha mais de 3 dias',
        'parameters': {
            'type': 'object',
            'properties': {},
            'required': [],
        },
    },
    'ver_comandos': {
        'func': ver_comandos,
        'description': 'Lista todos os comandos e exemplos disponiveis do assistente. Use quando o usuario pedir ajuda ou quiser saber o que pode fazer.',
        'parameters': {
            'type': 'object',
            'properties': {},
            'required': [],
        },
    },
}
