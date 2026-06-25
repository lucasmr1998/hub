"""Cutover da convergência de marketing.

Liga o `Fluxo` migrado (engine nova) e desliga a `RegraAutomacao` de origem (motor
antigo) — **atômico**, pra o evento não disparar nos dois motores. Dry-run por padrão
(lista os pares); `--ativar` executa, `--reverter` desfaz. Filtra por `--tenant`/`--fluxo`.
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Cutover: ativa o Fluxo migrado e desativa a regra antiga (atômico). Dry-run por padrão.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', help='slug do tenant')
        parser.add_argument('--fluxo', type=int, help='id de um Fluxo migrado específico')
        parser.add_argument('--ativar', action='store_true', help='executa o cutover')
        parser.add_argument('--reverter', action='store_true', help='desfaz o cutover')

    def handle(self, *args, **opts):
        from apps.automacao.models import Fluxo
        from apps.marketing.automacoes.models import RegraAutomacao

        qs = Fluxo.all_tenants.filter(origem_regra__isnull=False).select_related('tenant')
        if opts.get('tenant'):
            qs = qs.filter(tenant__slug=opts['tenant'])
        if opts.get('fluxo'):
            qs = qs.filter(id=opts['fluxo'])

        ativar, reverter = opts.get('ativar'), opts.get('reverter')
        aplicados = 0
        for f in qs:
            regra = RegraAutomacao.all_tenants.filter(id=f.origem_regra).first()
            estado_regra = f'regra {regra.id} ativa={regra.ativa}' if regra else 'regra de origem SUMIU'
            self.stdout.write(f'[{f.tenant.slug}] Fluxo {f.id} "{f.nome}" (ativo={f.ativo}) ⇄ {estado_regra}')
            if not (ativar or reverter):
                continue  # dry-run

            with transaction.atomic():
                if ativar:
                    if not f.ativo:
                        f.ativo = True
                        f.save(update_fields=['ativo', 'atualizado_em'])
                    if regra and regra.ativa:
                        regra.ativa = False
                        regra.save(update_fields=['ativa'])
                    self.stdout.write(self.style.SUCCESS('    → fluxo LIGADO, regra antiga DESLIGADA'))
                else:  # reverter
                    if f.ativo:
                        f.ativo = False
                        f.save(update_fields=['ativo', 'atualizado_em'])
                    if regra and not regra.ativa:
                        regra.ativa = True
                        regra.save(update_fields=['ativa'])
                    self.stdout.write(self.style.WARNING('    → fluxo DESLIGADO, regra antiga RELIGADA'))
            aplicados += 1

        modo = 'cutover' if ativar else ('reversão' if reverter else 'dry-run')
        self.stdout.write('')
        sufixo = f', {aplicados} aplicado(s)' if (ativar or reverter) else '  (use --ativar pra executar)'
        self.stdout.write(self.style.HTTP_INFO(f'{modo}: {qs.count()} fluxo(s) migrado(s){sufixo}'))
