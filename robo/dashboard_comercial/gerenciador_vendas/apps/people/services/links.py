"""
Ciclo de vida dos links publicos de auto cadastro.

Uma unidade pode ter VARIOS links ativos ao mesmo tempo, cada um com seu
contador. Isso e do produto real (ver GAPS-VISIO.md, gap 1): um link por
campanha, por turno ou por recrutador, e invalidar um nao pode derrubar os
outros.

Link nao se apaga, se desativa: a trilha de submissoes aponta pra ele, e saber
por qual link alguem entrou e parte da auditoria.
"""
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.people.models import LinkCadastroUnidade, SubmissaoLinkCadastro
from apps.people.services.configuracao import config_efetiva
from apps.people.utils import mascarar_cpf


TAMANHO_TOKEN = 32  # bytes; token_urlsafe devolve ~43 caracteres


def gerar_token():
    return secrets.token_urlsafe(TAMANHO_TOKEN)


def links_ativos(unidade):
    """Todos os links vivos da unidade, mais recentes primeiro."""
    return LinkCadastroUnidade.all_tenants.filter(unidade=unidade, ativo=True)


def link_ativo(unidade):
    """O link ativo mais recente. Atalho pra quando so um interessa."""
    return links_ativos(unidade).first()


@transaction.atomic
def criar_link(unidade, *, usuario=None, nome='', template=None, max_submissoes=None):
    """
    Cria mais um link pra unidade. Nao substitui os que ja existem.
    """
    config = config_efetiva(unidade)
    expira_em = None
    if config.link_expira_em_dias:
        expira_em = timezone.now() + timedelta(days=config.link_expira_em_dias)

    return LinkCadastroUnidade.all_tenants.create(
        tenant=unidade.tenant,
        unidade=unidade,
        nome=nome,
        token=gerar_token(),
        template=template,
        expira_em=expira_em,
        max_submissoes=max_submissoes,
        criado_por=usuario,
    )


@transaction.atomic
def rotacionar_link(link, *, usuario=None):
    """
    Invalida ESTE link e cria um substituto com a mesma configuracao.

    E a acao pra quando um link especifico vazou. Age sobre o link, nao sobre a
    unidade: os outros links da loja continuam valendo.
    """
    desativar_link(link, usuario=usuario)
    novo = criar_link(
        link.unidade, usuario=usuario, nome=link.nome,
        template=link.template, max_submissoes=link.max_submissoes,
    )
    novo.rotacionado_de = link
    novo.save(update_fields=['rotacionado_de'])
    return novo


def desativar_link(link, *, usuario=None):
    """Nunca deleta: a trilha de submissoes aponta pra ele."""
    link.ativo = False
    link.desativado_em = timezone.now()
    link.save(update_fields=['ativo', 'desativado_em'])
    return link


def reativar_link(link, *, usuario=None):
    link.ativo = True
    link.desativado_em = None
    link.save(update_fields=['ativo', 'desativado_em'])
    return link


def resolver_por_token(token):
    """
    Acha o link pela URL publica.

    Usa `all_tenants` de proposito: na view publica nao ha usuario logado, entao
    o TenantManager nao tem por onde filtrar. E justamente este link que vai
    dizer de qual tenant e o cadastro.
    """
    if not token:
        return None
    return (LinkCadastroUnidade.all_tenants
            .select_related('unidade', 'tenant', 'template')
            .filter(token=token)
            .first())


@transaction.atomic
def registrar_submissao(link, *, resultado, colaborador=None, erro='',
                        dados=None, ip='', user_agent=''):
    """
    Grava a submissao e conta no link.

    O contador sobe com select_for_update pra que rajada no mesmo link nao perca
    contagem, e ao bater o teto o link se desativa sozinho.
    """
    travado = (LinkCadastroUnidade.all_tenants
               .select_for_update()
               .get(pk=link.pk))

    if resultado != 'rejeitado':
        travado.submissoes += 1
        travado.ultima_submissao_em = timezone.now()
        campos = ['submissoes', 'ultima_submissao_em']

        if (travado.max_submissoes is not None
                and travado.submissoes >= travado.max_submissoes):
            travado.ativo = False
            travado.desativado_em = timezone.now()
            campos += ['ativo', 'desativado_em']

        travado.save(update_fields=campos)

    return SubmissaoLinkCadastro.all_tenants.create(
        tenant=travado.tenant,
        link=travado,
        colaborador=colaborador,
        resultado=resultado,
        erro=erro[:200],
        payload=_payload_seguro(dados or {}),
        ip_origem=ip[:64],
        user_agent=(user_agent or '')[:300],
    )


def _payload_seguro(dados):
    """
    Copia do que foi submetido, com o CPF mascarado.

    A pessoa ja esta registrada no Colaborador; isto aqui existe pra debugar e
    medir abuso, nao pra reconstruir a pessoa. Guardar documento inteiro em duas
    tabelas so aumenta a superficie de vazamento sem ganhar nada.
    """
    seguro = {}
    for chave, valor in dados.items():
        if chave == 'cpf':
            seguro[chave] = mascarar_cpf(valor)
        elif hasattr(valor, 'isoformat'):
            seguro[chave] = valor.isoformat()
        elif isinstance(valor, (str, int, float, bool)) or valor is None:
            seguro[chave] = valor
        else:
            seguro[chave] = str(valor)
    return seguro
