"""Nó `matrix_atendimento` — unit (sem DB, sem rede; service mockado no
namespace do nó) + teste puro de `formatar_transcript`."""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.nodes import Contexto, tipo_por_slug
from apps.automacao.services.matrix import formatar_transcript

_SVC = 'apps.automacao.nodes.matrix_atendimento.consultar_atendimento'
_FMT = 'apps.automacao.nodes.matrix_atendimento.formatar_transcript'


def _ctx(**kw):
    return Contexto(tenant=SimpleNamespace(pk=1, slug='t'), **kw)


def test_registrado():
    assert tipo_por_slug('matrix_atendimento') is not None


def test_codigo_vazio_vira_erro():
    res = tipo_por_slug('matrix_atendimento').executar({}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'vazio' in (res.erro or '').lower()


@mock.patch(_SVC)
def test_service_value_error_vira_erro(mock_consultar):
    mock_consultar.side_effect = ValueError('tenant sem integração Matrix ativa')
    res = tipo_por_slug('matrix_atendimento').executar({'codigo': '123'}, {}, _ctx())
    assert res.branch == 'erro'
    assert 'matrix' in (res.erro or '').lower()


@mock.patch(_SVC)
def test_caminho_feliz_resolve_template_e_monta_transcript(mock_consultar):
    ctx = _ctx(variaveis={'id_atendimento_matrix': '999'})
    mock_consultar.return_value = {
        'status': 'finalizado',
        'agente': 'Joana',
        'mensagens': [
            {'boleano_entrante': '1', 'descricao_msg': 'Oi, quero saber do plano',
             'data_msg': '2026-07-01 10:00:00', 'autor': ''},
            {'boleano_entrante': '0', 'descricao_msg': 'Claro! Vamos te ajudar',
             'data_msg': '2026-07-01 10:01:00', 'autor': 'BOT'},
        ],
    }
    no = tipo_por_slug('matrix_atendimento')
    res = no.executar({'codigo': '{{var.id_atendimento_matrix}}'}, {}, ctx)

    assert res.branch == 'sucesso'
    assert mock_consultar.call_args.args[0] is ctx.tenant
    assert mock_consultar.call_args.args[1] == '999'  # template resolvido
    assert res.output['total_mensagens'] == 2
    assert res.output['status'] == 'finalizado'
    assert res.output['agente'] == 'Joana'
    assert '[cliente]' in res.output['transcript']
    assert '[bot]' in res.output['transcript']


@mock.patch(_FMT)
@mock.patch(_SVC)
def test_anonimizar_default_true_chega_no_formatar(mock_consultar, mock_formatar):
    mock_consultar.return_value = {'status': 'x', 'agente': 'y', 'mensagens': []}
    mock_formatar.return_value = 'transcript'
    tipo_por_slug('matrix_atendimento').executar({'codigo': '1'}, {}, _ctx())
    assert mock_formatar.call_args.kwargs['anonimizar'] is True


@mock.patch(_FMT)
@mock.patch(_SVC)
def test_anonimizar_false_explicito_chega_no_formatar(mock_consultar, mock_formatar):
    mock_consultar.return_value = {'status': 'x', 'agente': 'y', 'mensagens': []}
    mock_formatar.return_value = 'transcript'
    tipo_por_slug('matrix_atendimento').executar({'codigo': '1', 'anonimizar': False}, {}, _ctx())
    assert mock_formatar.call_args.kwargs['anonimizar'] is False


# ──────────────────────────────────────────────
# formatar_transcript (puro, sem DB nem mock)
# ──────────────────────────────────────────────

def test_formatar_transcript_formata_linhas_por_tipo_e_hora():
    mensagens = [
        {'boleano_entrante': '1', 'descricao_msg': 'Meu telefone e (11) 98765-4321',
         'data_msg': '2026-07-01 10:00:00', 'autor': ''},
        {'boleano_entrante': '0', 'descricao_msg': 'Oi, tudo bem?',
         'data_msg': '2026-07-01 10:01:05', 'autor': 'BOT'},
        {'boleano_entrante': '0', 'descricao_msg': 'Vou te transferir',
         'data_msg': '2026-07-01 10:02:00', 'autor': 'Carla'},
    ]
    texto = formatar_transcript(mensagens)
    linhas = texto.splitlines()
    assert linhas[0].startswith('[cliente] 10:00:00:')
    assert '[TELEFONE]' in linhas[0]  # telefone digitado pelo cliente anonimizado
    assert '98765-4321' not in linhas[0]
    assert linhas[1].startswith('[bot] 10:01:05:')
    assert linhas[2].startswith('[agente] 10:02:00:')


def test_formatar_transcript_sem_anonimizar_mantem_texto_original():
    mensagens = [
        {'boleano_entrante': '1', 'descricao_msg': 'Meu telefone e (11) 98765-4321',
         'data_msg': '2026-07-01 10:00:00', 'autor': ''},
    ]
    texto = formatar_transcript(mensagens, anonimizar=False)
    assert '98765-4321' in texto


def test_formatar_transcript_max_mensagens_corta_ultimas():
    mensagens = [
        {'boleano_entrante': '1', 'descricao_msg': f'msg {i}',
         'data_msg': '2026-07-01 10:00:00', 'autor': ''}
        for i in range(5)
    ]
    texto = formatar_transcript(mensagens, max_mensagens=2)
    linhas = texto.splitlines()
    assert len(linhas) == 2
    assert 'msg 3' in linhas[0]
    assert 'msg 4' in linhas[1]
