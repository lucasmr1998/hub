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
    # Os campos saem da vaga (config_campos). Sem vaga (banco de talentos) usa o
    # padrao do catalogo, que ja e o conjunto sensato.
    from apps.people.models import Vaga

    fonte = link.vaga or Vaga(config_campos={})
    return {
        'link': link,
        'unidade': link.unidade,
        'vaga': link.vaga,
        'secoes': fonte.secoes_do_formulario(valores, erros),
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

        dados, erros = _ler_e_validar(request, link)

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


def _ler_e_validar(request, link):
    """
    Le o POST e valida conforme a config de campos da vaga.

    Deliberadamente pouco exigente por default: cada campo obrigatorio a mais e
    gente desistindo no meio, e a dor numero um do cliente e "nao chega
    candidato". Mas o RH decide o que exigir por vaga, e o que ele marcou como
    obrigatorio e validado aqui.

    nome e WhatsApp valem sempre, independente da config: sao travados no
    catalogo porque sem eles nao ha retorno nem dedup.
    """
    from apps.people import campos_candidatura as catalogo

    config = link.vaga.config_campos if link.vaga_id else {}
    extras = link.vaga.campos_extras() if link.vaga_id else []
    pedidos = catalogo.campos_solicitados(config, extras)
    solicitados = {c['nome'] for c in pedidos}
    obrigatorios = set(catalogo.campos_obrigatorios(config, extras))

    dados = {}
    custom = {}
    for campo in pedidos:
        nome = campo['nome']
        if catalogo.e_custom(nome):
            # Custom nao vira atributo do model: o valor vai pro JSON, sob o
            # slug. Guardado sob `nome` aqui so pra validacao e reexibicao
            # usarem a mesma chave do formulario.
            bruto = (request.POST.get(nome) or '').strip()
            if campo['tipo'] == 'bool':
                bruto = 'sim' if request.POST.get(nome) else ''
            elif campo['tipo'] == 'select' and bruto not in (campo.get('opcoes') or []):
                # Opcao fora da lista e POST forjado, nao erro de digitacao.
                bruto = ''
            dados[nome] = bruto
            custom[catalogo.slug_de(nome)] = bruto
        elif nome == 'curriculo':
            dados[nome] = request.FILES.get('curriculo')
        elif nome == 'data_nascimento':
            dados[nome] = (request.POST.get(nome) or '').strip() or None
        else:
            dados[nome] = (request.POST.get(nome) or '').strip()

    # Chave separada, e nao mais um campo solto, pra `registrar_candidatura`
    # nao ter que adivinhar o que e coluna e o que e JSON.
    dados['dados_custom'] = {k: v for k, v in custom.items() if v != ''}

    erros = {}

    # Travados: sempre exigidos, com validacao propria.
    nome_completo = dados.get('nome_completo', '')
    if not nome_completo:
        erros['nome_completo'] = 'Informe seu nome completo.'

    whatsapp = dados.get('whatsapp', '')
    if len(''.join(c for c in whatsapp if c.isdigit())) < 10:
        erros['whatsapp'] = 'Informe um WhatsApp com DDD.'

    # Demais obrigatorios da config: so precisa estar preenchido.
    rotulos = {c['nome']: c['rotulo'] for c in pedidos}
    for nome in obrigatorios:
        if nome in ('nome_completo', 'whatsapp'):
            continue
        vazio = not dados.get(nome)
        if vazio:
            erros[nome] = f'{rotulos.get(nome, "Este campo")} é obrigatório.'

    # Curriculo, quando enviado, valida tipo e tamanho independente de exigencia.
    arquivo = dados.get('curriculo')
    if arquivo:
        if arquivo.size > 5 * 1024 * 1024:
            erros['curriculo'] = 'O arquivo precisa ter até 5 MB.'
        elif not arquivo.name.lower().endswith(('.pdf', '.doc', '.docx')):
            erros['curriculo'] = 'Envie em PDF ou Word.'

    return dados, erros
