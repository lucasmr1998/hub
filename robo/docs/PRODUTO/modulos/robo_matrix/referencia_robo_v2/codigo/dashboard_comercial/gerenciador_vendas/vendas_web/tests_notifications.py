"""
Testes para o sistema de notificações
"""
import json
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock

from .models import (
    TipoNotificacao, CanalNotificacao, PreferenciaNotificacao, 
    Notificacao, TemplateNotificacao
)
from .services.notification_service import NotificationService


class NotificationModelsTest(TestCase):
    """Testes para os modelos de notificação"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.tipo = TipoNotificacao.objects.create(
            codigo='teste',
            nome='Notificação de Teste',
            descricao='Teste de notificação',
            prioridade_padrao='normal',
            ativo=True
        )
        
        self.canal = CanalNotificacao.objects.create(
            codigo='email',
            nome='Email',
            icone='fas fa-envelope',
            ativo=True
        )
    
    def test_tipo_notificacao_creation(self):
        """Testa criação de tipo de notificação"""
        self.assertEqual(self.tipo.codigo, 'teste')
        self.assertEqual(self.tipo.nome, 'Notificação de Teste')
        self.assertTrue(self.tipo.ativo)
        self.assertEqual(self.tipo.prioridade_padrao, 'normal')
    
    def test_canal_notificacao_creation(self):
        """Testa criação de canal de notificação"""
        self.assertEqual(self.canal.codigo, 'email')
        self.assertEqual(self.canal.nome, 'Email')
        self.assertTrue(self.canal.ativo)
    
    def test_preferencia_notificacao_creation(self):
        """Testa criação de preferência de notificação"""
        preferencia = PreferenciaNotificacao.objects.create(
            usuario=self.user,
            tipo_notificacao=self.tipo,
            canal_preferido=self.canal,
            ativo=True,
            horario_inicio='08:00',
            horario_fim='18:00',
            dias_semana=[0, 1, 2, 3, 4]  # Segunda a sexta
        )
        
        self.assertEqual(preferencia.usuario, self.user)
        self.assertEqual(preferencia.tipo_notificacao, self.tipo)
        self.assertEqual(preferencia.canal_preferido, self.canal)
        self.assertTrue(preferencia.ativo)
        self.assertEqual(preferencia.dias_semana, [0, 1, 2, 3, 4])
    
    def test_notificacao_creation(self):
        """Testa criação de notificação"""
        notificacao = Notificacao.objects.create(
            tipo=self.tipo,
            canal=self.canal,
            destinatario=self.user,
            titulo='Teste',
            mensagem='Mensagem de teste',
            status='pendente',
            prioridade='normal'
        )
        
        self.assertEqual(notificacao.tipo, self.tipo)
        self.assertEqual(notificacao.canal, self.canal)
        self.assertEqual(notificacao.destinatario, self.user)
        self.assertEqual(notificacao.status, 'pendente')
        self.assertEqual(notificacao.prioridade, 'normal')
    
    def test_template_notificacao_creation(self):
        """Testa criação de template de notificação"""
        template = TemplateNotificacao.objects.create(
            tipo_notificacao=self.tipo,
            canal=self.canal,
            nome='Template de Teste',
            assunto='Assunto: {{ nome }}',
            corpo_texto='Olá {{ nome }}, sua venda foi aprovada!',
            variaveis=['nome', 'valor'],
            ativo=True
        )
        
        self.assertEqual(template.tipo_notificacao, self.tipo)
        self.assertEqual(template.canal, self.canal)
        self.assertEqual(template.nome, 'Template de Teste')
        self.assertIn('nome', template.variaveis)
        self.assertIn('valor', template.variaveis)


class NotificationServiceTest(TestCase):
    """Testes para o serviço de notificações"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.tipo = TipoNotificacao.objects.create(
            codigo='teste',
            nome='Notificação de Teste',
            descricao='Teste de notificação',
            prioridade_padrao='normal',
            ativo=True
        )
        
        self.canal = CanalNotificacao.objects.create(
            codigo='email',
            nome='Email',
            icone='fas fa-envelope',
            ativo=True
        )
        
        self.template = TemplateNotificacao.objects.create(
            tipo_notificacao=self.tipo,
            canal=self.canal,
            nome='Template de Teste',
            assunto='Assunto: {{ nome }}',
            corpo_texto='Olá {{ nome }}, sua venda foi aprovada!',
            variaveis=['nome', 'valor'],
            ativo=True
        )
        
        self.service = NotificationService()
    
    @patch('requests.post')
    def test_enviar_notificacao_success(self, mock_post):
        """Testa envio de notificação com sucesso"""
        # Mock da resposta do N8N
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True, 'executionId': '123'}
        mock_post.return_value = mock_response
        
        # Dados de contexto
        dados_contexto = {
            'nome': 'João Silva',
            'valor': 'R$ 100,00'
        }
        
        # Enviar notificação
        notificacoes = self.service.enviar_notificacao(
            tipo_codigo='teste',
            destinatarios=[self.user],
            dados_contexto=dados_contexto
        )
        
        # Verificações
        self.assertEqual(len(notificacoes), 1)
        notificacao = notificacoes[0]
        self.assertEqual(notificacao.tipo, self.tipo)
        self.assertEqual(notificacao.canal, self.canal)
        self.assertEqual(notificacao.destinatario, self.user)
        self.assertEqual(notificacao.status, 'enviada')
        self.assertIn('João Silva', notificacao.titulo)
        self.assertIn('João Silva', notificacao.mensagem)
    
    @patch('requests.post')
    def test_enviar_notificacao_failure(self, mock_post):
        """Testa envio de notificação com falha"""
        # Mock da resposta de erro do N8N
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {'error': 'Erro interno'}
        mock_post.return_value = mock_response
        
        # Enviar notificação
        notificacoes = self.service.enviar_notificacao(
            tipo_codigo='teste',
            destinatarios=[self.user],
            dados_contexto={}
        )
        
        # Verificações
        self.assertEqual(len(notificacoes), 1)
        notificacao = notificacoes[0]
        self.assertEqual(notificacao.status, 'falhou')
        self.assertIsNotNone(notificacao.erro_detalhes)
    
    def test_renderizar_template(self):
        """Testa renderização de template"""
        dados_contexto = {
            'nome': 'Maria Santos',
            'valor': 'R$ 250,00'
        }
        
        assunto, corpo = self.service._renderizar_template(
            self.template, dados_contexto
        )
        
        self.assertEqual(assunto, 'Assunto: Maria Santos')
        self.assertEqual(corpo, 'Olá Maria Santos, sua venda foi aprovada!')
    
    def test_obter_estatisticas(self):
        """Testa obtenção de estatísticas"""
        # Criar algumas notificações
        Notificacao.objects.create(
            tipo=self.tipo,
            canal=self.canal,
            destinatario=self.user,
            titulo='Teste 1',
            mensagem='Mensagem 1',
            status='enviada'
        )
        
        Notificacao.objects.create(
            tipo=self.tipo,
            canal=self.canal,
            destinatario=self.user,
            titulo='Teste 2',
            mensagem='Mensagem 2',
            status='falhou'
        )
        
        stats = self.service.obter_estatisticas()
        
        self.assertEqual(stats['total_notificacoes'], 2)
        self.assertEqual(stats['notificacoes_enviadas'], 1)
        self.assertEqual(stats['notificacoes_falharam'], 1)
        self.assertEqual(stats['taxa_sucesso'], 50.0)


class NotificationViewsTest(TestCase):
    """Testes para as views de notificação"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.tipo = TipoNotificacao.objects.create(
            codigo='teste',
            nome='Notificação de Teste',
            descricao='Teste de notificação',
            prioridade_padrao='normal',
            ativo=True
        )
        
        self.canal = CanalNotificacao.objects.create(
            codigo='email',
            nome='Email',
            icone='fas fa-envelope',
            ativo=True
        )
    
    def test_configuracoes_notificacoes_view_requires_permission(self):
        """Testa que a view de configurações requer permissão"""
        # Usuário sem permissão
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('vendas_web:configuracoes_notificacoes'))
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_configuracoes_notificacoes_view_with_permission(self):
        """Testa acesso à view de configurações com permissão"""
        self.client.login(username='admin', password='adminpass123')
        response = self.client.get(reverse('vendas_web:configuracoes_notificacoes'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sistema de Notificações')
    
    def test_api_notificacao_enviar(self):
        """Testa API de envio de notificação"""
        self.client.login(username='admin', password='adminpass123')
        
        data = {
            'tipo': 'teste',
            'destinatarios': [self.user.id],
            'dados_contexto': {'nome': 'João'}
        }
        
        with patch('vendas_web.services.notification_service.NotificationService.enviar_notificacao') as mock_enviar:
            mock_enviar.return_value = []
            
            response = self.client.post(
                reverse('vendas_web:api_notificacao_enviar'),
                data=json.dumps(data),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertTrue(response_data['success'])
    
    def test_api_notificacoes_listar(self):
        """Testa API de listagem de notificações"""
        self.client.login(username='testuser', password='testpass123')
        
        # Criar notificação
        Notificacao.objects.create(
            tipo=self.tipo,
            canal=self.canal,
            destinatario=self.user,
            titulo='Teste',
            mensagem='Mensagem de teste',
            status='enviada'
        )
        
        response = self.client.get(reverse('vendas_web:api_notificacoes_listar'))
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(len(response_data['notificacoes']), 1)
    
    def test_api_notificacoes_preferencias_get(self):
        """Testa API de preferências (GET)"""
        self.client.login(username='testuser', password='testpass123')
        
        # Criar preferência
        PreferenciaNotificacao.objects.create(
            usuario=self.user,
            tipo_notificacao=self.tipo,
            canal_preferido=self.canal,
            ativo=True
        )
        
        response = self.client.get(reverse('vendas_web:api_notificacoes_preferencias'))
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(len(response_data['preferencias']), 1)
    
    def test_api_notificacoes_preferencias_post(self):
        """Testa API de preferências (POST)"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'tipo_notificacao_id': self.tipo.id,
            'canal_preferido_id': self.canal.id,
            'ativo': True,
            'horario_inicio': '08:00',
            'horario_fim': '18:00',
            'dias_semana': [0, 1, 2, 3, 4]
        }
        
        response = self.client.post(
            reverse('vendas_web:api_notificacoes_preferencias'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Verificar se a preferência foi criada
        preferencia = PreferenciaNotificacao.objects.get(
            usuario=self.user,
            tipo_notificacao=self.tipo,
            canal_preferido=self.canal
        )
        self.assertTrue(preferencia.ativo)


class NotificationSignalsTest(TestCase):
    """Testes para os sinais de notificação"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.tipo = TipoNotificacao.objects.create(
            codigo='novo_lead',
            nome='Novo Lead',
            descricao='Notificação de novo lead',
            prioridade_padrao='normal',
            ativo=True
        )
        
        self.canal = CanalNotificacao.objects.create(
            codigo='email',
            nome='Email',
            icone='fas fa-envelope',
            ativo=True
        )
    
    @patch('vendas_web.services.notification_service.NotificationService.enviar_notificacao')
    def test_lead_created_signal(self, mock_enviar):
        """Testa sinal de criação de lead"""
        from .models import LeadProspecto
        
        # Criar lead
        lead = LeadProspecto.objects.create(
            nome_razaosocial='João Silva',
            email='joao@example.com',
            telefone='11999999999',
            origem='site'
        )
        
        # Verificar se a notificação foi enviada
        mock_enviar.assert_called_once()
        call_args = mock_enviar.call_args
        self.assertEqual(call_args[1]['tipo_codigo'], 'novo_lead')
    
    @patch('vendas_web.services.notification_service.NotificationService.enviar_notificacao')
    def test_prospecto_created_signal(self, mock_enviar):
        """Testa sinal de criação de prospecto"""
        from .models import Prospecto
        
        # Criar prospecto
        prospecto = Prospecto.objects.create(
            nome_razaosocial='Maria Santos',
            email='maria@example.com',
            telefone='11888888888',
            origem='site'
        )
        
        # Verificar se a notificação foi enviada
        mock_enviar.assert_called_once()
        call_args = mock_enviar.call_args
        self.assertEqual(call_args[1]['tipo_codigo'], 'novo_prospecto')


class NotificationManagementCommandsTest(TestCase):
    """Testes para os comandos de gerenciamento"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_setup_notifications_command(self):
        """Testa comando de configuração inicial"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('setup_notifications', stdout=out)
        
        # Verificar se os tipos foram criados
        self.assertTrue(TipoNotificacao.objects.filter(codigo='novo_lead').exists())
        self.assertTrue(TipoNotificacao.objects.filter(codigo='venda_aprovada').exists())
        
        # Verificar se os canais foram criados
        self.assertTrue(CanalNotificacao.objects.filter(codigo='email').exists())
        self.assertTrue(CanalNotificacao.objects.filter(codigo='whatsapp').exists())
    
    @patch('vendas_web.services.notification_service.NotificationService.processar_notificacoes_pendentes')
    def test_process_notifications_command(self, mock_processar):
        """Testa comando de processamento de notificações"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('process_notifications', stdout=out)
        
        # Verificar se o método foi chamado
        mock_processar.assert_called_once()
    
    def test_cleanup_notifications_command(self):
        """Testa comando de limpeza de notificações"""
        from django.core.management import call_command
        from io import StringIO
        
        # Criar notificação antiga
        tipo = TipoNotificacao.objects.create(
            codigo='teste',
            nome='Teste',
            ativo=True
        )
        
        canal = CanalNotificacao.objects.create(
            codigo='email',
            nome='Email',
            ativo=True
        )
        
        notificacao = Notificacao.objects.create(
            tipo=tipo,
            canal=canal,
            destinatario=self.user,
            titulo='Teste',
            mensagem='Teste',
            status='enviada',
            data_criacao=timezone.now() - timedelta(days=100)
        )
        
        out = StringIO()
        call_command('cleanup_notifications', stdout=out)
        
        # Verificar se a notificação foi removida
        self.assertFalse(Notificacao.objects.filter(id=notificacao.id).exists())


class NotificationIntegrationTest(TestCase):
    """Testes de integração do sistema de notificações"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.tipo = TipoNotificacao.objects.create(
            codigo='teste',
            nome='Notificação de Teste',
            descricao='Teste de notificação',
            prioridade_padrao='normal',
            ativo=True
        )
        
        self.canal = CanalNotificacao.objects.create(
            codigo='email',
            nome='Email',
            icone='fas fa-envelope',
            ativo=True
        )
        
        self.template = TemplateNotificacao.objects.create(
            tipo_notificacao=self.tipo,
            canal=self.canal,
            nome='Template de Teste',
            assunto='Assunto: {{ nome }}',
            corpo_texto='Olá {{ nome }}, sua venda foi aprovada!',
            variaveis=['nome', 'valor'],
            ativo=True
        )
    
    def test_full_notification_flow(self):
        """Testa fluxo completo de notificação"""
        # Criar preferência do usuário
        PreferenciaNotificacao.objects.create(
            usuario=self.user,
            tipo_notificacao=self.tipo,
            canal_preferido=self.canal,
            ativo=True
        )
        
        # Enviar notificação
        service = NotificationService()
        
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True, 'executionId': '123'}
            mock_post.return_value = mock_response
            
            notificacoes = service.enviar_notificacao(
                tipo_codigo='teste',
                destinatarios=[self.user],
                dados_contexto={'nome': 'João Silva', 'valor': 'R$ 100,00'}
            )
        
        # Verificações
        self.assertEqual(len(notificacoes), 1)
        notificacao = notificacoes[0]
        
        # Verificar dados da notificação
        self.assertEqual(notificacao.tipo, self.tipo)
        self.assertEqual(notificacao.canal, self.canal)
        self.assertEqual(notificacao.destinatario, self.user)
        self.assertEqual(notificacao.status, 'enviada')
        self.assertIn('João Silva', notificacao.titulo)
        self.assertIn('João Silva', notificacao.mensagem)
        
        # Verificar integração com N8N
        self.assertIsNotNone(notificacao.n8n_execution_id)
        self.assertEqual(notificacao.n8n_execution_id, '123')
    
    def test_notification_with_retry(self):
        """Testa notificação com retry"""
        service = NotificationService()
        
        # Primeira tentativa falha
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {'error': 'Erro interno'}
            mock_post.return_value = mock_response
            
            notificacoes = service.enviar_notificacao(
                tipo_codigo='teste',
                destinatarios=[self.user],
                dados_contexto={}
            )
        
        notificacao = notificacoes[0]
        self.assertEqual(notificacao.status, 'falhou')
        self.assertEqual(notificacao.tentativas, 1)
        
        # Segunda tentativa (retry)
        with patch('requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True, 'executionId': '456'}
            mock_post.return_value = mock_response
            
            service._tentar_reenvio(notificacao)
        
        # Verificar se foi reenviada
        notificacao.refresh_from_db()
        self.assertEqual(notificacao.status, 'enviada')
        self.assertEqual(notificacao.tentativas, 2)
        self.assertEqual(notificacao.n8n_execution_id, '456')


if __name__ == '__main__':
    import django
    django.setup()
    
    # Executar testes
    import unittest
    unittest.main()
