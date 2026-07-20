"""
Formulario publico de candidatura.

Quem abre isto e o candidato, no celular, sem login, chegando por QR ou link.
Mesma postura de seguranca da view publica do DP, e pelos mesmos motivos:

- Tenant resolvido pelo TOKEN, com duas defesas somadas (escopo no thread local
  mais tenant explicito em toda leitura e escrita). Nenhuma basta sozinha.
- 404 generico pra token invalido, desativado, de vaga pausada ou encerrada.
  Diferenciar transformaria a pagina em oraculo de enumeracao.
- Resposta de conflito generica. Dizer que o numero ja existe transformaria o
  formulario num oraculo de "fulano se candidatou aqui?", aberto na internet.
- CSRF LIGADO. O form e renderizado pelo proprio Django. O @csrf_exempt que
  existe em `apps/comercial/cadastro/views.py` e pra webhook, nao pra isto.
"""
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.people.models import ConfiguracaoPeople, LinkCandidatura
from apps.people.services.candidaturas import (
    contabilizar_candidatura, gravar_consentimento, registrar_candidatura,
)
from apps.people.services.pipeline import garantir_etapa_inicial
from apps.people.tenant_scope import escopo_tenant


def _link_ou_404(token):
    """
    404 generico. Nao diferencia inexistente de desativado de vaga encerrada.

    `all_tenants` aqui e obrigatorio e nao descuido: nao ha usuario, entao o
    thread local esta vazio e o manager filtrado nao acharia nada. O token e o
    proprio mecanismo de resolucao de tenant.
    """
    link = (LinkCandidatura.all_tenants
            .select_related('tenant', 'unidade', 'vaga', 'vaga__cargo')
            .filter(token=token).first())
    if link is None or not link.esta_valido():
        raise Http404
    return link


def _contexto(link, valores=None, erros=None):
    return {
        'link': link,
        'unidade': link.unidade,
        'vaga': link.vaga,
        'valores': valores or {},
        'erros': erros or {},
    }


@require_http_methods(['GET'])
@ratelimit(key='ip', rate='30/m', block=True)
def formulario(request, token):
    link = _link_ou_404(token)

    with escopo_tenant(link.tenant):
        config = ConfiguracaoPeople.get_config(link.tenant)

    contexto = _contexto(link)
    contexto['config'] = config
    return render(request, 'people/candidatura_formulario.html', contexto)


@require_http_methods(['POST'])
@ratelimit(key='ip', rate='5/m', block=True)
@ratelimit(key=lambda grupo, request: request.resolver_match.kwargs.get('token', ''),
           rate='20/h', block=True)
def enviar(request, token):
    """
    Recebe a candidatura.

    O rate limit por TOKEN, alem do por IP, existe porque um pool de IPs
    enxurraria um link especifico sem ele.
    """
    link = _link_ou_404(token)

    with escopo_tenant(link.tenant):
        config = ConfiguracaoPeople.get_config(link.tenant)

        # Honeypot: campo escondido que humano nao ve. Preenchido, devolvemos
        # sucesso falso pro robo nao aprender qual foi o sinal.
        if request.POST.get('sobrenome_confirmacao'):
            return render(request, 'people/candidatura_ok.html',
                          {'unidade': link.unidade, 'vaga': link.vaga})

        dados, erros = _ler_e_validar(request)

        if not request.POST.get('consentimento_lgpd'):
            erros['consentimento_lgpd'] = 'É preciso aceitar para enviar.'

        if erros:
            contexto = _contexto(link, request.POST, erros)
            contexto['config'] = config
            return render(request, 'people/candidatura_formulario.html',
                          contexto, status=400)

        resultado = registrar_candidatura(link.tenant, link, dados)

        if not resultado.ok:
            contexto = _contexto(link, request.POST, resultado.erros)
            contexto['config'] = config
            # 409 no duplicado, 400 no resto. O corpo e o mesmo texto generico
            # nos dois casos: o status ajuda o log, nao o visitante.
            status = 409 if resultado.acao == 'duplicado' else 400
            return render(request, 'people/candidatura_formulario.html',
                          contexto, status=status)

        gravar_consentimento(resultado.candidato, request, config)
        contabilizar_candidatura(link)
        # Poe o candidato na primeira etapa pra ele aparecer no board. Sem
        # usuario: quem "moveu" foi o proprio candidato ao se inscrever.
        garantir_etapa_inicial(resultado.candidato)

    return render(request, 'people/candidatura_ok.html',
                  {'unidade': link.unidade, 'vaga': link.vaga})


def _ler_e_validar(request):
    """
    Le o POST e valida o minimo.

    Deliberadamente pouco exigente: cada campo obrigatorio a mais e gente
    desistindo no meio, e a dor numero um do cliente e "nao chega candidato".
    So nome e WhatsApp travam, porque sem eles nao ha como dar retorno nem
    deduplicar.
    """
    dados = {
        'nome_completo': (request.POST.get('nome_completo') or '').strip(),
        'whatsapp': (request.POST.get('whatsapp') or '').strip(),
        'email': (request.POST.get('email') or '').strip(),
        'data_nascimento': (request.POST.get('data_nascimento') or '').strip() or None,
        'cidade': (request.POST.get('cidade') or '').strip(),
        'estado': (request.POST.get('estado') or '').strip(),
        'bairro': (request.POST.get('bairro') or '').strip(),
        'experiencia_previa': (request.POST.get('experiencia_previa') or '').strip(),
        'disponibilidade_horario': (request.POST.get('disponibilidade_horario') or '').strip(),
        'curriculo': request.FILES.get('curriculo'),
    }

    erros = {}
    if not dados['nome_completo']:
        erros['nome_completo'] = 'Informe seu nome completo.'

    somente_digitos = ''.join(c for c in dados['whatsapp'] if c.isdigit())
    if len(somente_digitos) < 10:
        erros['whatsapp'] = 'Informe um WhatsApp com DDD.'

    arquivo = dados['curriculo']
    if arquivo:
        if arquivo.size > 5 * 1024 * 1024:
            erros['curriculo'] = 'O arquivo precisa ter até 5 MB.'
        elif not arquivo.name.lower().endswith(('.pdf', '.doc', '.docx')):
            erros['curriculo'] = 'Envie em PDF ou Word.'

    return dados, erros
