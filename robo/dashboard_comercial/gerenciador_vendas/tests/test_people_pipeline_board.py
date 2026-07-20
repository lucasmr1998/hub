"""
Board do pipeline: mover, sair, reabrir, e o historico que alimenta o funil.

Cobre a diferenca em relacao ao board do DP: mover entre etapas e livre, sair
exige motivo e passa por regra, e etapa desativada nao some o candidato.
"""
import secrets

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people import estados_recrutamento as estados_rs
from apps.people.models import (
    Cargo, Candidato, EtapaPipeline, HistoricoCandidato, Unidade, Vaga,
)
from apps.people.models_recrutamento import JUSTIFICATIVA_AUMENTO
from apps.people.services.pipeline import (
    dar_saida, garantir_etapa_inicial, mover_para_etapa,
)
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
from tests.factories import TenantFactory


@pytest.fixture
def cenario(db):
    tenant = TenantFactory(modulo_people=True)  # signal ja semeia as 7 etapas
    ConfiguracaoEmpresa.all_tenants.create(tenant=tenant,
                                           nome_empresa=tenant.nome, ativo=True)
    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='loja-centro')
    cargo = Cargo.all_tenants.create(tenant=tenant, nome='Atendente')
    vaga = Vaga.all_tenants.create(tenant=tenant, unidade=unidade, cargo=cargo,
                                   justificativa=JUSTIFICATIVA_AUMENTO)
    etapas = list(EtapaPipeline.do_escopo(tenant).order_by('ordem'))
    return {'tenant': tenant, 'unidade': unidade, 'cargo': cargo, 'vaga': vaga,
            'etapas': etapas}


def _candidato(cenario, **kwargs):
    dados = {'tenant': cenario['tenant'], 'unidade': cenario['unidade'],
             'vaga': cenario['vaga'], 'nome_completo': 'Candidato Teste',
             'whatsapp': secrets.token_hex(5)[:11]}
    dados.update(kwargs)
    # whatsapp precisa ser digito
    dados['whatsapp'] = ''.join(c for c in dados['whatsapp'] if c.isdigit()).ljust(11, '9')[:11]
    return Candidato.all_tenants.create(**dados)


def _cliente(cenario, username='rh_pipeline', funcionalidades=('people.ver', 'people.gerir_vagas')):
    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'],
                                            nome=f'Perfil {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    cliente = Client()
    cliente.force_login(user)
    return cliente


# ── garantir_etapa_inicial ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_candidato_novo_cai_na_primeira_etapa(cenario):
    candidato = _candidato(cenario)
    assert candidato.etapa_id is None

    garantir_etapa_inicial(candidato)

    candidato.refresh_from_db()
    assert candidato.etapa.nome == 'Triagem'


@pytest.mark.django_db
def test_garantir_etapa_e_idempotente(cenario):
    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)
    # O servico sincroniza a etapa de volta no objeto passado, entao ler aqui
    # ja da a etapa real, sem refresh.
    etapa_original = candidato.etapa_id
    assert etapa_original is not None

    # Ja tem etapa: nao move de novo
    garantir_etapa_inicial(candidato)

    candidato.refresh_from_db()
    assert candidato.etapa_id == etapa_original


# ── Mover entre etapas ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_mover_entre_etapas_e_livre(cenario):
    """Etapa e configuracao, nao maquina: pular do 1 pro 5 e permitido."""
    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)

    quinta = cenario['etapas'][4]
    mover_para_etapa(candidato, quinta)

    candidato.refresh_from_db()
    assert candidato.etapa_id == quinta.pk


@pytest.mark.django_db
def test_mover_grava_historico(cenario):
    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)
    mover_para_etapa(candidato, cenario['etapas'][2])

    historico = HistoricoCandidato.all_tenants.filter(
        candidato=candidato).order_by('criado_em')

    # entrada (garantir_etapa) + 1 movimento
    assert historico.count() == 2
    ultimo = historico.last()
    assert ultimo.de_etapa == 'Triagem'
    assert ultimo.para_etapa == cenario['etapas'][2].nome


@pytest.mark.django_db
def test_mover_pra_etapa_de_outro_tenant_falha(cenario):
    outro = TenantFactory(modulo_people=True)
    etapa_alheia = EtapaPipeline.do_escopo(outro).first()

    candidato = _candidato(cenario)

    with pytest.raises(ValueError):
        mover_para_etapa(candidato, etapa_alheia)


# ── Saida ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_dar_saida_com_motivo_tira_do_pipeline(cenario):
    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)

    dar_saida(candidato, estados_rs.SAIDA_BANCO_TALENTOS,
              motivo='Perfil bom, sem vaga agora')

    candidato.refresh_from_db()
    assert candidato.saida == estados_rs.SAIDA_BANCO_TALENTOS
    assert not candidato.esta_no_pipeline


@pytest.mark.django_db
def test_saida_sem_motivo_levanta(cenario):
    from apps.people.excecoes import CampoObrigatorioFaltando

    candidato = _candidato(cenario)

    with pytest.raises(CampoObrigatorioFaltando):
        dar_saida(candidato, estados_rs.SAIDA_INAPTO, motivo='')


@pytest.mark.django_db
def test_saida_grava_motivo_no_historico(cenario):
    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)

    dar_saida(candidato, estados_rs.SAIDA_INAPTO, motivo='Não compareceu à entrevista')

    ultimo = HistoricoCandidato.all_tenants.filter(candidato=candidato).first()
    assert ultimo.para_saida == estados_rs.SAIDA_INAPTO
    assert ultimo.motivo == 'Não compareceu à entrevista'


# ── Reabrir ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_reabrir_do_banco_volta_pro_pipeline(cenario):
    from apps.people.services.pipeline import reabrir

    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)
    dar_saida(candidato, estados_rs.SAIDA_BANCO_TALENTOS, motivo='Sem vaga')
    candidato.refresh_from_db()

    reabrir(candidato, cenario['etapas'][0])

    candidato.refresh_from_db()
    assert candidato.esta_no_pipeline
    assert candidato.saida == ''


@pytest.mark.django_db
def test_admitido_ja_vinculado_nao_reabre(cenario):
    from apps.people.excecoes import TransicaoInvalida
    from apps.people.models import Colaborador
    from apps.people.services.pipeline import reabrir

    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)
    dar_saida(candidato, estados_rs.SAIDA_ADMITIDO, motivo='Aprovado')
    candidato.refresh_from_db()

    # Simula a ponte pro DP tendo criado o colaborador
    colaborador = Colaborador.all_tenants.create(
        tenant=cenario['tenant'], unidade=cenario['unidade'],
        nome_completo='Candidato Teste')
    candidato.colaborador = colaborador
    candidato.save(update_fields=['colaborador'])

    with pytest.raises(TransicaoInvalida):
        reabrir(candidato, cenario['etapas'][0])


# ── Board (render e endpoints) ───────────────────────────────────────────────

@pytest.mark.django_db
def test_board_renderiza_as_colunas_das_etapas(cenario):
    candidato = _candidato(cenario, nome_completo='Maria Board')
    garantir_etapa_inicial(candidato)

    resposta = _cliente(cenario).get(reverse('people:pipeline_board'))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert 'Triagem' in corpo
    assert 'Admissão' in corpo
    assert 'Maria Board' in corpo


@pytest.mark.django_db
def test_endpoint_mover_troca_de_etapa(cenario):
    import json

    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)
    destino = cenario['etapas'][3]

    resposta = _cliente(cenario).post(
        reverse('people:pipeline_mover', args=[candidato.pk]),
        data=json.dumps({'etapa_id': destino.pk}),
        content_type='application/json')

    candidato.refresh_from_db()
    assert resposta.status_code == 200
    assert candidato.etapa_id == destino.pk


@pytest.mark.django_db
def test_endpoint_saida_sem_motivo_pede_motivo(cenario):
    import json

    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)

    resposta = _cliente(cenario).post(
        reverse('people:pipeline_saida', args=[candidato.pk]),
        data=json.dumps({'saida': estados_rs.SAIDA_INAPTO, 'motivo': ''}),
        content_type='application/json')

    assert resposta.status_code == 400
    assert resposta.json().get('precisa_motivo') is True
    candidato.refresh_from_db()
    assert candidato.esta_no_pipeline


@pytest.mark.django_db
def test_quem_so_ve_nao_move(cenario):
    import json

    candidato = _candidato(cenario)
    garantir_etapa_inicial(candidato)
    cliente = _cliente(cenario, username='so_ve', funcionalidades=('people.ver',))

    resposta = cliente.post(
        reverse('people:pipeline_mover', args=[candidato.pk]),
        data=json.dumps({'etapa_id': cenario['etapas'][2].pk}),
        content_type='application/json')

    assert resposta.status_code == 403


# ── Etapa desativada nao some o candidato ────────────────────────────────────

@pytest.mark.django_db
def test_candidato_em_etapa_desativada_aparece_fora_de_etapa(cenario):
    candidato = _candidato(cenario, nome_completo='Fica Visivel')
    garantir_etapa_inicial(candidato)

    # Desativa a Triagem, onde ele esta
    triagem = cenario['etapas'][0]
    triagem.ativa = False
    triagem.save()

    resposta = _cliente(cenario).get(reverse('people:pipeline_board'))
    corpo = resposta.content.decode()

    assert 'Fora de etapa' in corpo
    assert 'Fica Visivel' in corpo


# ── Board so mostra quem esta no pipeline ────────────────────────────────────

@pytest.mark.django_db
def test_quem_saiu_nao_aparece_no_board(cenario):
    ativo = _candidato(cenario, nome_completo='Ainda no processo')
    garantir_etapa_inicial(ativo)

    saiu = _candidato(cenario, nome_completo='Ja foi pro banco')
    garantir_etapa_inicial(saiu)
    dar_saida(saiu, estados_rs.SAIDA_BANCO_TALENTOS, motivo='Sem vaga')

    corpo = _cliente(cenario).get(reverse('people:pipeline_board')).content.decode()

    assert 'Ainda no processo' in corpo
    assert 'Ja foi pro banco' not in corpo


@pytest.mark.django_db
def test_candidato_anonimizado_nao_aparece(cenario):
    candidato = _candidato(cenario, nome_completo='Sera Anonimizado')
    garantir_etapa_inicial(candidato)
    candidato.anonimizar()

    corpo = _cliente(cenario).get(reverse('people:pipeline_board')).content.decode()

    assert 'Sera Anonimizado' not in corpo
