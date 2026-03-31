"""
Testes de modelo para o modulo CS (Clube, Parceiros, Indicacoes, Carteirinha).
"""
import pytest

from apps.cs.clube.models import MembroClube, NivelClube
from apps.cs.parceiros.models import CategoriaParceiro, Parceiro, CupomDesconto
from apps.cs.indicacoes.models import Indicacao
from apps.cs.carteirinha.models import ModeloCarteirinha

from tests.factories import (
    MembroClubeFactory,
    NivelClubeFactory,
    CategoriaParceiroFactory,
    ParceiroFactory,
    CupomDescontoFactory,
    IndicacaoFactory,
    ModeloCarteirinhaFactory,
)


# ──────────────────────────────────────────────
# Clube
# ──────────────────────────────────────────────

@pytest.mark.django_db
class TestMembroClube:

    def test_criar_membro_clube(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        membro = MembroClubeFactory(tenant=tenant_a)
        assert membro.pk is not None
        assert membro.tenant == tenant_a
        assert str(membro) == f"{membro.nome} ({membro.cpf})"

    def test_membro_saldo_default_zero(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        membro = MembroClubeFactory(tenant=tenant_a)
        assert membro.saldo == 0
        assert membro.xp_total == 0

    def test_membro_codigo_indicacao_gerado(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        membro = MembroClubeFactory(tenant=tenant_a)
        assert membro.codigo_indicacao is not None
        assert len(membro.codigo_indicacao) == 8

    def test_membro_nivel_atual_sem_niveis(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        membro = MembroClubeFactory(tenant=tenant_a)
        assert membro.nivel_atual == "Iniciante"

    def test_membro_isolado_por_tenant(self, tenant_a, tenant_b, set_tenant):
        set_tenant(tenant_a)
        MembroClubeFactory(tenant=tenant_a, cpf='00000000001')
        set_tenant(tenant_b)
        MembroClubeFactory(tenant=tenant_b, cpf='00000000002')

        set_tenant(tenant_a)
        assert MembroClube.objects.count() == 1

        set_tenant(tenant_b)
        assert MembroClube.objects.count() == 1


# ──────────────────────────────────────────────
# Parceiros
# ──────────────────────────────────────────────

@pytest.mark.django_db
class TestParceiros:

    def test_criar_categoria_parceiro(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        cat = CategoriaParceiroFactory(tenant=tenant_a)
        assert cat.pk is not None
        assert str(cat) == cat.nome

    def test_criar_parceiro_com_categoria(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        cat = CategoriaParceiroFactory(tenant=tenant_a)
        parceiro = ParceiroFactory(tenant=tenant_a, categoria=cat)
        assert parceiro.pk is not None
        assert parceiro.categoria == cat
        assert str(parceiro) == parceiro.nome

    def test_parceiro_isolado_por_tenant(self, tenant_a, tenant_b, set_tenant):
        set_tenant(tenant_a)
        ParceiroFactory(tenant=tenant_a, categoria=CategoriaParceiroFactory(tenant=tenant_a))
        set_tenant(tenant_b)
        ParceiroFactory(tenant=tenant_b, categoria=CategoriaParceiroFactory(tenant=tenant_b))

        set_tenant(tenant_a)
        assert Parceiro.objects.count() == 1

        set_tenant(tenant_b)
        assert Parceiro.objects.count() == 1

    def test_criar_cupom_desconto(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        cupom = CupomDescontoFactory(
            tenant=tenant_a,
            parceiro=ParceiroFactory(
                tenant=tenant_a,
                categoria=CategoriaParceiroFactory(tenant=tenant_a),
            ),
        )
        assert cupom.pk is not None
        assert cupom.tipo_desconto == 'percentual'
        assert cupom.ativo is True

    def test_cupom_vinculado_a_parceiro(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        parceiro = ParceiroFactory(
            tenant=tenant_a,
            categoria=CategoriaParceiroFactory(tenant=tenant_a),
        )
        cupom = CupomDescontoFactory(tenant=tenant_a, parceiro=parceiro)
        assert cupom.parceiro == parceiro
        assert parceiro.cupons.count() == 1

    def test_cupom_estoque_disponivel(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        cupom = CupomDescontoFactory(
            tenant=tenant_a,
            parceiro=ParceiroFactory(
                tenant=tenant_a,
                categoria=CategoriaParceiroFactory(tenant=tenant_a),
            ),
            quantidade_total=0,
        )
        assert cupom.estoque_disponivel is True
        assert cupom.estoque_restante == "Ilimitado"


# ──────────────────────────────────────────────
# Indicacoes
# ──────────────────────────────────────────────

@pytest.mark.django_db
class TestIndicacoes:

    def test_criar_indicacao(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        membro = MembroClubeFactory(tenant=tenant_a)
        indicacao = IndicacaoFactory(tenant=tenant_a, membro_indicador=membro)
        assert indicacao.pk is not None
        assert indicacao.status == 'pendente'
        assert indicacao.membro_indicador == membro

    def test_indicacao_str(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        membro = MembroClubeFactory(tenant=tenant_a, nome='Joao')
        indicacao = IndicacaoFactory(
            tenant=tenant_a,
            membro_indicador=membro,
            nome_indicado='Maria',
        )
        assert 'Joao' in str(indicacao)
        assert 'Maria' in str(indicacao)


# ──────────────────────────────────────────────
# Carteirinha
# ──────────────────────────────────────────────

@pytest.mark.django_db
class TestCarteirinha:

    def test_criar_modelo_carteirinha(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        modelo = ModeloCarteirinhaFactory(tenant=tenant_a)
        assert modelo.pk is not None
        assert modelo.ativo is True
        assert str(modelo) == modelo.nome
