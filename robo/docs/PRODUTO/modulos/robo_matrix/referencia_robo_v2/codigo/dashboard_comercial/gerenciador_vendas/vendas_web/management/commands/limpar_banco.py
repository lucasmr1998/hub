from django.core.management.base import BaseCommand
from django.db import connection
from django.core.management import call_command
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Limpa completamente o banco de dados e deixa-o zerado'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirma que você realmente quer limpar o banco (obrigatório)'
        )
        parser.add_argument(
            '--migrations',
            action='store_true',
            help='Também limpa as migrações e recria o banco do zero'
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Faz backup antes de limpar (recomendado)'
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.ERROR(
                    '❌ ATENÇÃO: Este comando irá APAGAR TODOS os dados do banco!\n'
                    'Use --confirm para confirmar que você realmente quer fazer isso.\n\n'
                    'Exemplo: python manage.py limpar_banco --confirm'
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                '⚠️  ATENÇÃO: Você está prestes a APAGAR TODOS os dados do banco!\n'
                'Esta ação é IRREVERSÍVEL!\n'
            )
        )

        # Confirmação final
        confirmacao = input('Digite "LIMPAR" para confirmar: ')
        if confirmacao != 'LIMPAR':
            self.stdout.write(self.style.ERROR('❌ Operação cancelada pelo usuário'))
            return

        try:
            # Backup opcional
            if options['backup']:
                self.stdout.write('📦 Fazendo backup do banco...')
                self.fazer_backup()

            # Limpar todas as tabelas
            self.stdout.write('🧹 Limpando todas as tabelas...')
            self.limpar_todas_tabelas()

            # Resetar sequências (auto-increment)
            self.stdout.write('🔄 Resetando sequências...')
            self.resetar_sequencias()

            if options['migrations']:
                self.stdout.write('🗂️  Limpando migrações...')
                self.limpar_migracoes()
                
                self.stdout.write('🔄 Recriando banco...')
                self.recriar_banco()

            self.stdout.write(
                self.style.SUCCESS(
                    '✅ Banco de dados limpo com sucesso!\n'
                    'Todos os dados foram removidos e o banco está zerado.'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erro ao limpar banco: {str(e)}')
            )

    def fazer_backup(self):
        """Faz backup do banco antes de limpar"""
        try:
            # Criar diretório de backup se não existir
            backup_dir = 'backups'
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)

            # Nome do arquivo de backup
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f'{backup_dir}/backup_antes_limpeza_{timestamp}.sql'

            # Comando de backup baseado no tipo de banco
            if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                # Para SQLite, copiar o arquivo
                db_path = settings.DATABASES['default']['NAME']
                import shutil
                shutil.copy2(db_path, backup_file)
                self.stdout.write(f'   ✓ Backup SQLite criado: {backup_file}')
            
            elif 'postgresql' in settings.DATABASES['default']['ENGINE']:
                # Para PostgreSQL
                db_name = settings.DATABASES['default']['NAME']
                db_user = settings.DATABASES['default']['USER']
                db_host = settings.DATABASES['default']['HOST']
                db_port = settings.DATABASES['default']['PORT']
                
                os.system(f'pg_dump -h {db_host} -p {db_port} -U {db_user} {db_name} > {backup_file}')
                self.stdout.write(f'   ✓ Backup PostgreSQL criado: {backup_file}')
            
            elif 'mysql' in settings.DATABASES['default']['ENGINE']:
                # Para MySQL
                db_name = settings.DATABASES['default']['NAME']
                db_user = settings.DATABASES['default']['USER']
                db_host = settings.DATABASES['default']['HOST']
                db_port = settings.DATABASES['default']['PORT']
                
                os.system(f'mysqldump -h {db_host} -P {db_port} -u {db_user} {db_name} > {backup_file}')
                self.stdout.write(f'   ✓ Backup MySQL criado: {backup_file}')

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Não foi possível fazer backup: {str(e)}')
            )

    def limpar_todas_tabelas(self):
        """Limpa todas as tabelas do banco"""
        with connection.cursor() as cursor:
            # Desabilitar verificação de chaves estrangeiras temporariamente
            if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                cursor.execute('PRAGMA foreign_keys = OFF')
            elif 'postgresql' in settings.DATABASES['default']['ENGINE']:
                cursor.execute('SET session_replication_role = replica')
            elif 'mysql' in settings.DATABASES['default']['ENGINE']:
                cursor.execute('SET FOREIGN_KEY_CHECKS = 0')

            # Listar todas as tabelas
            if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            elif 'postgresql' in settings.DATABASES['default']['ENGINE']:
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            elif 'mysql' in settings.DATABASES['default']['ENGINE']:
                cursor.execute("SHOW TABLES")

            tabelas = [row[0] for row in cursor.fetchall()]

            # Limpar cada tabela
            for tabela in tabelas:
                try:
                    if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                        cursor.execute(f'DELETE FROM "{tabela}"')
                    else:
                        cursor.execute(f'TRUNCATE TABLE "{tabela}" CASCADE')
                    
                    self.stdout.write(f'   ✓ Tabela {tabela} limpa')
                except Exception as e:
                    self.stdout.write(f'   ⚠️  Erro ao limpar {tabela}: {str(e)}')

            # Reabilitar verificação de chaves estrangeiras
            if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                cursor.execute('PRAGMA foreign_keys = ON')
            elif 'postgresql' in settings.DATABASES['default']['ENGINE']:
                cursor.execute('SET session_replication_role = DEFAULT')
            elif 'mysql' in settings.DATABASES['default']['ENGINE']:
                cursor.execute('SET FOREIGN_KEY_CHECKS = 1')

    def resetar_sequencias(self):
        """Reseta sequências de auto-increment"""
        with connection.cursor() as cursor:
            if 'postgresql' in settings.DATABASES['default']['ENGINE']:
                # Para PostgreSQL
                cursor.execute("""
                    SELECT c.relname FROM pg_class c WHERE c.relkind = 'S'
                """)
                sequencias = [row[0] for row in cursor.fetchall()]
                
                for seq in sequencias:
                    try:
                        cursor.execute(f'ALTER SEQUENCE {seq} RESTART WITH 1')
                        self.stdout.write(f'   ✓ Sequência {seq} resetada')
                    except Exception as e:
                        self.stdout.write(f'   ⚠️  Erro ao resetar {seq}: {str(e)}')
            
            elif 'mysql' in settings.DATABASES['default']['ENGINE']:
                # Para MySQL
                cursor.execute("SHOW TABLES")
                tabelas = [row[0] for row in cursor.fetchall()]
                
                for tabela in tabelas:
                    try:
                        cursor.execute(f'ALTER TABLE {tabela} AUTO_INCREMENT = 1')
                        self.stdout.write(f'   ✓ Auto-increment de {tabela} resetado')
                    except Exception as e:
                        self.stdout.write(f'   ⚠️  Erro ao resetar {tabela}: {str(e)}')

    def limpar_migracoes(self):
        """Remove arquivos de migração"""
        try:
            # Remover arquivos de migração (exceto __init__.py)
            for app in settings.INSTALLED_APPS:
                if '.' not in app:  # Apenas apps locais
                    migrations_dir = f'{app}/migrations'
                    if os.path.exists(migrations_dir):
                        for file in os.listdir(migrations_dir):
                            if file.endswith('.py') and file != '__init__.py':
                                os.remove(os.path.join(migrations_dir, file))
                                self.stdout.write(f'   ✓ Migração removida: {app}/{file}')
            
            # Remover migrações do banco
            with connection.cursor() as cursor:
                if 'sqlite' in settings.DATABASES['default']['ENGINE']:
                    cursor.execute("DELETE FROM django_migrations")
                else:
                    cursor.execute('TRUNCATE TABLE django_migrations CASCADE')
                
                self.stdout.write('   ✓ Tabela django_migrations limpa')
                
        except Exception as e:
            self.stdout.write(f'   ⚠️  Erro ao limpar migrações: {str(e)}')

    def recriar_banco(self):
        """Recria o banco do zero"""
        try:
            # Fazer migrações iniciais
            call_command('makemigrations', verbosity=0)
            self.stdout.write('   ✓ Migrações iniciais criadas')
            
            # Aplicar migrações
            call_command('migrate', verbosity=0)
            self.stdout.write('   ✓ Migrações aplicadas')
            
            # Criar superusuário padrão
            from django.contrib.auth.models import User
            if not User.objects.filter(username='admin').exists():
                User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
                self.stdout.write('   ✓ Superusuário admin criado (admin/admin123)')
            
        except Exception as e:
            self.stdout.write(f'   ⚠️  Erro ao recriar banco: {str(e)}')
