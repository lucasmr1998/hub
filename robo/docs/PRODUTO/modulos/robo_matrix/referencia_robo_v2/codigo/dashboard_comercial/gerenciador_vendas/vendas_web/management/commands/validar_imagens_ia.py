"""Validador automático de imagens de documentação via OpenAI Vision.

Escopo (fase 1): apenas leads com `origem='site'` e imagens com status
`pendente`. Marca como `documentos_validos` ou `documentos_rejeitados`
e grava o motivo na `observacao_validacao`.

Roda via systemd timer (a cada N min) ou manualmente.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from vendas_web.models import ImagemLeadProspecto
from vendas_web.services.validador_imagens import ValidadorImagens

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        'Valida imagens pendentes via OpenAI Vision. Escopo inicial: '
        'leads com origem="site" apenas.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--imagem-id', type=int,
            help='Validar apenas a imagem com este ID.',
        )
        parser.add_argument(
            '--lead-id', type=int,
            help='Validar todas as imagens pendentes deste lead.',
        )
        parser.add_argument(
            '--origem', type=str, default='site',
            help='Origem do lead a ser processada (padrão: "site").',
        )
        parser.add_argument(
            '--limite', type=int, default=10,
            help='Máximo de imagens por execução (padrão: 10).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Apenas lista o que faria, sem chamar OpenAI nem atualizar.',
        )
        parser.add_argument(
            '--reprocessar', action='store_true',
            help='Inclui já validadas (válidas E rejeitadas) — útil pra calibragem.',
        )
        parser.add_argument(
            '--minutos-cooldown', type=int, default=10,
            help='Não revalidar imagens validadas a menos de N min atrás (padrão: 10).',
        )

    def handle(self, *args, **options):
        try:
            validador = ValidadorImagens()
        except RuntimeError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        # Filtra imagens elegíveis
        if options['imagem_id']:
            qs = ImagemLeadProspecto.objects.filter(pk=options['imagem_id'])
        elif options['lead_id']:
            qs = ImagemLeadProspecto.objects.filter(lead_id=options['lead_id'])
            if not options['reprocessar']:
                qs = qs.filter(status_validacao=ImagemLeadProspecto.STATUS_PENDENTE)
        else:
            origem = options['origem']
            qs = ImagemLeadProspecto.objects.filter(lead__origem=origem)
            if not options['reprocessar']:
                qs = qs.filter(status_validacao=ImagemLeadProspecto.STATUS_PENDENTE)
            # Cooldown — evita reprocessar logo após uma validação automática
            if options['reprocessar']:
                corte = timezone.now() - timedelta(minutes=options['minutos_cooldown'])
                qs = qs.filter(data_validacao__lt=corte) | qs.filter(data_validacao__isnull=True)

        qs = qs.select_related('lead').order_by('id')
        imagens = list(qs[:options['limite']])

        if not imagens:
            self.stdout.write(self.style.WARNING('Nenhuma imagem pendente encontrada.'))
            return

        self.stdout.write(f'Validando {len(imagens)} imagem(ns)...\n')

        total_aprovadas = 0
        total_rejeitadas = 0
        custo_total = 0.0

        for img in imagens:
            self.stdout.write(
                f'  #{img.id} | lead={img.lead_id} ({img.lead.nome_razaosocial[:30]}) | '
                f'{img.descricao!r}... ',
                ending='',
            )

            if options['dry_run']:
                self.stdout.write(self.style.WARNING('[DRY-RUN] pulado'))
                continue

            resultado = validador.validar(img)
            custo_total += resultado.custo_estimado

            img.status_validacao = (
                ImagemLeadProspecto.STATUS_VALIDO if resultado.aprovado
                else ImagemLeadProspecto.STATUS_REJEITADO
            )
            img.observacao_validacao = resultado.motivo
            img.data_validacao = timezone.now()
            img.validado_por = 'IA OpenAI (gpt-4o-mini)'
            img.save(update_fields=[
                'status_validacao', 'observacao_validacao',
                'data_validacao', 'validado_por',
            ])

            if resultado.aprovado:
                self.stdout.write(self.style.SUCCESS(f'APROVADA — {resultado.motivo[:80]}'))
                total_aprovadas += 1
            else:
                self.stdout.write(self.style.ERROR(f'REJEITADA — {resultado.motivo[:80]}'))
                total_rejeitadas += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Concluído: {total_aprovadas} aprovada(s), {total_rejeitadas} rejeitada(s) | '
            f'custo estimado: ${custo_total:.4f}'
        ))
