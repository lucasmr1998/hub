"""Reconhecer prospecto que ja virou cliente no HubSoft (tarefa 220).

O pre-flight exige 8 campos antes de editar o prospecto, mas prospecto
convertido nao pode mais ser editado. Sem esta checagem o lead ficava travado
por dado que ninguem mais precisa: 54 vendas de julho da Nuvyon ficaram fora do
espelho por isso, 30 delas so por falta de nascimento/email/CEP.

O que mais importa aqui NAO e o caminho feliz, e as salvaguardas: marcar alguem
como cliente por engano e pior do que deixar o lead travado.
"""
from unittest.mock import MagicMock

import pytest

from apps.integracoes.models import ClienteHubsoft
from apps.integracoes.services import hubsoft_prospecto_rascunho as mod
from apps.integracoes.services.hubsoft import HubsoftServiceError
from apps.sistema.middleware import set_current_tenant
from tests.factories import (
    TenantFactory, UserFactory, PerfilFactory, ConfigEmpresaFactory,
    LeadProspectoFactory,
)

CPF = '52998224725'


@pytest.fixture
def lead_incompleto(db):
    """Lead com prospecto criado no HubSoft e cadastro pela metade — o cenario
    real dos 30 que travaram."""
    tenant = TenantFactory(plano_comercial='pro', modulo_comercial=True)
    user = UserFactory(is_staff=True)
    PerfilFactory(user=user, tenant=tenant)
    ConfigEmpresaFactory(tenant=tenant)
    set_current_tenant(tenant)

    lead = LeadProspectoFactory.build(
        tenant=tenant, cpf_cnpj=CPF, id_hubsoft='24000',
        status_api='rascunho_hubsoft',
        email='', rg='', cep='', numero_residencia='', data_nascimento=None,
    )
    lead._skip_crm_signal = True
    lead._skip_automacao = True
    lead.save()
    return lead


def _service_devolvendo(clientes, cliente_criado=None):
    svc = MagicMock()
    svc.consultar_cliente.return_value = {'clientes': clientes}
    svc._sincronizar_dados_cliente.return_value = cliente_criado or MagicMock(id_cliente=999)
    return svc


class TestReconheceClienteExistente:
    def test_marca_convertido_mesmo_com_cadastro_incompleto(self, lead_incompleto):
        """O ponto da tarefa: o lead nao tem email, RG, CEP, numero nem
        nascimento, e ainda assim deve ser reconhecido."""
        svc = _service_devolvendo([{'cpf_cnpj': CPF, 'id_cliente': 999}])

        r = mod._reconhecer_cliente_existente(lead_incompleto, svc)

        assert r is not None, 'devia ter reconhecido'
        assert r.ok is True and r.acao == 'ja_cliente'
        lead_incompleto.refresh_from_db()
        assert lead_incompleto.status_api == 'convertido_cliente'
        assert svc._sincronizar_dados_cliente.called, 'tem que espelhar o cliente'

    def test_limpa_motivo_rejeicao_antigo(self, lead_incompleto):
        type(lead_incompleto).objects.filter(pk=lead_incompleto.pk).update(
            motivo_rejeicao='editar falhou: Prospecto foi convertido para o cliente')
        svc = _service_devolvendo([{'cpf_cnpj': CPF, 'id_cliente': 999}])

        mod._reconhecer_cliente_existente(lead_incompleto, svc)

        lead_incompleto.refresh_from_db()
        assert lead_incompleto.motivo_rejeicao is None

    def test_nao_consulta_de_novo_se_ja_espelhado(self, lead_incompleto):
        ClienteHubsoft.all_tenants.create(
            tenant=lead_incompleto.tenant, lead=lead_incompleto,
            id_cliente=555, nome_razaosocial='X', cpf_cnpj=CPF)
        svc = _service_devolvendo([{'cpf_cnpj': CPF, 'id_cliente': 555}])

        r = mod._reconhecer_cliente_existente(lead_incompleto, svc)

        assert r is not None and r.acao == 'ja_cliente'
        assert not svc.consultar_cliente.called, 'ja espelhado nao precisa de API'
        lead_incompleto.refresh_from_db()
        assert lead_incompleto.status_api == 'convertido_cliente'


class TestSalvaguardas:
    """Marcar alguem como cliente por engano e pior que deixar travado."""

    def test_cpf_divergente_NAO_vincula(self, lead_incompleto):
        """Se o HubSoft devolver outra pessoa, nao pode vincular. O `clientes[0]`
        e pego sem validacao pela API; hoje se comporta como busca exata, mas
        depender disso vincularia a pessoa errada no dia em que mudar."""
        svc = _service_devolvendo([{'cpf_cnpj': '11144477735', 'id_cliente': 999}])

        r = mod._reconhecer_cliente_existente(lead_incompleto, svc)

        assert r is None, 'CPF diferente nao pode ser reconhecido'
        assert not svc._sincronizar_dados_cliente.called
        lead_incompleto.refresh_from_db()
        assert lead_incompleto.status_api == 'rascunho_hubsoft', 'status intacto'

    def test_erro_de_consulta_segue_fluxo_normal(self, lead_incompleto):
        """Falha de API nao pode virar deducao. Melhor seguir o fluxo e falhar
        visivelmente do que adivinhar."""
        svc = MagicMock()
        svc.consultar_cliente.side_effect = HubsoftServiceError('timeout')

        r = mod._reconhecer_cliente_existente(lead_incompleto, svc)

        assert r is None
        lead_incompleto.refresh_from_db()
        assert lead_incompleto.status_api == 'rascunho_hubsoft'

    def test_sem_cliente_no_hubsoft_segue_fluxo_normal(self, lead_incompleto):
        svc = _service_devolvendo([])

        r = mod._reconhecer_cliente_existente(lead_incompleto, svc)

        assert r is None
        assert not svc._sincronizar_dados_cliente.called

    def test_lead_sem_cpf_nao_consulta(self, lead_incompleto):
        type(lead_incompleto).objects.filter(pk=lead_incompleto.pk).update(cpf_cnpj='')
        lead_incompleto.refresh_from_db()
        svc = _service_devolvendo([{'cpf_cnpj': CPF}])

        assert mod._reconhecer_cliente_existente(lead_incompleto, svc) is None
        assert not svc.consultar_cliente.called

    def test_cpf_pontuado_bate_com_o_devolvido(self, lead_incompleto):
        """A comparacao e por digitos: formatacao diferente dos dois lados nao
        pode virar falso negativo."""
        type(lead_incompleto).objects.filter(pk=lead_incompleto.pk).update(
            cpf_cnpj='529.982.247-25')
        lead_incompleto.refresh_from_db()
        svc = _service_devolvendo([{'cpf_cnpj': '52998224725', 'id_cliente': 999}])

        r = mod._reconhecer_cliente_existente(lead_incompleto, svc)

        assert r is not None and r.acao == 'ja_cliente'
