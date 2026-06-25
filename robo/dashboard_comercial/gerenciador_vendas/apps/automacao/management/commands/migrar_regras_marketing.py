"""Traduz RegraAutomacao (motor antigo de marketing) → Fluxo (engine nova).

Dry-run por padrão (só simula e valida); `--salvar` cria os Fluxos (inativos — o
cutover liga depois). Filtros: `--tenant <slug>`, `--regra <id>`.
"""
from django.core.management.base import BaseCommand

from apps.automacao.migracao_marketing import traduzir_regra
from apps.automacao.runtime import validar_fluxo


class Command(BaseCommand):
    help = 'Traduz regras de automação do marketing para Fluxos da engine nova (dry-run por padrão).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', help='slug do tenant (vazio = todos)')
        parser.add_argument('--regra', type=int, help='id de uma regra específica')
        parser.add_argument('--salvar', action='store_true', help='cria os Fluxos (default: só simula)')

    def handle(self, *args, **opts):
        from apps.marketing.automacoes.models import RegraAutomacao
        from apps.automacao.models import Fluxo

        qs = RegraAutomacao.all_tenants.filter(ativa=True).select_related('tenant')
        if opts.get('tenant'):
            qs = qs.filter(tenant__slug=opts['tenant'])
        if opts.get('regra'):
            qs = qs.filter(id=opts['regra'])

        salvar = opts.get('salvar')
        total = validos = com_aviso = criados = 0

        for regra in qs:
            total += 1
            try:
                grafo, avisos = traduzir_regra(regra)
            except Exception as e:  # noqa: BLE001
                self.stdout.write(self.style.ERROR(f'  regra {regra.id} "{regra.nome}": ERRO ao traduzir: {e}'))
                continue

            erros = validar_fluxo(grafo)
            marca = self.style.SUCCESS('OK') if not erros else self.style.ERROR('INVÁLIDO')
            modo = 'visual' if regra.modo_fluxo else 'linear'
            self.stdout.write(
                f'[{regra.tenant.slug}] regra {regra.id} "{regra.nome}" ({modo}) → {marca} '
                f'| nós={len(grafo.get("nodes") or {})} conexões={len(grafo.get("conexoes") or [])}'
            )
            for a in avisos:
                self.stdout.write(self.style.WARNING(f'    aviso: {a}'))
            if avisos:
                com_aviso += 1
            if erros:
                for e in erros:
                    self.stdout.write(self.style.ERROR(f'    erro estrutural: {e}'))
                continue

            validos += 1
            if salvar:
                nome = f'[migrado] {regra.nome}'[:200]
                f = Fluxo.all_tenants.filter(tenant=regra.tenant, origem_regra=regra.id).first()
                if f:  # idempotente: re-rodar atualiza o grafo, sem mexer no ativo
                    f.nome, f.grafo = nome, grafo
                    f.save()
                    self.stdout.write(self.style.SUCCESS(f'    → Fluxo {f.id} atualizado'))
                else:
                    f = Fluxo.objects.create(
                        tenant=regra.tenant, nome=nome, grafo=grafo,
                        ativo=False,  # nasce inativo; o cutover liga
                        origem_regra=regra.id,
                    )
                    criados += 1
                    self.stdout.write(self.style.SUCCESS(f'    → Fluxo {f.id} criado (inativo)'))

        self.stdout.write('')
        resumo = f'total={total} válidos={validos} com_aviso={com_aviso}'
        resumo += f' criados={criados}' if salvar else '  (dry-run — use --salvar pra criar)'
        self.stdout.write(self.style.HTTP_INFO(resumo))
