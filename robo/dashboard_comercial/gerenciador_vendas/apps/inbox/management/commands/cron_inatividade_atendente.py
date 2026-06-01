"""Detecta inatividade do atendente e dispara acoes (v3).

2 niveis (config por fila em FilaInbox):
  A. realocar_inativo_ativo + tempo_max_sem_assumir_min
     -> atribuido ha tempo > X min, NAO assumida, dentro do max_realocacoes
     -> chama realocar_conversa_inativa()

  B. alerta_admin_inativo_ativo + tempo_max_sem_responder_min
     -> assumida=True, ultima msg eh do contato ha > Y min
     -> chama alertar_admin_inatividade() (idempotente via metadata)

Pre-requisitos universais:
  - conversa.status in ('aberta', 'pendente')
  - conversa.modo_atendimento = 'humano'
  - conversa.fila NOT NULL e fila tem feature ativa
  - dentro do horario da fila

Uso:
  python manage.py cron_inatividade_atendente
  python manage.py cron_inatividade_atendente --dry-run
  python manage.py cron_inatividade_atendente --tenant tr-carrion
  python manage.py cron_inatividade_atendente --fila-id 5
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Detecta inatividade do atendente e dispara realocacao automatica (nivel A) ou alerta admin (nivel B).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Simula sem agir')
        parser.add_argument('--tenant', type=str, default=None, help='So um tenant (slug)')
        parser.add_argument('--fila-id', type=int, default=None, help='So uma fila (id)')
        parser.add_argument('--heartbeat-timeout-min', type=int, default=5,
                            help='Minutos sem heartbeat para marcar agente offline')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant
        from apps.inbox.models import Conversa, FilaInbox, Mensagem, PerfilAgenteInbox
        from apps.inbox.distribution import verificar_horario_fila
        from apps.inbox.services_inatividade import (
            realocar_conversa_inativa, alertar_admin_inatividade,
        )

        dry = opts['dry_run']
        slug = opts['tenant']
        fila_id = opts['fila_id']
        heartbeat_timeout = opts['heartbeat_timeout_min']

        tenants = Tenant.objects.filter(ativo=True)
        if slug:
            tenants = tenants.filter(slug=slug)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n[Cron Inatividade Atendente]{" [DRY RUN]" if dry else ""}'
        ))

        total_realocadas = 0
        total_alertadas = 0
        total_skipped = 0
        total_offline_auto = 0
        agora = timezone.now()

        # ─── HEARTBEAT: marca offline quem nao pingou ha mais do limite ───
        # Roda ANTES dos niveis A/B porque selecao de "outro agente online"
        # depende desse status estar correto.
        limite_hb = agora - timedelta(minutes=heartbeat_timeout)
        perfis_stale = PerfilAgenteInbox.objects.filter(status='online').filter(
            ultimo_heartbeat__isnull=False, ultimo_heartbeat__lt=limite_hb,
        )
        # Tambem inclui quem nunca pingou + status_em antigo (compat com tela antiga sem heartbeat)
        # Se ultimo_heartbeat null E ultimo_status_em antigo, considera abandonado
        perfis_sem_hb = PerfilAgenteInbox.objects.filter(status='online').filter(
            ultimo_heartbeat__isnull=True, ultimo_status_em__lt=limite_hb,
        )
        for p in list(perfis_stale) + list(perfis_sem_hb):
            if dry:
                self.stdout.write(
                    f'  [DRY] marcaria offline: user={p.user_id} '
                    f'last_hb={p.ultimo_heartbeat} status_em={p.ultimo_status_em}'
                )
            else:
                p.status = 'offline'
                p.save(update_fields=['status', 'ultimo_status_em'])
            total_offline_auto += 1

        for tenant in tenants:
            filas_qs = FilaInbox.all_tenants.filter(tenant=tenant, ativo=True)
            if fila_id:
                filas_qs = filas_qs.filter(pk=fila_id)
            filas = list(filas_qs)
            if not filas:
                continue

            self.stdout.write(f'\n[{tenant.slug}] filas: {len(filas)}')

            for fila in filas:
                if not (fila.realocar_inativo_ativo or fila.alerta_admin_inativo_ativo):
                    continue

                if not verificar_horario_fila(fila):
                    self.stdout.write(f'  fila #{fila.id} {fila.nome!r}: fora do horario, skip')
                    continue

                conversas = Conversa.all_tenants.filter(
                    tenant=tenant,
                    fila=fila,
                    status__in=['aberta', 'pendente'],
                    modo_atendimento='humano',
                ).exclude(agente__isnull=True)

                # ── NIVEL A: realocar ────────────────────────
                if fila.realocar_inativo_ativo:
                    limite_a = agora - timedelta(minutes=fila.tempo_max_sem_assumir_min)
                    candidatas_a = conversas.filter(
                        assumida=False,
                        realocacoes_count__lt=fila.max_realocacoes,
                    )
                    for c in candidatas_a:
                        # tempo desde atribuicao (data_abertura como proxy se nao houver historico)
                        ultima_attr = c.transferencias.filter(
                            tipo__in=['atribuicao_inicial', 'realocar_inativo', 'transferir_manual'],
                        ).order_by('-data').first()
                        ref = ultima_attr.data if ultima_attr else c.data_abertura
                        if ref > limite_a:
                            continue
                        if dry:
                            self.stdout.write(
                                f'  [DRY] realocar conversa #{c.numero} '
                                f'(agente={c.agente_id}, ref={ref.isoformat()})'
                            )
                            total_realocadas += 1
                            continue
                        try:
                            realocar_conversa_inativa(c)
                            total_realocadas += 1
                        except Exception as exc:
                            self.stdout.write(self.style.ERROR(
                                f'  ERRO realocando conversa #{c.numero}: {exc}'
                            ))

                # ── NIVEL B: alertar admin ───────────────────
                if fila.alerta_admin_inativo_ativo:
                    limite_b = agora - timedelta(minutes=fila.tempo_max_sem_responder_min)
                    candidatas_b = conversas.filter(assumida=True)
                    for c in candidatas_b:
                        # ja alertou nessa "rodada"? metadata.alerta_inatividade_em
                        ja_alertou = (c.metadata or {}).get('alerta_inatividade_em')

                        # ultima msg foi do contato?
                        ultima_msg = Mensagem.all_tenants.filter(
                            tenant=tenant, conversa=c,
                        ).exclude(remetente_tipo='sistema').order_by('-data_envio').first()
                        if not ultima_msg or ultima_msg.remetente_tipo != 'contato':
                            # agente ja respondeu — limpa flag pra alertar de novo
                            # se reabrir o ciclo
                            if ja_alertou:
                                meta = c.metadata or {}
                                meta.pop('alerta_inatividade_em', None)
                                c.metadata = meta
                                c.save(update_fields=['metadata'])
                            continue
                        if ultima_msg.data_envio > limite_b:
                            continue
                        if ja_alertou:
                            total_skipped += 1
                            continue
                        if dry:
                            self.stdout.write(
                                f'  [DRY] alertar admin conversa #{c.numero} '
                                f'(agente={c.agente_id}, ultima_msg={ultima_msg.data_envio.isoformat()})'
                            )
                            total_alertadas += 1
                            continue
                        try:
                            alertar_admin_inatividade(c)
                            total_alertadas += 1
                        except Exception as exc:
                            self.stdout.write(self.style.ERROR(
                                f'  ERRO alertando conversa #{c.numero}: {exc}'
                            ))

        self.stdout.write(self.style.SUCCESS(
            f'\nConcluido: offline_auto={total_offline_auto}  '
            f'realocadas={total_realocadas}  alertadas={total_alertadas}  '
            f'ja_alertadas={total_skipped}'
        ))
