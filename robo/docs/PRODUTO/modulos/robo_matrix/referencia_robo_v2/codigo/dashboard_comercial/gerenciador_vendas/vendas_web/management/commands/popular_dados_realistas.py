import os
import django
import sys
from decimal import Decimal
from datetime import datetime, timedelta
import random
import json

# Configurar Django
sys.path.append('/home/darlan/clone_comercial/dashboard_comercial/gerenciador_vendas')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings')
django.setup()

from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from vendas_web.models import (
    LeadProspecto, Prospecto, HistoricoContato, 
    FluxoAtendimento, QuestaoFluxo, AtendimentoFluxo, RespostaQuestao,
    PlanoInternet, OpcaoVencimento, CadastroCliente, ConfiguracaoCadastro,
    StatusConfiguravel, ConfiguracaoSistema, LogSistema
)

fake = Faker('pt_BR')

class Command(BaseCommand):
    help = 'Gera dados realistas para o sistema de vendas de provedor de internet'

    def add_arguments(self, parser):
        parser.add_argument(
            '--leads',
            type=int,
            default=150,
            help='Número de leads para gerar'
        )
        parser.add_argument(
            '--contatos',
            type=int,
            default=300,
            help='Número de contatos para gerar'
        )
        parser.add_argument(
            '--atendimentos',
            type=int,
            default=80,
            help='Número de atendimentos de fluxo para gerar'
        )
        parser.add_argument(
            '--limpar',
            action='store_true',
            help='Limpar dados existentes antes de gerar novos'
        )

    def handle(self, *args, **options):
        if options['limpar']:
            self.limpar_dados()
        
        self.stdout.write('🚀 Iniciando geração de dados realistas...')
        
        # 1. Configurações básicas do sistema
        self.criar_configuracoes_sistema()
        
        # 2. Planos de internet e opções de vencimento
        self.criar_planos_e_vencimentos()
        
        # 3. Fluxos de atendimento para vendas
        self.criar_fluxos_atendimento()
        
        # 4. Status configuráveis
        self.criar_status_configuraveis()
        
        # 5. Leads de diferentes origens
        leads = self.gerar_leads_realistas(options['leads'])
        
        # 6. Histórico de contatos com IA
        self.gerar_historico_contatos_ia(options['contatos'], leads)
        
        # 7. Atendimentos de fluxo
        self.gerar_atendimentos_fluxo(options['atendimentos'], leads)
        
        # 8. Cadastros via site
        self.gerar_cadastros_site(30)
        
        # 9. Logs do sistema
        self.gerar_logs_sistema(100)
        
        self.stdout.write(self.style.SUCCESS('✅ Dados realistas gerados com sucesso!'))

    def limpar_dados(self):
        """Limpa dados existentes"""
        self.stdout.write('🗑️ Limpando dados existentes...')
        
        # Ordem para evitar problemas de FK
        RespostaQuestao.objects.all().delete()
        AtendimentoFluxo.objects.all().delete()
        QuestaoFluxo.objects.all().delete()
        FluxoAtendimento.objects.all().delete()
        CadastroCliente.objects.all().delete()
        HistoricoContato.objects.all().delete()
        Prospecto.objects.all().delete()
        LeadProspecto.objects.all().delete()
        PlanoInternet.objects.all().delete()
        OpcaoVencimento.objects.all().delete()
        ConfiguracaoCadastro.objects.all().delete()
        StatusConfiguravel.objects.all().delete()
        ConfiguracaoSistema.objects.all().delete()
        LogSistema.objects.all().delete()
        
        self.stdout.write('✅ Dados limpos!')

    def criar_configuracoes_sistema(self):
        """Cria configurações essenciais do sistema"""
        self.stdout.write('⚙️ Criando configurações do sistema...')
        
        configuracoes = [
            {
                'chave': 'ia_endpoint',
                'valor': 'https://api.openai.com/v1/chat/completions',
                'descricao': 'Endpoint da API de IA para atendimento',
                'tipo': 'string'
            },
            {
                'chave': 'max_tentativas_ia',
                'valor': '3',
                'descricao': 'Máximo de tentativas para resposta da IA',
                'tipo': 'integer'
            },
            {
                'chave': 'tempo_limite_atendimento',
                'valor': '1800',
                'descricao': 'Tempo limite para atendimento em segundos (30 min)',
                'tipo': 'integer'
            },
            {
                'chave': 'score_minimo_qualificacao',
                'valor': '6',
                'descricao': 'Score mínimo para qualificar lead',
                'tipo': 'integer'
            },
            {
                'chave': 'whatsapp_webhook',
                'valor': 'https://webhook.site/sua-url-webhook',
                'descricao': 'URL do webhook do WhatsApp',
                'tipo': 'string'
            }
        ]
        
        for config in configuracoes:
            ConfiguracaoSistema.objects.get_or_create(
                chave=config['chave'],
                defaults=config
            )

    def criar_planos_e_vencimentos(self):
        """Cria planos de internet realistas"""
        self.stdout.write('📶 Criando planos de internet...')
        
        planos_data = [
            {
                'nome': 'Megalink Start 100MB',
                'descricao': 'Plano ideal para navegação básica e streaming em HD',
                'velocidade_download': 100,
                'velocidade_upload': 100,
                'valor_mensal': Decimal('79.90'),
                'wifi_6': False,
                'suporte_prioritario': False,
                'destaque': 'economico',
                'ordem_exibicao': 1
            },
            {
                'nome': 'Megalink Plus 200MB',
                'descricao': 'Para famílias que precisam de mais velocidade',
                'velocidade_download': 200,
                'velocidade_upload': 200,
                'valor_mensal': Decimal('109.90'),
                'wifi_6': True,
                'suporte_prioritario': False,
                'destaque': 'popular',
                'ordem_exibicao': 2
            },
            {
                'nome': 'Megalink Ultra 400MB',
                'descricao': 'Máxima velocidade para gamers e empresas',
                'velocidade_download': 400,
                'velocidade_upload': 400,
                'valor_mensal': Decimal('149.90'),
                'wifi_6': True,
                'suporte_prioritario': True,
                'destaque': 'premium',
                'ordem_exibicao': 3
            },
            {
                'nome': 'Megalink Giga 600MB',
                'descricao': 'Para quem não pode perder conexão nunca',
                'velocidade_download': 600,
                'velocidade_upload': 600,
                'valor_mensal': Decimal('199.90'),
                'wifi_6': True,
                'suporte_prioritario': True,
                'destaque': 'recomendado',
                'ordem_exibicao': 4
            },
            {
                'nome': 'Megalink Business 1GB',
                'descricao': 'Solução empresarial com SLA garantido',
                'velocidade_download': 1000,
                'velocidade_upload': 1000,
                'valor_mensal': Decimal('299.90'),
                'wifi_6': True,
                'suporte_prioritario': True,
                'destaque': '',
                'ordem_exibicao': 5
            }
        ]
        
        for plano_data in planos_data:
            PlanoInternet.objects.get_or_create(
                nome=plano_data['nome'],
                defaults=plano_data
            )
        
        # Opções de vencimento
        self.stdout.write('📅 Criando opções de vencimento...')
        
        vencimentos_data = [
            {'dia_vencimento': 5, 'descricao': 'Todo dia 5', 'ordem_exibicao': 1},
            {'dia_vencimento': 10, 'descricao': 'Todo dia 10', 'ordem_exibicao': 2},
            {'dia_vencimento': 15, 'descricao': 'Todo dia 15', 'ordem_exibicao': 3},
            {'dia_vencimento': 20, 'descricao': 'Todo dia 20', 'ordem_exibicao': 4},
            {'dia_vencimento': 25, 'descricao': 'Todo dia 25', 'ordem_exibicao': 5},
        ]
        
        for venc_data in vencimentos_data:
            OpcaoVencimento.objects.get_or_create(
                dia_vencimento=venc_data['dia_vencimento'],
                defaults=venc_data
            )
        
        # Configuração de cadastro
        ConfiguracaoCadastro.objects.get_or_create(
            empresa='Megalink Piauí',
            defaults={
                'titulo_pagina': 'Cadastro Cliente - Megalink Piauí',
                'subtitulo_pagina': 'A melhor internet fibra ótica do Piauí',
                'telefone_suporte': '(89) 2221-0068',
                'whatsapp_suporte': '558922210068',
                'email_suporte': 'contato@megalinkpiaui.com.br',
                'mostrar_selecao_plano': True,
                'cpf_obrigatorio': True,
                'email_obrigatorio': True,
                'telefone_obrigatorio': True,
                'endereco_obrigatorio': True,
                'validar_cep': True,
                'validar_cpf': True,
                'mostrar_progress_bar': True,
                'numero_etapas': 4,
                'mensagem_sucesso': 'Parabéns! Seu cadastro foi realizado com sucesso. Em breve nossa equipe entrará em contato!',
                'criar_lead_automatico': True,
                'origem_lead_padrao': 'site'
            }
        )

    def criar_fluxos_atendimento(self):
        """Cria fluxos de atendimento para vendas de internet"""
        self.stdout.write('🔄 Criando fluxos de atendimento...')
        
        # Fluxo principal de qualificação e vendas
        fluxo_vendas, created = FluxoAtendimento.objects.get_or_create(
            nome='Qualificação e Vendas - Internet Fibra',
            defaults={
                'descricao': 'Fluxo principal para qualificar leads e realizar vendas de planos de internet fibra ótica',
                'tipo_fluxo': 'vendas',
                'status': 'ativo',
                'max_tentativas': 3,
                'tempo_limite_minutos': 30,
                'permite_pular_questoes': False,
                'criado_por': 'Sistema'
            }
        )
        
        if created:
            # Questões do fluxo de vendas
            questoes_vendas = [
                {
                    'indice': 1,
                    'titulo': 'Olá! Sou a IA da Megalink. Qual seu nome?',
                    'tipo_questao': 'texto',
                    'tipo_validacao': 'obrigatoria',
                    'tamanho_minimo': 2,
                    'tamanho_maximo': 100
                },
                {
                    'indice': 2,
                    'titulo': 'Qual seu telefone/WhatsApp para contato?',
                    'tipo_questao': 'telefone',
                    'tipo_validacao': 'obrigatoria',
                    'regex_validacao': r'^\+?1?\d{9,15}$'
                },
                {
                    'indice': 3,
                    'titulo': 'Você já tem internet em casa?',
                    'tipo_questao': 'select',
                    'tipo_validacao': 'obrigatoria',
                    'opcoes_resposta': ['Sim, tenho', 'Não tenho', 'Tenho, mas quero trocar']
                },
                {
                    'indice': 4,
                    'titulo': 'Qual velocidade você precisa para sua internet?',
                    'tipo_questao': 'select',
                    'tipo_validacao': 'obrigatoria',
                    'opcoes_resposta': ['Até 100MB - Uso básico', '200MB - Uso familiar', '400MB+ - Uso intenso/games', 'Não sei, me ajude a escolher']
                },
                {
                    'indice': 5,
                    'titulo': 'Quantas pessoas usam internet na sua casa?',
                    'tipo_questao': 'numero',
                    'tipo_validacao': 'obrigatoria',
                    'valor_minimo': 1,
                    'valor_maximo': 20
                },
                {
                    'indice': 6,
                    'titulo': 'Qual seu CEP?',
                    'tipo_questao': 'cep',
                    'tipo_validacao': 'obrigatoria',
                    'regex_validacao': r'^\d{5}-?\d{3}$'
                },
                {
                    'indice': 7,
                    'titulo': 'De 1 a 10, qual sua urgência para contratar?',
                    'tipo_questao': 'escala',
                    'tipo_validacao': 'obrigatoria',
                    'valor_minimo': 1,
                    'valor_maximo': 10
                },
                {
                    'indice': 8,
                    'titulo': 'Qual o melhor horário para nossa equipe te ligar?',
                    'tipo_questao': 'select',
                    'tipo_validacao': 'obrigatoria',
                    'opcoes_resposta': ['Manhã (8h-12h)', 'Tarde (12h-18h)', 'Noite (18h-21h)', 'Qualquer horário']
                },
                {
                    'indice': 9,
                    'titulo': 'Tem alguma observação ou dúvida específica?',
                    'tipo_questao': 'texto',
                    'tipo_validacao': 'opcional',
                    'tamanho_maximo': 500
                }
            ]
            
            for questao_data in questoes_vendas:
                QuestaoFluxo.objects.create(
                    fluxo=fluxo_vendas,
                    **questao_data
                )
        
        # Fluxo de suporte/pós-venda
        fluxo_suporte, created = FluxoAtendimento.objects.get_or_create(
            nome='Suporte e Atendimento',
            defaults={
                'descricao': 'Fluxo para atendimento de suporte e dúvidas de clientes',
                'tipo_fluxo': 'suporte',
                'status': 'ativo',
                'max_tentativas': 2,
                'tempo_limite_minutos': 15,
                'permite_pular_questoes': True,
                'criado_por': 'Sistema'
            }
        )
        
        if created:
            questoes_suporte = [
                {
                    'indice': 1,
                    'titulo': 'Olá! Como posso te ajudar hoje?',
                    'tipo_questao': 'select',
                    'tipo_validacao': 'obrigatoria',
                    'opcoes_resposta': ['Problema com internet', 'Dúvida sobre plano', 'Alterar vencimento', 'Cancelar serviço', 'Outro']
                },
                {
                    'indice': 2,
                    'titulo': 'Qual seu telefone para localizarmos seu cadastro?',
                    'tipo_questao': 'telefone',
                    'tipo_validacao': 'obrigatoria'
                },
                {
                    'indice': 3,
                    'titulo': 'Descreva brevemente sua situação:',
                    'tipo_questao': 'texto',
                    'tipo_validacao': 'obrigatoria',
                    'tamanho_minimo': 10,
                    'tamanho_maximo': 300
                }
            ]
            
            for questao_data in questoes_suporte:
                QuestaoFluxo.objects.create(
                    fluxo=fluxo_suporte,
                    **questao_data
                )

    def criar_status_configuraveis(self):
        """Cria status configuráveis para o sistema"""
        self.stdout.write('📊 Criando status configuráveis...')
        
        status_data = [
            # Status de Lead API
            ('lead_status_api', 'pendente', 'Aguardando Processamento'),
            ('lead_status_api', 'processado', 'Processado com Sucesso'),
            ('lead_status_api', 'erro', 'Erro no Processamento'),
            ('lead_status_api', 'sucesso', 'Enviado com Sucesso'),
            ('lead_status_api', 'rejeitado', 'Rejeitado pela API'),
            ('lead_status_api', 'aguardando_retry', 'Aguardando Nova Tentativa'),
            
            # Status de Prospecto
            ('prospecto_status', 'pendente', 'Pendente'),
            ('prospecto_status', 'processando', 'Em Processamento'),
            ('prospecto_status', 'processado', 'Processado'),
            ('prospecto_status', 'erro', 'Erro'),
            ('prospecto_status', 'finalizado', 'Finalizado'),
            ('prospecto_status', 'cancelado', 'Cancelado'),
            
            # Status de Histórico
            ('historico_status', 'fluxo_inicializado', 'Atendimento Iniciado'),
            ('historico_status', 'fluxo_finalizado', 'Atendimento Finalizado'),
            ('historico_status', 'transferido_humano', 'Transferido para Atendente'),
            ('historico_status', 'convertido_lead', 'Convertido em Lead'),
            ('historico_status', 'venda_confirmada', 'Venda Realizada'),
            ('historico_status', 'venda_rejeitada', 'Venda Cancelada'),
            ('historico_status', 'abandonou_fluxo', 'Cliente Abandonou'),
            
            # Status de Atendimento
            ('atendimento_status', 'iniciado', 'Iniciado'),
            ('atendimento_status', 'em_andamento', 'Em Andamento'),
            ('atendimento_status', 'completado', 'Completado'),
            ('atendimento_status', 'abandonado', 'Abandonado'),
            ('atendimento_status', 'pausado', 'Pausado'),
        ]
        
        for grupo, codigo, rotulo in status_data:
            StatusConfiguravel.objects.get_or_create(
                grupo=grupo,
                codigo=codigo,
                defaults={'rotulo': rotulo, 'ativo': True}
            )

    def gerar_leads_realistas(self, quantidade):
        """Gera leads realistas de diferentes origens"""
        self.stdout.write(f'👥 Gerando {quantidade} leads realistas...')
        
        planos = list(PlanoInternet.objects.all())
        leads_gerados = []
        
        # Distribuição de origens realista para provedor de internet
        origens_pesos = {
            'site': 35,  # 35% - Cadastros diretos no site
            'whatsapp': 25,  # 25% - Contatos via WhatsApp
            'facebook': 15,  # 15% - Campanhas Facebook/Instagram
            'google': 10,  # 10% - Google Ads
            'indicacao': 8,  # 8% - Indicações de clientes
            'telefone': 5,  # 5% - Ligações diretas
            'outros': 2   # 2% - Outras origens
        }
        
        # Gerar leads com distribuição realista
        for i in range(quantidade):
            origem = self._escolher_origem_ponderada(origens_pesos)
            
            # Dados básicos do lead
            nome = fake.name()
            telefone = self._gerar_telefone_brasileiro()
            email = fake.email() if random.random() > 0.1 else None  # 10% sem email
            
            # Valor baseado no plano (alguns leads sem valor definido)
            plano_interesse = random.choice(planos) if random.random() > 0.3 else None
            valor = plano_interesse.valor_mensal if plano_interesse else None
            
            # Score baseado na origem e dados
            score = self._calcular_score_lead(origem, email, valor)
            
            # Status baseado no score e origem
            status_api = self._definir_status_lead(score, origem)
            
            # Criar lead
            lead = LeadProspecto.objects.create(
                nome_razaosocial=nome,
                email=email,
                telefone=telefone,
                valor=valor,
                origem=origem,
                status_api=status_api,
                cpf_cnpj=fake.cpf().replace('.', '').replace('-', '') if random.random() > 0.4 else None,
                endereco=fake.address() if random.random() > 0.5 else None,
                cidade=fake.city(),
                estado=fake.state_abbr(),
                cep=fake.postcode(),
                data_cadastro=fake.date_time_between(start_date='-60d', end_date='now', tzinfo=timezone.get_current_timezone()),
                score_qualificacao=score,
                tentativas_contato=random.randint(0, 3),
                data_ultimo_contato=fake.date_time_between(start_date='-30d', end_date='now', tzinfo=timezone.get_current_timezone()) if random.random() > 0.3 else None,
                observacoes=self._gerar_observacao_lead(origem, score),
                canal_entrada=origem,
                tipo_entrada=self._definir_tipo_entrada(origem),
                custo_aquisicao=self._calcular_custo_aquisicao(origem) if random.random() > 0.4 else None
            )
            
            leads_gerados.append(lead)
            
            # Criar prospecto para alguns leads
            if random.random() > 0.7:  # 30% dos leads viram prospectos
                self._criar_prospecto_para_lead(lead)
        
        return leads_gerados

    def gerar_historico_contatos_ia(self, quantidade, leads):
        """Gera histórico de contatos simulando interação com IA"""
        self.stdout.write(f'🤖 Gerando {quantidade} contatos com IA...')
        
        if not leads:
            return
        
        # Tipos de interação por origem
        tipos_interacao = {
            'whatsapp': ['fluxo_inicializado', 'fluxo_finalizado', 'transferido_humano', 'convertido_lead', 'abandonou_fluxo'],
            'site': ['fluxo_finalizado', 'convertido_lead'],
            'telefone': ['transferido_humano', 'fluxo_finalizado', 'venda_confirmada'],
            'facebook': ['fluxo_inicializado', 'abandonou_fluxo', 'convertido_lead'],
            'google': ['fluxo_inicializado', 'fluxo_finalizado', 'convertido_lead']
        }
        
        for i in range(quantidade):
            # Escolher lead (pode gerar contatos para leads existentes ou novos números)
            if random.random() > 0.3:  # 70% para leads existentes
                lead = random.choice(leads)
                telefone = lead.telefone
                nome = lead.nome_razaosocial
                origem = lead.origem
            else:  # 30% para novos números (prospects)
                lead = None
                telefone = self._gerar_telefone_brasileiro()
                nome = fake.name()
                origem = random.choice(['whatsapp', 'telefone', 'site'])
            
            # Definir status baseado na origem
            status_opcoes = tipos_interacao.get(origem, ['fluxo_inicializado', 'fluxo_finalizado'])
            status = random.choice(status_opcoes)
            
            # Duração baseada no status
            duracao = self._calcular_duracao_contato(status, origem)
            
            # Dados do contato
            data_contato = fake.date_time_between(start_date='-45d', end_date='now', tzinfo=timezone.get_current_timezone())
            
            contato = HistoricoContato.objects.create(
                lead=lead,
                telefone=telefone,
                nome_contato=nome,
                data_hora_contato=data_contato,
                status=status,
                duracao_segundos=duracao,
                sucesso=self._definir_sucesso_contato(status),
                converteu_lead=status == 'convertido_lead',
                data_conversao_lead=data_contato if status == 'convertido_lead' else None,
                converteu_venda=status == 'venda_confirmada',
                data_conversao_venda=data_contato if status == 'venda_confirmada' else None,
                valor_venda=self._calcular_valor_venda() if status == 'venda_confirmada' else None,
                origem_contato=origem,
                observacoes=self._gerar_observacao_contato(status, origem, nome),
                transcricao=self._gerar_transcricao_ia(status, origem, nome) if random.random() > 0.6 else None,
                ip_origem=fake.ipv4(),
                identificador_cliente=f"{telefone}_{origem}"
            )
            
            # Criar dados extras com informações da IA
            if random.random() > 0.4:
                contato.dados_extras = {
                    'ia_engine': 'gpt-4',
                    'confianca_resposta': round(random.uniform(0.7, 0.98), 2),
                    'topicos_detectados': self._gerar_topicos_ia(origem),
                    'sentimento': random.choice(['positivo', 'neutro', 'negativo']),
                    'intencao': self._definir_intencao_contato(status),
                    'dispositivo': random.choice(['mobile', 'desktop', 'tablet']),
                    'tempo_resposta_ia': round(random.uniform(0.8, 3.2), 2)
                }
                contato.save()

    def gerar_atendimentos_fluxo(self, quantidade, leads):
        """Gera atendimentos de fluxo em diferentes estágios"""
        self.stdout.write(f'🔄 Gerando {quantidade} atendimentos de fluxo...')
        
        fluxos = list(FluxoAtendimento.objects.all())
        if not fluxos or not leads:
            return
        
        for i in range(quantidade):
            lead = random.choice(leads)
            fluxo = random.choice(fluxos)
            
            # Status realista baseado na progressão
            status_pesos = {
                'completado': 40,
                'em_andamento': 25,
                'abandonado': 20,
                'pausado': 10,
                'iniciado': 5
            }
            status = self._escolher_status_ponderado(status_pesos)
            
            # Questão atual baseada no status
            total_questoes = fluxo.get_total_questoes()
            if status == 'completado':
                questao_atual = total_questoes
                questoes_respondidas = total_questoes
            elif status == 'em_andamento':
                questao_atual = random.randint(2, max(2, total_questoes - 1))
                questoes_respondidas = questao_atual - 1
            elif status == 'abandonado':
                questao_atual = random.randint(1, max(1, total_questoes // 2))
                questoes_respondidas = max(0, questao_atual - 1)
            else:  # iniciado, pausado
                questao_atual = 1
                questoes_respondidas = 0
            
            # Datas
            data_inicio = fake.date_time_between(start_date='-30d', end_date='now', tzinfo=timezone.get_current_timezone())
            data_conclusao = None
            tempo_total = None
            
            if status in ['completado', 'abandonado']:
                data_conclusao = data_inicio + timedelta(minutes=random.randint(5, 45))
                tempo_total = int((data_conclusao - data_inicio).total_seconds())
            
            # Gerar respostas baseadas no progresso
            dados_respostas = self._gerar_respostas_fluxo(fluxo, questoes_respondidas, lead)
            
            atendimento = AtendimentoFluxo.objects.create(
                lead=lead,
                fluxo=fluxo,
                status=status,
                questao_atual=questao_atual,
                total_questoes=total_questoes,
                questoes_respondidas=questoes_respondidas,
                data_inicio=data_inicio,
                data_conclusao=data_conclusao,
                tempo_total=tempo_total,
                tentativas_atual=random.randint(0, 2),
                dados_respostas=dados_respostas,
                score_qualificacao=random.randint(1, 10) if status == 'completado' else None,
                observacoes=self._gerar_observacao_atendimento(status, fluxo.tipo_fluxo),
                ip_origem=fake.ipv4(),
                dispositivo=random.choice(['mobile', 'desktop', 'tablet']),
                user_agent=fake.user_agent()
            )
            
            # Criar respostas detalhadas para questões respondidas
            if questoes_respondidas > 0:
                self._criar_respostas_detalhadas(atendimento, fluxo, questoes_respondidas)

    def gerar_cadastros_site(self, quantidade):
        """Gera cadastros via site"""
        self.stdout.write(f'🌐 Gerando {quantidade} cadastros via site...')
        
        planos = list(PlanoInternet.objects.all())
        vencimentos = list(OpcaoVencimento.objects.all())
        
        for i in range(quantidade):
            nome = fake.name()
            data_inicio = fake.date_time_between(start_date='-15d', end_date='now', tzinfo=timezone.get_current_timezone())
            
            # Status realista
            status_pesos = {
                'finalizado': 60,
                'endereco': 15,
                'dados_pessoais': 10,
                'iniciado': 10,
                'erro': 5
            }
            status = self._escolher_status_ponderado(status_pesos)
            
            cadastro = CadastroCliente.objects.create(
                nome_completo=nome,
                cpf=fake.cpf().replace('.', '').replace('-', ''),
                email=fake.email(),
                telefone=self._gerar_telefone_brasileiro(),
                data_nascimento=fake.date_of_birth(minimum_age=18, maximum_age=80),
                cep=fake.postcode(),
                endereco=fake.street_name(),
                numero=str(random.randint(1, 9999)),
                bairro=fake.neighborhood(),
                cidade=fake.city(),
                estado=fake.state_abbr(),
                plano_selecionado=random.choice(planos) if planos else None,
                vencimento_selecionado=random.choice(vencimentos) if vencimentos else None,
                status=status,
                ip_cliente=fake.ipv4(),
                user_agent=fake.user_agent(),
                data_inicio=data_inicio,
                data_finalizacao=data_inicio + timedelta(minutes=random.randint(2, 20)) if status == 'finalizado' else None
            )
            
            # Se finalizado, criar lead automaticamente
            if status == 'finalizado' and random.random() > 0.2:  # 80% geram lead
                lead = LeadProspecto.objects.create(
                    nome_razaosocial=cadastro.nome_completo,
                    email=cadastro.email,
                    telefone=cadastro.telefone,
                    valor=cadastro.plano_selecionado.valor_mensal if cadastro.plano_selecionado else None,
                    origem='site',
                    status_api='pendente',
                    cpf_cnpj=cadastro.cpf,
                    endereco=f"{cadastro.endereco}, {cadastro.numero}",
                    cidade=cadastro.cidade,
                    estado=cadastro.estado,
                    cep=cadastro.cep,
                    observacoes=f"Lead gerado via cadastro do site - Plano: {cadastro.plano_selecionado.nome if cadastro.plano_selecionado else 'Não selecionado'}",
                    canal_entrada='site',
                    tipo_entrada='cadastro_site'
                )
                cadastro.lead_gerado = lead
                cadastro.save()

    def gerar_logs_sistema(self, quantidade):
        """Gera logs do sistema"""
        self.stdout.write(f'📋 Gerando {quantidade} logs do sistema...')
        
        modulos = [
            'atendimento_ia', 'webhook_whatsapp', 'processamento_lead', 
            'api_externa', 'fluxo_vendas', 'validacao_cadastro', 
            'integracao_hubsoft', 'notificacao_email'
        ]
        
        niveis = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        
        for i in range(quantidade):
            nivel = random.choice(niveis)
            modulo = random.choice(modulos)
            
            LogSistema.objects.create(
                nivel=nivel,
                modulo=modulo,
                mensagem=self._gerar_mensagem_log(nivel, modulo),
                dados_extras=self._gerar_dados_extras_log(modulo) if random.random() > 0.5 else None,
                usuario=fake.user_name() if random.random() > 0.6 else None,
                ip=fake.ipv4(),
                data_criacao=fake.date_time_between(start_date='-7d', end_date='now', tzinfo=timezone.get_current_timezone())
            )

    # ============================================================================
    # MÉTODOS AUXILIARES
    # ============================================================================
    
    def _escolher_origem_ponderada(self, origens_pesos):
        """Escolhe origem baseada em pesos"""
        total = sum(origens_pesos.values())
        rand = random.randint(1, total)
        atual = 0
        for origem, peso in origens_pesos.items():
            atual += peso
            if rand <= atual:
                return origem
        return 'site'
    
    def _escolher_status_ponderado(self, status_pesos):
        """Escolhe status baseado em pesos"""
        total = sum(status_pesos.values())
        rand = random.randint(1, total)
        atual = 0
        for status, peso in status_pesos.items():
            atual += peso
            if rand <= atual:
                return status
        return list(status_pesos.keys())[0]
    
    def _gerar_telefone_brasileiro(self):
        """Gera telefone brasileiro realista"""
        ddd = random.choice(['11', '21', '31', '41', '51', '61', '71', '81', '85', '89'])
        numero = f"9{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
        return f"55{ddd}{numero}"
    
    def _calcular_score_lead(self, origem, email, valor):
        """Calcula score do lead baseado em fatores"""
        score = 5  # Base
        
        # Origem influencia score
        score_origem = {
            'indicacao': 2, 'telefone': 1, 'site': 1, 
            'whatsapp': 0, 'google': 0, 'facebook': -1, 'outros': -1
        }
        score += score_origem.get(origem, 0)
        
        # Email válido aumenta score
        if email:
            score += 1
        
        # Valor do plano influencia
        if valor and valor > 100:
            score += 1
        
        return max(1, min(10, score))
    
    def _definir_status_lead(self, score, origem):
        """Define status do lead baseado no score"""
        if score >= 8:
            return random.choice(['processado', 'sucesso'])
        elif score >= 6:
            return random.choice(['pendente', 'processado'])
        elif score >= 4:
            return random.choice(['pendente', 'aguardando_retry'])
        else:
            return random.choice(['erro', 'rejeitado'])
    
    def _definir_tipo_entrada(self, origem):
        """Define tipo de entrada baseado na origem"""
        mapeamento = {
            'whatsapp': 'contato_whatsapp',
            'site': 'cadastro_site',
            'telefone': 'telefone',
            'facebook': 'formulario',
            'google': 'formulario',
            'indicacao': 'telefone',
            'outros': 'api_externa'
        }
        return mapeamento.get(origem, 'formulario')
    
    def _calcular_custo_aquisicao(self, origem):
        """Calcula custo de aquisição baseado na origem"""
        custos = {
            'google': Decimal(str(random.uniform(15, 35))),
            'facebook': Decimal(str(random.uniform(8, 25))),
            'site': Decimal(str(random.uniform(2, 8))),
            'whatsapp': Decimal(str(random.uniform(1, 5))),
            'indicacao': Decimal('0.00'),
            'telefone': Decimal(str(random.uniform(3, 10))),
            'outros': Decimal(str(random.uniform(5, 15)))
        }
        return custos.get(origem, Decimal('0.00'))
    
    def _gerar_observacao_lead(self, origem, score):
        """Gera observação realista para o lead"""
        observacoes = {
            'whatsapp': [
                "Contato iniciado via WhatsApp",
                "Cliente interessado em planos fibra",
                "Solicitou informações sobre velocidade"
            ],
            'site': [
                "Lead gerado via formulário do site",
                "Preencheu dados completos",
                "Demonstrou interesse em contratar"
            ],
            'telefone': [
                "Ligação recebida solicitando informações",
                "Cliente com urgência para contratar",
                "Já possui internet, quer trocar"
            ]
        }
        
        obs_base = random.choice(observacoes.get(origem, ["Lead qualificado"]))
        
        if score >= 8:
            obs_base += " - Lead de alta qualidade"
        elif score <= 3:
            obs_base += " - Necessita requalificação"
        
        return obs_base
    
    def _criar_prospecto_para_lead(self, lead):
        """Cria prospecto para um lead"""
        status_opcoes = ['pendente', 'processando', 'processado', 'erro']
        status = random.choice(status_opcoes)
        
        data_processamento = None
        tempo_processamento = None
        
        if status in ['processado', 'erro']:
            data_processamento = timezone.now()
            tempo_processamento = Decimal(str(random.uniform(2.5, 15.8)))
        
        Prospecto.objects.create(
            lead=lead,
            nome_prospecto=lead.nome_razaosocial,
            id_prospecto_hubsoft=f"HUB_{random.randint(10000, 99999)}" if random.random() > 0.5 else None,
            status=status,
            data_processamento=data_processamento,
            tentativas_processamento=random.randint(0, 2),
            tempo_processamento=tempo_processamento,
            erro_processamento="Timeout na API externa" if status == 'erro' else None,
            prioridade=random.randint(1, 5),
            score_conversao=Decimal(str(random.uniform(20, 95))) if random.random() > 0.3 else None
        )
    
    def _calcular_duracao_contato(self, status, origem):
        """Calcula duração realista do contato"""
        if status == 'abandonou_fluxo':
            return random.randint(15, 90)
        elif status == 'transferido_humano':
            return random.randint(180, 900)  # 3-15 min
        elif status == 'venda_confirmada':
            return random.randint(300, 1200)  # 5-20 min
        elif status == 'fluxo_finalizado':
            return random.randint(120, 480)  # 2-8 min
        else:
            return random.randint(30, 240)   # 30s-4min
    
    def _definir_sucesso_contato(self, status):
        """Define se o contato foi bem-sucedido"""
        status_sucesso = [
            'fluxo_finalizado', 'transferido_humano', 
            'convertido_lead', 'venda_confirmada'
        ]
        return status in status_sucesso
    
    def _calcular_valor_venda(self):
        """Calcula valor da venda"""
        planos = PlanoInternet.objects.all()
        if planos:
            plano = random.choice(planos)
            return plano.valor_mensal
        return Decimal('109.90')  # Valor padrão
    
    def _gerar_observacao_contato(self, status, origem, nome):
        """Gera observação para o contato"""
        observacoes = {
            'fluxo_finalizado': f"Atendimento IA finalizado. {nome} respondeu todas as questões do fluxo de qualificação.",
            'transferido_humano': f"Cliente {nome} solicitou transferência para atendente humano.",
            'venda_confirmada': f"Venda confirmada para {nome}. Cliente aceitou proposta apresentada.",
            'abandonou_fluxo': f"Cliente {nome} abandonou o atendimento na questão inicial.",
            'convertido_lead': f"Lead qualificado gerado para {nome} via {origem}."
        }
        return observacoes.get(status, f"Contato registrado para {nome}")
    
    def _gerar_transcricao_ia(self, status, origem, nome):
        """Gera transcrição simulada da IA"""
        if origem == 'whatsapp':
            transcricoes = {
                'fluxo_finalizado': f"""
IA: Olá {nome}! Sou a assistente virtual da Megalink. Como posso ajudar?
Cliente: Oi, queria saber sobre internet fibra
IA: Perfeito! Qual velocidade você precisa?
Cliente: Algo pra familia, uns 4 pessoas
IA: Recomendo nosso plano 200MB. Posso agendar uma visita?
Cliente: Pode sim, muito obrigado!
                """,
                'transferido_humano': f"""
IA: Olá {nome}! Como posso ajudar com sua internet?
Cliente: Quero cancelar meu plano
IA: Entendo. Vou transferir você para nossa equipe especializada.
Cliente: Ok, obrigado
                """,
                'abandonou_fluxo': f"""
IA: Olá {nome}! Seja bem-vindo à Megalink!
Cliente: oi
IA: Qual seu interesse hoje?
[Cliente não respondeu mais]
                """
            }
            return transcricoes.get(status, f"Conversa com {nome} via {origem}")
        return None
    
    def _gerar_topicos_ia(self, origem):
        """Gera tópicos detectados pela IA"""
        topicos_base = ['internet', 'fibra', 'velocidade', 'planos']
        
        topicos_origem = {
            'whatsapp': ['whatsapp', 'atendimento', 'suporte'],
            'site': ['cadastro', 'formulario', 'website'],
            'telefone': ['ligacao', 'urgencia', 'verbal'],
            'facebook': ['social_media', 'campanha', 'publicidade']
        }
        
        topicos = topicos_base + topicos_origem.get(origem, [])
        return random.sample(topicos, min(3, len(topicos)))
    
    def _definir_intencao_contato(self, status):
        """Define intenção do contato"""
        intencoes = {
            'fluxo_finalizado': 'contratar_servico',
            'transferido_humano': 'suporte_especializado', 
            'venda_confirmada': 'fechar_negocio',
            'abandonou_fluxo': 'apenas_informacao',
            'convertido_lead': 'interesse_comercial'
        }
        return intencoes.get(status, 'informacao_geral')
    
    def _gerar_respostas_fluxo(self, fluxo, questoes_respondidas, lead):
        """Gera respostas para o fluxo baseado no lead"""
        respostas = {}
        questoes = fluxo.get_questoes_ordenadas()[:questoes_respondidas]
        
        for questao in questoes:
            resposta_valor = self._gerar_resposta_questao(questao, lead)
            respostas[str(questao.indice)] = {
                'resposta': resposta_valor,
                'data_resposta': fake.date_time_between(start_date='-30d', end_date='now').isoformat(),
                'valida': True,
                'mensagem_erro': None
            }
        
        return respostas
    
    def _gerar_resposta_questao(self, questao, lead):
        """Gera resposta específica para uma questão"""
        if questao.tipo_questao == 'texto':
            if 'nome' in questao.titulo.lower():
                return lead.nome_razaosocial.split()[0]
            return fake.sentence(nb_words=random.randint(2, 8))
        
        elif questao.tipo_questao == 'telefone':
            return lead.telefone
        
        elif questao.tipo_questao == 'select':
            return random.choice(questao.get_opcoes_formatadas())
        
        elif questao.tipo_questao == 'numero':
            if questao.valor_minimo and questao.valor_maximo:
                return random.randint(int(questao.valor_minimo), int(questao.valor_maximo))
            return random.randint(1, 10)
        
        elif questao.tipo_questao == 'escala':
            return random.randint(1, 10)
        
        elif questao.tipo_questao == 'cep':
            return lead.cep or fake.postcode()
        
        return "Resposta padrão"
    
    def _criar_respostas_detalhadas(self, atendimento, fluxo, questoes_respondidas):
        """Cria respostas detalhadas para o atendimento"""
        questoes = fluxo.get_questoes_ordenadas()[:questoes_respondidas]
        
        for questao in questoes:
            resposta_valor = atendimento.dados_respostas.get(str(questao.indice), {}).get('resposta', '')
            
            RespostaQuestao.objects.create(
                atendimento=atendimento,
                questao=questao,
                resposta=str(resposta_valor),
                valida=True,
                tentativas=1,
                tempo_resposta=random.randint(10, 120),
                ip_origem=fake.ipv4(),
                user_agent=fake.user_agent()
            )
    
    def _gerar_observacao_atendimento(self, status, tipo_fluxo):
        """Gera observação para o atendimento"""
        observacoes = {
            'completado': f"Fluxo de {tipo_fluxo} completado com sucesso. Cliente qualificado.",
            'abandonado': f"Cliente abandonou o fluxo de {tipo_fluxo} antes de finalizar.",
            'em_andamento': f"Atendimento {tipo_fluxo} em progresso. Cliente engajado.",
            'pausado': f"Atendimento {tipo_fluxo} pausado a pedido do cliente."
        }
        return observacoes.get(status, f"Atendimento {tipo_fluxo} em processamento")
    
    def _gerar_mensagem_log(self, nivel, modulo):
        """Gera mensagem de log baseada no nível e módulo"""
        mensagens = {
            ('INFO', 'atendimento_ia'): "Atendimento IA iniciado com sucesso",
            ('WARNING', 'webhook_whatsapp'): "Webhook WhatsApp com delay na resposta",
            ('ERROR', 'api_externa'): "Falha na integração com API externa",
            ('DEBUG', 'processamento_lead'): "Lead processado e validado",
            ('CRITICAL', 'integracao_hubsoft'): "Sistema Hubsoft indisponível"
        }
        
        return mensagens.get((nivel, modulo), f"Evento {nivel.lower()} no módulo {modulo}")
    
    def _gerar_dados_extras_log(self, modulo):
        """Gera dados extras para logs"""
        dados = {
            'atendimento_ia': {
                'modelo': 'gpt-4',
                'tokens_utilizados': random.randint(50, 500),
                'tempo_resposta': round(random.uniform(0.5, 3.0), 2)
            },
            'webhook_whatsapp': {
                'numero_origem': self._gerar_telefone_brasileiro(),
                'tipo_mensagem': random.choice(['text', 'image', 'audio']),
                'status_entrega': random.choice(['delivered', 'sent', 'read'])
            },
            'api_externa': {
                'endpoint': '/api/v1/leads',
                'status_code': random.choice([200, 400, 500, 503]),
                'tempo_resposta': round(random.uniform(1.0, 10.0), 2)
            }
        }
        return dados.get(modulo, {'modulo': modulo})
