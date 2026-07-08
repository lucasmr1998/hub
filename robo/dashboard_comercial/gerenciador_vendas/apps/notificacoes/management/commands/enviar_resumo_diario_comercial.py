"""
Envia resumo diario comercial via WhatsApp pros destinatarios que ativaram
a PreferenciaNotificacao(tipo='resumo_diario_comercial', canal='whatsapp').

Uso:
    python manage.py enviar_resumo_diario_comercial
    python manage.py enviar_resumo_diario_comercial --tenant=nuvyon
    python manage.py enviar_resumo_diario_comercial --dry-run
    python manage.py enviar_resumo_diario_comercial --tenant=nuvyon --dia=2026-07-02

Agenda: rodar via cron `0 * * * *` (toda hora cheia). O command so envia
pra cada destinatario quando a hora atual BRT bate com o
`PreferenciaNotificacao.horario_inicio` (default 8h) e ainda nao houve
envio do dia (dedup por Notificacao). O resumo agrega o dia anterior
(default) + snapshot do pipeline atual. `--force` ignora horario e dedup.

Envio: usa a Uazapi da Aurora HQ (canal do sistema, nao o canal comercial
do proprio tenant). Falha por destinatario nao para o command — vai pro proximo.
"""
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.comercial.crm.services.resumo_diario import (
    formatar_whatsapp,
    montar_resumo,
)
from apps.notificacoes.models import (
    CanalNotificacao,
    Notificacao,
    PreferenciaNotificacao,
    TipoNotificacao,
)
from apps.notificacoes.services.enviar_whatsapp_aurora import (
    enviar_whatsapp_aurora,
)
from apps.sistema.models import Tenant

CODIGO_TIPO = 'resumo_diario_comercial'
CODIGO_CANAL = 'whatsapp'


class Command(BaseCommand):
    help = 'Envia resumo diario comercial via WhatsApp pros usuarios que ativaram a preferencia.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', help='slug do tenant (default: todos com PreferenciaNotificacao ativa)')
        parser.add_argument('--dia', help='dia do resumo YYYY-MM-DD (default: ontem BRT)')
        parser.add_argument('--dry-run', action='store_true', help='monta e imprime sem enviar')
        parser.add_argument('--force', action='store_true',
                            help='ignora horario da preferencia e dedup (pra teste manual)')

    def handle(self, *args, **opts):
        tenant_slug = opts.get('tenant')
        dia_str = opts.get('dia')
        dry = opts.get('dry_run', False)

        dia = None
        if dia_str:
            dia = datetime.strptime(dia_str, '%Y-%m-%d').date()

        # Tenants alvo
        tenants = Tenant.objects.filter(ativo=True)
        if tenant_slug:
            tenants = tenants.filter(slug=tenant_slug)

        total_enviados = 0
        total_falhados = 0

        for tenant in tenants:
            tipo = TipoNotificacao.objects.filter(
                tenant=tenant, codigo=CODIGO_TIPO, ativo=True,
            ).first()
            if not tipo:
                self.stdout.write(f'[{tenant.slug}] tipo "{CODIGO_TIPO}" nao existe, pulando')
                continue

            canal = CanalNotificacao.objects.filter(
                tenant=tenant, codigo=CODIGO_CANAL, ativo=True,
            ).first()
            if not canal:
                self.stdout.write(f'[{tenant.slug}] canal whatsapp inativo, pulando')
                continue

            preferencias = PreferenciaNotificacao.objects.filter(
                tenant=tenant,
                tipo_notificacao=tipo,
                canal_preferido=canal,
                ativo=True,
            ).select_related('usuario')

            if not preferencias.exists():
                self.stdout.write(f'[{tenant.slug}] nenhum destinatario preferencial, pulando')
                continue

            dados = montar_resumo(tenant, dia=dia)
            self.stdout.write(
                f'[{tenant.slug}] resumo montado pra {dados["dia"]}: '
                f'{dados["ops_dia"]} novas ops, {dados["ganhas_crm"]} vendas CRM, '
                f'{dados["total_pipeline"]} no pipeline'
            )

            hora_atual_brt = timezone.localtime().hour
            for pref in preferencias:
                # Respeita o horario da preferencia: envia so quando a hora
                # atual bate com horario_inicio (default 8h). O cron roda de
                # hora em hora; --force/--dry-run ignoram o gate.
                hora_pref = pref.horario_inicio.hour if pref.horario_inicio else 8
                if not opts.get('force') and not dry and hora_atual_brt != hora_pref:
                    self.stdout.write(
                        f'  {pref.usuario.username}: fora do horario '
                        f'(agora {hora_atual_brt}h BRT, preferencia {hora_pref}h), pulando'
                    )
                    continue

                # Dedup: 1 resumo por usuario por dia. Reexecucao do cron na
                # mesma hora (ou retry apos falha parcial) nao duplica envio.
                ja_enviada = Notificacao.objects.filter(
                    tenant=tenant, tipo=tipo, destinatario=pref.usuario,
                    status='enviada', dados_contexto__dia=str(dados['dia']),
                ).exists()
                if not opts.get('force') and not dry and ja_enviada:
                    self.stdout.write(
                        f'  {pref.usuario.username}: resumo de {dados["dia"]} ja enviado hoje, pulando'
                    )
                    continue

                telefone = _telefone_do_usuario(pref.usuario, tenant)
                if not telefone:
                    self.stdout.write(self.style.WARNING(
                        f'  {pref.usuario.username}: sem telefone no PerfilUsuario, pulando'
                    ))
                    continue

                nome = (pref.usuario.first_name or pref.usuario.username).split(' ')[0]
                texto = formatar_whatsapp(
                    dados, nome_destinatario=nome, nome_tenant=tenant.nome,
                )

                if dry:
                    self.stdout.write(self.style.WARNING(
                        f'--- DRY {pref.usuario.username} ({telefone}) ---'
                    ))
                    self.stdout.write(texto)
                    self.stdout.write('---')
                    continue

                resultado = enviar_whatsapp_aurora(telefone, texto)

                registro = Notificacao.objects.create(
                    tenant=tenant,
                    tipo=tipo,
                    canal=canal,
                    destinatario=pref.usuario,
                    destinatario_telefone=telefone,
                    titulo=f'Resumo diario {tenant.nome} — {dados["dia"]}',
                    mensagem=texto,
                    dados_contexto={'dia': str(dados['dia'])},
                    status='enviada' if resultado['ok'] else 'falhou',
                    data_envio=timezone.now() if resultado['ok'] else None,
                    resposta_externa=resultado.get('resposta'),
                    erro_detalhes=resultado.get('erro') or '',
                )

                if resultado['ok']:
                    total_enviados += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'  {pref.usuario.username} ({telefone}): enviado (notif #{registro.pk})'
                    ))
                else:
                    total_falhados += 1
                    self.stdout.write(self.style.ERROR(
                        f'  {pref.usuario.username}: FALHOU — {resultado["erro"]}'
                    ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Total enviados: {total_enviados} | falhados: {total_falhados}'
        ))


def _telefone_do_usuario(user, tenant):
    """Retorna o telefone do PerfilUsuario naquele tenant, so digitos."""
    perfil = user.perfis_por_tenant.filter(tenant=tenant).first() \
        if hasattr(user, 'perfis_por_tenant') else None
    if perfil is None:
        # Fallback: primeiro perfil que existir
        from apps.sistema.models import PerfilUsuario
        perfil = PerfilUsuario.objects.filter(user=user, tenant=tenant).first()
    if not perfil or not perfil.telefone:
        return None
    return ''.join(c for c in perfil.telefone if c.isdigit())
