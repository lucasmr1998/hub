"""Importacao de planilha de ads (Matrix) com match em leads existentes.

Fluxo em 3 estagios:
1. Upload CSV + tenant + dry-run preview
2. Usuario confirma matches (checkboxes pra Medium/Weak)
3. Persiste: enriquece leads (canal, fonte, campanha_origem,
   metadata_campanhas). Op herda automaticamente via save().

Formato esperado (export Matrix):
  Cod;Titulo do post;Tipo;Conta;Canal;Nome;Telefone;Classificacao;Data Acesso;Protocolo;Mensagem

Match em 3 camadas:
  Strong: tel + janela ±24h + canal compativel
  Medium: tel + (janela XOR canal)
  Weak:   so tel

Ver docs/PRODUTO/modulos/comercial/modelo_origem_lead_e_oportunidade.md
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import timedelta, datetime
from collections import defaultdict

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods


def _superuser_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_superuser)(view_func))


JANELA_HORAS = 24
CANAL_PADRAO_MATRIX = 'whatsapp'  # Matrix sempre eh whatsapp
FONTE_PADRAO_ADS = 'facebook'     # Matrix exporta ads do Meta (FB/Insta)


def _norm_tel(tel):
    return re.sub(r'\D', '', tel or '')


def _parse_data(s):
    """Parser pra formatos: '28/06/2026 22:13:45' ou '2026-06-28 22:13:45'."""
    if not s:
        return None
    s = s.strip()
    for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _parse_csv(arquivo):
    """Parseia o arquivo Matrix. Retorna lista de dicts."""
    raw = arquivo.read()
    # Matrix exporta em latin-1
    for enc in ('latin-1', 'utf-8-sig', 'utf-8'):
        try:
            texto = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError('Encoding desconhecido')

    reader = csv.DictReader(io.StringIO(texto), delimiter=';')
    rows = []
    for r in reader:
        tel = _norm_tel(r.get('Número de telefone') or r.get('Numero de telefone') or '')
        if not tel:
            continue
        rows.append({
            'cod':          r.get('Cod.', '').strip(),
            'titulo_post':  r.get('Título do post') or r.get('Titulo do post') or '',
            'tipo':         r.get('Tipo', '').strip(),
            'canal_csv':    (r.get('Canal') or '').strip().lower(),  # 'whatsapp'
            'nome':         (r.get('Nome do contato') or '').strip(),
            'telefone':     tel,
            'classificacao': (r.get('Classificação principal do atendimento') or
                             r.get('Classificacao principal do atendimento') or '').strip(),
            'data_acesso':  _parse_data(r.get('Data Acesso') or r.get('Data') or ''),
            'protocolo':    r.get('Protocolo', '').strip(),
            'mensagem':     r.get('Mensagem', ''),
        })
    return rows


def _classificar_match(row, lead, janela_horas=JANELA_HORAS):
    """Retorna 'strong' | 'medium' | 'weak' baseado em criterios:
    - tel: ja confirmado fora daqui (necessario)
    - janela: lead.data_cadastro em ±janela_horas da row['data_acesso']
    - canal: lead.canal == 'whatsapp' (Matrix exporta whatsapp)
    """
    tem_janela = False
    if row['data_acesso'] and lead.data_cadastro:
        delta = abs((row['data_acesso'] - lead.data_cadastro.replace(tzinfo=None)).total_seconds())
        tem_janela = delta <= janela_horas * 3600

    tem_canal = (lead.canal == CANAL_PADRAO_MATRIX)

    if tem_janela and tem_canal:
        return 'strong'
    if tem_janela or tem_canal:
        return 'medium'
    return 'weak'


def _executar_match(rows, tenant):
    """Roda o match em 3 camadas pra todos os rows. Retorna lista de
    matches (1 por row) incluindo info do lead encontrado."""
    from apps.comercial.leads.models import LeadProspecto

    tels = {r['telefone'] for r in rows}
    # 1 query so pra todos os leads do tenant que batem
    leads = list(LeadProspecto.all_tenants.filter(tenant=tenant, telefone__in=tels).select_related('campanha_origem'))
    leads_por_tel = defaultdict(list)
    for l in leads:
        tel_norm = _norm_tel(l.telefone)
        if tel_norm in tels:
            leads_por_tel[tel_norm].append(l)

    matches = []
    for row in rows:
        candidatos = leads_por_tel.get(row['telefone'], [])
        if not candidatos:
            matches.append({**row, 'status': 'no_match', 'lead': None, 'qualidade': None})
            continue

        # Se varios leads com mesmo tel, escolhe o mais proximo da data
        if row['data_acesso'] and len(candidatos) > 1:
            candidatos.sort(key=lambda l: abs((row['data_acesso'] - l.data_cadastro.replace(tzinfo=None)).total_seconds()))
        lead = candidatos[0]
        qualidade = _classificar_match(row, lead)
        matches.append({**row, 'status': 'match', 'lead': lead, 'qualidade': qualidade})
    return matches


@_superuser_required
@require_http_methods(['GET', 'POST'])
def importar_ads_view(request):
    """Pagina principal. GET = formulario. POST = preview ou confirmacao."""
    from apps.sistema.models import Tenant

    tenants = list(Tenant.objects.filter(ativo=True).order_by('slug'))

    contexto = {
        'tenants_choices': tenants,
        'matches': None,
        'estagio': 'upload',
        'janela_horas': JANELA_HORAS,
    }

    if request.method == 'POST':
        acao = request.POST.get('acao', 'preview')
        tenant_slug = request.POST.get('tenant')
        tenant = next((t for t in tenants if t.slug == tenant_slug), None)
        if not tenant:
            contexto['erro'] = 'Tenant invalido'
            return render(request, 'comercial/leads/importar_ads.html', contexto)
        contexto['tenant_selecionado'] = tenant.slug

        if acao == 'preview':
            arquivo = request.FILES.get('arquivo')
            if not arquivo:
                contexto['erro'] = 'Selecione um arquivo CSV'
                return render(request, 'comercial/leads/importar_ads.html', contexto)
            try:
                rows = _parse_csv(arquivo)
            except Exception as e:
                contexto['erro'] = f'Erro ao processar CSV: {e}'
                return render(request, 'comercial/leads/importar_ads.html', contexto)

            matches = _executar_match(rows, tenant)
            contexto.update({
                'estagio': 'preview',
                'matches': matches,
                'total_rows': len(rows),
                'total_match': sum(1 for m in matches if m['status'] == 'match'),
                'strong': sum(1 for m in matches if m['qualidade'] == 'strong'),
                'medium': sum(1 for m in matches if m['qualidade'] == 'medium'),
                'weak':   sum(1 for m in matches if m['qualidade'] == 'weak'),
                'no_match': sum(1 for m in matches if m['status'] == 'no_match'),
                # Serializa pra reenviar no POST de confirmacao
                'matches_json': json.dumps([
                    {
                        'lead_id': m['lead'].id if m['lead'] else None,
                        'titulo_post': m['titulo_post'],
                        'protocolo': m['protocolo'],
                        'data_acesso': m['data_acesso'].isoformat() if m['data_acesso'] else None,
                        'qualidade': m['qualidade'],
                        'classificacao': m['classificacao'],
                        'mensagem': m['mensagem'][:200] if m['mensagem'] else '',
                    }
                    for m in matches if m['status'] == 'match'
                ]),
            })

        elif acao == 'confirmar':
            matches_data = json.loads(request.POST.get('matches_json', '[]'))
            ids_aprovados = set(request.POST.getlist('aprovar'))  # lead_id como str
            resultado = _persistir_matches(matches_data, ids_aprovados, tenant)
            contexto.update({
                'estagio': 'resultado',
                'resultado': resultado,
            })

    return render(request, 'comercial/leads/importar_ads.html', contexto)


def _persistir_matches(matches_data, ids_aprovados, tenant):
    """Enriquece leads selecionados. Cria CampanhaTrafego se nao existir.
    Retorna estatisticas."""
    from apps.comercial.leads.models import LeadProspecto
    from apps.marketing.campanhas.models import CampanhaTrafego

    stats = {
        'enriquecidos': 0,
        'campanhas_criadas': 0,
        'pulados_nao_aprovados': 0,
        'erros': [],
    }

    # Cache de campanhas por nome pra evitar query repetida
    campanhas_cache = {}

    for m in matches_data:
        lead_id = m.get('lead_id')
        if not lead_id:
            continue
        if str(lead_id) not in ids_aprovados:
            stats['pulados_nao_aprovados'] += 1
            continue

        try:
            lead = LeadProspecto.all_tenants.get(id=lead_id, tenant=tenant)
        except LeadProspecto.DoesNotExist:
            stats['erros'].append(f'Lead {lead_id} nao encontrado')
            continue

        nome_campanha = (m.get('titulo_post') or '').strip()
        if not nome_campanha:
            stats['erros'].append(f'Lead {lead_id} sem titulo do post')
            continue

        # Cria/recupera CampanhaTrafego
        if nome_campanha in campanhas_cache:
            campanha = campanhas_cache[nome_campanha]
        else:
            campanha, criada = CampanhaTrafego.all_tenants.get_or_create(
                tenant=tenant,
                nome=nome_campanha,
                defaults={
                    'codigo': f'ads_{abs(hash(nome_campanha)) % 100000}',
                    'palavra_chave': nome_campanha[:200],
                    'plataforma': 'facebook_ads',
                    'meio': 'ads',
                    'tipo_trafego': 'pago',
                    'ativa': True,
                },
            )
            campanhas_cache[nome_campanha] = campanha
            if criada:
                stats['campanhas_criadas'] += 1

        # Enriquecimento
        if not lead.canal:
            lead.canal = CANAL_PADRAO_MATRIX
        if not lead.fonte:
            lead.fonte = FONTE_PADRAO_ADS
        if not lead.campanha_origem_id:
            lead.campanha_origem = campanha

        # Adiciona evento no metadata (historico nao destrutivo)
        meta = lead.metadata_campanhas or {}
        eventos = meta.get('eventos_ads', [])
        eventos.append({
            'campanha':     nome_campanha,
            'protocolo':    m.get('protocolo'),
            'data_acesso':  m.get('data_acesso'),
            'qualidade':    m.get('qualidade'),
            'classificacao': m.get('classificacao'),
            'mensagem':     m.get('mensagem'),
            'importado_em': timezone.now().isoformat(),
        })
        meta['eventos_ads'] = eventos
        lead.metadata_campanhas = meta
        lead.total_campanhas_detectadas = len(eventos)

        lead.save(update_fields=['canal', 'fonte', 'campanha_origem',
                                  'metadata_campanhas', 'total_campanhas_detectadas'])
        stats['enriquecidos'] += 1

    return stats
