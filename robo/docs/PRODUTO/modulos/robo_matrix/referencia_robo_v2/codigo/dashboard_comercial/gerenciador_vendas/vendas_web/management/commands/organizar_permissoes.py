"""Semeia/atualiza os PERFIS DE ACESSO padrão (RBAC). Idempotente.

    python manage.py organizar_permissoes

Não remove perfis criados manualmente nem mexe em atribuições de usuários — só
garante que os 5 perfis padrão existam com um conjunto de capacidades sensato.
"""
from django.core.management.base import BaseCommand

from vendas_web.models import PerfilAcesso
from vendas_web.rbac import TODAS_CAPACIDADES

VER_TODOS = [c for c in TODAS_CAPACIDADES if c.startswith('ver_')]

PERFIS = [
    {
        'slug': 'administrador', 'nome': 'Administrador', 'cor_hex': '#0022fa',
        'descricao': 'Acesso total — vê e opera tudo, gerencia usuários e configurações.',
        'escopo_dados': 'todos',
        'capacidades': sorted(TODAS_CAPACIDADES),
    },
    {
        'slug': 'gerente', 'nome': 'Gerente / Supervisor', 'cor_hex': '#6d28d9',
        'descricao': 'Vê todos os pipelines e relatórios; opera; sem configs de sistema.',
        'escopo_dados': 'todos',
        'capacidades': sorted(set(VER_TODOS) | {
            'operar_mover_oportunidade', 'operar_editar_lead', 'operar_indicacao',
            'operar_wifeed', 'operar_atribuir', 'operar_tarefas', 'gerenciar_wifeed',
        }),
    },
    {
        'slug': 'operador', 'nome': 'Operador', 'cor_hex': '#0ea5e9',
        'descricao': 'Opera pipelines de Indicação, Wifeed e Atendimento; sem configs.',
        'escopo_dados': 'pipeline',
        'capacidades': sorted({
            'ver_dashboard', 'ver_leads', 'ver_tarefas',
            'ver_pipeline_indicacao', 'ver_pipeline_wifeed', 'ver_pipeline_atendimento',
            'operar_mover_oportunidade', 'operar_editar_lead', 'operar_indicacao',
            'operar_wifeed', 'operar_tarefas',
        }),
    },
    {
        'slug': 'vendedor', 'nome': 'Vendedor', 'cor_hex': '#16a34a',
        'descricao': 'Opera apenas os próprios registros (aquisição).',
        'escopo_dados': 'proprios',
        'capacidades': sorted({
            'ver_dashboard', 'ver_leads', 'ver_vendas', 'ver_pipeline_aquisicao',
            'ver_tarefas', 'ver_metas',
            'operar_mover_oportunidade', 'operar_editar_lead', 'operar_tarefas',
        }),
    },
    {
        'slug': 'auditor', 'nome': 'Auditor', 'cor_hex': '#6b7280',
        'descricao': 'Somente leitura — vê tudo, não altera nada.',
        'escopo_dados': 'todos',
        'capacidades': sorted(VER_TODOS),
    },
]


class Command(BaseCommand):
    help = 'Cria/atualiza os perfis de acesso padrão (RBAC).'

    def handle(self, *args, **opts):
        for p in PERFIS:
            obj, created = PerfilAcesso.objects.update_or_create(
                slug=p['slug'],
                defaults={
                    'nome': p['nome'], 'descricao': p['descricao'],
                    'cor_hex': p['cor_hex'], 'ativo': True,
                    'capacidades': p['capacidades'], 'escopo_dados': p['escopo_dados'],
                },
            )
            self.stdout.write(('  + ' if created else '  ~ ') +
                              f"{obj.nome} ({len(obj.capacidades)} caps, escopo={obj.escopo_dados})")
        self.stdout.write(self.style.SUCCESS(f'OK — {len(PERFIS)} perfis garantidos.'))
