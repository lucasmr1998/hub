"""
Testes de modelo para o modulo Marketing (CampanhaTrafego, DeteccaoCampanha).
"""
import pytest
from datetime import date, timedelta

from apps.marketing.campanhas.models import CampanhaTrafego, DeteccaoCampanha

from tests.factories import (
    CampanhaTrafegoFactory,
    DeteccaoCampanhaFactory,
)


@pytest.mark.django_db
class TestCampanhaTrafego:

    def test_criar_campanha_trafego(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        camp = CampanhaTrafegoFactory(tenant=tenant_a)
        assert camp.pk is not None
        assert camp.ativa is True
        assert camp.plataforma == 'google_ads'

    def test_campanha_str(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        camp = CampanhaTrafegoFactory(
            tenant=tenant_a, nome='Black Friday', codigo='BF2026',
        )
        assert 'Black Friday' in str(camp)
        assert 'BF2026' in str(camp)

    def test_campanha_esta_ativa_sem_periodo(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        camp = CampanhaTrafegoFactory(tenant=tenant_a)
        assert camp.esta_no_periodo is True
        assert camp.esta_ativa is True

    def test_campanha_esta_ativa_dentro_periodo(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        camp = CampanhaTrafegoFactory(
            tenant=tenant_a,
            data_inicio=date.today() - timedelta(days=5),
            data_fim=date.today() + timedelta(days=5),
        )
        assert camp.esta_no_periodo is True
        assert camp.esta_ativa is True

    def test_campanha_fora_do_periodo_futuro(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        camp = CampanhaTrafegoFactory(
            tenant=tenant_a,
            data_inicio=date.today() + timedelta(days=10),
            data_fim=date.today() + timedelta(days=20),
        )
        assert camp.esta_no_periodo is False
        assert camp.esta_ativa is False

    def test_campanha_fora_do_periodo_passado(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        camp = CampanhaTrafegoFactory(
            tenant=tenant_a,
            data_inicio=date.today() - timedelta(days=20),
            data_fim=date.today() - timedelta(days=10),
        )
        assert camp.esta_no_periodo is False

    def test_campanha_inativa(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        camp = CampanhaTrafegoFactory(tenant=tenant_a, ativa=False)
        assert camp.esta_ativa is False

    def test_campanha_isolada_por_tenant(self, tenant_a, tenant_b, set_tenant):
        set_tenant(tenant_a)
        CampanhaTrafegoFactory(tenant=tenant_a)
        set_tenant(tenant_b)
        CampanhaTrafegoFactory(tenant=tenant_b)

        set_tenant(tenant_a)
        assert CampanhaTrafego.objects.count() == 1

        set_tenant(tenant_b)
        assert CampanhaTrafego.objects.count() == 1


@pytest.mark.django_db
class TestDeteccaoCampanha:

    def test_criar_deteccao_campanha(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        det = DeteccaoCampanhaFactory(
            tenant=tenant_a,
            campanha=CampanhaTrafegoFactory(tenant=tenant_a),
        )
        assert det.pk is not None
        assert det.aceita is True
        assert det.converteu_venda is False

    def test_deteccao_normaliza_mensagem(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        det = DeteccaoCampanhaFactory(
            tenant=tenant_a,
            campanha=CampanhaTrafegoFactory(tenant=tenant_a),
            mensagem_original='Promoção Especial!',
        )
        assert det.mensagem_normalizada != ''
        assert det.tamanho_mensagem == len('Promoção Especial!')

    def test_deteccao_vinculada_a_campanha(self, tenant_a, set_tenant):
        set_tenant(tenant_a)
        camp = CampanhaTrafegoFactory(tenant=tenant_a)
        det = DeteccaoCampanhaFactory(tenant=tenant_a, campanha=camp)
        assert det.campanha == camp
        assert camp.deteccoes.count() >= 1
