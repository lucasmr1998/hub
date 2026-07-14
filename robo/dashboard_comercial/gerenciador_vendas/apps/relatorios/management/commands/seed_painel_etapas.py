"""Painel Operacional por Etapa — copia do operacional, com outro recorte.

Diferenca pro "Painel Operacional" (que e a FILA: o que esta parado e ha quanto
tempo): este olha o PIPELINE — quantas oportunidades tem em cada etapa do funil,
e como cada vendedora esta indo.

  Linha 1: um card por ETAPA aberta do pipeline (clicavel: abre a lista).
  Abaixo:  tabela de desempenho por vendedora (abertas, ganhas, perdidas,
           conversao, receita).

Os cards saem do PIPELINE DO TENANT, nao de uma lista fixa no codigo: se a
Nuvyon renomear ou criar etapa, e so rodar de novo.

Rodar:
    python manage.py seed_painel_etapas --tenant nuvyon
    python manage.py seed_painel_etapas --tenant nuvyon --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.relatorios.models import Dashboard, Widget
from apps.sistema.models import Tenant

NOME_DASHBOARD = 'Pipeline por Etapa'
CARDS_POR_LINHA = 4


class Command(BaseCommand):
    help = 'Cria/atualiza o painel de Pipeline por Etapa (cards por etapa + tabela por vendedora).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant (ex: nuvyon)')
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **opts):
        from apps.comercial.crm.models import PipelineEstagio

        try:
            tenant = Tenant.objects.get(slug=opts['tenant'], ativo=True)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant {opts['tenant']!r} nao encontrado."))
            return

        dry = opts['dry_run']

        # Etapas ABERTAS do funil (ganho/perdido nao sao fila, sao desfecho).
        etapas = list(
            PipelineEstagio.all_tenants
            .filter(tenant=tenant, is_final_ganho=False, is_final_perdido=False)
            .order_by('ordem', 'id')
        )
        if not etapas:
            self.stdout.write(self.style.ERROR('Tenant sem estagios abertos no pipeline.'))
            return

        dash, criado = Dashboard.all_tenants.get_or_create(
            tenant=tenant, nome=NOME_DASHBOARD, criado_por=None,
            defaults={
                'descricao': 'Quantas oportunidades tem em cada etapa do funil (clique no card '
                             'pra ver quais) e como cada vendedora esta indo.',
                'icone': 'bi-diagram-3',
                'setor': 'comercial',
                'compartilhado': True,
                'ordem': 2,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"dashboard #{dash.pk} {'criado' if criado else 'ja existia'}: {dash.nome}"
        ))

        largura = 12 // CARDS_POR_LINHA  # 3 colunas por card
        ordem = 0

        # --- Linha(s) 1: um card por etapa ---
        for i, etapa in enumerate(etapas):
            x = (i % CARDS_POR_LINHA) * largura
            y = (i // CARDS_POR_LINHA) * 2
            titulo = etapa.nome
            filtros = [
                {'campo': 'estagio__nome', 'operador': 'igual', 'valor': etapa.nome},
                {'campo': 'estagio__is_final_ganho', 'operador': 'igual', 'valor': False},
                {'campo': 'estagio__is_final_perdido', 'operador': 'igual', 'valor': False},
            ]
            if dry:
                self.stdout.write(f'  [DRY] numero  {titulo}  (x={x} y={y})')
                ordem += 1
                continue
            w, novo = Widget.objects.update_or_create(
                dashboard=dash, titulo=titulo,
                defaults={
                    'descricao': f'Oportunidades abertas paradas na etapa "{etapa.nome}". '
                                 f'Clique pra ver quais sao.',
                    'data_source': 'oportunidade',
                    'visualizacao': 'numero',
                    'metrica': {'tipo': 'count'},
                    'agrupamento': {},
                    'filtros': filtros,
                    'layout': {'x': x, 'y': y, 'w': largura, 'h': 2},
                    'config_extra': {},
                    'ordem': ordem,
                },
            )
            self.stdout.write(f"  {'+' if novo else '~'} #{w.pk} numero  {titulo}")
            ordem += 1

        linhas_cards = (len(etapas) + CARDS_POR_LINHA - 1) // CARDS_POR_LINHA
        y_tabela = linhas_cards * 2

        # --- Tabela de desempenho por vendedora ---
        tabela = {
            'titulo': 'Desempenho por vendedora',
            'descricao': 'Uma linha por vendedora: quantas oportunidades ela tem abertas, quantas '
                         'ganhou e perdeu no periodo, a conversao (ganhas sobre o que FECHOU) e a '
                         'receita. Conversao acima da media da equipe sai em verde.',
            'data_source': 'oportunidade',
            'visualizacao': 'tabela',
            'metrica': {'tipo': 'count'},
            'agrupamento': {'transform': 'scorecard_vendedor', 'dias': 30},
            'filtros': [],
            'layout': {'x': 0, 'y': y_tabela, 'w': 12, 'h': 6},
            'config_extra': {},
        }
        # --- Onde as oportunidades empilham (visao rapida do gargalo) ---
        barra = {
            'titulo': 'Oportunidades abertas por etapa',
            'descricao': 'Os mesmos numeros dos cards, em barra, pra ver de relance onde a fila '
                         'esta empilhando.',
            'data_source': 'oportunidade',
            'visualizacao': 'barra',
            'metrica': {'tipo': 'count'},
            'agrupamento': {'dimensao': 'estagio__nome'},
            'filtros': [
                {'campo': 'estagio__is_final_ganho', 'operador': 'igual', 'valor': False},
                {'campo': 'estagio__is_final_perdido', 'operador': 'igual', 'valor': False},
            ],
            'layout': {'x': 0, 'y': y_tabela + 6, 'w': 12, 'h': 4},
            'config_extra': {},
        }

        for spec in (tabela, barra):
            if dry:
                self.stdout.write(f"  [DRY] {spec['visualizacao']:<7} {spec['titulo']}")
                ordem += 1
                continue
            w, novo = Widget.objects.update_or_create(
                dashboard=dash, titulo=spec['titulo'],
                defaults={**{k: v for k, v in spec.items() if k != 'titulo'}, 'ordem': ordem},
            )
            self.stdout.write(f"  {'+' if novo else '~'} #{w.pk} {spec['visualizacao']:<7} {spec['titulo']}")
            ordem += 1

        if dry:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('\nDRY-RUN: nada gravado.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n{NOME_DASHBOARD} pronto: /dashboards/{dash.pk}/ '
                f'({len(etapas)} etapas + tabela + barra)'
            ))
