"""
Seed de dados demo para pagina de Vendas (ClienteHubsoft + ServicoClienteHubsoft).
Simula clientes de um provedor de internet com planos, status e documentacao.
Idempotente: so cria se nao existir dados no tenant Demo ISP.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random


CLIENTES = [
    {
        'nome': 'FABIOLA PEREIRA ALMEIDA',
        'cpf': '099.307.343-33',
        'telefone': '(89) 98114-6166',
        'email': 'almeidafabiola090@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 1,
    },
    {
        'nome': 'JAKELINE DA SILVA PESSOA',
        'cpf': '021.735.623-04',
        'telefone': '(89) 98541-4073',
        'email': 'jakelinedasilvapessoapes@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 2,
    },
    {
        'nome': 'LEILIANE RODRIGUES',
        'cpf': '961.440.503-10',
        'telefone': '(89) 98126-0426',
        'email': 'rodrigues.leiliane@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 3,
    },
    {
        'nome': 'ENIVAN MARIANO DA SILVA FILHO',
        'cpf': '087.479.523-00',
        'telefone': '(89) 99974-0494',
        'email': 'marianoenivan8@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 2,
    },
    {
        'nome': 'CARLOS EDUARDO SANTOS',
        'cpf': '123.456.789-01',
        'telefone': '(89) 99812-3456',
        'email': 'carlos.santos@hotmail.com',
        'plano': '[VAREJO] MEGA PLANO 400MB',
        'valor': Decimal('79.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 10,
    },
    {
        'nome': 'MARIA JOSE DE OLIVEIRA',
        'cpf': '234.567.890-12',
        'telefone': '(89) 98765-4321',
        'email': 'maria.oliveira@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 200MB',
        'valor': Decimal('59.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 15,
    },
    {
        'nome': 'JOAO PEDRO ALVES COSTA',
        'cpf': '345.678.901-23',
        'telefone': '(89) 99654-3210',
        'email': 'jpedro.costa@outlook.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 7,
    },
    {
        'nome': 'ANA PAULA FERREIRA LIMA',
        'cpf': '456.789.012-34',
        'telefone': '(89) 98543-2109',
        'email': 'anapaula.lima@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 400MB',
        'valor': Decimal('79.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 0,
    },
    {
        'nome': 'FRANCISCO DAS CHAGAS SOUSA',
        'cpf': '567.890.123-45',
        'telefone': '(89) 99432-1098',
        'email': 'chagas.sousa@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 1GB',
        'valor': Decimal('139.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 20,
    },
    {
        'nome': 'RAIMUNDA NONATA SILVA',
        'cpf': '678.901.234-56',
        'telefone': '(89) 98321-0987',
        'email': 'raimunda.silva@hotmail.com',
        'plano': '[VAREJO] MEGA PLANO 200MB',
        'valor': Decimal('59.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 25,
    },
    {
        'nome': 'PEDRO HENRIQUE ARAUJO',
        'cpf': '789.012.345-67',
        'telefone': '(89) 99210-9876',
        'email': 'pedro.araujo@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 1,
    },
    {
        'nome': 'ANTONIA MARIA NASCIMENTO',
        'cpf': '890.123.456-78',
        'telefone': '(89) 98109-8765',
        'email': 'antonia.nasc@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 400MB',
        'valor': Decimal('79.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 12,
    },
    {
        'nome': 'LUCAS GABRIEL MENDES',
        'cpf': '901.234.567-89',
        'telefone': '(89) 99098-7654',
        'email': 'lucas.mendes@outlook.com',
        'plano': '[VAREJO] MEGA PLANO 1GB',
        'valor': Decimal('139.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 5,
    },
    {
        'nome': 'FRANCISCA SOUZA RIBEIRO',
        'cpf': '012.345.678-90',
        'telefone': '(89) 98987-6543',
        'email': 'fran.ribeiro@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 200MB',
        'valor': Decimal('59.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 0,
    },
    {
        'nome': 'JOSE RIBAMAR CARVALHO',
        'cpf': '147.258.369-01',
        'telefone': '(89) 99876-5432',
        'email': 'ribamar.carvalho@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 18,
    },
    {
        'nome': 'CONDOMINIO RESIDENCIAL AURORA',
        'cpf': '12.345.678/0001-90',
        'telefone': '(89) 3221-4567',
        'email': 'sindico@condaurora.com.br',
        'plano': '[CORPORATIVO] LINK DEDICADO 100MB',
        'valor': Decimal('599.00'),
        'status': 'Servico Habilitado',
        'dias_atras': 45,
        'tipo_pessoa': 'pj',
    },
    {
        'nome': 'ESCOLA MUNICIPAL SAO FRANCISCO',
        'cpf': '23.456.789/0001-01',
        'telefone': '(89) 3221-8901',
        'email': 'contato@emsaofrancisco.edu.br',
        'plano': '[CORPORATIVO] LINK DEDICADO 50MB',
        'valor': Decimal('399.00'),
        'status': 'Servico Habilitado',
        'dias_atras': 60,
        'tipo_pessoa': 'pj',
    },
    {
        'nome': 'SUPERMERCADO BOM PRECO LTDA',
        'cpf': '34.567.890/0001-12',
        'telefone': '(89) 3221-2345',
        'email': 'financeiro@bompreco.com.br',
        'plano': '[CORPORATIVO] MEGA EMPRESARIAL 300MB',
        'valor': Decimal('249.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 30,
        'tipo_pessoa': 'pj',
    },
    {
        'nome': 'RAFAELA BEATRIZ MOURA',
        'cpf': '258.369.147-02',
        'telefone': '(89) 98765-1234',
        'email': 'rafaela.moura@gmail.com',
        'plano': '[VAREJO] MEGA PLANO 620MB',
        'valor': Decimal('99.90'),
        'status': 'Servico Habilitado',
        'dias_atras': 8,
    },
    {
        'nome': 'MARCOS VINICIUS PEREIRA',
        'cpf': '369.147.258-03',
        'telefone': '(89) 99654-9876',
        'email': 'marcos.vinicius@hotmail.com',
        'plano': '[VAREJO] MEGA PLANO 400MB',
        'valor': Decimal('79.90'),
        'status': 'Aguardando Instalacao',
        'dias_atras': 0,
    },
]


class Command(BaseCommand):
    help = 'Cria dados demo de vendas (ClienteHubsoft) para o tenant Demo ISP'

    def handle(self, *args, **options):
        from apps.sistema.models import Tenant
        from apps.sistema.middleware import set_current_tenant
        from apps.integracoes.models import ClienteHubsoft, ServicoClienteHubsoft

        demo = Tenant.objects.filter(nome__icontains='demo').first()
        if not demo:
            self.stdout.write(self.style.WARNING('Tenant Demo nao encontrado. Pulando.'))
            return

        set_current_tenant(demo)

        # Verificar se ja tem dados
        existentes = ClienteHubsoft.objects.filter(tenant=demo).count()
        if existentes >= 10:
            self.stdout.write(f'  Demo ja tem {existentes} clientes. Pulando.')
            return

        agora = timezone.now()
        base_id = 67700

        for i, c in enumerate(CLIENTES):
            data_venda = agora - timedelta(days=c['dias_atras'])
            tipo_pessoa = c.get('tipo_pessoa', 'pf')

            cliente = ClienteHubsoft.objects.create(
                tenant=demo,
                id_cliente=base_id + i,
                codigo_cliente=base_id + i,
                nome_razaosocial=c['nome'],
                tipo_pessoa=tipo_pessoa,
                cpf_cnpj=c['cpf'],
                telefone_primario=c['telefone'],
                email_principal=c['email'],
                data_cadastro_hubsoft=data_venda,
                ativo=True,
            )

            status_prefixo = 'A' if 'Habilitado' in c['status'] else 'AI'

            ServicoClienteHubsoft.objects.create(
                tenant=demo,
                cliente=cliente,
                id_cliente_servico=90000 + i,
                nome=c['plano'],
                valor=c['valor'],
                status=c['status'],
                status_prefixo=status_prefixo,
                tecnologia='FIBRA',
                data_venda=data_venda.strftime('%d/%m/%Y'),
                data_habilitacao=data_venda if 'Habilitado' in c['status'] else None,
            )

        self.stdout.write(self.style.SUCCESS(
            f'  {len(CLIENTES)} clientes demo criados no tenant "{demo.nome}".'
        ))
