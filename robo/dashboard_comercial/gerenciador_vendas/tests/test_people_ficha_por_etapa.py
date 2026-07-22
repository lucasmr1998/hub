"""
Ficha do candidato organizada por etapa, e o perfil Avaliador (itens 5 e 4).

DECISAO DE PRODUTO DO LUCAS (21/07, opcao A): a ficha passa a ser onde o
processo acontece, e nao so consulta. Cada etapa tem aba propria com as
anotacoes daquela fase.

A DIFERENCA EM RELACAO A ORIGEM, e o que estes testes protegem: la as abas sao
FIXAS (Perfil comportamental, Entrevista RH, Teste Pratico...), porque o
pipeline e fixo. Aqui etapa e DADO: o cliente cria, renomeia e reordena em
/people/fluxo/. As abas sao GERADAS das etapas configuradas, e chumbar quebraria
isso no primeiro cliente que mexer no fluxo.

O PERFIL AVALIADOR existe com USUARIO, e nao como link publico sem login, que e
como a origem faz. Decisao do Lucas: link publico e pra quem esta FORA da empresa
(candidato, recem contratado); quem esta dentro tem conta.
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.people.models import (
    AnotacaoEtapa, Candidato, Cargo, EtapaPipeline, Unidade, Vaga,
)
from apps.sistema.models import (
    ConfiguracaoEmpresa, Funcionalidade, PerfilPermissao, PerfilUsuario,
    PermissaoUsuario,
)
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
    etapa = EtapaPipeline.all_tenants.get(tenant=tenant, nome='Entrevista / Seleção')
    candidato = Candidato.all_tenants.create(
        tenant=tenant, unidade=unidade, vaga=vaga, etapa=etapa,
        nome_completo='Diego Melo', whatsapp='5586999991111')
    return {'tenant': tenant, 'unidade': unidade, 'vaga': vaga,
            'etapa': etapa, 'candidato': candidato}


def _cliente(cenario, username='rh_ficha',
             funcionalidades=('people.ver', 'people.gerir_vagas', 'people.avaliar')):
    user = User.objects.create_user(username=username, password='x')
    PerfilUsuario.objects.create(user=user, tenant=cenario['tenant'])
    perfil = PerfilPermissao.objects.create(tenant=cenario['tenant'],
                                            nome=f'P {username}')
    for codigo in funcionalidades:
        func, _ = Funcionalidade.objects.get_or_create(
            codigo=codigo, defaults={'modulo': 'people', 'nome': codigo, 'ordem': 0})
        perfil.funcionalidades.add(func)
    PermissaoUsuario.objects.create(user=user, tenant=cenario['tenant'], perfil=perfil)
    c = Client()
    c.force_login(user)
    return c


def _ficha(cenario, cliente=None):
    cliente = cliente or _cliente(cenario)
    return cliente.get(reverse('people:candidato_detalhe',
                               args=[cenario['candidato'].pk])).content.decode()


# ── As abas saem das etapas configuradas ─────────────────────────────────────

@pytest.mark.django_db
def test_uma_aba_por_etapa_do_fluxo(cenario):
    corpo = _ficha(cenario)

    for etapa in EtapaPipeline.do_escopo(cenario['tenant']):
        assert f'tab-etapa-{etapa.pk}' in corpo, etapa.nome


@pytest.mark.django_db
def test_etapa_criada_pelo_cliente_vira_aba(cenario):
    """
    O TESTE QUE JUSTIFICA A ESCOLHA. Se as abas fossem chumbadas como na
    origem, uma etapa nova nao apareceria, e a tela de fluxo viraria mentira.
    """
    nova = EtapaPipeline.all_tenants.create(
        tenant=cenario['tenant'], nome='Teste em campo', ordem=99)

    corpo = _ficha(cenario)

    assert f'tab-etapa-{nova.pk}' in corpo
    assert 'Teste em campo' in corpo


@pytest.mark.django_db
def test_etapa_renomeada_muda_o_rotulo_da_aba(cenario):
    cenario['etapa'].nome = 'Entrevista técnica'
    cenario['etapa'].save()

    assert 'Entrevista técnica' in _ficha(cenario)


@pytest.mark.django_db
def test_a_aba_de_movimentacoes_nao_colide_com_a_etapa_historico(cenario):
    """
    O cliente pode nomear uma etapa de "Histórico". Duas abas com o mesmo rotulo,
    significando coisas diferentes (a etapa versus o log de movimento), e
    confusao garantida. A aba fixa se chama "Movimentações".
    """
    # "Histórico" saiu do seed (nao existe no produto real), porem o CLIENTE
    # pode criar uma etapa com esse nome. A aba fixa nao pode colidir com ela.
    etapa_historico = EtapaPipeline.all_tenants.create(
        tenant=cenario['tenant'], nome='Histórico', ordem=98,
        blocos=['anotacao'])

    corpo = _ficha(cenario)

    assert 'Movimentações' in corpo
    assert f'tab-etapa-{etapa_historico.pk}' in corpo


@pytest.mark.django_db
def test_a_aba_da_etapa_atual_e_marcada(cenario):
    corpo = _ficha(cenario)

    assert 'Está aqui agora' in corpo


# ── Anotacoes por etapa ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_salva_anotacao_na_etapa(cenario):
    _cliente(cenario).post(
        reverse('people:candidato_anotar_etapa',
                args=[cenario['candidato'].pk, cenario['etapa'].pk]),
        {'texto': 'Chegou no horário e demonstrou interesse.'})

    anotacao = AnotacaoEtapa.all_tenants.get(candidato=cenario['candidato'])
    assert anotacao.etapa_id == cenario['etapa'].pk
    assert 'horário' in anotacao.texto


@pytest.mark.django_db
def test_anotacoes_de_etapas_diferentes_nao_se_misturam(cenario):
    """
    E a razao de ser por etapa. Numa contratacao contestada depois, "o que o
    entrevistador anotou na Selecao" e pergunta diferente de "o que o gestor
    anotou na Avaliacao".
    """
    outra = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                          nome='Avaliação Gestor')
    cliente = _cliente(cenario)

    for etapa, texto in ((cenario['etapa'], 'Da seleção'), (outra, 'Do gestor')):
        cliente.post(reverse('people:candidato_anotar_etapa',
                             args=[cenario['candidato'].pk, etapa.pk]),
                     {'texto': texto})

    anotacoes = {a.etapa_id: a.texto for a in
                 AnotacaoEtapa.all_tenants.filter(candidato=cenario['candidato'])}
    assert anotacoes[cenario['etapa'].pk] == 'Da seleção'
    assert anotacoes[outra.pk] == 'Do gestor'


@pytest.mark.django_db
def test_salvar_de_novo_sobrescreve_em_vez_de_duplicar(cenario):
    cliente = _cliente(cenario)
    url = reverse('people:candidato_anotar_etapa',
                  args=[cenario['candidato'].pk, cenario['etapa'].pk])

    cliente.post(url, {'texto': 'primeira versão'})
    cliente.post(url, {'texto': 'segunda versão'})

    anotacoes = AnotacaoEtapa.all_tenants.filter(candidato=cenario['candidato'])
    assert anotacoes.count() == 1
    assert anotacoes.first().texto == 'segunda versão'


@pytest.mark.django_db
def test_texto_vazio_apaga_a_anotacao(cenario):
    """
    Anotacao em branco e indistinguivel de nao ter anotacao, e deixar as duas
    conviverem faria a bolinha da aba mentir.
    """
    cliente = _cliente(cenario)
    url = reverse('people:candidato_anotar_etapa',
                  args=[cenario['candidato'].pk, cenario['etapa'].pk])

    cliente.post(url, {'texto': 'alguma coisa'})
    cliente.post(url, {'texto': '   '})

    assert not AnotacaoEtapa.all_tenants.filter(
        candidato=cenario['candidato']).exists()


@pytest.mark.django_db
def test_registra_quem_anotou(cenario):
    """
    Numa contratacao contestada, "quem escreveu isso" e a primeira pergunta.
    """
    _cliente(cenario, username='supervisora').post(
        reverse('people:candidato_anotar_etapa',
                args=[cenario['candidato'].pk, cenario['etapa'].pk]),
        {'texto': 'Aprovado no teste prático.'})

    anotacao = AnotacaoEtapa.all_tenants.get(candidato=cenario['candidato'])
    assert anotacao.atualizado_por.username == 'supervisora'


# ── O perfil Avaliador ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_avaliador_anota_sem_poder_gerir(cenario):
    """
    O supervisor que entrevista registra a impressao dele, e so isso: nao move
    no pipeline, nao abre vaga e nao admite.
    """
    avaliador = _cliente(cenario, username='supervisor_tecnico',
                         funcionalidades=('people.ver', 'people.avaliar'))

    resposta = avaliador.post(
        reverse('people:candidato_anotar_etapa',
                args=[cenario['candidato'].pk, cenario['etapa'].pk]),
        {'texto': 'Sabe fusão de fibra, mas não tem CNH.'})

    assert resposta.status_code == 302
    assert AnotacaoEtapa.all_tenants.filter(
        candidato=cenario['candidato']).exists()


@pytest.mark.django_db
def test_avaliador_nao_admite(cenario):
    avaliador = _cliente(cenario, username='so_avalia',
                         funcionalidades=('people.ver', 'people.avaliar'))

    resposta = avaliador.post(
        reverse('people:candidato_admitir', args=[cenario['candidato'].pk]),
        {'cargo': cenario['tenant'].pk, 'data_inicio': '2026-08-01'})

    assert resposta.status_code == 403


@pytest.mark.django_db
def test_avaliador_nao_move_no_pipeline(cenario):
    avaliador = _cliente(cenario, username='so_avalia_2',
                         funcionalidades=('people.ver', 'people.avaliar'))
    outra = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                          nome='Admissão')

    resposta = avaliador.post(
        reverse('people:pipeline_mover', args=[cenario['candidato'].pk]),
        {'etapa': outra.pk})

    assert resposta.status_code == 403


@pytest.mark.django_db
def test_quem_so_ve_nao_anota(cenario):
    cliente = _cliente(cenario, username='so_ve_ficha',
                       funcionalidades=('people.ver',))

    resposta = cliente.post(
        reverse('people:candidato_anotar_etapa',
                args=[cenario['candidato'].pk, cenario['etapa'].pk]),
        {'texto': 'não deveria entrar'})

    assert resposta.status_code == 403
    assert not AnotacaoEtapa.all_tenants.exists()


@pytest.mark.django_db
def test_quem_so_ve_enxerga_a_anotacao_sem_o_formulario(cenario):
    """Ler o que foi registrado e diferente de poder registrar."""
    AnotacaoEtapa.all_tenants.create(
        tenant=cenario['tenant'], candidato=cenario['candidato'],
        etapa=cenario['etapa'], texto='Impressão do entrevistador')

    corpo = _ficha(cenario, _cliente(cenario, username='leitora',
                                     funcionalidades=('people.ver',)))

    assert 'Impressão do entrevistador' in corpo
    assert 'Salvar anotação' not in corpo


@pytest.mark.django_db
def test_anotacao_de_outro_tenant_nao_vaza(cenario):
    outro = TenantFactory(modulo_people=True)
    etapa_alheia = EtapaPipeline.do_escopo(outro).first()

    resposta = _cliente(cenario).post(
        reverse('people:candidato_anotar_etapa',
                args=[cenario['candidato'].pk, etapa_alheia.pk]),
        {'texto': 'x'})

    assert resposta.status_code == 404


# ── Blocos por etapa: e o que faz cada aba ter conteudo proprio ──────────────
#
# A estrutura espelha a da origem (Entrevista RH com roteiro, Teste Pratico com
# agendamento, Avaliacao Gestor com decisao), SEM chumbar o pipeline dela: as
# seis etapas padrao ja nascem com os blocos certos, e o cliente reconfigura.

@pytest.mark.django_db
def test_cada_etapa_padrao_nasce_com_os_blocos_da_origem(cenario):
    from apps.people import estados_recrutamento as estados_rs

    por_nome = {e.nome: e for e in EtapaPipeline.do_escopo(cenario['tenant'])}

    assert estados_rs.BLOCO_ROTEIRO in por_nome['Entrevista / Seleção'].blocos
    assert estados_rs.BLOCO_AGENDAMENTO in por_nome['Teste Prático'].blocos
    assert estados_rs.BLOCO_DECISAO in por_nome['Avaliação Gestor'].blocos
    assert estados_rs.BLOCO_ADMISSAO in por_nome['Admissão'].blocos


@pytest.mark.django_db
def test_abas_tem_conteudo_diferente(cenario):
    """
    O defeito que o Lucas viu: seis abas com a mesma coisa dentro. Cada uma
    precisa mostrar o bloco da SUA etapa.
    """
    corpo = _ficha(cenario)

    assert 'Roteiro da conversa' in corpo      # so na Entrevista / Seleção
    assert 'Agendamento' in corpo              # so no Teste prático
    assert 'Decisão' in corpo                  # so na Avaliação Gestor


@pytest.mark.django_db
def test_bloco_desconhecido_e_ignorado_em_vez_de_quebrar(cenario):
    """
    Bloco removido do codigo continuaria gravado nas etapas dos tenants. A tela
    tem que ignorar, e nao procurar um template que nao existe mais.
    """
    cenario['etapa'].blocos = ['anotacao', 'bloco_que_nao_existe_mais']
    cenario['etapa'].save()

    assert cenario['etapa'].blocos_validos == ['anotacao']
    assert 'Diego Melo' in _ficha(cenario)     # a pagina abre


@pytest.mark.django_db
def test_marca_item_do_roteiro(cenario):
    selecao = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                            nome='Entrevista / Seleção')
    pergunta = selecao.roteiro[0]

    _cliente(cenario).post(
        reverse('people:candidato_anotar_etapa',
                args=[cenario['candidato'].pk, selecao.pk]),
        {'itens': [pergunta], 'texto': ''})

    anotacao = AnotacaoEtapa.all_tenants.get(candidato=cenario['candidato'])
    assert anotacao.itens_marcados == [pergunta]


@pytest.mark.django_db
def test_item_forjado_nao_entra(cenario):
    """
    POST nao inventa pergunta. Tambem protege de roteiro editado depois: item
    que nao existe mais na etapa nao fica marcado como se existisse.
    """
    selecao = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                            nome='Entrevista / Seleção')

    _cliente(cenario).post(
        reverse('people:candidato_anotar_etapa',
                args=[cenario['candidato'].pk, selecao.pk]),
        {'itens': ['Pergunta que ninguém cadastrou']})

    assert not AnotacaoEtapa.all_tenants.exists()


@pytest.mark.django_db
def test_decisao_registra_sem_mover_o_candidato(cenario):
    """
    Registrar decisao NAO move: decisao errada e facil de corrigir, movimento
    automatico ja teria disparado mensagem e historico.
    """
    gestor = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                           nome='Avaliação Gestor')
    etapa_antes = cenario['candidato'].etapa_id

    _cliente(cenario).post(
        reverse('people:candidato_anotar_etapa',
                args=[cenario['candidato'].pk, gestor.pk]),
        {'decisao': 'reprovado'})

    cenario['candidato'].refresh_from_db()
    assert AnotacaoEtapa.all_tenants.get(
        candidato=cenario['candidato']).decisao == 'reprovado'
    assert cenario['candidato'].etapa_id == etapa_antes
    assert cenario['candidato'].saida == ''


@pytest.mark.django_db
def test_decisao_invalida_e_descartada(cenario):
    gestor = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                           nome='Avaliação Gestor')

    _cliente(cenario).post(
        reverse('people:candidato_anotar_etapa',
                args=[cenario['candidato'].pk, gestor.pk]),
        {'decisao': 'talvez', 'texto': 'algo'})

    assert AnotacaoEtapa.all_tenants.get(
        candidato=cenario['candidato']).decisao == ''


@pytest.mark.django_db
def test_etapa_nova_sem_bloco_nasce_com_o_minimo(cenario):
    """Etapa sem bloco teria aba vazia, que e pior que aba generica."""
    from apps.people import estados_recrutamento as estados_rs

    _cliente(cenario).post(reverse('people:fluxo_etapa_salvar'),
                           {'nome': 'Teste em campo'})

    nova = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                         nome='Teste em campo')
    assert nova.blocos == [estados_rs.BLOCO_ANOTACAO, estados_rs.BLOCO_MENSAGEM]


@pytest.mark.django_db
def test_cliente_escolhe_os_blocos_da_etapa(cenario):
    _cliente(cenario).post(reverse('people:fluxo_etapa_salvar'), {
        'nome': 'Visita técnica',
        'blocos': ['agendamento', 'anotacao'],
        'roteiro': 'Pergunta A\nPergunta B'})

    nova = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                         nome='Visita técnica')
    assert nova.blocos == ['agendamento', 'anotacao']
    assert nova.roteiro == ['Pergunta A', 'Pergunta B']
