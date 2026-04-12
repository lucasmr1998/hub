# ============================================================================
# apps/comercial/leads/views.py
# Migrado de vendas_web/views.py — Sub-phase 3F
# ============================================================================
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import datetime, timedelta
import json
import traceback
import logging

from apps.sistema.decorators import api_token_required
from apps.sistema.utils import auditar
from apps.sistema.utils import (
    _parse_json_request,
    _model_field_names,
    _serialize_instance,
    _apply_updates,
    _criar_log_sistema,
    _parse_bool,
    _safe_ordering,
)

from .models import LeadProspecto, ImagemLeadProspecto, Prospecto, HistoricoContato, CampoCustomizado

logger = logging.getLogger(__name__)


# ============================================================================
# VIEWS DE PÁGINA
# ============================================================================

@login_required(login_url='sistema:login')
def leads_view(request):
    """View para a página de gerenciamento de leads"""
    context = {
        'user': request.user
    }
    return render(request, 'comercial/leads/leads.html', context)


@login_required(login_url='sistema:login')
@login_required(login_url='sistema:login')
@require_http_methods(["PUT"])
def api_lead_editar(request, lead_id):
    """API para editar campos do lead inline."""
    try:
        lead = LeadProspecto.objects.get(id=lead_id)
    except LeadProspecto.DoesNotExist:
        return JsonResponse({'error': 'Lead nao encontrado'}, status=404)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    campos_editaveis = [
        'nome_razaosocial', 'email', 'telefone', 'cpf_cnpj', 'cidade', 'estado',
        'cep', 'rua', 'numero_residencia', 'bairro', 'ponto_referencia',
        'empresa', 'data_nascimento', 'observacoes', 'origem', 'status_api',
    ]

    campos_atualizados = []
    for campo, valor in data.items():
        if campo in campos_editaveis and hasattr(lead, campo):
            setattr(lead, campo, valor)
            campos_atualizados.append(campo)

    if campos_atualizados:
        lead.save(update_fields=campos_atualizados)
        from apps.sistema.utils import registrar_acao
        registrar_acao('leads', 'editar', 'lead', lead.id,
                       f'Campos atualizados: {", ".join(campos_atualizados)}', request=request)

    return JsonResponse({'success': True, 'campos': campos_atualizados})


@login_required(login_url='sistema:login')
def lead_detail_view(request, lead_id):
    """View para a página de detalhes de um lead"""
    try:
        lead = LeadProspecto.objects.get(id=lead_id)
    except LeadProspecto.DoesNotExist:
        raise Http404("Lead não encontrado")

    # Buscar imagens do lead
    imagens = ImagemLeadProspecto.objects.filter(lead=lead).order_by('-data_criacao')

    # Buscar histórico de contatos
    historicos = HistoricoContato.objects.filter(lead=lead).order_by('-data_hora_contato')

    # Campos customizados do tenant
    campos_custom = CampoCustomizado.objects.filter(ativo=True).order_by('ordem', 'nome')
    dados_custom = lead.dados_custom or {}

    # Conversas do Inbox
    from apps.inbox.models import Conversa
    conversas_inbox = Conversa.objects.filter(lead=lead).select_related('canal').order_by('-ultima_mensagem_em')

    context = {
        'lead': lead,
        'imagens': imagens,
        'historicos': historicos,
        'campos_custom': campos_custom,
        'dados_custom': dados_custom,
        'conversas_inbox': conversas_inbox,
    }
    return render(request, 'comercial/leads/lead_detail.html', context)


@login_required(login_url='sistema:login')
def historico_detail_view(request, historico_id):
    """View para a página de detalhes de um histórico de contato"""
    try:
        historico = HistoricoContato.objects.select_related('lead').get(id=historico_id)
    except HistoricoContato.DoesNotExist:
        raise Http404("Histórico não encontrado")

    # Buscar conversas e mensagens do inbox associadas ao lead
    conversas = []
    mensagens = []
    if historico.lead:
        from apps.inbox.models import Conversa, Mensagem
        conversas = Conversa.objects.filter(lead=historico.lead).order_by('-ultima_mensagem_em')
        # Buscar mensagens de todas as conversas do lead
        conversa_ids = conversas.values_list('id', flat=True)
        mensagens = Mensagem.objects.filter(conversa_id__in=conversa_ids).order_by('data_envio')

    context = {
        'h': historico,
        'lead': historico.lead,
        'conversas': conversas,
        'mensagens': mensagens,
    }
    return render(request, 'comercial/leads/historico_detail.html', context)


@login_required(login_url='sistema:login')
def campos_custom_view(request):
    """Pagina de configuracao dos campos customizaveis de leads"""
    campos = CampoCustomizado.objects.all().order_by('ordem', 'nome')
    return render(request, 'comercial/leads/campos_custom.html', {'campos': campos})


@login_required(login_url='sistema:login')
@csrf_exempt
@auditar('config', 'gerenciar', 'campo_custom')
def api_campos_custom(request):
    """API para criar e listar campos customizados"""
    if request.method == 'GET':
        campos = CampoCustomizado.objects.all().order_by('ordem', 'nome')
        result = []
        for c in campos:
            result.append({
                'id': c.id, 'nome': c.nome, 'slug': c.slug,
                'tipo': c.tipo, 'tipo_display': c.get_tipo_display(),
                'opcoes': c.opcoes, 'obrigatorio': c.obrigatorio,
                'ordem': c.ordem, 'ativo': c.ativo,
            })
        return JsonResponse({'campos': result})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            from django.utils.text import slugify
            nome = data.get('nome', '').strip()
            if not nome:
                return JsonResponse({'error': 'Nome e obrigatorio'}, status=400)
            slug = slugify(nome).replace('-', '_')
            # Garantir slug unico
            base_slug = slug
            counter = 1
            while CampoCustomizado.objects.filter(slug=slug).exists():
                slug = f"{base_slug}_{counter}"
                counter += 1
            campo = CampoCustomizado.objects.create(
                nome=nome,
                slug=slug,
                tipo=data.get('tipo', 'texto'),
                opcoes=data.get('opcoes', []),
                obrigatorio=data.get('obrigatorio', False),
                ordem=data.get('ordem', 0),
                ativo=True,
            )
            return JsonResponse({
                'id': campo.id, 'nome': campo.nome, 'slug': campo.slug,
                'tipo': campo.tipo, 'tipo_display': campo.get_tipo_display(),
                'opcoes': campo.opcoes, 'obrigatorio': campo.obrigatorio,
                'ordem': campo.ordem, 'ativo': campo.ativo,
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Metodo nao permitido'}, status=405)


@login_required(login_url='sistema:login')
@csrf_exempt
@auditar('config', 'gerenciar', 'campo_custom')
def api_campo_custom_detalhe(request, campo_id):
    """API para editar e deletar um campo customizado"""
    try:
        campo = CampoCustomizado.objects.get(id=campo_id)
    except CampoCustomizado.DoesNotExist:
        return JsonResponse({'error': 'Campo nao encontrado'}, status=404)

    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            if 'nome' in data:
                campo.nome = data['nome'].strip()
            if 'tipo' in data:
                campo.tipo = data['tipo']
            if 'opcoes' in data:
                campo.opcoes = data['opcoes']
            if 'obrigatorio' in data:
                campo.obrigatorio = data['obrigatorio']
            if 'ordem' in data:
                campo.ordem = data['ordem']
            if 'ativo' in data:
                campo.ativo = data['ativo']
            campo.save()
            return JsonResponse({
                'id': campo.id, 'nome': campo.nome, 'slug': campo.slug,
                'tipo': campo.tipo, 'tipo_display': campo.get_tipo_display(),
                'opcoes': campo.opcoes, 'obrigatorio': campo.obrigatorio,
                'ordem': campo.ordem, 'ativo': campo.ativo,
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    if request.method == 'DELETE':
        campo.delete()
        return JsonResponse({'ok': True})

    return JsonResponse({'error': 'Metodo nao permitido'}, status=405)


@login_required
@xframe_options_sameorigin
def visualizar_conversa_lead(request, lead_id):
    """Serve o HTML da conversa do atendimento gerado para um LeadProspecto."""
    import os

    try:
        lead = LeadProspecto.objects.get(id=lead_id)
    except LeadProspecto.DoesNotExist:
        raise Http404("Lead não encontrado")

    if not lead.html_conversa_path:
        raise Http404("Conversa não disponível para este lead")

    base_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        'media'
    )
    full_path = os.path.join(base_dir, lead.html_conversa_path)

    if not os.path.exists(full_path):
        raise Http404("Arquivo da conversa não encontrado")

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return HttpResponse(content, content_type='text/html; charset=utf-8')


@login_required
def visualizar_conversa_pdf(request, lead_id):
    """Gera e serve o PDF da conversa do atendimento para um LeadProspecto."""
    import os
    import logging
    from django.conf import settings

    try:
        lead = LeadProspecto.objects.get(id=lead_id)
    except LeadProspecto.DoesNotExist:
        raise Http404("Lead não encontrado")

    if not lead.html_conversa_path:
        raise Http404("Conversa HTML não disponível para este lead")

    base_dir = str(getattr(settings, 'BASE_DIR', os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))))
    media_root = getattr(settings, 'MEDIA_ROOT', None) or os.path.join(base_dir, 'media')

    caminho_html = os.path.join(media_root, lead.html_conversa_path)
    if not os.path.exists(caminho_html):
        raise Http404("Arquivo HTML da conversa não encontrado")

    # Verifica se já existe PDF em cache no disco
    pasta_pdf = os.path.join(media_root, 'conversas_pdf')
    os.makedirs(pasta_pdf, exist_ok=True)
    caminho_pdf = os.path.join(pasta_pdf, f'{lead.pk}_conversa.pdf')

    if not os.path.exists(caminho_pdf):
        try:
            logging.getLogger('weasyprint').setLevel(logging.ERROR)
            logging.getLogger('fontTools').setLevel(logging.ERROR)
            from weasyprint import HTML as WeasyHTML
            pdf_bytes = WeasyHTML(filename=caminho_html).write_pdf()
            # Corrige segundo comentário do weasyprint (%🖤) para padrão compatível
            pdf_bytes = pdf_bytes.replace(b'%\xf0\x9f\x96\xa4', b'%\xe2\xe3\xcf\xd3', 1)
            with open(caminho_pdf, 'wb') as f:
                f.write(pdf_bytes)
        except Exception as exc:
            logging.getLogger(__name__).error("Erro ao gerar PDF para lead %s: %s", lead_id, exc)
            raise Http404("Erro ao gerar PDF da conversa")

    with open(caminho_pdf, 'rb') as f:
        pdf_bytes = f.read()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="conversa_atendimento_{lead_id}.pdf"'
    return response


# ============================================================================
# APIs DE REGISTRO E ATUALIZAÇÃO — LEADS
# ============================================================================

@csrf_exempt
@api_token_required
def registrar_lead_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_lead_api',
            mensagem='Tentativa de registro com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    required = ['nome_razaosocial', 'telefone']
    missing = [f for f in required if not data.get(f)]
    if missing:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_lead_api',
            mensagem=f'Campos obrigatórios ausentes: {", ".join(missing)}',
            dados_extras={'dados_recebidos': data, 'campos_faltando': missing},
            request=request
        )
        return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)

    try:
        allowed = _model_field_names(LeadProspecto)
        payload = {k: v for k, v in data.items() if k in allowed}
        lead = LeadProspecto.objects.create(**payload)

        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='registrar_lead_api',
            mensagem=f'Lead registrado com sucesso - ID: {lead.id}',
            dados_extras={
                'lead_id': lead.id,
                'nome': lead.nome_razaosocial,
                'telefone': lead.telefone,
                'origem': lead.origem,
                'dados_enviados': data
            },
            request=request
        )

        from apps.sistema.utils import registrar_acao
        registrar_acao('leads', 'criar', 'lead', lead.id,
                       f'Lead criado: {lead.nome_razaosocial}', request=request,
                       dados_extras={'origem': lead.origem, 'telefone': lead.telefone})

        return JsonResponse({'success': True, 'id': lead.id, 'lead': _serialize_instance(lead)}, status=201)
    except Exception as e:
        # Log de erro
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_lead_api',
            mensagem=f'Erro ao registrar lead: {str(e)}',
            dados_extras={
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_enviados': data
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@api_token_required
@auditar('leads', 'editar', 'lead')
def atualizar_lead_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem='Tentativa de atualização com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    termo = data.get('termo_busca')
    busca = data.get('busca')
    if not termo or busca is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem='Parâmetros de busca faltando',
            dados_extras={'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Parâmetros obrigatórios: termo_busca e busca'}, status=400)

    try:
        qs = LeadProspecto.objects.filter(**{termo: busca})
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_lead_api',
            mensagem=f'Termo de busca inválido: {termo}',
            dados_extras={'termo': termo, 'busca': busca, 'erro': str(e)},
            request=request
        )
        return JsonResponse({'error': 'termo_busca inválido para LeadProspecto'}, status=400)

    count = qs.count()
    if count == 0:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem='Lead não encontrado',
            dados_extras={'termo': termo, 'busca': busca},
            request=request
        )
        return JsonResponse({'error': 'Registro não encontrado'}, status=404)

    if count > 1:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem=f'Múltiplos leads encontrados ({count})',
            dados_extras={'termo': termo, 'busca': busca, 'quantidade': count},
            request=request
        )
        return JsonResponse({'error': f'Múltiplos registros encontrados ({count}). Refine a busca.'}, status=400)

    lead = qs.first()
    updates = {k: v for k, v in data.items() if k not in ['termo_busca', 'busca']}
    if not updates:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_lead_api',
            mensagem='Nenhum campo para atualizar',
            dados_extras={'lead_id': lead.id, 'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Nenhum campo para atualizar informado'}, status=400)

    # Guardar valores antigos para o log
    valores_antigos = {}
    for campo in updates.keys():
        if hasattr(lead, campo):
            valores_antigos[campo] = getattr(lead, campo)

    try:
        _apply_updates(lead, updates)

        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='atualizar_lead_api',
            mensagem=f'Lead atualizado com sucesso - ID: {lead.id}',
            dados_extras={
                'lead_id': lead.id,
                'termo_busca': termo,
                'valor_busca': busca,
                'campos_atualizados': list(updates.keys()),
                'valores_antigos': valores_antigos,
                'valores_novos': updates
            },
            request=request
        )

        return JsonResponse({'success': True, 'id': lead.id, 'lead': _serialize_instance(lead)})
    except ValueError as ve:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_lead_api',
            mensagem=f'Erro de validação ao atualizar lead: {str(ve)}',
            dados_extras={
                'lead_id': lead.id,
                'erro': str(ve),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(ve)}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_lead_api',
            mensagem=f'Erro ao atualizar lead: {str(e)}',
            dados_extras={
                'lead_id': lead.id,
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================================
# APIs DE IMAGENS DE LEADS
# ============================================================================

@csrf_exempt
@api_token_required
def registrar_imagem_lead_api(request):
    """Adiciona uma ou mais imagens (URLs) a um LeadProspecto.

    POST JSON aceito:
      { "lead_id": 1, "link_url": "https://..." }
      ou
      { "lead_id": 1, "imagens": [ {"link_url": "https://...", "descricao": "..."}, ... ] }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    lead_id = data.get('lead_id')
    if not lead_id:
        return JsonResponse({'error': 'Campo obrigatório: lead_id'}, status=400)

    try:
        lead = LeadProspecto.objects.get(pk=lead_id)
    except LeadProspecto.DoesNotExist:
        return JsonResponse({'error': f'Lead #{lead_id} não encontrado'}, status=404)

    imagens_input = data.get('imagens')
    if imagens_input is None:
        link_url = data.get('link_url')
        if not link_url:
            return JsonResponse({'error': 'Informe link_url ou imagens[]'}, status=400)
        imagens_input = [{'link_url': link_url, 'descricao': data.get('descricao', '')}]

    criadas = []
    for item in imagens_input:
        url = item.get('link_url', '').strip() if isinstance(item, dict) else str(item).strip()
        if not url:
            continue
        descricao = item.get('descricao', '') if isinstance(item, dict) else ''
        img = ImagemLeadProspecto.objects.create(
            lead=lead,
            link_url=url,
            descricao=descricao,
        )
        criadas.append({
            'id': img.id,
            'link_url': img.link_url,
            'descricao': img.descricao,
            'data_criacao': img.data_criacao.isoformat(),
        })

    if not criadas:
        return JsonResponse({'error': 'Nenhuma imagem válida informada'}, status=400)

    return JsonResponse({
        'success': True,
        'lead_id': lead.id,
        'imagens_criadas': len(criadas),
        'imagens': criadas,
    }, status=201)


@csrf_exempt
@api_token_required
def listar_imagens_lead_api(request):
    """Lista imagens de um LeadProspecto.  GET ?lead_id=1"""
    lead_id = request.GET.get('lead_id')
    if not lead_id:
        return JsonResponse({'error': 'Parâmetro obrigatório: lead_id'}, status=400)

    imagens = ImagemLeadProspecto.objects.filter(lead_id=lead_id).order_by('-data_criacao')
    data = [{
        'id': img.id,
        'link_url': img.link_url,
        'descricao': img.descricao,
        'data_criacao': img.data_criacao.isoformat(),
    } for img in imagens]

    return JsonResponse({'lead_id': int(lead_id), 'total': len(data), 'imagens': data})


@csrf_exempt
@api_token_required
def deletar_imagem_lead_api(request):
    """Remove uma imagem pelo ID.  POST { "imagem_id": 1 }"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    imagem_id = data.get('imagem_id')
    if not imagem_id:
        return JsonResponse({'error': 'Campo obrigatório: imagem_id'}, status=400)

    try:
        img = ImagemLeadProspecto.objects.get(pk=imagem_id)
        img.delete()
        return JsonResponse({'success': True, 'message': f'Imagem #{imagem_id} removida'})
    except ImagemLeadProspecto.DoesNotExist:
        return JsonResponse({'error': f'Imagem #{imagem_id} não encontrada'}, status=404)


@csrf_exempt
@api_token_required
def imagens_por_cliente_api(request):
    """
    GET /api/leads/imagens/por-cliente/?cliente_hubsoft_id=<id>
    Retorna as imagens vinculadas ao lead relacionado ao ClienteHubsoft.
    """
    from apps.integracoes.models import ClienteHubsoft

    cliente_id = request.GET.get('cliente_hubsoft_id')
    if not cliente_id:
        return JsonResponse({'error': 'Parâmetro obrigatório: cliente_hubsoft_id'}, status=400)

    try:
        cliente = ClienteHubsoft.objects.select_related('lead').get(pk=cliente_id)
    except ClienteHubsoft.DoesNotExist:
        return JsonResponse({'error': 'Cliente não encontrado'}, status=404)

    lead = cliente.lead
    if not lead:
        return JsonResponse({'success': True, 'imagens': [], 'lead': None,
                             'message': 'Cliente sem lead relacionado'})

    imagens = ImagemLeadProspecto.objects.filter(lead=lead).order_by('-data_criacao')
    imagens_data = [
        {
            'id':                   img.pk,
            'link_url':             img.link_url,
            'descricao':            img.descricao,
            'status_validacao':     img.status_validacao,
            'observacao_validacao': img.observacao_validacao,
            'validado_por':         img.validado_por,
            'data_validacao':       img.data_validacao.isoformat() if img.data_validacao else None,
            'data_criacao':         img.data_criacao.isoformat(),
        }
        for img in imagens
    ]

    return JsonResponse({
        'success': True,
        'lead': {
            'id':                     lead.id,
            'nome':                   lead.nome_razaosocial,
            'documentacao_completa':  lead.documentacao_completa,
            'documentacao_validada':  lead.documentacao_validada,
        },
        'imagens': imagens_data,
        'total':   len(imagens_data),
    })


@csrf_exempt
@api_token_required
@auditar('leads', 'validar', 'imagem')
def validar_imagem_api(request):
    """
    POST /api/leads/imagens/validar/
    Body: { "imagem_id": 1, "acao": "aprovar"|"rejeitar", "observacao": "..." }
    Atualiza status_validacao da imagem.
    Quando TODAS as imagens do lead forem aprovadas -> documentacao_validada = True no lead.
    Quando QUALQUER imagem for rejeitada -> documentacao_validada = False no lead.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    imagem_id  = data.get('imagem_id')
    acao       = data.get('acao', '').strip().lower()
    observacao = data.get('observacao', '').strip()

    if not imagem_id:
        return JsonResponse({'error': 'Campo obrigatório: imagem_id'}, status=400)
    if acao not in ('aprovar', 'rejeitar'):
        return JsonResponse({'error': 'acao deve ser "aprovar" ou "rejeitar"'}, status=400)

    try:
        img = ImagemLeadProspecto.objects.select_related('lead').get(pk=imagem_id)
    except ImagemLeadProspecto.DoesNotExist:
        return JsonResponse({'error': f'Imagem #{imagem_id} não encontrada'}, status=404)

    novo_status = (ImagemLeadProspecto.STATUS_VALIDO
                   if acao == 'aprovar'
                   else ImagemLeadProspecto.STATUS_REJEITADO)

    usuario = request.user.get_full_name() or request.user.username

    img.status_validacao     = novo_status
    img.observacao_validacao = observacao
    img.data_validacao       = timezone.now()
    img.validado_por         = usuario
    img.save(update_fields=['status_validacao', 'observacao_validacao',
                             'data_validacao', 'validado_por'])

    # Atualizar flags de documentação no lead
    lead = img.lead
    todas_imagens = list(lead.imagens.values_list('status_validacao', flat=True))

    if todas_imagens:
        todas_validas   = all(s == ImagemLeadProspecto.STATUS_VALIDO    for s in todas_imagens)
        alguma_rejeitada = any(s == ImagemLeadProspecto.STATUS_REJEITADO for s in todas_imagens)

        lead.documentacao_validada = todas_validas
        if todas_validas:
            lead.data_documentacao_validada = timezone.now()
        elif alguma_rejeitada:
            lead.data_documentacao_validada = None
        lead.save(update_fields=['documentacao_validada', 'data_documentacao_validada'])

    return JsonResponse({
        'success':          True,
        'imagem_id':        img.pk,
        'status_validacao': img.status_validacao,
        'validado_por':     img.validado_por,
        'lead': {
            'id':                    lead.id,
            'documentacao_validada': lead.documentacao_validada,
        },
        'message': f'Imagem {"aprovada" if acao == "aprovar" else "rejeitada"} com sucesso',
    })


# ============================================================================
# APIs DE REGISTRO E ATUALIZAÇÃO — PROSPECTOS
# ============================================================================

@csrf_exempt
@api_token_required
def registrar_prospecto_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_prospecto_api',
            mensagem='Tentativa de registro com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    required = ['nome_prospecto']
    missing = [f for f in required if not data.get(f)]
    if missing:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_prospecto_api',
            mensagem=f'Campos obrigatórios ausentes: {", ".join(missing)}',
            dados_extras={'dados_recebidos': data, 'campos_faltando': missing},
            request=request
        )
        return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)

    try:
        allowed = _model_field_names(Prospecto)
        payload = {k: v for k, v in data.items() if k in allowed}
        # Resolver lead se vier como id simples
        if 'lead' in data and isinstance(data['lead'], int):
            payload['lead'] = LeadProspecto.objects.get(id=data['lead'])
        if 'lead_id' in data and isinstance(data['lead_id'], int):
            payload['lead_id'] = data['lead_id']
        prospecto = Prospecto.objects.create(**payload)

        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='registrar_prospecto_api',
            mensagem=f'Prospecto registrado com sucesso - ID: {prospecto.id}',
            dados_extras={
                'prospecto_id': prospecto.id,
                'nome': prospecto.nome_prospecto,
                'lead_id': prospecto.lead_id,
                'status': prospecto.status,
                'dados_enviados': data
            },
            request=request
        )

        return JsonResponse({'success': True, 'id': prospecto.id, 'prospecto': _serialize_instance(prospecto)}, status=201)
    except LeadProspecto.DoesNotExist:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_prospecto_api',
            mensagem='Lead informado não encontrado',
            dados_extras={'lead_id': data.get('lead') or data.get('lead_id')},
            request=request
        )
        return JsonResponse({'error': 'Lead informado não encontrado'}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_prospecto_api',
            mensagem=f'Erro ao registrar prospecto: {str(e)}',
            dados_extras={
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_enviados': data
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@api_token_required
def atualizar_prospecto_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem='Tentativa de atualização com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    termo = data.get('termo_busca')
    busca = data.get('busca')
    if not termo or busca is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem='Parâmetros de busca faltando',
            dados_extras={'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Parâmetros obrigatórios: termo_busca e busca'}, status=400)

    try:
        qs = Prospecto.objects.filter(**{termo: busca})
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_prospecto_api',
            mensagem=f'Termo de busca inválido: {termo}',
            dados_extras={'termo': termo, 'busca': busca, 'erro': str(e)},
            request=request
        )
        return JsonResponse({'error': 'termo_busca inválido para Prospecto'}, status=400)

    count = qs.count()
    if count == 0:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem='Prospecto não encontrado',
            dados_extras={'termo': termo, 'busca': busca},
            request=request
        )
        return JsonResponse({'error': 'Registro não encontrado'}, status=404)

    if count > 1:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem=f'Múltiplos prospectos encontrados ({count})',
            dados_extras={'termo': termo, 'busca': busca, 'quantidade': count},
            request=request
        )
        return JsonResponse({'error': f'Múltiplos registros encontrados ({count}). Refine a busca.'}, status=400)

    prospecto = qs.first()
    updates = {k: v for k, v in data.items() if k not in ['termo_busca', 'busca']}
    if not updates:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_prospecto_api',
            mensagem='Nenhum campo para atualizar',
            dados_extras={'prospecto_id': prospecto.id, 'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Nenhum campo para atualizar informado'}, status=400)

    # Guardar valores antigos para o log
    valores_antigos = {}
    for campo in updates.keys():
        if hasattr(prospecto, campo):
            valores_antigos[campo] = getattr(prospecto, campo)

    try:
        _apply_updates(prospecto, updates)

        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='atualizar_prospecto_api',
            mensagem=f'Prospecto atualizado com sucesso - ID: {prospecto.id}',
            dados_extras={
                'prospecto_id': prospecto.id,
                'termo_busca': termo,
                'valor_busca': busca,
                'campos_atualizados': list(updates.keys()),
                'valores_antigos': valores_antigos,
                'valores_novos': updates
            },
            request=request
        )

        return JsonResponse({'success': True, 'id': prospecto.id, 'prospecto': _serialize_instance(prospecto)})
    except ValueError as ve:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_prospecto_api',
            mensagem=f'Erro de validação ao atualizar prospecto: {str(ve)}',
            dados_extras={
                'prospecto_id': prospecto.id,
                'erro': str(ve),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(ve)}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_prospecto_api',
            mensagem=f'Erro ao atualizar prospecto: {str(e)}',
            dados_extras={
                'prospecto_id': prospecto.id,
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================================
# APIs DE REGISTRO E ATUALIZAÇÃO — HISTÓRICO DE CONTATOS
# ============================================================================

@csrf_exempt
@api_token_required
def registrar_historico_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_historico_api',
            mensagem='Tentativa de registro com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    required = ['telefone', 'status']
    missing = [f for f in required if not data.get(f)]
    if missing:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='registrar_historico_api',
            mensagem=f'Campos obrigatórios ausentes: {", ".join(missing)}',
            dados_extras={'dados_recebidos': data, 'campos_faltando': missing},
            request=request
        )
        return JsonResponse({'error': f'Campos obrigatórios ausentes: {", ".join(missing)}'}, status=400)

    try:
        allowed = _model_field_names(HistoricoContato)
        payload = {k: v for k, v in data.items() if k in allowed}
        if 'lead' in data and isinstance(data['lead'], int):
            payload['lead'] = LeadProspecto.objects.get(id=data['lead'])
        if 'lead_id' in data and isinstance(data['lead_id'], int):
            payload['lead_id'] = data['lead_id']
        contato = HistoricoContato.objects.create(**payload)

        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='registrar_historico_api',
            mensagem=f'Histórico de contato registrado com sucesso - ID: {contato.id}',
            dados_extras={
                'historico_id': contato.id,
                'telefone': contato.telefone,
                'status': contato.status,
                'lead_id': contato.lead_id,
                'dados_enviados': data
            },
            request=request
        )

        return JsonResponse({'success': True, 'id': contato.id, 'historico': _serialize_instance(contato)}, status=201)
    except LeadProspecto.DoesNotExist:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_historico_api',
            mensagem='Lead informado não encontrado',
            dados_extras={'lead_id': data.get('lead') or data.get('lead_id')},
            request=request
        )
        return JsonResponse({'error': 'Lead informado não encontrado'}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='registrar_historico_api',
            mensagem=f'Erro ao registrar histórico: {str(e)}',
            dados_extras={
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_enviados': data
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@api_token_required
def atualizar_historico_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = _parse_json_request(request)
    if data is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem='Tentativa de atualização com JSON inválido',
            dados_extras={'body': request.body.decode('utf-8', errors='ignore')[:500]},
            request=request
        )
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    termo = data.get('termo_busca')
    busca = data.get('busca')
    if not termo or busca is None:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem='Parâmetros de busca faltando',
            dados_extras={'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Parâmetros obrigatórios: termo_busca e busca'}, status=400)

    try:
        qs = HistoricoContato.objects.filter(**{termo: busca})
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_historico_api',
            mensagem=f'Termo de busca inválido: {termo}',
            dados_extras={'termo': termo, 'busca': busca, 'erro': str(e)},
            request=request
        )
        return JsonResponse({'error': 'termo_busca inválido para Histórico de Contato'}, status=400)

    count = qs.count()
    if count == 0:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem='Histórico não encontrado',
            dados_extras={'termo': termo, 'busca': busca},
            request=request
        )
        return JsonResponse({'error': 'Registro não encontrado'}, status=404)

    if count > 1:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem=f'Múltiplos históricos encontrados ({count})',
            dados_extras={'termo': termo, 'busca': busca, 'quantidade': count},
            request=request
        )
        return JsonResponse({'error': f'Múltiplos registros encontrados ({count}). Refine a busca.'}, status=400)

    contato = qs.first()
    updates = {k: v for k, v in data.items() if k not in ['termo_busca', 'busca']}
    if not updates:
        _criar_log_sistema(
            nivel='WARNING',
            modulo='atualizar_historico_api',
            mensagem='Nenhum campo para atualizar',
            dados_extras={'historico_id': contato.id, 'dados_recebidos': data},
            request=request
        )
        return JsonResponse({'error': 'Nenhum campo para atualizar informado'}, status=400)

    # Guardar valores antigos para o log
    valores_antigos = {}
    for campo in updates.keys():
        if hasattr(contato, campo):
            valores_antigos[campo] = getattr(contato, campo)

    try:
        _apply_updates(contato, updates)

        # Log de sucesso
        _criar_log_sistema(
            nivel='INFO',
            modulo='atualizar_historico_api',
            mensagem=f'Histórico atualizado com sucesso - ID: {contato.id}',
            dados_extras={
                'historico_id': contato.id,
                'termo_busca': termo,
                'valor_busca': busca,
                'campos_atualizados': list(updates.keys()),
                'valores_antigos': valores_antigos,
                'valores_novos': updates
            },
            request=request
        )

        return JsonResponse({'success': True, 'id': contato.id, 'historico': _serialize_instance(contato)})
    except ValueError as ve:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_historico_api',
            mensagem=f'Erro de validação ao atualizar histórico: {str(ve)}',
            dados_extras={
                'historico_id': contato.id,
                'erro': str(ve),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(ve)}, status=404)
    except Exception as e:
        _criar_log_sistema(
            nivel='ERROR',
            modulo='atualizar_historico_api',
            mensagem=f'Erro ao atualizar histórico: {str(e)}',
            dados_extras={
                'historico_id': contato.id,
                'erro': str(e),
                'traceback': traceback.format_exc(),
                'dados_tentados': updates
            },
            request=request
        )
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================================
# APIs DE VERIFICAÇÃO E RELACIONAMENTOS
# ============================================================================

@csrf_exempt
@api_token_required
def verificar_relacionamentos_api(request):
    """
    API para verificar e relacionar prospectos órfãos com leads baseado no id_hubsoft
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        # Log da verificação
        _criar_log_sistema('INFO', 'verificar_relacionamentos_api', 'Iniciando verificação de relacionamentos', request=request)

        relacionamentos_criados = 0

        # Buscar prospectos sem lead que tenham id_prospecto_hubsoft
        prospectos_sem_lead = Prospecto.objects.filter(
            lead__isnull=True,
            id_prospecto_hubsoft__isnull=False
        ).exclude(id_prospecto_hubsoft='')

        for prospecto in prospectos_sem_lead:
            id_hub = prospecto.id_prospecto_hubsoft.strip()
            if not id_hub:
                continue

            # Buscar lead correspondente
            lead = LeadProspecto.objects.filter(id_hubsoft=id_hub).first()
            if lead:
                # Relacionar prospecto com lead
                prospecto.lead = lead
                prospecto.save()
                relacionamentos_criados += 1

                # Log do relacionamento criado
                _criar_log_sistema(
                    'INFO',
                    'verificar_relacionamentos_api',
                    f'Relacionamento criado: Prospecto #{prospecto.id} → Lead #{lead.id}',
                    dados_extras={
                        'prospecto_id': prospecto.id,
                        'lead_id': lead.id,
                        'id_hubsoft': id_hub
                    },
                    request=request
                )

        # Buscar leads sem prospectos que tenham id_hubsoft
        leads_com_hubsoft = LeadProspecto.objects.filter(
            id_hubsoft__isnull=False
        ).exclude(id_hubsoft='')

        for lead in leads_com_hubsoft:
            id_hub = lead.id_hubsoft.strip()
            if not id_hub:
                continue

            # Buscar prospectos órfãos correspondentes
            prospectos_sem_lead = Prospecto.objects.filter(
                id_prospecto_hubsoft=id_hub,
                lead__isnull=True
            )

            if prospectos_sem_lead.exists():
                # Relacionar todos os prospectos encontrados
                count = prospectos_sem_lead.update(lead=lead)
                relacionamentos_criados += count

                # Log dos relacionamentos criados
                for prospecto in prospectos_sem_lead:
                    _criar_log_sistema(
                        'INFO',
                        'verificar_relacionamentos_api',
                        f'Relacionamento criado: Lead #{lead.id} → Prospecto #{prospecto.id}',
                        dados_extras={
                            'lead_id': lead.id,
                            'prospecto_id': prospecto.id,
                            'id_hubsoft': id_hub
                        },
                        request=request
                    )

        # Log final
        _criar_log_sistema(
            'INFO',
            'verificar_relacionamentos_api',
            f'Verificação concluída: {relacionamentos_criados} relacionamentos criados',
            dados_extras={'relacionamentos_criados': relacionamentos_criados},
            request=request
        )

        return JsonResponse({
            'success': True,
            'relacionamentos_criados': relacionamentos_criados,
            'message': f'Verificação concluída. {relacionamentos_criados} relacionamentos criados.'
        })

    except Exception as e:
        error_msg = str(e)
        _criar_log_sistema('ERROR', 'verificar_relacionamentos_api', f'Erro na verificação: {error_msg}', request=request)
        return JsonResponse({'error': f'Erro na verificação: {error_msg}'}, status=500)


# ============================================================================
# APIs DE CONSULTA (GET)
# ============================================================================

def consultar_leads_api(request):
    """API GET de consulta sobre LeadProspecto com filtros e paginação."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        per_page = max(1, min(per_page, 100))

        lead_id = request.GET.get('id')
        search = request.GET.get('search')
        origem = request.GET.get('origem')
        status_api = request.GET.get('status_api')
        ativo_param = request.GET.get('ativo')
        data_inicio = request.GET.get('data_inicio')  # formato YYYY-MM-DD
        data_fim = request.GET.get('data_fim')        # formato YYYY-MM-DD
        ordering = request.GET.get('ordering')

        qs = LeadProspecto.objects.all()

        if lead_id:
            qs = qs.filter(id=lead_id)
        else:
            if search:
                qs = qs.filter(
                    Q(nome_razaosocial__icontains=search) |
                    Q(email__icontains=search) |
                    Q(telefone__icontains=search) |
                    Q(empresa__icontains=search) |
                    Q(cpf_cnpj__icontains=search) |
                    Q(id_hubsoft__icontains=search)
                )

            if origem:
                qs = qs.filter(origem=origem)

            if status_api:
                qs = qs.filter(status_api=status_api)

            ativo = _parse_bool(ativo_param)
            if ativo is not None:
                qs = qs.filter(ativo=ativo)

            if data_inicio:
                try:
                    di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    qs = qs.filter(data_cadastro__date__gte=di)
                except ValueError:
                    pass

            if data_fim:
                try:
                    df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    qs = qs.filter(data_cadastro__date__lte=df)
                except ValueError:
                    pass

        allowed_order_fields = {'id', 'data_cadastro', 'data_atualizacao', 'nome_razaosocial', 'valor'}
        order_by = _safe_ordering(ordering, allowed_order_fields) or '-data_cadastro'
        qs = qs.order_by(order_by)

        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]

        results = []
        for item in items:
            data = _serialize_instance(item)
            # Enriquecimentos úteis
            data['valor_formatado'] = item.get_valor_formatado()
            data['origem_display'] = item.get_origem_display()
            data['status_api_display'] = item.get_status_api_display()
            data['dados_custom'] = item.dados_custom or {}
            results.append(data)

        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def consultar_historicos_api(request):
    """API GET de consulta sobre HistoricoContato com filtros e paginação."""
    if request.method != 'GET':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        per_page = max(1, min(per_page, 100))

        contato_id = request.GET.get('id')
        telefone = request.GET.get('telefone')
        lead_id = request.GET.get('lead_id')
        status = request.GET.get('status')
        sucesso_param = request.GET.get('sucesso')
        conv_lead_param = request.GET.get('converteu_lead')
        conv_venda_param = request.GET.get('converteu_venda')
        data_inicio = request.GET.get('data_inicio')  # YYYY-MM-DD
        data_fim = request.GET.get('data_fim')        # YYYY-MM-DD
        ordering = request.GET.get('ordering')

        qs = HistoricoContato.objects.select_related('lead')

        if contato_id:
            qs = qs.filter(id=contato_id)
        else:
            if telefone:
                qs = qs.filter(telefone__icontains=telefone)

            if lead_id:
                qs = qs.filter(lead_id=lead_id)

            if status:
                qs = qs.filter(status=status)

            sucesso = _parse_bool(sucesso_param)
            if sucesso is not None:
                qs = qs.filter(sucesso=sucesso)

            converteu_lead = _parse_bool(conv_lead_param)
            if converteu_lead is not None:
                qs = qs.filter(converteu_lead=converteu_lead)

            converteu_venda = _parse_bool(conv_venda_param)
            if converteu_venda is not None:
                qs = qs.filter(converteu_venda=converteu_venda)

            if data_inicio:
                try:
                    di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    qs = qs.filter(data_hora_contato__date__gte=di)
                except ValueError:
                    pass

            if data_fim:
                try:
                    df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    qs = qs.filter(data_hora_contato__date__lte=df)
                except ValueError:
                    pass

        allowed_order_fields = {'id', 'data_hora_contato', 'telefone', 'status'}
        order_by = _safe_ordering(ordering, allowed_order_fields) or '-data_hora_contato'
        qs = qs.order_by(order_by)

        total = qs.count()
        start = (page - 1) * per_page
        end = start + per_page
        items = qs[start:end]

        results = []
        for item in items:
            data = _serialize_instance(item)
            # Enriquecimentos úteis
            data['status_display'] = item.get_status_display()
            data['duracao_formatada'] = item.get_duracao_formatada()
            data['valor_venda_formatado'] = item.get_valor_venda_formatado() if item.valor_venda else None
            if item.lead:
                data['lead_info'] = {
                    'id': item.lead.id,
                    'nome_razaosocial': item.lead.nome_razaosocial,
                    'telefone': item.lead.telefone,
                    'empresa': item.lead.empresa,
                }
            results.append(data)

        return JsonResponse({
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page,
            'ordering': order_by,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIs DE VALIDAÇÃO DE VENDAS
# ============================================================================

def _atualizar_resultado_processamento(prospecto, novos_dados):
    """
    Atualiza o resultado_processamento de um prospecto de forma segura
    """
    if prospecto.resultado_processamento:
        if isinstance(prospecto.resultado_processamento, dict):
            prospecto.resultado_processamento.update(novos_dados)
        else:
            try:
                existing_data = json.loads(prospecto.resultado_processamento) if isinstance(prospecto.resultado_processamento, str) else {}
                existing_data.update(novos_dados)
                prospecto.resultado_processamento = existing_data
            except (json.JSONDecodeError, TypeError):
                prospecto.resultado_processamento = novos_dados
    else:
        prospecto.resultado_processamento = novos_dados


def aprovar_venda_api(request):
    """API para aprovar uma venda"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)

        prospecto_id = data.get('prospecto_id')
        observacoes = data.get('observacoes', '')

        if not prospecto_id:
            return JsonResponse({'error': 'ID do prospecto é obrigatório'}, status=400)

        if not observacoes.strip():
            return JsonResponse({'error': 'Observações da validação são obrigatórias'}, status=400)

        # Buscar prospecto
        prospecto = Prospecto.objects.get(id=prospecto_id)

        # Verificar se pode ser aprovado
        if prospecto.status not in ['processado', 'aguardando_validacao']:
            return JsonResponse({'error': 'Prospecto não pode ser aprovado neste status'}, status=400)

        # Atualizar status
        prospecto.status = 'validacao_aprovada'
        prospecto.save()

        # Criar registro de validação
        usuario_validacao = f"{request.user.username}" if request.user.is_authenticated else "Sistema"
        if request.user.is_authenticated and (request.user.first_name or request.user.last_name):
            usuario_validacao = f"{request.user.first_name} {request.user.last_name}".strip()

        validacao_data = {
            'observacoes': observacoes,
            'data_validacao': timezone.now().isoformat(),
            'status_validacao': 'aprovada',
            'usuario_validacao': usuario_validacao
        }

        # Atualizar resultado_processamento de forma segura
        _atualizar_resultado_processamento(prospecto, validacao_data)

        prospecto.save()

        from apps.sistema.utils import registrar_acao
        registrar_acao('leads', 'aprovar', 'prospecto', prospecto.id,
                       f'Venda aprovada: prospecto #{prospecto.id}', request=request)

        return JsonResponse({
            'success': True,
            'message': 'Venda aprovada com sucesso',
            'prospecto_id': prospecto.id,
            'novo_status': prospecto.status
        })

    except Prospecto.DoesNotExist:
        return JsonResponse({'error': 'Prospecto não encontrado'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


def rejeitar_venda_api(request):
    """API para rejeitar uma venda"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    try:
        data = json.loads(request.body)

        prospecto_id = data.get('prospecto_id')
        motivo_rejeicao = data.get('motivo_rejeicao', '')

        if not prospecto_id:
            return JsonResponse({'error': 'ID do prospecto é obrigatório'}, status=400)

        if not motivo_rejeicao.strip():
            return JsonResponse({'error': 'Motivo da rejeição é obrigatório'}, status=400)

        # Buscar prospecto
        prospecto = Prospecto.objects.get(id=prospecto_id)

        # Verificar se pode ser rejeitado
        if prospecto.status not in ['processado', 'aguardando_validacao']:
            return JsonResponse({'error': 'Prospecto não pode ser rejeitado neste status'}, status=400)

        # Atualizar status
        prospecto.status = 'validacao_rejeitada'
        prospecto.save()

        # Criar registro de rejeição
        usuario_validacao = f"{request.user.username}" if request.user.is_authenticated else "Sistema"
        if request.user.is_authenticated and (request.user.first_name or request.user.last_name):
            usuario_validacao = f"{request.user.first_name} {request.user.last_name}".strip()

        rejeicao_data = {
            'motivo_rejeicao': motivo_rejeicao,
            'data_validacao': timezone.now().isoformat(),
            'status_validacao': 'rejeitada',
            'usuario_validacao': usuario_validacao
        }

        # Atualizar resultado_processamento de forma segura
        _atualizar_resultado_processamento(prospecto, rejeicao_data)

        prospecto.save()

        from apps.sistema.utils import registrar_acao
        registrar_acao('leads', 'rejeitar', 'prospecto', prospecto.id,
                       f'Venda rejeitada: prospecto #{prospecto.id}. Motivo: {motivo_rejeicao[:100]}',
                       request=request, nivel='WARNING')

        return JsonResponse({
            'success': True,
            'message': 'Venda rejeitada',
            'prospecto_id': prospecto.id,
            'novo_status': prospecto.status
        })

    except Prospecto.DoesNotExist:
        return JsonResponse({'error': 'Prospecto não encontrado'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Dados JSON inválidos'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


# ============================================================================
# API PARA HISTÓRICO DE CONTATOS
# ============================================================================

def get_status_categoria(status):
    """Categoriza o status para facilitar a exibição"""
    categorias = {
        'fluxo_inicializado': 'inicio',
        'fluxo_finalizado': 'sucesso',
        'transferido_humano': 'transferencia',
        'convertido_lead': 'conversao',
        'venda_confirmada': 'venda',
        'chamada_perdida': 'problema',
        'ocupado': 'problema',
        'desligou': 'problema',
        'nao_atendeu': 'problema',
        'erro_sistema': 'erro',
        'timeout': 'erro'
    }
    return categorias.get(status, 'outros')


def historico_contatos_api(request):
    """API para buscar histórico de contatos por lead ID ou telefone"""
    try:
        lead_id = request.GET.get('lead_id')
        prospecto_id = request.GET.get('prospecto_id')
        telefone = request.GET.get('telefone')

        if not lead_id and not prospecto_id and not telefone:
            return JsonResponse({'error': 'É necessário fornecer lead_id, prospecto_id ou telefone'}, status=400)

        historicos_query = HistoricoContato.objects.select_related('lead')

        # Buscar por lead_id
        if lead_id:
            try:
                lead = LeadProspecto.objects.get(id=lead_id)
                historicos_query = historicos_query.filter(
                    Q(lead_id=lead_id) | Q(telefone=lead.telefone)
                )
            except LeadProspecto.DoesNotExist:
                return JsonResponse({'error': 'Lead não encontrado'}, status=404)

        # Buscar por prospecto_id
        elif prospecto_id:
            try:
                prospecto = Prospecto.objects.get(id=prospecto_id)
                if prospecto.lead:
                    historicos_query = historicos_query.filter(
                        Q(lead_id=prospecto.lead.id) | Q(telefone=prospecto.lead.telefone)
                    )
                else:
                    # Se o prospecto não tem lead, buscar por nome semelhante (se houver telefone)
                    return JsonResponse({'historicos': [], 'total': 0, 'info': 'Prospecto sem lead associado'})
            except Prospecto.DoesNotExist:
                return JsonResponse({'error': 'Prospecto não encontrado'}, status=404)

        # Buscar por telefone
        elif telefone:
            historicos_query = historicos_query.filter(telefone=telefone)

        # Ordenar por data mais recente
        historicos = historicos_query.order_by('-data_hora_contato')[:50]  # Limitar a 50 registros mais recentes

        historicos_data = []
        for historico in historicos:
            # Formatar duração
            duracao_formatada = 'N/A'
            if historico.duracao_segundos:
                minutos = historico.duracao_segundos // 60
                segundos = historico.duracao_segundos % 60
                duracao_formatada = f"{minutos}m {segundos}s" if minutos > 0 else f"{segundos}s"

            # Status formatado
            status_info = {
                'status': historico.status,
                'display': historico.get_status_display(),
                'categoria': get_status_categoria(historico.status)
            }

            # Dados completos do lead relacionado
            lead_data = None
            if historico.lead:
                lead_data = {
                    'id': historico.lead.id,
                    'nome': historico.lead.nome_razaosocial,
                    'nome_razaosocial': historico.lead.nome_razaosocial,
                    'email': historico.lead.email,
                    'telefone': historico.lead.telefone,
                    'empresa': historico.lead.empresa or '',
                    'cpf_cnpj': historico.lead.cpf_cnpj or '',
                    'rg': historico.lead.rg or '',
                    'endereco': historico.lead.endereco or '',
                    'rua': historico.lead.rua or '',
                    'numero_residencia': historico.lead.numero_residencia or '',
                    'bairro': historico.lead.bairro or '',
                    'cidade': historico.lead.cidade or '',
                    'estado': historico.lead.estado or '',
                    'cep': historico.lead.cep or '',
                    'ponto_referencia': historico.lead.ponto_referencia or '',
                    'valor': historico.lead.get_valor_formatado(),
                    'valor_numerico': float(historico.lead.valor) if historico.lead.valor else 0,
                    'id_plano_rp': historico.lead.id_plano_rp,
                    'id_dia_vencimento': historico.lead.id_dia_vencimento,
                    'id_vendedor_rp': historico.lead.id_vendedor_rp,
                    'data_nascimento': historico.lead.data_nascimento.isoformat() if historico.lead.data_nascimento else '',
                    'origem': historico.lead.get_origem_display(),
                    'status_api': historico.lead.get_status_api_display(),
                    'id_hubsoft': historico.lead.id_hubsoft or '',
                    'observacoes': historico.lead.observacoes or ''
                }

            historico_item = {
                'id': historico.id,
                'data_hora': historico.data_hora_contato.isoformat() if historico.data_hora_contato else None,
                'status': status_info,
                'telefone': historico.telefone or '',
                'nome_contato': historico.nome_contato or 'Não identificado',
                'duracao': duracao_formatada,
                'duracao_segundos': historico.duracao_segundos or 0,
                'transcricao': historico.transcricao[:200] + '...' if historico.transcricao and len(historico.transcricao) > 200 else (historico.transcricao or ''),
                'transcricao_completa': historico.transcricao or '',
                'observacoes': historico.observacoes or '',
                'protocolo_atendimento': historico.protocolo_atendimento or '',
                'codigo_atendimento': historico.codigo_atendimento or '',
                'id_conta': historico.id_conta or '',
                'numero_conta': historico.numero_conta or '',
                'ultima_mensagem': historico.ultima_mensagem or '',
                'ip_origem': historico.ip_origem or '',
                'user_agent': historico.user_agent or '',
                'origem_contato': historico.get_origem_contato_display() if historico.origem_contato else '',
                'converteu_lead': historico.converteu_lead,
                'converteu_venda': historico.converteu_venda,
                'sucesso': historico.sucesso,
                'lead': lead_data
            }

            historicos_data.append(historico_item)

        # Estatísticas do histórico
        total_contatos = len(historicos_data)
        contatos_convertidos = sum(1 for h in historicos_data if h['converteu_lead'])
        vendas_convertidas = sum(1 for h in historicos_data if h['converteu_venda'])

        data = {
            'historicos': historicos_data,
            'total': total_contatos,
            'estatisticas': {
                'total_contatos': total_contatos,
                'contatos_convertidos': contatos_convertidos,
                'vendas_convertidas': vendas_convertidas,
                'taxa_conversao_lead': (contatos_convertidos / total_contatos * 100) if total_contatos > 0 else 0,
                'taxa_conversao_venda': (vendas_convertidas / total_contatos * 100) if total_contatos > 0 else 0
            }
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)


# ============================================================================
# IMPORTAÇÃO DE LEADS VIA CSV
# ============================================================================

CAMPOS_IMPORTAVEIS = [
    ('nome_razaosocial', 'Nome / Razão Social', True),
    ('telefone', 'Telefone', True),
    ('email', 'Email', False),
    ('cpf_cnpj', 'CPF/CNPJ', False),
    ('empresa', 'Empresa', False),
    ('valor', 'Valor (R$)', False),
    ('origem', 'Origem', False),
    ('cidade', 'Cidade', False),
    ('estado', 'Estado (UF)', False),
    ('bairro', 'Bairro', False),
    ('cep', 'CEP', False),
    ('rua', 'Rua', False),
    ('numero_residencia', 'Número', False),
    ('observacoes', 'Observações', False),
    ('data_nascimento', 'Data de Nascimento', False),
]


@login_required
def importar_csv_view(request):
    """Página de importação de leads via CSV."""
    campos = [{'id': c[0], 'label': c[1], 'obrigatorio': c[2]} for c in CAMPOS_IMPORTAVEIS]
    import json as json_mod
    return render(request, 'comercial/leads/importar_csv.html', {'campos_json': json_mod.dumps(campos)})


@login_required
@require_http_methods(["POST"])
def api_importar_csv_preview(request):
    """Faz parse do CSV e retorna preview das primeiras linhas + colunas."""
    import csv
    import io

    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        return JsonResponse({'error': 'Nenhum arquivo enviado'}, status=400)

    if not arquivo.name.endswith('.csv'):
        return JsonResponse({'error': 'Formato inválido. Envie um arquivo .csv'}, status=400)

    if arquivo.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'Arquivo muito grande (máximo 10MB)'}, status=400)

    try:
        conteudo = arquivo.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            arquivo.seek(0)
            conteudo = arquivo.read().decode('latin-1')
        except Exception:
            return JsonResponse({'error': 'Não foi possível ler o arquivo.'}, status=400)

    # Auto-detectar delimitador
    primeira_linha = conteudo.split('\n')[0] if conteudo else ''
    delimiter = ';' if primeira_linha.count(';') > primeira_linha.count(',') else ','

    reader = csv.reader(io.StringIO(conteudo), delimiter=delimiter)
    linhas = list(reader)

    if len(linhas) < 2:
        return JsonResponse({'error': 'Arquivo vazio ou com apenas cabeçalho'}, status=400)

    colunas = linhas[0]
    preview = linhas[1:6]
    total_linhas = len(linhas) - 1

    request.session['csv_import_data'] = conteudo
    request.session['csv_import_delimiter'] = delimiter

    return JsonResponse({
        'success': True,
        'colunas': colunas,
        'preview': preview,
        'total_linhas': total_linhas,
    })


@login_required
@require_http_methods(["POST"])
def api_importar_csv_executar(request):
    """Executa a importação com o mapeamento definido."""
    import csv
    import io

    data = json.loads(request.body)
    mapeamento = data.get('mapeamento', {})
    criar_oportunidades = data.get('criar_oportunidades', False)

    if 'nome_razaosocial' not in mapeamento or 'telefone' not in mapeamento:
        return JsonResponse({'error': 'Mapeamento de Nome e Telefone é obrigatório'}, status=400)

    conteudo = request.session.get('csv_import_data')
    if not conteudo:
        return JsonResponse({'error': 'Dados do CSV expirados. Faça upload novamente.'}, status=400)

    delimiter = request.session.get('csv_import_delimiter', ';')
    reader = csv.reader(io.StringIO(conteudo), delimiter=delimiter)
    linhas = list(reader)

    if len(linhas) < 2:
        return JsonResponse({'error': 'Arquivo vazio'}, status=400)

    dados = linhas[1:]
    from .models import LeadProspecto

    tenant = request.tenant
    importados = 0
    duplicados = 0
    erros = []

    for i, linha in enumerate(dados, start=2):
        try:
            valores = {}
            for campo, idx in mapeamento.items():
                idx = int(idx)
                if idx < len(linha):
                    val = linha[idx].strip()
                    if val:
                        valores[campo] = val

            nome = valores.get('nome_razaosocial', '').strip()
            telefone = valores.get('telefone', '').strip()

            if not nome or not telefone:
                erros.append(f'Linha {i}: nome ou telefone vazio')
                continue

            if LeadProspecto.objects.filter(tenant=tenant, telefone=telefone).exists():
                duplicados += 1
                continue

            lead_data = {
                'tenant': tenant,
                'nome_razaosocial': nome,
                'telefone': telefone,
                'tipo_entrada': 'importacao',
                'canal_entrada': 'importacao',
                'origem': valores.get('origem', 'outros'),
                'status_api': 'processado',
            }

            for campo in ['email', 'cpf_cnpj', 'empresa', 'cidade', 'estado', 'bairro',
                          'cep', 'rua', 'numero_residencia', 'observacoes']:
                if campo in valores:
                    lead_data[campo] = valores[campo]

            if 'valor' in valores:
                try:
                    lead_data['valor'] = float(valores['valor'].replace(',', '.').replace('R$', '').strip())
                except (ValueError, AttributeError):
                    pass

            if 'data_nascimento' in valores:
                from datetime import datetime as dt
                for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        lead_data['data_nascimento'] = dt.strptime(valores['data_nascimento'], fmt).date()
                        break
                    except ValueError:
                        continue

            lead = LeadProspecto(**lead_data)
            lead._skip_notificacao = True
            lead.save()
            importados += 1

            if criar_oportunidades:
                try:
                    from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio
                    estagio = PipelineEstagio.objects.filter(tenant=tenant, ativo=True).order_by('ordem').first()
                    if estagio and not hasattr(lead, 'oportunidade_crm'):
                        OportunidadeVenda.objects.create(
                            tenant=tenant, lead=lead, estagio=estagio,
                            titulo=nome, origem_crm='importacao',
                            valor_estimado=lead_data.get('valor'),
                        )
                except Exception:
                    pass

        except Exception as e:
            erros.append(f'Linha {i}: {str(e)[:80]}')

    request.session.pop('csv_import_data', None)
    request.session.pop('csv_import_delimiter', None)

    return JsonResponse({
        'success': True,
        'importados': importados,
        'duplicados': duplicados,
        'erros': erros[:50],
        'total_processado': len(dados),
    })
