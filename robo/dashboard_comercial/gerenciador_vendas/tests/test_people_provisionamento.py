"""
Provisionamento do pipeline de recrutamento.

O signal roda no save do Tenant, longe da vista. Se ele parar de funcionar,
nada quebra: o tenant simplesmente fica com o board de recrutamento sem coluna,
e a descoberta acontece quando alguem abre a tela e estranha. Por isso cada
caminho tem teste proprio.
"""
import pytest

from apps.people.models import EtapaPipeline
from apps.sistema.models import Tenant


def _etapas(tenant):
    return EtapaPipeline.all_tenants.filter(tenant=tenant, unidade__isnull=True)


@pytest.mark.django_db
def test_tenant_criado_com_people_ligado_ja_nasce_com_pipeline():
    tenant = Tenant.objects.create(nome='Rede Nova', slug='rede-nova',
                                   modulo_people=True)

    assert _etapas(tenant).count() == 6


@pytest.mark.django_db
def test_tenant_sem_people_nao_ganha_pipeline():
    """Tenant que nao contratou o modulo nao carrega tabela dele."""
    tenant = Tenant.objects.create(nome='Rede Sem', slug='rede-sem',
                                   modulo_people=False)

    assert _etapas(tenant).count() == 0


@pytest.mark.django_db
def test_ativar_o_modulo_depois_provisiona():
    """O caso do cliente que contrata People meses depois de virar tenant."""
    tenant = Tenant.objects.create(nome='Rede Depois', slug='rede-depois',
                                   modulo_people=False)
    assert _etapas(tenant).count() == 0

    tenant.modulo_people = True
    tenant.save()

    assert _etapas(tenant).count() == 6


@pytest.mark.django_db
def test_salvar_o_tenant_de_novo_nao_duplica():
    tenant = Tenant.objects.create(nome='Rede Dup', slug='rede-dup',
                                   modulo_people=True)

    tenant.nome = 'Rede Dup Renomeada'
    tenant.save()
    tenant.save()

    assert _etapas(tenant).count() == 6


@pytest.mark.django_db
def test_etapa_apagada_de_proposito_nao_volta_no_proximo_save():
    """
    Desfazer decisao do cliente e pior que faltar dado. Se o tenant montou o
    pipeline dele e removeu uma etapa, salvar o tenant nao pode repor.
    """
    tenant = Tenant.objects.create(nome='Rede Custom', slug='rede-custom',
                                   modulo_people=True)
    _etapas(tenant).filter(nome='Perfil comportamental').delete()
    assert _etapas(tenant).count() == 5      # das seis, sobrou cinco

    tenant.nome = 'Rede Custom 2'
    tenant.save()

    assert _etapas(tenant).count() == 5      # e continua cinco


@pytest.mark.django_db
def test_desligar_e_religar_o_modulo_nao_duplica():
    tenant = Tenant.objects.create(nome='Rede Volta', slug='rede-volta',
                                   modulo_people=True)

    tenant.modulo_people = False
    tenant.save()
    tenant.modulo_people = True
    tenant.save()

    assert _etapas(tenant).count() == 6


@pytest.mark.django_db
def test_pipeline_nasce_na_ordem_certa():
    tenant = Tenant.objects.create(nome='Rede Ordem', slug='rede-ordem',
                                   modulo_people=True)

    nomes = list(_etapas(tenant).order_by('ordem').values_list('nome', flat=True))

    # A lista sai do PRODUTO RODANDO, e nao da spec de handoff. O board real
    # tem seis etapas, sem "Historico". Ver ETAPAS_PADRAO.
    assert nomes == ['Análise de inscrição', 'Perfil comportamental',
                     'Entrevista / Seleção', 'Teste Prático',
                     'Avaliação Gestor', 'Admissão']


@pytest.mark.django_db
def test_pipeline_nao_vaza_entre_tenants():
    um = Tenant.objects.create(nome='Rede A', slug='rede-a', modulo_people=True)
    outro = Tenant.objects.create(nome='Rede B', slug='rede-b', modulo_people=True)

    assert _etapas(um).count() == 6
    assert _etapas(outro).count() == 6
    assert not _etapas(um).filter(tenant=outro).exists()


@pytest.mark.django_db
def test_erro_no_seed_nao_derruba_o_save_do_tenant(monkeypatch):
    """
    Pipeline vazio e recuperavel pela tela de etapas; tenant que nao salva, nao.
    O try/except do signal existe pra isso, e este teste garante que ele
    continua ali.
    """
    def explodir(*args, **kwargs):
        raise RuntimeError('banco fora do ar')

    monkeypatch.setattr(EtapaPipeline, 'semear_padrao', explodir)

    tenant = Tenant.objects.create(nome='Rede Falha', slug='rede-falha',
                                   modulo_people=True)

    assert tenant.pk is not None
    assert _etapas(tenant).count() == 0
