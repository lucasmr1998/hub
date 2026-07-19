import logging

from django.db.models import Q, Count
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import ClienteHubsoft, ServicoClienteHubsoft
from vendas_web.models import ImagemLeadProspecto, LeadProspecto

logger = logging.getLogger(__name__)


def _servico_para_dict(s):
    """Serializa ServicoClienteHubsoft para JSON."""
    return {
        'id': s.id,
        'id_cliente_servico': s.id_cliente_servico,
        'nome': s.nome,
        'valor': float(s.valor) if s.valor else 0,
        'status': s.status,
        'status_prefixo': s.status_prefixo,
        'tecnologia': s.tecnologia,
        'velocidade_download': s.velocidade_download,
        'velocidade_upload': s.velocidade_upload,
        'login': s.login,
        'senha': s.senha,
        'mac_addr': s.mac_addr,
        'ipv4': s.ipv4 or '',
        'data_habilitacao': s.data_habilitacao.isoformat() if s.data_habilitacao else '',
        'data_venda': s.data_venda,
        'data_inicio_contrato': s.data_inicio_contrato,
        'data_fim_contrato': s.data_fim_contrato,
        'vigencia_meses': s.vigencia_meses,
        'vendedor_nome': s.vendedor_nome,
        'vendedor_email': s.vendedor_email,
        'data_cancelamento': s.data_cancelamento.isoformat() if s.data_cancelamento else '',
        'motivo_cancelamento': s.motivo_cancelamento,
    }


def _lead_para_dict_resumo(lead):
    """Campos principais do lead para APIs externas."""
    if not lead:
        return None
    return {
        'id': lead.id,
        'nome_razaosocial': lead.nome_razaosocial or '',
        'email': lead.email or '',
        'telefone': lead.telefone or '',
        'cpf_cnpj': lead.cpf_cnpj or '',
        'origem': lead.origem or '',
        'status_api': lead.status_api or '',
        'id_hubsoft': lead.id_hubsoft or '',
        'id_origem': lead.id_origem or '',
        'valor': float(lead.valor) if lead.valor is not None else 0,
        'data_cadastro': lead.data_cadastro.isoformat() if lead.data_cadastro else '',
        'documentacao_validada': bool(lead.documentacao_validada),
        'contrato_aceito': bool(getattr(lead, 'contrato_aceito', False)),
        'data_aceite_contrato': (
            lead.data_aceite_contrato.isoformat()
            if getattr(lead, 'data_aceite_contrato', None) else ''
        ),
        'cidade': lead.cidade or '',
        'estado': lead.estado or '',
        'cep': lead.cep or '',
    }


def _cliente_hubsoft_para_dict(c, incluir_lead_docs=True):
    """Serializa ClienteHubsoft + serviços (+ resumo docs do lead se houver)."""
    servicos_data = [_servico_para_dict(s) for s in c.servicos.all()]

    lead_data = None
    if c.lead and incluir_lead_docs:
        imagens = list(
            ImagemLeadProspecto.objects.filter(lead=c.lead)
            .values('status_validacao', 'data_criacao', 'data_validacao')
        )
        total_imgs = len(imagens)
        aprovados = sum(1 for i in imagens if i['status_validacao'] == ImagemLeadProspecto.STATUS_VALIDO)
        rejeitados = sum(1 for i in imagens if i['status_validacao'] == ImagemLeadProspecto.STATUS_REJEITADO)
        pendentes = total_imgs - aprovados - rejeitados
        datas_pendentes = [
            i['data_criacao'].isoformat()
            for i in imagens
            if i['status_validacao'] not in (
                ImagemLeadProspecto.STATUS_VALIDO,
                ImagemLeadProspecto.STATUS_REJEITADO,
            )
        ]
        data_pendente_mais_antiga = min(datas_pendentes) if datas_pendentes else None
        lead_data = {
            'id': c.lead.id,
            'nome_razaosocial': c.lead.nome_razaosocial or '',
            'telefone': c.lead.telefone or '',
            'email': c.lead.email or '',
            'status_api': c.lead.status_api or '',
            'id_hubsoft': c.lead.id_hubsoft or '',
            'documentacao_validada': c.lead.documentacao_validada,
            'url_pdf_conversa': c.lead.url_pdf_conversa or '',
            'html_conversa_path': c.lead.html_conversa_path or '',
            'docs': {
                'total': total_imgs,
                'aprovados': aprovados,
                'rejeitados': rejeitados,
                'pendentes': pendentes,
                'data_pendente_mais_antiga': data_pendente_mais_antiga,
            },
        }

    return {
        'id': c.id,
        'id_cliente': c.id_cliente,
        'uuid_cliente': c.uuid_cliente,
        'codigo_cliente': c.codigo_cliente,
        'nome_razaosocial': c.nome_razaosocial,
        'nome_fantasia': c.nome_fantasia,
        'tipo_pessoa': c.tipo_pessoa,
        'cpf_cnpj': c.cpf_cnpj,
        'telefone_primario': c.telefone_primario,
        'telefone_secundario': c.telefone_secundario,
        'email_principal': c.email_principal,
        'email_secundario': c.email_secundario,
        'rg': c.rg,
        'data_nascimento': c.data_nascimento.isoformat() if c.data_nascimento else '',
        'nacionalidade': c.nacionalidade,
        'estado_civil': c.estado_civil,
        'genero': c.genero,
        'profissao': c.profissao,
        'nome_pai': c.nome_pai,
        'nome_mae': c.nome_mae,
        'ativo': c.ativo,
        'alerta': c.alerta,
        'alerta_mensagens': c.alerta_mensagens or [],
        'origem_cliente': c.origem_cliente,
        'id_externo': c.id_externo,
        'grupos': c.grupos or [],
        'data_cadastro_hubsoft': c.data_cadastro_hubsoft.isoformat() if c.data_cadastro_hubsoft else '',
        'data_atualizacao_hubsoft': c.data_atualizacao_hubsoft.isoformat() if c.data_atualizacao_hubsoft else '',
        'data_sync': c.data_sync.isoformat() if c.data_sync else '',
        'houve_alteracao': c.houve_alteracao,
        'historico_alteracoes': c.historico_alteracoes or [],
        'servicos': servicos_data,
        'lead': lead_data,
    }


def api_lead_hubsoft_status(request):
    """
    Consulta se o lead (ID interno Rob-Vendas) virou cliente no Hubsoft.

    GET ?lead_id=<int>

    Resposta:
      - eh_cliente_hubsoft: true se existir ClienteHubsoft vinculado (FK lead)
      - lead: dados principais do LeadProspecto
      - cliente_hubsoft: espelho local do cliente Hubsoft (ou null)
      - servicos: lista com id_cliente_servico e demais campos de cada serviço
    """
    if request.method != 'GET':
        return JsonResponse({'success': False, 'error': 'Use GET'}, status=405)

    raw = request.GET.get('lead_id', '').strip()
    if not raw:
        return JsonResponse({
            'success': False,
            'error': 'Informe o parâmetro lead_id (ex: ?lead_id=123)',
        }, status=400)

    try:
        lead_pk = int(raw)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'lead_id inválido'}, status=400)

    try:
        lead = LeadProspecto.objects.get(pk=lead_pk)
    except LeadProspecto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Lead não encontrado'}, status=404)

    cliente = (
        ClienteHubsoft.objects.prefetch_related('servicos')
        .select_related('lead')
        .filter(lead_id=lead_pk)
        .first()
    )

    servicos = [_servico_para_dict(s) for s in cliente.servicos.all()] if cliente else []
    cliente_dict = _cliente_hubsoft_para_dict(cliente) if cliente else None

    return JsonResponse({
        'success': True,
        'lead_id': lead_pk,
        'eh_cliente_hubsoft': cliente is not None,
        'lead': _lead_para_dict_resumo(lead),
        'cliente_hubsoft': cliente_dict,
        'servicos': servicos,
    })


def api_clientes_hubsoft(request):
    """API que retorna clientes Hubsoft com seus serviços para a página de vendas."""
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        search = request.GET.get('search', '').strip()
        status_servico = request.GET.get('status_servico', '').strip()
        ativo_filter = request.GET.get('ativo', '').strip()
        cliente_id = request.GET.get('id', '').strip()
        lead_id = request.GET.get('lead_id', '').strip()

        qs = ClienteHubsoft.objects.prefetch_related('servicos').select_related('lead')

        if cliente_id:
            qs = qs.filter(pk=cliente_id)
        elif lead_id:
            try:
                qs = qs.filter(lead_id=int(lead_id))
            except ValueError:
                return JsonResponse({'error': 'lead_id inválido'}, status=400)
        else:
            if search:
                qs = qs.filter(
                    Q(nome_razaosocial__icontains=search) |
                    Q(cpf_cnpj__icontains=search) |
                    Q(telefone_primario__icontains=search) |
                    Q(email_principal__icontains=search) |
                    Q(codigo_cliente__icontains=search) |
                    Q(servicos__login__icontains=search)
                ).distinct()

            if status_servico:
                qs = qs.filter(servicos__status_prefixo=status_servico).distinct()

            if ativo_filter:
                qs = qs.filter(ativo=(ativo_filter == 'true'))

        total = qs.count()
        start = (page - 1) * per_page
        clientes = qs.order_by('-data_cadastro_hubsoft', '-data_sync')[start:start + per_page]

        status_counts = {}
        all_servicos = ServicoClienteHubsoft.objects.values('status_prefixo', 'status').annotate(
            total=Count('id')
        )
        for item in all_servicos:
            if item['status_prefixo']:
                status_counts[item['status_prefixo']] = {
                    'label': item['status'],
                    'count': item['total'],
                }

        total_clientes = ClienteHubsoft.objects.count()
        total_ativos = ClienteHubsoft.objects.filter(ativo=True).count()
        total_servicos = ServicoClienteHubsoft.objects.count()
        total_com_alteracao = ClienteHubsoft.objects.filter(houve_alteracao=True).count()

        clientes_data = [_cliente_hubsoft_para_dict(c) for c in clientes]

        return JsonResponse({
            'clientes': clientes_data,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page if total else 0,
            'stats': {
                'total_clientes': total_clientes,
                'total_ativos': total_ativos,
                'total_servicos': total_servicos,
                'total_com_alteracao': total_com_alteracao,
                'status_servicos': status_counts,
            },
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# Atendimentos e Ordens de Serviço do Cliente Hubsoft
# ============================================================================

def _obter_cliente_hubsoft(request):
    """
    Resolve o ClienteHubsoft a partir de:
      - ?cliente_id=<pk local>
      - ?id_cliente=<id hubsoft>
      - ?lead_id=<pk lead>
    Retorna (cliente, erro_response). erro_response vem preenchido em caso de falha.
    """
    pk = request.GET.get('cliente_id')
    id_cliente_hub = request.GET.get('id_cliente')
    lead_id = request.GET.get('lead_id')

    try:
        if pk:
            cliente = ClienteHubsoft.objects.get(pk=int(pk))
        elif id_cliente_hub:
            cliente = ClienteHubsoft.objects.get(id_cliente=int(id_cliente_hub))
        elif lead_id:
            cliente = ClienteHubsoft.objects.filter(lead_id=int(lead_id)).first()
            if not cliente:
                return None, JsonResponse({'success': False, 'error': 'Lead sem ClienteHubsoft vinculado'}, status=404)
        else:
            return None, JsonResponse({
                'success': False,
                'error': 'Informe cliente_id, id_cliente ou lead_id',
            }, status=400)
    except (ValueError, ClienteHubsoft.DoesNotExist):
        return None, JsonResponse({'success': False, 'error': 'Cliente não encontrado'}, status=404)

    return cliente, None


def _sincronizar_hubsoft_cliente(cliente):
    """Dispara sincronização sob demanda de atendimentos/OS via API Hubsoft."""
    from .models import IntegracaoAPI
    from .services.hubsoft import HubsoftService

    integracao = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()
    if not integracao or not cliente.codigo_cliente:
        return None
    try:
        service = HubsoftService(integracao)
        return service.sincronizar_atendimentos_os(cliente)
    except Exception as exc:
        return {'erro': str(exc)}


def _atendimento_para_dict(a):
    return {
        'id_atendimento': a.id_atendimento,
        'protocolo': a.protocolo,
        'tipo_atendimento': a.tipo_atendimento,
        'status': a.status,
        'status_fechamento': a.status_fechamento,
        'motivo_fechamento': a.motivo_fechamento,
        'setor_responsavel': a.setor_responsavel,
        'usuario_abertura': a.usuario_abertura,
        'usuario_responsavel': a.usuario_responsavel,
        'usuario_fechamento': a.usuario_fechamento,
        'descricao_abertura': a.descricao_abertura,
        'descricao_fechamento': a.descricao_fechamento,
        'data_cadastro': a.data_cadastro,
        'data_fechamento': a.data_fechamento,
        'qtd_ordens_servico': a.qtd_ordens_servico,
    }


def _os_para_dict(o):
    return {
        'id_ordem_servico': o.id_ordem_servico,
        'numero_ordem_servico': o.numero_ordem_servico,
        'tipo': o.tipo,
        'status': o.status,
        'status_fechamento': o.status_fechamento,
        'usuario_abertura': o.usuario_abertura,
        'usuario_fechamento': o.usuario_fechamento,
        'descricao_abertura': o.descricao_abertura,
        'descricao_servico': o.descricao_servico,
        'descricao_fechamento': o.descricao_fechamento,
        'data_cadastro': o.data_cadastro,
        'data_inicio_programado': o.data_inicio_programado,
        'data_termino_programado': o.data_termino_programado,
        'data_inicio_executado': o.data_inicio_executado,
        'data_termino_executado': o.data_termino_executado,
        'tecnicos': o.tecnicos or [],
        'qtd_anexos': o.qtd_anexos,
    }


def api_cliente_atendimentos(request):
    """
    GET /integracoes/api/cliente/atendimentos/?cliente_id=<pk>&sync=1
    Lê do banco local. Se sync=1, sincroniza do Hubsoft antes.
    """
    from .models import AtendimentoHubsoft

    cliente, err = _obter_cliente_hubsoft(request)
    if err:
        return err

    sync_info = None
    if request.GET.get('sync') in ('1', 'true'):
        sync_info = _sincronizar_hubsoft_cliente(cliente)

    atendimentos = AtendimentoHubsoft.objects.filter(cliente=cliente).order_by('-id_atendimento')
    lista = [_atendimento_para_dict(a) for a in atendimentos]

    return JsonResponse({
        'success': True,
        'cliente_id': cliente.pk,
        'id_cliente_hubsoft': cliente.id_cliente,
        'total': len(lista),
        'atendimentos': lista,
        'sync': sync_info,
    })


def api_cliente_ordens_servico(request):
    """
    GET /integracoes/api/cliente/ordens-servico/?cliente_id=<pk>&sync=1
    """
    from .models import OrdemServicoHubsoft

    cliente, err = _obter_cliente_hubsoft(request)
    if err:
        return err

    sync_info = None
    if request.GET.get('sync') in ('1', 'true'):
        sync_info = _sincronizar_hubsoft_cliente(cliente)

    ordens = OrdemServicoHubsoft.objects.filter(cliente=cliente).order_by('-id_ordem_servico')
    lista = [_os_para_dict(o) for o in ordens]

    return JsonResponse({
        'success': True,
        'cliente_id': cliente.pk,
        'id_cliente_hubsoft': cliente.id_cliente,
        'total': len(lista),
        'ordens_servico': lista,
        'sync': sync_info,
    })


def api_cliente_novos_servicos(request):
    """Retorna NewService(s) contratados via WhatsApp por este cliente Hubsoft.

    GET /integracoes/api/cliente/novos-servicos/?cliente_id=<pk>

    Match: por LeadProspecto.cpf_cnpj = ClienteHubsoft.cpf_cnpj. Inclui
    novos serviços em qualquer status — operador vê o histórico completo
    de contratações adicionais que o bot conduziu.
    """
    from vendas_web.models import NewService, LeadProspecto

    cliente, err = _obter_cliente_hubsoft(request)
    if err:
        return err

    cpf = (cliente.cpf_cnpj or '').strip()
    if not cpf:
        return JsonResponse({
            'success': True, 'cliente_id': cliente.pk,
            'total': 0, 'novos_servicos': [],
        })

    # Mapeia plano id_rp → label (espelho do que o bot usa)
    PLANOS_LABELS = {
        1647: ('Plano 300MB',      79.90),
        1648: ('Plano 1GB Turbo', 129.90),
        1649: ('Plano 620MB',      99.90),
        1650: ('Plano 2GB',       169.90),
    }
    DIAS_VENC = {28: 1, 9: 5, 5: 15, 6: 20}

    lead_ids = list(
        LeadProspecto.objects.filter(cpf_cnpj=cpf).values_list('id', flat=True)
    )
    qs = (
        NewService.objects
        .filter(lead_id__in=lead_ids)
        .select_related('lead')
        .prefetch_related('imagens')
        .order_by('-criado_em')
    )

    novos = []
    for ns in qs:
        plano_label, plano_valor_label = PLANOS_LABELS.get(ns.id_plano_rp, ('', None))
        # Endereço composto
        partes = []
        if ns.rua:
            partes.append(f'{ns.rua}' + (f', Nº {ns.numero_residencia}' if ns.numero_residencia else ''))
        if ns.bairro:
            partes.append(ns.bairro)
        if ns.cidade or ns.estado:
            partes.append(f'{ns.cidade}/{ns.estado}' if (ns.cidade and ns.estado) else (ns.cidade or ns.estado))
        if ns.cep:
            partes.append(f'CEP {ns.cep}')
        endereco_completo = ' - '.join(partes)

        # Imagens
        imagens = [{
            'id': img.id,
            'link_url': img.link_url,
            'descricao': img.descricao,
            'status_validacao': img.status_validacao,
            'data_criacao': img.data_criacao.isoformat() if img.data_criacao else None,
        } for img in ns.imagens.all()]

        novos.append({
            'id': ns.id,
            'lead_id': ns.lead_id,
            'status': ns.status,
            'status_display': ns.get_status_display(),
            'criado_em': ns.criado_em.isoformat() if ns.criado_em else None,
            'finalizado_em': ns.finalizado_em.isoformat() if ns.finalizado_em else None,
            # Plano
            'id_plano_rp': ns.id_plano_rp,
            'plano_label': plano_label or (str(ns.id_plano_rp) if ns.id_plano_rp else ''),
            'valor': float(ns.valor) if ns.valor is not None else plano_valor_label,
            'plano_confirmado': ns.plano_confirmado,
            'id_dia_vencimento': ns.id_dia_vencimento,
            'dia_vencimento': DIAS_VENC.get(ns.id_dia_vencimento),
            # Imóvel
            'tipo_imovel': ns.tipo_imovel,
            'tipo_residencia': ns.tipo_residencia,
            # Endereço
            'cep': ns.cep,
            'rua': ns.rua,
            'numero_residencia': ns.numero_residencia,
            'bairro': ns.bairro,
            'cidade': ns.cidade,
            'estado': ns.estado,
            'ponto_referencia': ns.ponto_referencia,
            'endereco_completo': endereco_completo,
            # Agendamento
            'turno_instalacao': ns.turno_instalacao,
            'data_instalacao': ns.data_instalacao.isoformat() if ns.data_instalacao else None,
            # Sync Matrix
            'matrix_sync_status': ns.matrix_sync_status,
            'matrix_sync_status_display': ns.get_matrix_sync_status_display(),
            'id_atendimento_matrix': ns.id_atendimento_matrix,
            'id_os_matrix': ns.id_os_matrix,
            'data_sync_matrix': ns.data_sync_matrix.isoformat() if ns.data_sync_matrix else None,
            'tentativas_sync_matrix': ns.tentativas_sync_matrix,
            'ultimo_erro_sync_matrix': ns.ultimo_erro_sync_matrix,
            # Confirmações
            'dados_confirmados': ns.dados_confirmados,
            'doc_selfie_recebida': ns.doc_selfie_recebida,
            'doc_frente_recebida': ns.doc_frente_recebida,
            'doc_verso_recebida':  ns.doc_verso_recebida,
            'imagens': imagens,
            'observacoes': ns.observacoes,
        })

    return JsonResponse({
        'success': True,
        'cliente_id': cliente.pk,
        'id_cliente_hubsoft': cliente.id_cliente,
        'cpf_cnpj': cpf,
        'total': len(novos),
        'novos_servicos': novos,
    })


# ────────────────────────────────────────────────────────────────────────
# AGENDAMENTO DE INSTALAÇÃO (fluxo IA / WhatsApp)
# ────────────────────────────────────────────────────────────────────────

@csrf_exempt
def api_agendar_instalacao_ia(request, lead_id):
    """Dispara o agendamento de instalação pro lead vindo do fluxo IA.

    POST /integracoes/api/agendar-instalacao-ia/<lead_id>/

    Lê turno_instalacao e data_instalacao já salvos no LeadProspecto (a API
    IA já preencheu nas etapas anteriores), e tenta executar via Matrix:
    consultar_agenda → abrir_atendimento → abrir_os.

    Retornos possíveis:
    - 200 {status: 'agendado',         dados: {horario, nome_tecnico, ...}}
    - 200 {status: 'aguardando_sync',  ...}  → worker reprocessa depois
    - 200 {status: 'erro',             mensagem: '...'}
    - 404 {status: 'erro', mensagem: 'lead não encontrado'}
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'erro', 'mensagem': 'Use POST'}, status=405)

    try:
        lead = LeadProspecto.objects.get(pk=lead_id)
    except LeadProspecto.DoesNotExist:
        return JsonResponse(
            {'status': 'erro', 'mensagem': f'Lead {lead_id} não encontrado'},
            status=404,
        )

    from integracoes.services.agendamento_ia import (
        AgendamentoIAError, criar_ou_obter_agendamento, executar_agendamento,
    )

    try:
        agendamento = criar_ou_obter_agendamento(lead)
    except AgendamentoIAError as e:
        return JsonResponse(
            {'status': 'erro', 'mensagem': str(e)},
            status=400,
        )

    # Idempotência: se já foi agendado antes, retorna direto
    if agendamento.status == 'agendado':
        return JsonResponse({
            'status': 'agendado',
            'mensagem': 'Já estava agendado',
            'agendamento_id': agendamento.pk,
            'dados': {
                'data': agendamento.data_instalacao.strftime('%d/%m/%Y'),
                'turno': agendamento.turno,
                'horario': agendamento.horario.strftime('%H:%M') if agendamento.horario else '',
                'nome_tecnico': agendamento.nome_tecnico,
            },
        })

    try:
        resultado = executar_agendamento(agendamento)
    except Exception as e:
        logger.exception('Falha inesperada agendamento_ia lead=%s', lead_id)
        return JsonResponse(
            {'status': 'erro', 'mensagem': str(e), 'agendamento_id': agendamento.pk},
            status=500,
        )

    return JsonResponse({
        **resultado,
        'agendamento_id': agendamento.pk,
    })


# ────────────────────────────────────────────────────────────────────────
# DETECÇÃO DE CLIENTE EXISTENTE (fluxo IA / WhatsApp)
# ────────────────────────────────────────────────────────────────────────

@csrf_exempt
def api_verificar_cliente_por_cpf(request, lead_id):
    """Verifica se o CPF do lead já é cliente no Hubsoft.

    POST /integracoes/api/verificar-cliente-cpf/<lead_id>/

    Estratégia em 2 etapas:
    1. **Detecção síncrona** (rápida): GET /api/v1/integracao/cliente?busca=cpf_cnpj
       direto na API Hubsoft. Se vier ao menos 1 cliente, marca o lead como
       'cliente_ativo' IMEDIATAMENTE. Resposta volta pro bot.
    2. **Sincronização em background** (best-effort): tenta criar/atualizar
       o ClienteHubsoft local com todos os dados. Se falhar (validação,
       campo faltando, etc), não impacta a detecção principal — o lead já
       foi marcado.

    Retorna:
      {status:'ok', eh_cliente: True,  nome: '...', cliente_hubsoft_id?: int}
      {status:'ok', eh_cliente: False, mensagem: '...'}
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'erro', 'mensagem': 'Use POST'}, status=405)

    try:
        lead = LeadProspecto.objects.get(pk=lead_id)
    except LeadProspecto.DoesNotExist:
        return JsonResponse(
            {'status': 'erro', 'mensagem': f'Lead {lead_id} não encontrado'},
            status=404,
        )

    if not lead.cpf_cnpj:
        return JsonResponse(
            {'status': 'erro', 'mensagem': 'Lead sem CPF — chame depois de coleta_cpf'},
            status=400,
        )

    from integracoes.models import IntegracaoAPI
    from integracoes.services.hubsoft import HubsoftService, HubsoftServiceError

    integ = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()
    if not integ:
        return JsonResponse(
            {'status': 'erro', 'mensagem': 'Integração Hubsoft não configurada'},
            status=500,
        )

    service = HubsoftService(integ)

    # ── 1) Detecção: apenas faz o GET na API Hubsoft ─────────────────
    try:
        resposta = service.consultar_cliente(lead.cpf_cnpj, lead=lead)
    except HubsoftServiceError as e:
        logger.warning('consultar_cliente lead=%s cpf=%s falhou: %s',
                       lead_id, lead.cpf_cnpj, e)
        return JsonResponse({
            'status': 'erro_api', 'mensagem': str(e),
            'eh_cliente': False,
        }, status=200)
    except Exception as e:
        logger.exception('consultar_cliente lead=%s erro inesperado', lead_id)
        return JsonResponse({
            'status': 'erro', 'mensagem': str(e),
            'eh_cliente': False,
        }, status=200)

    clientes = (resposta or {}).get('clientes') or []
    if not clientes:
        return JsonResponse({
            'status': 'ok',
            'eh_cliente': False,
            'mensagem': 'CPF não encontrado no Hubsoft',
        })

    # CPF encontrado — marca lead AGORA, antes de tentar criar ClienteHubsoft
    dados_cli = clientes[0] or {}
    nome_cli = dados_cli.get('nome_razaosocial') or ''
    id_cli_hubsoft = dados_cli.get('id_cliente')

    lead.status_api = 'cliente_ativo'
    lead.save(update_fields=['status_api', 'data_atualizacao'])
    logger.info('CPF %s identificado como cliente Hubsoft (lead=%s, id_cli=%s)',
                lead.cpf_cnpj, lead_id, id_cli_hubsoft)

    # ── 2) Sincronização best-effort: cria ClienteHubsoft local ───────
    # Se falhar (validação, etc), não afeta a detecção principal.
    cliente_local_pk = None
    try:
        cliente_local = service._sincronizar_dados_cliente(dados_cli, lead)
        cliente_local_pk = cliente_local.pk if cliente_local else None
    except Exception as e:
        logger.warning('Falha sincronizar ClienteHubsoft local lead=%s cpf=%s: %s',
                       lead_id, lead.cpf_cnpj, e)

    return JsonResponse({
        'status': 'ok',
        'eh_cliente': True,
        'cliente_hubsoft_id': cliente_local_pk,
        'id_cliente_hubsoft': id_cli_hubsoft,
        'nome': nome_cli,
    })


# Status do Hubsoft → label amigável pro cliente
STATUS_OS_LABELS = {
    'aguardando_aprovacao':    'Aguardando aprovação',
    'aguardando_agendamento':  'Aguardando agendamento',
    'agendado':                'Agendada',
    'aguardando_inicio':       'Aguardando início',
    'em_deslocamento':         'Técnico a caminho',
    'em_execucao':             'Em execução',
    'pausada':                 'Pausada',
    'aguardando_finalizacao':  'Aguardando finalização',
    'pendente':                'Pendente',
    # Status finais (exibidos quando OS já encerrou)
    'finalizada':              'Finalizada',
    'concluida':               'Concluída',
    'cancelada':               'Cancelada',
    'encerrada':               'Encerrada',
}

STATUS_OS_FINAIS = {'finalizada', 'concluida', 'cancelada', 'encerrada'}


def api_proxima_instalacao_lead(request, lead_id):
    """Retorna informações resumidas da OS de instalação em aberto do lead.

    GET /integracoes/api/lead/<lead_id>/proxima-instalacao/

    NÃO inclui nome de técnicos nem responsáveis.
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'erro', 'mensagem': 'Use GET'}, status=405)

    try:
        lead = LeadProspecto.objects.get(pk=lead_id)
    except LeadProspecto.DoesNotExist:
        return JsonResponse({'status': 'erro', 'mensagem': 'Lead não encontrado'}, status=404)

    # Cliente acabou de AGENDAR (escolheu data) — a OS pode ainda estar sendo
    # aberta (sync/agendamento em processamento). Sinaliza p/ o bot mostrar
    # "em processamento" em vez de "não encontrei + transbordo".
    agendou = bool(getattr(lead, 'data_instalacao', None))
    if not agendou:
        try:
            from integracoes.models import AgendamentoInstalacaoIA
            agendou = AgendamentoInstalacaoIA.objects.filter(
                lead_id=lead_id,
                status__in=['aguardando_sync', 'agendado']).exists()
        except Exception:
            pass
    data_inst_fmt = (lead.data_instalacao.strftime('%d/%m/%Y')
                     if getattr(lead, 'data_instalacao', None) else '')

    cliente = ClienteHubsoft.objects.filter(lead_id=lead_id).first()
    if not cliente:
        # Tenta achar pelo CPF mesmo sem FK
        if lead.cpf_cnpj:
            cliente = ClienteHubsoft.objects.filter(cpf_cnpj=lead.cpf_cnpj).first()

    if not cliente:
        return JsonResponse({
            'status': 'ok', 'tem_os': False,
            'agendou': agendou, 'data_instalacao': data_inst_fmt,
            'mensagem': 'Cliente Hubsoft não encontrado',
        })

    # ── Sincroniza OS em tempo real (best-effort) ─────────────────────
    # Sem isso, OS finalizada no Hubsoft pode aparecer como pendente
    # localmente até o sincronizador periódico rodar.
    try:
        from integracoes.models import IntegracaoAPI
        from integracoes.services.hubsoft import HubsoftService
        integ = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()
        if integ:
            HubsoftService(integ).sincronizar_atendimentos_os(cliente)
    except Exception as e:
        logger.warning('Pré-sync OS lead=%s falhou (segue com dados locais): %s',
                       lead_id, e)

    from integracoes.models import OrdemServicoHubsoft

    # Busca TODAS as OS de instalação do cliente (independente do serviço).
    # Filtra por tipo contendo 'INSTALAÇÃO' (case-insensitive). Cobre tipos
    # tipo 'B2C - INSTALAÇÃO', 'B2B - INSTALAÇÃO', etc.
    todas_oss = list(
        OrdemServicoHubsoft.objects
        .filter(cliente=cliente)
        .filter(tipo__icontains='INSTALA')
        .order_by('-data_inicio_programado', '-data_cadastro')
    )

    if not todas_oss:
        return JsonResponse({
            'status': 'ok', 'tem_os': False,
            'agendou': agendou, 'data_instalacao': data_inst_fmt,
            'mensagem': 'Nenhuma OS de instalação encontrada pra esse cliente',
        })

    # Endereço base do LeadProspecto (espelho do cadastro). Hoje todas as
    # OS herdam o mesmo endereço — quando o sistema gravar endereço por
    # OS no Hubsoft, dá pra puxar de os.dados_completos['endereco_*'].
    def _endereco_do_lead() -> str:
        partes = []
        rua = (lead.rua or '').strip()
        numero = (lead.numero_residencia or '').strip()
        bairro = (lead.bairro or '').strip()
        cidade = (lead.cidade or '').strip()
        estado = (lead.estado or '').strip()
        cep = (lead.cep or '').strip()
        if rua:
            partes.append(f'{rua}{(", Nº " + numero) if numero else ""}')
        if bairro:
            partes.append(bairro)
        if cidade or estado:
            partes.append(f'{cidade}/{estado}' if (cidade and estado) else (cidade or estado))
        if cep:
            partes.append(f'CEP {cep}')
        return ' - '.join(partes)

    endereco_base = _endereco_do_lead()

    # Endereço REAL de cada OS: cada OS está atrelada a um cliente_servico que tem
    # seu PRÓPRIO endereço de instalação no HubSoft. Sem isso, todas as OS herdavam
    # o endereço (único) do lead e apareciam IGUAIS no acompanhamento. Resolve do
    # banco do HubSoft por id_cliente_servico (vem em dados_completos['servico']).
    def _enderecos_reais_por_cs():
        ids = [cs for cs in (
            ((o.dados_completos or {}).get('servico') or {}).get('id_cliente_servico')
            for o in todas_oss) if cs]
        mapa = {}
        if not ids:
            return mapa
        try:
            from posvenda_hubsoft.services.ambiente import preparar_ambiente_webdriver
            preparar_ambiente_webdriver()
            from posvenda_hubsoft.webdriver.main_novo_servico import _conn
            conn = _conn('HUBSOFT')
            cur = conn.cursor()
            cur.execute(
                "SELECT cse.id_cliente_servico, en.endereco, en.numero, en.bairro, "
                "       ci.nome, est.sigla, en.cep "
                "FROM cliente_servico_endereco cse "
                "JOIN endereco_numero en ON en.id_endereco_numero = cse.id_endereco_numero "
                "LEFT JOIN cidade ci ON ci.id_cidade = en.id_cidade "
                "LEFT JOIN estado est ON est.id_estado = ci.id_estado "
                "WHERE cse.id_cliente_servico = ANY(%s) AND cse.tipo = 'instalacao'",
                [list(set(ids))])
            for cs, rua, num, bairro, cidade, uf, cep in cur.fetchall():
                partes = []
                if rua:
                    partes.append(f'{rua}{(", Nº " + str(num)) if num else ""}')
                if bairro:
                    partes.append(bairro)
                if cidade or uf:
                    partes.append(f'{cidade}/{uf}' if (cidade and uf) else (cidade or uf))
                if cep:
                    partes.append(f'CEP {cep}')
                mapa[cs] = ' - '.join(partes)
            conn.close()
        except Exception as e:
            logger.warning('Endereço real por OS lead=%s falhou (usa fallback): %s',
                           lead_id, e)
        return mapa

    enderecos_reais = _enderecos_reais_por_cs()

    def _endereco_da_os(os_obj):
        """Endereço de instalação ESPECÍFICO da OS (resolvido do cliente_servico no
        HubSoft); cai p/ dados_completos e, por fim, p/ o endereço do LeadProspecto."""
        dc = os_obj.dados_completos or {}
        cs = (dc.get('servico') or {}).get('id_cliente_servico')
        if cs and enderecos_reais.get(cs):
            return enderecos_reais[cs]
        # Tenta chaves comuns que o Hubsoft pode usar (raiz da OS)
        for key in ('endereco_instalacao', 'endereco', 'endereco_completo'):
            v = dc.get(key)
            if v and isinstance(v, str) and v.strip():
                return v.strip()
        # Tenta dentro de servico.referencia (raro mas possível)
        ref = ((dc.get('servico') or {}).get('referencia') or {})
        if isinstance(ref, dict):
            partes = []
            rua = (ref.get('logradouro') or ref.get('rua') or '').strip()
            num = (ref.get('numero') or '').strip()
            bairro = (ref.get('bairro') or '').strip()
            cidade = (ref.get('cidade') or '').strip()
            estado = (ref.get('estado') or ref.get('uf') or '').strip()
            cep = (ref.get('cep') or '').strip()
            if rua:
                partes.append(f'{rua}{(", Nº " + num) if num else ""}')
            if bairro:
                partes.append(bairro)
            if cidade or estado:
                partes.append(f'{cidade}/{estado}' if (cidade and estado) else (cidade or estado))
            if cep:
                partes.append(f'CEP {cep}')
            if partes:
                return ' - '.join(partes)
        return endereco_base

    def _nome_servico_da_os(os_obj):
        """Nome do plano/serviço vinculado à OS (ajuda a diferenciar várias OSs)."""
        dc = os_obj.dados_completos or {}
        servico = dc.get('servico') or {}
        return (servico.get('nome') or '').strip()

    oss_payload = []
    for os_obj in todas_oss:
        eh_final = os_obj.status in STATUS_OS_FINAIS
        oss_payload.append({
            'numero': os_obj.numero_ordem_servico,
            'tipo': os_obj.tipo or '',
            'data_programada': os_obj.data_inicio_programado or '',
            'data_termino_programado': os_obj.data_termino_programado or '',
            'data_termino_executado': os_obj.data_termino_executado or '',
            'status_raw': os_obj.status or '',
            'status_label': STATUS_OS_LABELS.get(
                os_obj.status, os_obj.status or 'Em processamento'
            ),
            'status_fechamento': os_obj.status_fechamento or '',
            'descricao_servico': os_obj.descricao_servico or '',
            'descricao_fechamento': os_obj.descricao_fechamento or '',
            'finalizada': eh_final,
            'endereco_instalacao': _endereco_da_os(os_obj),
            'nome_servico': _nome_servico_da_os(os_obj),
        })

    # Compat: também devolve `os` (singular) com a 1ª OS — clientes antigos
    # do endpoint que só leem `os` continuam funcionando.
    return JsonResponse({
        'status': 'ok', 'tem_os': True,
        'total': len(oss_payload),
        'oss': oss_payload,
        'os': oss_payload[0] if oss_payload else None,
    })


@csrf_exempt
def api_clube_indicacao_criar(request):
    """Recebe indicação do Clube de Benefícios (server-to-server).

    POST /integracoes/api/clube/indicacoes/criar/
    Body JSON: secret_key + campos do lead (mesmo formato de /crm/indicacoes/criar/).
    """
    import json

    from django.conf import settings

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'erro': 'Use POST'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'erro': 'JSON inválido'}, status=400)

    secret = (data.get('secret_key') or '').strip()
    expected = getattr(settings, 'CLUBE_WEBHOOK_SECRET', '').strip()
    if not expected or secret != expected:
        return JsonResponse({'ok': False, 'erro': 'Secret key inválida'}, status=403)

    from crm.views import criar_lead_indicacao

    try:
        lead, op = criar_lead_indicacao(data)
    except ValueError as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)
    except Exception as e:
        logger.exception('Falha ao criar indicação do Clube')
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)

    return JsonResponse({
        'ok': True,
        'lead_id': lead.id,
        'oportunidade_id': op.id if op else None,
    }, status=201)
