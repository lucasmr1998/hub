"""Testes do nó `definir_propriedade_lead` e do registry `propriedades_lead`.

O bot de venda coletava CPF, nome, email e endereço e nada chegava na ficha do
lead. Este nó fecha esse buraco; os testes travam o contrato dos handlers
(nunca levantam por regra de negócio) e o comportamento de não sobrescrever.
"""
import datetime

import pytest

from apps.automacao.nodes import Contexto
from apps.automacao.nodes.base import REGISTRY
from apps.automacao.opcoes import opcoes_de
from apps.automacao.propriedades_lead import PROPRIEDADES
from tests.factories import LeadProspectoFactory, TenantFactory


def _rodar(tenant, lead, config):
    ctx = Contexto(tenant=tenant)
    ctx.lead = lead
    no = REGISTRY['definir_propriedade_lead']
    return no.executar(config, None, ctx)


@pytest.mark.django_db
def test_grava_cpf_so_com_digitos():
    """Pontuação removida de propósito: é o formato que o HubSoft espera na
    busca e o que a deduplicação de lead compara."""
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, cpf_cnpj='')

    r = _rodar(tenant, lead, {'propriedade': 'cpf_cnpj', 'valor': '111.444.777-35'})

    assert r.branch == 'sucesso'
    assert r.output['aplicado'] is True
    lead.refresh_from_db()
    assert lead.cpf_cnpj == '11144477735'


@pytest.mark.django_db
@pytest.mark.parametrize('entrada', ['123', '111444777351234567', 'abc'])
def test_cpf_invalido_nao_levanta_e_nao_grava(entrada):
    """Regra de negócio vira `aplicado=False`, nunca exceção: erro
    determinístico não deve acionar retry do runtime."""
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, cpf_cnpj='')

    r = _rodar(tenant, lead, {'propriedade': 'cpf_cnpj', 'valor': entrada})

    assert r.branch == 'sucesso'
    assert r.output['aplicado'] is False
    assert r.output['motivo_skip'] == 'formato_invalido'
    lead.refresh_from_db()
    assert lead.cpf_cnpj in ('', None)


@pytest.mark.django_db
@pytest.mark.parametrize('entrada,esperado', [
    ('14/03/1998', datetime.date(1998, 3, 14)),
    ('1998-03-14', datetime.date(1998, 3, 14)),
])
def test_data_nascimento_aceita_o_que_o_cliente_digita_e_o_ja_normalizado(entrada, esperado):
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, data_nascimento=None)

    r = _rodar(tenant, lead, {'propriedade': 'data_nascimento', 'valor': entrada})

    assert r.output['aplicado'] is True
    lead.refresh_from_db()
    assert lead.data_nascimento == esperado


@pytest.mark.django_db
def test_nao_sobrescreve_o_que_ja_tem_valor():
    """Padrão ligado: o bot pode reperguntar um item, e uma segunda passada não
    deve apagar o que um humano ajustou na ficha nesse meio tempo."""
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, email='humano@corrigiu.com')

    r = _rodar(tenant, lead, {'propriedade': 'email', 'valor': 'bot@escreveu.com'})

    assert r.output['aplicado'] is False
    assert r.output['motivo_skip'] == 'ja_preenchido'
    lead.refresh_from_db()
    assert lead.email == 'humano@corrigiu.com'


@pytest.mark.django_db
def test_sobrescreve_quando_desligado_explicitamente():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, email='antigo@exemplo.com')

    r = _rodar(tenant, lead, {'propriedade': 'email', 'valor': 'novo@exemplo.com',
                              'somente_se_vazio': False})

    assert r.output['aplicado'] is True
    lead.refresh_from_db()
    assert lead.email == 'novo@exemplo.com'


@pytest.mark.django_db
def test_dado_custom_exige_chave():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)

    r = _rodar(tenant, lead, {'propriedade': 'dado_custom', 'valor': 'x'})

    assert r.output['aplicado'] is False
    assert r.output['motivo_skip'] == 'sem_chave'


@pytest.mark.django_db
def test_dado_custom_grava_sem_apagar_o_que_ja_existia():
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, dados_custom={'ja_tinha': 'valor'})

    r = _rodar(tenant, lead, {'propriedade': 'dado_custom', 'chave': 'turno',
                              'valor': 'manha'})

    assert r.output['aplicado'] is True
    lead.refresh_from_db()
    assert lead.dados_custom == {'ja_tinha': 'valor', 'turno': 'manha'}


@pytest.mark.django_db
def test_sem_lead_no_contexto_cai_no_erro():
    tenant = TenantFactory()
    ctx = Contexto(tenant=tenant)
    no = REGISTRY['definir_propriedade_lead']

    r = no.executar({'propriedade': 'email', 'valor': 'x@y.com'}, None, ctx)

    assert r.branch == 'erro'


@pytest.mark.django_db
def test_propriedade_desconhecida_e_rejeitada_na_config():
    """Slug literal errado é pego na validação do fluxo, antes de rodar."""
    no = REGISTRY['definir_propriedade_lead']

    assert no.validar_config({'propriedade': 'campo_que_nao_existe'})
    assert no.validar_config({'propriedade': 'email'}) == []
    # Template não dá pra validar aqui: o valor só existe em execução.
    assert no.validar_config({'propriedade': '{{nodes.validar.chave}}'}) == []


@pytest.mark.django_db
def test_propriedade_por_template_escreve_o_campo_certo():
    """No bot, o fluxo não sabe em tempo de desenho qual campo escrever: depende
    de qual pergunta o cliente respondeu. A chave do item tem o mesmo nome do
    campo do lead, então um nó só resolve, em vez de treze `if`."""
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant, email='')
    ctx = Contexto(tenant=tenant)
    ctx.lead = lead
    ctx.nodes = {'validar': {'chave': 'email', 'valor_processado': 'cliente@exemplo.com'}}

    r = REGISTRY['definir_propriedade_lead'].executar(
        {'propriedade': '{{nodes.validar.chave}}',
         'valor': '{{nodes.validar.valor_processado}}'}, None, ctx)

    assert r.output['aplicado'] is True
    lead.refresh_from_db()
    assert lead.email == 'cliente@exemplo.com'


@pytest.mark.django_db
def test_chave_que_nao_e_campo_do_lead_e_skip_nao_erro():
    """A maioria das perguntas (`tipo_imovel`, `plano_confirmado`) não vira
    campo da ficha. Isso é o caso NORMAL quando a propriedade vem de template:
    erro aqui encheria o log e acionaria retry à toa."""
    tenant = TenantFactory()
    lead = LeadProspectoFactory(tenant=tenant)
    ctx = Contexto(tenant=tenant)
    ctx.lead = lead
    ctx.nodes = {'validar': {'chave': 'tipo_imovel', 'valor_processado': 'casa'}}

    r = REGISTRY['definir_propriedade_lead'].executar(
        {'propriedade': '{{nodes.validar.chave}}',
         'valor': '{{nodes.validar.valor_processado}}'}, None, ctx)

    assert r.branch == 'sucesso'
    assert r.output['aplicado'] is False
    assert r.output['motivo_skip'] == 'propriedade_desconhecida'


@pytest.mark.django_db
def test_dropdown_lista_todas_as_propriedades_do_registry():
    """A tela e o registry não podem divergir: propriedade nova no registry
    aparece sozinha no editor, sem ninguém lembrar de mexer no nó."""
    tenant = TenantFactory()

    opcoes = opcoes_de('propriedades_lead', tenant)

    assert {o['value'] for o in opcoes} == set(PROPRIEDADES)
    assert all(o['label'] for o in opcoes)
