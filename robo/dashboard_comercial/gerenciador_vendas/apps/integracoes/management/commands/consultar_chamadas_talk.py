"""Consulta as chamadas de um telefone no Talk. READ-ONLY (so GET na API deles).

Existe por um caso concreto: 7 oportunidades vindas do Talk ficaram sem
vendedora porque o `sync_vendedores_matrix` nao acha "chamada atendida com
agente" pro telefone. Mas se o lead nasceu de um PROSPECT do Talk, alguem
ligou — entao a chamada tem que existir, e a suspeita e a BUSCA (formato do
numero ou data), nao a ausencia de ligacao.

O comando mostra a resposta CRUA da API e testa variacoes do numero (com e sem
o 9o digito, com DDI), pra separar "nao existe chamada" de "existe mas a gente
procura errado".

Uso:
    python manage.py consultar_chamadas_talk --tenant nuvyon --telefone 19996879015
    python manage.py consultar_chamadas_talk --tenant nuvyon --telefone 19996879015 --data 2026-07-13
    python manage.py consultar_chamadas_talk --tenant nuvyon --oportunidade 2536
"""
import json

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.integracoes.models import IntegracaoAPI
from apps.integracoes.services.talk import TalkService, TalkServiceError
from apps.sistema.models import Tenant


def _digitos(s):
    return ''.join(c for c in str(s or '') if c.isdigit())


def _variacoes(tel: str) -> list[tuple[str, str]]:
    """Formatos plausiveis do mesmo numero. O Talk pode indexar de um jeito so."""
    d = _digitos(tel)
    if len(d) > 11:
        d = d[-11:]  # tira DDI
    vars_ = [('como esta (11 digitos)', d)]
    if len(d) == 11 and d[2] == '9':
        vars_.append(('sem o 9o digito (10)', d[:2] + d[3:]))
    if len(d) == 10:
        vars_.append(('com o 9o digito (11)', d[:2] + '9' + d[2:]))
    vars_.append(('com DDI 55', '55' + d))
    return vars_


class Command(BaseCommand):
    help = 'Lista as chamadas de um telefone no Talk (diagnostico, read-only).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True)
        parser.add_argument('--telefone', default=None, help='So digitos (ex: 19996879015)')
        parser.add_argument('--oportunidade', type=int, default=None,
                            help='Pega o telefone e a data direto da oportunidade.')
        parser.add_argument('--data', default=None, help='YYYY-MM-DD (default: hoje ou a da op)')
        parser.add_argument('--dias', type=int, default=1,
                            help='Alem da data, procura tambem nos N dias ANTERIORES.')

    def handle(self, *args, **opts):
        from apps.comercial.crm.models import OportunidadeVenda
        from datetime import timedelta

        try:
            tenant = Tenant.objects.get(slug=opts['tenant'], ativo=True)
        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Tenant {opts['tenant']!r} nao encontrado."))
            return

        integ = IntegracaoAPI.all_tenants.filter(tenant=tenant, tipo='talk', ativa=True).first()
        if not integ:
            self.stdout.write(self.style.ERROR('Tenant sem IntegracaoAPI talk ativa.'))
            return

        telefone = opts['telefone']
        data_base = opts['data']

        if opts['oportunidade']:
            op = (OportunidadeVenda.all_tenants
                  .filter(tenant=tenant, pk=opts['oportunidade'])
                  .select_related('lead').first())
            if not op or not op.lead:
                self.stdout.write(self.style.ERROR('Oportunidade nao encontrada (ou sem lead).'))
                return
            telefone = telefone or op.lead.telefone
            if not data_base:
                iso = (op.lead.dados_custom or {}).get('talk_created_at')
                if iso:
                    from datetime import datetime
                    dt = datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
                    data_base = timezone.localtime(dt).date().isoformat()
                else:
                    data_base = timezone.localtime(op.data_criacao).date().isoformat()
            self.stdout.write(f'  oportunidade #{op.pk} | lead #{op.lead.pk} | criada '
                              f'{timezone.localtime(op.data_criacao):%d/%m/%Y %H:%M}')

        if not telefone:
            self.stdout.write(self.style.ERROR('Informe --telefone ou --oportunidade.'))
            return
        if not data_base:
            data_base = timezone.localtime().date().isoformat()

        svc = TalkService(integ)
        from datetime import date
        d0 = date.fromisoformat(data_base)
        datas = [(d0 - timedelta(days=i)).isoformat() for i in range(max(1, opts['dias']))]

        self.stdout.write(f"\n  telefone: {_digitos(telefone)}  |  datas: {datas}\n")

        achou_algo = False
        for rotulo, num in _variacoes(telefone):
            for dia in datas:
                try:
                    chamadas = svc.listar_chamadas_por_telefone(num, dia)
                except TalkServiceError as exc:
                    self.stdout.write(self.style.ERROR(f'  [{rotulo}] {dia}: ERRO {exc}'))
                    continue

                if not chamadas:
                    self.stdout.write(f'  [{rotulo:<22}] {dia}: nenhuma chamada')
                    continue

                achou_algo = True
                self.stdout.write(self.style.SUCCESS(
                    f'  [{rotulo:<22}] {dia}: {len(chamadas)} chamada(s)'
                ))
                for ch in chamadas:
                    self.stdout.write(
                        f"      resposta={ch.get('nom_resposta')!r} "
                        f"agente={ch.get('nom_agente')!r} "
                        f"cod_agente={ch.get('cod_agente')!r} "
                        f"quando={ch.get('dat_ligacao')!r} "
                        f"tipo={ch.get('nom_tipo') or ch.get('tipo')!r}"
                    )
                    self.stdout.write(f'      cru: {json.dumps(ch, ensure_ascii=False)[:220]}')

        self.stdout.write('')
        if not achou_algo:
            self.stdout.write(self.style.WARNING(
                '  O Talk nao devolveu chamada NENHUMA, em nenhum formato de numero nem data.\n'
                '  Ou a ligacao nao existe la, ou o endpoint de rastreabilidade nao a enxerga.'
            ))
