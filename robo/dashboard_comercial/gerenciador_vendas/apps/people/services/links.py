"""
Ciclo de vida do link publico de auto cadastro.

Um link ativo por unidade. Rotacionar significa invalidar o que esta circulando
(no grupo de WhatsApp da loja, num cartaz na parede) e por outro no lugar, sem
apagar o velho: a trilha de quem entrou por qual link e parte da auditoria.
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


def link_ativo(unidade):
    return LinkCadastroUnidade.all_tenants.filter(unidade=unidade, ativo=True).first()


@transaction.atomic
def criar_link(unidade, *, usuario=None, max_submissoes=None):
    """
    Cria o link da unidade. Se ja houver um ativo, devolve o que existe em vez
    de criar outro: a constraint parcial nao deixaria mesmo, e falhar aqui seria
    hostil com quem so clicou duas vezes.
    """
    existente = link_ativo(unidade)
    if existente is not None:
        return existente

    config = config_efetiva(unidade)
    expira_em = None
    if config.link_expira_em_dias:
        expira_em = timezone.now() + timedelta(days=config.link_expira_em_dias)

    return LinkCadastroUnidade.all_tenants.create(
        tenant=unidade.tenant,
        unidade=unidade,
        token=gerar_token(),
        expira_em=expira_em,
        max_submissoes=max_submissoes,
        criado_por=usuario,
    )


@transaction.atomic
def rotacionar_link(unidade, *, usuario=None):
    """
    Invalida o link atual e cria outro.

    A ordem importa e nao e simetrica: desativar PRIMEIRO, criar depois. A
    constraint parcial de um ativo por unidade nao deixaria os dois coexistirem,
    entao inverter a ordem daria IntegrityError. Aqui isso e garantia, nao
    acidente: se alguem reescrever isto ao contrario, quebra na hora em vez de
    deixar dois links vivos pra mesma loja.
    """
    anterior = link_ativo(unidade)
    if anterior is not None:
        desativar_link(anterior, usuario=usuario)

    novo = criar_link(unidade, usuario=usuario)
    if anterior is not None:
        novo.rotacionado_de = anterior
        novo.save(update_fields=['rotacionado_de'])
    return novo


def desativar_link(link, *, usuario=None):
    """Nunca deleta: a trilha de submissoes aponta pra ele."""
    link.ativo = False
    link.desativado_em = timezone.now()
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
            .select_related('unidade', 'tenant')
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
