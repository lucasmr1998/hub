"""
Formulario publico de auto cadastro.

O colaborador de loja geralmente nao tem login. Ele recebe o link por WhatsApp,
abre no celular e preenche os proprios dados. Nao ha usuario autenticado em
nenhum momento aqui, e isso muda tudo:

- O TENANT vem do token do link, nao da sessao. Ver tenant_scope.py.
- O FORMULARIO vem do template configurado no link, nao de campos fixos.
- A RESPOSTA DE CONFLITO e generica de proposito: dizer "esse CPF ja existe"
  transformaria a pagina num oraculo de "fulano trabalha aqui?", aberto na
  internet.

Anti abuso: rate limit por IP e por token, honeypot, teto de submissoes no
proprio link, e CSRF ligado (o form e renderizado pelo Django, nao e webhook).
"""
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.people import estados
from apps.people.campos_formulario import CAMPOS_POR_NOME
from apps.people.forms import UFS
from apps.people.models import TIPO_CHAVE_PIX_CHOICES, TemplateFormulario
from apps.people.services import (
    config_efetiva, registrar_colaborador, registrar_submissao, resolver_por_token,
)
from apps.people.tenant_scope import escopo_tenant


MENSAGEM_CONFLITO = (
    'Ja existe um cadastro com esses dados. Procure o RH da sua unidade.'
)


def _ip(request):
    encaminhado = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if encaminhado:
        return encaminhado.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _link_ou_404(token):
    """
    404 generico pra token invalido, expirado, desativado ou de unidade
    inativa. Nunca diferencie: mensagens distintas transformam a pagina num
    oraculo de quais tokens ja existiram.
    """
    link = resolver_por_token(token)
    if link is None or not link.esta_valido() or not link.unidade.ativo:
        raise Http404
    return link


OPCOES_POR_CAMPO = {
    'estado': UFS,
    'tipo_chave_pix': TIPO_CHAVE_PIX_CHOICES,
}


def _campos_do_link(link, valores=None, erros=None):
    """
    Monta os campos ja resolvidos pro template: rotulo, tipo, valor digitado e
    erro. O template so itera e renderiza, sem filtro custom nem logica.
    """
    valores = valores or {}
    erros = erros or {}

    template = link.template or TemplateFormulario.padrao_do_tenant(link.tenant)
    campos = []
    for campo in template.campos_do_formulario():
        nome = campo['nome']
        campos.append({
            'nome': nome,
            'rotulo': campo['rotulo'],
            'tipo': campo['tipo'],
            'obrigatorio': campo['obrigatorio'],
            'descricao': campo.get('descricao', ''),
            'opcoes': OPCOES_POR_CAMPO.get(nome),
            'valor': valores.get(nome, ''),
            'erro': erros.get(nome, ''),
        })
    return template, campos


@require_http_methods(['GET'])
@ratelimit(key='ip', rate='30/m', block=True)
def formulario(request, token):
    link = _link_ou_404(token)

    with escopo_tenant(link.tenant):
        _, campos = _campos_do_link(link)
        config = config_efetiva(link.unidade)

    return render(request, 'people/publico_formulario.html', {
        'link': link, 'unidade': link.unidade, 'campos': campos,
        'config': config, 'erros': {},
    })


@require_http_methods(['POST'])
@ratelimit(key='ip', rate='5/m', block=True)
@ratelimit(key=lambda grupo, request: request.resolver_match.kwargs.get('token', ''),
           rate='20/h', block=True)
def enviar(request, token):
    """
    Recebe o cadastro.

    Toda leitura e escrita passa tenant explicito, mesmo dentro do escopo. E
    redundante de proposito: escopo protege o que e chamado indiretamente,
    explicito protege o que esta na nossa frente.
    """
    link = _link_ou_404(token)

    with escopo_tenant(link.tenant):
        config = config_efetiva(link.unidade)

        # Honeypot: campo escondido que humano nao ve. Preenchido, respondemos
        # sucesso falso pro robo nao aprender, e registramos como rejeitado.
        if request.POST.get('sobrenome_confirmacao'):
            registrar_submissao(
                link, resultado='rejeitado', erro='honeypot',
                ip=_ip(request), user_agent=request.META.get('HTTP_USER_AGENT', ''))
            return render(request, 'people/publico_ok.html', {'unidade': link.unidade})

        _, campos = _campos_do_link(link)
        dados, erros = _ler_e_validar(request, campos, config)

        if not request.POST.get('consentimento_lgpd'):
            erros['consentimento_lgpd'] = 'E preciso aceitar para enviar o cadastro.'

        if erros:
            _, campos = _campos_do_link(link, request.POST, erros)
            return render(request, 'people/publico_formulario.html', {
                'link': link, 'unidade': link.unidade, 'campos': campos,
                'config': config, 'erros': erros,
            }, status=400)

        resultado = registrar_colaborador(
            link.tenant, link.unidade, dados,
            origem='link_publico',
            situacao_inicial=estados.SITUACAO_CADASTRO,
        )

        if not resultado.ok:
            registrar_submissao(
                link, resultado='rejeitado', erro=resultado.motivo_conflito,
                dados=dados, ip=_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''))
            _, campos = _campos_do_link(link, request.POST)
            return render(request, 'people/publico_formulario.html', {
                'link': link, 'unidade': link.unidade, 'campos': campos,
                'config': config, 'erros': {'geral': MENSAGEM_CONFLITO},
            }, status=409)

        _gravar_consentimento(resultado.colaborador, request, config)
        registrar_submissao(
            link, resultado=resultado.acao, colaborador=resultado.colaborador,
            dados=dados, ip=_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''))

    return render(request, 'people/publico_ok.html', {'unidade': link.unidade})


def _ler_e_validar(request, campos, config):
    """
    Le so os campos que o template pede. Campo fora da lista nao entra, mesmo
    que venha no POST: quem posta aqui e a internet.
    """
    dados, erros = {}, {}

    for campo in campos:
        nome = campo['nome']
        valor = (request.POST.get(nome) or '').strip()

        if campo['obrigatorio'] and not valor:
            erros[nome] = f'{campo["rotulo"]} e obrigatorio.'
            continue
        if valor:
            dados[nome] = valor

    # O CPF tem uma exigencia propria, que vem da configuracao e nao do
    # template: e ele que sustenta o dedup do modulo inteiro.
    if config.exige_cpf_no_autocadastro and 'cpf' in CAMPOS_POR_NOME:
        pede_cpf = any(c['nome'] == 'cpf' for c in campos)
        if pede_cpf and not dados.get('cpf'):
            erros['cpf'] = 'CPF e obrigatorio.'

    return dados, erros


def _gravar_consentimento(colaborador, request, config):
    """
    Registra o aceite com IP, user agent e versao do texto.

    Sem a versao, um consentimento antigo pareceria valer pro texto novo, o que
    e justamente o que a LGPD nao aceita.
    """
    colaborador.consentimento_lgpd = True
    colaborador.consentimento_lgpd_em = timezone.now()
    colaborador.consentimento_lgpd_ip = _ip(request)[:64]
    colaborador.consentimento_lgpd_versao = config.versao_consentimento_lgpd
    colaborador.consentimento_lgpd_user_agent = (
        request.META.get('HTTP_USER_AGENT', '') or '')[:300]
    colaborador.save(update_fields=[
        'consentimento_lgpd', 'consentimento_lgpd_em', 'consentimento_lgpd_ip',
        'consentimento_lgpd_versao', 'consentimento_lgpd_user_agent',
        'atualizado_em',
    ])
