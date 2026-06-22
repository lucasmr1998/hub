"""
Roda UM nó de automação isolado e imprime o NodeResult.

Permite validar um bloco sozinho, sem editor/persistência/runtime:

    python manage.py testar_no --tipo http_request --tenant alpha \\
        --config '{"metodo":"GET","url":"https://httpbin.org/get"}' \\
        --contexto '{"variaveis":{"x":"Lucas"}}' \\
        --settings=gerenciador_vendas.settings_local

O nó é responsável por mascarar secrets no próprio output; este command só
imprime o que o nó devolve.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.automacao.nodes import Contexto, tipo_por_slug, REGISTRY


class _TenantStub:
    """Tenant leve pra teste isolado sem DB (nós que não tocam ORM).

    Nós que tocam o ORM exigem `--tenant <slug>` real — o command avisa.
    """
    pk = None
    slug = '_stub'
    nome = 'stub'

    def __str__(self):
        return 'stub'


class Command(BaseCommand):
    help = 'Executa um nó de automação isolado (config + contexto) e imprime o NodeResult.'

    def add_arguments(self, parser):
        parser.add_argument('--tipo', required=True, help='slug do nó (ex: http_request)')
        parser.add_argument('--config', default='{}', help='JSON da config do nó')
        parser.add_argument('--entrada', default='{}', help='JSON da entrada (output do nó anterior)')
        parser.add_argument('--contexto', default='{}',
                            help='JSON: {"variaveis": {...}, "nodes": {...}}')
        parser.add_argument('--tenant', help='slug do tenant (obrigatório p/ nós que tocam ORM)')

    def handle(self, *args, **opts):
        no = tipo_por_slug(opts['tipo'])
        if no is None:
            disponiveis = ', '.join(sorted(REGISTRY)) or '(nenhum)'
            raise CommandError(f"Nó '{opts['tipo']}' não registrado. Disponíveis: {disponiveis}")

        config = self._json(opts['config'], '--config')
        entrada = self._json(opts['entrada'], '--entrada')
        ctx_raw = self._json(opts['contexto'], '--contexto')

        tenant = self._resolver_tenant(opts.get('tenant'))

        contexto = Contexto(
            tenant=tenant,
            variaveis=ctx_raw.get('variaveis'),
            nodes=ctx_raw.get('nodes'),
        )

        erros = no.validar_config(config)
        if erros:
            self.stdout.write(self.style.ERROR('Config inválida:'))
            for e in erros:
                self.stdout.write(f'  - {e}')
            return

        resultado = no.executar(config, entrada, contexto)
        # Mimetiza o runtime: registra output + aplica promote, pra mostrar a ponte.
        contexto.aplicar_resultado(opts['tipo'], resultado)
        self._imprimir(opts['tipo'], resultado, contexto)

    # -- helpers -------------------------------------------------------------

    def _json(self, raw, flag):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandError(f'{flag} não é JSON válido: {exc}')

    def _resolver_tenant(self, slug):
        if not slug:
            self.stdout.write(self.style.WARNING(
                'Sem --tenant: usando stub (ok p/ nós que não tocam ORM).'))
            return _TenantStub()
        from apps.sistema.models import Tenant
        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant '{slug}' não encontrado.")
        return tenant

    def _imprimir(self, tipo, resultado, contexto):
        estilo = self.style.SUCCESS if resultado.status == 'ok' else self.style.ERROR
        self.stdout.write(estilo(f'[{tipo}] status={resultado.status} branch={resultado.branch}'))
        if resultado.erro:
            self.stdout.write(self.style.ERROR(f'erro: {resultado.erro}'))
        self.stdout.write('output:')
        self.stdout.write(json.dumps(resultado.output, ensure_ascii=False, indent=2, default=str))
        self.stdout.write('variaveis (após promote):')
        self.stdout.write(json.dumps(contexto.variaveis, ensure_ascii=False, indent=2, default=str))
