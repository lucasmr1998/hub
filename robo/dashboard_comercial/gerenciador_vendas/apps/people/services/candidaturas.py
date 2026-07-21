"""
Registro de candidatura.

Caminho unico de escrita de Candidato, no mesmo espirito do
`registrar_colaborador` do DP: quem quiser criar candidato passa por aqui, e o
dedup fica embutido em vez de depender de cada chamador lembrar.

Diferenca importante em relacao ao dedup do DP: la, duplicata devolve conflito
com os candidatos pro RH decidir. Aqui NAO. O formulario de candidatura e
publico e anonimo, e devolver qualquer coisa alem de uma mensagem generica
transformaria a pagina num oraculo de "fulano se candidatou aqui?", aberto na
internet. Quem resolve duplicata e o RH, pelo painel, buscando por nome.
"""
import re
from dataclasses import dataclass, field
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.people.models import Candidato, ConfiguracaoPeople


# Mensagem unica de conflito. Generica de proposito: nao confirma nem nega que o
# numero existe na base, nao diz de qual vaga, nao diz quando. Facil de errar
# quando alguem quiser "melhorar" e tornar util.
MENSAGEM_CONFLITO = (
    'Já recebemos uma candidatura com esses dados. Se precisar atualizar '
    'alguma informação, fale com o RH da unidade.'
)


@dataclass
class ResultadoCandidatura:
    """
    Nunca levanta excecao por duplicata: duplicata e fluxo normal, nao erro.
    Excecao aqui seria erro de programacao.
    """
    candidato: Candidato | None = None
    acao: str = 'criado'  # criado | duplicado
    erros: dict = field(default_factory=dict)

    @property
    def ok(self):
        return self.candidato is not None and not self.erros


def normalizar_whatsapp(valor):
    """
    So digitos, ou None.

    Vazio vira None e nunca string vazia: e a string vazia que quebraria a
    unique no segundo candidato sem numero.
    """
    return re.sub(r'\D', '', valor or '') or None


def _retencao_ate(tenant):
    """
    Ate quando o dado deste candidato pode ficar.

    Materializa a decisao D3 do plano: prazo declarado no consentimento e
    expurgo automatico. Gravado no registro, e nao calculado na hora do expurgo,
    porque o prazo pode mudar depois e quem se candidatou sob a regra antiga tem
    direito a ela.
    """
    config = ConfiguracaoPeople.get_config(tenant)
    dias = config.dias_retencao_candidato
    if not dias:
        return None
    return timezone.localdate() + timedelta(days=dias)


def registrar_candidatura(tenant, link, dados):
    """
    Cria o candidato a partir de uma submissao do formulario publico.

    `tenant` e primeiro parametro posicional obrigatorio de proposito, mesmo
    havendo `link.tenant`: torna impossivel esquecer o escopo na view publica,
    onde o thread local nao ajuda.
    """
    whatsapp = normalizar_whatsapp(dados.get('whatsapp'))

    if not whatsapp:
        return ResultadoCandidatura(
            erros={'whatsapp': 'Informe um WhatsApp para contato.'})

    with transaction.atomic():
        ja_existe = Candidato.all_tenants.filter(
            tenant=tenant, whatsapp=whatsapp).exists()
        if ja_existe:
            return ResultadoCandidatura(acao='duplicado',
                                        erros={'geral': MENSAGEM_CONFLITO})

        candidato = Candidato(
            tenant=tenant,
            unidade=link.unidade,
            vaga=link.vaga,
            link_origem=link,
            nome_completo=(dados.get('nome_completo') or '').strip(),
            whatsapp=whatsapp,
            email=(dados.get('email') or '').strip(),
            data_nascimento=dados.get('data_nascimento') or None,
            cidade=(dados.get('cidade') or '').strip(),
            estado=(dados.get('estado') or '').strip().upper()[:2],
            bairro=(dados.get('bairro') or '').strip(),
            experiencia_previa=(dados.get('experiencia_previa') or '').strip(),
            disponibilidade_horario=(dados.get('disponibilidade_horario') or '').strip(),
            dados_custom=dados.get('dados_custom') or {},
            curriculo=dados.get('curriculo') or None,
            retencao_ate=_retencao_ate(tenant),
        )

        try:
            candidato.save()
        except IntegrityError:
            # Corrida entre duas submissoes do mesmo numero no mesmo instante.
            # A checagem acima e TOCTOU; a constraint e que garante. Um mutirao
            # de divulgacao exercita isso de verdade.
            return ResultadoCandidatura(acao='duplicado',
                                        erros={'geral': MENSAGEM_CONFLITO})

    return ResultadoCandidatura(candidato=candidato, acao='criado')


def gravar_consentimento(candidato, request, config):
    """
    Registra o aceite com IP, versao do texto e user agent.

    Sem a versao, um aceite antigo pareceria valer pro texto novo, e a trilha
    de consentimento nao provaria nada.
    """
    candidato.consentimento_lgpd = True
    candidato.consentimento_em = timezone.now()
    candidato.consentimento_ip = _ip_do_request(request)
    candidato.consentimento_versao = config.versao_consentimento_lgpd
    candidato.consentimento_user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    candidato.save(update_fields=[
        'consentimento_lgpd', 'consentimento_em', 'consentimento_ip',
        'consentimento_versao', 'consentimento_user_agent', 'atualizado_em',
    ])


def contabilizar_candidatura(link):
    """
    Incrementa o contador do link. E a atribuicao de canal.

    F() e nao leitura mais soma: duas candidaturas simultaneas pelo mesmo link
    perderiam uma contagem, e o numero que justifica manter ou cortar um canal
    ficaria errado pra menos.
    """
    from django.db.models import F

    tipo = type(link)
    tipo.all_tenants.filter(pk=link.pk).update(
        candidaturas=F('candidaturas') + 1,
        ultima_candidatura_em=timezone.now(),
    )


def _ip_do_request(request):
    encaminhado = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if encaminhado:
        return encaminhado.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
