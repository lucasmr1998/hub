"""Worker que abre Atendimento+OS no Matrix pra NewService finalizados.

Quando um cliente Hubsoft contrata um Novo Serviço pelo WhatsApp, o fluxo
IA termina marcando o NewService como 'finalizado' (sem nenhuma integração
externa nesse momento — só registro local).

Este command roda periodicamente (cron/systemd timer), busca os NewServices
com:
    - status='finalizado'
    - matrix_sync_status in ('pendente', 'erro')
e tenta abrir Atendimento + OS de Instalação no Matrix, usando a data e
turno escolhidos pelo cliente.

Idempotente: pode ser chamado várias vezes, só processa o que ainda não
foi sincronizado.

Rodar a cada 5–10 minutos via cron ou systemd timer:

    */10 * * * * cd /path/projeto && venv/bin/python manage.py \\
                 processar_newservice_finalizados

Uso direto:
    python manage.py processar_newservice_finalizados
    python manage.py processar_newservice_finalizados --max-tentativas 10
    python manage.py processar_newservice_finalizados --new-service-id 5
"""
from __future__ import annotations

import logging
import traceback

from django.core.management.base import BaseCommand

from integracoes.services.agendamento_new_service import (
    executar_agendamento_new_service,
)
from vendas_web.models import NewService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Abre Atendimento+OS no Matrix pra NewServices finalizados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-tentativas', type=int, default=20,
            help='NewServices que já tentaram mais que isso e ainda estão '
                 'pendentes viram "erro" (default: 20).',
        )
        parser.add_argument(
            '--new-service-id', type=int, default=None,
            help='Processa apenas um NewService específico (debug).',
        )
        parser.add_argument(
            '--incluir-erro', action='store_true',
            help='Reprocessa também os que estão em status erro (retry manual).',
        )
        parser.add_argument(
            '--delay-min', type=int, default=2,
            help='Janela mínima em minutos após finalizado_em antes de processar '
                 '(default: 2). Garante que o webdriver criou o serviço no Hubsoft.',
        )
        parser.add_argument(
            '--agora', action='store_true',
            help='Ignora a janela --delay-min e processa imediatamente (debug).',
        )

    def handle(self, *args, **opts):
        from datetime import timedelta
        from django.utils import timezone

        max_tent = opts['max_tentativas']
        ns_id = opts.get('new_service_id')
        incluir_erro = opts.get('incluir_erro', False)
        # Janela mínima após finalizado_em — garante que o webdriver teve
        # tempo de criar o serviço no Hubsoft (~1-2 min). Pulável via --agora.
        delay_min = opts.get('delay_min', 2)
        agora_flag = opts.get('agora', False)

        # Critério padrão: finalizado + sync pendente.
        # Com --incluir-erro: também tenta de novo os que falharam.
        status_sync_alvo = ['pendente']
        if incluir_erro:
            status_sync_alvo.append('erro')

        qs = NewService.objects.filter(
            status='finalizado',
            matrix_sync_status__in=status_sync_alvo,
        ).select_related('lead')

        # Filtro de janela do webdriver — só processa NS cujo finalizado_em
        # foi há pelo menos `delay_min` minutos. Sem isso, processaríamos
        # antes do webdriver criar o serviço no Hubsoft → matcher acha
        # serviço antigo OU None.
        if not agora_flag and not ns_id:
            corte = timezone.now() - timedelta(minutes=delay_min)
            qs = qs.filter(finalizado_em__lte=corte)

        if ns_id:
            qs = qs.filter(pk=ns_id)

        total = qs.count()
        if not total:
            self.stdout.write('Nenhum NewService finalizado pendente de sync.')
            return

        self.stdout.write(
            f'Processando {total} NewService(s) '
            f'(janela mínima: {delay_min} min após finalização)...'
        )

        sincronizados = 0
        ainda_pendente = 0
        erros = 0
        pulados = 0

        for ns in qs:
            # Pula os que excederam o limite de tentativas (vira erro pra
            # análise manual — operador olha no admin e age)
            if ns.tentativas_sync_matrix >= max_tent:
                ns.matrix_sync_status = 'erro'
                ns.ultimo_erro_sync_matrix = (
                    f'Excedeu {max_tent} tentativas. Requer análise manual. '
                    f'Último erro: {ns.ultimo_erro_sync_matrix}'
                )[:1000]
                ns.save(update_fields=[
                    'matrix_sync_status', 'ultimo_erro_sync_matrix',
                    'atualizado_em',
                ])
                pulados += 1
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ ns={ns.pk} lead={ns.lead_id}: excedeu tentativas → erro'
                ))
                continue

            try:
                resultado = executar_agendamento_new_service(ns)
            except Exception as e:
                erros += 1
                logger.exception('Erro inesperado processar ns=%s: %s', ns.pk, e)
                # Persiste como erro pra próxima rodada não tentar de novo
                # se for problema permanente
                ns.matrix_sync_status = 'erro'
                ns.ultimo_erro_sync_matrix = (
                    f'Exceção inesperada: {e}\n{traceback.format_exc()[-500:]}'
                )[:1000]
                ns.tentativas_sync_matrix += 1
                ns.save(update_fields=[
                    'matrix_sync_status', 'ultimo_erro_sync_matrix',
                    'tentativas_sync_matrix', 'atualizado_em',
                ])
                self.stdout.write(self.style.ERROR(
                    f'  ✗ ns={ns.pk}: exceção {e}'
                ))
                continue

            status_res = resultado.get('status', '')
            if status_res in ('sincronizado', 'ja_sincronizado'):
                sincronizados += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ ns={ns.pk} lead={ns.lead_id}: atendimento='
                    f'{resultado.get("id_atendimento")} os={resultado.get("id_os")}'
                ))
            elif status_res == 'aguardando_sync':
                ainda_pendente += 1
                self.stdout.write(
                    f'  ⏳ ns={ns.pk}: cliente Hubsoft ainda não sincronizado '
                    f'(tentativa {ns.tentativas_sync_matrix})'
                )
            else:
                erros += 1
                self.stdout.write(self.style.ERROR(
                    f'  ✗ ns={ns.pk}: {resultado.get("mensagem", "erro desconhecido")}'
                ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Resumo: {sincronizados} sincronizados | {ainda_pendente} pendentes | '
            f'{erros} erros | {pulados} pulados'
        ))
