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
    assert candidato.etapa.nome == 'Análise de inscrição'


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
    assert ultimo.de_etapa == 'Análise de inscrição'
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
    assert 'Análise de inscrição' in corpo
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

    cliente = _cliente(cenario)

    # Na vista padrao o chip existe, entao ninguem fica invisivel
    corpo = cliente.get(reverse('people:pipeline_board')).content.decode()
    assert 'Fora de etapa' in corpo
    assert 'etapa=sem-etapa' in corpo

    # E clicar no chip lista quem esta la
    corpo = cliente.get(reverse('people:pipeline_board'),
                        {'etapa': 'sem-etapa'}).content.decode()
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


@pytest.mark.django_db
def test_card_tem_o_destino_da_ficha_mesmo_pra_quem_so_le(cenario):
    """
    Abrir a ficha e LEITURA, nao movimentacao.

    O JS do board tinha a navegacao dentro da guarda de `podeMover`, entao pra
    quem nao podia mover o card inteiro parava de clicar e sobrava so o link do
    nome. Este teste garante que o dado que o JS precisa (data-detalhe) sai no
    HTML mesmo pro usuario que so tem people.ver.
    """
    candidato = _candidato(cenario, nome_completo='So Leitura Ve')
    garantir_etapa_inicial(candidato)
    cliente = _cliente(cenario, username='so_le', funcionalidades=('people.ver',))

    # Na lista, o nome e link; no kanban, o card inteiro carrega o destino.
    corpo = cliente.get(reverse('people:pipeline_board')).content.decode()
    assert f'/people/candidatos/{candidato.pk}/' in corpo

    corpo = cliente.get(reverse('people:pipeline_board'),
                        {'vista': 'kanban'}).content.decode()
    assert f'data-detalhe="/people/candidatos/{candidato.pk}/"' in corpo


# ── Board novo: chips, saidas visiveis, lote (gaps 1 e 2) ────────────────────

@pytest.mark.django_db
def test_saida_aparece_no_board_com_contador(cenario):
    """
    O gap 1, que era quase um bug: antes o board filtrava saida vazia e quem ia
    pro Banco de Talentos sumia da interface, sem tela que chegasse nele.
    """
    candidato = _candidato(cenario, nome_completo='Foi Pro Banco')
    garantir_etapa_inicial(candidato)
    dar_saida(candidato, estados_rs.SAIDA_BANCO_TALENTOS, motivo='Sem vaga agora')

    corpo = _cliente(cenario).get(reverse('people:pipeline_board')).content.decode()

    # O chip da saida existe e conta
    assert 'Banco de talentos' in corpo
    assert f'?saida={estados_rs.SAIDA_BANCO_TALENTOS}' in corpo


@pytest.mark.django_db
def test_clicar_na_saida_lista_quem_esta_nela(cenario):
    candidato = _candidato(cenario, nome_completo='Achavel No Banco')
    garantir_etapa_inicial(candidato)
    dar_saida(candidato, estados_rs.SAIDA_BANCO_TALENTOS, motivo='Sem vaga agora')

    corpo = _cliente(cenario).get(
        reverse('people:pipeline_board'),
        {'saida': estados_rs.SAIDA_BANCO_TALENTOS}).content.decode()

    assert 'Achavel No Banco' in corpo
    assert 'Sem vaga agora' in corpo   # o motivo fica visivel


@pytest.mark.django_db
def test_lista_mostra_so_a_etapa_selecionada(cenario):
    """O board nao renderiza todas as fases de uma vez: seleciona uma."""
    na_triagem = _candidato(cenario, nome_completo='Esta Na Triagem')
    garantir_etapa_inicial(na_triagem)

    adiante = _candidato(cenario, nome_completo='Esta Adiante')
    garantir_etapa_inicial(adiante)
    mover_para_etapa(adiante, cenario['etapas'][3])

    corpo = _cliente(cenario).get(reverse('people:pipeline_board')).content.decode()

    # Default e a primeira etapa
    assert 'Esta Na Triagem' in corpo
    assert 'Esta Adiante' not in corpo


@pytest.mark.django_db
def test_candidato_em_etapa_desativada_tem_chip_proprio(cenario):
    candidato = _candidato(cenario, nome_completo='Ficou Fora')
    garantir_etapa_inicial(candidato)
    triagem = cenario['etapas'][0]
    triagem.ativa = False
    triagem.save()

    corpo = _cliente(cenario).get(reverse('people:pipeline_board'),
                                  {'etapa': 'sem-etapa'}).content.decode()

    assert 'Fora de etapa' in corpo
    assert 'Ficou Fora' in corpo


@pytest.mark.django_db
def test_busca_por_nome_filtra_a_lista(cenario):
    for nome in ['Maria Aparecida', 'Joao Pedro']:
        c = _candidato(cenario, nome_completo=nome)
        garantir_etapa_inicial(c)

    corpo = _cliente(cenario).get(reverse('people:pipeline_board'),
                                  {'busca': 'maria'}).content.decode()

    assert 'Maria Aparecida' in corpo
    assert 'Joao Pedro' not in corpo


@pytest.mark.django_db
def test_lote_move_varios_de_uma_vez(cenario):
    import json

    candidatos = []
    for nome in ['Um', 'Dois', 'Tres']:
        c = _candidato(cenario, nome_completo=nome)
        garantir_etapa_inicial(c)
        candidatos.append(c)

    destino = cenario['etapas'][2]
    resposta = _cliente(cenario).post(
        reverse('people:pipeline_lote'),
        data=json.dumps({'acao': 'etapa', 'etapa_id': destino.pk,
                         'ids': [c.pk for c in candidatos]}),
        content_type='application/json')

    assert resposta.status_code == 200
    assert resposta.json()['movidos'] == 3
    for c in candidatos:
        c.refresh_from_db()
        assert c.etapa_id == destino.pk


@pytest.mark.django_db
def test_lote_grava_historico_de_cada_um(cenario):
    """
    O lote passa pelos servicos, um a um, e nao por queryset.update(): update em
    massa passaria por cima do historico e deixaria o funil cego.
    """
    import json

    candidatos = []
    for nome in ['A', 'B']:
        c = _candidato(cenario, nome_completo=nome)
        garantir_etapa_inicial(c)
        candidatos.append(c)

    _cliente(cenario).post(
        reverse('people:pipeline_lote'),
        data=json.dumps({'acao': 'etapa', 'etapa_id': cenario['etapas'][1].pk,
                         'ids': [c.pk for c in candidatos]}),
        content_type='application/json')

    for c in candidatos:
        # entrada (garantir_etapa) + o movimento do lote
        assert HistoricoCandidato.all_tenants.filter(candidato=c).count() == 2


@pytest.mark.django_db
def test_lote_de_saida_exige_motivo(cenario):
    import json

    c = _candidato(cenario)
    garantir_etapa_inicial(c)

    resposta = _cliente(cenario).post(
        reverse('people:pipeline_lote'),
        data=json.dumps({'acao': 'saida', 'saida': estados_rs.SAIDA_INAPTO,
                         'motivo': '', 'ids': [c.pk]}),
        content_type='application/json')

    assert resposta.status_code == 400
    assert resposta.json().get('precisa_motivo') is True
    c.refresh_from_db()
    assert c.esta_no_pipeline


@pytest.mark.django_db
def test_lote_nao_alcanca_candidato_de_outro_tenant(cenario):
    """O id vem do cliente; quem decide de quem e o escopo de tenant."""
    import json
    import secrets

    outro = TenantFactory(modulo_people=True)
    unidade_alheia = Unidade.all_tenants.create(tenant=outro, nome='Deles',
                                                codigo='deles')
    alheio = Candidato.all_tenants.create(
        tenant=outro, unidade=unidade_alheia, nome_completo='Do Outro',
        whatsapp=''.join(str(secrets.randbelow(10)) for _ in range(11)))

    resposta = _cliente(cenario).post(
        reverse('people:pipeline_lote'),
        data=json.dumps({'acao': 'etapa', 'etapa_id': cenario['etapas'][1].pk,
                         'ids': [alheio.pk]}),
        content_type='application/json')

    alheio.refresh_from_db()
    assert resposta.json()['movidos'] == 0
    assert alheio.etapa_id is None
