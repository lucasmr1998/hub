"""
Comando para testar as melhorias implementadas no sistema de leads
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from vendas_web.models import LeadProspecto, Prospecto, HistoricoContato
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Testa as novas funcionalidades implementadas no sistema de leads'

    def add_arguments(self, parser):
        parser.add_argument(
            '--criar-dados',
            action='store_true',
            help='Cria dados de teste para as novas funcionalidades'
        )

    def handle(self, *args, **options):
        if options['criar_dados']:
            self.criar_dados_teste()
        
        self.testar_novos_metodos()
        self.stdout.write(
            self.style.SUCCESS('✅ Teste das melhorias concluído com sucesso!')
        )

    def criar_dados_teste(self):
        """Cria dados de teste para as novas funcionalidades"""
        self.stdout.write("📊 Criando dados de teste...")

        # Criar alguns leads com os novos campos
        leads_teste = [
            {
                'nome_razaosocial': 'Empresa Teste Melhorias',
                'email': 'teste.melhorias@email.com',
                'telefone': '+5511999999999',
                'empresa': 'Tech Solutions',
                'valor': Decimal('2500.00'),
                'origem': 'site',
                'canal_entrada': 'site',
                'tipo_entrada': 'cadastro_site',
                'custo_aquisicao': Decimal('150.00'),
            },
            {
                'nome_razaosocial': 'Lead WhatsApp Teste',
                'email': 'whatsapp.teste@email.com',
                'telefone': '+5511888888888',
                'origem': 'whatsapp',
                'canal_entrada': 'whatsapp',
                'tipo_entrada': 'contato_whatsapp',
                'custo_aquisicao': Decimal('80.00'),
            }
        ]

        for lead_data in leads_teste:
            lead, created = LeadProspecto.objects.get_or_create(
                email=lead_data['email'],
                defaults=lead_data
            )
            if created:
                # Calcular score automaticamente
                lead.score_qualificacao = lead.calcular_score_qualificacao()
                lead.save()
                self.stdout.write(f"  ✅ Lead criado: {lead.nome_razaosocial}")

    def testar_novos_metodos(self):
        """Testa os novos métodos implementados"""
        self.stdout.write("🧪 Testando novos métodos...")

        # Testar métodos do LeadProspecto
        leads = LeadProspecto.objects.all()[:5]
        
        for lead in leads:
            # Testar cálculo de score
            score_original = lead.score_qualificacao
            score_calculado = lead.calcular_score_qualificacao()
            
            self.stdout.write(
                f"  📊 {lead.nome_razaosocial}:"
            )
            self.stdout.write(
                f"     Score original: {score_original} | Calculado: {score_calculado}"
            )
            self.stdout.write(
                f"     Pode reprocessar: {lead.pode_reprocessar()}"
            )
            self.stdout.write(
                f"     Qualificação: {lead.get_score_qualificacao_display()}"
            )
            
            # Testar canal automático
            if not lead.canal_entrada:
                lead.definir_canal_entrada_automatico()
                self.stdout.write(f"     Canal definido automaticamente: {lead.canal_entrada}")

        # Testar métodos do Prospecto
        prospectos = Prospecto.objects.all()[:3]
        
        for prospecto in prospectos:
            # Calcular score de conversão
            score_conversao = prospecto.calcular_score_conversao_automatico()
            prospecto.score_conversao = score_conversao
            prospecto.save()
            
            self.stdout.write(
                f"  🎯 {prospecto.nome_prospecto}:"
            )
            self.stdout.write(
                f"     Score conversão: {prospecto.get_score_conversao_display()}"
            )
            self.stdout.write(
                f"     Pode reprocessar: {prospecto.pode_reprocessar()}"
            )

        # Testar novos status
        self.stdout.write("  📋 Novos status disponíveis:")
        
        # HistoricoContato
        novos_status_contato = [
            'venda_sem_viabilidade', 'cliente_desistiu', 
            'aguardando_validacao', 'followup_agendado', 'nao_qualificado'
        ]
        
        for status_code, status_name in HistoricoContato.STATUS_CHOICES:
            if status_code in novos_status_contato:
                self.stdout.write(f"     ✅ HistoricoContato: {status_name}")

        # Prospecto
        novos_status_prospecto = [
            'aguardando_validacao', 'validacao_aprovada', 'validacao_rejeitada'
        ]
        
        for status_code, status_name in Prospecto.STATUS_CHOICES:
            if status_code in novos_status_prospecto:
                self.stdout.write(f"     ✅ Prospecto: {status_name}")

        # LeadProspecto
        novos_status_api = ['aguardando_retry', 'processamento_manual']
        
        for status_code, status_name in LeadProspecto.STATUS_API_CHOICES:
            if status_code in novos_status_api:
                self.stdout.write(f"     ✅ LeadProspecto API: {status_name}")

    def demonstrar_fluxo_unificado(self):
        """Demonstra o novo fluxo unificado"""
        self.stdout.write("🔄 Demonstrando fluxo unificado...")

        # Simular entrada por diferentes canais
        canais_teste = [
            ('site', 'cadastro_site'),
            ('whatsapp', 'contato_whatsapp'),
            ('telefone', 'telefone'),
            ('facebook', 'formulario')
        ]

        for origem, tipo_entrada in canais_teste:
            lead = LeadProspecto.objects.create(
                nome_razaosocial=f"Cliente {origem.title()}",
                email=f"cliente.{origem}@teste.com",
                telefone=f"+5511{random.randint(100000000, 999999999)}",
                origem=origem,
                canal_entrada=origem,
                tipo_entrada=tipo_entrada,
                custo_aquisicao=Decimal(str(random.uniform(50, 200)))
            )
            
            # Calcular score automaticamente
            lead.score_qualificacao = lead.calcular_score_qualificacao()
            lead.save()
            
            self.stdout.write(f"  ✅ Lead criado via {origem}: Score {lead.score_qualificacao}")

            # Se for WhatsApp, criar histórico de contato
            if origem == 'whatsapp':
                contato = HistoricoContato.objects.create(
                    lead=lead,
                    telefone=lead.telefone,
                    status='fluxo_inicializado',
                    nome_contato=lead.nome_razaosocial,
                    origem_contato=origem
                )
                self.stdout.write(f"     📞 Histórico de contato criado")

            # Simular processamento na API
            if random.choice([True, False]):
                lead.status_api = 'sucesso'
                lead.save()
                
                # Criar prospecto
                prospecto = Prospecto.objects.create(
                    lead=lead,
                    nome_prospecto=lead.nome_razaosocial,
                    status='processado'
                )
                
                # Calcular score de conversão
                prospecto.atualizar_score_conversao()
                
                self.stdout.write(f"     🎯 Prospecto criado: {prospecto.get_score_conversao_display()}")
