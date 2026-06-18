"""
Seed das 2 regras de automacao 'sincronizar_prospecto_hubsoft' pra um tenant.

Regra 1: gatilho `lead_criado` -> sincronizar_prospecto_hubsoft (cria rascunho)
Regra 2: gatilho `lead_status_pendente` -> sincronizar_prospecto_hubsoft (atualiza)

Idempotente: nao duplica se ja existir uma regra com o mesmo nome no tenant.

Uso:
    python manage.py seed_regra_prospecto_hubsoft --tenant nuvyon
    python manage.py seed_regra_prospecto_hubsoft --tenant nuvyon --desativar
"""
from django.core.management.base import BaseCommand

from apps.marketing.automacoes.models import RegraAutomacao, AcaoRegra
from apps.sistema.models import Tenant


NOME_REGRA_RASCUNHO = 'HubSoft - Criar rascunho ao receber lead'
NOME_REGRA_UPDATE = 'HubSoft - Atualizar prospecto quando pendente'


class Command(BaseCommand):
    help = 'Cria as 2 regras de automacao pra sincronizar prospecto HubSoft.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, required=True,
            help='Slug do tenant (obrigatorio).')
        parser.add_argument('--desativar', action='store_true',
            help='Desativa as regras em vez de criar/ativar.')

    def handle(self, *args, **opts):
        try:
            tenant = Tenant.objects.get(slug=opts['tenant'], ativo=True)
        except Tenant.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Tenant {opts["tenant"]!r} nao encontrado'))
            return

        if opts['desativar']:
            self._desativar(tenant)
            return

        self._criar_ou_atualizar(tenant)

    def _criar_ou_atualizar(self, tenant):
        # Regra 1 - lead_criado
        regra1, created1 = RegraAutomacao.objects.get_or_create(
            tenant=tenant,
            nome=NOME_REGRA_RASCUNHO,
            defaults={
                'descricao': (
                    'Quando um lead novo entra no Hubtrix, cria um prospecto '
                    'rascunho no HubSoft com nome + telefone reais e '
                    'placeholders nos demais campos. Mantem id_hubsoft no Lead '
                    'pra o update posterior. Multi-tenant via TenantMixin.'
                ),
                'evento': 'lead_criado',
                'ativa': True,
                'modo_fluxo': False,
                'cooldown_horas': 1,
                'max_execucoes_por_lead': 1,
                'periodo_limite_horas': 24,
            },
        )
        if not created1:
            regra1.evento = 'lead_criado'
            regra1.ativa = True
            regra1.cooldown_horas = max(regra1.cooldown_horas, 1)
            regra1.max_execucoes_por_lead = max(regra1.max_execucoes_por_lead, 1)
            regra1.save()
        AcaoRegra.objects.get_or_create(
            tenant=tenant,
            regra=regra1,
            tipo='sincronizar_prospecto_hubsoft',
            defaults={'configuracao': '', 'ordem': 0},
        )
        self.stdout.write(self.style.SUCCESS(
            f'[{tenant.slug}] Regra 1 {"criada" if created1 else "atualizada"}: {regra1.nome}'
        ))

        # Regra 2 - lead_status_pendente
        regra2, created2 = RegraAutomacao.objects.get_or_create(
            tenant=tenant,
            nome=NOME_REGRA_UPDATE,
            defaults={
                'descricao': (
                    'Quando o lead atinge status pendente (todos os dados reais '
                    'coletados), atualiza o prospecto HubSoft existente via PUT '
                    '/prospecto/{id}. Sem id_hubsoft, faz create no lugar.'
                ),
                'evento': 'lead_status_pendente',
                'ativa': True,
                'modo_fluxo': False,
                'cooldown_horas': 1,
                'max_execucoes_por_lead': 3,
                'periodo_limite_horas': 24,
            },
        )
        if not created2:
            regra2.evento = 'lead_status_pendente'
            regra2.ativa = True
            regra2.save()
        AcaoRegra.objects.get_or_create(
            tenant=tenant,
            regra=regra2,
            tipo='sincronizar_prospecto_hubsoft',
            defaults={'configuracao': '', 'ordem': 0},
        )
        self.stdout.write(self.style.SUCCESS(
            f'[{tenant.slug}] Regra 2 {"criada" if created2 else "atualizada"}: {regra2.nome}'
        ))

        self.stdout.write(self.style.WARNING(
            '\nIMPORTANTE: regras criadas como ATIVAS. Pra desativar (rollback): '
            f'python manage.py seed_regra_prospecto_hubsoft --tenant {tenant.slug} --desativar'
        ))

    def _desativar(self, tenant):
        n = RegraAutomacao.objects.filter(
            tenant=tenant,
            nome__in=[NOME_REGRA_RASCUNHO, NOME_REGRA_UPDATE],
        ).update(ativa=False)
        self.stdout.write(self.style.SUCCESS(
            f'[{tenant.slug}] {n} regra(s) HubSoft desativadas. Fluxo antigo segue ativo.'
        ))
