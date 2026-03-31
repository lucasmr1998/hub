"""
Comando: taguear_leads

Analisa os dados preenchidos em cada LeadProspecto e atribui automaticamente
as tags CRM correspondentes às OportunidadeVenda.

Lógica de tagging baseada nos campos realmente preenchidos:

  Tag "Comercial"   → lead tem id_plano_rp preenchido (escolheu um plano de serviço)
  Tag "Endereço"    → lead tem rua + número + bairro + cep preenchidos (endereço completo)
  Tag "Documental"  → lead tem cpf_cnpj preenchido (documento de identificação)

As tags são acumulativas: um lead pode ter 0, 1, 2 ou 3 tags.
A ausência de uma tag indica exatamente o que ainda falta ser coletado.

Opções:
  --dry-run     Mostra o que seria feito sem gravar no banco
  --resetar     Remove todas as tags antes de re-aplicar (reprocessamento limpo)
  --estagio     Filtra apenas leads em determinado tipo de estágio
                (novo|qualificacao|negociacao|fechamento|cliente|perdido)
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.comercial.crm.models import OportunidadeVenda, TagCRM


TAG_COMERCIAL = 'Comercial'
TAG_ENDERECO = 'Endereço'
TAG_DOCUMENTAL = 'Documental'


def _campos_preenchidos(lead):
    """Retorna set de nomes de tags que se aplicam a este lead."""
    tags = set()

    # ── COMERCIAL ─────────────────────────────────────────────────────────
    # Critério: escolheu um plano de serviço (id_plano_rp) ou
    # definiu o dia de vencimento (id_dia_vencimento).
    tem_plano = lead.id_plano_rp is not None
    tem_vencimento = lead.id_dia_vencimento is not None
    if tem_plano or tem_vencimento:
        tags.add(TAG_COMERCIAL)

    # ── ENDEREÇO ──────────────────────────────────────────────────────────
    # Critério: rua + número + bairro + cep todos preenchidos.
    # Ponto de referência é desejável mas não obrigatório para o critério.
    def preenchido(v):
        return v is not None and str(v).strip() != ''

    tem_rua = preenchido(lead.rua)
    tem_numero = preenchido(lead.numero_residencia)
    tem_bairro = preenchido(lead.bairro)
    tem_cep = preenchido(lead.cep)
    if tem_rua and tem_numero and tem_bairro and tem_cep:
        tags.add(TAG_ENDERECO)

    # ── DOCUMENTAL ────────────────────────────────────────────────────────
    # Critério principal: CPF/CNPJ preenchido.
    # Reforçado por: data de nascimento ou documentação marcada como completa.
    tem_cpf = preenchido(lead.cpf_cnpj)
    tem_nasc = lead.data_nascimento is not None
    tem_doc_completa = lead.documentacao_completa or lead.documentacao_validada
    if tem_cpf or tem_doc_completa:
        tags.add(TAG_DOCUMENTAL)
    # data_nascimento sozinha não basta (pode estar nos leads de cliente ativo)

    return tags


class Command(BaseCommand):
    help = 'Atribui tags CRM às oportunidades com base nos dados preenchidos no LeadProspecto'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula sem gravar no banco',
        )
        parser.add_argument(
            '--resetar',
            action='store_true',
            help='Remove todas as tags existentes antes de re-aplicar',
        )
        parser.add_argument(
            '--estagio',
            type=str,
            default=None,
            help='Filtra por tipo de estágio (ex: qualificacao)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        resetar = options['resetar']
        filtro_estagio = options.get('estagio')

        # ── Garantir que as tags existam ──────────────────────────────────
        tags_definidas = {
            TAG_COMERCIAL:  '#667eea',
            TAG_ENDERECO:   '#f39c12',
            TAG_DOCUMENTAL: '#0ea5e9',
        }
        obj_tags = {}
        for nome, cor in tags_definidas.items():
            tag, criado = TagCRM.objects.get_or_create(
                nome=nome,
                defaults={'cor_hex': cor},
            )
            obj_tags[nome] = tag
            if criado:
                self.stdout.write(self.style.SUCCESS(f'  Tag criada: {nome}'))

        # ── Montar queryset de oportunidades ──────────────────────────────
        qs = OportunidadeVenda.objects.select_related(
            'lead', 'estagio'
        ).filter(ativo=True)

        if filtro_estagio:
            qs = qs.filter(estagio__tipo=filtro_estagio)
            self.stdout.write(f'Filtrando por estágio tipo="{filtro_estagio}"')

        total = qs.count()
        self.stdout.write(f'\nAnalisando {total} oportunidades...')
        if dry_run:
            self.stdout.write(self.style.WARNING('  [DRY-RUN] nenhuma alteração será salva\n'))

        # ── Contadores ────────────────────────────────────────────────────
        cnt = {
            'com_comercial': 0,
            'com_endereco': 0,
            'com_documental': 0,
            'nenhuma_tag': 0,
            'todas_tags': 0,
            'adicionadas': 0,
            'removidas': 0,
        }

        for opv in qs.prefetch_related('tags'):
            lead = opv.lead
            tags_devidas = _campos_preenchidos(lead)

            tags_atuais = set(opv.tags.values_list('nome', flat=True))

            if resetar and not dry_run:
                # Remove apenas as 3 tags gerenciadas (não toca em outras)
                opv.tags.remove(*[obj_tags[n] for n in tags_definidas if n in tags_atuais])
                tags_atuais = tags_atuais - set(tags_definidas.keys())

            tags_para_add = tags_devidas - tags_atuais
            tags_para_rem = (tags_atuais & set(tags_definidas.keys())) - tags_devidas

            if not dry_run:
                if tags_para_add:
                    opv.tags.add(*[obj_tags[n] for n in tags_para_add])
                if tags_para_rem:
                    opv.tags.remove(*[obj_tags[n] for n in tags_para_rem])

            cnt['adicionadas'] += len(tags_para_add)
            cnt['removidas'] += len(tags_para_rem)

            # Contagem por tag
            tags_final = tags_devidas  # o que deveria ter
            if TAG_COMERCIAL in tags_final:
                cnt['com_comercial'] += 1
            if TAG_ENDERECO in tags_final:
                cnt['com_endereco'] += 1
            if TAG_DOCUMENTAL in tags_final:
                cnt['com_documental'] += 1
            if not tags_final:
                cnt['nenhuma_tag'] += 1
            if len(tags_final) == 3:
                cnt['todas_tags'] += 1

            # Verbose: leads que mudaram
            if (tags_para_add or tags_para_rem) and dry_run:
                self.stdout.write(
                    f'  #{opv.pk} {lead.nome_razaosocial[:30]:30s} '
                    f'[+{",".join(tags_para_add) or "-"}] '
                    f'[-{",".join(tags_para_rem) or "-"}]'
                )

        # ── Relatório final ───────────────────────────────────────────────
        self.stdout.write('\n' + '─' * 55)
        self.stdout.write(self.style.SUCCESS('RESULTADO'))
        self.stdout.write(f'  Total analisado :  {total}')
        self.stdout.write(f'  Tags adicionadas:  {cnt["adicionadas"]}')
        self.stdout.write(f'  Tags removidas  :  {cnt["removidas"]}')
        self.stdout.write('')
        self.stdout.write('  Distribuição por tag (total de leads com cada):')
        self.stdout.write(f'    🔵 Comercial   (plano escolhido)   : {cnt["com_comercial"]:>4}')
        self.stdout.write(f'    🟠 Endereço    (endereço completo) : {cnt["com_endereco"]:>4}')
        self.stdout.write(f'    🔷 Documental  (CPF preenchido)    : {cnt["com_documental"]:>4}')
        self.stdout.write(f'    ⚪ Sem nenhuma tag                 : {cnt["nenhuma_tag"]:>4}')
        self.stdout.write(f'    ✅ Com as 3 tags                   : {cnt["todas_tags"]:>4}')
        self.stdout.write('─' * 55)

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY-RUN] Nenhuma tag foi salva.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nTagging concluído com sucesso.'))
