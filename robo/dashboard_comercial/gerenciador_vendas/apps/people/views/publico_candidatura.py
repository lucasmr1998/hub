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
from apps.people.utils import NOME_HONEYPOT, e_robo
from apps.sistema.utils import registrar_acao


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
        'nome_honeypot': NOME_HONEYPOT,
    }


@require_http_methods(['GET'])
@ratelimit(key='ip', rate='30/m', block=True)
def formulario(request, token):
    link = _link_ou_404(token)

    with escopo_tenant(link.tenant):
        config = ConfiguracaoPeople.get_config(link.tenant)

    contexto = _contexto(link)
    contexto['config'] = config
    resposta = render(request, 'people/candidatura_formulario.html', contexto)
    return _contar_visita(request, resposta, link)


def _contar_visita(request, resposta, link):
    """
    Conta VISITANTE, e nao acesso, e devolve a resposta com o cookie marcado.

    Contar acesso deixaria numerador e denominador em unidades diferentes: a
    candidatura e uma pessoa, entao a taxa so significa alguma coisa se a visita
    tambem for. Recarregar a pagina, ou voltar pra corrigir um campo, e comum num
    formulario e infla o numero sem ninguem novo ter chegado.

    COOKIE PROPRIO, e nao a sessao do Django, de proposito: a sessao mora numa
    tabela do banco e o `clearsessions` nao roda em lugar nenhum do projeto
    (prod tinha 144 linhas, 100 ja vencidas). Criar uma sessao por visitante
    anonimo de QR faria essa virar a tabela que mais cresce, sem nada limpando.
    Este cookie nao gera linha nenhuma.

    Nada de dado pessoal aqui, e nao por acaso: quem so visitou nao consentiu
    com nada. O cookie diz apenas "ja contei este visitante neste link".

    LIMITES ASSUMIDOS, ambos errando PRA CIMA (a taxa real e melhor que a
    exibida, nunca pior): quem bloqueia cookie conta a cada visita, e quem abre
    no celular e depois no computador conta duas.
    """
    from django.db.models import F

    if e_robo(request.META.get('HTTP_USER_AGENT', '')):
        return resposta

    chave = f'hv{link.pk}'
    if request.COOKIES.get(chave):
        return resposta

    # F() em vez de ler, somar e gravar: dois visitantes no mesmo instante
    # perderiam uma visita, e um QR em evento exercita isso de verdade.
    LinkCandidatura.all_tenants.filter(pk=link.pk).update(
        visitas=F('visitas') + 1)

    resposta.set_cookie(chave, '1', max_age=30 * 24 * 3600,
                        samesite='Lax', httponly=True)
    return resposta


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
        #
        # O campo NAO pode ter nome de dado pessoal. Ele se chamava
        # `sobrenome_confirmacao`, e o Chrome ignora autocomplete=off em campo
        # que parece nome, entao o preenchedor automatico caia nele: candidato
        # real via a tela de sucesso e a candidatura era descartada. Aconteceu
        # em prod em 21/07 e nao deixou rastro nenhum.
        #
        # Por isso a rejeicao agora e REGISTRADA. Honeypot que falha em silencio
        # nao tem como ser auditado, e falso positivo custa candidato.
        if request.POST.get(NOME_HONEYPOT):
            registrar_acao(
                'people', 'rejeitar', 'candidatura', link.pk,
                f'Candidatura descartada pelo honeypot no link {link.pk} '
                f'({link.get_canal_display()}). Se houver reclamacao de '
                f'candidato que "enviou e nao apareceu", comecar por aqui.',
                request=request, tenant=link.tenant)
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
    # Extensoes e limite saem do catalogo, nao chumbados aqui: sao os mesmos que
    # alimentam o `accept` do campo e o texto que o candidato le.
    arquivo = dados.get('curriculo')
    if arquivo:
        limite = catalogo.TAMANHO_MAX_CURRICULO_MB
        if arquivo.size > limite * 1024 * 1024:
            erros['curriculo'] = f'O arquivo precisa ter até {limite} MB.'
        elif not catalogo.curriculo_aceito(arquivo.name):
            erros['curriculo'] = (
                f'Envie em {catalogo.rotulo_formatos_curriculo()}.')

    return dados, erros
