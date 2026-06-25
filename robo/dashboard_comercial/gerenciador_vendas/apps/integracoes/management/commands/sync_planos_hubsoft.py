"""
Sincroniza catalogo de planos do HubSoft pra ProdutoServico do CRM.

Pra cada IntegracaoAPI hubsoft ativa:
1. Le CEPs padrao por empresa (configuracoes_extras.cep_default_por_empresa)
2. Pra cada CEP, chama GET /prospecto/create?cep= no HubSoft (retorna planos+precos)
3. UPSERT em ProdutoServico (chave: tenant + id_externo=id_servico)
4. Marca categoria='plano' e dados_erp.empresa pra filtrar na UI

Rodar:
    python manage.py sync_planos_hubsoft --tenant=nuvyon
    python manage.py sync_planos_hubsoft --tenant=nuvyon --dry-run
"""
import logging
from decimal import Decimal

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sincroniza catalogo de planos HubSoft -> ProdutoServico do CRM'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, required=True, help='Slug do tenant (ex: nuvyon)')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant
        from apps.integracoes.models import IntegracaoAPI
        from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
        from apps.comercial.crm.models import ProdutoServico

        slug = opts['tenant']
        dry = opts['dry_run']
        try:
            tenant = Tenant.objects.get(slug=slug, ativo=True)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant {slug!r} nao encontrado'))
            return

        integ = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='hubsoft', ativa=True).first()
        if not integ:
            self.stdout.write(self.style.ERROR(f'Tenant {slug} sem IntegracaoAPI hubsoft ativa'))
            return

        extras = integ.configuracoes_extras or {}
        ceps_por_empresa = extras.get('cep_default_por_empresa') or {}
        if not ceps_por_empresa:
            cep_legado = extras.get('cep_default')
            if cep_legado:
                ceps_por_empresa = {'default': cep_legado}
        if not ceps_por_empresa:
            self.stdout.write(self.style.ERROR(
                'Sem CEPs configurados em configuracoes_extras.cep_default_por_empresa'
            ))
            return

        svc = HubsoftService(integ)
        criados = 0
        atualizados = 0
        sem_mudanca = 0
        empresas_vistas = []

        for empresa, cep in ceps_por_empresa.items():
            cep_limpo = str(cep).replace('-', '').replace(' ', '').strip()
            self.stdout.write(f'\n=== Empresa {empresa!r} (CEP {cep_limpo}) ===')
            try:
                planos = svc.listar_planos_por_cep(cep_limpo)
            except HubsoftServiceError as e:
                self.stdout.write(self.style.ERROR(f'  Erro ao listar planos: {e}'))
                continue
            self.stdout.write(f'  {len(planos)} planos retornados pelo HubSoft')
            empresas_vistas.append(empresa)

            for p in planos:
                id_servico = str(p.get('id_servico') or '').strip()
                if not id_servico:
                    continue
                nome = (p.get('descricao') or p.get('nome_exibicao') or '').strip() or f'Plano {id_servico}'
                preco_raw = p.get('valor') or p.get('valor_com_pacote') or 0
                try:
                    preco = Decimal(str(preco_raw))
                except Exception:
                    preco = Decimal('0')
                velocidade_down = p.get('velocidade_download')
                velocidade_up = p.get('velocidade_upload')

                if dry:
                    self.stdout.write(f'  [DRY] {id_servico:>5} | R$ {preco:>7} | {nome}')
                    continue

                # UPSERT por (tenant, id_externo).
                #
                # IMPORTANTE: este sync NUNCA mexe no campo `ativo` — o admin
                # do tenant controla quais planos ficam ativos no CRM via UI
                # (whitelist). Sync atualiza apenas nome/preco/dados_erp.
                # Novos planos ainda nascem com ativo=False (default seguro)
                # pra que o admin decida ativar.
                produto, criado_agora = ProdutoServico.all_tenants.get_or_create(
                    tenant=tenant, id_externo=id_servico,
                    defaults={
                        'nome': nome,
                        'preco': preco,
                        'categoria': 'plano',
                        'recorrencia': 'mensal',
                        'ativo': False,
                        'dados_erp': {
                            'empresa': empresa,
                            'velocidade_download_mbps': velocidade_down,
                            'velocidade_upload_mbps': velocidade_up,
                            'id_servico_hubsoft': id_servico,
                        },
                    },
                )
                if criado_agora:
                    criados += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'  CRIADO  {id_servico:>5} | R$ {preco:>7} | {nome} (ativo=False)'
                    ))
                else:
                    mudou = False
                    if produto.nome != nome:
                        produto.nome = nome; mudou = True
                    if produto.preco != preco:
                        produto.preco = preco; mudou = True
                    # NAO mexer em produto.ativo — controlado pelo admin
                    dados = dict(produto.dados_erp or {})
                    dados.update({
                        'empresa': empresa,
                        'velocidade_download_mbps': velocidade_down,
                        'velocidade_upload_mbps': velocidade_up,
                        'id_servico_hubsoft': id_servico,
                    })
                    if dados != (produto.dados_erp or {}):
                        produto.dados_erp = dados; mudou = True
                    if produto.categoria != 'plano':
                        produto.categoria = 'plano'; mudou = True
                    if mudou:
                        produto.save()
                        atualizados += 1
                        self.stdout.write(f'  UPD     {id_servico:>5} | R$ {preco:>7} | {nome}')
                    else:
                        sem_mudanca += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Resumo: criados={criados} atualizados={atualizados} sem_mudanca={sem_mudanca} '
            f'empresas={empresas_vistas} dry={dry}'
        ))
