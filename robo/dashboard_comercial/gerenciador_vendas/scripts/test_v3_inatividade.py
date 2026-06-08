"""Teste E2E manual da v3 reatribuicao por inatividade.

Uso:
  python manage.py shell --settings=gerenciador_vendas.settings_local < scripts/test_v3_inatividade.py

Usa `all_tenants` em todos os manager access (shell nao tem request.tenant setado).
"""
from datetime import timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from apps.sistema.models import Tenant
from apps.inbox.models import (
    Conversa, Mensagem, FilaInbox, MembroEquipeInbox,
    PerfilAgenteInbox, CanalInbox, HistoricoTransferencia,
)

t = Tenant.objects.get(slug='aurora-hq')
fila = FilaInbox.all_tenants.filter(tenant=t).first()
canal = CanalInbox.all_tenants.filter(tenant=t).first()
equipe = fila.equipe

print('\n' + '='*70 + '\nSETUP\n' + '='*70)
print(f'Tenant: {t.slug}  Fila: {fila.nome} (id={fila.id})')

# Limpa conversas de teste anteriores
old_qs = Conversa.all_tenants.filter(tenant=t, metadata__v3_test=True)
old_pks = list(old_qs.values_list('pk', flat=True))
print(f'Limpando {len(old_pks)} conversas de teste anteriores: {old_pks}')
HistoricoTransferencia.all_tenants.filter(conversa_id__in=old_pks).delete()
Mensagem.all_tenants.filter(conversa_id__in=old_pks).delete()
Conversa.all_tenants.filter(pk__in=old_pks).delete()

# Garante 2 agentes online
bob, created = User.objects.get_or_create(
    username='bob_teste_v3',
    defaults={'first_name': 'Bob', 'last_name': 'Teste', 'email': 'bob@teste.local'},
)
if created:
    bob.set_password('bobtest123'); bob.save()
    print(f'Criado user: {bob.username}')
MembroEquipeInbox.all_tenants.get_or_create(tenant=t, equipe=equipe, user=bob)
pa, _ = PerfilAgenteInbox.all_tenants.get_or_create(tenant=t, user=bob, defaults={'status': 'online'})
pa.status = 'online'; pa.save()

aurora = User.objects.get(username='aurora')

print(f'Agentes online esperados na equipe: aurora (id={aurora.id}), bob (id={bob.id})')

# Forca aurora pra online tambem
pa_aur, _ = PerfilAgenteInbox.all_tenants.get_or_create(tenant=t, user=aurora, defaults={'status': 'online'})
pa_aur.status = 'online'; pa_aur.save()

# Ativa features na fila
fila.realocar_inativo_ativo = True
fila.tempo_max_sem_assumir_min = 10
fila.max_realocacoes = 2
fila.alerta_admin_inativo_ativo = True
fila.tempo_max_sem_responder_min = 30
fila.save()
print(f'Fila configurada: realocar=10min max=2  alerta=30min')

agora = timezone.now()

# Cenario A
ca = Conversa(
    tenant=t, canal=canal, contato_nome='Cliente Teste A (nao assumiu)',
    contato_telefone='5598999990001', status='aberta', modo_atendimento='humano',
    agente=aurora, equipe=equipe, fila=fila, assumida=False,
    numero=999001, metadata={'v3_test': True, 'cenario': 'A'},
)
ca.save()
Conversa.all_tenants.filter(pk=ca.pk).update(data_abertura=agora - timedelta(minutes=20))
HistoricoTransferencia.all_tenants.create(
    tenant=t, conversa=ca, tipo='atribuicao_inicial',
    para_agente=aurora, para_equipe=equipe, para_fila=fila, motivo='teste v3',
)
HistoricoTransferencia.all_tenants.filter(conversa=ca).update(data=agora - timedelta(minutes=15))
m_a = Mensagem(tenant=t, conversa=ca, remetente_tipo='contato',
               remetente_nome='Cliente A', tipo_conteudo='texto', conteudo='Oi, quero o plano')
m_a.save()
Mensagem.all_tenants.filter(pk=m_a.pk).update(data_envio=agora - timedelta(minutes=15))
print(f'\n[A] #{ca.numero} pk={ca.pk} criada — atribuida ha 15min, assumida=False, agente=aurora({aurora.id})')

# Cenario B
cb = Conversa(
    tenant=t, canal=canal, contato_nome='Cliente Teste B (atendente sumiu)',
    contato_telefone='5598999990002', status='aberta', modo_atendimento='humano',
    agente=aurora, equipe=equipe, fila=fila, assumida=True,
    data_assumida=agora - timedelta(minutes=40),
    numero=999002, metadata={'v3_test': True, 'cenario': 'B'},
)
cb.save()
Conversa.all_tenants.filter(pk=cb.pk).update(data_abertura=agora - timedelta(minutes=50))
HistoricoTransferencia.all_tenants.create(
    tenant=t, conversa=cb, tipo='atribuicao_inicial',
    para_agente=aurora, para_equipe=equipe, para_fila=fila,
)
HistoricoTransferencia.all_tenants.filter(conversa=cb).update(data=agora - timedelta(minutes=50))
m_b1 = Mensagem(tenant=t, conversa=cb, remetente_tipo='contato', remetente_nome='Cliente B',
                tipo_conteudo='texto', conteudo='Bom dia, vi um plano')
m_b1.save()
m_b2 = Mensagem(tenant=t, conversa=cb, remetente_tipo='agente', remetente_nome='Aurora',
                tipo_conteudo='texto', conteudo='Bom dia! Posso ajudar', remetente_user=aurora)
m_b2.save()
m_b3 = Mensagem(tenant=t, conversa=cb, remetente_tipo='contato', remetente_nome='Cliente B',
                tipo_conteudo='texto', conteudo='Qual o valor?')
m_b3.save()
Mensagem.all_tenants.filter(pk=m_b1.pk).update(data_envio=agora - timedelta(minutes=45))
Mensagem.all_tenants.filter(pk=m_b2.pk).update(data_envio=agora - timedelta(minutes=42))
Mensagem.all_tenants.filter(pk=m_b3.pk).update(data_envio=agora - timedelta(minutes=35))
print(f'[B] #{cb.numero} pk={cb.pk} criada — assumida ha 40min, ultima msg contato ha 35min')

# Signals de Mensagem criam Lead+Fluxo+spam de msg do bot. Limpamos spam e forcamos estado:
Mensagem.all_tenants.filter(
    conversa__in=[ca.pk, cb.pk],
).exclude(pk__in=[m_a.pk, m_b1.pk, m_b2.pk, m_b3.pk]).delete()
Conversa.all_tenants.filter(pk__in=[ca.pk, cb.pk]).update(
    modo_atendimento='humano', status='aberta', agente=aurora,
)
Conversa.all_tenants.filter(pk=ca.pk).update(assumida=False)
Conversa.all_tenants.filter(pk=cb.pk).update(assumida=True)
print('Estado forcado: modo=humano, status=aberta, agente=aurora; msgs bot/spam removidas')

print('\n' + '='*70 + '\nDEBUG — o que o cron VAI ver\n' + '='*70)
print(f'fila.realocar_inativo_ativo={fila.realocar_inativo_ativo}  alerta={fila.alerta_admin_inativo_ativo}')

# Replica o filtro que o cron usa
conversas_qs = Conversa.all_tenants.filter(
    tenant=t, fila=fila, status__in=['aberta','pendente'],
    modo_atendimento='humano',
).exclude(agente__isnull=True)
print(f'Conversas que o cron veria: {conversas_qs.count()}')
for c in conversas_qs:
    print(f'  pk={c.pk} #{c.numero} assumida={c.assumida} agente={c.agente_id} realoc={c.realocacoes_count}')

print('\n' + '='*70 + '\nRODANDO CRON --dry-run\n' + '='*70)
from django.core.management import call_command
call_command('cron_inatividade_atendente', '--dry-run', '--tenant', 'aurora-hq')

print('\n' + '='*70 + '\nRODANDO CRON DE VERDADE\n' + '='*70)
call_command('cron_inatividade_atendente', '--tenant', 'aurora-hq')

print('\n' + '='*70 + '\nESTADO DEPOIS DO CRON\n' + '='*70)
ca_after = Conversa.all_tenants.get(pk=ca.pk)
cb_after = Conversa.all_tenants.get(pk=cb.pk)

print(f'\n[A] #{ca_after.numero} pk={ca_after.pk}')
print(f'   agente_id ANTES=aurora({aurora.id})  DEPOIS={ca_after.agente_id}  esperado=bob({bob.id})')
print(f'   assumida={ca_after.assumida}  realocacoes_count={ca_after.realocacoes_count}')
print(f'   status={ca_after.status}')
print(f'   Historicos ({HistoricoTransferencia.all_tenants.filter(conversa=ca_after).count()}):')
for h in HistoricoTransferencia.all_tenants.filter(conversa=ca_after).order_by('data'):
    print(f'     {h.data.strftime("%H:%M:%S")} tipo={h.tipo:20} de={h.de_agente_id} para={h.para_agente_id} motivo={h.motivo[:50]}')
msgs_sys_a = Mensagem.all_tenants.filter(conversa=ca_after, remetente_tipo='sistema').order_by('data_envio')
print(f'   Msgs sistema ({msgs_sys_a.count()}):')
for m in msgs_sys_a:
    print(f'     - {m.conteudo[:100]}')

print(f'\n[B] #{cb_after.numero} pk={cb_after.pk}')
print(f'   agente_id={cb_after.agente_id}  assumida={cb_after.assumida} (esperado: nao mudou)')
print(f'   metadata.alerta_inatividade_em={(cb_after.metadata or {}).get("alerta_inatividade_em")}')
print(f'   Historicos ({HistoricoTransferencia.all_tenants.filter(conversa=cb_after).count()}):')
for h in HistoricoTransferencia.all_tenants.filter(conversa=cb_after).order_by('data'):
    print(f'     {h.data.strftime("%H:%M:%S")} tipo={h.tipo:20} motivo={h.motivo[:60]}')

from apps.notificacoes.models import Notificacao
notifs = Notificacao.objects.filter(
    tenant=t, dados_contexto__conversa_id=cb_after.pk,
).order_by('-data_criacao')
print(f'   Notificacoes criadas: {notifs.count()}')
for n in notifs[:5]:
    print(f'     - dest_id={n.destinatario_id} titulo={n.titulo[:60]!r} prio={n.prioridade}')

print('\n' + '='*70 + '\nFIM\n' + '='*70)
