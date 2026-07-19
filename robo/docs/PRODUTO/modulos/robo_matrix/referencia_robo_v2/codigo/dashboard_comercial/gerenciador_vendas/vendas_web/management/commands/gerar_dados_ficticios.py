from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
import random
from faker import Faker
from decimal import Decimal
from vendas_web.models import LeadProspecto, Prospecto, HistoricoContato, ConfiguracaoSistema, LogSistema


class Command(BaseCommand):
    help = 'Gera dados fictícios para testar o dashboard'

    def add_arguments(self, parser):
        parser.add_argument(
            '--leads',
            type=int,
            default=100,
            help='Número de leads para criar (padrão: 100)'
        )
        parser.add_argument(
            '--prospectos',
            type=int,
            default=60,
            help='Número de prospectos para criar (padrão: 60)'
        )
        parser.add_argument(
            '--contatos',
            type=int,
            default=200,
            help='Número de contatos para criar (padrão: 200)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Limpar dados existentes antes de criar novos'
        )

    def handle(self, *args, **options):
        fake = Faker('pt_BR')
        
        if options['clear']:
            self.stdout.write('Limpando dados existentes...')
            LeadProspecto.objects.all().delete()
            Prospecto.objects.all().delete()
            HistoricoContato.objects.all().delete()
            ConfiguracaoSistema.objects.all().delete()
            LogSistema.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Dados limpos com sucesso!'))

        # Gerar Leads
        self.stdout.write(f'Gerando {options["leads"]} leads...')
        leads_criados = self.gerar_leads(fake, options['leads'])
        
        # Gerar Prospectos
        self.stdout.write(f'Gerando {options["prospectos"]} prospectos...')
        self.gerar_prospectos(fake, options['prospectos'], leads_criados)
        
        # Gerar Histórico de Contatos
        self.stdout.write(f'Gerando {options["contatos"]} contatos...')
        self.gerar_contatos(fake, options['contatos'], leads_criados)
        
        # Gerar Configurações
        self.stdout.write('Gerando configurações do sistema...')
        self.gerar_configuracoes()
        
        # Gerar Logs
        self.stdout.write('Gerando logs do sistema...')
        self.gerar_logs(fake, 50)
        
        self.stdout.write(
            self.style.SUCCESS('Dados fictícios gerados com sucesso!')
        )

    def gerar_leads(self, fake, quantidade):
        """Gera leads fictícios"""
        leads = []
        empresas = [
            'Tech Solutions Ltda', 'Inovação Digital', 'Consultoria ABC',
            'Marketing Pro', 'Vendas Master', 'Gestão Moderna',
            'Empresa XYZ', 'Negócios Online', 'Soluções Web',
            'Desenvolvimento Ágil', 'StartupTech', 'InnovaCorp',
            'DigitalFirst', 'SalesBoost', 'WebMaster Pro',
            None, None, None  # Alguns sem empresa
        ]
        
        origens = [choice[0] for choice in LeadProspecto.ORIGEM_CHOICES]
        status_api = [choice[0] for choice in LeadProspecto.STATUS_API_CHOICES]
        
        # Pré-gerar alguns telefones que serão usados nos contatos
        telefones_predefinidos = [self.gerar_telefone_brasileiro() for _ in range(30)]
        
        for i in range(quantidade):
            # Data de cadastro nos últimos 45 dias
            data_cadastro = fake.date_time_between(
                start_date='-45d',
                end_date='now',
                tzinfo=timezone.get_current_timezone()
            )
            
            # 40% dos leads usam telefones predefinidos para matching com contatos
            if i < quantidade * 0.4:
                telefone = telefones_predefinidos[i % len(telefones_predefinidos)]
            else:
                telefone = self.gerar_telefone_brasileiro()
            
            # Status API baseado na data (leads mais antigos têm mais chance de estar processados)
            dias_atras = (timezone.now() - data_cadastro).days
            if dias_atras > 30:
                status_api_lead = random.choice(['processado', 'sucesso', 'erro'])
            elif dias_atras > 15:
                status_api_lead = random.choice(['processado', 'sucesso', 'pendente'])
            else:
                status_api_lead = random.choice(['pendente', 'processado'])
            
            # Valor baseado no status (leads processados com sucesso têm mais valor)
            if status_api_lead == 'sucesso':
                valor = Decimal(random.uniform(1000, 15000)).quantize(Decimal('0.01'))
            elif status_api_lead == 'processado':
                valor = Decimal(random.uniform(500, 8000)).quantize(Decimal('0.01')) if random.random() < 0.7 else Decimal('0.00')
            else:
                valor = Decimal(random.uniform(100, 3000)).quantize(Decimal('0.01')) if random.random() < 0.3 else Decimal('0.00')
            
            # Escolher tipo de entrada baseado na origem
            origem_escolhida = random.choice(origens)
            tipo_entrada_map = {
                'site': 'cadastro_site',
                'whatsapp': 'contato_whatsapp',
                'telefone': 'telefone',
                'facebook': 'formulario',
                'instagram': 'formulario',
                'google': 'formulario',
                'email': 'formulario',
                'indicacao': 'telefone',
                'outros': 'telefone'
            }
            
            tipo_entrada = tipo_entrada_map.get(origem_escolhida, 'cadastro_site')
            
            lead = LeadProspecto.objects.create(
                nome_razaosocial=fake.name(),
                email=fake.email(),
                telefone=telefone,
                valor=valor,
                empresa=random.choice(empresas),
                origem=origem_escolhida,
                data_cadastro=data_cadastro,
                status_api=status_api_lead,
                cpf_cnpj=fake.cpf() if random.random() < 0.6 else None,
                endereco=fake.address() if random.random() < 0.4 else None,
                cidade=fake.city() if random.random() < 0.5 else None,
                estado=fake.state_abbr() if random.random() < 0.5 else None,
                cep=fake.postcode() if random.random() < 0.4 else None,
                observacoes=fake.text(max_nb_chars=200) if random.random() < 0.2 else None,
                ativo=random.choice([True, True, True, True, False]),  # 80% ativos
                # Novos campos
                canal_entrada=origem_escolhida,
                tipo_entrada=tipo_entrada,
                tentativas_contato=random.randint(0, 3),
                custo_aquisicao=Decimal(random.uniform(50, 300)).quantize(Decimal('0.01')) if random.random() < 0.6 else None,
                data_ultimo_contato=data_cadastro if random.random() < 0.5 else None
            )
            
            # Calcular score de qualificação automaticamente
            lead.score_qualificacao = lead.calcular_score_qualificacao()
            lead.save()
            leads.append(lead)
            
        self.stdout.write(f'✓ {len(leads)} leads criados com telefones estratégicos')
        return leads

    def gerar_prospectos(self, fake, quantidade, leads_disponiveis):
        """Gera prospectos fictícios"""
        status_choices = [choice[0] for choice in Prospecto.STATUS_CHOICES]
        
        for i in range(quantidade):
            # Alguns prospectos terão leads associados
            lead = random.choice(leads_disponiveis) if random.choice([True, False]) else None
            
            data_criacao = fake.date_time_between(
                start_date='-20d',
                end_date='now',
                tzinfo=timezone.get_current_timezone()
            )
            
            # Data de processamento pode ser posterior à criação
            data_processamento = None
            if random.choice([True, False, False]):  # 33% foram processados
                data_processamento = fake.date_time_between(
                    start_date=data_criacao,
                    end_date='now',
                    tzinfo=timezone.get_current_timezone()
                )
            
            status = random.choice(status_choices)
            
            # Datas de início e fim de processamento
            data_inicio_processamento = None
            data_fim_processamento = None
            
            if data_processamento:
                data_inicio_processamento = data_processamento
                # Fim pode ser alguns minutos/horas após o início
                data_fim_processamento = fake.date_time_between(
                    start_date=data_inicio_processamento,
                    end_date=data_inicio_processamento + timezone.timedelta(hours=random.randint(1, 24)),
                    tzinfo=timezone.get_current_timezone()
                )
            
            prospecto = Prospecto.objects.create(
                lead=lead,
                nome_prospecto=fake.name(),
                id_prospecto_hubsoft=f'HUB{fake.random_int(min=1000, max=9999)}' if random.choice([True, False]) else None,
                status=status,
                data_criacao=data_criacao,
                data_processamento=data_processamento,
                tentativas_processamento=random.randint(0, 5),
                tempo_processamento=Decimal(random.uniform(0.5, 30.0)).quantize(Decimal('0.001')) if data_processamento else None,
                erro_processamento=fake.text(max_nb_chars=100) if status == 'erro' else None,
                prioridade=random.randint(1, 5),
                dados_processamento={'origem': 'dashboard', 'versao': '1.0'} if random.choice([True, False]) else None,
                resultado_processamento={'sucesso': True, 'codigo': 200} if status == 'processado' else None,
                # Novos campos
                data_inicio_processamento=data_inicio_processamento,
                data_fim_processamento=data_fim_processamento,
                usuario_processamento=random.choice(['admin', 'sistema', 'operador', None])
            )
            
            # Calcular score de conversão automaticamente
            prospecto.atualizar_score_conversao()
            
        self.stdout.write(f'✓ {quantidade} prospectos criados')

    def gerar_contatos(self, fake, quantidade, leads_disponiveis):
        """Gera histórico de contatos fictícios seguindo o funil de vendas"""
        # Gerar alguns telefones fixos para simular múltiplos contatos do mesmo cliente
        telefones_fixos = [self.gerar_telefone_brasileiro() for _ in range(15)]
        origens = [choice[0] for choice in LeadProspecto.ORIGEM_CHOICES]
        
        contatos_criados = []
        
        for i in range(quantidade):
            # 60% dos contatos usam telefones fixos (para simular recorrência)
            if random.random() < 0.6:
                telefone = random.choice(telefones_fixos)
            else:
                telefone = self.gerar_telefone_brasileiro()
            
            # Data do contato nos últimos 15 dias
            data_contato = fake.date_time_between(
                start_date='-15d',
                end_date='now',
                tzinfo=timezone.get_current_timezone()
            )
            
            # Definir fluxo realista de status
            # 1. Todo contato começa com fluxo_inicializado
            if random.random() < 0.8:  # 80% dos contatos são inicializados
                status_inicial = 'fluxo_inicializado'
            else:
                # 20% têm problemas técnicos
                status_inicial = random.choice(['nao_atendeu', 'ocupado', 'numero_invalido', 'erro_sistema'])
            
            # Determinar se o contato irá evoluir no funil
            evoluir_funil = status_inicial == 'fluxo_inicializado' and random.random() < 0.4  # 40% dos inicializados evoluem
            
            origem_contato = random.choice(origens)
            nome_contato = fake.name() if random.choice([True, False]) else None
            
            # Criar identificador único para o cliente (mesmo telefone = mesmo cliente)
            import hashlib
            identificador_cliente = hashlib.md5(telefone.encode()).hexdigest()[:16]
            
            # Configurar status e conversões
            if evoluir_funil:
                # Contato que evolui no funil
                if random.random() < 0.7:  # 70% finalizam o fluxo
                    status_final = 'fluxo_finalizado'
                else:  # 30% são transferidos para humano
                    status_final = 'transferido_humano'
                
                duracao = random.randint(120, 600)  # 2-10 minutos para contatos bem-sucedidos
                converteu_lead = random.random() < 0.6  # 60% dos finalizados viram lead
                
                # Se converteu em lead, pode virar venda
                converteu_venda = False
                valor_venda = None
                data_conversao_lead = None
                data_conversao_venda = None
                
                if converteu_lead:
                    data_conversao_lead = data_contato + timezone.timedelta(hours=random.randint(1, 48))
                    converteu_venda = random.random() < 0.3  # 30% dos leads viram venda
                    
                    if converteu_venda:
                        valor_venda = Decimal(random.uniform(500, 5000)).quantize(Decimal('0.01'))
                        data_conversao_venda = data_conversao_lead + timezone.timedelta(days=random.randint(1, 7))
                        status_final = 'venda_confirmada'
                    elif random.random() < 0.1:  # 10% chance de venda rejeitada
                        status_final = 'venda_rejeitada'
                        data_conversao_venda = data_conversao_lead + timezone.timedelta(days=random.randint(1, 3))
                
            else:
                # Contato que não evolui
                if status_inicial == 'fluxo_inicializado':
                    status_final = random.choice(['abandonou_fluxo', 'desligou', 'nao_atendeu'])
                else:
                    status_final = status_inicial
                
                duracao = random.randint(5, 60)  # Contatos curtos
                converteu_lead = False
                converteu_venda = False
                valor_venda = None
                data_conversao_lead = None
                data_conversao_venda = None
            
            # Relacionar com lead existente se converteu
            lead_relacionado = None
            if converteu_lead and leads_disponiveis:
                # Tentar encontrar lead com mesmo telefone ou criar relacionamento
                lead_candidatos = [l for l in leads_disponiveis if l.telefone == telefone]
                if lead_candidatos:
                    lead_relacionado = random.choice(lead_candidatos)
                elif random.random() < 0.3:  # 30% chance de vincular a um lead aleatório
                    lead_relacionado = random.choice(leads_disponiveis)
            
            contato = HistoricoContato.objects.create(
                lead=lead_relacionado,
                telefone=telefone,
                data_hora_contato=data_contato,
                status=status_final,
                nome_contato=nome_contato,
                duracao_segundos=duracao,
                transcricao=fake.text(max_nb_chars=300) if random.random() < 0.2 else None,  # 20% têm transcrição
                observacoes=fake.text(max_nb_chars=150) if random.random() < 0.3 else None,  # 30% têm observações
                ip_origem=fake.ipv4() if random.random() < 0.8 else None,
                user_agent=fake.user_agent() if random.random() < 0.5 else None,
                dados_extras={
                    'campanha': f'camp_{fake.random_int(1, 20)}',
                    'utm_source': random.choice(['google', 'facebook', 'instagram', 'whatsapp', 'direct']),
                    'dispositivo': random.choice(['mobile', 'desktop', 'tablet'])
                } if random.random() < 0.6 else None,
                sucesso=status_final in ['fluxo_finalizado', 'transferido_humano', 'convertido_lead', 'venda_confirmada'],
                
                # Novos campos do funil
                converteu_lead=converteu_lead,
                data_conversao_lead=data_conversao_lead,
                converteu_venda=converteu_venda,
                data_conversao_venda=data_conversao_venda,
                valor_venda=valor_venda,
                origem_contato=origem_contato,
                identificador_cliente=identificador_cliente
            )
            
            contatos_criados.append(contato)
            
            # Se o telefone é fixo, simular múltiplos contatos para o mesmo cliente
            if telefone in telefones_fixos and random.random() < 0.4:  # 40% chance de contato adicional
                self._criar_contato_sequencial(fake, telefone, data_contato, origem_contato, 
                                              identificador_cliente, nome_contato, lead_relacionado)
        
        self.stdout.write(f'✓ {len(contatos_criados)} contatos criados no funil de vendas')
        
        # Estatísticas dos dados gerados
        total_inicializados = HistoricoContato.objects.filter(status='fluxo_inicializado').count()
        total_finalizados = HistoricoContato.objects.filter(status='fluxo_finalizado').count()
        total_convertidos = HistoricoContato.objects.filter(converteu_lead=True).count()
        total_vendas = HistoricoContato.objects.filter(converteu_venda=True).count()
        
        self.stdout.write(f'📊 Estatísticas do funil:')
        self.stdout.write(f'   • Fluxos inicializados: {total_inicializados}')
        self.stdout.write(f'   • Fluxos finalizados: {total_finalizados}')
        self.stdout.write(f'   • Convertidos em lead: {total_convertidos}')
        self.stdout.write(f'   • Vendas confirmadas: {total_vendas}')
    
    def _criar_contato_sequencial(self, fake, telefone, data_base, origem_contato, 
                                identificador_cliente, nome_contato, lead_relacionado):
        """Cria um contato sequencial para simular múltiplas interações"""
        # Contato posterior (1-3 dias depois)
        data_contato = data_base + timezone.timedelta(days=random.randint(1, 3), 
                                                     hours=random.randint(1, 12))
        
        # Contatos sequenciais têm maior chance de sucesso
        if random.random() < 0.6:  # 60% de sucesso
            status = random.choice(['fluxo_finalizado', 'transferido_humano'])
            duracao = random.randint(180, 900)  # 3-15 minutos
            converteu_lead = random.random() < 0.7  # 70% viram lead
        else:
            status = random.choice(['nao_atendeu', 'ocupado', 'abandonou_fluxo'])
            duracao = random.randint(10, 120)
            converteu_lead = False
        
        HistoricoContato.objects.create(
            lead=lead_relacionado,
            telefone=telefone,
            data_hora_contato=data_contato,
            status=status,
            nome_contato=nome_contato,
            duracao_segundos=duracao,
            sucesso=status in ['fluxo_finalizado', 'transferido_humano'],
            converteu_lead=converteu_lead,
            data_conversao_lead=data_contato + timezone.timedelta(hours=2) if converteu_lead else None,
            origem_contato=origem_contato,
            identificador_cliente=identificador_cliente,
            observacoes=f"Contato de follow-up - {fake.sentence()}" if random.random() < 0.5 else None
        )

    def gerar_configuracoes(self):
        """Gera configurações do sistema"""
        configuracoes = [
            {
                'chave': 'api_hubsoft_url',
                'valor': 'https://api.hubsoft.com.br/v1/',
                'descricao': 'URL base da API do Hubsoft',
                'tipo': 'string'
            },
            {
                'chave': 'max_tentativas_processamento',
                'valor': '3',
                'descricao': 'Número máximo de tentativas de processamento',
                'tipo': 'integer'
            },
            {
                'chave': 'auto_refresh_dashboard',
                'valor': 'true',
                'descricao': 'Habilitar auto-refresh do dashboard',
                'tipo': 'boolean'
            },
            {
                'chave': 'tempo_limite_processamento',
                'valor': '30.0',
                'descricao': 'Tempo limite para processamento em segundos',
                'tipo': 'decimal'
            },
            {
                'chave': 'configuracao_avancada',
                'valor': '{"tema": "dark", "notificacoes": true}',
                'descricao': 'Configurações avançadas em JSON',
                'tipo': 'json'
            }
        ]
        
        for config in configuracoes:
            ConfiguracaoSistema.objects.get_or_create(
                chave=config['chave'],
                defaults={
                    'valor': config['valor'],
                    'descricao': config['descricao'],
                    'tipo': config['tipo']
                }
            )
            
        self.stdout.write(f'✓ {len(configuracoes)} configurações criadas')

    def gerar_logs(self, fake, quantidade):
        """Gera logs do sistema"""
        niveis = [choice[0] for choice in LogSistema.NIVEL_CHOICES]
        modulos = [
            'dashboard.views', 'api.leads', 'api.prospectos', 
            'core.models', 'auth.middleware', 'tasks.processamento',
            'integracoes.hubsoft', 'utils.helpers'
        ]
        
        for i in range(quantidade):
            nivel = random.choice(niveis)
            modulo = random.choice(modulos)
            
            # Mensagens baseadas no nível
            if nivel == 'ERROR':
                mensagem = f"Erro ao processar {fake.word()}: {fake.sentence()}"
            elif nivel == 'WARNING':
                mensagem = f"Aviso: {fake.sentence()}"
            elif nivel == 'INFO':
                mensagem = f"Processamento concluído: {fake.sentence()}"
            else:
                mensagem = fake.sentence()
            
            LogSistema.objects.create(
                nivel=nivel,
                modulo=modulo,
                mensagem=mensagem,
                dados_extras={'request_id': fake.uuid4()} if random.choice([True, False]) else None,
                usuario=fake.user_name() if random.choice([True, False]) else None,
                ip=fake.ipv4() if random.choice([True, False]) else None,
                data_criacao=fake.date_time_between(
                    start_date='-7d',
                    end_date='now',
                    tzinfo=timezone.get_current_timezone()
                )
            )
            
        self.stdout.write(f'✓ {quantidade} logs criados')

    def gerar_telefone_brasileiro(self):
        """Gera um telefone brasileiro válido"""
        ddd = random.choice([
            '11', '12', '13', '14', '15', '16', '17', '18', '19',  # SP
            '21', '22', '24',  # RJ
            '27', '28',  # ES
            '31', '32', '33', '34', '35', '37', '38',  # MG
            '41', '42', '43', '44', '45', '46',  # PR
            '47', '48', '49',  # SC
            '51', '53', '54', '55',  # RS
            '61',  # DF
            '62', '64',  # GO
            '65', '66',  # MT
            '67',  # MS
            '68',  # AC
            '69',  # RO
            '71', '73', '74', '75', '77',  # BA
            '79',  # SE
            '81', '87',  # PE
            '82',  # AL
            '83',  # PB
            '84',  # RN
            '85', '88',  # CE
            '86', '89',  # PI
            '91', '93', '94',  # PA
            '92', '97',  # AM
            '95',  # RR
            '96',  # AP
            '98', '99'  # MA
        ])
        
        # Celular (9 dígitos) ou fixo (8 dígitos)
        if random.choice([True, False]):
            # Celular
            numero = f"9{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
        else:
            # Fixo
            numero = f"{random.randint(2000, 5999)}{random.randint(1000, 9999)}"
        
        return f"+55{ddd}{numero}"