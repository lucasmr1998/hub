#!/usr/bin/env python3
"""
Migra o tenant Aurora HQ e seu CRM do SQLite para o PostgreSQL local.
Passo 1: Lê do SQLite e salva em memória.
Passo 2: Escreve no PostgreSQL usando Django ORM.
"""
import os, sys, json

# ═══════════════════════════════════════════════════════════════════════════
# PASSO 1: Ler dados do SQLite
# ═══════════════════════════════════════════════════════════════════════════
os.environ['DJANGO_SETTINGS_MODULE'] = 'gerenciador_vendas.settings_local'

import django
django.setup()

from apps.sistema.models import Tenant, PerfilUsuario, ConfiguracaoEmpresa
from apps.sistema.middleware import set_current_tenant
from apps.comercial.crm.models import (
    Pipeline, PipelineEstagio, ConfiguracaoCRM, EquipeVendas, TagCRM,
)
from apps.suporte.models import CategoriaTicket, SLAConfig
from apps.notificacoes.models import TipoNotificacao, CanalNotificacao

aurora = Tenant.objects.get(slug='aurora-hq')
set_current_tenant(aurora)

# Serializar tudo
snapshot = {'tenant': {}, 'config_empresa': {}, 'users': [], 'pipelines': [], 'config_crm': {},
            'equipes': [], 'tags': [], 'cat_tickets': [], 'slas': [], 'tipos_notif': [], 'canais_notif': []}

# Tenant
for f in ['nome','slug','modulo_comercial','modulo_marketing','modulo_cs','plano_comercial','plano_marketing','plano_cs','ativo']:
    snapshot['tenant'][f] = getattr(aurora, f)

# Config empresa
ce = ConfiguracaoEmpresa.objects.first()
if ce:
    for f in ['nome_empresa','ativo']:
        snapshot['config_empresa'][f] = getattr(ce, f)

# Users
for p in PerfilUsuario.objects.filter(tenant=aurora):
    u = p.user
    snapshot['users'].append({
        'username': u.username, 'email': u.email, 'first_name': u.first_name,
        'last_name': u.last_name, 'is_staff': u.is_staff, 'is_superuser': u.is_superuser,
        'password': u.password,
    })

# Pipelines + Estagios
for p in Pipeline.objects.all():
    pd = {'nome': p.nome, 'slug': p.slug, 'tipo': p.tipo, 'padrao': p.padrao, 'cor_hex': p.cor_hex, 'estagios': []}
    for e in PipelineEstagio.objects.filter(pipeline=p).order_by('ordem'):
        pd['estagios'].append({
            'nome': e.nome, 'slug': e.slug, 'tipo': e.tipo, 'ordem': e.ordem,
            'cor_hex': e.cor_hex, 'probabilidade_padrao': e.probabilidade_padrao,
            'is_final_ganho': e.is_final_ganho, 'is_final_perdido': e.is_final_perdido,
        })
    snapshot['pipelines'].append(pd)

# Config CRM
cfg = ConfiguracaoCRM.objects.first()
if cfg:
    snapshot['config_crm'] = {
        'pipeline_slug': cfg.pipeline_padrao.slug if cfg.pipeline_padrao else None,
        'estagio_slug': cfg.estagio_inicial_padrao.slug if cfg.estagio_inicial_padrao else None,
        'criar_auto': cfg.criar_oportunidade_automatico,
        'score_min': cfg.score_minimo_auto_criacao,
    }

# Equipes
for eq in EquipeVendas.objects.all():
    snapshot['equipes'].append({
        'nome': eq.nome, 'descricao': eq.descricao or '', 'cor_hex': eq.cor_hex or '#3b82f6',
        'lider': eq.lider.username if eq.lider else None,
    })

# Tags
for t in TagCRM.objects.all():
    snapshot['tags'].append({'nome': t.nome, 'cor_hex': t.cor_hex})

# Categorias ticket
for ct in CategoriaTicket.objects.all():
    snapshot['cat_tickets'].append({'nome': ct.nome, 'slug': ct.slug, 'icone': ct.icone or 'fa-tag'})

# SLA
for s in SLAConfig.objects.all():
    snapshot['slas'].append({'plano_tier': s.plano_tier, 'resp': s.tempo_primeira_resposta_horas, 'resol': s.tempo_resolucao_horas})

# Notificacoes
for tn in TipoNotificacao.objects.all():
    snapshot['tipos_notif'].append({'codigo': tn.codigo, 'nome': tn.nome, 'descricao': tn.descricao or '',
                                     'template': tn.template_padrao or '', 'prioridade': tn.prioridade_padrao})
for cn in CanalNotificacao.objects.all():
    snapshot['canais_notif'].append({'codigo': cn.codigo, 'nome': cn.nome, 'ativo': cn.ativo})

print(f"SQLite lido: {len(snapshot['users'])} users, {len(snapshot['pipelines'])} pipelines, "
      f"{len(snapshot['equipes'])} equipes, {len(snapshot['tags'])} tags")

# ═══════════════════════════════════════════════════════════════════════════
# PASSO 2: Escrever no PostgreSQL via Django ORM
# ═══════════════════════════════════════════════════════════════════════════

# Trocar settings para PG
from django.conf import settings
settings.DATABASES['default'] = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'aurora_dev', 'USER': 'postgres', 'PASSWORD': 'admin123',
    'HOST': 'localhost', 'PORT': '5432',
}

# Fechar conexões antigas (SQLite)
from django.db import connections
for conn in connections.all():
    conn.close()

# Agora o ORM usa PG
from django.contrib.auth.models import User
set_current_tenant(None)

# Tenant
t, _ = Tenant.objects.get_or_create(slug=snapshot['tenant']['slug'], defaults=snapshot['tenant'])
print(f"\nPG: Tenant '{t.nome}' (id={t.pk})")

# Config empresa
if snapshot['config_empresa']:
    ConfiguracaoEmpresa.all_tenants.get_or_create(tenant=t, defaults=snapshot['config_empresa'])

# Users
user_map = {}
for ud in snapshot['users']:
    u, created = User.objects.get_or_create(username=ud['username'], defaults={
        'email': ud['email'], 'first_name': ud['first_name'], 'last_name': ud['last_name'],
        'is_staff': ud['is_staff'], 'is_superuser': ud['is_superuser'],
    })
    if created:
        u.password = ud['password']
        u.save(update_fields=['password'])
    PerfilUsuario.objects.get_or_create(user=u, defaults={'tenant': t})
    user_map[ud['username']] = u
print(f"PG: {len(user_map)} users")

set_current_tenant(t)

# Pipelines + Estagios
pipe_map = {}
est_map = {}
for pd in snapshot['pipelines']:
    p, _ = Pipeline.all_tenants.get_or_create(tenant=t, slug=pd['slug'], defaults={
        'nome': pd['nome'], 'tipo': pd['tipo'], 'padrao': pd['padrao'], 'cor_hex': pd['cor_hex'],
    })
    pipe_map[pd['slug']] = p
    for ed in pd['estagios']:
        e, _ = PipelineEstagio.all_tenants.get_or_create(tenant=t, pipeline=p, slug=ed['slug'], defaults={
            'nome': ed['nome'], 'tipo': ed['tipo'], 'ordem': ed['ordem'], 'cor_hex': ed['cor_hex'],
            'probabilidade_padrao': ed['probabilidade_padrao'],
            'is_final_ganho': ed['is_final_ganho'], 'is_final_perdido': ed['is_final_perdido'],
        })
        est_map[f"{pd['slug']}:{ed['slug']}"] = e
print(f"PG: {len(pipe_map)} pipelines, {sum(len(pd['estagios']) for pd in snapshot['pipelines'])} estagios")

# Config CRM
if snapshot['config_crm'] and snapshot['config_crm'].get('pipeline_slug'):
    c = snapshot['config_crm']
    pip = pipe_map.get(c['pipeline_slug'])
    est = est_map.get(f"{c['pipeline_slug']}:{c['estagio_slug']}")
    if pip:
        ConfiguracaoCRM.all_tenants.get_or_create(tenant=t, defaults={
            'pipeline_padrao': pip, 'estagio_inicial_padrao': est,
            'criar_oportunidade_automatico': c['criar_auto'], 'score_minimo_auto_criacao': c['score_min'],
        })
        print("PG: ConfiguracaoCRM criada")

# Equipes
for ed in snapshot['equipes']:
    lider = user_map.get(ed['lider'])
    EquipeVendas.all_tenants.get_or_create(tenant=t, nome=ed['nome'], defaults={
        'descricao': ed['descricao'], 'cor_hex': ed['cor_hex'], 'lider': lider,
    })
print(f"PG: {len(snapshot['equipes'])} equipes")

# Tags
for td in snapshot['tags']:
    TagCRM.all_tenants.get_or_create(tenant=t, nome=td['nome'], defaults={'cor_hex': td['cor_hex']})
print(f"PG: {len(snapshot['tags'])} tags")

# Categorias ticket
for cd in snapshot['cat_tickets']:
    CategoriaTicket.all_tenants.get_or_create(tenant=t, slug=cd['slug'], defaults={'nome': cd['nome'], 'icone': cd['icone']})

# SLA
for sd in snapshot['slas']:
    SLAConfig.all_tenants.get_or_create(tenant=t, plano_tier=sd['plano_tier'], defaults={
        'tempo_primeira_resposta_horas': sd['resp'], 'tempo_resolucao_horas': sd['resol'],
    })

# Notificacoes
for nd in snapshot['tipos_notif']:
    TipoNotificacao.all_tenants.get_or_create(tenant=t, codigo=nd['codigo'], defaults={
        'nome': nd['nome'], 'descricao': nd['descricao'], 'template_padrao': nd['template'],
        'prioridade_padrao': nd['prioridade'],
    })
for cd in snapshot['canais_notif']:
    CanalNotificacao.all_tenants.get_or_create(tenant=t, codigo=cd['codigo'], defaults={
        'nome': cd['nome'], 'ativo': cd['ativo'],
    })

print(f"\nMigração concluída! Aurora HQ no PostgreSQL com CRM completo.")
