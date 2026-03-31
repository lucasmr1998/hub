"""
Popula o CRM com dados existentes do sistema Megalink.

Mapeamento por prioridade (avalia na ordem abaixo e usa a primeira que bate):

  P1: Lead tem ClienteHubsoft com status_prefixo='servico_habilitado'
      → tipo='cliente'  (Cliente Ativo)

  P2: Lead tem ClienteHubsoft com status_prefixo='aguardando_instalacao'
      → tipo='fechamento' (Aguardando Instalação)

  P3: Lead tem documentacao_validada=True (sem Hubsoft correspondente)
      → tipo='fechamento' (Aguardando Instalação)

  P4: Lead tem status_api='processado' e documentacao_validada=False
      → tipo='negociacao' (Aguardando Assinatura)

  P5: Lead tem status_api='processamento_manual'
      → tipo='qualificacao' (Em Qualificação)

  P6: Todos os demais
      → tipo='novo' (Novo Lead)

Uso:
    python manage.py popular_crm
    python manage.py popular_crm --dry-run          (simula sem gravar)
    python manage.py popular_crm --limpar            (apaga OportunidadeVenda antes de popular)
    python manage.py popular_crm --criar-perfis      (cria PerfilVendedor para usuários sem perfil)
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction


def determinar_tipo_estagio(lead, ids_servico_habilitado, ids_aguardando_instalacao):
    """
    Retorna o tipo de estágio para o lead com base no mapeamento de prioridade.

    Args:
        lead: instância de LeadProspecto
        ids_servico_habilitado: set de lead_ids com status 'servico_habilitado'
        ids_aguardando_instalacao: set de lead_ids com status 'aguardando_instalacao'
    """
    # P1: Cliente Ativo no Hubsoft
    if lead.pk in ids_servico_habilitado:
        return 'cliente'

    # P2: Aguardando instalação no Hubsoft
    if lead.pk in ids_aguardando_instalacao:
        return 'fechamento'

    # P3: Documentação validada (sem Hubsoft ativo)
    if getattr(lead, 'documentacao_validada', False):
        return 'fechamento'

    # P4: Processado sem documentação validada → Aguardando Assinatura
    status = (lead.status_api or '').strip()
    if status == 'processado' and not getattr(lead, 'documentacao_validada', False):
        return 'negociacao'

    # P5: Em processamento manual → Em Qualificação
    if status == 'processamento_manual':
        return 'qualificacao'

    # P6: Novo Lead
    return 'novo'


class Command(BaseCommand):
    help = 'Popula o app CRM com os dados existentes de LeadProspecto'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Simula a operação sem gravar no banco'
        )
        parser.add_argument(
            '--limpar', action='store_true',
            help='Apaga OportunidadeVenda existentes antes de popular'
        )
        parser.add_argument(
            '--criar-perfis', action='store_true',
            help='Cria PerfilVendedor para usuários ativos sem perfil CRM'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limpar = options['limpar']
        criar_perfis = options['criar_perfis']

        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n🚀 Popular CRM com dados existentes'
            + (' [DRY RUN]' if dry_run else '')
        ))

        from apps.comercial.crm.models import (
            PipelineEstagio, OportunidadeVenda, HistoricoPipelineEstagio,
            PerfilVendedor,
        )
        from apps.comercial.leads.models import LeadProspecto
        from django.contrib.auth.models import User

        # ----------------------------------------------------------------
        # 1. Carregar estágios indexados por tipo
        # ----------------------------------------------------------------
        estagios_por_tipo = {}
        for e in PipelineEstagio.objects.filter(ativo=True).order_by('ordem'):
            if e.tipo not in estagios_por_tipo:
                estagios_por_tipo[e.tipo] = e

        self.stdout.write(f'\n  Estágios disponíveis:')
        for tipo, estagio in estagios_por_tipo.items():
            self.stdout.write(f'    tipo={tipo!r} → "{estagio.nome}" (slug={estagio.slug!r})')

        tipos_necessarios = {'novo', 'qualificacao', 'negociacao', 'fechamento', 'cliente'}
        faltando = tipos_necessarios - set(estagios_por_tipo.keys())
        if faltando:
            raise CommandError(
                f'\n  ✗ Tipos de estágio ausentes: {faltando}\n'
                f'  Crie os estágios no admin em /admin/crm/pipelineestagio/'
            )
        self.stdout.write(self.style.SUCCESS(f'\n  ✓ Todos os tipos de estágio encontrados'))

        # ----------------------------------------------------------------
        # 2. Pré-carregar dados do Hubsoft para joins eficientes
        # ----------------------------------------------------------------
        self.stdout.write('\n  Carregando dados do Hubsoft...')
        try:
            from apps.integracoes.models import ClienteHubsoft, ServicoClienteHubsoft

            # Lead IDs com 'servico_habilitado'
            ids_servico_habilitado = set(
                ClienteHubsoft.objects
                .filter(
                    servicos__status_prefixo='servico_habilitado'
                )
                .values_list('lead_id', flat=True)
            )

            # Lead IDs com 'aguardando_instalacao'
            ids_aguardando_instalacao = set(
                ClienteHubsoft.objects
                .filter(
                    servicos__status_prefixo='aguardando_instalacao'
                )
                .values_list('lead_id', flat=True)
            ) - ids_servico_habilitado  # evitar sobreposição

            self.stdout.write(
                f'    servico_habilitado:    {len(ids_servico_habilitado)} leads\n'
                f'    aguardando_instalacao: {len(ids_aguardando_instalacao)} leads'
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f'  ⚠ Não foi possível carregar dados do Hubsoft: {e}\n'
                f'    Leads Hubsoft serão tratados como Novo Lead'
            ))
            ids_servico_habilitado = set()
            ids_aguardando_instalacao = set()

        # ----------------------------------------------------------------
        # 3. (Opcional) Criar PerfilVendedor para usuários sem perfil
        # ----------------------------------------------------------------
        if criar_perfis:
            self._criar_perfis_vendedor(User, PerfilVendedor, dry_run)

        # ----------------------------------------------------------------
        # 4. (Opcional) Limpar oportunidades existentes
        # ----------------------------------------------------------------
        if limpar and not dry_run:
            count_antes = OportunidadeVenda.objects.count()
            OportunidadeVenda.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'\n  ⚠ {count_antes} OportunidadeVenda removidas')
            )

        # ----------------------------------------------------------------
        # 5. Popular OportunidadeVenda para cada LeadProspecto
        # ----------------------------------------------------------------
        leads = LeadProspecto.objects.filter(ativo=True).order_by('data_cadastro')
        total = leads.count()
        self.stdout.write(f'\n  Processando {total} leads ativos...')

        # IDs de leads que já têm oportunidade
        ids_com_op = set(
            OportunidadeVenda.objects.values_list('lead_id', flat=True)
        )

        stats = {
            'criados': 0,
            'ja_existia': 0,
            'por_estagio': {},
        }

        ops_para_criar = []

        for lead in leads:
            if lead.pk in ids_com_op and not limpar:
                stats['ja_existia'] += 1
                continue

            # Determinar tipo de estágio pela nova lógica de negócio
            tipo = determinar_tipo_estagio(
                lead,
                ids_servico_habilitado,
                ids_aguardando_instalacao,
            )
            estagio = estagios_por_tipo[tipo]

            # Data de entrada = data de cadastro do lead
            data_entrada = lead.data_cadastro
            if data_entrada and timezone.is_naive(data_entrada):
                data_entrada = timezone.make_aware(data_entrada)
            if not data_entrada:
                data_entrada = timezone.now()

            op = OportunidadeVenda(
                lead=lead,
                estagio=estagio,
                titulo=lead.nome_razaosocial or '',
                valor_estimado=lead.valor if lead.valor else None,
                probabilidade=estagio.probabilidade_padrao,
                origem_crm='importacao',
                data_entrada_estagio=data_entrada,
                churn_risk_score=None,
            )
            if estagio.is_final_ganho:
                op.data_fechamento_real = data_entrada

            stats['criados'] += 1
            stats['por_estagio'][estagio.nome] = stats['por_estagio'].get(estagio.nome, 0) + 1

            if dry_run:
                status_display = (lead.status_api or '').strip() or '—'
                doc = '✓doc' if getattr(lead, 'documentacao_validada', False) else '✗doc'
                hub = ''
                if lead.pk in ids_servico_habilitado:
                    hub = ' [hub:ativo]'
                elif lead.pk in ids_aguardando_instalacao:
                    hub = ' [hub:inst]'
                self.stdout.write(
                    f'    [DRY] {lead.nome_razaosocial or "?":<28} '
                    f'{status_display:<22} {doc}{hub} → {estagio.nome}'
                )
            else:
                ops_para_criar.append(op)

        # Inserção em lote
        if not dry_run and ops_para_criar:
            with transaction.atomic():
                criadas = OportunidadeVenda.objects.bulk_create(
                    ops_para_criar, ignore_conflicts=False
                )
                self.stdout.write(
                    f'\n  Criando histórico inicial para {len(criadas)} oportunidades...'
                )
                historicos = [
                    HistoricoPipelineEstagio(
                        oportunidade=op,
                        estagio_anterior=None,
                        estagio_novo=op.estagio,
                        motivo='Importação inicial — mapeamento por status/Hubsoft/documentação',
                        tempo_no_estagio_horas=0,
                    )
                    for op in criadas
                ]
                HistoricoPipelineEstagio.objects.bulk_create(historicos)

        # ----------------------------------------------------------------
        # 6. Relatório final
        # ----------------------------------------------------------------
        self._imprimir_relatorio(stats, dry_run)

    def _criar_perfis_vendedor(self, User, PerfilVendedor, dry_run):
        self.stdout.write('\n  --- Criando PerfilVendedor ---')
        usuarios = User.objects.filter(is_active=True)
        ids_com_perfil = set(
            PerfilVendedor.objects.values_list('user_id', flat=True)
        )

        criados = 0
        for u in usuarios:
            if u.pk not in ids_com_perfil:
                if not dry_run:
                    PerfilVendedor.objects.create(
                        user=u,
                        cargo='vendedor',
                        ativo=True,
                    )
                criados += 1
                self.stdout.write(
                    f'    {"[DRY] " if dry_run else "✓ "}PerfilVendedor: '
                    f'{u.get_full_name() or u.username}'
                )

        if criados == 0:
            self.stdout.write('    (todos os usuários já têm perfil)')
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'    Total: {criados} perfis {"simulados" if dry_run else "criados"}'
                )
            )

    def _imprimir_relatorio(self, stats, dry_run):
        prefixo = '[DRY RUN] ' if dry_run else ''
        self.stdout.write('\n' + '─' * 60)
        self.stdout.write(self.style.SUCCESS(f'\n  {prefixo}✅ Resultado:\n'))
        self.stdout.write(f'    Criados:     {stats["criados"]}')
        self.stdout.write(f'    Já existiam: {stats["ja_existia"]}')

        if stats['por_estagio']:
            self.stdout.write('\n    Distribuição por estágio:')
            for nome, qtd in sorted(stats['por_estagio'].items(), key=lambda x: -x[1]):
                barra = '█' * min(qtd // 5 + 1, 35)
                self.stdout.write(f'      {nome:<30} {barra} {qtd}')

        self.stdout.write('')
