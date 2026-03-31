from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Sum, Q
from datetime import datetime, timedelta
from .models import LeadProspecto, HistoricoContato


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
