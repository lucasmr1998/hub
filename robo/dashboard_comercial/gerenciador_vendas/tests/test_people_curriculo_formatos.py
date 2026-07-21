"""
Formatos de curriculo aceitos, e o conserto do ERR_UPLOAD_FILE_CHANGED.

SO PDF E WORD. Decisao do Lucas em 21/07, revertendo o suporte a imagem que eu
tinha entregue horas antes. O motivo e coerencia com a triagem por IA: ela le
PDF e nao le foto, o que exigiria OCR. Aceitar imagem produziria candidato que
entra no sistema mas nao pode ser triado, e uma fila de curriculos que ninguem
consegue processar e pior que a recusa na porta.

CONSEQUENCIA que estes testes registram: quem so tem foto do curriculo impresso
nao anexa. Com o curriculo marcado como obrigatorio numa vaga, essa pessoa nao
se candidata. As duas configuracoes andam juntas.

O PROBLEMA QUE CONTINUA RESOLVIDO:

Um candidato real bateu no ERR_UPLOAD_FILE_CHANGED do Chrome, que aborta o
   envio no aparelho quando o arquivo muda entre a selecao e o submit. O
   conserto e no template (troca o arquivo por uma copia em memoria) e por isso
   nao da pra testar aqui; o que se testa e que a marcacao que ele depende
   continua existindo.

O QUE ESTES TESTES DEFENDEM DE VERDADE: que os TRES lugares que falam de formato
(o `accept` do campo, a validacao do POST e o texto que o candidato le) continuem
saindo da mesma lista. Foi exatamente essa divergencia que fez o honeypot parar
de funcionar em silencio hoje de manha.
"""
import secrets

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.people import campos_candidatura as catalogo
from apps.people.models import Candidato, Cargo, LinkCandidatura, Unidade, Vaga
from apps.sistema.models import ConfiguracaoEmpresa
from tests.factories import TenantFactory


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    vaga = Vaga.all_tenants.create(tenant=tenant, unidade=unidade, cargo=cargo,
                                   status='publicada')
    link = LinkCandidatura.all_tenants.create(
        tenant=tenant, vaga=vaga, unidade=unidade, canal='instagram',
        token=secrets.token_urlsafe(16))
    return {'tenant': tenant, 'unidade': unidade, 'vaga': vaga, 'link': link}


@pytest.fixture(autouse=True)
def sem_rate_limit(settings):
    """
    Desliga o rate limit, no mesmo padrao de test_people_candidatura_publica.

    Todos os testes saem do mesmo IP, e o limite de 5 POSTs por minuto e
    COMPARTILHADO com os outros arquivos de teste que batem neste endpoint. Sem
    isto, estes testes passam sozinhos e falham na suite completa, dependendo de
    quem rodou antes. Foi exatamente o que aconteceu ao criar este arquivo.
    """
    settings.RATELIMIT_ENABLE = False


def _enviar(cenario, arquivo=None, nome='Candidata Teste'):
    dados = {'nome_completo': nome, 'whatsapp': '86999997777',
             'consentimento_lgpd': 'on'}
    if arquivo is not None:
        dados['curriculo'] = arquivo
    return Client().post(f'/people/candidatura/{cenario["link"].token}/enviar/',
                         dados)


# ── Os tres lugares saem da mesma lista ──────────────────────────────────────

def test_accept_do_campo_sai_da_lista_de_extensoes():
    campo = catalogo.CAMPOS_POR_NOME['curriculo']

    assert campo['accept'] == ','.join(catalogo.EXTENSOES_CURRICULO)


def test_texto_de_ajuda_diz_o_formato_e_o_limite_real():
    ajuda = catalogo.CAMPOS_POR_NOME['curriculo']['ajuda']

    assert 'PDF' in ajuda
    assert str(catalogo.TAMANHO_MAX_CURRICULO_MB) in ajuda


def test_imagem_NAO_e_aceita():
    """
    Trava a decisao do Lucas. A IA de triagem le PDF e nao le foto: aceitar
    imagem produziria candidato que entra e nao pode ser triado. Se alguem
    reabrir isso, tem que decidir OCR junto.
    """
    for extensao in ('.jpg', '.jpeg', '.png', '.webp', '.heic'):
        assert extensao not in catalogo.EXTENSOES_CURRICULO, extensao
        assert catalogo.curriculo_aceito(f'curriculo{extensao}') is False


@pytest.mark.parametrize('nome,esperado', [
    ('curriculo.pdf', True),
    ('CURRICULO.PDF', True),        # extensao maiuscula
    ('cv.docx', True),
    ('foto-do-cv.jpg', False),
    ('scan.png', False),
    ('arquivo.exe', False),
    ('planilha.xlsx', False),
    ('sem_extensao', False),
    ('', False),
    (None, False),
])
def test_curriculo_aceito(nome, esperado):
    assert catalogo.curriculo_aceito(nome) is esperado


# ── Ponta a ponta pelo formulario publico ────────────────────────────────────

@pytest.mark.django_db
def test_candidatura_com_foto_e_recusada(cenario):
    """
    Decisao de produto, e nao limitacao tecnica. Se um dia aceitarmos imagem,
    a triagem por IA precisa de OCR no mesmo pacote, senao entra candidato que
    o sistema nao consegue processar.
    """
    foto = SimpleUploadedFile('curriculo.jpg', b'\xff\xd8\xff' + b'x' * 500,
                              content_type='image/jpeg')

    resposta = _enviar(cenario, foto, nome='Marina Foto')

    assert resposta.status_code == 400
    assert not Candidato.all_tenants.filter(nome_completo='Marina Foto').exists()


@pytest.mark.django_db
def test_candidatura_com_pdf_e_aceita(cenario):
    pdf = SimpleUploadedFile('curriculo.pdf', b'%PDF-1.4' + b'x' * 500,
                             content_type='application/pdf')

    _enviar(cenario, pdf, nome='Marina PDF')

    candidato = Candidato.all_tenants.get(nome_completo='Marina PDF')
    assert candidato.curriculo.name.endswith('.pdf')


@pytest.mark.django_db
def test_formato_nao_aceito_e_recusado_com_a_lista_no_erro(cenario):
    """A mensagem tem que dizer o que serve, e nao so que aquilo nao serve."""
    ruim = SimpleUploadedFile('virus.exe', b'MZ' + b'x' * 100,
                              content_type='application/octet-stream')

    resposta = _enviar(cenario, ruim, nome='Nao Deve Entrar')

    assert resposta.status_code == 400
    corpo = resposta.content.decode()
    assert 'PDF' in corpo
    assert not Candidato.all_tenants.filter(
        nome_completo='Nao Deve Entrar').exists()


@pytest.mark.django_db
def test_arquivo_grande_demais_e_recusado_com_o_limite_do_catalogo(cenario):
    limite = catalogo.TAMANHO_MAX_CURRICULO_MB
    grande = SimpleUploadedFile('cv.pdf', b'x' * ((limite * 1024 * 1024) + 1024),
                                content_type='application/pdf')

    resposta = _enviar(cenario, grande, nome='Arquivo Grande')

    assert resposta.status_code == 400
    assert f'{limite} MB' in resposta.content.decode()
    assert not Candidato.all_tenants.filter(
        nome_completo='Arquivo Grande').exists()


@pytest.mark.django_db
def test_sem_curriculo_continua_passando_quando_nao_e_obrigatorio(cenario):
    """
    O padrao de fabrica e curriculo OPCIONAL, e de proposito: cada campo
    obrigatorio a mais e gente desistindo no meio.
    """
    _enviar(cenario, None, nome='Sem Anexo')

    assert Candidato.all_tenants.filter(nome_completo='Sem Anexo').exists()


# ── O conserto do ERR_UPLOAD_FILE_CHANGED ────────────────────────────────────

@pytest.mark.django_db
def test_o_formulario_carrega_o_conserto_do_upload(cenario):
    """
    O conserto vive no template: le os bytes na selecao e troca o arquivo do
    input por uma copia em memoria, pra o Chrome nao ter o que reconferir no
    submit. Se alguem apagar esse bloco, o erro volta e ninguem percebe, porque
    ele acontece no aparelho do candidato e nao gera log nenhum aqui.
    """
    corpo = Client().get(
        f'/people/candidatura/{cenario["link"].token}/').content.decode()

    assert 'DataTransfer' in corpo
    assert 'arrayBuffer' in corpo
    assert '.pdf' in corpo
    assert '.heic' not in corpo
