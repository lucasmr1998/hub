import json
import logging
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import IntegracaoAPI, LogIntegracao, ClienteHubsoft, ServicoClienteHubsoft, ClienteSGP
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

        tipos_ia = ['openai', 'anthropic', 'groq', 'google_ai']
        if not nome:
            return JsonResponse({'error': 'Nome e obrigatorio'}, status=400)
        if not base_url and tipo not in tipos_ia:
            return JsonResponse({'error': 'URL e obrigatoria'}, status=400)

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
            api_key=data.get('api_key', ''),
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
            # Para Uazapi: salvar token em configuracoes_extras (sem encriptacao)
            if integ.tipo == 'uazapi':
                extras = integ.configuracoes_extras or {}
                extras['token'] = data['access_token']
                integ.configuracoes_extras = extras
            else:
                integ.access_token = data['access_token']
        if 'api_key' in data:
            integ.api_key = data['api_key']
        if 'ativa' in data:
            integ.ativa = data['ativa']
        if 'configuracoes_extras' in data:
            novas_extras = data['configuracoes_extras'] or {}
            # Preservar token do Uazapi (salvo acima) se nao veio no JSON
            extras_atuais = integ.configuracoes_extras or {}
            if 'token' in extras_atuais and 'token' not in novas_extras:
                novas_extras['token'] = extras_atuais['token']
            integ.configuracoes_extras = novas_extras

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

        elif integ.tipo in ('openai', 'anthropic', 'groq', 'google_ai'):
            api_key = integ.api_key or integ.configuracoes_extras.get('api_key', '') or ''
            if not api_key:
                return JsonResponse({'success': False, 'message': 'API Key nao configurada.'})

            try:
                if integ.tipo == 'openai':
                    resp = http_requests.get(
                        'https://api.openai.com/v1/models',
                        headers={'Authorization': f'Bearer {api_key}'},
                        timeout=10,
                    )
                elif integ.tipo == 'anthropic':
                    resp = http_requests.post(
                        'https://api.anthropic.com/v1/messages',
                        headers={'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'},
                        json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 1, 'messages': [{'role': 'user', 'content': 'hi'}]},
                        timeout=10,
                    )
                elif integ.tipo == 'groq':
                    resp = http_requests.get(
                        'https://api.groq.com/openai/v1/models',
                        headers={'Authorization': f'Bearer {api_key}'},
                        timeout=10,
                    )
                else:
                    resp = http_requests.get(integ.base_url, timeout=10)

                if resp.status_code in (200, 201):
                    return JsonResponse({'success': True, 'message': f'{integ.get_tipo_display()} conectado. API Key valida.'})
                else:
                    return JsonResponse({'success': False, 'message': f'{integ.get_tipo_display()} retornou HTTP {resp.status_code}. Verifique a API Key.'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Erro de conexao: {e}'})

        else:
            try:
                resp = http_requests.get(integ.base_url, timeout=10)
                return JsonResponse({'success': True, 'message': f'URL respondeu com HTTP {resp.status_code}'})
            except Exception as e:
                return JsonResponse({'success': False, 'message': f'Erro: {e}'})

    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integração não encontrada'}, status=404)


# ============================================================================
# Pagina de detalhe (visualizacao + configuracao avancada por integracao)
# ============================================================================

@login_required
def integracao_detalhe(request, pk):
    """Pagina de detalhe + configuracao avancada de uma integracao."""
    try:
        integ = IntegracaoAPI.objects.get(pk=pk, tenant=request.tenant)
    except IntegracaoAPI.DoesNotExist:
        from django.http import Http404
        raise Http404('Integracao nao encontrada.')

    info = TIPO_INFO.get(integ.tipo, TIPO_INFO['outro'])
    integ.icon = info['icon']
    integ.cor = info['cor']
    integ.tipo_descricao = info['descricao']

    extras = integ.configuracoes_extras or {}
    cache = extras.get('cache') or {}

    catalogos = []
    if integ.tipo == 'sgp':
        from apps.comercial.crm.models import ProdutoServico, OpcaoVencimentoCRM
        catalogos = [
            {'chave': 'planos', 'label': 'Planos', 'icon': 'bi-box-seam',
             'total': ProdutoServico.objects.filter(tenant=integ.tenant, categoria='plano').count(),
             'destino': 'crm.ProdutoServico'},
            {'chave': 'vencimentos', 'label': 'Opcoes de vencimento', 'icon': 'bi-calendar',
             'total': OpcaoVencimentoCRM.objects.filter(tenant=integ.tenant).count(),
             'destino': 'crm.OpcaoVencimentoCRM'},
            {'chave': 'vendedores', 'label': 'Vendedores', 'icon': 'bi-person-badge',
             'total': len(cache.get('vendedores') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'pops', 'label': 'POPs', 'icon': 'bi-broadcast-pin',
             'total': len(cache.get('pops') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'portadores', 'label': 'Portadores financeiros', 'icon': 'bi-bank',
             'total': len(cache.get('portadores') or []),
             'destino': 'cache (configuracoes_extras)'},
        ]
    elif integ.tipo == 'hubsoft':
        from apps.comercial.crm.models import ProdutoServico, OpcaoVencimentoCRM
        catalogos = [
            {'chave': 'servicos', 'label': 'Planos / Servicos', 'icon': 'bi-box-seam',
             'total': ProdutoServico.objects.filter(tenant=integ.tenant, categoria='plano').count(),
             'destino': 'crm.ProdutoServico'},
            {'chave': 'vencimentos', 'label': 'Opcoes de vencimento', 'icon': 'bi-calendar',
             'total': OpcaoVencimentoCRM.objects.filter(tenant=integ.tenant).count(),
             'destino': 'crm.OpcaoVencimentoCRM'},
            {'chave': 'vendedores', 'label': 'Vendedores', 'icon': 'bi-person-badge',
             'total': len(cache.get('vendedores') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'origens_cliente', 'label': 'Origens de cliente', 'icon': 'bi-tag',
             'total': len(cache.get('origens_cliente') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'origens_contato', 'label': 'Origens de contato', 'icon': 'bi-chat-left',
             'total': len(cache.get('origens_contato') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'meios_pagamento', 'label': 'Meios de pagamento', 'icon': 'bi-credit-card',
             'total': len(cache.get('meios_pagamento') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'grupos_cliente', 'label': 'Grupos de cliente', 'icon': 'bi-people',
             'total': len(cache.get('grupos_cliente') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'motivos_contratacao', 'label': 'Motivos de contratacao', 'icon': 'bi-question-circle',
             'total': len(cache.get('motivos_contratacao') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'tipos_servico', 'label': 'Tipos de servico', 'icon': 'bi-list-ul',
             'total': len(cache.get('tipos_servico') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'servico_status', 'label': 'Status de servico', 'icon': 'bi-toggle-on',
             'total': len(cache.get('servico_status') or []),
             'destino': 'cache (configuracoes_extras)'},
            {'chave': 'servicos_tecnologia', 'label': 'Tecnologias de servico', 'icon': 'bi-broadcast',
             'total': len(cache.get('servicos_tecnologia') or []),
             'destino': 'cache (configuracoes_extras)'},
        ]

    defaults_sgp = {
        # Fixos (1 valor)
        'vendedor_id_padrao': extras.get('vendedor_id_padrao'),
        'portador_id_padrao': extras.get('portador_id_padrao'),
        'precadastro_ativar_padrao': extras.get('precadastro_ativar_padrao', 0),
        'pop_id_padrao': extras.get('pop_id_padrao'),  # TODO: derivar do CEP
        # Listas permitidas (multi)
        'planos_permitidos': extras.get('planos_permitidos') or [],
        'formas_cobranca_permitidas': extras.get('formas_cobranca_permitidas') or [],
        'dias_vencimento_permitidos': extras.get('dias_vencimento_permitidos') or [],
    }

    # Defaults HubSoft — usados como fallback quando o lead nao traz o id
    defaults_hubsoft = {
        # Fixos (1 valor)
        'plano_id_padrao': extras.get('plano_id_padrao'),
        'vendedor_id_padrao': extras.get('vendedor_id_padrao'),
        'dia_vencimento_id_padrao': extras.get('dia_vencimento_id_padrao'),
        'id_origem_padrao': extras.get('id_origem_padrao'),
        'id_origem_servico_padrao': extras.get('id_origem_servico_padrao'),
        # Listas permitidas (multi)
        'planos_permitidos_hubsoft': extras.get('planos_permitidos_hubsoft') or [],
        'dias_vencimento_permitidos_hubsoft': extras.get('dias_vencimento_permitidos_hubsoft') or [],
    }

    hubsoft_choices = {}
    if integ.tipo == 'hubsoft':
        from apps.comercial.crm.models import ProdutoServico, OpcaoVencimentoCRM
        hubsoft_choices = {
            'planos': [
                {'id': int(p.id_externo), 'label': p.nome}
                for p in ProdutoServico.objects.filter(
                    tenant=integ.tenant, categoria='plano', ativo=True,
                ).order_by('nome')
                if p.id_externo and p.id_externo.isdigit()
            ],
            'vendedores': [
                {'id': v.get('id'), 'label': v.get('name', '?')}
                for v in (cache.get('vendedores') or [])
                if v.get('id') is not None
            ],
            'vencimentos': [
                {'id': int(v.id_externo), 'label': f'Dia {v.dia}'}
                for v in OpcaoVencimentoCRM.objects.filter(
                    tenant=integ.tenant, ativo=True,
                ).order_by('dia')
                if v.id_externo and v.id_externo.isdigit()
            ],
            'origens_cliente': [
                {'id': o.get('id_origem_cliente'), 'label': o.get('descricao', '?')}
                for o in (cache.get('origens_cliente') or [])
                if o.get('id_origem_cliente') is not None
            ],
            # HubSoft expoe origens de contato (canal); o campo na API de prospecto
            # eh id_origem_servico — usamos a mesma lista cacheada como melhor proxy.
            'origens_servico': [
                {'id': o.get('id_origem_contato'), 'label': o.get('descricao', '?')}
                for o in (cache.get('origens_contato') or [])
                if o.get('id_origem_contato') is not None
            ],
        }

    sgp_choices = {}
    if integ.tipo == 'sgp':
        from apps.comercial.crm.models import ProdutoServico
        sgp_choices = {
            'planos': [
                {'id': p.codigo or p.id_externo, 'label': f'{p.nome} (R$ {p.preco})'}
                for p in ProdutoServico.objects.filter(tenant=integ.tenant, categoria='plano', ativo=True).order_by('nome')
                if (p.codigo or p.id_externo)
            ],
            'vendedores': [
                {'id': v.get('id'), 'label': v.get('nome', '?')}
                for v in (cache.get('vendedores') or [])
            ],
            'pops': [
                {'id': p.get('id'), 'label': p.get('pop', '?')}
                for p in (cache.get('pops') or [])
            ],
            'portadores': [
                {'id': p.get('id'), 'label': p.get('descricao', '?')}
                for p in (cache.get('portadores') or [])
            ],
            'formas_cobranca': [
                {'id': 1, 'label': 'Dinheiro'},
                {'id': 4, 'label': 'Cartao de Credito'},
                {'id': 6, 'label': 'PIX'},
                {'id': 3, 'label': 'Boleto'},
            ],
            'dias_vencimento': [{'id': d, 'label': f'Dia {d}'} for d in (5, 10, 15, 20, 25)],
        }

    if integ.tipo == 'sgp':
        features_relevantes = (
            'enviar_lead', 'sincronizar_cliente', 'sincronizar_servicos',
            'sincronizar_planos', 'sincronizar_vencimentos',
            'sincronizar_vendedores', 'sincronizar_pops', 'sincronizar_portadores',
        )
    elif integ.tipo == 'hubsoft':
        features_relevantes = (
            'enviar_lead', 'sincronizar_cliente', 'sincronizar_servicos',
            'sincronizar_planos', 'sincronizar_vencimentos', 'sincronizar_vendedores',
            'anexar_documentos_contrato', 'aceitar_contrato',
        )
    else:
        features_relevantes = tuple(IntegracaoAPI.SYNC_FEATURES.keys())

    modos_sync_view = [
        {
            'feature': f,
            'label': IntegracaoAPI.SYNC_FEATURES[f],
            'modo': integ.get_modo_sync(f),
        }
        for f in features_relevantes if f in IntegracaoAPI.SYNC_FEATURES
    ]

    desde_24h = timezone.now() - timedelta(hours=24)
    logs_recentes = integ.logs.order_by('-data_criacao')[:20]
    stats = {
        'chamadas_24h': integ.logs.filter(data_criacao__gte=desde_24h).count(),
        'erros_24h': integ.logs.filter(data_criacao__gte=desde_24h, sucesso=False).count(),
        'total_logs': integ.logs.count(),
        'clientes_sincronizados': (
            ClienteSGP.objects.filter(integracao=integ).count() if integ.tipo == 'sgp'
            else ClienteHubsoft.objects.filter(tenant=integ.tenant).count() if integ.tipo == 'hubsoft'
            else 0
        ),
    }

    return render(request, 'integracoes/integracao_detalhe.html', {
        'integracao': integ,
        'catalogos': catalogos,
        'defaults_sgp': defaults_sgp,
        'sgp_choices': sgp_choices,
        'defaults_hubsoft': defaults_hubsoft,
        'hubsoft_choices': hubsoft_choices,
        'modos_sync_view': modos_sync_view,
        'modos_disponiveis': IntegracaoAPI.SYNC_MODOS,
        'logs_recentes': logs_recentes,
        'stats': stats,
        'modulo_atual': 'configuracoes',
    })


@login_required
@require_http_methods(["POST"])
def api_integracao_defaults(request, pk):
    """Salva defaults da integracao em configuracoes_extras (SGP-style)."""
    try:
        integ = IntegracaoAPI.objects.get(pk=pk, tenant=request.tenant)
    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integracao nao encontrada'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    extras = dict(integ.configuracoes_extras or {})

    # Fixos: 1 inteiro (chaves SGP + HubSoft)
    chaves_int = (
        # SGP
        'vendedor_id_padrao', 'portador_id_padrao',
        'precadastro_ativar_padrao', 'pop_id_padrao',
        # HubSoft (vendedor_id_padrao ja entra acima)
        'plano_id_padrao', 'dia_vencimento_id_padrao',
        'id_origem_padrao', 'id_origem_servico_padrao',
    )
    for chave in chaves_int:
        if chave in data:
            valor = data[chave]
            if valor in (None, ''):
                extras.pop(chave, None)
            else:
                try:
                    extras[chave] = int(valor)
                except (TypeError, ValueError):
                    return JsonResponse({'error': f'{chave} deve ser inteiro.'}, status=400)

    # Listas permitidas: lista de inteiros
    chaves_lista = (
        # SGP
        'planos_permitidos', 'formas_cobranca_permitidas', 'dias_vencimento_permitidos',
        # HubSoft (chaves separadas pra nao colidir com SGP num tenant que use os dois)
        'planos_permitidos_hubsoft', 'dias_vencimento_permitidos_hubsoft',
    )
    for chave in chaves_lista:
        if chave in data:
            valor = data[chave]
            if valor in (None, '', []):
                extras.pop(chave, None)
            elif isinstance(valor, list):
                try:
                    extras[chave] = [int(v) for v in valor]
                except (TypeError, ValueError):
                    return JsonResponse({'error': f'{chave} deve ser lista de inteiros.'}, status=400)
            else:
                return JsonResponse({'error': f'{chave} deve ser lista.'}, status=400)

    integ.configuracoes_extras = extras
    integ.save(update_fields=['configuracoes_extras'])
    return JsonResponse({'success': True, 'message': 'Configuracao salva.', 'configuracoes_extras': extras})


@login_required
@require_http_methods(["POST"])
def api_integracao_sincronizar_catalogo(request, pk):
    """Sincroniza um catalogo do SGP sob demanda (botao 'sincronizar agora')."""
    try:
        integ = IntegracaoAPI.objects.get(pk=pk, tenant=request.tenant)
    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integracao nao encontrada'}, status=404)

    if integ.tipo not in ('sgp', 'hubsoft'):
        return JsonResponse({'error': 'Sincronizacao de catalogo so suportada em SGP e HubSoft.'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = {}
    chave = data.get('chave') or 'todos'

    if integ.tipo == 'sgp':
        permitidos = ('planos', 'vencimentos', 'vendedores', 'pops', 'portadores', 'todos')
        if chave not in permitidos:
            return JsonResponse({'error': f'chave invalida. Permitidos: {permitidos}'}, status=400)

        from apps.integracoes.services.sgp import SGPService, SGPServiceError
        svc = SGPService(integ)
        resumos = {}
        try:
            if chave in ('planos', 'todos'):
                resumos['planos'] = svc.sincronizar_planos()
            if chave in ('vencimentos', 'todos'):
                resumos['vencimentos'] = svc.sincronizar_vencimentos()
            if chave in ('vendedores', 'todos'):
                resumos['vendedores'] = svc.sincronizar_vendedores()
            if chave in ('pops', 'todos'):
                resumos['pops'] = svc.sincronizar_pops()
            if chave in ('portadores', 'todos'):
                resumos['portadores'] = svc.sincronizar_portadores()
        except SGPServiceError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=502)
        return JsonResponse({'success': True, 'resumos': resumos})

    # HubSoft
    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
    permitidos = (
        'todos', 'servicos', 'vencimentos',
        'vendedores', 'origens_cliente', 'origens_contato',
        'meios_pagamento', 'grupos_cliente', 'motivos_contratacao',
        'tipos_servico', 'servico_status', 'servicos_tecnologia',
    )
    if chave not in permitidos:
        return JsonResponse({'error': f'chave invalida. Permitidos: {permitidos}'}, status=400)

    svc = HubsoftService(integ)
    try:
        if chave == 'todos':
            resultado = svc.sincronizar_configuracoes()
            resumos = {k: v for k, v in resultado.items() if not k.startswith('_')}
        elif chave == 'servicos':
            resumos = {'servicos': svc.sincronizar_servicos_catalogo()}
        elif chave == 'vencimentos':
            resumos = {'vencimentos': svc.sincronizar_vencimentos()}
        else:
            resumos = {chave: svc.sincronizar_catalogo_cacheado(chave)}
    except HubsoftServiceError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=502)
    return JsonResponse({'success': True, 'resumos': resumos})


@login_required
@require_http_methods(["POST"])
def api_integracao_financeiro_sandbox(request, pk):
    """
    Sandbox de teste do financeiro HubSoft direto do painel da integracao.

    Body JSON:
      {
        "acao": "listar_faturas" | "listar_renegociacoes",
        "cpf_cnpj": "...",
        "apenas_pendente": true,   // listar_faturas
        "limit": 20,                // listar_faturas
        "data_inicio": "YYYY-MM-DD",  // listar_renegociacoes
        "data_fim": "YYYY-MM-DD"      // listar_renegociacoes
      }

    Nao escreve nada — so consulta. Pra simular/efetivar renegociacao,
    usar o fluxo do Inbox/Atendimento (ver inbox_acoes_hubsoft).
    """
    try:
        integ = IntegracaoAPI.objects.get(pk=pk, tenant=request.tenant)
    except IntegracaoAPI.DoesNotExist:
        return JsonResponse({'error': 'Integracao nao encontrada'}, status=404)

    if integ.tipo != 'hubsoft':
        return JsonResponse({'error': 'Sandbox financeiro so suportado em integracoes HubSoft.'}, status=400)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    acao = data.get('acao')
    cpf = (data.get('cpf_cnpj') or '').strip()

    # Acoes que nao usam cpf_cnpj — viabilidade por coords/endereco e operacionais por id
    acoes_sem_cpf = {
        'viabilidade_coords', 'viabilidade_endereco',
        'solicitar_desconexao', 'reset_mac', 'reset_phy',
        'desbloqueio_confianca', 'suspender', 'habilitar', 'ativar',
    }
    if not cpf and acao not in acoes_sem_cpf:
        return JsonResponse({'error': 'cpf_cnpj eh obrigatorio.'}, status=400)

    from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
    svc = HubsoftService(integ)

    try:
        if acao == 'listar_faturas':
            faturas = svc.listar_faturas_cliente(
                cpf_cnpj=cpf,
                apenas_pendente=bool(data.get('apenas_pendente', False)),
                limit=data.get('limit') or None,
            )
            return JsonResponse({'success': True, 'acao': acao, 'total': len(faturas), 'faturas': faturas})
        elif acao == 'listar_renegociacoes':
            resultado = svc.listar_renegociacoes(
                cpf_cnpj=cpf,
                data_inicio=data.get('data_inicio') or None,
                data_fim=data.get('data_fim') or None,
                pagina=int(data.get('pagina') or 0),
                itens_por_pagina=int(data.get('itens_por_pagina') or 50),
            )
            return JsonResponse({'success': True, 'acao': acao, **resultado})
        elif acao == 'extrato_conexao':
            # busca pode ser 'login', 'ipv4', 'ipv6_wan', 'ipv6_lan', 'mac'
            registros = svc.verificar_extrato_conexao(
                busca=data.get('busca') or 'login',
                termo_busca=cpf,  # aqui cpf vira o termo livre
                limit=int(data.get('limit') or 20),
                data_inicio=data.get('data_inicio') or None,
                data_fim=data.get('data_fim') or None,
            )
            return JsonResponse({'success': True, 'acao': acao, 'total': len(registros), 'registros': registros})
        elif acao == 'planos_por_cep':
            # cpf vira o cep aqui
            servicos = svc.listar_planos_por_cep(cep=cpf)
            return JsonResponse({'success': True, 'acao': acao, 'total': len(servicos), 'servicos': servicos})
        elif acao == 'listar_atendimentos':
            atendimentos = svc.listar_atendimentos_cliente(cpf_cnpj=cpf, limit=int(data.get('limit') or 20))
            return JsonResponse({'success': True, 'acao': acao, 'total': len(atendimentos), 'atendimentos': atendimentos})
        elif acao == 'listar_os':
            os_list = svc.listar_os_cliente(cpf_cnpj=cpf, limit=int(data.get('limit') or 20))
            return JsonResponse({'success': True, 'acao': acao, 'total': len(os_list), 'ordens_servico': os_list})
        elif acao == 'viabilidade_coords':
            r = svc.consultar_viabilidade_coords(
                latitude=float(data['latitude']), longitude=float(data['longitude']),
                raio=int(data.get('raio') or 250),
            )
            return JsonResponse({'success': True, 'acao': acao, 'resultado': r})
        elif acao == 'viabilidade_endereco':
            r = svc.consultar_viabilidade_endereco(
                endereco=data.get('endereco', ''), numero=data.get('numero', ''),
                bairro=data.get('bairro', ''), cidade=data.get('cidade', ''),
                estado=data.get('estado', ''), raio=int(data.get('raio') or 250),
            )
            return JsonResponse({'success': True, 'acao': acao, 'resultado': r})
        elif acao in {'solicitar_desconexao', 'reset_mac', 'reset_phy',
                      'desbloqueio_confianca', 'suspender', 'habilitar', 'ativar'}:
            id_cs = data.get('id_cliente_servico')
            if not id_cs:
                return JsonResponse({'error': 'id_cliente_servico obrigatorio.'}, status=400)
            id_cs = int(id_cs)
            if acao == 'solicitar_desconexao':
                r = svc.solicitar_desconexao(id_cs)
            elif acao == 'reset_mac':
                r = svc.reset_mac_addr(id_cs)
            elif acao == 'reset_phy':
                r = svc.reset_phy_addr(id_cs)
            elif acao == 'desbloqueio_confianca':
                r = svc.desbloqueio_confianca(id_cs, dias_desbloqueio=int(data.get('dias') or 1))
            elif acao == 'suspender':
                r = svc.suspender_servico(id_cs, tipo_suspensao=data.get('tipo_suspensao') or 'suspenso_debito')
            elif acao == 'habilitar':
                r = svc.habilitar_servico(id_cs, motivo_habilitacao=data.get('motivo') or 'Habilitado via Hubtrix sandbox.')
            else:  # ativar
                r = svc.ativar_servico(id_cs)
            return JsonResponse({'success': True, 'acao': acao, 'resposta': r})
        else:
            return JsonResponse({
                'error': 'acao invalida. Permitidos: listar_faturas, listar_renegociacoes, extrato_conexao, planos_por_cep, listar_atendimentos, listar_os, viabilidade_coords, viabilidade_endereco, solicitar_desconexao, reset_mac, reset_phy, desbloqueio_confianca, suspender, habilitar, ativar.'
            }, status=400)
    except HubsoftServiceError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=502)
