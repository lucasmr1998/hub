# ============================================================================
# DASHBOARD & REPORT VIEWS
# Migradas de vendas_web/views.py e vendas_web/funil_insights.py
# ============================================================================
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.db import models
from datetime import datetime, timedelta
from decimal import Decimal
import json
import logging
import os

logger = logging.getLogger(__name__)

# Models
from vendas_web.models import (
    LeadProspecto,
    Prospecto,
    HistoricoContato,
    FluxoAtendimento,
    AtendimentoFluxo,
)
from apps.integracoes.models import ClienteHubsoft, ServicoClienteHubsoft


# ============================================================================
# VIEWS DE PÁGINAS (Template rendering)
# ============================================================================

def dashboard_view(request):
    """View principal do dashboard"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'dashboard/new_dash.html', context)


@login_required(login_url='sistema:login')
def dashboard1(request):
    """View alternativa do dashboard - alias para dashboard_view"""
    context = {
        'user': request.user
    }
    return render(request, 'dashboard/new_dash.html', context)


@login_required(login_url='sistema:login')
def vendas_view(request):
    """View para a página de gerenciamento de vendas (prospectos)"""
    context = {
        'user': request.user
    }
    return render(request, 'dashboard/vendas.html', context)


@login_required(login_url='sistema:login')
def relatorios_view(request):
    """View para a página principal de relatórios"""
    from vendas_web.models import LeadProspecto, Prospecto, HistoricoContato
    from apps.integracoes.models import ClienteHubsoft, ServicoClienteHubsoft
    from django.db.models import Count, Q, Avg, Sum
    from datetime import datetime, timedelta
    from decimal import Decimal
    import json

    try:
        # Estatísticas gerais
        total_leads = LeadProspecto.objects.count()
        total_prospectos = Prospecto.objects.count()
        total_atendimentos = HistoricoContato.objects.filter(status='fluxo_inicializado').count()

        taxa_conversao = (total_prospectos / total_leads * 100) if total_leads > 0 else 0

        data_30_dias_atras = datetime.now() - timedelta(days=30)
        data_7_dias_atras = datetime.now() - timedelta(days=7)
        hoje = datetime.now().date()

        # Leads por período
        leads_hoje    = LeadProspecto.objects.filter(data_cadastro__date=hoje).count()
        leads_7_dias  = LeadProspecto.objects.filter(data_cadastro__gte=data_7_dias_atras).count()
        leads_30_dias = LeadProspecto.objects.filter(data_cadastro__gte=data_30_dias_atras).count()

        # Prospectos por período
        prospectos_hoje    = Prospecto.objects.filter(data_criacao__date=hoje).count()
        prospectos_7_dias  = Prospecto.objects.filter(data_criacao__gte=data_7_dias_atras).count()
        prospectos_30_dias = Prospecto.objects.filter(data_criacao__gte=data_30_dias_atras).count()

        # Atendimentos por período
        atendimentos_hoje    = HistoricoContato.objects.filter(data_hora_contato__date=hoje, status='fluxo_inicializado').count()
        atendimentos_7_dias  = HistoricoContato.objects.filter(data_hora_contato__gte=data_7_dias_atras, status='fluxo_inicializado').count()
        atendimentos_30_dias = HistoricoContato.objects.filter(data_hora_contato__gte=data_30_dias_atras, status='fluxo_inicializado').count()

        # ── Dados reais do Hubsoft (ClienteHubsoft / ServicoClienteHubsoft) ──
        total_clientes_hubsoft  = ClienteHubsoft.objects.count()
        clientes_ativos         = ClienteHubsoft.objects.filter(ativo=True).count()
        total_servicos          = ServicoClienteHubsoft.objects.count()
        clientes_com_alteracao  = ClienteHubsoft.objects.filter(houve_alteracao=True).count()

        # Serviços por status_prefixo (dados reais de habilitados/aguardando)
        servicos_habilitados      = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado').count()
        servicos_aguardando_inst  = ServicoClienteHubsoft.objects.filter(status_prefixo='aguardando_instalacao').count()
        servicos_cancelados       = ServicoClienteHubsoft.objects.filter(status_prefixo__icontains='cancel').count()
        servicos_suspensos        = ServicoClienteHubsoft.objects.filter(status_prefixo__icontains='suspen').count()

        # Receita total (soma dos valores dos serviços habilitados)
        receita_agg = ServicoClienteHubsoft.objects.filter(
            status_prefixo='servico_habilitado', valor__isnull=False
        ).aggregate(total=Sum('valor'))
        receita_total = float(receita_agg['total'] or 0)

        # Distribuição completa de status dos serviços
        servicos_por_status_raw = ServicoClienteHubsoft.objects.values('status_prefixo', 'status').annotate(
            total=Count('id')
        ).order_by('-total')
        servicos_por_status = [
            {'status': item['status'] or item['status_prefixo'] or 'Não informado', 'total': item['total']}
            for item in servicos_por_status_raw
        ]

        # Clientes habilitados por período (usando data_habilitacao dos serviços)
        habilitados_hoje    = ServicoClienteHubsoft.objects.filter(
            status_prefixo='servico_habilitado', data_habilitacao__date=hoje
        ).count()
        habilitados_7_dias  = ServicoClienteHubsoft.objects.filter(
            status_prefixo='servico_habilitado', data_habilitacao__gte=data_7_dias_atras
        ).count()
        habilitados_30_dias = ServicoClienteHubsoft.objects.filter(
            status_prefixo='servico_habilitado', data_habilitacao__gte=data_30_dias_atras
        ).count()

        # Evolução de habilitações — últimos 30 dias
        evolucao_habilitacoes_30d = []
        for i in range(30):
            data_atual = hoje - timedelta(days=i)
            evolucao_habilitacoes_30d.append({
                'data': data_atual.strftime('%d/%m'),
                'total': ServicoClienteHubsoft.objects.filter(
                    status_prefixo='servico_habilitado',
                    data_habilitacao__date=data_atual
                ).count(),
            })
        evolucao_habilitacoes_30d.reverse()

        # Funil de conversão real: Leads → Prospectos → Clientes Hubsoft → Habilitados
        funil_conversao = [
            {'etapa': 'Leads',              'total': total_leads},
            {'etapa': 'Prospectos',         'total': total_prospectos},
            {'etapa': 'Clientes Hubsoft',   'total': total_clientes_hubsoft},
            {'etapa': 'Habilitados',        'total': servicos_habilitados},
        ]

        # Leads por origem
        leads_por_origem = LeadProspecto.objects.values('origem').annotate(total=Count('id')).order_by('-total')[:6]

        # Atendimentos
        atendimentos_por_origem = HistoricoContato.objects.filter(
            status='fluxo_inicializado'
        ).values('origem_contato').annotate(total=Count('id')).order_by('-total')

        atendimentos_por_status = HistoricoContato.objects.filter(
            status__in=['fluxo_finalizado', 'transferido_humano']
        ).values('status').annotate(total=Count('id')).order_by('-total')

        # Série temporal — leads/prospectos/atendimentos (últimos 7 dias)
        leads_por_dia = []
        prospectos_por_dia = []
        atendimentos_por_dia = []
        for i in range(7):
            data_atual = hoje - timedelta(days=i)
            leads_por_dia.append({'data': data_atual.strftime('%d/%m'), 'total': LeadProspecto.objects.filter(data_cadastro__date=data_atual).count()})
            prospectos_por_dia.append({'data': data_atual.strftime('%d/%m'), 'total': Prospecto.objects.filter(data_criacao__date=data_atual).count()})
            atendimentos_por_dia.append({'data': data_atual.strftime('%d/%m'), 'total': HistoricoContato.objects.filter(data_hora_contato__date=data_atual, status='fluxo_inicializado').count()})
        leads_por_dia.reverse()
        prospectos_por_dia.reverse()
        atendimentos_por_dia.reverse()

        dados_graficos = {
            'leads_por_origem':             list(leads_por_origem),
            'servicos_por_status':          servicos_por_status,
            'atendimentos_por_origem':      list(atendimentos_por_origem),
            'atendimentos_por_status':      list(atendimentos_por_status),
            'leads_por_dia':                leads_por_dia,
            'prospectos_por_dia':           prospectos_por_dia,
            'atendimentos_por_dia':         atendimentos_por_dia,
            'evolucao_habilitacoes_30d':    evolucao_habilitacoes_30d,
            'funil_conversao':              funil_conversao,
        }

        stats = {
            'total_leads':        total_leads,
            'total_prospectos':   total_prospectos,
            'total_atendimentos': total_atendimentos,
            'taxa_conversao':     round(taxa_conversao, 1),

            'leads_hoje':    leads_hoje,
            'leads_7_dias':  leads_7_dias,
            'leads_30_dias': leads_30_dias,

            'prospectos_hoje':    prospectos_hoje,
            'prospectos_7_dias':  prospectos_7_dias,
            'prospectos_30_dias': prospectos_30_dias,

            'atendimentos_hoje':    atendimentos_hoje,
            'atendimentos_7_dias':  atendimentos_7_dias,
            'atendimentos_30_dias': atendimentos_30_dias,

            # Dados Hubsoft reais
            'total_clientes_hubsoft':  total_clientes_hubsoft,
            'clientes_ativos':         clientes_ativos,
            'total_servicos':          total_servicos,
            'clientes_com_alteracao':  clientes_com_alteracao,
            'servicos_habilitados':    servicos_habilitados,
            'servicos_aguardando_inst': servicos_aguardando_inst,
            'servicos_cancelados':     servicos_cancelados,
            'servicos_suspensos':      servicos_suspensos,
            'receita_total':           receita_total,
            'habilitados_hoje':        habilitados_hoje,
            'habilitados_7_dias':      habilitados_7_dias,
            'habilitados_30_dias':     habilitados_30_dias,

            'dados_graficos': json.dumps(dados_graficos),
        }
    except Exception as e:
        logger.error("Erro ao calcular estatísticas: %s", e, exc_info=True)
        stats = {
            'total_leads': 0, 'total_prospectos': 0, 'total_atendimentos': 0,
            'taxa_conversao': 0,
            'leads_hoje': 0, 'leads_7_dias': 0, 'leads_30_dias': 0,
            'prospectos_hoje': 0, 'prospectos_7_dias': 0, 'prospectos_30_dias': 0,
            'atendimentos_hoje': 0, 'atendimentos_7_dias': 0, 'atendimentos_30_dias': 0,
            'total_clientes_hubsoft': 0, 'clientes_ativos': 0, 'total_servicos': 0,
            'clientes_com_alteracao': 0, 'servicos_habilitados': 0,
            'servicos_aguardando_inst': 0, 'servicos_cancelados': 0, 'servicos_suspensos': 0,
            'receita_total': 0, 'habilitados_hoje': 0, 'habilitados_7_dias': 0,
            'habilitados_30_dias': 0,
            'dados_graficos': json.dumps({}),
        }

    context = {
        'user': request.user,
        'stats': stats
    }
    return render(request, 'dashboard/relatorios.html', context)


def relatorio_leads_view(request):
    """Relatorio focado em Leads — reutiliza dados da view principal"""
    from vendas_web.models import LeadProspecto
    from django.db.models import Count
    from datetime import datetime, timedelta
    import json

    hoje = datetime.now().date()
    data_30 = datetime.now() - timedelta(days=30)
    data_7 = datetime.now() - timedelta(days=7)

    total = LeadProspecto.objects.count()
    leads_hoje = LeadProspecto.objects.filter(data_cadastro__date=hoje).count()
    leads_7d = LeadProspecto.objects.filter(data_cadastro__gte=data_7).count()
    leads_30d = LeadProspecto.objects.filter(data_cadastro__gte=data_30).count()

    por_origem = list(LeadProspecto.objects.values('origem').annotate(total=Count('id')).order_by('-total')[:6])

    por_dia = []
    for i in range(30):
        d = hoje - timedelta(days=i)
        por_dia.append({'data': d.strftime('%d/%m'), 'total': LeadProspecto.objects.filter(data_cadastro__date=d).count()})
    por_dia.reverse()

    return render(request, 'dashboard/relatorio_leads_page.html', {
        'stats': {
            'total': total, 'hoje': leads_hoje, 'semana': leads_7d, 'mes': leads_30d,
        },
        'graficos': json.dumps({
            'por_origem': por_origem,
            'por_dia': por_dia,
        }),
    })


def relatorio_clientes_view(request):
    """Relatorio focado em Clientes HubSoft — somente leitura"""
    from apps.integracoes.models import ClienteHubsoft, ServicoClienteHubsoft
    from django.db.models import Count, Sum
    from datetime import datetime, timedelta
    import json

    hoje = datetime.now().date()
    data_30 = datetime.now() - timedelta(days=30)
    data_7 = datetime.now() - timedelta(days=7)

    total_clientes = ClienteHubsoft.objects.count()
    ativos = ClienteHubsoft.objects.filter(ativo=True).count()
    total_servicos = ServicoClienteHubsoft.objects.count()
    habilitados = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado').count()
    aguardando = ServicoClienteHubsoft.objects.filter(status_prefixo='aguardando_instalacao').count()
    cancelados = ServicoClienteHubsoft.objects.filter(status_prefixo__icontains='cancel').count()
    suspensos = ServicoClienteHubsoft.objects.filter(status_prefixo__icontains='suspen').count()

    receita_agg = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', valor__isnull=False).aggregate(total=Sum('valor'))
    receita = float(receita_agg['total'] or 0)

    servicos_por_status = list(ServicoClienteHubsoft.objects.values('status_prefixo', 'status').annotate(total=Count('id')).order_by('-total'))

    hab_hoje = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', data_habilitacao__date=hoje).count()
    hab_7d = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', data_habilitacao__gte=data_7).count()
    hab_30d = ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', data_habilitacao__gte=data_30).count()

    evolucao = []
    for i in range(30):
        d = hoje - timedelta(days=i)
        evolucao.append({'data': d.strftime('%d/%m'), 'total': ServicoClienteHubsoft.objects.filter(status_prefixo='servico_habilitado', data_habilitacao__date=d).count()})
    evolucao.reverse()

    return render(request, 'dashboard/relatorio_clientes_page.html', {
        'stats': {
            'total_clientes': total_clientes, 'ativos': ativos, 'total_servicos': total_servicos,
            'habilitados': habilitados, 'aguardando': aguardando, 'cancelados': cancelados,
            'suspensos': suspensos, 'receita': receita,
            'hab_hoje': hab_hoje, 'hab_7d': hab_7d, 'hab_30d': hab_30d,
        },
        'graficos': json.dumps({
            'servicos_por_status': [{'status': s['status'] or s['status_prefixo'], 'total': s['total']} for s in servicos_por_status],
            'evolucao_habilitacoes': evolucao,
        }),
    })


def relatorio_atendimentos_view(request):
    """Relatorio focado em Atendimentos — somente leitura"""
    from vendas_web.models import HistoricoContato
    from django.db.models import Count
    from datetime import datetime, timedelta
    import json

    hoje = datetime.now().date()
    data_30 = datetime.now() - timedelta(days=30)
    data_7 = datetime.now() - timedelta(days=7)

    total = HistoricoContato.objects.filter(status='fluxo_inicializado').count()
    atend_hoje = HistoricoContato.objects.filter(data_hora_contato__date=hoje, status='fluxo_inicializado').count()
    atend_7d = HistoricoContato.objects.filter(data_hora_contato__gte=data_7, status='fluxo_inicializado').count()
    atend_30d = HistoricoContato.objects.filter(data_hora_contato__gte=data_30, status='fluxo_inicializado').count()

    por_status = list(HistoricoContato.objects.values('status').annotate(total=Count('id')).order_by('-total')[:10])

    por_dia = []
    for i in range(30):
        d = hoje - timedelta(days=i)
        por_dia.append({'data': d.strftime('%d/%m'), 'total': HistoricoContato.objects.filter(data_hora_contato__date=d, status='fluxo_inicializado').count()})
    por_dia.reverse()

    return render(request, 'dashboard/relatorio_atendimentos_page.html', {
        'stats': {
            'total': total, 'hoje': atend_hoje, 'semana': atend_7d, 'mes': atend_30d,
        },
        'graficos': json.dumps({
            'por_status': por_status,
            'por_dia': por_dia,
        }),
    })


def analise_atendimentos_view(request):
    """View para análise de atendimentos"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'dashboard/analise_atendimentos.html', context)


def relatorio_conversoes_view(request):
    """View para relatório de conversões"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'dashboard/relatorio_conversoes.html', context)


def ajuda_view(request):
    """View para página de ajuda"""
    context = {
        'user': request.user if request.user.is_authenticated else None,
        'page_title': 'Central de Ajuda - Megalink'
    }
    return render(request, 'dashboard/ajuda.html', context)


def documentacao_view(request):
    """View para página de documentação do projeto"""
    context = {
        'user': request.user if request.user.is_authenticated else None,
        'page_title': 'Documentação - Megalink'
    }
    return render(request, 'dashboard/documentacao.html', context)


def api_swagger_view(request):
    """View para a documentação Swagger da API"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'dashboard/api_swagger.html', context)


def api_documentation_view(request):
    """View para servir a documentação da API em markdown"""
    # Ler o arquivo de documentação
    doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'api_documentation.md')

    try:
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Retornar como texto plano com quebras de linha preservadas
        response = HttpResponse(content, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = 'inline; filename="api_documentation.txt"'
        return response
    except FileNotFoundError:
        return HttpResponse("Documentação não encontrada", status=404)


def n8n_guide_view(request):
    """View para o guia de integração N8N"""
    context = {
        'user': request.user if request.user.is_authenticated else None
    }
    return render(request, 'dashboard/n8n_guide.html', context)


# ============================================================================
# APIs de Dados do Dashboard
# ============================================================================

def dashboard_data(request):
    """API para dados principais do dashboard"""
    try:
        # Cálculo das métricas conforme especificação:
        # 1. ATENDIMENTOS = Histórico de contatos com fluxo inicializado
        atendimentos = HistoricoContato.objects.filter(
            status='fluxo_inicializado'
        ).count()

        # 2. LEADS = Quantidade de LeadProspecto ativos
        leads = LeadProspecto.objects.filter(ativo=True).count()

        # 3. PROSPECTOS = Leads registrados no Hubsoft (com id_hubsoft preenchido)
        prospectos = LeadProspecto.objects.filter(
            id_hubsoft__isnull=False
        ).exclude(id_hubsoft='').count()

        # 4. CLIENTES = Clientes reais sincronizados do Hubsoft
        vendas = ClienteHubsoft.objects.count()

        # Calcular métricas do período anterior para comparação (últimos 30 dias vs 30 dias anteriores)
        hoje = timezone.now()
        inicio_periodo_atual = hoje - timedelta(days=30)
        inicio_periodo_anterior = hoje - timedelta(days=60)
        fim_periodo_anterior = hoje - timedelta(days=30)

        # Métricas do período anterior
        atendimentos_anterior = HistoricoContato.objects.filter(
            status='fluxo_inicializado',
            data_hora_contato__gte=inicio_periodo_anterior,
            data_hora_contato__lt=fim_periodo_anterior
        ).count()

        leads_anterior = LeadProspecto.objects.filter(
            ativo=True,
            data_cadastro__gte=inicio_periodo_anterior,
            data_cadastro__lt=fim_periodo_anterior
        ).count()

        prospectos_anterior = LeadProspecto.objects.filter(
            id_hubsoft__isnull=False,
            data_cadastro__gte=inicio_periodo_anterior,
            data_cadastro__lt=fim_periodo_anterior
        ).exclude(id_hubsoft='').count()

        vendas_anterior = ClienteHubsoft.objects.filter(
            data_criacao__gte=inicio_periodo_anterior,
            data_criacao__lt=fim_periodo_anterior
        ).count()

        # Calcular diferenças e variações percentuais
        def calcular_variacao(atual, anterior):
            if anterior == 0:
                if atual > 0:
                    return "+100.0%", atual
                else:
                    return "0.0%", 0
            else:
                variacao = ((atual - anterior) / anterior) * 100
                sinal = "+" if variacao >= 0 else ""
                return f"{sinal}{variacao:.1f}%", atual - anterior

        atendimentos_variacao, atendimentos_diff = calcular_variacao(atendimentos, atendimentos_anterior)
        leads_variacao, leads_diff = calcular_variacao(leads, leads_anterior)
        prospectos_variacao, prospectos_diff = calcular_variacao(prospectos, prospectos_anterior)
        vendas_variacao, vendas_diff = calcular_variacao(vendas, vendas_anterior)

        # Calcular taxas de conversão entre as etapas do funil
        taxa_atendimento_lead = f"{(leads/atendimentos*100):.2f}%" if atendimentos > 0 else "0.00%"
        taxa_lead_prospecto = f"{(prospectos/leads*100):.2f}%" if leads > 0 else "0.00%"
        taxa_prospecto_venda = f"{(vendas/prospectos*100):.2f}%" if prospectos > 0 else "0.00%"

        data = {
            'stats': {
                # Métricas principais conforme especificação
                'atendimentos': atendimentos,
                'atendimentos_variacao': atendimentos_variacao,
                'atendimentos_diff': atendimentos_diff,

                'leads': leads,
                'leads_variacao': leads_variacao,
                'leads_diff': leads_diff,

                'prospectos': prospectos,
                'prospectos_variacao': prospectos_variacao,
                'prospectos_diff': prospectos_diff,

                'vendas': vendas,
                'vendas_variacao': vendas_variacao,
                'vendas_diff': vendas_diff,

                # Taxas de conversão para as setas
                'taxa_atendimento_lead': taxa_atendimento_lead,
                'taxa_lead_prospecto': taxa_lead_prospecto,
                'taxa_prospecto_venda': taxa_prospecto_venda
            }
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_charts_data(request):
    """API para dados dos gráficos - Evolução dos últimos 7 dias"""
    try:
        # Função auxiliar para gerar dados dos últimos 7 dias
        def gerar_ultimos_7_dias(query_func):
            dados = []
            for i in range(7):
                data = timezone.now().date() - timedelta(days=i)
                count = query_func(data)
                dados.append({
                    'date': data.strftime('%d/%m'),
                    'count': count
                })
            dados.reverse()
            return dados

        # 1. ATENDIMENTOS dos últimos 7 dias (contatos com fluxo inicializado)
        def count_atendimentos(data):
            return HistoricoContato.objects.filter(
                data_hora_contato__date=data,
                status__in=['fluxo_inicializado']
            ).count()

        atendimentosUltimos7Dias = gerar_ultimos_7_dias(count_atendimentos)

        # 2. LEADS dos últimos 7 dias
        def count_leads(data):
            return LeadProspecto.objects.filter(
                data_cadastro__date=data,
                ativo=True
            ).count()

        leadsUltimos7Dias = gerar_ultimos_7_dias(count_leads)

        # 3. PROSPECTOS dos últimos 7 dias (leads registrados no Hubsoft)
        def count_prospectos(data):
            return LeadProspecto.objects.filter(
                data_cadastro__date=data,
                id_hubsoft__isnull=False,
            ).exclude(id_hubsoft='').count()

        prospectosUltimos7Dias = gerar_ultimos_7_dias(count_prospectos)

        # 4. CLIENTES dos últimos 7 dias (ClienteHubsoft sincronizados)
        def count_vendas(data):
            return ClienteHubsoft.objects.filter(
                data_criacao__date=data
            ).count()

        vendasUltimos7Dias = gerar_ultimos_7_dias(count_vendas)

        data = {
            # Dados para o gráfico de tendências (padrão será LEADS)
            'leadsUltimos7Dias': leadsUltimos7Dias,

            # Dados para troca dinâmica no frontend
            'atendimentosUltimos7Dias': atendimentosUltimos7Dias,
            'prospectosUltimos7Dias': prospectosUltimos7Dias,
            'vendasUltimos7Dias': vendasUltimos7Dias
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_tables_data(request):
    """API para dados das tabelas"""
    try:
        # Top empresas
        top_empresas = LeadProspecto.objects.filter(
            ativo=True,
            empresa__isnull=False
        ).exclude(empresa='').values('empresa').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Top origens
        top_origens = LeadProspecto.objects.filter(
            ativo=True
        ).values('origem').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        data = {
            'topEmpresas': list(top_empresas),
            'topOrigens': list(top_origens)
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_leads_data(request):
    """API para dados dos leads"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = 20
        search = request.GET.get('search', '')
        origem_filter = request.GET.get('origem', '')
        status_filter = request.GET.get('status', '')
        ativo_filter = request.GET.get('ativo', '')
        valor_filter = request.GET.get('valor', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        lead_id = request.GET.get('id', '')

        leads_query = LeadProspecto.objects.all()

        # Filtro por ID específico (para modal de detalhes)
        if lead_id:
            leads_query = leads_query.filter(id=lead_id)
        else:
            # Filtros normais
            if search:
                leads_query = leads_query.filter(
                    Q(nome_razaosocial__icontains=search) |
                    Q(email__icontains=search) |
                    Q(telefone__icontains=search) |
                    Q(empresa__icontains=search) |
                    Q(cpf_cnpj__icontains=search) |
                    Q(id_hubsoft__icontains=search)
                )

            if origem_filter:
                leads_query = leads_query.filter(origem=origem_filter)

            if status_filter:
                leads_query = leads_query.filter(status_api=status_filter)

            if ativo_filter:
                leads_query = leads_query.filter(ativo=(ativo_filter.lower() == 'true'))

            # Filtro de valor
            if valor_filter:
                if valor_filter == 'sim':
                    leads_query = leads_query.filter(
                        Q(valor__isnull=False) & Q(valor__gt=0)
                    )
                elif valor_filter == 'nao':
                    leads_query = leads_query.filter(
                        Q(valor__isnull=True) | Q(valor=0)
                    )

            # Filtros de data
            if data_inicio:
                try:
                    from datetime import datetime
                    di = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    leads_query = leads_query.filter(data_cadastro__date__gte=di)
                except ValueError:
                    pass

            if data_fim:
                try:
                    from datetime import datetime
                    df = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    leads_query = leads_query.filter(data_cadastro__date__lte=df)
                except ValueError:
                    pass

        total = leads_query.count()
        start = (page - 1) * per_page
        end = start + per_page

        leads = leads_query.order_by('-data_cadastro')[start:end]

        leads_data = []
        for lead in leads:
            leads_data.append({
                # Dados básicos
                'id': lead.id,
                'nome_razaosocial': lead.nome_razaosocial,
                'email': lead.email,
                'telefone': lead.telefone,
                'empresa': lead.empresa or '',

                # IDs e identificadores
                'id_hubsoft': lead.id_hubsoft or '',
                'id_origem': lead.id_origem or '',
                'id_origem_servico': lead.id_origem_servico or '',

                # Documentos
                'cpf_cnpj': lead.cpf_cnpj or '',
                'rg': lead.rg or '',

                # Endereço completo
                'endereco': lead.endereco or '',
                'rua': lead.rua or '',
                'numero_residencia': lead.numero_residencia or '',
                'bairro': lead.bairro or '',
                'cidade': lead.cidade or '',
                'estado': lead.estado or '',
                'cep': lead.cep or '',
                'ponto_referencia': lead.ponto_referencia or '',

                # Dados comerciais
                'valor': lead.get_valor_formatado(),
                'valor_numerico': float(lead.valor) if lead.valor else 0,
                'id_plano_rp': lead.id_plano_rp,
                'id_dia_vencimento': lead.id_dia_vencimento,
                'id_vendedor_rp': lead.id_vendedor_rp,
                'data_nascimento': lead.data_nascimento.isoformat() if lead.data_nascimento else '',

                # Status e origem
                'origem': lead.get_origem_display(),
                'origem_codigo': lead.origem,
                'canal_entrada': lead.canal_entrada or '',
                'tipo_entrada': lead.tipo_entrada or '',
                'status_api': lead.get_status_api_display(),
                'status_api_codigo': lead.status_api,
                'ativo': lead.ativo,

                # Qualificação e rastreamento
                'score_qualificacao': lead.score_qualificacao,
                'tentativas_contato': lead.tentativas_contato,
                'data_ultimo_contato': lead.data_ultimo_contato.isoformat() if lead.data_ultimo_contato else '',
                'motivo_rejeicao': lead.motivo_rejeicao or '',
                'custo_aquisicao': float(lead.custo_aquisicao) if lead.custo_aquisicao else 0,

                # Campanhas
                'campanha_origem_id': lead.campanha_origem.id if lead.campanha_origem else None,
                'campanha_origem_nome': lead.campanha_origem.nome if lead.campanha_origem else '',
                'campanha_conversao_id': lead.campanha_conversao.id if lead.campanha_conversao else None,
                'campanha_conversao_nome': lead.campanha_conversao.nome if lead.campanha_conversao else '',
                'total_campanhas_detectadas': lead.total_campanhas_detectadas,

                # Documentação e contrato
                'documentacao_completa': lead.documentacao_completa,
                'documentacao_validada': lead.documentacao_validada,
                'data_documentacao_completa': lead.data_documentacao_completa.isoformat() if lead.data_documentacao_completa else '',
                'data_documentacao_validada': lead.data_documentacao_validada.isoformat() if lead.data_documentacao_validada else '',
                'contrato_aceito': lead.contrato_aceito,
                'data_aceite_contrato': lead.data_aceite_contrato.isoformat() if lead.data_aceite_contrato else '',

                # Observações e datas
                'observacoes': lead.observacoes or '',
                'data_cadastro': lead.data_cadastro.isoformat() if lead.data_cadastro else None,
                'data_atualizacao': lead.data_atualizacao.isoformat() if lead.data_atualizacao else None,

                # Conversa do atendimento (HTML gerado)
                'html_conversa_path': lead.html_conversa_path or '',
                'data_geracao_html': lead.data_geracao_html.isoformat() if lead.data_geracao_html else '',
            })

        # Choices para filtros
        origem_choices = [
            {'value': choice[0], 'label': choice[1]}
            for choice in LeadProspecto.ORIGEM_CHOICES
        ]

        status_choices = [
            {'value': choice[0], 'label': choice[1]}
            for choice in LeadProspecto.STATUS_API_CHOICES
        ]

        # Calcular estatísticas totais (não apenas da página atual)
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta

        # Valor total de todos os leads com valor
        try:
            valor_total = LeadProspecto.objects.filter(
                valor__isnull=False,
                valor__gt=0
            ).aggregate(
                total=Sum('valor')
            )['total'] or 0
        except Exception:
            valor_total = 0

        # Leads de hoje
        try:
            hoje = timezone.now().date()
            leads_hoje = LeadProspecto.objects.filter(
                data_cadastro__date=hoje
            ).count()
        except Exception:
            leads_hoje = 0

        # Leads desta semana
        try:
            inicio_semana = hoje - timedelta(days=hoje.weekday())
            leads_semana = LeadProspecto.objects.filter(
                data_cadastro__date__gte=inicio_semana
            ).count()
        except Exception:
            leads_semana = 0

        data = {
            'leads': leads_data,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
            'origemChoices': origem_choices,
            'statusChoices': status_choices,
            'valor_total': valor_total,
            'leads_hoje': leads_hoje,
            'leads_semana': leads_semana
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_prospectos_data(request):
    """API para dados dos prospectos"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = 20
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        prioridade_filter = request.GET.get('prioridade', '')
        prospecto_id = request.GET.get('id', '')

        prospectos_query = Prospecto.objects.select_related('lead')

        # Filtro por ID específico (para modal de detalhes)
        if prospecto_id:
            prospectos_query = prospectos_query.filter(id=prospecto_id)
        else:
            # Filtros normais
            if search:
                prospectos_query = prospectos_query.filter(
                    Q(nome_prospecto__icontains=search) |
                    Q(id_prospecto_hubsoft__icontains=search) |
                    Q(lead__nome_razaosocial__icontains=search)
                )

            if status_filter:
                prospectos_query = prospectos_query.filter(status=status_filter)

            if prioridade_filter:
                prospectos_query = prospectos_query.filter(prioridade=prioridade_filter)

        total = prospectos_query.count()
        start = (page - 1) * per_page
        end = start + per_page

        prospectos = prospectos_query.order_by('-data_criacao')[start:end]

        prospectos_data = []
        for prospecto in prospectos:
            lead_data = None

            logger.debug("Processando Prospecto ID %s, id_hubsoft=%s, lead_id=%s",
                         prospecto.id, prospecto.id_prospecto_hubsoft,
                         prospecto.lead.id if prospecto.lead else None)

            # Estratégia 1: Buscar LeadProspecto pelo id_hubsoft do prospecto
            if prospecto.id_prospecto_hubsoft:
                try:
                    logger.debug("Buscando LeadProspecto com id_hubsoft=%s", prospecto.id_prospecto_hubsoft)
                    lead_prospecto = LeadProspecto.objects.filter(
                        id_hubsoft=prospecto.id_prospecto_hubsoft
                    ).first()

                    if lead_prospecto:
                        logger.debug("Lead encontrado pelo id_hubsoft, lead_id=%s", lead_prospecto.id)
                        lead_data = {
                            'id': lead_prospecto.id,
                            'nome_razaosocial': lead_prospecto.nome_razaosocial or '',
                            'email': lead_prospecto.email or '',
                            'telefone': lead_prospecto.telefone or '',
                            'empresa': lead_prospecto.empresa or '',
                            'cpf_cnpj': lead_prospecto.cpf_cnpj or '',
                            'rg': lead_prospecto.rg or '',
                            'endereco': lead_prospecto.endereco or '',
                            'rua': lead_prospecto.rua or '',
                            'numero_residencia': lead_prospecto.numero_residencia or '',
                            'bairro': lead_prospecto.bairro or '',
                            'cidade': lead_prospecto.cidade or '',
                            'estado': lead_prospecto.estado or '',
                            'cep': lead_prospecto.cep or '',
                            'ponto_referencia': lead_prospecto.ponto_referencia or '',
                            'valor': lead_prospecto.get_valor_formatado(),
                            'id_plano_rp': lead_prospecto.id_plano_rp,
                            'id_dia_vencimento': lead_prospecto.id_dia_vencimento,
                            'id_vendedor_rp': lead_prospecto.id_vendedor_rp,
                            'data_nascimento': lead_prospecto.data_nascimento.isoformat() if lead_prospecto.data_nascimento else '',
                            'origem': lead_prospecto.get_origem_display(),
                            'status_api': lead_prospecto.get_status_api_display(),
                            'id_hubsoft': lead_prospecto.id_hubsoft or '',
                            'observacoes': lead_prospecto.observacoes or '',
                            'data_criacao': lead_prospecto.data_cadastro.isoformat() if lead_prospecto.data_cadastro else None
                        }
                    else:
                        logger.debug("Nenhum LeadProspecto encontrado com id_hubsoft=%s", prospecto.id_prospecto_hubsoft)
                except Exception as e:
                    logger.error("Erro ao buscar LeadProspecto por id_hubsoft: %s", e, exc_info=True)

            # Estratégia 2: Se o lead relacionado existe, tentar buscar o LeadProspecto pelo ID do lead
            if not lead_data and prospecto.lead:
                # Primeiro, verificar se o lead relacionado TEM id_hubsoft
                lead_id_hubsoft = getattr(prospecto.lead, 'id_hubsoft', None)
                if lead_id_hubsoft:
                    logger.debug("Lead relacionado (ID %s) tem id_hubsoft=%s", prospecto.lead.id, lead_id_hubsoft)
                    try:
                        lead_prospecto_alt = LeadProspecto.objects.filter(id_hubsoft=lead_id_hubsoft).first()
                        if lead_prospecto_alt and lead_prospecto_alt.id != prospecto.lead.id:
                            logger.debug("Encontrado LeadProspecto alternativo, lead_id=%s", lead_prospecto_alt.id)
                            # Usar este lead ao invés do relacionado direto
                            lead_data = {
                                'id': lead_prospecto_alt.id,
                                'nome_razaosocial': lead_prospecto_alt.nome_razaosocial or '',
                                'email': lead_prospecto_alt.email or '',
                                'telefone': lead_prospecto_alt.telefone or '',
                                'empresa': lead_prospecto_alt.empresa or '',
                                'cpf_cnpj': lead_prospecto_alt.cpf_cnpj or '',
                                'rg': lead_prospecto_alt.rg or '',
                                'endereco': lead_prospecto_alt.endereco or '',
                                'rua': lead_prospecto_alt.rua or '',
                                'numero_residencia': lead_prospecto_alt.numero_residencia or '',
                                'bairro': lead_prospecto_alt.bairro or '',
                                'cidade': lead_prospecto_alt.cidade or '',
                                'estado': lead_prospecto_alt.estado or '',
                                'cep': lead_prospecto_alt.cep or '',
                                'ponto_referencia': lead_prospecto_alt.ponto_referencia or '',
                                'valor': lead_prospecto_alt.get_valor_formatado(),
                                'id_plano_rp': lead_prospecto_alt.id_plano_rp,
                                'id_dia_vencimento': lead_prospecto_alt.id_dia_vencimento,
                                'id_vendedor_rp': lead_prospecto_alt.id_vendedor_rp,
                                'data_nascimento': lead_prospecto_alt.data_nascimento.isoformat() if lead_prospecto_alt.data_nascimento else '',
                                'origem': lead_prospecto_alt.get_origem_display(),
                                'status_api': lead_prospecto_alt.get_status_api_display(),
                                'id_hubsoft': lead_prospecto_alt.id_hubsoft or '',
                                'observacoes': lead_prospecto_alt.observacoes or '',
                                'data_criacao': lead_prospecto_alt.data_cadastro.isoformat() if lead_prospecto_alt.data_cadastro else None
                            }
                    except Exception as e:
                        logger.error("Erro ao buscar por id_hubsoft do lead relacionado: %s", e)

            # Estratégia 3: Usar o lead relacionado direto como último recurso
            if not lead_data and prospecto.lead:
                try:
                    logger.debug("Usando lead relacionado direto, lead_id=%s", prospecto.lead.id)

                    lead_data = {
                        'id': prospecto.lead.id,
                        'nome_razaosocial': prospecto.lead.nome_razaosocial or '',
                        'email': prospecto.lead.email or '',
                        'telefone': prospecto.lead.telefone or '',
                        'empresa': prospecto.lead.empresa or '',
                        'cpf_cnpj': getattr(prospecto.lead, 'cpf_cnpj', '') or '',
                        'rg': getattr(prospecto.lead, 'rg', '') or '',
                        'endereco': getattr(prospecto.lead, 'endereco', '') or '',
                        'rua': getattr(prospecto.lead, 'rua', '') or '',
                        'numero_residencia': getattr(prospecto.lead, 'numero_residencia', '') or '',
                        'bairro': getattr(prospecto.lead, 'bairro', '') or '',
                        'cidade': getattr(prospecto.lead, 'cidade', '') or '',
                        'estado': getattr(prospecto.lead, 'estado', '') or '',
                        'cep': getattr(prospecto.lead, 'cep', '') or '',
                        'ponto_referencia': getattr(prospecto.lead, 'ponto_referencia', '') or '',
                        'valor': prospecto.lead.get_valor_formatado() if hasattr(prospecto.lead, 'get_valor_formatado') else 'R$ 0,00',
                        'id_plano_rp': getattr(prospecto.lead, 'id_plano_rp', None),
                        'id_dia_vencimento': getattr(prospecto.lead, 'id_dia_vencimento', None),
                        'id_vendedor_rp': getattr(prospecto.lead, 'id_vendedor_rp', None),
                        'data_nascimento': prospecto.lead.data_nascimento.isoformat() if hasattr(prospecto.lead, 'data_nascimento') and prospecto.lead.data_nascimento else '',
                        'origem': prospecto.lead.get_origem_display() if hasattr(prospecto.lead, 'get_origem_display') else '',
                        'status_api': prospecto.lead.get_status_api_display() if hasattr(prospecto.lead, 'get_status_api_display') else '',
                        'id_hubsoft': getattr(prospecto.lead, 'id_hubsoft', '') or '',
                        'observacoes': getattr(prospecto.lead, 'observacoes', '') or '',
                        'data_criacao': prospecto.lead.data_cadastro.isoformat() if hasattr(prospecto.lead, 'data_cadastro') and prospecto.lead.data_cadastro else None
                    }
                except Exception as e:
                    logger.error("Erro ao buscar dados do lead relacionado: %s", e, exc_info=True)
                    # Dados mínimos em caso de erro
                    lead_data = {
                        'id': prospecto.lead.id,
                        'nome_razaosocial': getattr(prospecto.lead, 'nome_razaosocial', ''),
                        'email': getattr(prospecto.lead, 'email', ''),
                        'telefone': getattr(prospecto.lead, 'telefone', ''),
                        'empresa': getattr(prospecto.lead, 'empresa', ''),
                        'valor': 'R$ 0,00'
                    }

            # Se ainda não tem lead_data, o prospecto não tem lead relacionado
            if not lead_data:
                logger.debug("Prospecto %s sem lead relacionado", prospecto.id)
            else:
                logger.debug("Lead_data final para prospecto %s: lead_id=%s", prospecto.id, lead_data.get('id'))

            prospectos_data.append({
                'id': prospecto.id,
                'nome_prospecto': prospecto.nome_prospecto,
                'lead': lead_data,
                'id_prospecto_hubsoft': prospecto.id_prospecto_hubsoft or '-',
                'status': prospecto.status,  # Status raw para o frontend
                'status_display': prospecto.get_status_display(),
                'prioridade': getattr(prospecto, 'prioridade', 1),
                'score_conversao': float(prospecto.score_conversao) if hasattr(prospecto, 'score_conversao') and prospecto.score_conversao else None,
                'data_criacao': prospecto.data_criacao.isoformat() if prospecto.data_criacao else None,
                'data_processamento': prospecto.data_processamento.isoformat() if prospecto.data_processamento else None,
                'observacoes': getattr(prospecto, 'observacoes', '') or '',
                'historico_status': getattr(prospecto, 'historico_status', '') or '',
                # Campos técnicos (apenas para admin/debug)
                'tentativas_processamento': prospecto.tentativas_processamento,
                'tempo_processamento': prospecto.get_tempo_processamento_formatado() if hasattr(prospecto, 'get_tempo_processamento_formatado') else '-',
                'erro_processamento': prospecto.erro_processamento[:50] + '...' if prospecto.erro_processamento and len(prospecto.erro_processamento) > 50 else (prospecto.erro_processamento or '-'),
                'dados_processamento': getattr(prospecto, 'dados_processamento', None),
                'resultado_processamento': getattr(prospecto, 'resultado_processamento', None)
            })

        # Status choices para o filtro
        status_choices = [
            {'value': choice[0], 'label': choice[1]}
            for choice in Prospecto.STATUS_CHOICES
        ]

        data = {
            'prospectos': prospectos_data,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
            'statusChoices': status_choices
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_historico_data(request):
    """API para dados do histórico de contatos"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = 20
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        sucesso_filter = request.GET.get('sucesso', '')
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')
        contato_id = request.GET.get('id', '')

        historico_query = HistoricoContato.objects.select_related('lead')

        # Filtro por ID específico (para modal de detalhes)
        if contato_id:
            historico_query = historico_query.filter(id=contato_id)
        else:
            # Filtros normais
            if search:
                historico_query = historico_query.filter(
                    Q(telefone__icontains=search) |
                    Q(nome_contato__icontains=search) |
                    Q(lead__nome_razaosocial__icontains=search)
                )

            if status_filter:
                historico_query = historico_query.filter(status=status_filter)

            if sucesso_filter:
                historico_query = historico_query.filter(sucesso=(sucesso_filter.lower() == 'true'))

            if data_inicio:
                try:
                    data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    historico_query = historico_query.filter(data_hora_contato__date__gte=data_inicio_obj)
                except ValueError:
                    pass

            if data_fim:
                try:
                    data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    historico_query = historico_query.filter(data_hora_contato__date__lte=data_fim_obj)
                except ValueError:
                    pass

        total = historico_query.count()
        start = (page - 1) * per_page
        end = start + per_page

        historico = historico_query.order_by('-data_hora_contato')[start:end]

        historico_data = []
        for contato in historico:
            historico_data.append({
                'id': contato.id,
                'telefone': contato.telefone,
                'nome_contato': contato.nome_contato or '-',
                'lead_relacionado': contato.lead.nome_razaosocial if contato.lead else None,
                'status': contato.get_status_display(),
                'status_color': contato.get_status_display_color(),
                'data_hora_contato': contato.data_hora_contato.isoformat() if contato.data_hora_contato else None,
                'duracao_formatada': contato.get_duracao_formatada(),
                'sucesso': contato.sucesso,
                'converteu_lead': contato.converteu_lead,
                'converteu_venda': contato.converteu_venda,
                'valor_venda': contato.get_valor_venda_formatado() if contato.valor_venda else None,
                'data_conversao_lead': contato.data_conversao_lead.isoformat() if contato.data_conversao_lead else None,
                'data_conversao_venda': contato.data_conversao_venda.isoformat() if contato.data_conversao_venda else None,
                'origem_contato': contato.get_origem_contato_display() if contato.origem_contato else None,
                'transcricao': contato.transcricao or '-',
                'observacoes': contato.observacoes or '-',
                'ip_origem': contato.ip_origem or '-',
                'tempo_relativo': contato.get_tempo_relativo(),
                'dados_extras': contato.dados_extras,
                'bem_sucedido': contato.is_contato_bem_sucedido(),
                'conversao_completa': contato.is_conversao_completa()
            })

        # Status choices para o filtro
        status_choices = [
            {'value': choice[0], 'label': choice[1]}
            for choice in HistoricoContato.STATUS_CHOICES
        ]

        data = {
            'historico': historico_data,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page,
            'statusChoices': status_choices
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_contatos_realtime(request):
    """API para contatos em tempo real"""
    try:
        # Últimos 10 contatos
        contatos_recentes = HistoricoContato.objects.order_by('-data_hora_contato')[:10]

        contatos_data = []
        for contato in contatos_recentes:
            contatos_data.append({
                'id': contato.id,
                'telefone': contato.telefone,
                'nome_contato': contato.nome_contato or 'Não identificado',
                'status': contato.get_status_display(),
                'data_hora_contato': contato.data_hora_contato.isoformat() if contato.data_hora_contato else None,
                'tempo_relativo': contato.get_tempo_relativo(),
                'sucesso': contato.sucesso
            })

        data = {
            'contatos': contatos_data
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_contato_historico(request, telefone):
    """API para histórico detalhado de um telefone"""
    try:
        # Buscar todos os contatos deste telefone
        contatos = HistoricoContato.objects.filter(
            telefone=telefone
        ).order_by('-data_hora_contato')

        # Estatísticas básicas do telefone
        total_contatos = contatos.count()
        contatos_sucesso = contatos.filter(sucesso=True).count()
        contatos_finalizados = contatos.filter(status='fluxo_finalizado').count()
        contatos_transferidos = contatos.filter(status='transferido_humano').count()
        contatos_inicializados = contatos.filter(status='fluxo_inicializado').count()
        contatos_convertidos_lead = contatos.filter(converteu_lead=True).count()
        contatos_vendas = contatos.filter(converteu_venda=True).count()
        duracao_total = sum([c.duracao_segundos or 0 for c in contatos])

        # Calcular taxas
        taxa_sucesso = (contatos_sucesso / total_contatos * 100) if total_contatos > 0 else 0
        taxa_finalizacao = ((contatos_finalizados + contatos_transferidos) / total_contatos * 100) if total_contatos > 0 else 0
        taxa_conversao_lead = (contatos_convertidos_lead / total_contatos * 100) if total_contatos > 0 else 0
        taxa_conversao_venda = (contatos_vendas / contatos_convertidos_lead * 100) if contatos_convertidos_lead > 0 else 0

        # Último contato
        ultimo_contato = contatos.first()
        ultimo_contato_data = ultimo_contato.data_hora_contato.isoformat() if ultimo_contato else None

        # Valor total das vendas
        valor_total_vendas = contatos.filter(converteu_venda=True).aggregate(
            total=Sum('valor_venda')
        )['total'] or 0

        # Timeline dos contatos com informações detalhadas
        timeline_data = []
        for contato in contatos:
            timeline_data.append({
                'id': contato.id,
                'data_hora_contato': contato.data_hora_contato.isoformat() if contato.data_hora_contato else None,
                'status': contato.get_status_display(),
                'nome_contato': contato.nome_contato or 'Não identificado',
                'duracao_formatada': contato.get_duracao_formatada(),
                'sucesso': contato.sucesso,
                'converteu_lead': contato.converteu_lead,
                'converteu_venda': contato.converteu_venda,
                'valor_venda': contato.get_valor_venda_formatado() if contato.valor_venda else None,
                'observacoes': contato.observacoes or '',
                'transcricao': contato.transcricao or '',
                'tempo_relativo': contato.get_tempo_relativo(),
                'origem_contato': contato.get_origem_contato_display() if contato.origem_contato else None
            })

        data = {
            'telefone': telefone,
            'total': total_contatos,
            'ultimo_contato': ultimo_contato_data,
            'taxa_sucesso': f"{taxa_sucesso:.1f}%",
            'estatisticas': {
                'total_contatos': total_contatos,
                'contatos_sucesso': contatos_sucesso,
                'contatos_finalizados': contatos_finalizados,
                'contatos_transferidos': contatos_transferidos,
                'contatos_inicializados': contatos_inicializados,
                'contatos_convertidos_lead': contatos_convertidos_lead,
                'contatos_vendas': contatos_vendas,
                'duracao_total_minutos': duracao_total // 60 if duracao_total else 0,
                'taxa_sucesso': taxa_sucesso,
                'taxa_finalizacao': taxa_finalizacao,
                'taxa_conversao_lead': taxa_conversao_lead,
                'taxa_conversao_venda': taxa_conversao_venda,
                'valor_total_vendas': valor_total_vendas,
                'valor_total_vendas_formatado': f"R$ {valor_total_vendas:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            },
            'historico': timeline_data,
            'timeline': timeline_data
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dashboard_ultimas_conversoes(request):
    """API para últimas conversões — leads que viraram clientes Hubsoft"""
    try:
        limite = int(request.GET.get('limite', 6))

        # Leads que possuem ao menos um ClienteHubsoft vinculado
        clientes = (
            ClienteHubsoft.objects
            .select_related('lead')
            .prefetch_related('servicos')
            .filter(lead__isnull=False)
            .order_by('-data_criacao')[:limite]
        )

        conversoes = []
        for cliente in clientes:
            lead = cliente.lead

            # Serviço principal (primeiro serviço ativo, ou o primeiro disponível)
            servicos = list(cliente.servicos.all())
            servico_principal = next(
                (s for s in servicos if s.status_prefixo and 'habilit' in s.status_prefixo.lower()),
                servicos[0] if servicos else None
            )

            conversoes.append({
                'nome': cliente.nome_razaosocial,
                'cpf_cnpj': cliente.cpf_cnpj or '',
                'telefone': cliente.telefone_primario or (lead.telefone if lead else ''),
                'origem': lead.get_origem_display() if lead else '-',
                'data_sync': cliente.data_sync.isoformat() if cliente.data_sync else None,
                'data_cadastro': lead.data_cadastro.isoformat() if lead and lead.data_cadastro else None,
                'servico_nome': servico_principal.nome if servico_principal else '-',
                'servico_status': servico_principal.status if servico_principal else '-',
                'valor': (
                    f"R$ {servico_principal.valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    if servico_principal and servico_principal.valor else '-'
                ),
                'ativo': cliente.ativo,
                'lead_id': lead.id if lead else None,
            })

        return JsonResponse({'conversoes': conversoes})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# APIs de Análise de Atendimentos
# ============================================================================

@login_required
def api_analise_atendimentos_data(request):
    """API para dados da análise de atendimentos"""
    try:
        from django.db.models import Count, Avg, Q, F
        from datetime import datetime, timedelta

        # Parâmetros de filtro
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        fluxo_id = request.GET.get('fluxo_id')
        status_filter = request.GET.get('status')

        # Query base
        atendimentos = AtendimentoFluxo.objects.all()
        historicos = HistoricoContato.objects.all()

        # Aplicar filtros de data
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                atendimentos = atendimentos.filter(data_inicio__date__gte=data_inicio_obj)
                historicos = historicos.filter(data_hora_contato__date__gte=data_inicio_obj)
            except ValueError:
                pass

        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                atendimentos = atendimentos.filter(data_inicio__date__lte=data_fim_obj)
                historicos = historicos.filter(data_hora_contato__date__lte=data_fim_obj)
            except ValueError:
                pass

        # Aplicar filtro de fluxo
        if fluxo_id:
            try:
                atendimentos = atendimentos.filter(fluxo_id=int(fluxo_id))
            except ValueError:
                pass

        # Aplicar filtro de status
        if status_filter:
            atendimentos = atendimentos.filter(status=status_filter)

        # Métricas principais
        total_atendimentos = atendimentos.count()
        atendimentos_completados = atendimentos.filter(status='completado').count()
        atendimentos_abandonados = atendimentos.filter(status='abandonado').count()
        atendimentos_em_andamento = atendimentos.filter(status__in=['iniciado', 'em_andamento']).count()

        # Calcular taxas
        if total_atendimentos > 0:
            taxa_completude = round((atendimentos_completados / total_atendimentos) * 100, 1)
            taxa_abandono = round((atendimentos_abandonados / total_atendimentos) * 100, 1)
        else:
            taxa_completude = 0
            taxa_abandono = 0

        # Tempo médio
        tempo_medio = atendimentos.filter(
            tempo_total__isnull=False
        ).aggregate(
            tempo_medio=Avg('tempo_total')
        )['tempo_medio'] or 0

        # Formatação do tempo médio
        if tempo_medio > 0:
            if tempo_medio < 60:
                tempo_medio_formatado = f"{int(tempo_medio)}s"
            elif tempo_medio < 3600:
                minutos = int(tempo_medio // 60)
                segundos = int(tempo_medio % 60)
                tempo_medio_formatado = f"{minutos}m {segundos}s"
            else:
                horas = int(tempo_medio // 3600)
                minutos = int((tempo_medio % 3600) // 60)
                tempo_medio_formatado = f"{horas}h {minutos}m"
        else:
            tempo_medio_formatado = "0s"

        # Dados para gráficos - últimos 7 dias
        data_fim_chart = datetime.now().date()
        data_inicio_chart = data_fim_chart - timedelta(days=6)

        chart_data = []
        for i in range(7):
            data_chart = data_inicio_chart + timedelta(days=i)
            atendimentos_dia = atendimentos.filter(data_inicio__date=data_chart).count()
            completados_dia = atendimentos.filter(
                data_inicio__date=data_chart,
                status='completado'
            ).count()

            chart_data.append({
                'date': data_chart.strftime('%d/%m'),
                'atendimentos': atendimentos_dia,
                'completados': completados_dia
            })

        # Distribuição por status
        status_distribution = atendimentos.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        # Distribuição por fluxo
        fluxo_distribution = atendimentos.select_related('fluxo').values(
            'fluxo__nome'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Score médio de qualificação
        score_medio = atendimentos.filter(
            score_qualificacao__isnull=False
        ).aggregate(
            score_medio=Avg('score_qualificacao')
        )['score_medio'] or 0

        # Dados de histórico de contatos
        total_contatos = historicos.count()
        contatos_sucesso = historicos.filter(sucesso=True).count()
        contatos_convertidos = historicos.filter(converteu_lead=True).count()
        vendas_confirmadas = historicos.filter(converteu_venda=True).count()

        # Taxa de conversão de contatos
        if total_contatos > 0:
            taxa_conversao_contatos = round((contatos_convertidos / total_contatos) * 100, 1)
            taxa_vendas = round((vendas_confirmadas / total_contatos) * 100, 1)
        else:
            taxa_conversao_contatos = 0
            taxa_vendas = 0

        response_data = {
            'metricas_principais': {
                'total_atendimentos': total_atendimentos,
                'atendimentos_completados': atendimentos_completados,
                'atendimentos_abandonados': atendimentos_abandonados,
                'atendimentos_em_andamento': atendimentos_em_andamento,
                'taxa_completude': taxa_completude,
                'taxa_abandono': taxa_abandono,
                'tempo_medio_segundos': round(tempo_medio, 2),
                'tempo_medio_formatado': tempo_medio_formatado,
                'score_medio_qualificacao': round(score_medio, 1),
            },
            'metricas_contatos': {
                'total_contatos': total_contatos,
                'contatos_sucesso': contatos_sucesso,
                'contatos_convertidos': contatos_convertidos,
                'vendas_confirmadas': vendas_confirmadas,
                'taxa_conversao_contatos': taxa_conversao_contatos,
                'taxa_vendas': taxa_vendas,
            },
            'graficos': {
                'evolucao_7_dias': chart_data,
                'distribuicao_status': list(status_distribution),
                'distribuicao_fluxo': list(fluxo_distribution),
            }
        }

        return JsonResponse(response_data)

    except Exception as e:
        import traceback
        logger.error(f"Erro na API de análise de atendimentos: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'error': f'Erro ao carregar dados de análise: {str(e)}'
        }, status=500)


@login_required
def api_analise_atendimentos_fluxos(request):
    """API para listar fluxos disponíveis para filtro"""
    try:
        fluxos = FluxoAtendimento.objects.filter(ativo=True).values(
            'id', 'nome', 'tipo_fluxo'
        ).order_by('nome')

        fluxos_data = []
        for fluxo in fluxos:
            total_atendimentos = AtendimentoFluxo.objects.filter(fluxo_id=fluxo['id']).count()
            fluxos_data.append({
                'id': fluxo['id'],
                'nome': fluxo['nome'],
                'tipo_fluxo': fluxo['tipo_fluxo'],
                'total_atendimentos': total_atendimentos
            })

        return JsonResponse({
            'fluxos': fluxos_data
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Erro ao carregar fluxos: {str(e)}'
        }, status=500)


@login_required
def api_analise_detalhada_atendimentos(request):
    """API para dados detalhados de atendimentos com paginação"""
    try:
        from django.core.paginator import Paginator

        # Parâmetros
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 100)

        # Filtros
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        fluxo_id = request.GET.get('fluxo_id')
        status_filter = request.GET.get('status')
        search = request.GET.get('search', '').strip()

        # Query base
        atendimentos = AtendimentoFluxo.objects.select_related('lead', 'fluxo').all()

        # Aplicar filtros
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                atendimentos = atendimentos.filter(data_inicio__date__gte=data_inicio_obj)
            except ValueError:
                pass

        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d').date()
                atendimentos = atendimentos.filter(data_inicio__date__lte=data_fim_obj)
            except ValueError:
                pass

        if fluxo_id:
            try:
                atendimentos = atendimentos.filter(fluxo_id=int(fluxo_id))
            except ValueError:
                pass

        if status_filter:
            atendimentos = atendimentos.filter(status=status_filter)

        if search:
            atendimentos = atendimentos.filter(
                Q(lead__nome_razaosocial__icontains=search) |
                Q(lead__telefone__icontains=search) |
                Q(lead__email__icontains=search) |
                Q(fluxo__nome__icontains=search)
            )

        # Ordenação
        atendimentos = atendimentos.order_by('-data_inicio')

        # Paginação
        paginator = Paginator(atendimentos, per_page)
        page_obj = paginator.get_page(page)

        # Serializar dados
        atendimentos_data = []
        for atendimento in page_obj:
            atendimentos_data.append({
                'id': atendimento.id,
                'lead': {
                    'id': atendimento.lead.id,
                    'nome': atendimento.lead.nome_razaosocial,
                    'telefone': atendimento.lead.telefone,
                    'email': atendimento.lead.email or '',
                },
                'fluxo': {
                    'id': atendimento.fluxo.id,
                    'nome': atendimento.fluxo.nome,
                    'tipo': atendimento.fluxo.tipo_fluxo,
                },
                'status': atendimento.status,
                'status_display': atendimento.get_status_display(),
                'data_inicio': atendimento.data_inicio.strftime('%d/%m/%Y %H:%M'),
                'data_conclusao': atendimento.data_conclusao.strftime('%d/%m/%Y %H:%M') if atendimento.data_conclusao else None,
                'progresso_percentual': atendimento.get_progresso_percentual(),
                'questao_atual': atendimento.questao_atual,
                'total_questoes': atendimento.total_questoes,
                'tempo_total': atendimento.get_tempo_formatado(),
                'score_qualificacao': atendimento.score_qualificacao,
                'observacoes': atendimento.observacoes or ''
            })

        return JsonResponse({
            'atendimentos': atendimentos_data,
            'total': paginator.count,
            'page': page,
            'pages': paginator.num_pages,
            'per_page': per_page
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Erro ao carregar atendimentos detalhados: {str(e)}'
        }, status=500)


@login_required
def api_jornada_cliente_completa(request):
    """API para obter jornada completa de um cliente (lead + histórico + atendimentos)"""
    try:
        lead_id = request.GET.get('lead_id')
        atendimento_id = request.GET.get('atendimento_id')

        if not lead_id and not atendimento_id:
            return JsonResponse({
                'error': 'É necessário informar lead_id ou atendimento_id'
            }, status=400)

        # Buscar lead
        if lead_id:
            try:
                lead = LeadProspecto.objects.get(id=lead_id)
            except LeadProspecto.DoesNotExist:
                return JsonResponse({'error': 'Lead não encontrado'}, status=404)
        else:
            try:
                atendimento = AtendimentoFluxo.objects.select_related('lead').get(id=atendimento_id)
                lead = atendimento.lead
            except AtendimentoFluxo.DoesNotExist:
                return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)

        # Buscar todos os contatos relacionados
        historicos = HistoricoContato.objects.filter(
            models.Q(lead=lead) | models.Q(telefone=lead.telefone)
        ).order_by('data_hora_contato')

        # Buscar todos os atendimentos de fluxo
        atendimentos = AtendimentoFluxo.objects.filter(lead=lead).select_related(
            'fluxo', 'historico_contato'
        ).order_by('data_inicio')

        # Serializar dados do lead
        lead_data = {
            'id': lead.id,
            'nome': lead.nome_razaosocial,
            'email': lead.email,
            'telefone': lead.telefone,
            'empresa': lead.empresa,
            'valor': lead.get_valor_formatado(),
            'origem': lead.origem,
            'data_cadastro': lead.data_cadastro.strftime('%d/%m/%Y %H:%M'),
            'status_api': lead.status_api,
            'score_qualificacao': lead.score_qualificacao,
            'tentativas_contato': lead.tentativas_contato,
            'data_ultimo_contato': lead.data_ultimo_contato.strftime('%d/%m/%Y %H:%M') if lead.data_ultimo_contato else None,
            'observacoes': lead.observacoes,
            'ativo': lead.ativo,
        }

        # Serializar histórico de contatos
        historicos_data = []
        for historico in historicos:
            historicos_data.append({
                'id': historico.id,
                'telefone': historico.telefone,
                'data_hora': historico.data_hora_contato.strftime('%d/%m/%Y %H:%M:%S'),
                'status': historico.status,
                'status_display': historico.get_status_display(),
                'nome_contato': historico.nome_contato,
                'duracao_segundos': historico.duracao_segundos,
                'duracao_formatada': f"{historico.duracao_segundos//60}m {historico.duracao_segundos%60}s" if historico.duracao_segundos else None,
                'transcricao': historico.transcricao,
                'observacoes': historico.observacoes,
                'sucesso': historico.sucesso,
                'converteu_lead': historico.converteu_lead,
                'converteu_venda': historico.converteu_venda,
                'valor_venda': historico.valor_venda,
                'origem_contato': historico.origem_contato,
            })

        # Serializar atendimentos
        atendimentos_data = []
        for atendimento in atendimentos:
            # Buscar respostas detalhadas
            respostas = atendimento.get_respostas_formatadas()

            atendimentos_data.append({
                'id': atendimento.id,
                'fluxo': {
                    'id': atendimento.fluxo.id,
                    'nome': atendimento.fluxo.nome,
                    'tipo_fluxo': atendimento.fluxo.tipo_fluxo,
                    'descricao': atendimento.fluxo.descricao,
                },
                'status': atendimento.status,
                'status_display': atendimento.get_status_display(),
                'data_inicio': atendimento.data_inicio.strftime('%d/%m/%Y %H:%M:%S'),
                'data_conclusao': atendimento.data_conclusao.strftime('%d/%m/%Y %H:%M:%S') if atendimento.data_conclusao else None,
                'questao_atual': atendimento.questao_atual,
                'total_questoes': atendimento.total_questoes,
                'questoes_respondidas': atendimento.questoes_respondidas,
                'progresso_percentual': atendimento.get_progresso_percentual(),
                'tempo_total': atendimento.tempo_total,
                'tempo_formatado': atendimento.get_tempo_formatado(),
                'tentativas_atual': atendimento.tentativas_atual,
                'max_tentativas': atendimento.max_tentativas,
                'score_qualificacao': atendimento.score_qualificacao,
                'observacoes': atendimento.observacoes,
                'historico_contato_id': atendimento.historico_contato.id if atendimento.historico_contato else None,
                'respostas': respostas,
                'dados_respostas': atendimento.dados_respostas,
            })

        # Calcular estatísticas da jornada
        total_contatos = len(historicos_data)
        contatos_sucesso = sum(1 for h in historicos_data if h['sucesso'])
        total_atendimentos = len(atendimentos_data)
        atendimentos_completados = sum(1 for a in atendimentos_data if a['status'] == 'completado')

        # Timeline unificada (contatos + início de atendimentos)
        timeline = []

        # Adicionar contatos à timeline
        for historico in historicos_data:
            timeline.append({
                'tipo': 'contato',
                'data': historico['data_hora'],
                'timestamp': historico['data_hora'],
                'titulo': f"Contato - {historico['status_display']}",
                'descricao': f"Telefone: {historico['telefone']}",
                'detalhes': historico,
                'icone': 'phone',
                'cor': '#3498db' if historico['sucesso'] else '#e74c3c'
            })

        # Adicionar atendimentos à timeline
        for atendimento in atendimentos_data:
            timeline.append({
                'tipo': 'atendimento',
                'data': atendimento['data_inicio'],
                'timestamp': atendimento['data_inicio'],
                'titulo': f"Atendimento - {atendimento['fluxo']['nome']}",
                'descricao': f"Status: {atendimento['status_display']} ({atendimento['progresso_percentual']}%)",
                'detalhes': atendimento,
                'icone': 'comments',
                'cor': '#27ae60' if atendimento['status'] == 'completado' else '#f39c12'
            })

        # Ordenar timeline por data
        timeline.sort(key=lambda x: x['timestamp'])

        response_data = {
            'lead': lead_data,
            'historico_contatos': historicos_data,
            'atendimentos': atendimentos_data,
            'timeline': timeline,
            'estatisticas': {
                'total_contatos': total_contatos,
                'contatos_sucesso': contatos_sucesso,
                'taxa_sucesso_contatos': round((contatos_sucesso / total_contatos) * 100, 1) if total_contatos > 0 else 0,
                'total_atendimentos': total_atendimentos,
                'atendimentos_completados': atendimentos_completados,
                'taxa_completude_atendimentos': round((atendimentos_completados / total_atendimentos) * 100, 1) if total_atendimentos > 0 else 0,
                'primeiro_contato': historicos_data[0]['data_hora'] if historicos_data else None,
                'ultimo_contato': historicos_data[-1]['data_hora'] if historicos_data else None,
                'duracao_jornada_dias': None,  # Calcular depois se necessário
            }
        }

        return JsonResponse(response_data)

    except Exception as e:
        import traceback
        logger.error(f"Erro na API de jornada do cliente: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'error': f'Erro ao carregar jornada do cliente: {str(e)}'
        }, status=500)


@login_required
def api_atendimento_em_tempo_real(request):
    """API para acompanhar atendimento em tempo real"""
    try:
        atendimento_id = request.GET.get('atendimento_id')

        if not atendimento_id:
            return JsonResponse({
                'error': 'atendimento_id é obrigatório'
            }, status=400)

        try:
            atendimento = AtendimentoFluxo.objects.select_related(
                'lead', 'fluxo', 'historico_contato'
            ).get(id=atendimento_id)
        except AtendimentoFluxo.DoesNotExist:
            return JsonResponse({'error': 'Atendimento não encontrado'}, status=404)

        # Questão atual detalhada
        questao_atual = atendimento.get_questao_atual_obj()
        questao_data = None
        if questao_atual:
            questao_data = {
                'id': questao_atual.id,
                'indice': questao_atual.indice,
                'titulo': questao_atual.titulo,
                'descricao': questao_atual.descricao,
                'tipo_questao': questao_atual.tipo_questao,
                'tipo_validacao': questao_atual.tipo_validacao,
                'opcoes_resposta': questao_atual.get_opcoes_formatadas(),
                'resposta_padrao': questao_atual.resposta_padrao,
                'permite_voltar': questao_atual.permite_voltar,
                'permite_editar': questao_atual.permite_editar,
            }

        # Próxima questão
        proxima_questao = atendimento.get_proxima_questao()
        proxima_questao_data = None
        if proxima_questao:
            proxima_questao_data = {
                'id': proxima_questao.id,
                'indice': proxima_questao.indice,
                'titulo': proxima_questao.titulo,
            }

        # Todas as questões do fluxo
        todas_questoes = []
        for questao in atendimento.fluxo.get_questoes_ordenadas():
            respondida = str(questao.indice) in atendimento.dados_respostas
            resposta_data = atendimento.dados_respostas.get(str(questao.indice), {})

            todas_questoes.append({
                'id': questao.id,
                'indice': questao.indice,
                'titulo': questao.titulo,
                'tipo_questao': questao.tipo_questao,
                'respondida': respondida,
                'resposta': resposta_data.get('resposta') if respondida else None,
                'valida': resposta_data.get('valida', False) if respondida else None,
                'data_resposta': resposta_data.get('data_resposta') if respondida else None,
            })

        response_data = {
            'atendimento': {
                'id': atendimento.id,
                'status': atendimento.status,
                'status_display': atendimento.get_status_display(),
                'questao_atual': atendimento.questao_atual,
                'total_questoes': atendimento.total_questoes,
                'questoes_respondidas': atendimento.questoes_respondidas,
                'progresso_percentual': atendimento.get_progresso_percentual(),
                'tempo_total': atendimento.tempo_total,
                'tempo_formatado': atendimento.get_tempo_formatado(),
                'data_inicio': atendimento.data_inicio.strftime('%d/%m/%Y %H:%M:%S'),
                'data_ultima_atividade': atendimento.data_ultima_atividade.strftime('%d/%m/%Y %H:%M:%S'),
                'tentativas_atual': atendimento.tentativas_atual,
                'max_tentativas': atendimento.max_tentativas,
            },
            'lead': {
                'id': atendimento.lead.id,
                'nome': atendimento.lead.nome_razaosocial,
                'telefone': atendimento.lead.telefone,
                'email': atendimento.lead.email,
            },
            'fluxo': {
                'id': atendimento.fluxo.id,
                'nome': atendimento.fluxo.nome,
                'tipo_fluxo': atendimento.fluxo.tipo_fluxo,
                'descricao': atendimento.fluxo.descricao,
            },
            'questao_atual': questao_data,
            'proxima_questao': proxima_questao_data,
            'todas_questoes': todas_questoes,
            'pode_avancar': atendimento.pode_avancar(),
            'pode_voltar': atendimento.pode_voltar(),
        }

        return JsonResponse(response_data)

    except Exception as e:
        import traceback
        logger.error(f"Erro na API de tempo real: {str(e)}")
        logger.error(traceback.format_exc())
        return JsonResponse({
            'error': f'Erro ao carregar dados em tempo real: {str(e)}'
        }, status=500)


# ============================================================================
# Funil Insights (migrado de vendas_web/funil_insights.py)
# ============================================================================

def dashboard_funil_insights(request):
    """API para insights detalhados do funil de vendas"""
    try:
        # Parâmetros de período
        periodo = request.GET.get('periodo', 'mes')  # hoje, semana, mes, customizado
        data_inicio_param = request.GET.get('data_inicio')
        data_fim_param = request.GET.get('data_fim')

        # Definir período baseado no parâmetro
        agora = timezone.now()

        if periodo == 'hoje':
            data_inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora
        elif periodo == 'semana':
            inicio_semana = agora.date() - timedelta(days=agora.weekday())
            data_inicio = timezone.make_aware(datetime.combine(inicio_semana, datetime.min.time()))
            data_fim = agora
        elif periodo == 'mes':
            data_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora
        elif periodo == 'customizado' and data_inicio_param and data_fim_param:
            try:
                data_inicio = timezone.make_aware(datetime.strptime(data_inicio_param, '%Y-%m-%d'))
                data_fim = timezone.make_aware(datetime.strptime(data_fim_param, '%Y-%m-%d'))
            except ValueError:
                return JsonResponse({'error': 'Formato de data inválido'}, status=400)
        else:
            # Padrão: último mês
            data_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            data_fim = agora

        # Obter insights do período
        insights = HistoricoContato.get_funil_insights(data_inicio, data_fim)

        # Análise de origem de contatos
        analise_origem = []
        for origem_choice in LeadProspecto.ORIGEM_CHOICES:
            origem_value, origem_label = origem_choice

            contatos_origem = HistoricoContato.objects.filter(
                origem_contato=origem_value,
                data_hora_contato__gte=data_inicio,
                data_hora_contato__lte=data_fim
            )

            total = contatos_origem.count()
            if total > 0:
                finalizados = contatos_origem.filter(
                    status__in=['fluxo_finalizado', 'transferido_humano']
                ).count()
                convertidos = contatos_origem.filter(converteu_lead=True).count()
                vendas = contatos_origem.filter(converteu_venda=True).count()
                valor_total = contatos_origem.filter(converteu_venda=True).aggregate(
                    total=Sum('valor_venda')
                )['total'] or 0

                analise_origem.append({
                    'origem': origem_label,
                    'total_contatos': total,
                    'finalizados': finalizados,
                    'convertidos_lead': convertidos,
                    'vendas_confirmadas': vendas,
                    'valor_total': valor_total,
                    'taxa_finalizacao': round((finalizados / total * 100), 1) if total > 0 else 0,
                    'taxa_conversao_lead': round((convertidos / total * 100), 1) if total > 0 else 0,
                    'taxa_conversao_venda': round((vendas / convertidos * 100), 1) if convertidos > 0 else 0,
                    'ticket_medio': round((valor_total / vendas), 2) if vendas > 0 else 0
                })

        # Análise temporal (por dia do período) - limitado a 30 dias
        analise_temporal = []
        atual = data_inicio
        dias_analisados = 0
        max_dias = 30  # Limitar para não sobrecarregar

        while atual.date() <= data_fim.date() and dias_analisados < max_dias:
            proximo_dia = atual + timedelta(days=1)
            insights_dia = HistoricoContato.get_funil_insights(atual, proximo_dia)

            analise_temporal.append({
                'data': atual.strftime('%d/%m/%Y'),
                'data_iso': atual.strftime('%Y-%m-%d'),
                **insights_dia
            })

            atual = proximo_dia
            dias_analisados += 1

        # Top telefones com mais contatos
        top_telefones = HistoricoContato.objects.filter(
            data_hora_contato__gte=data_inicio,
            data_hora_contato__lte=data_fim
        ).values('telefone').annotate(
            total_contatos=Count('id'),
            total_finalizados=Count('id', filter=Q(status__in=['fluxo_finalizado', 'transferido_humano'])),
            converteu_lead=Count('id', filter=Q(converteu_lead=True)),
            converteu_venda=Count('id', filter=Q(converteu_venda=True)),
            valor_total=Sum('valor_venda')
        ).order_by('-total_contatos')[:10]

        data = {
            'periodo': {
                'tipo': periodo,
                'data_inicio': data_inicio.strftime('%d/%m/%Y'),
                'data_fim': data_fim.strftime('%d/%m/%Y'),
                'data_inicio_iso': data_inicio.strftime('%Y-%m-%d'),
                'data_fim_iso': data_fim.strftime('%Y-%m-%d')
            },
            'insights_gerais': {
                **insights,
                'valor_total_vendas_formatado': f"R$ {insights['valor_total_vendas']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            },
            'analise_origem': analise_origem,
            'analise_temporal': analise_temporal,
            'top_telefones': list(top_telefones)
        }

        return JsonResponse(data)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
