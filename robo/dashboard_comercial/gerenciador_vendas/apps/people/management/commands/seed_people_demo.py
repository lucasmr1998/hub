"""
Popula People com dados ficticios pra inspecao em dev.

Usa `registrar_colaborador` e `mover_situacao` de verdade, entao o seed tambem
serve de demonstracao: as duplicatas que ele tenta criar de proposito sao
recusadas pelo dedup, e o relatorio no fim mostra o que aconteceu em cada caso.

DEV ONLY. Recusa rodar com DEBUG desligado, salvo --forcar.
Nomes e documentos sao ficticios: nada aqui pode virar PII de gente real.
"""
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.people import estados
from apps.people.models import Colaborador, Unidade
from apps.people.services import mover_situacao, registrar_colaborador
from apps.sistema.models import Tenant


def cpf_ficticio(base9):
    """Monta um CPF com digito verificador correto a partir de 9 digitos."""
    digitos = [int(c) for c in str(base9).zfill(9)]
    for tamanho in (9, 10):
        soma = sum(d * (tamanho + 1 - i) for i, d in enumerate(digitos[:tamanho]))
        resto = (soma * 10) % 11
        digitos.append(0 if resto == 10 else resto)
    return ''.join(str(d) for d in digitos)


UNIDADES = [
    {'nome': 'Unidade Centro', 'codigo': 'demo-centro', 'cidade': 'Teresina', 'estado': 'PI'},
    {'nome': 'Unidade Shopping', 'codigo': 'demo-shopping', 'cidade': 'Teresina', 'estado': 'PI'},
]

# (nome, base do cpf, cargo, fase alvo, dias desde a admissao)
PESSOAS = [
    ('Ana Beatriz Moreira',  111111111, 'Atendente',       estados.SITUACAO_CADASTRO,        None),
    ('Bruno Carvalho Lima',  222222222, 'Atendente',       estados.SITUACAO_EM_ADMISSAO,     3),
    ('Carla Dias Nogueira',  333333333, 'Auxiliar',        estados.SITUACAO_EM_EXPERIENCIA,  20),
    ('Diego Ferreira Rocha', 444444444, 'Auxiliar',        estados.SITUACAO_EM_EXPERIENCIA,  50),
    ('Elisa Gomes Tavares',  555555555, 'Subgerente',      estados.SITUACAO_EFETIVADO,       200),
    ('Fabio Henrique Alves', 666666666, 'Gerente',         estados.SITUACAO_EFETIVADO,       400),
    ('Gabriela Inacio Melo', 777777777, 'Atendente',       estados.SITUACAO_EM_DESLIGAMENTO, 150),
    ('Heitor Jorge Pacheco', 888888888, 'Atendente',       estados.SITUACAO_DESLIGADO,       300),
]


class Command(BaseCommand):
    help = 'Popula People com dados ficticios pra inspecao em dev (DEV ONLY).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', dest='slug', default='aurora-hq',
                            help='Slug do tenant. Default: aurora-hq')
        parser.add_argument('--limpar', action='store_true',
                            help='Apaga o que o seed criou antes de recriar.')
        parser.add_argument('--forcar', action='store_true',
                            help='Roda mesmo com DEBUG desligado. Use com cuidado.')

    def handle(self, *args, **opcoes):
        if not settings.DEBUG and not opcoes['forcar']:
            raise CommandError(
                'DEBUG esta desligado. Este comando cria dado ficticio e nao deve '
                'rodar em producao. Use --forcar se voce tem certeza.'
            )

        tenant = Tenant.all_tenants.filter(slug=opcoes['slug']).first() \
            if hasattr(Tenant, 'all_tenants') else Tenant.objects.filter(slug=opcoes['slug']).first()
        if tenant is None:
            raise CommandError(f'Tenant "{opcoes["slug"]}" nao existe.')

        if opcoes['limpar']:
            self._limpar(tenant)

        unidades = self._criar_unidades(tenant)
        cargos = self._criar_cargos(tenant)
        self._criar_pessoas(tenant, unidades, cargos)
        self._demonstrar_dedup(tenant, unidades[0])
        self._resumo(tenant)

    def _limpar(self, tenant):
        codigos = [u['codigo'] for u in UNIDADES]
        alvo = Colaborador.all_tenants.filter(
            tenant=tenant, unidade__codigo__in=codigos)
        total = alvo.count()
        for colaborador in alvo:
            colaborador._apagar_de_verdade = True
            colaborador.delete()
        Unidade.all_tenants.filter(tenant=tenant, codigo__in=codigos).delete()
        self.stdout.write(f'Limpeza: {total} colaboradores e as unidades de demo removidos.')

    def _criar_unidades(self, tenant):
        criadas = []
        for dados in UNIDADES:
            unidade, nova = Unidade.all_tenants.get_or_create(
                tenant=tenant, codigo=dados['codigo'],
                defaults={k: v for k, v in dados.items() if k != 'codigo'},
            )
            criadas.append(unidade)
            self.stdout.write(
                f'{"criada" if nova else "ja existia"}: unidade {unidade.nome}')
        return criadas

    def _criar_cargos(self, tenant):
        """Cargo e entidade, nao texto. Ver GAPS-VISIO.md, gap 2."""
        from apps.people.models import Cargo

        cargos = {}
        for ordem, nome in enumerate(sorted({p[2] for p in PESSOAS})):
            cargo, _ = Cargo.all_tenants.get_or_create(
                tenant=tenant, nome=nome, defaults={'ordem': ordem * 10})
            cargos[nome] = cargo
        self.stdout.write(f'cargos: {", ".join(cargos)}')
        return cargos

    def _criar_pessoas(self, tenant, unidades, cargos):
        self.stdout.write('')
        self.stdout.write('Colaboradores:')
        hoje = date.today()

        for indice, (nome, base, nome_cargo, fase, dias) in enumerate(PESSOAS):
            unidade = unidades[indice % len(unidades)]
            cargo = cargos[nome_cargo]
            admissao = hoje - timedelta(days=dias) if dias else None

            resultado = registrar_colaborador(
                tenant, unidade,
                {
                    'nome_completo': nome,
                    'cpf': cpf_ficticio(base),
                    'telefone': f'869{base % 100000000:08d}',
                    'email': f'{nome.split()[0].lower()}@exemplo.invalido',
                    'cargo': cargo,
                    'regime_contratacao': 'clt',
                    'data_admissao': admissao,
                },
                origem='rh',
            )
            if not resultado.ok:
                self.stdout.write(f'  conflito em {nome}, pulando')
                continue

            colaborador = resultado.colaborador
            if resultado.acao == 'criado':
                self._levar_ate(colaborador, fase, admissao, hoje)

            self.stdout.write(
                f'  {resultado.acao:14} {nome:24} {colaborador.situacao}')

    def _levar_ate(self, colaborador, fase, admissao, hoje):
        """Caminha pela maquina de estados ate a fase alvo, uma transicao por vez."""
        if fase == estados.SITUACAO_CADASTRO:
            return

        mover_situacao(colaborador, estados.SITUACAO_EM_ADMISSAO,
                       motivo='Documentacao recebida',
                       dados={'data_admissao': admissao})
        if fase == estados.SITUACAO_EM_ADMISSAO:
            return

        mover_situacao(colaborador, estados.SITUACAO_EM_EXPERIENCIA,
                       motivo='Checklist de admissao concluido')
        if fase == estados.SITUACAO_EM_EXPERIENCIA:
            return

        mover_situacao(colaborador, estados.SITUACAO_EFETIVADO,
                       motivo='Avaliacao de experiencia aprovada')
        if fase == estados.SITUACAO_EFETIVADO:
            return

        mover_situacao(colaborador, estados.SITUACAO_EM_DESLIGAMENTO,
                       motivo='Pedido de demissao',
                       dados={'motivo_desligamento': 'pedido'})
        if fase == estados.SITUACAO_EM_DESLIGAMENTO:
            return

        mover_situacao(colaborador, estados.SITUACAO_DESLIGADO,
                       motivo='Desligamento concluido',
                       dados={'data_desligamento': hoje - timedelta(days=5),
                              'motivo_desligamento': 'pedido'})

    def _demonstrar_dedup(self, tenant, unidade):
        """Tenta duplicar de proposito. O que aparece aqui e o dedup trabalhando."""
        self.stdout.write('')
        self.stdout.write('Dedup em acao (tentativas propositais):')

        mesma = registrar_colaborador(
            tenant, unidade,
            {'nome_completo': 'Ana B. Moreira', 'cpf': cpf_ficticio(111111111),
             'email': 'ana.nova@exemplo.invalido'},
            origem='link_publico',
        )
        self.stdout.write(
            f'  mesmo CPF pelo link publico  -> {mesma.acao} '
            f'(id {mesma.colaborador.pk if mesma.colaborador else "nenhum"})')

        telefone = registrar_colaborador(
            tenant, unidade,
            {'nome_completo': 'Pessoa Diferente', 'telefone': '86911111111'},
            origem='link_publico',
        )
        self.stdout.write(
            f'  telefone repetido            -> {telefone.acao} '
            f'({telefone.motivo_conflito or "sem conflito"})')

        readmitido = registrar_colaborador(
            tenant, unidade,
            {'nome_completo': 'Heitor Jorge Pacheco', 'cpf': cpf_ficticio(888888888)},
            origem='rh',
        )
        self.stdout.write(
            f'  desligado se recadastrando   -> {readmitido.acao} '
            f'(id {readmitido.colaborador.pk if readmitido.colaborador else "nenhum"})')

    def _resumo(self, tenant):
        from apps.people.consultas import contagem_por_situacao

        self.stdout.write('')
        self.stdout.write('Total por situacao:')
        for situacao, total in contagem_por_situacao(tenant=tenant).items():
            if total:
                self.stdout.write(f'  {estados.rotulo(situacao):18} {total}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            'Pronto. Veja em /admin/people/colaborador/ '
            '(o historico de cada um fica no fim da ficha).'))
