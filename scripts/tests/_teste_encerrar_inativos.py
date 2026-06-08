"""Teste e2e em dev (settings_local) do encerramento automatico.
Cria 1 conversa humana stale + 1 bot stale (controle), liga a config no tenant,
roda dry-run e real, verifica: humana fica resolvida com motivo de sistema; bot
nao e tocada. Limpa os controles no final."""
import os, sys, django, io
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'robo/dashboard_comercial/gerenciador_vendas')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings_local')
django.setup()

from django.utils import timezone
from datetime import timedelta
from django.core.management import call_command

from apps.sistema.models import Tenant
from apps.sistema.middleware import set_current_tenant
from apps.inbox.models import (
    Conversa, CanalInbox, ConfiguracaoInbox, MotivoEncerramento, Mensagem,
)


t = Tenant.objects.filter(slug='aurora-hq').first() or Tenant.objects.filter(ativo=True).first()
print('tenant:', t.slug, '(id', t.id, ')')
set_current_tenant(t)

cfg, _ = ConfiguracaoInbox.objects.get_or_create()
cfg.encerramento_auto_ativo = True
cfg.encerramento_auto_horas = 24
cfg.encerramento_auto_aviso_ativo = True
cfg.encerramento_auto_aviso_texto = (
    'Teste: encerramos por inatividade. Se precisar, e so chamar.'
)
cfg.save()
print('config: auto_ativo=True, horas=24, aviso ON')

# Canal: usa primeiro disponivel (cria se nao tiver)
canal = CanalInbox.objects.filter(ativo=True).first()
if not canal:
    canal = CanalInbox.objects.create(
        tenant=t, tipo='interno', nome='Canal Teste',
        ativo=True, configuracao={},
    )
    print('criou canal de teste')

# numero auto-increment por tenant: pega o maior
ultimo_num = Conversa.all_tenants.filter(tenant=t).order_by('-numero').first()
base = (ultimo_num.numero if ultimo_num else 0) + 1

velho = timezone.now() - timedelta(hours=48)

c_humana = Conversa.objects.create(
    tenant=t, canal=canal, contato_nome='TESTE_AUTOFECHA_HUMANA',
    contato_telefone='+5555901234567', status='aberta',
    modo_atendimento='humano', numero=base,
    ultima_mensagem_em=velho, ultima_mensagem_preview='oi',
)
c_bot = Conversa.objects.create(
    tenant=t, canal=canal, contato_nome='TESTE_AUTOFECHA_BOT',
    contato_telefone='+5555901234568', status='aberta',
    modo_atendimento='bot', numero=base + 1,
    ultima_mensagem_em=velho, ultima_mensagem_preview='oi',
)
print(f'criei conversas: humana #{c_humana.numero} (id {c_humana.id})  bot #{c_bot.numero} (id {c_bot.id})')

set_current_tenant(None)

print('\n--- DRY-RUN ---')
buf = io.StringIO()
call_command('encerrar_inativos', '--dry-run', '--tenant', t.slug, stdout=buf)
print(buf.getvalue())

print('--- REAL ---')
buf = io.StringIO()
call_command('encerrar_inativos', '--tenant', t.slug, stdout=buf)
print(buf.getvalue())

c_humana.refresh_from_db()
c_bot.refresh_from_db()
print('=== resultado ===')
print(f'humana: status={c_humana.status} motivo={c_humana.motivo_encerramento and c_humana.motivo_encerramento.nome!r}')
print(f'bot:    status={c_bot.status} motivo={c_bot.motivo_encerramento}')

ult_msgs = Mensagem.all_tenants.filter(conversa=c_humana).order_by('-data_envio')[:3]
print('\nultimas mensagens da humana:')
for m in ult_msgs:
    print(f'  [{m.remetente_tipo}/{m.tipo_conteudo}] {m.conteudo[:80]}')

# Asserts
ok = True
if c_humana.status != 'resolvida':
    print('FALHA: humana nao foi resolvida'); ok = False
if not c_humana.motivo_encerramento or c_humana.motivo_encerramento.codigo != MotivoEncerramento.CODIGO_AUTO:
    print('FALHA: motivo nao foi o auto_inatividade'); ok = False
if c_bot.status != 'aberta':
    print('FALHA: bot foi tocada'); ok = False
print('\nRESULTADO:', 'OK' if ok else 'FALHA')

# Cleanup das conversas de teste
print('\nlimpando conversas de teste...')
Mensagem.all_tenants.filter(conversa__in=[c_humana, c_bot]).delete()
c_humana.delete(); c_bot.delete()
# devolve config ao default (off) pra nao deixar feature ligada em dev por engano
cfg.encerramento_auto_ativo = False
cfg.save()
print('cleanup ok. config voltou pra OFF.')
