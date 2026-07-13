"""Reconcilia o STATUS dos servicos do espelho HubSoft com a realidade da API.

POR QUE ESTE COMANDO EXISTE
---------------------------
O espelho local congela. O cron (`sincronizar_clientes`) consulta cada cliente
UMA unica vez, no momento em que a venda e processada, e depois o exclui das
proximas rodadas (`qs.exclude(pk__in=ids_ja_sincronizados)`). Naquele instante
o servico esta sempre "Aguardando Instalacao", porque acabou de ser vendido.
Quando o tecnico instala, o HubSoft muda e o nosso banco nao fica sabendo.

Efeito: "Instalacoes pendentes" virou um contador que so sobe, e cancelamento /
suspensao nunca aparecem. Este comando vai na API, compara e corrige.

POR QUE NAO USA O ORM `.save()`
-------------------------------
`ServicoClienteHubsoft` tem post_save conectado em DOIS lugares:
  - apps/comercial/crm/signals.py           -> roda a engine de regras do pipeline
  - apps/automacao/signals_dominio.py       -> emite evento de dominio
A engine do CRM tem acoes que ESCREVEM NO HUBSOFT (criar prospecto, gerar
contrato) e movem oportunidade de estagio. Reconciliar centenas de servicos
com `.save()` acordaria a engine uma vez por servico. Ela tem trava de
idempotencia, mas o risco nao compensa: a reconciliacao e leitura de status,
nao um evento de negocio.

Por isso a escrita e feita com `queryset.update()`, que NAO dispara signals.

USO
---
    # So relata a defasagem (nao escreve nada):
    python manage.py atualizar_status_servicos_hubsoft --tenant nuvyon --dry-run

    # Corrige o espelho (sem acordar a engine):
    python manage.py atualizar_status_servicos_hubsoft --tenant nuvyon

    # Varre a base inteira, nao so os pendentes (pega cancelado/suspenso):
    python manage.py atualizar_status_servicos_hubsoft --tenant nuvyon --escopo todos

Sem `--tenant`, processa todos os tenants com IntegracaoAPI hubsoft ativa.
"""
import logging
import time
from collections import Counter

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.integracoes.models import (
    IntegracaoAPI,
    ClienteHubsoft,
    ServicoClienteHubsoft,
)
from apps.integracoes.services.hubsoft import HubsoftService, HubsoftServiceError
from apps.sistema.models import Tenant

logger = logging.getLogger(__name__)

# Status que ficam congelados na foto da venda. Sao esses que precisam
# ser reconciliados; 'servico_habilitado' so muda em caso de churn/suspensao
# (use --escopo todos pra varrer esses tambem).
PREFIXOS_PENDENTES = (
    'aguardando_instalacao',
    'aguardando_assinatura_contrato',
    'aguardando_migracao',
)


def _aware(valor):
    if not valor:
        return None
    dt = parse_datetime(str(valor).replace(' ', 'T'))
    if dt and timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    return dt


class Command(BaseCommand):
    help = 'Reconcilia o status dos servicos do espelho HubSoft com a API (sem disparar signals).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, help='Slug do tenant (opcional).')
        parser.add_argument('--dry-run', action='store_true',
            help='So relata a defasagem. Nao escreve nada.')
        parser.add_argument('--escopo', choices=['pendentes', 'todos'], default='pendentes',
            help='pendentes (default): so servicos aguardando_*. todos: a base inteira.')
        parser.add_argument('--limite', type=int, default=None,
            help='Processa no maximo N clientes (pra teste).')
        parser.add_argument('--rate-limit', type=float, default=0.3,
            help='Pausa em segundos entre chamadas a API (default: 0.3).')

    def handle(self, *args, **opts):
        tenants_qs = Tenant.objects.filter(ativo=True)
        if opts.get('tenant'):
            tenants_qs = tenants_qs.filter(slug=opts['tenant'])

        for tenant in tenants_qs:
            integ = IntegracaoAPI.all_tenants.filter(
                tenant=tenant, tipo='hubsoft', ativa=True,
            ).first()
            if not integ:
                continue
            self._processar_tenant(tenant, integ, opts)

    def _processar_tenant(self, tenant, integ, opts):
        dry = opts['dry_run']
        svc = HubsoftService(integ)

        servicos_qs = ServicoClienteHubsoft.all_tenants.filter(tenant=tenant)
        if opts['escopo'] == 'pendentes':
            servicos_qs = servicos_qs.filter(status_prefixo__in=PREFIXOS_PENDENTES)

        ids_clientes = list(
            servicos_qs.values_list('cliente_id', flat=True).distinct()
        )
        if opts['limite']:
            ids_clientes = ids_clientes[:opts['limite']]

        modo = 'DRY-RUN (nao escreve)' if dry else 'APLICANDO'
        self.stdout.write(self.style.WARNING(
            f'[{tenant.slug}] {modo} | escopo={opts["escopo"]} | '
            f'{len(ids_clientes)} cliente(s) a consultar na API'
        ))

        transicoes = Counter()
        verificados = mudados = erros = sem_cpf = 0

        for cliente in ClienteHubsoft.all_tenants.filter(pk__in=ids_clientes).iterator():
            if not cliente.cpf_cnpj:
                sem_cpf += 1
                continue

            try:
                resposta = svc.consultar_cliente(cliente.cpf_cnpj)
            except (HubsoftServiceError, Exception) as exc:  # noqa: BLE001
                erros += 1
                logger.warning('[%s] erro ao consultar id_cliente=%s: %s',
                               tenant.slug, cliente.id_cliente, exc)
                continue
            finally:
                if opts['rate_limit']:
                    time.sleep(opts['rate_limit'])

            remotos = (resposta.get('clientes') or [{}])[0].get('servicos') or []
            por_id = {str(s.get('id_cliente_servico')): s for s in remotos}

            locais = ServicoClienteHubsoft.all_tenants.filter(
                tenant=tenant, cliente=cliente,
            )
            if opts['escopo'] == 'pendentes':
                locais = locais.filter(status_prefixo__in=PREFIXOS_PENDENTES)

            for local in locais:
                verificados += 1
                remoto = por_id.get(str(local.id_cliente_servico))
                if not remoto:
                    continue

                prefixo_novo = remoto.get('status_prefixo') or ''
                if not prefixo_novo or prefixo_novo == local.status_prefixo:
                    continue

                transicoes[f'{local.status_prefixo} -> {prefixo_novo}'] += 1
                mudados += 1

                if dry:
                    continue

                # update() no queryset: NAO dispara post_save, logo nao acorda
                # a engine de regras do CRM nem o evento de dominio. Escopo
                # minimo de campos: status e as datas que dependem dele.
                ServicoClienteHubsoft.all_tenants.filter(pk=local.pk).update(
                    status=remoto.get('status') or '',
                    status_prefixo=prefixo_novo,
                    data_habilitacao=_aware(remoto.get('data_habilitacao')),
                    data_cancelamento=_aware(remoto.get('data_cancelamento')),
                    id_motivo_cancelamento=remoto.get('id_motivo_cancelamento'),
                    motivo_cancelamento=remoto.get('motivo_cancelamento') or '',
                    dados_completos=remoto,
                )

            if not dry:
                ClienteHubsoft.all_tenants.filter(pk=cliente.pk).update(
                    ativo=bool((resposta.get('clientes') or [{}])[0].get('ativo', True)),
                    data_sync=timezone.now(),
                )

        self.stdout.write('')
        self.stdout.write(f'  servicos verificados : {verificados}')
        self.stdout.write(self.style.SUCCESS(f'  status DEFASADOS     : {mudados}'))
        self.stdout.write(f'  clientes sem cpf     : {sem_cpf}')
        self.stdout.write(f'  erros de consulta    : {erros}')
        if transicoes:
            self.stdout.write('')
            self.stdout.write('  --- transicoes encontradas ---')
            for chave, n in transicoes.most_common():
                self.stdout.write(f'    {n:>4}x  {chave}')
        self.stdout.write('')
        if dry and mudados:
            self.stdout.write(self.style.WARNING(
                f'  DRY-RUN: nada foi gravado. Rode sem --dry-run pra corrigir os {mudados}.'
            ))
