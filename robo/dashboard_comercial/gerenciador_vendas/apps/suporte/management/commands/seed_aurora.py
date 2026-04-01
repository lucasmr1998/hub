"""
Cria o tenant Aurora HQ com pipeline B2B, categorias de ticket e SLA.
Uso: python manage.py seed_aurora --settings=gerenciador_vendas.settings_local
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from apps.sistema.models import Tenant, PerfilUsuario, ConfiguracaoEmpresa
from apps.suporte.models import CategoriaTicket, SLAConfig


class Command(BaseCommand):
    help = "Cria o tenant Aurora HQ como primeiro cliente do sistema."

    def add_arguments(self, parser):
        parser.add_argument('--admin-user', default='aurora', help='Username do admin')
        parser.add_argument('--admin-email', default='admin@auroraisp.com.br', help='Email do admin')
        parser.add_argument('--admin-senha', default='aurora123', help='Senha do admin')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\nCriando Aurora HQ...\n'))

        # ── Tenant ──────────────────────────────────────────────────────
        tenant, created = Tenant.objects.get_or_create(
            slug='aurora-hq',
            defaults={
                'nome': 'Aurora HQ',
                'modulo_comercial': True,
                'modulo_marketing': True,
                'modulo_cs': True,
                'plano_comercial': 'pro',
                'plano_marketing': 'start',
                'plano_cs': 'start',
                'ativo': True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  Tenant Aurora HQ criado'))
        else:
            self.stdout.write('  Tenant Aurora HQ ja existe')

        # ── Config Empresa ──────────────────────────────────────────────
        ConfiguracaoEmpresa.all_tenants.get_or_create(
            tenant=tenant,
            defaults={'nome_empresa': 'Aurora HQ', 'ativo': True},
        )

        # ── Admin User ──────────────────────────────────────────────────
        username = options['admin_user']
        email = options['admin_email']
        senha = options['admin_senha']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'is_staff': True,
                'is_superuser': True,
                'first_name': 'Aurora',
                'last_name': 'Admin',
            },
        )
        if created:
            user.set_password(senha)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'  User {username} criado'))
        else:
            self.stdout.write(f'  User {username} ja existe')

        PerfilUsuario.objects.get_or_create(user=user, defaults={'tenant': tenant})

        # ── Pipeline B2B ────────────────────────────────────────────────
        try:
            from apps.comercial.crm.models import Pipeline, PipelineEstagio, ConfiguracaoCRM

            pipeline, _ = Pipeline.all_tenants.get_or_create(
                tenant=tenant, slug='vendas-b2b',
                defaults={
                    'nome': 'Vendas B2B (Provedores)',
                    'tipo': 'vendas',
                    'padrao': True,
                    'cor_hex': '#818cf8',
                    'icone_fa': 'fa-building',
                },
            )

            estagios = [
                (1, 'Lead Identificado', 'lead-identificado', 'novo', '#94a3b8', 10, False, False),
                (2, 'Contato Inicial', 'contato-inicial', 'qualificacao', '#3b82f6', 20, False, False),
                (3, 'Demo Agendada', 'demo-agendada', 'qualificacao', '#8b5cf6', 40, False, False),
                (4, 'Em Trial', 'em-trial', 'negociacao', '#f59e0b', 60, False, False),
                (5, 'Negociacao', 'negociacao-b2b', 'negociacao', '#f97316', 75, False, False),
                (6, 'Cliente Ativo', 'cliente-ativo', 'cliente', '#22c55e', 100, True, False),
                (7, 'Churn/Perdido', 'churn-perdido', 'perdido', '#ef4444', 0, False, True),
            ]

            estagio_inicial = None
            for ordem, nome, slug, tipo, cor, prob, ganho, perdido in estagios:
                est, _ = PipelineEstagio.all_tenants.get_or_create(
                    tenant=tenant, pipeline=pipeline, slug=slug,
                    defaults={
                        'nome': nome, 'tipo': tipo, 'ordem': ordem,
                        'cor_hex': cor, 'probabilidade_padrao': prob,
                        'is_final_ganho': ganho, 'is_final_perdido': perdido,
                    },
                )
                if ordem == 1:
                    estagio_inicial = est

            self.stdout.write(self.style.SUCCESS(f'  Pipeline B2B: {len(estagios)} estagios'))

            # Config CRM
            config, _ = ConfiguracaoCRM.all_tenants.get_or_create(
                tenant=tenant,
                defaults={
                    'criar_oportunidade_automatico': True,
                    'estagio_inicial_padrao': estagio_inicial,
                    'pipeline_padrao': pipeline,
                },
            )

        except (ImportError, Exception) as e:
            self.stdout.write(self.style.WARNING(f'  Pipeline B2B: pulado ({e})'))

        # ── Categorias de Ticket ────────────────────────────────────────
        categorias = [
            ('Bug', 'bug', 'fa-bug', 1),
            ('Duvida', 'duvida', 'fa-question-circle', 2),
            ('Solicitacao', 'solicitacao', 'fa-hand-paper', 3),
            ('Incidente', 'incidente', 'fa-exclamation-triangle', 4),
            ('Melhoria', 'melhoria', 'fa-lightbulb', 5),
        ]
        for nome, slug, icone, ordem in categorias:
            CategoriaTicket.all_tenants.get_or_create(
                tenant=tenant, slug=slug,
                defaults={'nome': nome, 'icone': icone, 'ordem': ordem},
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(categorias)} categorias de ticket'))

        # ── SLA Configs ─────────────────────────────────────────────────
        slas = [
            ('starter', 24, 72),
            ('start', 12, 48),
            ('pro', 4, 24),
        ]
        for tier, resposta, resolucao in slas:
            SLAConfig.all_tenants.get_or_create(
                tenant=tenant, plano_tier=tier,
                defaults={
                    'tempo_primeira_resposta_horas': resposta,
                    'tempo_resolucao_horas': resolucao,
                },
            )
        self.stdout.write(self.style.SUCCESS(f'  {len(slas)} configs de SLA'))

        self.stdout.write(self.style.SUCCESS('\nAurora HQ configurada com sucesso!'))
