from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q, F
from datetime import timedelta
import logging

from apps.notificacoes.models import Notificacao
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Processa notificações pendentes e falhas que precisam de retry'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Número máximo de notificações para processar por vez (padrão: 50)'
        )
        parser.add_argument(
            '--max-age-hours',
            type=int,
            default=24,
            help='Idade máxima em horas para processar notificações pendentes (padrão: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula o processamento sem enviar notificações'
        )
        parser.add_argument(
            '--force-retry',
            action='store_true',
            help='Força retry de notificações que já atingiram o máximo de tentativas'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        max_age_hours = options['max_age_hours']
        dry_run = options['dry_run']
        force_retry = options['force_retry']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Iniciando processamento de notificações...\n'
                f'Batch size: {batch_size}\n'
                f'Max age: {max_age_hours}h\n'
                f'Dry run: {dry_run}\n'
                f'Force retry: {force_retry}'
            )
        )
        
        try:
            # Estatísticas iniciais
            stats = self._get_initial_stats()
            self._print_stats('Estatísticas iniciais', stats)
            
            # Processar notificações
            if not dry_run:
                processed_count = self._process_notifications(
                    batch_size, max_age_hours, force_retry
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Processadas {processed_count} notificações')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('MODO DRY-RUN: Nenhuma notificação foi enviada')
                )
                self._simulate_processing(batch_size, max_age_hours, force_retry)
            
            # Estatísticas finais
            final_stats = self._get_initial_stats()
            self._print_stats('Estatísticas finais', final_stats)
            
            # Mostrar mudanças
            self._show_changes(stats, final_stats)
            
        except Exception as e:
            logger.error(f"Erro durante o processamento de notificações: {e}", exc_info=True)
            self.stdout.write(
                self.style.ERROR(f'Erro durante o processamento: {e}')
            )

    def _get_initial_stats(self):
        """Obtém estatísticas iniciais das notificações"""
        return {
            'total': Notificacao.objects.count(),
            'pendentes': Notificacao.objects.filter(status='pendente').count(),
            'enviando': Notificacao.objects.filter(status='enviando').count(),
            'enviadas': Notificacao.objects.filter(status='enviada').count(),
            'falhas': Notificacao.objects.filter(status='falhou').count(),
            'canceladas': Notificacao.objects.filter(status='cancelada').count(),
        }

    def _print_stats(self, title, stats):
        """Imprime estatísticas formatadas"""
        self.stdout.write(f'\n{self.style.HTTP_INFO(title)}:')
        self.stdout.write(f'  Total: {stats["total"]}')
        self.stdout.write(f'  Pendentes: {stats["pendentes"]}')
        self.stdout.write(f'  Enviando: {stats["enviando"]}')
        self.stdout.write(f'  Enviadas: {stats["enviadas"]}')
        self.stdout.write(f'  Falhas: {stats["falhas"]}')
        self.stdout.write(f'  Canceladas: {stats["canceladas"]}')

    def _process_notifications(self, batch_size, max_age_hours, force_retry):
        """Processa notificações pendentes"""
        agora = timezone.now()
        limite_idade = agora - timedelta(hours=max_age_hours)
        
        # Construir query base
        query = Q(status__in=['pendente', 'falhou'])
        
        # Filtrar por idade se especificado
        if max_age_hours > 0:
            query &= Q(data_criacao__gte=limite_idade)
        
        # Filtrar tentativas
        if not force_retry:
            query &= Q(tentativas__lt=F('max_tentativas'))
        
        # Buscar notificações para processar
        notificacoes = Notificacao.objects.filter(query).order_by(
            'prioridade', 'data_criacao'
        )[:batch_size]
        
        processed_count = 0
        
        self.stdout.write(self.style.WARNING('Sistema de notificações temporariamente desativado.'))
        return 0

    def _simulate_processing(self, batch_size, max_age_hours, force_retry):
        """Simula o processamento para dry-run"""
        agora = timezone.now()
        limite_idade = agora - timedelta(hours=max_age_hours)
        
        query = Q(status__in=['pendente', 'falhou'])
        
        if max_age_hours > 0:
            query &= Q(data_criacao__gte=limite_idade)
        
        if not force_retry:
            query &= Q(tentativas__lt=F('max_tentativas'))
        
        notificacoes = Notificacao.objects.filter(query).order_by(
            'prioridade', 'data_criacao'
        )[:batch_size]
        
        self.stdout.write(f'\n{self.style.WARNING("Notificações que seriam processadas:")}')
        
        for notif in notificacoes:
            self.stdout.write(
                f'  ID: {notif.id} | '
                f'Tipo: {notif.tipo.nome} | '
                f'Canal: {notif.canal.nome} | '
                f'Status: {notif.status} | '
                f'Tentativas: {notif.tentativas}/{notif.max_tentativas} | '
                f'Prioridade: {notif.prioridade}'
            )

    def _show_changes(self, initial_stats, final_stats):
        """Mostra as mudanças nas estatísticas"""
        self.stdout.write(f'\n{self.style.HTTP_INFO("Mudanças:")}')
        
        for key in initial_stats:
            change = final_stats[key] - initial_stats[key]
            if change != 0:
                color = self.style.SUCCESS if change > 0 else self.style.ERROR
                self.stdout.write(f'  {key}: {change:+d} ({color(change)})')
            else:
                self.stdout.write(f'  {key}: {change:+d}')