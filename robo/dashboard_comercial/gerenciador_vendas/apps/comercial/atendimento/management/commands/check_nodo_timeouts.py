"""
Verifica timeouts em nodos de fluxos de atendimento.

Para cada AtendimentoFluxo ativo onde:
- nodo_atual.configuracao tem 'timeout_segundos' definido
- data_ultima_atividade < now - timeout_segundos
- Existe conexão tipo_saida='timeout' saindo do nodo_atual

Move o atendimento pro nodo de destino do timeout e dispara a execução do
caminho alternativo.

Uso:
    python manage.py check_nodo_timeouts --settings=gerenciador_vendas.settings_local

Crontab (a cada 1 minuto):
    * * * * * cd /path/to/project && python manage.py check_nodo_timeouts >> /var/log/timeouts.log 2>&1
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Detecta atendimentos com timeout no nodo atual e segue caminho alternativo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Lista atendimentos com timeout sem aplicar transição',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Máximo de atendimentos a processar nesta rodada (default: 100)',
        )

    def handle(self, *args, **options):
        from apps.comercial.atendimento.models import (
            AtendimentoFluxo, ConexaoNodoAtendimento,
        )
        from apps.comercial.atendimento.engine import _percorrer_a_partir_de

        dry = options['dry_run']
        limit = options['limit']
        agora = timezone.now()

        # Atendimentos ativos com nodo atual tendo timeout configurado
        ativos = (
            AtendimentoFluxo.objects
            .filter(status__in=['em_andamento', 'aguardando_resposta', 'ativo'])
            .filter(nodo_atual__isnull=False)
            .select_related('nodo_atual', 'fluxo', 'lead', 'tenant')
        )

        processados = 0
        timeouts_aplicados = 0
        for atendimento in ativos[:limit * 5]:  # filtro Python à frente
            if processados >= limit:
                break

            nodo = atendimento.nodo_atual
            if not nodo or not nodo.configuracao:
                continue

            timeout_seg = nodo.configuracao.get('timeout_segundos')
            if not timeout_seg or not isinstance(timeout_seg, (int, float)) or timeout_seg <= 0:
                continue

            tempo_no_nodo = (agora - atendimento.data_ultima_atividade).total_seconds()
            if tempo_no_nodo < timeout_seg:
                continue

            processados += 1

            # Achar conexão de timeout
            conexao_timeout = (
                ConexaoNodoAtendimento.objects
                .filter(nodo_origem=nodo, tipo_saida='timeout')
                .select_related('nodo_destino')
                .first()
            )

            if not conexao_timeout:
                msg = (
                    f'[Timeout SEM caminho] Atendimento #{atendimento.id} '
                    f'em nodo #{nodo.id} ({nodo.tipo}) há {tempo_no_nodo:.0f}s, '
                    f'mas nenhuma conexão tipo_saida=timeout configurada. Pulando.'
                )
                self.stdout.write(self.style.WARNING(msg))
                logger.warning(msg)
                continue

            destino = conexao_timeout.nodo_destino
            msg = (
                f'[Timeout] Atendimento #{atendimento.id} '
                f'(lead: {atendimento.lead.nome_razaosocial if atendimento.lead else "?"}) '
                f'em nodo #{nodo.id} há {tempo_no_nodo:.0f}s '
                f'(limite: {timeout_seg}s) → mover para nodo #{destino.id} ({destino.tipo})'
            )
            self.stdout.write(self.style.SUCCESS(msg))
            logger.info(msg)

            if dry:
                continue

            try:
                contexto = atendimento.dados_respostas or {}
                _percorrer_a_partir_de(atendimento, destino, contexto)
                timeouts_aplicados += 1
            except Exception as exc:
                err = f'Erro ao aplicar timeout em #{atendimento.id}: {exc}'
                self.stdout.write(self.style.ERROR(err))
                logger.error(err)

        resumo = (
            f'\n=== Resumo ==='
            f'\nAtendimentos com timeout detectado: {processados}'
            f'\nTimeouts aplicados: {timeouts_aplicados}'
            f'\nModo: {"dry-run (sem alteração)" if dry else "aplicado"}'
        )
        self.stdout.write(resumo)
