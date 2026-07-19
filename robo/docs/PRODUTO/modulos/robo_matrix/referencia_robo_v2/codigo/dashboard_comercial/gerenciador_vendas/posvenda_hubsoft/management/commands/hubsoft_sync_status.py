"""Worker: sincroniza o status dos clientes/serviços no HubSoft e reconcilia o CRM.

Para clientes com oportunidade ainda ABERTA (aquisição não em Cliente Ativo/Perdido,
ou novo serviço não em Serviço Ativo/Falha), re-puxa o cliente do HubSoft. Isso
atualiza ServicoClienteHubsoft.status_prefixo → o signal move a aquisição para
"Cliente Ativo" quando o serviço fica 'servico_habilitado'. Em seguida roda a
reconciliação pós-venda (move o novo serviço para "Serviço Ativo").

    manage.py hubsoft_sync_status --intervalo 120 [--once]
"""
import signal
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sincroniza status HubSoft de clientes com oportunidade aberta + reconcilia CRM'

    def add_arguments(self, parser):
        parser.add_argument('--intervalo', type=int, default=120)
        parser.add_argument('--once', action='store_true')

    def handle(self, *args, **o):
        self._stop = False
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, '_stop', True))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, '_stop', True))
        self.stdout.write(self.style.SUCCESS(
            f'[sync_status] worker iniciado (intervalo={o["intervalo"]}s)'))
        while not self._stop:
            try:
                self._ciclo()
            except Exception as e:  # noqa: BLE001
                self.stderr.write(self.style.ERROR(f'[sync_status] erro: {e}'))
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
                if self._stop:
                    break
                time.sleep(1)
        self.stdout.write('[sync_status] worker encerrado')

    def _ciclo(self):
        from vendas_web.models import LeadProspecto
        from integracoes.models import (IntegracaoAPI, ClienteHubsoft,
                                         AgendamentoInstalacaoIA)
        from integracoes.services.hubsoft import HubsoftService
        from crm.models import OportunidadeVenda

        # leads-cliente com oportunidade ainda aberta (que ainda podem mover)
        abertas_aquis = OportunidadeVenda.objects.filter(
            tipo='aquisicao', ativo=True).exclude(
            estagio__slug__in=['ativo', 'perdido']).values_list('lead_id', flat=True)
        abertas_ns = OportunidadeVenda.objects.filter(
            tipo='novo_servico', ativo=True).exclude(
            estagio__slug__in=['ns_ativo', 'ns_falha']).values_list('lead_id', flat=True)
        abertas_ind = OportunidadeVenda.objects.filter(
            tipo='indicacao', ativo=True).exclude(
            estagio__slug__in=['ind_concluido', 'ind_perdido']).values_list('lead_id', flat=True)
        com_oport = set(abertas_aquis) | set(abertas_ns) | set(abertas_ind)
        # status só faz sentido p/ quem JÁ tem cliente no HubSoft
        com_cliente = com_oport & set(ClienteHubsoft.objects.filter(
            lead_id__in=com_oport).values_list('lead_id', flat=True))

        # leads com agendamento AGUARDANDO SYNC — precisam do sync INICIAL (criar o
        # ClienteHubsoft a partir do CPF) p/ que a OS de instalação possa ser aberta.
        ag_pendentes = set(AgendamentoInstalacaoIA.objects.filter(
            status='aguardando_sync').values_list('lead_id', flat=True))

        lead_ids = com_cliente | ag_pendentes
        if not lead_ids:
            return

        integ = IntegracaoAPI.objects.filter(tipo='hubsoft', ativa=True).first()
        if not integ:
            return
        svc = HubsoftService(integ)
        for lid in lead_ids:
            if self._stop:
                break
            lead = LeadProspecto.objects.filter(pk=lid).first()
            if lead:
                try:
                    svc.sincronizar_cliente(lead)   # cria/atualiza ClienteHubsoft + ServicoClienteHubsoft
                except Exception as e:  # noqa: BLE001
                    self.stderr.write(f'[sync_status] sync lead {lid} falhou: {e}')

        # agendamentos pendentes: agora que o cliente foi sincronizado, abre a O.S.
        if ag_pendentes:
            try:
                call_command('processar_agendamentos_ia_pendentes')
            except Exception as e:  # noqa: BLE001
                self.stderr.write(f'[sync_status] agendamentos: {e}')

        # reconcilia pós-venda (move novo serviço → Serviço Ativo quando habilitado)
        call_command('crm_reconciliar_posvenda')
        # reconcilia indicação (O.S. aberta, serviço habilitado → Concluído)
        call_command('crm_sincronizar_indicacao')
        # Anexos + aceite do contrato PENDENTES: cobre qualquer ordem de eventos
        # (docs validados antes OU depois da conversão). O gatilho pontual
        # (signal na validação / retry no worker de conversão) pode rodar cedo
        # demais; aqui é a garantia de consistência eventual, a cada ciclo.
        self._retry_aceites_pendentes()
        self.stdout.write(
            f'[sync_status] ciclo: {len(lead_ids)} sincronizado(s), '
            f'{len(ag_pendentes)} agendamento(s) pendente(s)')

    def _retry_aceites_pendentes(self, limite: int = 3):
        """Leads convertidos (id_hubsoft) com documentação validada e anexos
        ainda não enviados → tenta anexar docs ao contrato e marcar o aceite.
        Só leads recentes (30 dias) para não re-tentar histórico eternamente.
        Indicações ficam de fora naturalmente (sem imagens de docs do robô)."""
        import datetime as _dt
        from django.utils import timezone as _tz
        from vendas_web.models import LeadProspecto
        from vendas_web.services.contrato_service import tentar_aceite_pos_conversao
        limiar = _tz.now() - _dt.timedelta(days=30)
        pendentes = (LeadProspecto.objects
                     .filter(documentacao_validada=True,
                             anexos_contrato_enviados=False,
                             ativo=True,
                             data_cadastro__gte=limiar)
                     .exclude(id_hubsoft__isnull=True).exclude(id_hubsoft='')
                     .order_by('id')[:limite])
        for lead in pendentes:
            if self._stop:
                break
            try:
                ok = tentar_aceite_pos_conversao(lead)
                self.stdout.write(f'[sync_status] aceite pendente lead={lead.pk} → {ok}')
            except Exception as e:  # noqa: BLE001
                self.stderr.write(f'[sync_status] aceite lead={lead.pk} falhou: {e}')
