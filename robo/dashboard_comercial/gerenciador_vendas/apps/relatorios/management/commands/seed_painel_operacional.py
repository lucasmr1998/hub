"""Cria o PAINEL OPERACIONAL do comercial (fila de trabalho do dia).

Diferenca pro painel executivo: o executivo e um PLACAR (quanto vendemos, qual
a conversao, como evoluiu). O operacional e uma FILA: o que esta parado, ha
quanto tempo, e de quem e. Cada card e uma pilha de trabalho, nao uma
estatistica — por isso todos abrem lista (drill-down) com link pra ficha.

O desenho saiu dos dados reais da Nuvyon, nao de teoria:
  - 44% das perdas sao "Sem retorno" (contra 9 pra concorrente): a Nuvyon
    quase nao perde pro mercado, perde pro proprio processo. Dai o card mais
    importante ser "leads sem nenhum contato".
  - Tarefas de follow-up ficaram DE FORA: o modulo tem zero uso no tenant.
    Card que marca zero pra sempre ensina a equipe a ignorar o painel.

Rodar:
    python manage.py seed_painel_operacional --tenant nuvyon
    python manage.py seed_painel_operacional --tenant nuvyon --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.relatorios.models import Dashboard, Widget
from apps.sistema.models import Tenant


# (titulo, descricao, data_source, visualizacao, metrica, agrupamento, filtros, layout, config_extra)
WIDGETS = [
    # ---- Linha 1: a fila do dia (6 KPIs, largura 2 = 12 colunas) ----
    (
        'Leads sem contato',
        'Leads que entraram e NINGUEM atendeu ainda (zero contatos registrados). '
        'E aqui que a venda vaza: 44% das perdas da base sao "sem retorno". '
        'Clique pra ver a lista e distribuir.',
        'lead', 'numero', {'tipo': 'count'}, {},
        [{'campo': 'qtd_contatos', 'operador': 'igual', 'valor': 0}],
        {'x': 0, 'y': 0, 'w': 2, 'h': 2},
        {'sentido': 'menor_melhor'},
    ),
    (
        'Sem contato ha 3+ dias',
        'Dos leads sem contato, os que ja passaram de 3 dias. Estes sao os que '
        'provavelmente ja fecharam com outro provedor.',
        'lead', 'numero', {'tipo': 'count'}, {},
        [{'campo': 'qtd_contatos', 'operador': 'igual', 'valor': 0},
         {'campo': 'data_cadastro', 'operador': 'ha_mais_de_dias', 'valor': 3}],
        {'x': 2, 'y': 0, 'w': 2, 'h': 2},
        {'sentido': 'menor_melhor'},
    ),
    (
        'Cadastro travado',
        'Lead que JA escolheu o plano mas esta sem CPF. A venda esta a um passo '
        'de fechar e parou por falta de documento.',
        'lead', 'numero', {'tipo': 'count'}, {},
        [{'campo': 'id_plano_rp', 'operador': 'existe', 'valor': ''},
         {'campo': 'cpf_cnpj', 'operador': 'nao_existe', 'valor': ''}],
        {'x': 4, 'y': 0, 'w': 2, 'h': 2},
        {'sentido': 'menor_melhor'},
    ),
    (
        'Oportunidades sem dono',
        'Oportunidades abertas sem vendedora responsavel. Ninguem atende o que '
        'nao e de ninguem.',
        'oportunidade', 'numero', {'tipo': 'count'}, {},
        [{'campo': 'responsavel__username', 'operador': 'nao_existe', 'valor': ''},
         {'campo': 'estagio__is_final_ganho', 'operador': 'igual', 'valor': False},
         {'campo': 'estagio__is_final_perdido', 'operador': 'igual', 'valor': False}],
        {'x': 6, 'y': 0, 'w': 2, 'h': 2},
        {'sentido': 'menor_melhor'},
    ),
    (
        'Paradas ha 7+ dias',
        'Oportunidades abertas que estao no mesmo estagio ha mais de 7 dias. '
        'Negociacao esfriando.',
        'oportunidade', 'numero', {'tipo': 'count'}, {},
        [{'campo': 'data_entrada_estagio', 'operador': 'ha_mais_de_dias', 'valor': 7},
         {'campo': 'estagio__is_final_ganho', 'operador': 'igual', 'valor': False},
         {'campo': 'estagio__is_final_perdido', 'operador': 'igual', 'valor': False}],
        {'x': 8, 'y': 0, 'w': 2, 'h': 2},
        {'sentido': 'menor_melhor'},
    ),
    (
        'Instalacoes pendentes',
        'Vendas fechadas esperando o tecnico instalar, segundo o HubSoft. '
        'Depende do sync de status rodar: se congelar, este numero infla.',
        'servico_hubsoft', 'numero', {'tipo': 'count'}, {},
        [{'campo': 'status_prefixo', 'operador': 'igual', 'valor': 'aguardando_instalacao'}],
        {'x': 10, 'y': 0, 'w': 2, 'h': 2},
        {'sentido': 'menor_melhor'},
    ),

    # ---- Linha 2: quem esta afogada e quem esta ociosa ----
    (
        'Carga por vendedora (abertas)',
        'Oportunidades abertas por vendedora. Serve pra equilibrar a fila: '
        'clique na barra pra ver as dela.',
        'oportunidade', 'barra', {'tipo': 'count'},
        {'dimensao': 'responsavel__first_name'},
        [{'campo': 'estagio__is_final_ganho', 'operador': 'igual', 'valor': False},
         {'campo': 'estagio__is_final_perdido', 'operador': 'igual', 'valor': False}],
        {'x': 0, 'y': 2, 'w': 6, 'h': 4},
        {},
    ),
    (
        'Onde as oportunidades estao paradas',
        'Oportunidades abertas por estagio do funil. Mostra onde a fila esta '
        'empilhando agora (nao e historico).',
        'oportunidade', 'barra', {'tipo': 'count'},
        {'dimensao': 'estagio__nome'},
        [{'campo': 'estagio__is_final_ganho', 'operador': 'igual', 'valor': False},
         {'campo': 'estagio__is_final_perdido', 'operador': 'igual', 'valor': False}],
        {'x': 6, 'y': 2, 'w': 6, 'h': 4},
        {},
    ),

    # ---- Linha 3: o que esta chegando e o que esta se perdendo ----
    (
        'Atendimentos por dia (14d)',
        'Volume de atendimentos por dia. Queda aqui antecede queda de venda '
        'duas semanas depois.',
        'historico_contato', 'linha', {'tipo': 'count'},
        {'dimensao': 'data_hora_contato', 'granularidade': 'dia'},
        [{'campo': 'data_hora_contato', 'operador': 'ultimos_dias', 'valor': 14}],
        {'x': 0, 'y': 6, 'w': 6, 'h': 4},
        {},
    ),
    (
        'Motivos de perda (7d)',
        'Por que perdemos nos ultimos 7 dias. Clique na barra pra ver quais '
        'oportunidades foram.',
        'oportunidade', 'barra', {'tipo': 'count'},
        {'dimensao': 'motivo_perda_ref__nome'},
        [{'campo': 'estagio__is_final_perdido', 'operador': 'igual', 'valor': True},
         {'campo': 'data_fechamento_real', 'operador': 'ultimos_dias', 'valor': 7}],
        {'x': 6, 'y': 6, 'w': 6, 'h': 4},
        {},
    ),
]


class Command(BaseCommand):
    help = 'Cria/atualiza o Painel Operacional do comercial (fila do dia).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant (ex: nuvyon)')
        parser.add_argument('--dry-run', action='store_true',
                            help='So mostra o que faria; nao grava.')

    @transaction.atomic
    def handle(self, *args, **opts):
        try:
            tenant = Tenant.objects.get(slug=opts['tenant'], ativo=True)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant {opts['tenant']!r} nao encontrado."))
            return

        dry = opts['dry_run']

        dash, criado = Dashboard.all_tenants.get_or_create(
            tenant=tenant, nome='Painel Operacional', criado_por=None,
            defaults={
                'descricao': 'A fila do dia: o que esta parado, ha quanto tempo e de quem e. '
                             'Todo card abre a lista (clique no numero).',
                'icone': 'bi-list-check',
                'setor': 'comercial',
                'compartilhado': True,
                'ordem': 1,
            },
        )
        self.stdout.write(self.style.SUCCESS(
            f"dashboard #{dash.pk} {'criado' if criado else 'ja existia'}: {dash.nome}"
        ))

        for ordem, (titulo, desc, fonte, viz, metrica, agrup, filtros, layout, extra) in enumerate(WIDGETS):
            if dry:
                self.stdout.write(f'  [DRY] {viz:<7} {titulo}')
                continue
            w, novo = Widget.objects.update_or_create(
                dashboard=dash, titulo=titulo,
                defaults={
                    'descricao': desc,
                    'data_source': fonte,
                    'visualizacao': viz,
                    'metrica': metrica,
                    'agrupamento': agrup,
                    'filtros': filtros,
                    'layout': layout,
                    'config_extra': extra,
                    'ordem': ordem,
                },
            )
            self.stdout.write(f"  {'+' if novo else '~'} #{w.pk} {viz:<7} {titulo}")

        if dry:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING('\nDRY-RUN: nada gravado.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nPainel Operacional pronto: /dashboards/{dash.pk}/'
            ))
