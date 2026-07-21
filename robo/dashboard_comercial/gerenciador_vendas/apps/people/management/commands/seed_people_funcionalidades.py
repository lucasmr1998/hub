"""
Cria as funcionalidades do People e faz back-fill nos perfis que ja existem.

O back-fill e a parte que costuma ser esquecida. O comando canonico
(`seed_funcionalidades`) so cria as linhas de Funcionalidade; quem ja tinha um
perfil Admin montado antes do modulo existir continua sem nenhuma delas, e o
resultado e um modulo que ninguem enxerga apesar de estar contratado. Foi o que
aconteceu no Workspace, e por isso ele criou um comando proprio. Este segue o
mesmo caminho.

Idempotente. Roda quantas vezes quiser.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.sistema.models import Funcionalidade, PerfilPermissao


MODULO = 'people'

FUNCIONALIDADES = [
    {
        'codigo': 'people.ver',
        'nome': 'Ver People',
        'descricao': 'Acessar o modulo People (board, fichas, unidades)',
        'ordem': 10,
    },
    {
        'codigo': 'people.gerir_unidades',
        'nome': 'Gerir unidades',
        'descricao': 'Criar, editar e desativar lojas ou filiais',
        'ordem': 20,
    },
    {
        'codigo': 'people.criar_colaborador',
        'nome': 'Cadastrar colaborador',
        'descricao': 'Cadastrar pessoa e resolver duplicata apontada pelo dedup',
        'ordem': 30,
    },
    {
        'codigo': 'people.mover_colaborador',
        'nome': 'Mover de fase',
        'descricao': 'Mudar a fase do colaborador no ciclo de vida (admissao, '
                     'experiencia, efetivacao, desligamento)',
        'ordem': 40,
    },
    {
        'codigo': 'people.gerir_links',
        'nome': 'Gerir links de cadastro',
        'descricao': 'Gerar, rotacionar e desativar o link publico de auto cadastro',
        'ordem': 50,
    },
    {
        'codigo': 'people.gerir_vagas',
        'nome': 'Gerir vagas',
        'descricao': 'Abrir, editar, publicar, pausar e encerrar vaga de '
                     'recrutamento, e definir os requisitos dela',
        'ordem': 60,
    },
    {
        'codigo': 'people.avaliar',
        'nome': 'Avaliar candidato',
        'descricao': 'Registrar anotacoes nas etapas do processo seletivo, sem '
                     'poder mover, abrir vaga nem admitir',
        'ordem': 70,
    },
]

# Quem ganha o que no back-fill. Perfil fora deste mapa nao e tocado: dar
# permissao a quem ninguem pediu e pior que faltar permissao, porque ninguem
# revisa o que ja veio ligado.
PERFIL_DEFAULTS = {
    'Admin': [f['codigo'] for f in FUNCIONALIDADES],
    # Gestor abre vaga: na rede de franquia e o gerente de loja quem sabe que
    # esta faltando gente. Quem NAO entra e o Supervisor, que so acompanha.
    'Gestor': ['people.ver', 'people.criar_colaborador',
               'people.mover_colaborador', 'people.gerir_vagas',
               'people.avaliar'],
    'Supervisor Comercial': ['people.ver'],
}

# Perfil de quem SO avalia: o supervisor tecnico que entrevista o candidato e
# registra a impressao, sem poder mover no pipeline, abrir vaga nem admitir.
#
# Existe com USUARIO, e nao como link publico sem login como a origem faz. Tres
# motivos: (a) a avaliacao decide contratacao, e "quem avaliou" precisa ser
# identidade e nao nome digitado; (b) link sem login exibindo dados e curriculo
# do candidato e superficie de vazamento LGPD; (c) na origem o avaliador e o
# gerente de loja de shopping, que roda toda hora, enquanto num provedor o
# supervisor tecnico e funcionario fixo com email.
PERFIL_AVALIADOR = {
    'nome': 'Avaliador de candidatos',
    'funcionalidades': ['people.ver', 'people.avaliar'],
}


class Command(BaseCommand):
    help = 'Cria as funcionalidades do People e aplica nos perfis existentes.'

    def add_arguments(self, parser):
        parser.add_argument('--sem-backfill', action='store_true',
                            help='So cria as funcionalidades, sem tocar nos perfis.')

    @transaction.atomic
    def handle(self, *args, **opcoes):
        criadas = self._criar_funcionalidades()
        if opcoes['sem_backfill']:
            self.stdout.write('Back-fill pulado por --sem-backfill.')
        else:
            self._backfill_perfis()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{criadas} funcionalidades novas, {len(FUNCIONALIDADES)} no total.'))

    def _criar_funcionalidades(self):
        criadas = 0
        for dados in FUNCIONALIDADES:
            _, nova = Funcionalidade.objects.update_or_create(
                codigo=dados['codigo'],
                defaults={
                    'modulo': MODULO,
                    'nome': dados['nome'],
                    'descricao': dados['descricao'],
                    'ordem': dados['ordem'],
                },
            )
            criadas += int(nova)
            self.stdout.write(f'  {"criada" if nova else "atualizada"}: {dados["codigo"]}')
        return criadas

    def _backfill_perfis(self):
        """Liga as funcionalidades nos perfis que ja existem, de todos os tenants."""
        self.stdout.write('')
        self.stdout.write('Back-fill nos perfis existentes:')

        por_codigo = {
            f.codigo: f
            for f in Funcionalidade.objects.filter(modulo=MODULO)
        }

        total = 0
        for nome_perfil, codigos in PERFIL_DEFAULTS.items():
            funcs = [por_codigo[c] for c in codigos if c in por_codigo]
            perfis = PerfilPermissao.objects.filter(nome=nome_perfil)
            for perfil in perfis:
                perfil.funcionalidades.add(*funcs)
                total += 1
            if perfis:
                self.stdout.write(
                    f'  {nome_perfil}: {len(funcs)} funcionalidades em {len(perfis)} perfis')

        if not total:
            self.stdout.write('  nenhum perfil encontrado pelos nomes padrao')
