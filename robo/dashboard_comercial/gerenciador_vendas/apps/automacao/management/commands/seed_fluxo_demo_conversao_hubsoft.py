"""Seed de um fluxo minimo pra teste manual da conversao HubSoft no editor da
engine de automacao: Carregar lead -> HubSoft: converter prospecto em cliente.

Diferente de `seed_fluxos_hubsoft_escrita` (que semeia os 3 fluxos de producao
com gatilho de agenda/varredura), este fluxo NAO tem trigger nenhum: e so pra
abrir no editor (/automacao/editor/) e clicar em "Testar" (ou duplo clique no no
de conversao -> "Executar no"), com o lead alvo fixo no proprio grafo.

O no de conversao NASCE sem `dry_run` sobrescrito, ou seja, respeita o guard do
`PerfilConversaoHubsoft` (dry_run_forcado + cpf_allowlist). Pra validar uma
escrita real, adicione o CPF do lead na allowlist do perfil antes de testar;
sem isso, todo teste sai em dry_run (comportamento seguro por padrao).

Uso:
    python manage.py seed_fluxo_demo_conversao_hubsoft --tenant demo-local \\
        --lead-id 5 --settings=gerenciador_vendas.settings_local
"""
from django.core.management.base import BaseCommand, CommandError

from apps.automacao.models import Fluxo
from apps.automacao.runtime import validar_fluxo


def _grafo(lead_id: str, perfil: str) -> dict:
    return {
        'inicio': 'carregar',
        'nodes': {
            'carregar': {
                'tipo': 'carregar_lead',
                'config': {'lead_id': str(lead_id)},
                'pos': {'x': 0, 'y': 0},
                'label': f'Carregar lead {lead_id}',
            },
            'converter': {
                'tipo': 'hubsoft_converter_prospecto',
                'config': {'perfil': perfil},
                'pos': {'x': 320, 'y': 0},
                'label': 'HubSoft: converter prospecto em cliente',
            },
        },
        'conexoes': [
            {'de': 'carregar', 'para': 'converter', 'saida': 'encontrado'},
        ],
    }


class Command(BaseCommand):
    help = ('Seed de um fluxo Carregar lead -> Converter prospecto, pra teste manual '
            'no editor (botao Testar). Sem gatilho, sem override de dry_run no no; a '
            'decisao de escrita real fica inteira no PerfilConversaoHubsoft. Nasce '
            'INATIVO. Idempotente por nome (re-rodar atualiza o grafo).')

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant.')
        parser.add_argument('--lead-id', required=True, help='pk do LeadProspecto alvo.')
        parser.add_argument('--perfil', default='padrao',
                            help='Nome do PerfilConversaoHubsoft usado no no (default: padrao).')
        parser.add_argument('--nome', default=None,
                            help='Nome do fluxo (default: "[TESTE] Demo conversao HubSoft (lead <id>)").')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant
        from apps.comercial.leads.models import LeadProspecto

        slug = (opts.get('tenant') or '').strip()
        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant '{slug}' nao encontrado.")

        lead_id = str(opts['lead_id']).strip()
        lead = LeadProspecto.objects.filter(pk=lead_id, tenant=tenant).first()
        if lead is None:
            raise CommandError(f'Lead pk={lead_id} nao encontrado no tenant {tenant.slug}.')

        perfil = (opts.get('perfil') or 'padrao').strip()
        nome = (opts.get('nome') or '').strip() or (
            f'[TESTE] Demo conversao HubSoft (lead {lead.id_hubsoft or lead.pk})')

        grafo = _grafo(lead_id, perfil)
        erros = validar_fluxo(grafo)
        if erros:
            raise CommandError(f'Grafo invalido: {"; ".join(erros)}')

        fluxo, criado = Fluxo.all_tenants.update_or_create(
            tenant=tenant, nome=nome,
            defaults=dict(
                descricao=(
                    'Fluxo de demonstracao/teste manual: carrega o lead informado e '
                    'roda o node de conversao HubSoft via API interna do painel (sem '
                    'clicar em nada no HubSoft, so login com token cacheado). Sem '
                    'trigger automatico — e so pra clicar "Testar" no editor. O guard '
                    'de escrita real e do PerfilConversaoHubsoft (dry_run_forcado + '
                    'cpf_allowlist); sem o CPF do lead na allowlist, sai sempre em '
                    'dry_run.'),
                grafo=grafo, ativo=False,
            ),
        )
        self.stdout.write(self.style.SUCCESS(
            f'{"criado" if criado else "atualizado"}: "{fluxo.nome}" '
            f'(id={fluxo.pk}, ativo={fluxo.ativo}, lead={lead.pk})'))
