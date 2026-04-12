import json
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft
from apps.comercial.leads.models import ImagemLeadProspecto, LeadProspecto
from apps.sistema.decorators import user_tem_funcionalidade

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

        # TenantManager filtra automaticamente por tenant
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
# PÁGINA DE GERENCIAMENTO DE INTEGRAÇÕES
# ============================================================================

TIPO_INFO = {
    'hubsoft': {'icon': 'fas fa-server', 'cor': '#2563eb', 'descricao': 'ERP de gestão para provedores de internet'},
    'uazapi': {'icon': 'fab fa-whatsapp', 'cor': '#25D366', 'descricao': 'API de WhatsApp para envio e recebimento de mensagens'},
    'n8n': {'icon': 'fas fa-project-diagram', 'cor': '#ff6d5a', 'descricao': 'Plataforma de automação de fluxos e webhooks'},
    'outro': {'icon': 'fas fa-plug', 'cor': '#64748b', 'descricao': 'Integração customizada'},
}


@login_required
def integracoes_view(request):
    """Página de gerenciamento de integrações."""
    integracoes = IntegracaoAPI.objects.order_by('-ativa', 'nome')

    for integ in integracoes:
        info = TIPO_INFO.get(integ.tipo, TIPO_INFO['outro'])
        integ.icon = info['icon']
        integ.cor = info['cor']
        integ.tipo_descricao = info['descricao']
        integ.logs_recentes = integ.logs.order_by('-data_criacao')[:5]
        integ.total_chamadas_24h = integ.logs.filter(
            data_criacao__gte=timezone.now() - timedelta(hours=24)
        ).count()
        integ.erros_24h = integ.logs.filter(
            data_criacao__gte=timezone.now() - timedelta(hours=24),
            sucesso=False,
        ).count()

    tipos_disponiveis = IntegracaoAPI.TIPO_CHOICES

    return render(request, 'integracoes/integracoes.html', {
        'integracoes': integracoes,
        'tipos_disponiveis': tipos_disponiveis,
        'tipo_info': TIPO_INFO,
    })


@login_required
@require_http_methods(["POST"])
def api_integracao_criar(request):
    """Criar nova integração."""
    try:
        data = json.loads(request.body)
        nome = data.get('nome', '').strip()
        tipo = data.get('tipo', 'outro')
        base_url = data.get('base_url', '').strip()

        if not nome or not base_url:
            return JsonResponse({'error': 'Nome e URL são obrigatórios'}, status=400)

        integ = IntegracaoAPI.objects.create(
            tenant=request.tenant,
            nome=nome,
            tipo=tipo,
            base_url=base_url,
            client_id=data.get('client_id', ''),
            client_secret=data.get('client_secret', ''),
            username=data.get('username', ''),
            password=data.get('password', ''),
            access_token=data.get('access_token', ''),
            ativa=data.get('ativa', True),
            configuracoes_extras=data.get('configuracoes_extras', {}),
        )
        return JsonResponse({'success': True, 'id': integ.pk, 'message': f'Integração "{nome}" criada'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["PUT"])
def api_integracao_editar(request, pk):
    """Editar integração existente."""
    try:
        integ = IntegracaoAPI.objects.get(pk=pk)
        data = json.loads(request.body)

        if 'nome' in data:
            integ.nome = data['nome'].strip()
        if 'base_url' in data:
            integ.base_url = data['base_url'].strip()
        if 'tipo' in data:
            integ.tipo = data['tipo']
        if 'client_id' in data:
            integ.client_id = data['client_id']
        if 'client_secret' in data and data['client_secret']:
            integ.client_secret = data['client_secret']
        if 'username' in data:
            integ.username = data['username']
        if 'password' in data and data['password']:
            integ.password = data['password']
        if 'access_token' in data and data['access_token']:
            integ.access_token = data['access_token']
        if 'ativa' in data:
            integ.ativa = data['ativa']
        if 'configuracoes_extras' in data:
            integ.configuracoes_extras = data['configuracoes_extras']

        integ.save()
        return JsonResponse({'success': True, 'message': f'Integração "{integ.nome}" atualizada'})
    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integração não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def api_integracao_excluir(request, pk):
    """Excluir integração."""
    try:
        integ = IntegracaoAPI.objects.get(pk=pk)
        nome = integ.nome
        integ.delete()
        return JsonResponse({'success': True, 'message': f'Integração "{nome}" excluída'})
    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integração não encontrada'}, status=404)


@login_required
@require_http_methods(["POST"])
def api_integracao_toggle(request, pk):
    """Ativar/desativar integração."""
    try:
        integ = IntegracaoAPI.objects.get(pk=pk)
        integ.ativa = not integ.ativa
        integ.save(update_fields=['ativa'])
        return JsonResponse({'success': True, 'ativa': integ.ativa})
    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integração não encontrada'}, status=404)


@login_required
@require_http_methods(["POST"])
def api_integracao_modos_sync(request, pk):
    """Salvar modos de sincronização de uma integração."""
    try:
        integ = IntegracaoAPI.objects.get(pk=pk)
        data = json.loads(request.body)
        modos = data.get('modos_sync', {})

        for feature, modo in modos.items():
            if feature in IntegracaoAPI.SYNC_FEATURES and modo in IntegracaoAPI.SYNC_MODOS:
                integ.set_modo_sync(feature, modo)

        return JsonResponse({
            'success': True,
            'modos_sync': integ.modos_sync_dict,
            'message': 'Modos de sincronização atualizados.',
        })
    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integração não encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_integracao_modos_sync_get(request, pk):
    """Retorna os modos de sincronização de uma integração."""
    try:
        integ = IntegracaoAPI.objects.get(pk=pk)
        return JsonResponse({
            'success': True,
            'modos_sync': integ.modos_sync_dict,
            'features': {k: v for k, v in IntegracaoAPI.SYNC_FEATURES.items()},
            'modos_disponiveis': IntegracaoAPI.SYNC_MODOS,
        })
    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integração não encontrada'}, status=404)


@login_required
@require_http_methods(["POST"])
def api_integracao_testar(request, pk):
    """Testar conexão com a integração."""
    import requests as http_requests

    try:
        integ = IntegracaoAPI.objects.get(pk=pk)

        if integ.tipo == 'hubsoft':
            from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
            try:
                service = HubsoftService(integ)
                service.obter_token()
                return JsonResponse({'success': True, 'message': 'Conexão HubSoft OK. Token obtido com sucesso.'})
            except HubsoftServiceError as e:
                return JsonResponse({'success': False, 'message': f'Falha: {e}'})

        elif integ.tipo == 'uazapi':
            try:
                token = integ.configuracoes_extras.get('token', '') or integ.access_token or ''
                if not token:
                    return JsonResponse({'success': False, 'message': 'Token não configurado. Preencha o campo Token/API Key.'})
                resp = http_requests.get(
                    f"{integ.base_url.rstrip('/')}/instance/status",
                    headers={
                        'Accept': 'application/json',
                        'token': token,
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get('status', data.get('state', 'desconhecido'))
                    return JsonResponse({'success': True, 'message': f'Uazapi conectado. Status: {status}'})
                else:
                    return JsonResponse({'success': False, 'message': f'Uazapi retornou HTTP {resp.status_code}. Verifique o token.'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Erro de conexão: {e}'})

        elif integ.tipo == 'n8n':
            try:
                resp = http_requests.get(
                    f"{integ.base_url.rstrip('/')}/healthz",
                    timeout=10,
                )
                if resp.status_code == 200:
                    return JsonResponse({'success': True, 'message': 'N8N online e respondendo.'})
                else:
                    return JsonResponse({'success': False, 'message': f'N8N retornou HTTP {resp.status_code}'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Erro de conexão: {e}'})

        else:
            try:
                resp = http_requests.get(integ.base_url, timeout=10)
                return JsonResponse({'success': True, 'message': f'URL respondeu com HTTP {resp.status_code}'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Erro: {e}'})

    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integração não encontrada'}, status=404)
