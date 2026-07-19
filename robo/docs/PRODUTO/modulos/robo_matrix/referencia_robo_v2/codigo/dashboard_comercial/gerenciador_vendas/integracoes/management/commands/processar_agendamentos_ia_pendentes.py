"""Worker que reprocessa agendamentos IA que ficaram pendentes.

Quando o cliente confirma o agendamento no WhatsApp mas o sync com Hubsoft
ainda não rodou (cliente novo, recém-cadastrado), o agendamento fica em
'aguardando_sync'. Este command roda periodicamente (via cron) e tenta
de novo — se o sync já trouxe o cliente, o agendamento é finalizado.

Rodar via cron a cada ~5min, após o sincronizar_clientes:

    */5 * * * * cd /path/projeto && venv/bin/python manage.py \\
                processar_agendamentos_ia_pendentes

Uso direto:
    python manage.py processar_agendamentos_ia_pendentes
    python manage.py processar_agendamentos_ia_pendentes --max-tentativas 10
    python manage.py processar_agendamentos_ia_pendentes --lead-id 123
"""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

from integracoes.models import AgendamentoInstalacaoIA
from integracoes.services.agendamento_ia import executar_agendamento

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reprocessa agendamentos IA pendentes (aguardando sync Hubsoft).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-tentativas', type=int, default=20,
            help='Pula agendamentos que já tentaram mais do que esse número '
                 '(default: 20). Vira "erro" para análise manual.',
        )
        parser.add_argument(
            '--lead-id', type=int, default=None,
            help='Processa apenas o agendamento de um lead específico (debug).',
        )

    def handle(self, *args, **opts):
        max_tent = opts['max_tentativas']
        lead_id = opts.get('lead_id')

        qs = AgendamentoInstalacaoIA.objects.filter(status='aguardando_sync')
        if lead_id:
            qs = qs.filter(lead_id=lead_id)

        total = qs.count()
        if not total:
            self.stdout.write('Nenhum agendamento pendente.')
            return

        self.stdout.write(f'Processando {total} agendamento(s) pendente(s)...')

        agendados = 0
        ainda_pendente = 0
        erros = 0
        pulados = 0

        for ag in qs.select_related('lead'):
            if ag.tentativas >= max_tent:
                ag.status = 'erro'
                ag.ultimo_erro = (
                    f'Excedeu {max_tent} tentativas sem encontrar ClienteHubsoft '
                    f'vinculado. Análise manual necessária.'
                )
                ag.save(update_fields=['status', 'ultimo_erro', 'data_atualizacao'])
                pulados += 1
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ ag={ag.pk} lead={ag.lead_id}: excedeu tentativas → erro'
                ))
                continue

            try:
                resultado = executar_agendamento(ag)
            except Exception as e:
                logger.exception('Erro inesperado processando ag=%s', ag.pk)
                erros += 1
                self.stdout.write(self.style.ERROR(
                    f'  ✗ ag={ag.pk} lead={ag.lead_id}: {e}'
                ))
                continue

            status = resultado.get('status')
            if status == 'agendado':
                agendados += 1
                try:
                    from crm.services.indicacao_pipeline import sincronizar_indicacao_do_lead
                    sincronizar_indicacao_do_lead(ag.lead_id)
                except Exception as e:  # noqa: BLE001
                    logger.warning('Sync indicação após agendamento lead %s: %s', ag.lead_id, e)
                dados = resultado.get('dados', {})
                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ ag={ag.pk} lead={ag.lead_id} → '
                    f'agendado {dados.get("data")} {dados.get("turno")} '
                    f'tecnico={dados.get("nome_tecnico")}'
                ))
            elif status == 'aguardando_sync':
                ainda_pendente += 1
                self.stdout.write(
                    f'  · ag={ag.pk} lead={ag.lead_id}: ainda sem ClienteHubsoft'
                )
            else:
                erros += 1
                self.stdout.write(self.style.ERROR(
                    f'  ✗ ag={ag.pk} lead={ag.lead_id}: '
                    f'{resultado.get("mensagem", "erro desconhecido")}'
                ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Resumo: {agendados} agendados, {ainda_pendente} ainda pendentes, '
            f'{erros} erros, {pulados} esgotaram tentativas.'
        ))
