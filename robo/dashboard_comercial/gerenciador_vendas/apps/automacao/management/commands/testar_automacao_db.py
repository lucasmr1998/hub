"""
Smoke test da CAMADA DE BANCO da automação (Fluxo/ExecucaoFluxo, persistência,
conversa pausa→resposta→retoma).

Por que um command e não pytest: o DB de teste do projeto não cria localmente
(a extensão `pgvector` do app `suporte` não está instalada, e o `inbox` tem FK
pra `suporte.Ticket`). Este command roda contra o banco de dev (`aurora_dev`),
é **não-destrutivo** (cria temporários e limpa) e sai com código != 0 se algo
falhar (CI-friendly).

    python manage.py testar_automacao_db --settings=gerenciador_vendas.settings_local
"""
from unittest import mock

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Smoke test da camada de banco da automação (não-destrutivo).'

    def handle(self, *args, **options):
        from apps.sistema.models import Tenant
        from apps.automacao.models import Fluxo, ExecucaoFluxo
        from apps.automacao.nodes import Contexto
        from apps.automacao.services.whatsapp import chave_telefone
        from apps.automacao.execucao import executar_e_persistir, retomar_por_resposta

        falhas = []

        def check(cond, nome):
            self.stdout.write(
                (self.style.SUCCESS('PASS') if cond else self.style.ERROR('FAIL')) + ' ' + nome
            )
            if not cond:
                falhas.append(nome)

        tenant = Tenant.objects.filter(ativo=True).first()
        if tenant is None:
            raise CommandError('Sem tenant ativo no banco.')

        # 1) Fluxo simples persiste e completa.
        g1 = {'inicio': 'a', 'nodes': {
            'a': {'tipo': 'set_fields', 'config': {'campo': 'r', 'valor': '{{var.n}}'}}}, 'conexoes': []}
        f1 = Fluxo.objects.create(tenant=tenant, nome='_test_db simples', grafo=g1)
        try:
            ex1, res1 = executar_e_persistir(f1, Contexto(tenant=tenant, variaveis={'n': 'X'}))
            check(res1.status == 'completado', 'fluxo simples completa')
            check(ExecucaoFluxo.all_tenants.filter(pk=ex1.pk).exists(), 'execucao persistida')
        finally:
            ExecucaoFluxo.all_tenants.filter(fluxo=f1).delete()
            f1.delete()

        # 2) Conversa: pausa na resposta → retoma quando o contato responde.
        g2 = {'inicio': 'p', 'nodes': {
            'p': {'tipo': 'whatsapp_pergunta',
                  'config': {'telefone': '5589999', 'mensagem': '?', 'timeout_min': 0}},
            'g': {'tipo': 'set_fields', 'config': {'campo': 'resp', 'valor': '{{var.resposta}}'}},
        }, 'conexoes': [{'de': 'p', 'para': 'g', 'saida': 'resposta'}]}
        f2 = Fluxo.objects.create(tenant=tenant, nome='_test_db conversa', grafo=g2)
        try:
            with mock.patch('apps.automacao.nodes.whatsapp.uazapi_do_tenant', return_value=mock.Mock()):
                ex2, res2 = executar_e_persistir(f2, Contexto(tenant=tenant, variaveis={}))
                check(res2.status == 'aguardando' and ex2.modo_espera == 'resposta',
                      'conversa pausa esperando resposta')
                ok = retomar_por_resposta(tenant, chave_telefone('5589999'), 'Joao')
                ex2.refresh_from_db()
                check(bool(ok) and ex2.status == 'completado', 'conversa retoma na resposta')
                check([p['handle'] for p in ex2.trace] == ['p', 'g'], 'trace correto (p -> g)')
        finally:
            ExecucaoFluxo.all_tenants.filter(fluxo=f2).delete()
            f2.delete()

        if falhas:
            raise CommandError(f'{len(falhas)} checagem(ns) falharam: {", ".join(falhas)}')
        self.stdout.write(self.style.SUCCESS('OK — todos os checks da camada de banco passaram.'))
