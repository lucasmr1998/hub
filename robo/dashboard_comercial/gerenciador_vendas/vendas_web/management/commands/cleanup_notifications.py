from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
import logging

from apps.notificacoes.models import Notificacao

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Limpa notificações antigas do banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Número de dias para manter notificações (padrão: 30)'
        )
        parser.add_argument(
            '--keep-failed',
            type=int,
            default=7,
            help='Número de dias para manter notificações falhadas (padrão: 7)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula a limpeza sem deletar registros'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força a limpeza mesmo com poucos registros'
        )

    def handle(self, *args, **options):
        days = options['days']
        keep_failed_days = options['keep_failed']
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Iniciando limpeza de notificações...\n'
                f'Manter notificações por: {days} dias\n'
                f'Manter falhas por: {keep_failed_days} dias\n'
                f'Dry run: {dry_run}\n'
                f'Force: {force}'
            )
        )
        
        try:
            # Estatísticas iniciais
            total_inicial = Notificacao.objects.count()
            self.stdout.write(f'Total de notificações: {total_inicial}')
            
            if total_inicial < 1000 and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f'Poucas notificações ({total_inicial}). Use --force para continuar.'
                    )
                )
                return
            
            # Calcular datas limite
            agora = timezone.now()
            limite_geral = agora - timedelta(days=days)
            limite_falhas = agora - timedelta(days=keep_failed_days)
            
            # Notificações para deletar
            query_geral = Q(data_criacao__lt=limite_geral)
            query_falhas = Q(
                status='falhou',
                data_criacao__lt=limite_falhas
            )
            
            # Notificações enviadas antigas
            notificacoes_antigas = Notificacao.objects.filter(
                query_geral,
                status__in=['enviada', 'cancelada']
            )
            
            # Notificações falhadas antigas
            notificacoes_falhas_antigas = Notificacao.objects.filter(query_falhas)
            
            # Contar registros
            count_antigas = notificacoes_antigas.count()
            count_falhas_antigas = notificacoes_falhas_antigas.count()
            total_para_deletar = count_antigas + count_falhas_antigas
            
            self.stdout.write(f'\nNotificações antigas (>{days} dias): {count_antigas}')
            self.stdout.write(f'Falhas antigas (>{keep_failed_days} dias): {count_falhas_antigas}')
            self.stdout.write(f'Total para deletar: {total_para_deletar}')
            
            if total_para_deletar == 0:
                self.stdout.write(
                    self.style.SUCCESS('Nenhuma notificação antiga encontrada.')
                )
                return
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING('MODO DRY-RUN: Nenhum registro foi deletado')
                )
                self._show_sample_records(notificacoes_antigas, notificacoes_falhas_antigas)
            else:
                # Confirmar antes de deletar
                if not self._confirm_deletion(total_para_deletar):
                    self.stdout.write('Operação cancelada pelo usuário.')
                    return
                
                # Deletar registros
                deleted_antigas = notificacoes_antigas.delete()[0]
                deleted_falhas = notificacoes_falhas_antigas.delete()[0]
                total_deleted = deleted_antigas + deleted_falhas
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Limpeza concluída!\n'
                        f'Deletadas: {total_deleted} notificações\n'
                        f'  - Antigas: {deleted_antigas}\n'
                        f'  - Falhas: {deleted_falhas}'
                    )
                )
                
                # Estatísticas finais
                total_final = Notificacao.objects.count()
                self.stdout.write(f'Total restante: {total_final}')
                self.stdout.write(f'Espaço liberado: {total_inicial - total_final} registros')
            
        except Exception as e:
            logger.error(f"Erro durante a limpeza de notificações: {e}", exc_info=True)
            self.stdout.write(
                self.style.ERROR(f'Erro durante a limpeza: {e}')
            )

    def _confirm_deletion(self, count):
        """Confirma a deleção com o usuário"""
        self.stdout.write(
            self.style.WARNING(
                f'ATENÇÃO: {count} notificações serão deletadas permanentemente!'
            )
        )
        
        while True:
            response = input('Deseja continuar? (s/N): ').lower().strip()
            if response in ['s', 'sim', 'y', 'yes']:
                return True
            elif response in ['n', 'não', 'nao', 'no', '']:
                return False
            else:
                self.stdout.write('Por favor, responda "s" para sim ou "n" para não.')

    def _show_sample_records(self, notificacoes_antigas, notificacoes_falhas_antigas):
        """Mostra uma amostra dos registros que seriam deletados"""
        self.stdout.write(f'\n{self.style.HTTP_INFO("Amostra de registros que seriam deletados:")}')
        
        # Amostra de notificações antigas
        if notificacoes_antigas.exists():
            self.stdout.write('\nNotificações antigas:')
            for notif in notificacoes_antigas[:5]:
                self.stdout.write(
                    f'  ID: {notif.id} | '
                    f'Tipo: {notif.tipo.nome} | '
                    f'Status: {notif.status} | '
                    f'Data: {notif.data_criacao.strftime("%d/%m/%Y %H:%M")}'
                )
            
            if notificacoes_antigas.count() > 5:
                self.stdout.write(f'  ... e mais {notificacoes_antigas.count() - 5} registros')
        
        # Amostra de falhas antigas
        if notificacoes_falhas_antigas.exists():
            self.stdout.write('\nFalhas antigas:')
            for notif in notificacoes_falhas_antigas[:5]:
                self.stdout.write(
                    f'  ID: {notif.id} | '
                    f'Tipo: {notif.tipo.nome} | '
                    f'Tentativas: {notif.tentativas}/{notif.max_tentativas} | '
                    f'Data: {notif.data_criacao.strftime("%d/%m/%Y %H:%M")}'
                )
            
            if notificacoes_falhas_antigas.count() > 5:
                self.stdout.write(f'  ... e mais {notificacoes_falhas_antigas.count() - 5} registros')
