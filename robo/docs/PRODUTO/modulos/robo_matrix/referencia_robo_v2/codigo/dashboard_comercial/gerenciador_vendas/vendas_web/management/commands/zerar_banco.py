from django.core.management.base import BaseCommand
from django.db import transaction
from vendas_web.models import LeadProspecto, Prospecto, HistoricoContato, ConfiguracaoSistema, LogSistema
import json
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Zera todos os dados do banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirma que você quer zerar o banco de dados'
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Faz backup dos dados antes de zerar'
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.ERROR(
                    '❌ Use --confirm para confirmar que quer zerar o banco de dados.\n'
                    'ATENÇÃO: Esta ação irá DELETAR TODOS OS DADOS!'
                )
            )
            return

        self.stdout.write('🗑️  Iniciando processo de limpeza do banco de dados...')

        try:
            # Backup opcional
            if options['backup']:
                self.fazer_backup()

            # Zerar dados em transação
            with transaction.atomic():
                self.zerar_dados()

            self.stdout.write(
                self.style.SUCCESS(
                    '✅ Banco de dados zerado com sucesso!\n'
                    '📊 Use o comando "python manage.py gerar_dados_ficticios" para gerar novos dados de teste.'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro ao zerar banco: {str(e)}')
            )

    def fazer_backup(self):
        """Faz backup dos dados em JSON"""
        self.stdout.write('📦 Fazendo backup dos dados...')
        
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'leads': list(LeadProspecto.objects.values()),
            'prospectos': list(Prospecto.objects.values()),
            'historico_contatos': list(HistoricoContato.objects.values()),
            'configuracoes': list(ConfiguracaoSistema.objects.values()),
            'logs': list(LogSistema.objects.values())
        }

        # Criar diretório de backup se não existir
        backup_dir = 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Nome do arquivo com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{backup_dir}/backup_banco_{timestamp}.json'

        # Salvar backup
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2, default=str)

        self.stdout.write(f'✅ Backup salvo em: {backup_file}')

    def zerar_dados(self):
        """Remove todos os dados das tabelas"""
        self.stdout.write('🧹 Removendo dados...')

        # Contadores para relatório
        contadores = {}

        # Deletar dados em ordem (respeitando FK)
        tabelas = [
            ('Histórico de Contatos', HistoricoContato),
            ('Prospectos', Prospecto),
            ('Leads', LeadProspecto),
            ('Logs do Sistema', LogSistema),
            ('Configurações', ConfiguracaoSistema)
        ]

        for nome, model in tabelas:
            count = model.objects.count()
            if count > 0:
                model.objects.all().delete()
                contadores[nome] = count
                self.stdout.write(f'  ✓ {nome}: {count} registros removidos')
            else:
                self.stdout.write(f'  - {nome}: já vazio')

        # Relatório final
        if contadores:
            self.stdout.write('\n📊 Resumo da limpeza:')
            total = sum(contadores.values())
            for nome, count in contadores.items():
                self.stdout.write(f'  • {nome}: {count:,} registros')
            self.stdout.write(f'  • TOTAL: {total:,} registros removidos')
        else:
            self.stdout.write('ℹ️  Banco já estava vazio.')

    def resetar_sequences(self):
        """Reseta as sequências de auto-incremento (PostgreSQL/MySQL)"""
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Para PostgreSQL
            if 'postgresql' in connection.vendor:
                tabelas = [
                    'vendas_web_leadprospecto',
                    'vendas_web_prospecto', 
                    'vendas_web_historicocontato',
                    'vendas_web_configuracaosistema',
                    'vendas_web_logsistema'
                ]
                
                for tabela in tabelas:
                    try:
                        cursor.execute(f"ALTER SEQUENCE {tabela}_id_seq RESTART WITH 1;")
                    except:
                        pass  # Ignora se a sequência não existir
                        
            # Para MySQL
            elif 'mysql' in connection.vendor:
                tabelas = [
                    'vendas_web_leadprospecto',
                    'vendas_web_prospecto',
                    'vendas_web_historicocontato', 
                    'vendas_web_configuracaosistema',
                    'vendas_web_logsistema'
                ]
                
                for tabela in tabelas:
                    try:
                        cursor.execute(f"ALTER TABLE {tabela} AUTO_INCREMENT = 1;")
                    except:
                        pass  # Ignora se a tabela não existir

        self.stdout.write('✅ Sequências de ID resetadas')