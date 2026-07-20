"""
Passo 1 do plano de Recrutamento: a maquina de saidas e a EtapaPipeline.

A maquina e Python puro, entao a maior parte destes testes nao toca banco. Os
que tocam existem por um motivo especifico: a constraint com
`nulls_distinct=False` e a peca que impede o seed de duplicar o pipeline
default, e constraint so vale se o banco de fato a aplicar.
"""
import pytest
from django.db import IntegrityError, transaction

from apps.people import estados_recrutamento as estados_rs
from apps.people.excecoes import CampoObrigatorioFaltando, TransicaoInvalida


# ── Maquina pura ─────────────────────────────────────────────────────────────

def test_toda_saida_tem_rotulo_de_tela():
    for valor in estados_rs.VALORES_SAIDA:
        rotulo = estados_rs.rotulo_saida(valor)
        assert rotulo and rotulo != valor, f'{valor} sem rotulo proprio'


def test_saida_desconhecida_e_recusada():
    with pytest.raises(TransicaoInvalida):
        estados_rs.validar_saida('contratado', motivo='qualquer')


@pytest.mark.parametrize('saida', estados_rs.VALORES_SAIDA)
def test_toda_saida_exige_motivo(saida):
    """
    A spec marca o motivo como coluna real que ficou fora da especificacao
    escrita. Sem ele o board vira cemiterio: ninguem sabe por que o candidato
    saiu, e a analise de funil so consegue contar.
    """
    with pytest.raises(CampoObrigatorioFaltando):
        estados_rs.validar_saida(saida, motivo='')


@pytest.mark.parametrize('motivo', ['', '   ', '\n', None])
def test_motivo_em_branco_nao_conta_como_motivo(motivo):
    """Espaco nao e motivo. Sem o strip, o campo obrigatorio vira decorativo."""
    with pytest.raises(CampoObrigatorioFaltando):
        estados_rs.validar_saida(estados_rs.SAIDA_INAPTO, motivo=motivo)


def test_saida_com_motivo_passa():
    estados_rs.validar_saida(estados_rs.SAIDA_BANCO_TALENTOS,
                             motivo='Perfil bom, sem vaga aberta agora')


# ── Reabertura ───────────────────────────────────────────────────────────────

def test_banco_de_talentos_reabre():
    """Reaproveitar quem foi pro banco e literalmente o produto."""
    assert estados_rs.pode_reabrir(estados_rs.SAIDA_BANCO_TALENTOS)


@pytest.mark.parametrize('saida', [estados_rs.SAIDA_INAPTO,
                                   estados_rs.SAIDA_ARQUIVADO])
def test_inapto_e_arquivado_reabrem_porque_clique_errado_acontece(saida):
    """
    Se nao reabrissem, o RH corrigiria cadastrando a pessoa de novo, que e
    exatamente a duplicata que a constraint de WhatsApp existe pra impedir.
    """
    assert estados_rs.pode_reabrir(saida)


def test_admitido_reabre_enquanto_nao_virou_colaborador():
    """Desfazer clique errado tem que ser possivel."""
    assert estados_rs.pode_reabrir(estados_rs.SAIDA_ADMITIDO,
                                   tem_colaborador_vinculado=False)


def test_admitido_nao_reabre_depois_que_virou_colaborador():
    """
    Aqui ja existe uma pessoa contratada apontando pra este candidato. Reabrir
    deixaria um colaborador ativo dentro do processo seletivo.
    """
    assert not estados_rs.pode_reabrir(estados_rs.SAIDA_ADMITIDO,
                                       tem_colaborador_vinculado=True)

    with pytest.raises(TransicaoInvalida) as erro:
        estados_rs.validar_reabertura(estados_rs.SAIDA_ADMITIDO,
                                      tem_colaborador_vinculado=True)
    # A mensagem precisa dizer o caminho certo, senao o RH tenta contornar
    assert 'Departamento Pessoal' in str(erro.value)


# ── Etapas padrao ────────────────────────────────────────────────────────────

def test_pipeline_padrao_tem_as_sete_etapas_da_origem():
    nomes = [e['nome'] for e in estados_rs.ETAPAS_PADRAO]
    assert nomes == ['Triagem', 'Histórico', 'Teste Comportamental', 'Seleção',
                     'Teste prático', 'Avaliação Gestor', 'Admissão']


def test_ordem_das_etapas_padrao_e_sequencial_e_sem_buraco():
    ordens = [e['ordem'] for e in estados_rs.ETAPAS_PADRAO]
    assert ordens == list(range(1, len(ordens) + 1))


def test_admissao_e_etapa_e_admitido_e_saida_e_sao_coisas_diferentes():
    """
    Guarda contra colapsar os dois. "Admissao" e a etapa em que o processo esta
    acontecendo; "admitido" e o desfecho. Mesma distincao que o DP faz entre
    `em_admissao` e estar contratado.
    """
    nomes_de_etapa = {e['nome'] for e in estados_rs.ETAPAS_PADRAO}
    assert 'Admissão' in nomes_de_etapa
    assert estados_rs.SAIDA_ADMITIDO not in nomes_de_etapa


# ── EtapaPipeline (banco) ────────────────────────────────────────────────────

@pytest.fixture
def cenario(db):
    """
    Tenant com People ligado, porem com o pipeline ZERADO.

    O signal de provisionamento (apps/people/signals.py) semeia as sete etapas
    ao ativar o modulo, entao um tenant criado aqui ja nasceria com elas. Os
    testes deste arquivo sao sobre a mecanica de `semear_padrao`, de
    `do_escopo` e da constraint, e todos precisam partir do vazio pra dizer
    alguma coisa. Limpar aqui deixa a premissa de cada teste explicita, em vez
    de cada um ter que descontar as sete que vieram de brinde.

    O provisionamento em si tem arquivo proprio: test_people_provisionamento.py
    """
    from apps.sistema.models import Tenant
    from apps.people.models import EtapaPipeline, Unidade

    tenant = Tenant.objects.create(nome='Rede Teste', slug='rede-teste',
                                   modulo_people=True)
    EtapaPipeline.all_tenants.filter(tenant=tenant).delete()

    unidade = Unidade.all_tenants.create(tenant=tenant, nome='Loja Centro',
                                         codigo='centro')
    outra = Unidade.all_tenants.create(tenant=tenant, nome='Loja Shopping',
                                       codigo='shopping')
    return {'tenant': tenant, 'unidade': unidade, 'outra': outra}


@pytest.mark.django_db
def test_semear_padrao_cria_as_sete_etapas(cenario):
    from apps.people.models import EtapaPipeline

    criadas = EtapaPipeline.semear_padrao(cenario['tenant'])

    assert len(criadas) == 7
    assert EtapaPipeline.all_tenants.filter(
        tenant=cenario['tenant'], unidade__isnull=True).count() == 7


@pytest.mark.django_db
def test_semear_padrao_e_idempotente(cenario):
    """Rodar o seed duas vezes e o jeito mais facil de duplicar o pipeline."""
    from apps.people.models import EtapaPipeline

    EtapaPipeline.semear_padrao(cenario['tenant'])
    segunda = EtapaPipeline.semear_padrao(cenario['tenant'])

    assert segunda == []
    assert EtapaPipeline.all_tenants.filter(tenant=cenario['tenant']).count() == 7


@pytest.mark.django_db
def test_o_banco_recusa_etapa_global_duplicada(cenario):
    """
    O teste que prova o `nulls_distinct=False`.

    Sem ele o Postgres trata cada `unidade IS NULL` como valor distinto, a
    constraint nao pega nada, e o tenant acumula "Triagem" repetida. Este e o
    unico jeito de saber se a constraint esta valendo: pedir pro banco recusar.
    """
    from apps.people.models import EtapaPipeline

    EtapaPipeline.all_tenants.create(tenant=cenario['tenant'], unidade=None,
                                     nome='Triagem', ordem=1)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EtapaPipeline.all_tenants.create(tenant=cenario['tenant'],
                                             unidade=None, nome='Triagem',
                                             ordem=2)


@pytest.mark.django_db
def test_mesma_etapa_pode_existir_em_unidades_diferentes(cenario):
    """A constraint e por escopo, nao global: cada loja tem a Triagem dela."""
    from apps.people.models import EtapaPipeline

    EtapaPipeline.all_tenants.create(tenant=cenario['tenant'],
                                     unidade=cenario['unidade'],
                                     nome='Triagem', ordem=1)
    EtapaPipeline.all_tenants.create(tenant=cenario['tenant'],
                                     unidade=cenario['outra'],
                                     nome='Triagem', ordem=1)

    assert EtapaPipeline.all_tenants.filter(
        tenant=cenario['tenant'], nome='Triagem').count() == 2


@pytest.mark.django_db
def test_unidade_sem_etapa_propria_herda_a_do_tenant(cenario):
    from apps.people.models import EtapaPipeline

    EtapaPipeline.semear_padrao(cenario['tenant'])

    etapas = EtapaPipeline.do_escopo(cenario['tenant'], cenario['unidade'])

    assert etapas.count() == 7
    assert all(e.unidade_id is None for e in etapas)


@pytest.mark.django_db
def test_unidade_com_etapa_propria_ignora_a_do_tenant(cenario):
    """
    Override substitui, nao soma. Somar produziria um pipeline montado de dois
    lugares, que ninguem configurou e que o cliente nao teria como prever ao
    criar a primeira etapa da loja.
    """
    from apps.people.models import EtapaPipeline

    EtapaPipeline.semear_padrao(cenario['tenant'])
    EtapaPipeline.all_tenants.create(tenant=cenario['tenant'],
                                     unidade=cenario['unidade'],
                                     nome='Entrevista com RH', ordem=1)

    etapas = list(EtapaPipeline.do_escopo(cenario['tenant'], cenario['unidade']))

    assert [e.nome for e in etapas] == ['Entrevista com RH']
    # A outra loja continua no fluxo do tenant
    assert EtapaPipeline.do_escopo(cenario['tenant'], cenario['outra']).count() == 7


@pytest.mark.django_db
def test_etapa_desativada_sai_do_escopo_mas_continua_existindo(cenario):
    """
    Desativar nao apaga. Se apagasse, candidato parado nela ficaria orfao e o
    historico apontaria pra uma linha inexistente.
    """
    from apps.people.models import EtapaPipeline

    EtapaPipeline.semear_padrao(cenario['tenant'])
    etapa = EtapaPipeline.all_tenants.get(tenant=cenario['tenant'],
                                          nome='Teste Comportamental')
    etapa.ativa = False
    etapa.save()

    assert EtapaPipeline.do_escopo(cenario['tenant']).count() == 6
    assert EtapaPipeline.do_escopo(
        cenario['tenant'], somente_ativas=False).count() == 7
    assert EtapaPipeline.all_tenants.filter(pk=etapa.pk).exists()


@pytest.mark.django_db
def test_etapas_saem_na_ordem_configurada(cenario):
    from apps.people.models import EtapaPipeline

    EtapaPipeline.semear_padrao(cenario['tenant'])

    nomes = [e.nome for e in EtapaPipeline.do_escopo(cenario['tenant'])]

    assert nomes[0] == 'Triagem'
    assert nomes[-1] == 'Admissão'


@pytest.mark.django_db
def test_etapa_nao_vaza_entre_tenants(cenario):
    """Multi tenancy: o de sempre, e o que nunca pode faltar."""
    from apps.sistema.models import Tenant
    from apps.people.models import EtapaPipeline

    outro = Tenant.objects.create(nome='Outra Rede', slug='outra-rede',
                                  modulo_people=True)
    EtapaPipeline.semear_padrao(cenario['tenant'])
    EtapaPipeline.semear_padrao(outro)

    do_primeiro = EtapaPipeline.do_escopo(cenario['tenant'])

    assert do_primeiro.count() == 7
    assert all(e.tenant_id == cenario['tenant'].id for e in do_primeiro)
