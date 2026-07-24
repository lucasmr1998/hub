"""Roda um fluxo da engine para UM lead especifico (teste/homologacao manual).

O gatilho (agenda/evento) so serve pra AGENDAR execucoes em producao; aqui a gente
pula isso e injeta o lead direto no Contexto, rodando o grafo do inicio. Util pra
testar os fluxos de escrita HubSoft com os dados que voce quer, sem esperar a
varredura nem mexer no gatilho.

O grafo roda de verdade: nos que escrevem (ex: sincronizar prospecto) escrevem
mesmo. Os nos de conversao/servico respeitam o guard de dry run do perfil. Por
padrao NAO persiste ExecucaoFluxo (--persistir liga).

Uso:
    python manage.py automacao_rodar_fluxo --tenant demo-local --fluxo 2 --lead 3 \\
        --settings=gerenciador_vendas.settings_local
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Roda um fluxo para um lead especifico (teste manual), imprimindo o trace.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--fluxo', required=True, help='id (int) ou nome exato do fluxo.')
        parser.add_argument('--lead', required=True, type=int, help='pk do LeadProspecto.')

    def handle(self, *args, **o):
        from apps.sistema.models import Tenant
        from apps.automacao.models import Fluxo
        from apps.automacao.runtime import executar_fluxo
        from apps.automacao.nodes.context import Contexto
        from apps.comercial.leads.models import LeadProspecto

        tenant = Tenant.objects.filter(slug=(o['tenant'] or '').strip()).first()
        if tenant is None:
            raise CommandError(f"Tenant '{o['tenant']}' nao encontrado.")

        ref = str(o['fluxo']).strip()
        qs = Fluxo.all_tenants.filter(tenant=tenant)
        fluxo = qs.filter(pk=int(ref)).first() if ref.isdigit() else qs.filter(nome=ref).first()
        if fluxo is None:
            raise CommandError(f"Fluxo '{ref}' nao encontrado no tenant {tenant.slug}.")

        lead = LeadProspecto.all_tenants.filter(tenant=tenant, pk=o['lead']).first()
        if lead is None:
            raise CommandError(f"Lead pk={o['lead']} nao encontrado no tenant {tenant.slug}.")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Rodando "{fluxo.nome}" (id={fluxo.pk}) para lead {lead.pk} '
            f'"{lead.nome_razaosocial}" | id_hubsoft={lead.id_hubsoft!r}'))

        contexto = Contexto(tenant=tenant, lead=lead)
        resultado = executar_fluxo(fluxo.grafo, contexto)

        self.stdout.write(f'  status geral: {resultado.status}'
                          + (f' | erro: {resultado.erro}' if resultado.erro else ''))
        self.stdout.write('  --- passos ---')
        for p in resultado.passos:
            linha = f'    {p.handle} [{p.tipo}] -> {p.branch or p.status}'
            if p.erro:
                linha += f'  ERRO: {p.erro}'
            self.stdout.write(linha)

        # Mostra o output do no de acao (payload/resumo em dry run), se houver
        interessantes = {h: v for h, v in (contexto.nodes or {}).items()
                         if isinstance(v, dict) and ('resumo' in v or 'payload' in v or 'id_prospecto' in v)}
        if interessantes:
            self.stdout.write('  --- outputs relevantes ---')
            self.stdout.write('  ' + json.dumps(interessantes, ensure_ascii=False, default=str)[:2000])

        # relembra o estado do lead apos rodar (ex: id_hubsoft preenchido)
        lead.refresh_from_db()
        self.stdout.write(f'  lead apos: id_hubsoft={lead.id_hubsoft!r} | status_api={lead.status_api!r}')
