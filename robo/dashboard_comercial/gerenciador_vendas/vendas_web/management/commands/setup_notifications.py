"""
Comando para configurar dados iniciais do sistema de notificações
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.notificacoes.models import TipoNotificacao, CanalNotificacao, TemplateNotificacao


class Command(BaseCommand):
    help = 'Configura dados iniciais do sistema de notificações'

    def handle(self, *args, **options):
        self.stdout.write('Configurando sistema de notificações...')
        
        # Criar tipos de notificação
        self.criar_tipos_notificacao()
        
        # Criar canais de notificação
        self.criar_canais_notificacao()
        
        # Criar templates básicos
        self.criar_templates_basicos()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Sistema de notificações configurado com sucesso!')
        )

    def criar_tipos_notificacao(self):
        """Cria tipos de notificação básicos"""
        tipos = [
            {
                'codigo': 'lead_novo',
                'nome': 'Novo Lead',
                'descricao': 'Notificação enviada quando um novo lead é cadastrado no sistema',
                'template_padrao': 'Novo lead recebido: {{ lead.nome }} - {{ lead.empresa }}',
                'prioridade_padrao': 'alta'
            },
            {
                'codigo': 'lead_convertido',
                'nome': 'Lead Convertido',
                'descricao': 'Notificação enviada quando um lead é convertido em prospecto',
                'template_padrao': 'Lead convertido: {{ lead.nome }} foi convertido em prospecto',
                'prioridade_padrao': 'normal'
            },
            {
                'codigo': 'venda_aprovada',
                'nome': 'Venda Aprovada',
                'descricao': 'Notificação enviada quando uma venda é aprovada',
                'template_padrao': 'Venda aprovada: {{ venda.valor }} - {{ venda.cliente }}',
                'prioridade_padrao': 'alta'
            },
            {
                'codigo': 'venda_rejeitada',
                'nome': 'Venda Rejeitada',
                'descricao': 'Notificação enviada quando uma venda é rejeitada',
                'template_padrao': 'Venda rejeitada: {{ venda.valor }} - {{ venda.cliente }}',
                'prioridade_padrao': 'normal'
            },
            {
                'codigo': 'prospecto_aguardando',
                'nome': 'Prospecto Aguardando Validação',
                'descricao': 'Notificação enviada quando um prospecto está aguardando validação',
                'template_padrao': 'Prospecto aguardando validação: {{ prospecto.nome }}',
                'prioridade_padrao': 'alta'
            }
        ]
        
        for tipo_data in tipos:
            tipo, created = TipoNotificacao.objects.get_or_create(
                codigo=tipo_data['codigo'],
                defaults=tipo_data
            )
            if created:
                self.stdout.write(f'  ✅ Criado tipo: {tipo.nome}')
            else:
                self.stdout.write(f'  ⚠️  Tipo já existe: {tipo.nome}')

    def criar_canais_notificacao(self):
        """Cria canais de notificação básicos"""
        canais = [
            {
                'codigo': 'whatsapp',
                'nome': 'WhatsApp',
                'icone': 'fab fa-whatsapp',
                'configuracao': {
                    'api_url': 'https://automation-n8n.v4riem.easypanel.host/webhook/5a88a51b-f099-4ea9-afb5-68a10254bcdd',
                    'template_format': 'text',
                    'max_length': 4096
                }
            },
            {
                'codigo': 'webhook',
                'nome': 'Webhook',
                'icone': 'fas fa-link',
                'configuracao': {
                    'method': 'POST',
                    'content_type': 'application/json',
                    'timeout': 30
                }
            }
        ]
        
        for canal_data in canais:
            canal, created = CanalNotificacao.objects.get_or_create(
                codigo=canal_data['codigo'],
                defaults=canal_data
            )
            if created:
                self.stdout.write(f'  ✅ Criado canal: {canal.nome}')
            else:
                self.stdout.write(f'  ⚠️  Canal já existe: {canal.nome}')

    def criar_templates_basicos(self):
        """Cria templates básicos para email"""
        try:
            tipo_lead_novo = TipoNotificacao.objects.get(codigo='lead_novo')
            canal_email = CanalNotificacao.objects.get(codigo='email')
            
            template, created = TemplateNotificacao.objects.get_or_create(
                tipo_notificacao=tipo_lead_novo,
                canal=canal_email,
                defaults={
                    'nome': 'Template Email - Novo Lead',
                    'assunto': '🎯 Novo Lead Recebido - {{ lead.nome }}',
                    'corpo_html': '''
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                        <h2 style="color: #1F3D59;">🎯 Novo Lead Recebido!</h2>
                        <p>Olá <strong>{{ usuario.nome }}</strong>,</p>
                        <p>Um novo lead foi cadastrado no sistema:</p>
                        <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; margin: 1rem 0;">
                            <p><strong>Nome:</strong> {{ lead.nome }}</p>
                            <p><strong>Empresa:</strong> {{ lead.empresa }}</p>
                            <p><strong>Email:</strong> {{ lead.email }}</p>
                            <p><strong>Telefone:</strong> {{ lead.telefone }}</p>
                            <p><strong>Origem:</strong> {{ lead.origem }}</p>
                        </div>
                        <p>Acesse o sistema para mais detalhes: <a href="{{ site_url }}/leads/">Ver Leads</a></p>
                        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0;">
                        <p style="color: #6b7280; font-size: 0.9rem;">
                            Megalink - Sistema de Gestão Comercial<br>
                            <a href="{{ site_url }}">{{ site_url }}</a>
                        </p>
                    </div>
                    ''',
                    'corpo_texto': '''
                    Novo Lead Recebido!
                    
                    Olá {{ usuario.nome }},
                    
                    Um novo lead foi cadastrado no sistema:
                    
                    Nome: {{ lead.nome }}
                    Empresa: {{ lead.empresa }}
                    Email: {{ lead.email }}
                    Telefone: {{ lead.telefone }}
                    Origem: {{ lead.origem }}
                    
                    Acesse o sistema para mais detalhes: {{ site_url }}/leads/
                    
                    ---
                    Megalink - Sistema de Gestão Comercial
                    {{ site_url }}
                    ''',
                    'variaveis': ['lead.nome', 'lead.empresa', 'lead.email', 'lead.telefone', 'lead.origem', 'usuario.nome', 'site_url']
                }
            )
            
            if created:
                self.stdout.write(f'  ✅ Criado template: {template.nome}')
            else:
                self.stdout.write(f'  ⚠️  Template já existe: {template.nome}')
                
        except (TipoNotificacao.DoesNotExist, CanalNotificacao.DoesNotExist) as e:
            self.stdout.write(f'  ⚠️  Erro ao criar template: {e}')
