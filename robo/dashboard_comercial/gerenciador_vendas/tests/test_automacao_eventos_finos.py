"""Testes das emissões dos eventos finos do funil (chamam o receiver direto,
instância fake, sem DB). AUTOMACAO_SHADOW_ATIVO=True em settings_local → _emissao_ativa."""
from types import SimpleNamespace
from unittest import mock

import apps.automacao.signals_dominio as sd


def _tenant():
    return SimpleNamespace(pk=1, slug='alpha')


def _lead(old=None, **fields):
    d = dict(tenant=_tenant(), status_api='', id_plano_rp=None, id_dia_vencimento=None,
             id_hubsoft=None, cep=None, numero_residencia=None, cpf_cnpj=None,
             data_nascimento=None, email=None, dados_custom={},
             nome_razaosocial='ACME', telefone='5511')
    d.update(fields)
    lead = SimpleNamespace(**d)
    lead._old_lead = old or {}
    return lead


def _eventos(mock_disp):
    return [c.args[0] for c in mock_disp.call_args_list]


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_lead_status_mudou_dispara(m_disp, _m_op):
    sd.on_lead_eventos_finos(None, _lead({'status_api': 'novo'}, status_api='aguardando_assinatura'),
                             created=False)
    assert 'lead_status_mudou' in _eventos(m_disp)
    assert m_disp.call_args_list[0].args[1]['status_api'] == 'aguardando_assinatura'


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_lead_status_igual_nao_dispara(m_disp, _m_op):
    sd.on_lead_eventos_finos(None, _lead({'status_api': 'x'}, status_api='x'), created=False)
    assert 'lead_status_mudou' not in _eventos(m_disp)


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_lead_campo_ganhou_valor_dispara(m_disp, _m_op):
    sd.on_lead_eventos_finos(None, _lead({'id_plano_rp': None}, id_plano_rp='555'), created=False)
    ev = m_disp.call_args_list
    assert any(c.args[0] == 'lead_campo_mudou' and c.args[1]['campo'] == 'id_plano_rp'
               and c.args[1]['valor'] == '555' for c in ev)


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_lead_campo_ja_tinha_nao_dispara(m_disp, _m_op):
    sd.on_lead_eventos_finos(None, _lead({'id_plano_rp': '555'}, id_plano_rp='555'), created=False)
    assert 'lead_campo_mudou' not in _eventos(m_disp)


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_viabilidade_consultada_dispara(m_disp, _m_op):
    lead = _lead({'dados_custom': {'viabilidade': {'status': 'nao_consultado'}}},
                 dados_custom={'viabilidade': {'status': 'fora_cobertura'}})
    sd.on_lead_eventos_finos(None, lead, created=False)
    ev = m_disp.call_args_list
    assert any(c.args[0] == 'viabilidade_consultada'
               and c.args[1]['viabilidade_status'] == 'fora_cobertura' for c in ev)


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_skip_automacao_nao_dispara(m_disp, _m_op):
    lead = _lead({'status_api': 'novo'}, status_api='aguardando_assinatura')
    lead._skip_automacao = True
    sd.on_lead_eventos_finos(None, lead, created=False)
    assert m_disp.call_count == 0


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_historico_contato_dispara(m_disp, _m_op):
    inst = SimpleNamespace(lead=SimpleNamespace(pk=1, tenant=_tenant(), nome_razaosocial='A', telefone='5'),
                           status='resposta')
    sd.on_historico_contato(None, inst, created=True)
    assert m_disp.call_args.args[0] == 'historico_contato'
    assert m_disp.call_args.args[1]['status'] == 'resposta'


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_historico_nao_created_nao_dispara(m_disp, _m_op):
    inst = SimpleNamespace(lead=SimpleNamespace(pk=1, tenant=_tenant()), status='resposta')
    sd.on_historico_contato(None, inst, created=False)
    assert m_disp.call_count == 0


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_documento_status_mudou_dispara(m_disp, _m_op):
    inst = SimpleNamespace(status_validacao='documentos_rejeitados', tenant=_tenant(),
                           lead=SimpleNamespace(pk=1, tenant=_tenant(), nome_razaosocial='A', telefone='5'))
    inst._old_img_status = 'pendente'
    sd.on_documento_status_mudou(None, inst, created=False)
    assert m_disp.call_args.args[0] == 'documento_status_mudou'
    assert m_disp.call_args.args[1]['status'] == 'documentos_rejeitados'


@mock.patch.object(sd, '_op_do_lead', return_value=None)
@mock.patch.object(sd, 'disparar_evento')
def test_documento_status_igual_nao_dispara(m_disp, _m_op):
    inst = SimpleNamespace(status_validacao='pendente', tenant=_tenant(), lead=None)
    inst._old_img_status = 'pendente'
    sd.on_documento_status_mudou(None, inst, created=False)
    assert m_disp.call_count == 0
