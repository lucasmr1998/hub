"""Seed do fluxo de follow-up de oportunidade parada no estágio (pedido da Gabi,
Nuvyon): quando uma op fica sem avançar tempo demais numa etapa do funil ("lead
esquecido na coluna"), cria uma TAREFA pra vendedora responsável revisar.

O limite de tempo é POR ETAPA, via `PipelineEstagio.sla_horas` (a Gabi vai
preencher no CRM; hoje o campo nasce vazio). SEM SLA cadastrado num estágio,
esse estágio simplesmente não entra na varredura (`apenas_com_sla=true`).

Idempotente POR NOME (get por tenant + nome): re-rodar atualiza grafo/descrição
em vez de duplicar. Nasce INATIVO (`ativo=False`); num fluxo que já existe o
campo `ativo` NUNCA é tocado (o comando nunca liga nem desliga um fluxo).

Diferente do fluxo de recuperação de perdidas (`seed_fluxos_recuperacao_analise`):
aqui NÃO há marcador em `dados_custom` — o follow-up é RECORRENTE (a mesma op
pode parar de novo em outra etapa depois). O freio contra recriar a tarefa toda
hora é o `cooldown_horas` do gatilho `agenda`, não um marcador permanente.

Uso:
    python manage.py seed_fluxo_oportunidades_paradas --tenant nuvyon \\
        --settings=gerenciador_vendas.settings_local
"""
from django.core.management.base import BaseCommand, CommandError

from apps.automacao.models import Fluxo
from apps.automacao.runtime import validar_fluxo

NOME_FLUXO = '[Nuvyon] Follow-up de oportunidade parada'

DESCRICAO_FLUXO = (
    'Varredura a cada 15min das oportunidades vivas (estágio não final) paradas '
    'além do SLA da etapa atual (PipelineEstagio.sla_horas, preenchido pela Gabi '
    'no CRM). Cria uma TAREFA pra vendedora responsável revisar e mover o lead no '
    'funil, mais uma nota registrando o achado. Só entram oportunidades COM '
    'responsável definido (exige_responsavel), pra a tarefa nunca nascer órfã, e '
    'só estágios com SLA preenchido (apenas_com_sla). RECORRENTE: sem marcador '
    'permanente em dados_custom (a op pode parar de novo em outra etapa depois) — '
    'o freio contra recriar a mesma tarefa é o cooldown_horas do gatilho. Teto '
    'baixo por rodada (max_por_rodada) pra não despejar o backlog acumulado de '
    'uma vez só. Nasce INATIVO, revisar antes de ligar.'
)

_DESCRICAO_TAREFA = '\n'.join([
    'Oportunidade parada ha {{var.horas_paradas}}h em "{{var.estagio_nome}}" (limite {{var.sla_horas}}h).',
    '',
    'Reveja o lead e mova pra etapa correta do funil, ou registre o proximo passo.',
])


def _grafo():
    nodes = {
        'trigger': {
            'tipo': 'agenda',
            'config': {
                'intervalo_minutos': 15,
                'varredura': 'oportunidades_paradas',
                'varredura_config': {
                    'apenas_com_sla': 'true',
                    'exige_responsavel': 'true',
                },
                'max_por_rodada': 10,
                'max_por_lead': 1,
                'cooldown_horas': 24,
            },
            'pos': {'x': 0, 'y': 0},
            'label': 'Varredura: oportunidades paradas (SLA)',
        },
        'tarefa': {
            'tipo': 'criar_tarefa',
            'config': {
                'titulo': 'Mover no funil: {{lead.nome_razaosocial}}',
                'tipo': 'followup',
                'prioridade': 'alta',
                'prazo_dias': '1',
                'descricao': _DESCRICAO_TAREFA,
            },
            'pos': {'x': 240, 'y': 0},
            'label': 'Tarefa: mover no funil',
        },
        'nota': {
            'tipo': 'criar_nota',
            'config': {
                'texto': (
                    'Follow-up automatico: parada ha {{var.horas_paradas}}h em {{var.estagio_nome}}.'
                ),
            },
            'pos': {'x': 480, 'y': 0},
            'label': 'Nota: follow-up automatico',
        },
    }
    conexoes = [
        {'de': 'trigger', 'para': 'tarefa', 'saida': 'default'},
        {'de': 'tarefa', 'para': 'nota', 'saida': 'sucesso'},
    ]
    return {'inicio': 'trigger', 'nodes': nodes, 'conexoes': conexoes}


class Command(BaseCommand):
    help = (
        'Seed do fluxo de follow-up de oportunidade parada no estágio (pedido da '
        'Gabi, Nuvyon). Idempotente por nome, nasce INATIVO.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant (obrigatório).')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant

        slug = (opts.get('tenant') or '').strip()
        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant '{slug}' não encontrado.")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Seed fluxo oportunidades paradas, tenant: {tenant.slug}'))

        grafo = _grafo()
        erros = validar_fluxo(grafo)
        if erros:
            raise CommandError(f'Grafo inválido para "{NOME_FLUXO}": {"; ".join(erros)}')

        fluxo, criado = self._upsert_fluxo(tenant, grafo)
        self.stdout.write(
            f'  {"criado" if criado else "atualizado"}: fluxo "{fluxo.nome}" '
            f'(id={fluxo.pk}, ativo={fluxo.ativo})')

        self.stdout.write(self.style.SUCCESS('Seed concluído. Nasce INATIVO, revisar antes de ativar.'))

    def _upsert_fluxo(self, tenant, grafo):
        fluxo = Fluxo.all_tenants.filter(tenant=tenant, nome=NOME_FLUXO).first()
        criado = fluxo is None
        if fluxo is None:
            fluxo = Fluxo.all_tenants.create(
                tenant=tenant, nome=NOME_FLUXO, descricao=DESCRICAO_FLUXO, grafo=grafo, ativo=False,
            )
            return fluxo, criado
        fluxo.descricao = DESCRICAO_FLUXO
        fluxo.grafo = grafo
        fluxo.save()  # `ativo` propositalmente intocado (nunca liga/desliga num re-run)
        return fluxo, criado
