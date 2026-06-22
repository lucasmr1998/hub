"""
Executa um fluxo (grafo de nós em JSON) e imprime o trace, sem persistência.

    python manage.py testar_fluxo --fluxo @meu_fluxo.json --tenant alpha \\
        --settings=gerenciador_vendas.settings_local

`--fluxo` aceita JSON inline ou `@caminho.json`.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.automacao.nodes import Contexto
from apps.automacao.runtime import executar_fluxo, validar_fluxo


class _TenantStub:
    pk = None
    slug = '_stub'
    nome = 'stub'

    def __str__(self):
        return 'stub'


class Command(BaseCommand):
    help = 'Executa um fluxo (grafo JSON) e imprime o trace. Sem persistência.'

    def add_arguments(self, parser):
        parser.add_argument('--fluxo', required=True, help='JSON do fluxo ou @caminho.json')
        parser.add_argument('--contexto', default='{}',
                            help='JSON: {"variaveis": {...}, "nodes": {...}}')
        parser.add_argument('--tenant', help='slug do tenant (p/ nós que tocam ORM)')

    def handle(self, *args, **opts):
        fluxo = self._carregar_fluxo(opts['fluxo'])
        erros = validar_fluxo(fluxo)
        if erros:
            raise CommandError('Fluxo inválido: ' + '; '.join(erros))

        ctx_raw = self._json(opts['contexto'], '--contexto')
        contexto = Contexto(
            tenant=self._tenant(opts.get('tenant')),
            variaveis=ctx_raw.get('variaveis'),
            nodes=ctx_raw.get('nodes'),
        )

        resultado = executar_fluxo(fluxo, contexto)
        self._imprimir(resultado, contexto)

    # -- helpers -------------------------------------------------------------

    def _carregar_fluxo(self, arg):
        if arg.startswith('@'):
            try:
                with open(arg[1:], encoding='utf-8') as fh:
                    return json.load(fh)
            except OSError as exc:
                raise CommandError(f'Não consegui ler o fluxo: {exc}')
            except json.JSONDecodeError as exc:
                raise CommandError(f'Arquivo de fluxo não é JSON válido: {exc}')
        return self._json(arg, '--fluxo')

    def _json(self, raw, flag):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandError(f'{flag} não é JSON válido: {exc}')

    def _tenant(self, slug):
        if not slug:
            self.stdout.write(self.style.WARNING(
                'Sem --tenant: usando stub (ok p/ nós que não tocam ORM).'))
            return _TenantStub()
        from apps.sistema.models import Tenant
        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant '{slug}' não encontrado.")
        return tenant

    def _imprimir(self, resultado, contexto):
        estilo = self.style.SUCCESS if resultado.status == 'completado' else (
            self.style.WARNING if resultado.status == 'aguardando' else self.style.ERROR)
        self.stdout.write(estilo(f'fluxo: {resultado.status}'))
        if resultado.erro:
            self.stdout.write(self.style.ERROR(f'erro: {resultado.erro}'))
        self.stdout.write('trace:')
        for i, p in enumerate(resultado.passos, 1):
            marca = '' if not p.erro else f'  ({p.erro})'
            self.stdout.write(f'  {i}. {p.handle} [{p.tipo}] -> {p.status}/{p.branch}{marca}')
        if resultado.aguardando:
            self.stdout.write(f"aguardando -> retoma em: {resultado.aguardando['retomar_em']}")
        self.stdout.write('variaveis:')
        self.stdout.write(json.dumps(contexto.variaveis, ensure_ascii=False, indent=2, default=str))
