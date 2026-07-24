"""Seed dos 3 fluxos de escrita no HubSoft via painel: conversao de prospecto,
novo servico e upgrade de plano.

Cada fluxo nasce no padrao: gatilho `agenda` + varredura `prospectos_por_criterio`
(o "start por vendedor/status") -> no de escrita do painel em DRY RUN -> marcador
em dados_custom no sucesso, TAREFA pra humano no erro, NOTA no dry_run. O gatilho
pode ser trocado no editor por `evento` (lead_status_mudou) sem mexer no resto.

Seguranca de fabrica: todos nascem INATIVOS, com o no em dry_run e o perfil com
dry_run_forcado (so a allowlist escreve). Idempotente POR NOME por tenant: re-rodar
atualiza grafo/descricao, nunca duplica, e NUNCA liga/desliga um fluxo existente.
Depende de um PerfilConversaoHubsoft chamado como `--perfil` (padrao "padrao").

Uso:
    python manage.py seed_fluxos_hubsoft_escrita --tenant demo-local \\
        --settings=gerenciador_vendas.settings_local
"""
from django.core.management.base import BaseCommand, CommandError

from apps.automacao.models import Fluxo
from apps.automacao.runtime import validar_fluxo


def _grafo(acao_tipo: str, *, perfil: str, marcador: str, status_api: str,
           acao_label: str, acao_config: dict | None = None):
    """Grafo padrao: varredura -> acao (dry_run) -> marcar/tarefa/nota."""
    cfg_acao = {'perfil': perfil, 'dry_run': 'true'}
    cfg_acao.update(acao_config or {})
    nodes = {
        'trigger': {
            'tipo': 'agenda',
            'config': {
                'intervalo_minutos': 30,
                'varredura': 'prospectos_por_criterio',
                'varredura_config': {
                    'status_api': status_api,
                    'com_id_hubsoft': 'true',
                    'sem_marcador': marcador,
                    'exige_vendedor': 'true',
                    'limite': 50,
                },
                'max_por_rodada': 5,
                'max_por_lead': 1,
                'cooldown_horas': 24,
            },
            'pos': {'x': 0, 'y': 0},
            'label': 'Varredura: prospectos por vendedor/status',
        },
        'acao': {
            'tipo': acao_tipo,
            'config': cfg_acao,
            'pos': {'x': 260, 'y': 0},
            'label': acao_label,
        },
        'marcar': {
            'tipo': 'definir_propriedade_lead',
            'config': {
                'propriedade': 'dado_custom',
                'chave': marcador,
                'valor': '{{nodes.acao.resumo}}',
                'somente_se_vazio': 'true',
            },
            'pos': {'x': 540, 'y': -80},
            'label': f'Marcar {marcador}',
        },
        'tarefa_erro': {
            'tipo': 'criar_tarefa',
            'config': {
                'titulo': f'{acao_label}: revisar {{{{lead.nome_razaosocial}}}}',
                'tipo': 'followup',
                'prioridade': 'alta',
                'prazo_dias': '1',
                'descricao': (
                    'A rotina automatica de HubSoft falhou pra este lead.\n'
                    'Erro: {{nodes.acao.erro}}\n\nRevise manualmente no painel.'),
            },
            'pos': {'x': 540, 'y': 80},
            'label': 'Tarefa: revisar no painel',
        },
        'nota_dry': {
            'tipo': 'criar_nota',
            'config': {
                'texto': ('Simulacao (dry run) de {} montou o payload sem escrever. '
                          'Resumo: {{{{nodes.acao.resumo}}}}').format(acao_label),
            },
            'pos': {'x': 540, 'y': 220},
            'label': 'Nota: simulacao registrada',
        },
    }
    conexoes = [
        {'de': 'trigger', 'para': 'acao', 'saida': 'default'},
        {'de': 'acao', 'para': 'marcar', 'saida': 'sucesso'},
        {'de': 'acao', 'para': 'tarefa_erro', 'saida': 'erro'},
        {'de': 'acao', 'para': 'nota_dry', 'saida': 'dry_run'},
    ]
    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


def _fluxos(perfil: str):
    """Os 3 fluxos (nome, descricao, grafo). Nome com [HubSoft] pra agrupar."""
    return [
        {
            'nome': '[HubSoft] Conversao de prospecto em cliente',
            'descricao': (
                'Converte prospectos em clientes no HubSoft via painel. Varre a cada '
                '30min os prospectos com id_hubsoft e vendedor, ainda sem o marcador '
                '_hub_conversao, e roda o no de conversao em DRY RUN (so a allowlist de '
                'CPF do perfil escreve de verdade). Sucesso marca o lead; erro abre '
                'tarefa; dry run vira nota. Nasce INATIVO. Troque o status_api/vendedor '
                'da varredura, ou o gatilho por evento lead_status_mudou, no editor.'),
            'grafo': _grafo('hubsoft_converter_prospecto', perfil=perfil,
                            marcador='_hub_conversao', status_api='pendente',
                            acao_label='Conversao de prospecto'),
        },
        {
            'nome': '[HubSoft] Novo servico',
            'descricao': (
                'Adiciona um novo servico a um cliente ja existente no HubSoft (espelho '
                'ClienteHubsoft), via painel. Mesmo padrao de varredura + dry run + '
                'marcador _hub_novo_servico. Configure o id_servico (plano) no no. '
                'Nasce INATIVO.'),
            'grafo': _grafo('hubsoft_adicionar_servico', perfil=perfil,
                            marcador='_hub_novo_servico', status_api='convertido_cliente',
                            acao_label='Novo servico'),
        },
        {
            'nome': '[HubSoft] Upgrade de plano',
            'descricao': (
                'Migra/upgrade o plano de um servico existente no HubSoft via painel '
                '(POST /cliente/servico com campos de migracao, serviço nasce '
                'habilitado). Configure o id_servico_novo no no. Mesmo padrao de '
                'varredura + dry run + marcador _hub_upgrade. Nasce INATIVO.'),
            'grafo': _grafo('hubsoft_migrar_plano', perfil=perfil,
                            marcador='_hub_upgrade', status_api='convertido_cliente',
                            acao_label='Upgrade de plano',
                            acao_config={'id_servico_novo': ''}),
        },
    ]


class Command(BaseCommand):
    help = ('Seed dos 3 fluxos de escrita no HubSoft (conversao/novo servico/upgrade). '
            'Idempotente por nome, nascem INATIVOS e em dry run.')

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant (obrigatorio).')
        parser.add_argument('--perfil', default='padrao',
                            help='Nome do PerfilConversaoHubsoft usado nos nos (padrao: padrao).')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant

        slug = (opts.get('tenant') or '').strip()
        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant '{slug}' nao encontrado.")
        perfil = (opts.get('perfil') or 'padrao').strip()

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Seed fluxos HubSoft (escrita), tenant: {tenant.slug}, perfil: {perfil}'))

        for spec in _fluxos(perfil):
            erros = validar_fluxo(spec['grafo'])
            if erros:
                raise CommandError(f'Grafo invalido para "{spec["nome"]}": {"; ".join(erros)}')
            fluxo, criado = self._upsert(tenant, spec)
            self.stdout.write(
                f'  {"criado" if criado else "atualizado"}: "{fluxo.nome}" '
                f'(id={fluxo.pk}, ativo={fluxo.ativo})')

        self.stdout.write(self.style.SUCCESS(
            'Seed concluido. Os 3 nascem INATIVOS e em dry run. Revise o perfil '
            '(template/IDs/allowlist) e os filtros da varredura antes de ativar.'))

    def _upsert(self, tenant, spec):
        fluxo = Fluxo.all_tenants.filter(tenant=tenant, nome=spec['nome']).first()
        criado = fluxo is None
        if fluxo is None:
            fluxo = Fluxo.all_tenants.create(
                tenant=tenant, nome=spec['nome'], descricao=spec['descricao'],
                grafo=spec['grafo'], ativo=False)
            return fluxo, criado
        fluxo.descricao = spec['descricao']
        fluxo.grafo = spec['grafo']
        fluxo.save()  # `ativo` intocado (nunca liga/desliga num re-run)
        return fluxo, criado
