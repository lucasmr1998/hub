"""Importa cidades/bairros com viabilidade a partir da base real de clientes
no HubSoft (banco espelho, HUBSOFT_DB_*), restrito aos grupos de serviço
'Varejo' (id 29) e 'Varejo - Regional 5' (id 132).

Só considera cidades com mais de N clientes (--min-cidade, default 50) nesses
grupos, e dentro delas só bairros com mais de M clientes (--min-bairro,
default 2) após normalizar variações de grafia (maiúsculas, acentos, espaços
duplicados, pontuação) — o texto do bairro no HubSoft é livre e tem bastante
ruído de digitação.

Cidades fora de MA/PI são ignoradas e reportadas: a operação atende só essas
duas UFs, então um cliente fora delas quase sempre é erro de cadastro no
HubSoft (UF errada selecionada), não cobertura real.

Alguns nomes de cidade no HubSoft usam o nome oficial completo (ex: "Ipiranga
do Piauí", "São José do Piauí") enquanto o cadastro de viabilidade já tinha a
forma curta ("Ipiranga", "São José") — ALIAS_CIDADE mapeia esses casos
conhecidos para o registro existente em vez de criar cidade duplicada.

Uso:
    python manage.py importar_bairros_hubsoft --dry-run
    python manage.py importar_bairros_hubsoft
"""
import os
import re
import unicodedata
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from vendas_web.models import CidadeViabilidade, BairroViabilidade

GRUPOS_SERVICO = (29, 132)  # Varejo, Varejo - Regional 5
UFS_ATENDIDAS = ('MA', 'PI')

# (nome retornado pelo HubSoft, UF) -> (cidade, UF) já cadastrada na viabilidade
ALIAS_CIDADE = {
    ('Ipiranga do Piauí', 'PI'): ('Ipiranga', 'PI'),
    ('São José do Piauí', 'PI'): ('São José', 'PI'),
}


def _norm_key(texto):
    texto = (texto or '').strip().lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^a-z0-9]+', ' ', texto).strip()
    return re.sub(r'\s+', ' ', texto)


def _conn_hubsoft():
    import psycopg2
    return psycopg2.connect(
        host=os.environ['HUBSOFT_DB_HOST'], port=os.environ['HUBSOFT_DB_PORT'],
        dbname=os.environ['HUBSOFT_DB_NAME'], user=os.environ['HUBSOFT_DB_USER'],
        password=os.environ['HUBSOFT_DB_PASSWORD'], connect_timeout=10,
    )


class Command(BaseCommand):
    help = 'Importa cidades/bairros com viabilidade a partir dos clientes reais no HubSoft'

    def add_arguments(self, parser):
        parser.add_argument('--min-cidade', type=int, default=50,
                             help='Mínimo de clientes na cidade para considerá-la (default 50)')
        parser.add_argument('--min-bairro', type=int, default=2,
                             help='Mínimo de clientes no bairro (após normalizar) para incluí-lo (default 2)')
        parser.add_argument('--dry-run', action='store_true',
                             help='Só mostra o que seria feito, sem gravar')

    def handle(self, *args, **opts):
        min_cidade = opts['min_cidade']
        min_bairro = opts['min_bairro']
        dry_run = opts['dry_run']

        conn = _conn_hubsoft()
        cur = conn.cursor()
        cur.execute('''
            SELECT ci.nome, est.sigla, en.bairro, COUNT(DISTINCT cs.id_cliente_servico) n
            FROM cliente_servico cs
            JOIN cliente_servico_grupo csg ON csg.id_cliente_servico = cs.id_cliente_servico
            JOIN grupo_cliente_servico g ON g.id = csg.id_grupo_cliente_servico
            JOIN cliente_servico_endereco cse ON cse.id_cliente_servico = cs.id_cliente_servico
                AND cse.tipo = 'instalacao'
            JOIN endereco_numero en ON en.id_endereco_numero = cse.id_endereco_numero
            LEFT JOIN cidade ci ON ci.id_cidade = en.id_cidade
            LEFT JOIN estado est ON est.id_estado = ci.id_estado
            WHERE g.id = ANY(%s)
            GROUP BY ci.nome, est.sigla, en.bairro
        ''', [list(GRUPOS_SERVICO)])
        rows = cur.fetchall()
        conn.close()

        # 1. total de clientes por cidade/UF
        total_cidade = Counter()
        for cidade, uf, _bairro, n in rows:
            total_cidade[(cidade, uf)] += n

        qualificadas = {k for k, v in total_cidade.items() if v > min_cidade}
        fora_da_area = sorted(
            (k, v) for k, v in total_cidade.items() if v > min_cidade and k[1] not in UFS_ATENDIDAS
        )
        qualificadas = {k for k in qualificadas if k[1] in UFS_ATENDIDAS}

        self.stdout.write(f'Cidades com mais de {min_cidade} clientes (grupos Varejo/Regional 5): '
                           f'{len(qualificadas)} dentro de MA/PI')
        if fora_da_area:
            self.stdout.write(self.style.WARNING(
                f'  Ignoradas por estarem fora de MA/PI (provável erro de cadastro no HubSoft): '
                + ', '.join(f'{c}/{u} ({n} clientes)' for (c, u), n in fora_da_area)
            ))

        # 2. agrega bairros por cidade qualificada, normalizando variações de grafia
        agg = defaultdict(lambda: Counter())
        for cidade, uf, bairro, n in rows:
            if (cidade, uf) not in qualificadas:
                continue
            k = _norm_key(bairro)
            if not k:
                continue
            agg[(cidade, uf, k)][bairro.strip()] += n

        existentes = {(c.cidade.strip().lower(), c.estado): c for c in CidadeViabilidade.objects.all()}

        cidades_novas = []
        cidades_resolvidas = {}  # (cidade_hubsoft, uf) -> CidadeViabilidade
        for (cidade, uf) in sorted(qualificadas):
            alvo_nome, alvo_uf = ALIAS_CIDADE.get((cidade, uf), (cidade, uf))
            obj = existentes.get((alvo_nome.strip().lower(), alvo_uf))
            if obj:
                cidades_resolvidas[(cidade, uf)] = obj
            else:
                cidades_novas.append((cidade, uf))

        if cidades_novas:
            self.stdout.write(f'Cidades novas a criar ({len(cidades_novas)}): '
                               + ', '.join(f'{c}/{u}' for c, u in cidades_novas))

        # 3. monta lista final de bairros (canonizados + filtrados por min_bairro)
        bairros_a_gravar = []  # (cidade_hubsoft, uf, nome_canonico, total_clientes)
        ignorados_ruido = 0
        for (cidade, uf, _k), variantes in agg.items():
            total = sum(variantes.values())
            if total < min_bairro:
                ignorados_ruido += 1
                continue
            nome_canonico = variantes.most_common(1)[0][0]
            bairros_a_gravar.append((cidade, uf, nome_canonico, total))

        self.stdout.write(f'Bairros a gravar: {len(bairros_a_gravar)} '
                           f'(ignorados por ruído/typo isolado, <{min_bairro} cliente(s): {ignorados_ruido})')

        if dry_run:
            self.stdout.write(self.style.WARNING('--dry-run: nada foi gravado.'))
            return

        criadas = 0
        atualizadas_bairro = 0
        with transaction.atomic():
            for cidade, uf in cidades_novas:
                obj, created = CidadeViabilidade.objects.get_or_create(
                    cidade=cidade, estado=uf,
                    defaults={
                        'ativo': True,
                        'observacao': 'Cidade identificada via clientes ativos no HubSoft '
                                      '(grupos Varejo/Varejo Regional 5) — regional a definir.',
                    },
                )
                cidades_resolvidas[(cidade, uf)] = obj
                if created:
                    criadas += 1

            # resolve observação do São José agora que a ambiguidade foi confirmada
            sao_jose = existentes.get(('são josé', 'PI'))
            if sao_jose and sao_jose.observacao and 'confirmar' in sao_jose.observacao.lower():
                sao_jose.observacao = 'Confirmado via HubSoft: município é São José do Piauí.'
                sao_jose.save(update_fields=['observacao'])

            for cidade, uf, nome_bairro, _total in bairros_a_gravar:
                cidade_obj = cidades_resolvidas[(cidade, uf)]
                _bairro_obj, created = BairroViabilidade.objects.get_or_create(
                    cidade=cidade_obj, nome=nome_bairro,
                    defaults={'ativo': True},
                )
                if created:
                    atualizadas_bairro += 1

        self.stdout.write(self.style.SUCCESS(
            f'OK — {criadas} cidade(s) nova(s), {atualizadas_bairro} bairro(s) novo(s) gravado(s).'
        ))
