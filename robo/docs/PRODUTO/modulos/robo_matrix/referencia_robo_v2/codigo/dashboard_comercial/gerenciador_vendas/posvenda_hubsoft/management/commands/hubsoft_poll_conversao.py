"""Worker: converte PROSPECTOS pendentes do robô v2 em clientes via API interna.

Mira nos LEADS do próprio projeto (não num vendedor específico): pega leads que já
viraram prospecto no HubSoft (id_hubsoft preenchido) e ainda NÃO são clientes, e
roda a conversão via API (ExecutorApiConversao → POST /api/v1/cliente + id_prospecto).
Os prospectos do v2 nascem com vendedor 1613 (separado do gestao_leads_bot, que só
converte os do 1618), então não há conflito.

Idempotência: pula leads já convertidos por nós (ExecucaoHubsoft conversao=sucesso),
já com ClienteHubsoft local, ou cujo prospecto já tem id_cliente no HubSoft; e
desiste após 3 falhas. Advisory lock 947_312_007.

    manage.py hubsoft_poll_conversao --intervalo 45 --batch 2 [--dry-run] [--once]
"""
import signal
import time
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import connection

from posvenda_hubsoft.executores.seletor import processar

ADVISORY_LOCK = 947_312_007
MAX_FALHAS = 3


class Command(BaseCommand):
    help = 'Worker de conversão prospecto→cliente via API interna (robô v2)'

    def add_arguments(self, parser):
        parser.add_argument('--intervalo', type=int, default=45)
        parser.add_argument('--batch', type=int, default=2)
        parser.add_argument('--dry-run', dest='dry_run', action='store_true')
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **o):
        self._parar = False
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, '_parar', True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, '_parar', True))
        self.stdout.write(self.style.SUCCESS(
            f'[conversao] worker iniciado (batch={o["batch"]} dry_run={o["dry_run"]})'))
        while not self._parar:
            try:
                n = self._ciclo(o['batch'], o['dry_run'])
                if n:
                    self.stdout.write(f'[conversao] ciclo processou {n}')
            except Exception as e:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f'[conversao] erro no ciclo: {e}'))
                # Conexão de DB pode ter morrido (queda de rede/restart do
                # Postgres). Fecha TODAS — o Django reabre na próxima query.
                # Sem isso o worker fica preso em "connection already closed".
                try:
                    from django.db import connections
                    connections.close_all()
                except Exception:  # noqa: BLE001
                    pass
            if o['once']:
                break
            for _ in range(o['intervalo']):
                if self._parar:
                    break
                time.sleep(1)
        self.stdout.write('[conversao] worker encerrado')

    def _ciclo(self, batch, dry_run):
        from vendas_web.models import LeadProspecto
        from integracoes.models import ClienteHubsoft
        from posvenda_hubsoft.models import ExecucaoHubsoft

        with connection.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(%s)', [ADVISORY_LOCK])
            if not cur.fetchone()[0]:
                return 0
        try:
            ja_ok = set(ExecucaoHubsoft.objects.filter(
                processo='conversao', status='sucesso').values_list('registro_id', flat=True))
            ja_cliente = set(ClienteHubsoft.objects.exclude(
                lead_id__isnull=True).values_list('lead_id', flat=True))
            falhas = Counter(ExecucaoHubsoft.objects.filter(
                processo='conversao', status='falha').values_list('registro_id', flat=True))

            # leads que viraram prospecto (id_hubsoft) e ainda não são clientes
            cands = (LeadProspecto.objects
                     .exclude(id_hubsoft__isnull=True).exclude(id_hubsoft='')
                     .exclude(pk__in=ja_ok).exclude(pk__in=ja_cliente)
                     .order_by('id').values_list('id', 'id_hubsoft'))
            por_prospecto = {}
            for lid, idh in cands:
                if falhas.get(lid, 0) >= MAX_FALHAS:
                    continue
                try:
                    por_prospecto[int(idh)] = lid
                except (TypeError, ValueError):
                    continue
            if not por_prospecto:
                return 0

            # mantém só os cujo prospecto AINDA não tem id_cliente (não convertido)
            nao_conv = self._prospectos_nao_convertidos(list(por_prospecto.keys()))
            fila = [por_prospecto[p] for p in nao_conv][:batch]
            for lead_id in fila:
                if self._parar:
                    break
                self._processar_um(lead_id, dry_run)
            return len(fila)
        finally:
            with connection.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(%s)', [ADVISORY_LOCK])

    def _prospectos_nao_convertidos(self, ids):
        from posvenda_hubsoft.services.ambiente import preparar_ambiente_webdriver
        preparar_ambiente_webdriver()
        from posvenda_hubsoft.webdriver.main_novo_servico import _conn
        c = _conn('HUBSOFT'); cur = c.cursor()
        cur.execute('SELECT id_prospecto FROM prospecto '
                    'WHERE id_prospecto = ANY(%s) AND id_cliente IS NULL', [ids])
        r = [x[0] for x in cur.fetchall()]
        c.close()
        return r

    def _processar_um(self, lead_id, dry_run):
        res = processar('conversao', lead_id, dry_run=dry_run)
        self.stdout.write(
            f'[conversao] lead={lead_id} → {res.status} ({res.executor}, '
            f'{res.duracao_ms}ms) {(res.erro or "")[:80]}')
        if not dry_run and getattr(res, 'status', None) == 'sucesso':
            try:
                from vendas_web.models import LeadProspecto
                from integracoes.services.clube_indicacoes import notificar_clube_conversao_indicacao
                lead = LeadProspecto.objects.get(pk=lead_id)
                notificar_clube_conversao_indicacao(lead, valor_venda=getattr(lead, 'valor', None))
            except Exception as exc:
                self.stderr.write(self.style.WARNING(
                    f'[conversao] lead={lead_id} convertido, mas Clube não notificado: {exc}'
                ))
            # Docs → contrato: agora que o cliente EXISTE no HubSoft, anexa os
            # documentos validados ao contrato e marca o aceite (o signal na
            # validação dos docs roda cedo demais — sem cliente ainda).
            try:
                from vendas_web.models import LeadProspecto
                from vendas_web.services.contrato_service import tentar_aceite_pos_conversao
                tentar_aceite_pos_conversao(LeadProspecto.objects.get(pk=lead_id))
            except Exception as exc:
                self.stderr.write(self.style.WARNING(
                    f'[conversao] lead={lead_id} convertido, mas aceite/anexos falharam: {exc}'
                ))
