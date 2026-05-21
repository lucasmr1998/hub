"""
Gera um token de API inbound para um tenant.

Cria uma IntegracaoAPI com `api_token` unico — usado por sistemas
externos (Matrix, N8N, etc) pra autenticar chamadas AS APIs do Hubtrix.
O decorator `api_token_required` identifica o tenant por esse token.

Uso:
    python manage.py gerar_token_api \
        --tenant nuvyon \
        --nome "Matrix Nuvyon" \
        --tipo outro

Se ja existir IntegracaoAPI com o mesmo nome no tenant, o comando
mostra o token existente em vez de criar outra (idempotente por nome).
Use --regenerar pra forcar um token novo na integracao existente.
"""
import secrets

from django.core.management.base import BaseCommand, CommandError

from apps.sistema.models import Tenant
from apps.integracoes.models import IntegracaoAPI


class Command(BaseCommand):
    help = 'Gera token de API inbound para um tenant (Matrix, N8N, etc).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant')
        parser.add_argument('--nome', required=True, help='Nome da integracao (ex: "Matrix Nuvyon")')
        parser.add_argument('--tipo', default='outro',
                            choices=[c[0] for c in IntegracaoAPI.TIPO_CHOICES],
                            help='Tipo da integracao (default: outro)')
        parser.add_argument('--regenerar', action='store_true',
                            help='Se a integracao ja existir, gera um token novo (revoga o antigo).')

    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(slug=options['tenant'])
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant "{options["tenant"]}" nao encontrado.')

        nome = options['nome']
        existente = IntegracaoAPI.all_tenants.filter(tenant=tenant, nome=nome).first()

        if existente and not options['regenerar']:
            self.stdout.write(self.style.WARNING(
                f'Integracao "{nome}" ja existe no tenant {tenant.slug}.'
            ))
            self._imprimir(existente)
            self.stdout.write(self.style.WARNING(
                'Use --regenerar pra gerar um token novo (revoga o atual).'
            ))
            return

        token = secrets.token_urlsafe(32)

        if existente:
            existente.api_token = token
            existente.ativa = True
            existente.save(update_fields=['api_token', 'ativa', 'data_atualizacao'])
            self.stdout.write(self.style.SUCCESS(f'Token regenerado para "{nome}".'))
            self._imprimir(existente)
            return

        integ = IntegracaoAPI.objects.create(
            tenant=tenant,
            nome=nome,
            tipo=options['tipo'],
            api_token=token,
            ativa=True,
            # Campos OAuth nao usados em integracao inbound — ficam vazios.
            client_id='',
            client_secret='',
            username='',
            password='',
            base_url='',
        )
        self.stdout.write(self.style.SUCCESS(f'Integracao "{nome}" criada no tenant {tenant.slug}.'))
        self._imprimir(integ)

    def _imprimir(self, integ):
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('=== Integracao de API inbound ==='))
        self.stdout.write(f'  Tenant:   {integ.tenant.slug} (id {integ.tenant_id})')
        self.stdout.write(f'  Nome:     {integ.nome}')
        self.stdout.write(f'  Tipo:     {integ.tipo}')
        self.stdout.write(f'  Integ id: {integ.pk}')
        self.stdout.write(f'  Ativa:    {integ.ativa}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'  API TOKEN: {integ.api_token}'))
        self.stdout.write('')
        self.stdout.write('  Uso pelo sistema externo (Matrix/N8N):')
        self.stdout.write(f'    Authorization: Bearer {integ.api_token}')
