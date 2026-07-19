"""Organiza e estrutura o CRM do Robô V2 — estágios, regras, tags e status.

Alinha o pipeline de aquisição ao funil real do bot (RegraValidacao):

    cumprimento → endereço/CEP → plano → nome/CPF → confirmação de dados
    → documentação (selfie/frente/verso) → agendamento → instalação

O que faz (idempotente — pode rodar quantas vezes quiser):
1. Estágios de aquisição: cores/ícones no padrão TecHub (slugs e SLAs mantidos).
2. RegraPipelineEstagio: regras de movimentação automática ligando os eventos
   que o bot grava (HistoricoContato.status, status_api, tags, serviço HubSoft)
   a cada estágio do Kanban. Sem isso o pipeline não anda sozinho.
3. TagCRM: pré-cadastra todas as tags que as RegraValidacao aplicam, com cor
   por fase do funil (evita tags soltas criadas on-the-fly com cor padrão).
4. StatusConfiguravel: completa os grupos lead_status_api e historico_status
   com os códigos que o robô realmente usa.

Uso:
    python manage.py organizar_crm           # aplica
    python manage.py organizar_crm --dry-run # só mostra o que faria
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from crm.models import PipelineEstagio, RegraPipelineEstagio, TagCRM
from vendas_web.models import StatusConfiguravel


# ── 1. Estágios (aquisição) — visual TecHub ─────────────────────────────────
ESTAGIOS = {
    # slug: (cor_hex, icone_fa)
    'novo':                  ('#0022fa', 'fa-user-plus'),
    'qualificacao':          ('#6366f1', 'fa-list-check'),
    'aguardando_assinatura': ('#f59e0b', 'fa-file-signature'),
    'instalacao':            ('#ff6b00', 'fa-screwdriver-wrench'),
    'ativo':                 ('#10b981', 'fa-check-circle'),
    'perdido':               ('#ef4444', 'fa-times-circle'),
}

# ── 2. Regras de movimentação automática ────────────────────────────────────
# Avaliação do motor: estágios em ordem DECRESCENTE (mais avançado primeiro),
# regras OR entre si, condições AND dentro da regra. Estágios finais não
# reavaliam. Por isso "Perdido" só tem perdas DEFINITIVAS (abandono/transbordo
# ficam de fora: o lead pode retomar o fluxo).
def _c(tipo, valor, operador='igual', campo=''):
    cond = {'tipo': tipo, 'operador': operador, 'valor': valor}
    if campo:
        cond['campo'] = campo
    return cond


REGRAS = {
    'qualificacao': [
        ('CEP validado pelo robô',        [_c('historico_status', 'cep_validado')]),
        ('Plano confirmado na conversa',  [_c('historico_status', 'plano_confirmado')]),
        ('CPF validado pelo robô',        [_c('historico_status', 'cpf_validado')]),
        ('Plano selecionado',             [_c('historico_status', 'plano_selecionado')]),
    ],
    'aguardando_assinatura': [
        ('Dados confirmados pelo cliente', [_c('historico_status', 'dados_confirmados')]),
        ('Documentação em envio',          [_c('tag', 'Documentação')]),
    ],
    'instalacao': [
        ('Cadastro concluído (docs completos)', [_c('historico_status', 'cadastro_concluido')]),
        ('Instalação agendada (histórico)',     [_c('historico_status', 'instalacao_agendada')]),
        ('Instalação agendada (status do lead)', [_c('lead_status_api', 'instalacao_agendada')]),
    ],
    'ativo': [
        # status real do HubSoft p/ serviço habilitado = 'servico_habilitado'
        ('Serviço habilitado no HubSoft', [_c('servico_status', 'servico_habilitado')]),
        ('Venda confirmada',              [_c('converteu_venda', True)]),
        ('Lead instalado',                [_c('lead_status_api', 'instalado')]),
    ],
    'perdido': [
        ('Lead cancelado',     [_c('lead_status_api', 'cancelado')]),
        ('Cliente desistiu',   [_c('historico_status', 'cliente_desistiu')]),
        ('Venda rejeitada',    [_c('historico_status', 'venda_rejeitada')]),
        ('Sem viabilidade',    [_c('historico_status', 'venda_sem_viabilidade')]),
        ('Não qualificado',    [_c('historico_status', 'nao_qualificado')]),
    ],
}

# ── 3. Tags do funil (mesmos nomes que as RegraValidacao aplicam) ───────────
TAGS = {
    # nome: cor_hex  (fase: cinza=entrada, azul=comercial, âmbar/laranja=docs/
    # instalação, verde=concluído)
    'Lead Novo':           '#94a3b8',
    'Endereço':            '#f59e0b',
    'Comercial':           '#0022fa',
    'CPF Validado':        '#6366f1',
    'Plano Escolhido':     '#0018b0',
    'Dados Confirmados':   '#10b981',
    'Documentação':        '#0ea5e9',
    'Documental':          '#0ea5e9',
    'Assinado':            '#059669',
    'Docs Completos':      '#14b8a6',
    'Cadastro Concluído':  '#16a34a',
    'Instalação Agendada': '#ff6b00',
}

# ── 4. Status configuráveis usados pelo robô ────────────────────────────────
STATUS_LEAD_API = [
    # (codigo, rotulo) — continuação dos 7 já seedados
    ('aguardando_assinatura', 'Aguardando Assinatura'),
    ('em_instalacao',         'Em Instalação'),
    ('instalado',             'Instalado'),
    ('cancelado',             'Cancelado'),
    ('inativo',               'Inativo'),
    ('lead_novo',             'Lead Novo (robô)'),
    ('cliente_ativo',         'Cliente Ativo (HubSoft)'),
    ('instalacao_agendada',   'Instalação Agendada'),
    ('transbordo_atendente',  'Transbordo p/ Atendente'),
    ('em_fluxo_new_service',  'Em Fluxo: Novo Serviço'),
    ('em_fluxo_upgrade',      'Em Fluxo: Upgrade'),
    ('atendimento_concluido', 'Atendimento Concluído'),
]

STATUS_HISTORICO = [
    ('canal_escolhido',             'Canal Escolhido'),
    ('cep_validado',                'CEP Validado'),
    ('endereco_confirmado',         'Endereço Confirmado'),
    ('plano_confirmado',            'Plano Confirmado'),
    ('plano_alternativo_escolhido', 'Plano Alternativo Escolhido'),
    ('cpf_validado',                'CPF Validado'),
    ('plano_selecionado',           'Plano Selecionado'),
    ('dados_confirmados',           'Dados Confirmados'),
    ('doc_selfie_enviada',          'Selfie Enviada'),
    ('doc_frente_enviada',          'Doc. Frente Enviada'),
    ('cadastro_concluido',          'Cadastro Concluído'),
    ('turno_escolhido',             'Turno Escolhido'),
    ('instalacao_agendada',         'Instalação Agendada'),
    ('ajuste_solicitado',           'Ajuste Solicitado'),
    ('documentacao_enviada',        'Documentação Enviada'),
    ('proposta_enviada',            'Proposta Enviada'),
    ('proposta_aceita',             'Proposta Aceita'),
    ('contrato_assinado',           'Contrato Assinado'),
    ('em_negociacao',               'Em Negociação'),
    ('retorno_agendado',            'Retorno Agendado'),
    ('cancelamento_solicitado',     'Cancelamento Solicitado'),
    ('reativacao',                  'Reativação'),
]


class Command(BaseCommand):
    help = 'Organiza estágios, regras de pipeline, tags e status do CRM (idempotente)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Só mostra o que faria')

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING('DRY-RUN — nada será gravado'))

        # 0. Etapa final 'Serviço Ativo' do pós-venda (novo serviço habilitado)
        if not dry:
            PipelineEstagio.objects.filter(slug='ns_concluido').update(
                is_final_ganho=False, probabilidade_padrao=90)
            PipelineEstagio.objects.filter(slug='ns_falha').update(ordem=6)
            PipelineEstagio.objects.update_or_create(
                slug='ns_ativo',
                defaults=dict(nome='Serviço Ativo', pipeline_tipo='novo_servico', ordem=5,
                              tipo='cliente', is_final_ganho=True, probabilidade_padrao=100,
                              cor_hex='#10b981', icone_fa='fa-check-circle', ativo=True),
            )
            self.stdout.write('0. etapa ns_ativo (Serviço Ativo) garantida')

        # 1. Estágios
        self.stdout.write(self.style.MIGRATE_HEADING('1. Estágios (aquisição)'))
        for slug, (cor, icone) in ESTAGIOS.items():
            estagio = PipelineEstagio.objects.filter(slug=slug).first()
            if not estagio:
                self.stdout.write(self.style.ERROR(f'  estágio {slug!r} não existe — pulei'))
                continue
            if not dry:
                estagio.cor_hex = cor
                estagio.icone_fa = icone
                estagio.save(update_fields=['cor_hex', 'icone_fa'])
            self.stdout.write(f'  {estagio.ordem}. {estagio.nome} → cor {cor}, ícone {icone}')

        # 2. Regras de movimentação
        self.stdout.write(self.style.MIGRATE_HEADING('2. Regras de movimentação automática'))
        criadas = atualizadas = 0
        for slug, regras in REGRAS.items():
            estagio = PipelineEstagio.objects.filter(slug=slug).first()
            if not estagio:
                continue
            for prioridade, (nome, condicoes) in enumerate(regras):
                if dry:
                    self.stdout.write(f'  [{estagio.nome}] {nome}: {condicoes}')
                    continue
                _, created = RegraPipelineEstagio.objects.update_or_create(
                    estagio=estagio,
                    nome=nome,
                    defaults={'condicoes': condicoes, 'prioridade': prioridade, 'ativo': True},
                )
                criadas += created
                atualizadas += (not created)
                self.stdout.write(f'  [{estagio.nome}] {"+" if created else "="} {nome}')
        self.stdout.write(f'  regras: {criadas} criadas, {atualizadas} atualizadas')

        # 3. Tags
        self.stdout.write(self.style.MIGRATE_HEADING('3. Tags do funil'))
        for nome, cor in TAGS.items():
            if dry:
                self.stdout.write(f'  {nome} → {cor}')
                continue
            tag, created = TagCRM.objects.update_or_create(
                nome=nome, defaults={'cor_hex': cor},
            )
            self.stdout.write(f'  {"+" if created else "="} {nome} ({cor})')

        # 4. Status configuráveis
        self.stdout.write(self.style.MIGRATE_HEADING('4. Status configuráveis'))
        for grupo, lista, ordem_base in (
            ('lead_status_api', STATUS_LEAD_API, 100),
            ('historico_status', STATUS_HISTORICO, 100),
        ):
            novos = 0
            for i, (codigo, rotulo) in enumerate(lista):
                if dry:
                    continue
                _, created = StatusConfiguravel.objects.get_or_create(
                    grupo=grupo, codigo=codigo,
                    defaults={'rotulo': rotulo, 'ativo': True, 'ordem': ordem_base + i},
                )
                novos += created
            self.stdout.write(f'  {grupo}: +{novos} novos (total agora: '
                              f'{StatusConfiguravel.objects.filter(grupo=grupo).count()})')

        if dry:
            transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS('CRM organizado.'))
