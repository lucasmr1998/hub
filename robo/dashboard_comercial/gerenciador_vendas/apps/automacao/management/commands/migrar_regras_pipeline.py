"""Traduz as RegraPipelineEstagio (motor antigo do funil) em Fluxos da engine nova.

Migração da automação do funil (Fase 2, Passo 1). Idempotente: cada regra vira um
Fluxo com `origem_regra = regra.pk`; re-rodar atualiza o grafo em vez de duplicar.
Cria os Fluxos INATIVOS por padrão (shadow) — não ligam nada em produção. NÃO toca
no motor antigo (só LÊ as regras).

Uso:
    # prévia sem escrever (read-only) — mostra cada regra → fluxo:
    python manage.py migrar_regras_pipeline --dry-run
    python manage.py migrar_regras_pipeline --dry-run --tenant nuvyon

    # escreve os fluxos (inativos):
    python manage.py migrar_regras_pipeline --tenant nuvyon

    # escreve já ativos (NÃO recomendado antes do shadow):
    python manage.py migrar_regras_pipeline --tenant nuvyon --ativar
"""
from django.core.management.base import BaseCommand

from apps.automacao.tradutor_pipeline import (
    regra_para_grafo, descricao_da_regra, regra_traduzivel,
)


class Command(BaseCommand):
    help = 'Traduz RegraPipelineEstagio em Fluxos da engine nova (idempotente, inativos).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='', help='Slug do tenant (vazio = todos).')
        parser.add_argument('--dry-run', action='store_true', help='Não escreve; só mostra.')
        parser.add_argument('--ativar', action='store_true',
                            help='Cria os fluxos já ativos (padrão: inativos/shadow).')

    def handle(self, *args, **opts):
        from apps.comercial.crm.models import RegraPipelineEstagio
        from apps.automacao.models import Fluxo

        tenant_slug = (opts.get('tenant') or '').strip()
        dry = opts.get('dry_run')
        ativar = opts.get('ativar')

        regras = (RegraPipelineEstagio.all_tenants
                  .filter(ativo=True)
                  .select_related('estagio', 'tenant')
                  .order_by('tenant__slug', 'estagio__ordem', 'prioridade'))
        if tenant_slug:
            regras = regras.filter(tenant__slug=tenant_slug)

        criados = atualizados = pulados = 0
        tenant_atual = None
        total = regras.count()
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Traduzindo {total} regra(s) ativa(s){" do tenant " + tenant_slug if tenant_slug else ""} '
            f'{"[DRY-RUN, nada escrito]" if dry else ("[criando ATIVOS]" if ativar else "[criando inativos/shadow]")}'))

        for regra in regras:
            slug = regra.tenant.slug if regra.tenant else '?'
            if slug != tenant_atual:
                tenant_atual = slug
                self.stdout.write(f'\n== tenant: {slug} ==')

            ok, motivo = regra_traduzivel(regra)
            if not ok:
                pulados += 1
                self.stdout.write(f'  - PULADA regra #{regra.pk} "{regra.nome}": {motivo}')
                continue

            grafo = regra_para_grafo(regra)
            n_cond = len(regra.condicoes or [])
            if regra.estagio_id:
                alvo = f'mover → {regra.estagio.nome}'
            else:
                alvo = 'ações: ' + ', '.join((a.get('tipo') or '?') for a in (regra.acoes or []))
            self.stdout.write(
                f'  • regra #{regra.pk} "{regra.nome}" → fluxo [{n_cond} cond] {alvo}')

            if dry:
                continue

            existente = Fluxo.all_tenants.filter(tenant=regra.tenant, origem_regra=regra.pk).first()
            nome = f'[Funil] {regra.nome}'[:200]
            descricao = descricao_da_regra(regra)
            if existente:
                existente.nome = nome
                existente.descricao = descricao
                existente.grafo = grafo
                # respeita o estado atual do fluxo; só força ativo quando --ativar explícito
                if ativar:
                    existente.ativo = True
                existente.save()
                atualizados += 1
            else:
                Fluxo.all_tenants.create(
                    tenant=regra.tenant, nome=nome, descricao=descricao,
                    grafo=grafo, origem_regra=regra.pk, ativo=bool(ativar),
                )
                criados += 1

        self.stdout.write('')
        resumo = f'Feito. Criados: {criados} · Atualizados: {atualizados} · Pulados: {pulados}'
        self.stdout.write(self.style.SUCCESS(resumo) if not dry
                          else self.style.WARNING(resumo + ' (dry-run: nada escrito)'))
