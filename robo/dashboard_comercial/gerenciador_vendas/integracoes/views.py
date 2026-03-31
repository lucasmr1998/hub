from django.db.models import Q, Count
from django.http import JsonResponse

from .models import ClienteHubsoft, ServicoClienteHubsoft
from apps.comercial.leads.models import ImagemLeadProspecto, LeadProspecto


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
