# ============================================================================
# Views migradas de vendas_web.views (Phase 3A)
# ============================================================================
import json
import re
import unicodedata
import logging
import traceback
from decimal import Decimal

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.sistema.decorators import api_token_required, user_tem_funcionalidade
from apps.marketing.campanhas.models import CampanhaTrafego, DeteccaoCampanha
from apps.comercial.leads.models import LeadProspecto

logger = logging.getLogger(__name__)


# ============================================================================
# VIEWS DE PÁGINA
# ============================================================================

@login_required
def campanhas_trafego_view(request):
    """View para gerenciar campanhas de tráfego pago"""
    if not user_tem_funcionalidade(request, 'marketing.gerenciar_campanhas'):
        return JsonResponse({'error': 'Sem permissão'}, status=403)
    campanhas = CampanhaTrafego.objects.all().order_by('-ativa', 'ordem_exibicao', 'nome')

    # Calcular estatísticas gerais
    from django.db.models import Count, Sum
    total_campanhas = campanhas.count()
    campanhas_ativas = campanhas.filter(ativa=True).count()
    total_deteccoes = sum(c.contador_deteccoes for c in campanhas)
    total_leads = sum(c.total_leads for c in campanhas)

    return render(request, 'marketing/campanhas/campanhas.html', {
        'campanhas': campanhas,
        'total_campanhas': total_campanhas,
        'campanhas_ativas': campanhas_ativas,
        'total_deteccoes': total_deteccoes,
        'total_leads': total_leads,
    })


@login_required
def deteccoes_campanha_view(request):
    """View para visualizar detecções de campanhas"""
    # Filtros
    campanha_id = request.GET.get('campanha')
    aceita = request.GET.get('aceita')

    deteccoes = DeteccaoCampanha.objects.all().select_related('campanha', 'lead')

    if campanha_id:
        deteccoes = deteccoes.filter(campanha_id=campanha_id)
    if aceita is not None:
        deteccoes = deteccoes.filter(aceita=aceita == 'true')

    deteccoes = deteccoes.order_by('-detectado_em')[:100]  # Últimas 100

    campanhas = CampanhaTrafego.objects.filter(ativa=True).order_by('nome')

    return render(request, 'marketing/campanhas/deteccoes.html', {
        'deteccoes': deteccoes,
        'campanhas': campanhas,
    })


# ============================================================================
# APIS DE CAMPANHAS DE TRÁFEGO
# ============================================================================

@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_campanhas_trafego_gerencia(request):
    """API para gerenciar campanhas de tráfego pago"""
    try:
        if request.method == 'GET':
            campanhas = CampanhaTrafego.objects.all().order_by('-ativa', 'ordem_exibicao', 'nome')
            data = []
            for campanha in campanhas:
                data.append({
                    'id': campanha.id,
                    'nome': campanha.nome,
                    'codigo': campanha.codigo,
                    'descricao': campanha.descricao,
                    'palavra_chave': campanha.palavra_chave,
                    'tipo_match': campanha.tipo_match,
                    'case_sensitive': campanha.case_sensitive,
                    'plataforma': campanha.plataforma,
                    'tipo_trafego': campanha.tipo_trafego,
                    'prioridade': campanha.prioridade,
                    'ativa': campanha.ativa,
                    'data_inicio': campanha.data_inicio.strftime('%Y-%m-%d') if campanha.data_inicio else None,
                    'data_fim': campanha.data_fim.strftime('%Y-%m-%d') if campanha.data_fim else None,
                    'url_destino': campanha.url_destino,
                    'orcamento': float(campanha.orcamento) if campanha.orcamento else None,
                    'meta_leads': campanha.meta_leads,
                    'contador_deteccoes': campanha.contador_deteccoes,
                    'total_leads': campanha.total_leads,
                    'cor_identificacao': campanha.cor_identificacao,
                    'ordem_exibicao': campanha.ordem_exibicao,
                })
            return JsonResponse({'success': True, 'data': data})

        elif request.method == 'POST':
            data = json.loads(request.body)
            campanha = CampanhaTrafego.objects.create(
                nome=data.get('nome'),
                codigo=data.get('codigo'),
                descricao=data.get('descricao', ''),
                palavra_chave=data.get('palavra_chave'),
                tipo_match=data.get('tipo_match', 'parcial'),
                case_sensitive=data.get('case_sensitive', False),
                plataforma=data.get('plataforma'),
                tipo_trafego=data.get('tipo_trafego', ''),
                prioridade=data.get('prioridade', 5),
                ativa=data.get('ativa', True),
                data_inicio=data.get('data_inicio'),
                data_fim=data.get('data_fim'),
                url_destino=data.get('url_destino', ''),
                orcamento=data.get('orcamento'),
                meta_leads=data.get('meta_leads'),
                cor_identificacao=data.get('cor_identificacao', '#667eea'),
                ordem_exibicao=data.get('ordem_exibicao', 0),
                observacoes=data.get('observacoes', ''),
                criado_por=request.user
            )
            return JsonResponse({
                'success': True,
                'message': 'Campanha criada com sucesso!',
                'id': campanha.id
            })

        elif request.method == 'PUT':
            data = json.loads(request.body)
            campanha_id = data.get('id')
            campanha = CampanhaTrafego.objects.get(id=campanha_id)

            campanha.nome = data.get('nome', campanha.nome)
            campanha.descricao = data.get('descricao', campanha.descricao)
            campanha.palavra_chave = data.get('palavra_chave', campanha.palavra_chave)
            campanha.tipo_match = data.get('tipo_match', campanha.tipo_match)
            campanha.case_sensitive = data.get('case_sensitive', campanha.case_sensitive)
            campanha.plataforma = data.get('plataforma', campanha.plataforma)
            campanha.tipo_trafego = data.get('tipo_trafego', campanha.tipo_trafego)
            campanha.prioridade = data.get('prioridade', campanha.prioridade)
            campanha.ativa = data.get('ativa', campanha.ativa)
            campanha.data_inicio = data.get('data_inicio', campanha.data_inicio)
            campanha.data_fim = data.get('data_fim', campanha.data_fim)
            campanha.url_destino = data.get('url_destino', campanha.url_destino)
            campanha.orcamento = data.get('orcamento', campanha.orcamento)
            campanha.meta_leads = data.get('meta_leads', campanha.meta_leads)
            campanha.cor_identificacao = data.get('cor_identificacao', campanha.cor_identificacao)
            campanha.ordem_exibicao = data.get('ordem_exibicao', campanha.ordem_exibicao)
            campanha.observacoes = data.get('observacoes', campanha.observacoes)
            campanha.save()

            return JsonResponse({
                'success': True,
                'message': 'Campanha atualizada com sucesso!'
            })

        elif request.method == 'DELETE':
            data = json.loads(request.body)
            campanha_id = data.get('id')
            campanha = CampanhaTrafego.objects.get(id=campanha_id)
            campanha.delete()

            return JsonResponse({
                'success': True,
                'message': 'Campanha excluída com sucesso!'
            })

    except Exception as e:
        logger.error(f"Erro na API de campanhas: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@api_token_required
@require_http_methods(["POST"])
def api_detectar_campanha(request):
    """
    API para N8N detectar campanha em mensagem de cliente

    POST /api/campanhas/detectar/
    {
        "telefone": "5589999999999",
        "mensagem": "Oi, vi o cupom50 no Instagram",
        "origem": "whatsapp",
        "timestamp": "2024-11-20 10:30:00"
    }

    Response:
    {
        "success": true,
        "campanha_detectada": {
            "id": 5,
            "codigo": "CUPOM50",
            "nome": "Promoção Cupom 50% OFF",
            "plataforma": "instagram_ads"
        },
        "lead_id": 123,
        "score": 95.5,
        "lead_criado": false
    }
    """
    try:
        data = json.loads(request.body)
        telefone = data.get('telefone')
        mensagem = data.get('mensagem')
        origem = data.get('origem', 'whatsapp')
        timestamp_mensagem = data.get('timestamp')

        if not telefone or not mensagem:
            return JsonResponse({
                'success': False,
                'error': 'Telefone e mensagem são obrigatórios'
            }, status=400)

        # Normalizar mensagem
        mensagem_normalizada = unicodedata.normalize('NFKD', mensagem.lower())
        mensagem_normalizada = mensagem_normalizada.encode('ASCII', 'ignore').decode('ASCII')

        # Buscar campanhas ativas
        campanhas_ativas = CampanhaTrafego.objects.filter(ativa=True)

        melhor_match = None
        melhor_score = 0
        melhor_campanha = None
        melhor_trecho = None
        melhor_posicao = None

        for campanha in campanhas_ativas:
            # Verificar se está no período
            if not campanha.esta_ativa:
                continue

            palavra = campanha.palavra_chave
            if not campanha.case_sensitive:
                palavra = palavra.lower()

            # Aplicar detecção baseada no tipo
            if campanha.tipo_match == 'exato':
                # Match exato
                if campanha.case_sensitive:
                    encontrado = palavra in mensagem
                else:
                    encontrado = palavra in mensagem_normalizada

                if encontrado:
                    pos = mensagem_normalizada.find(palavra)
                    score = 100.0  # Match exato = 100%
                    if score > melhor_score or (score == melhor_score and campanha.prioridade > melhor_campanha.prioridade):
                        melhor_score = score
                        melhor_campanha = campanha
                        melhor_trecho = palavra
                        melhor_posicao = (pos, pos + len(palavra))
                        melhor_match = 'exato'

            elif campanha.tipo_match == 'parcial':
                # Match parcial
                if campanha.case_sensitive:
                    encontrado = palavra in mensagem
                else:
                    encontrado = palavra in mensagem_normalizada

                if encontrado:
                    pos = mensagem_normalizada.find(palavra)
                    # Score baseado no tamanho relativo da palavra
                    score = min(95.0, (len(palavra) / len(mensagem)) * 100 + 50)
                    if score > melhor_score or (score == melhor_score and campanha.prioridade > melhor_campanha.prioridade):
                        melhor_score = score
                        melhor_campanha = campanha
                        melhor_trecho = palavra
                        melhor_posicao = (pos, pos + len(palavra))
                        melhor_match = 'parcial'

            elif campanha.tipo_match == 'regex':
                # Match por regex
                try:
                    padrao = re.compile(palavra, re.IGNORECASE if not campanha.case_sensitive else 0)
                    match = padrao.search(mensagem_normalizada if not campanha.case_sensitive else mensagem)

                    if match:
                        score = 90.0  # Regex = 90%
                        if score > melhor_score or (score == melhor_score and campanha.prioridade > melhor_campanha.prioridade):
                            melhor_score = score
                            melhor_campanha = campanha
                            melhor_trecho = match.group()
                            melhor_posicao = (match.start(), match.end())
                            melhor_match = 'regex'
                except:
                    continue

        # Se não encontrou nenhuma campanha
        if not melhor_campanha:
            return JsonResponse({
                'success': True,
                'campanha_detectada': None,
                'mensagem': 'Nenhuma campanha detectada'
            })

        # Buscar ou criar lead
        lead = None
        lead_criado = False
        try:
            lead = LeadProspecto.objects.get(telefone=telefone)
        except LeadProspecto.DoesNotExist:
            # Criar lead básico
            lead = LeadProspecto.objects.create(
                telefone=telefone,
                nome_razaosocial=f"Lead {telefone}",
                origem='whatsapp',
                campanha_origem=melhor_campanha
            )
            lead_criado = True

        # Se é primeiro contato do lead com campanha
        if lead and not lead.campanha_origem:
            lead.campanha_origem = melhor_campanha
            lead.total_campanhas_detectadas = 1
            lead.save()
        elif lead and lead.campanha_origem != melhor_campanha:
            lead.total_campanhas_detectadas += 1
            lead.save()

        # Registrar detecção
        deteccao = DeteccaoCampanha.objects.create(
            lead=lead,
            campanha=melhor_campanha,
            telefone=telefone,
            mensagem_original=mensagem,
            mensagem_normalizada=mensagem_normalizada,
            trecho_detectado=melhor_trecho,
            posicao_inicio=melhor_posicao[0] if melhor_posicao else None,
            posicao_fim=melhor_posicao[1] if melhor_posicao else None,
            metodo_deteccao=melhor_match,
            score_confianca=Decimal(str(melhor_score)),
            eh_primeira_mensagem=lead_criado,
            origem=origem,
            timestamp_mensagem=timestamp_mensagem,
            processado_n8n=True,
            data_processamento_n8n=timezone.now()
        )

        return JsonResponse({
            'success': True,
            'campanha_detectada': {
                'id': melhor_campanha.id,
                'codigo': melhor_campanha.codigo,
                'nome': melhor_campanha.nome,
                'plataforma': melhor_campanha.plataforma,
                'cor': melhor_campanha.cor_identificacao,
            },
            'deteccao': {
                'id': deteccao.id,
                'trecho_detectado': melhor_trecho,
                'score_confianca': float(melhor_score),
                'metodo': melhor_match,
            },
            'lead_id': lead.id if lead else None,
            'lead_criado': lead_criado
        })

    except Exception as e:
        logger.error(f"Erro ao detectar campanha: {str(e)}")
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
