"""
Configurações personalizadas para o Admin dos Fluxos de Atendimento
Este arquivo contém configurações adicionais e personalizações para melhorar a experiência do usuário
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe


def get_admin_url(model, action='changelist'):
    """Gera URL do admin para um modelo específico"""
    try:
        return reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_{action}')
    except:
        return "#"


def create_dashboard_widget(title, content, color="#3498db", icon="📊"):
    """Cria um widget visual para o dashboard"""
    html = f"""
    <div style="background:{color};color:#fff;padding:15px;border-radius:8px;margin:10px 0;">
        <h3 style="margin:0 0 10px 0;font-size:16px;">
            {icon} {title}
        </h3>
        <div style="font-size:14px;">
            {content}
        </div>
    </div>
    """
    return format_html(html)


def create_progress_bar(value, max_value, label="", color="#2ecc71"):
    """Cria uma barra de progresso visual"""
    if max_value == 0:
        percentage = 0
    else:
        percentage = min(100, (value / max_value) * 100)
    
    html = f"""
    <div style="margin:5px 0;">
        <div style="display:flex;justify-content:space-between;margin-bottom:5px;">
            <span style="font-size:12px;color:#666;">{label}</span>
            <span style="font-size:12px;color:#666;">{value}/{max_value} ({percentage:.1f}%)</span>
        </div>
        <div style="background:#f0f0f0;height:20px;border-radius:10px;overflow:hidden;">
            <div style="background:{color};height:100%;width:{percentage}%;transition:width 0.3s ease;"></div>
        </div>
    </div>
    """
    return format_html(html)


def create_status_badge(status, status_choices, colors=None):
    """Cria um badge de status colorido"""
    if colors is None:
        colors = {
            'ativo': '#2ecc71',
            'inativo': '#e74c3c',
            'pendente': '#f39c12',
            'processando': '#3498db',
            'completado': '#27ae60',
            'erro': '#c0392b',
            'rascunho': '#95a5a6',
            'teste': '#f39c12',
        }
    
    color = colors.get(status, '#7f8c8d')
    label = dict(status_choices).get(status, status)
    
    html = f"""
    <span style="padding:2px 8px;border-radius:12px;background:{color};color:#fff;font-size:11px;font-weight:bold;">
        {label}
    </span>
    """
    return format_html(html)


def create_metric_card(title, value, subtitle="", icon="📈", color="#3498db"):
    """Cria um card de métrica visual"""
    html = f"""
    <div style="background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:15px;margin:10px 0;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
        <div style="display:flex;align-items:center;margin-bottom:10px;">
            <span style="font-size:24px;margin-right:10px;">{icon}</span>
            <div>
                <h4 style="margin:0;color:{color};font-size:16px;">{title}</h4>
                {f'<p style="margin:0;color:#666;font-size:12px;">{subtitle}</p>' if subtitle else ''}
            </div>
        </div>
        <div style="font-size:24px;font-weight:bold;color:#2c3e50;">
            {value}
        </div>
    </div>
    """
    return format_html(html)


def create_action_button(text, url, color="#3498db", icon="🔗"):
    """Cria um botão de ação visual"""
    html = f"""
    <a href="{url}" style="display:inline-block;background:{color};color:#fff;padding:8px 16px;text-decoration:none;border-radius:6px;font-size:12px;font-weight:bold;margin:5px;">
        {icon} {text}
    </a>
    """
    return format_html(html)


def create_info_panel(title, content, type="info"):
    """Cria um painel de informação"""
    colors = {
        "info": "#3498db",
        "success": "#2ecc71",
        "warning": "#f39c12",
        "error": "#e74c3c"
    }
    
    color = colors.get(type, "#3498db")
    
    html = f"""
    <div style="background:#f8f9fa;border-left:4px solid {color};padding:15px;margin:10px 0;border-radius:4px;">
        <h4 style="margin:0 0 10px 0;color:{color};">{title}</h4>
        <div style="color:#495057;line-height:1.5;">
            {content}
        </div>
    </div>
    """
    return format_html(html)


def create_table_summary(data, title="Resumo"):
    """Cria uma tabela de resumo visual"""
    if not data:
        return "Nenhum dado disponível"
    
    html = f"""
    <div style="background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:15px;margin:10px 0;">
        <h4 style="margin:0 0 15px 0;color:#495057;">{title}</h4>
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#f8f9fa;">
                    <th style="padding:8px;text-align:left;border-bottom:1px solid #dee2e6;font-weight:bold;">Item</th>
                    <th style="padding:8px;text-align:right;border-bottom:1px solid #dee2e6;font-weight:bold;">Valor</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for item, value in data.items():
        html += f"""
                <tr>
                    <td style="padding:8px;border-bottom:1px solid #f0f0f0;">{item}</td>
                    <td style="padding:8px;border-bottom:1px solid #f0f0f0;text-align:right;font-weight:bold;">{value}</td>
                </tr>
        """
    
    html += """
            </tbody>
        </table>
    </div>
    """
    
    return format_html(html)


def create_quick_stats(fluxo):
    """Cria estatísticas rápidas para um fluxo"""
    if not fluxo.pk:
        return "Salve o fluxo para ver estatísticas"
    
    estatisticas = fluxo.get_estatisticas()
    
    stats_data = {
        "Total de Atendimentos": estatisticas['total_atendimentos'],
        "Completados": estatisticas['atendimentos_completados'],
        "Taxa de Completação": f"{estatisticas['taxa_completacao']}%",
        "Tempo Médio": f"{estatisticas['tempo_medio_segundos']}s",
        "Questões Ativas": fluxo.get_total_questoes()
    }
    
    return create_table_summary(stats_data, "📊 Estatísticas do Fluxo")


def create_fluxo_preview(fluxo):
    """Cria uma prévia visual do fluxo"""
    if not fluxo.pk:
        return "Salve o fluxo para ver a prévia"
    
    questoes = fluxo.get_questoes_ordenadas()
    
    html = f"""
    <div style="background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:15px;margin:10px 0;">
        <h4 style="margin:0 0 15px 0;color:#495057;">🔍 Prévia do Fluxo</h4>
        <div style="max-height:300px;overflow-y:auto;">
    """
    
    for questao in questoes:
        tipo_color = {
            'texto': '#3498db',
            'numero': '#2ecc71',
            'email': '#9b59b6',
            'telefone': '#f39c12',
            'select': '#8e44ad',
            'multiselect': '#d35400',
            'boolean': '#e74c3c',
            'escala': '#f1c40f',
        }.get(questao.tipo_questao, '#7f8c8d')
        
        html += f"""
            <div style="border-left:3px solid {tipo_color};padding:8px;margin:5px 0;background:#f8f9fa;">
                <strong>Q{questao.indice}:</strong> {questao.titulo}<br>
                <span style="font-size:11px;color:#666;">
                    Tipo: {questao.get_tipo_questao_display()} | 
                    Validação: {questao.get_tipo_validacao_display()}
                </span>
            </div>
        """
    
    html += """
        </div>
    </div>
    """
    
    return format_html(html)


def create_atendimento_summary(atendimento):
    """Cria um resumo visual do atendimento"""
    if not atendimento.pk:
        return "Salve o atendimento para ver o resumo"
    
    progresso = atendimento.get_progresso_percentual()
    
    html = f"""
    <div style="background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:15px;margin:10px 0;">
        <h4 style="margin:0 0 15px 0;color:#495057;">📱 Resumo do Atendimento</h4>
        
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-bottom:15px;">
            <div>
                <strong>Status:</strong> {atendimento.get_status_display()}<br>
                <strong>Questão Atual:</strong> {atendimento.questao_atual}<br>
                <strong>Progresso:</strong> {progresso}%
            </div>
            <div>
                <strong>Questões Respondidas:</strong> {atendimento.questoes_respondidas}/{atendimento.total_questoes}<br>
                <strong>Tempo Total:</strong> {atendimento.get_tempo_formatado()}<br>
                <strong>Score:</strong> {atendimento.score_qualificacao or 'N/A'}/10
            </div>
        </div>
        
        {create_progress_bar(atendimento.questoes_respondidas, atendimento.total_questoes, "Progresso")}
    </div>
    """
    
    return format_html(html)


# Configurações para personalizar o admin
ADMIN_CUSTOMIZATIONS = {
    'fluxo_atendimento': {
        'list_display_extra': ['get_quick_actions'],
        'list_filter_extra': ['criado_por'],
        'search_fields_extra': ['nome', 'descricao'],
        'actions_extra': ['exportar_fluxos', 'importar_fluxos'],
    },
    'questao_fluxo': {
        'list_display_extra': ['get_fluxo_info'],
        'list_filter_extra': ['fluxo__tipo_fluxo'],
        'search_fields_extra': ['titulo', 'fluxo__nome'],
    },
    'atendimento_fluxo': {
        'list_display_extra': ['get_lead_info'],
        'list_filter_extra': ['fluxo__tipo_fluxo'],
        'search_fields_extra': ['lead__nome_razaosocial', 'fluxo__nome'],
        'actions_extra': ['exportar_atendimentos'],
    },
    'resposta_questao': {
        'list_display_extra': ['get_atendimento_info'],
        'list_filter_extra': ['questao__tipo_questao'],
        'search_fields_extra': ['resposta', 'questao__titulo'],
    }
}


def apply_admin_customizations():
    """Aplica as customizações do admin"""
    # Esta função pode ser chamada no admin.py para aplicar as customizações
    pass


# Funções utilitárias para o admin
def get_admin_actions():
    """Retorna ações personalizadas para o admin"""
    return {
        'exportar_fluxos': {
            'label': 'Exportar Fluxos',
            'description': 'Exporta fluxos selecionados em formato JSON',
            'function': lambda request, queryset: export_fluxos_json(request, queryset)
        },
        'importar_fluxos': {
            'label': 'Importar Fluxos',
            'description': 'Importa fluxos de arquivo JSON',
            'function': lambda request, queryset: import_fluxos_json(request, queryset)
        },
        'exportar_atendimentos': {
            'label': 'Exportar Atendimentos',
            'description': 'Exporta atendimentos selecionados em CSV',
            'function': lambda request, queryset: export_atendimentos_csv(request, queryset)
        }
    }


def export_fluxos_json(request, queryset):
    """Exporta fluxos em formato JSON"""
    import json
    from django.http import HttpResponse
    
    data = []
    for fluxo in queryset:
        fluxo_data = {
            'nome': fluxo.nome,
            'descricao': fluxo.descricao,
            'tipo_fluxo': fluxo.tipo_fluxo,
            'configuracoes': {
                'max_tentativas': fluxo.max_tentativas,
                'tempo_limite_minutos': fluxo.tempo_limite_minutos,
                'permite_pular_questoes': fluxo.permite_pular_questoes
            },
            'questoes': []
        }
        
        for questao in fluxo.questoes.all():
            questao_data = {
                'indice': questao.indice,
                'titulo': questao.titulo,
                'descricao': questao.descricao,
                'tipo_questao': questao.tipo_questao,
                'tipo_validacao': questao.tipo_validacao,
                'opcoes_resposta': questao.opcoes_resposta,
                'regex_validacao': questao.regex_validacao,
                'tamanho_minimo': questao.tamanho_minimo,
                'tamanho_maximo': questao.tamanho_maximo,
                'valor_minimo': questao.valor_minimo,
                'valor_maximo': questao.valor_maximo,
                'permite_voltar': questao.permite_voltar,
                'permite_editar': questao.permite_editar
            }
            fluxo_data['questoes'].append(questao_data)
        
        data.append(fluxo_data)
    
    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json; charset=utf-8'
    )
    response['Content-Disposition'] = 'attachment; filename="fluxos_export.json"'
    return response


def export_atendimentos_csv(request, queryset):
    """Exporta atendimentos em formato CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="atendimentos_export.csv"'
    
    writer = csv.writer(response)
    headers = [
        'ID', 'Lead', 'Fluxo', 'Status', 'Questão Atual', 'Progresso (%)',
        'Questões Respondidas', 'Tempo Total (s)', 'Score', 'Data Início', 'Data Conclusão'
    ]
    writer.writerow(headers)
    
    for obj in queryset:
        writer.writerow([
            obj.id,
            obj.lead.nome_razaosocial if obj.lead else '',
            obj.fluxo.nome if obj.fluxo else '',
            obj.get_status_display(),
            obj.questao_atual,
            obj.get_progresso_percentual(),
            obj.questoes_respondidas,
            obj.tempo_total or 0,
            obj.score_qualificacao or '',
            obj.data_inicio.strftime('%d/%m/%Y %H:%M') if obj.data_inicio else '',
            obj.data_conclusao.strftime('%d/%m/%Y %H:%M') if obj.data_conclusao else ''
        ])
    
    return response


def import_fluxos_json(request, queryset):
    """Importa fluxos de arquivo JSON"""
    # Esta função seria implementada para importar fluxos
    # Por enquanto, apenas retorna uma mensagem
    from django.contrib import messages
    messages.info(request, "Funcionalidade de importação será implementada em breve.")
    return None
