"""
Triagem de candidato por IA, sob demanda (tarefa 218, item 8).

A chamada de LLM e SEMPRE mockada: teste que bate na OpenAI seria lento, caro,
nao determinista e falharia sem rede. O que se testa aqui e o nosso lado.

O QUE ESTES TESTES DEFENDEM, em ordem de gravidade:

1. A IA NUNCA MOVE O CANDIDATO. E sugestao. Automatizar a recusa seria decidir
   contratacao por LLM, sem ninguem pra responder por ela.
2. RECUSA analisar sem requisito de triagem cadastrado. Sem criterio declarado,
   a IA inventa o proprio, e a "consistencia" que ela promete vira
   arbitrariedade com cara de objetividade.
3. Dado pessoal que NAO ajuda a avaliar nao vai pro prompt (nome, WhatsApp,
   email). Cada campo enviado e exposicao a um terceiro.
4. Resposta estranha do modelo nao vira lixo no banco nem 500 na tela.
"""
import json
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people.models import (
    AnaliseCandidato, Candidato, Cargo, EtapaPipeline, RequisitoVaga, Unidade,
    Vaga,
)
from apps.people.services.triagem_ia import (
    TriagemIndisponivel, _perfil_do_candidato, analisar_candidato,
)
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory

RESPOSTA_BOA = json.dumps({
    'veredito': 'apto',
    'resumo': 'Tem experiência em atendimento e mora perto da loja.',
    'sinais_de_atencao': ['Confirmar disponibilidade para fins de semana'],
    'requisitos': [
        {'requisito': 'Experiência com atendimento', 'atende': 'sim',
         'porque': 'Informou um ano como atendente.'},
    ],
})


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    vaga = Vaga.all_tenants.create(tenant=tenant, unidade=unidade, cargo=cargo,
                                   titulo='Atendente', status='publicada')
    RequisitoVaga.all_tenants.create(
        tenant=tenant, vaga=vaga, texto='Experiência com atendimento',
        obrigatorio=True, usar_na_triagem=True, aparece_no_anuncio=True)
    etapa = EtapaPipeline.all_tenants.get(tenant=tenant, nome='Triagem')
    candidato = Candidato.all_tenants.create(
        tenant=tenant, unidade=unidade, vaga=vaga, etapa=etapa,
        nome_completo='Vitória Russi', whatsapp='5589994395653',
        email='vitoria@exemplo.com', cidade='Teresina', bairro='Centro',
        experiencia_previa='1 ano como atendente',
        disponibilidade_horario='Qualquer horário')
    return {'tenant': tenant, 'unidade': unidade, 'vaga': vaga,
            'etapa': etapa, 'candidato': candidato}


def _cliente(cenario, funcionalidades=('people.ver', 'people.gerir_vagas')):
    user = User.objects.create_user(username='rh_ia', password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'], nome='P ia')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    c = Client()
    c.force_login(user)
    return c


class _IntegracaoFalsa:
    tipo = 'openai'
    base_url = ''
    configuracoes_extras = {'modelo': 'gpt-4o-mini'}


def _com_ia(resposta=RESPOSTA_BOA):
    """Substitui a integracao e a chamada. Devolve o mock do chamar_llm."""
    return (
        patch('apps.people.services.triagem_ia.integracao_ia_do_tenant',
              return_value=_IntegracaoFalsa()),
        patch('apps.people.services.triagem_ia.chamar_llm',
              return_value=resposta),
    )


# ── A garantia central: a IA nao decide ──────────────────────────────────────

@pytest.mark.django_db
def test_analise_nao_move_o_candidato(cenario):
    """
    O TESTE MAIS IMPORTANTE DESTE ARQUIVO.

    Mesmo com veredito "inapto", o candidato continua na etapa em que estava e
    sem saida. Automatizar a recusa seria decidir contratacao por LLM.
    """
    ruim = json.dumps({'veredito': 'inapto', 'resumo': 'Fora do perfil',
                       'sinais_de_atencao': [], 'requisitos': []})
    etapa_antes = cenario['candidato'].etapa_id

    p1, p2 = _com_ia(ruim)
    with p1, p2:
        analisar_candidato(cenario['candidato'])

    cenario['candidato'].refresh_from_db()
    assert cenario['candidato'].etapa_id == etapa_antes
    assert cenario['candidato'].saida == ''
    assert cenario['candidato'].historico.count() == 0


# ── Recusa quando nao ha o que avaliar ───────────────────────────────────────

@pytest.mark.django_db
def test_recusa_sem_requisito_de_triagem(cenario):
    """
    Sem criterio declarado a IA inventaria o proprio, e a consistencia que ela
    promete viraria arbitrariedade com cara de objetividade.
    """
    RequisitoVaga.all_tenants.filter(vaga=cenario['vaga']).update(
        usar_na_triagem=False)

    p1, p2 = _com_ia()
    with p1, p2, pytest.raises(TriagemIndisponivel, match='requisito'):
        analisar_candidato(cenario['candidato'])


@pytest.mark.django_db
def test_recusa_candidato_do_banco_de_talentos(cenario):
    """Sem vaga nao ha requisito contra o qual avaliar."""
    candidato = Candidato.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Sem Vaga', whatsapp='5586999990000')

    p1, p2 = _com_ia()
    with p1, p2, pytest.raises(TriagemIndisponivel, match='banco de talentos'):
        analisar_candidato(candidato)


@pytest.mark.django_db
def test_recusa_sem_integracao_de_ia(cenario):
    with patch('apps.people.services.triagem_ia.integracao_ia_do_tenant',
               return_value=None):
        with pytest.raises(TriagemIndisponivel, match='integração de IA'):
            analisar_candidato(cenario['candidato'])


# ── O que vai (e o que NAO vai) pro prompt ───────────────────────────────────

@pytest.mark.django_db
def test_dado_pessoal_inutil_para_avaliacao_nao_vai_pro_prompt(cenario):
    """
    Nome, WhatsApp e email nao ajudam a julgar aptidao e so aumentam a exposicao
    a um terceiro. Cidade e bairro ficam, porque deslocamento e criterio real.
    """
    perfil = _perfil_do_candidato(cenario['candidato'])

    assert 'Vitória' not in perfil
    assert '5589994395653' not in perfil
    assert 'vitoria@exemplo.com' not in perfil
    assert 'Teresina' in perfil
    assert '1 ano como atendente' in perfil


@pytest.mark.django_db
def test_o_prompt_leva_os_requisitos_da_vaga(cenario):
    p1, p2 = _com_ia()
    with p1, p2 as mock_llm:
        analisar_candidato(cenario['candidato'])

    mensagens = mock_llm.call_args[0][1]
    prompt = mensagens[-1]['content']
    assert 'Experiência com atendimento' in prompt
    assert 'OBRIGATÓRIO' in prompt


@pytest.mark.django_db
def test_campos_custom_entram_no_perfil(cenario):
    cenario['candidato'].dados_custom = {'cnh': 'Sim', 'turno': 'Noite'}
    cenario['candidato'].save()

    perfil = _perfil_do_candidato(cenario['candidato'])

    assert 'cnh: Sim' in perfil


# ── O resultado gravado ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_grava_a_analise(cenario):
    p1, p2 = _com_ia()
    with p1, p2:
        analise = analisar_candidato(cenario['candidato'])

    assert analise.veredito == AnaliseCandidato.VEREDITO_APTO
    assert 'atendimento' in analise.resumo
    assert analise.sinais_de_atencao == [
        'Confirmar disponibilidade para fins de semana']
    assert len(analise.requisitos_avaliados) == 1
    assert analise.usou_curriculo is False       # nao ha curriculo anexado


@pytest.mark.django_db
def test_cada_analise_e_uma_linha_nova(cenario):
    """
    Historico e nao registro unico: a vaga pode mudar de requisito e a pessoa
    ser reanalisada. Guardar so a ultima apagaria a base da decisao ja tomada.
    """
    p1, p2 = _com_ia()
    with p1, p2:
        analisar_candidato(cenario['candidato'])
        analisar_candidato(cenario['candidato'])

    assert cenario['candidato'].analises.count() == 2


# ── Resposta estranha do modelo ──────────────────────────────────────────────

@pytest.mark.django_db
def test_json_dentro_de_cerca_markdown_e_lido(cenario):
    """O modelo devolve ```json ... ``` mesmo mandado nao fazer."""
    p1, p2 = _com_ia(f'```json\n{RESPOSTA_BOA}\n```')
    with p1, p2:
        analise = analisar_candidato(cenario['candidato'])

    assert analise.veredito == AnaliseCandidato.VEREDITO_APTO


@pytest.mark.django_db
def test_resposta_que_nao_e_json_vira_erro_tratado(cenario):
    p1, p2 = _com_ia('Desculpe, não consigo ajudar com isso.')
    with p1, p2, pytest.raises(TriagemIndisponivel, match='formato esperado'):
        analisar_candidato(cenario['candidato'])


@pytest.mark.django_db
def test_veredito_inventado_cai_em_insuficiente(cenario):
    """
    Cair no lado seguro: "insuficiente" nao afirma nada sobre a pessoa e pede
    olho humano. Aceitar a categoria inventada gravaria lixo num campo que
    outras telas filtram.
    """
    p1, p2 = _com_ia(json.dumps({'veredito': 'talvez', 'resumo': 'x',
                                 'sinais_de_atencao': [], 'requisitos': []}))
    with p1, p2:
        analise = analisar_candidato(cenario['candidato'])

    assert analise.veredito == AnaliseCandidato.VEREDITO_INSUFICIENTE


@pytest.mark.django_db
def test_llm_sem_resposta_vira_erro_tratado(cenario):
    """`chamar_llm` devolve None em erro de rede ou credencial."""
    p1, p2 = _com_ia(None)
    with p1, p2, pytest.raises(TriagemIndisponivel):
        analisar_candidato(cenario['candidato'])


# ── Pela tela ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_analisa_pela_ficha_e_mostra_o_resultado(cenario):
    cliente = _cliente(cenario)

    p1, p2 = _com_ia()
    with p1, p2:
        cliente.post(reverse('people:candidato_analisar',
                             args=[cenario['candidato'].pk]))

    corpo = cliente.get(reverse('people:candidato_detalhe',
                                args=[cenario['candidato'].pk])).content.decode()
    assert 'Apto' in corpo
    assert 'É sugestão' in corpo
    assert 'Confirmar disponibilidade' in corpo


@pytest.mark.django_db
def test_erro_da_triagem_vira_mensagem_e_nao_500(cenario):
    RequisitoVaga.all_tenants.filter(vaga=cenario['vaga']).update(
        usar_na_triagem=False)

    p1, p2 = _com_ia()
    with p1, p2:
        resposta = _cliente(cenario).post(
            reverse('people:candidato_analisar', args=[cenario['candidato'].pk]),
            follow=True)

    assert resposta.status_code == 200
    assert 'requisito' in resposta.content.decode().lower()


@pytest.mark.django_db
def test_quem_so_ve_nao_analisa(cenario):
    cliente = _cliente(cenario, funcionalidades=('people.ver',))

    resposta = cliente.post(reverse('people:candidato_analisar',
                                    args=[cenario['candidato'].pk]))

    assert resposta.status_code == 403
