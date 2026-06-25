"""Testes do tradutor de regras de marketing → Fluxo (apps.automacao.migracao_marketing).

Testa a lógica pura (template flat→var, renome de campo, mapa de saída, ação suportada
ou não). A tradução completa de uma regra (lê DB) é validada via dry-run do command.
"""
from apps.automacao.migracao_marketing import (
    _conv_template, _conv_config, _map_saida, _no_da_acao,
)


def test_conv_template_flat_vira_var():
    assert _conv_template('Oi {{lead_nome}}') == 'Oi {{var.lead_nome}}'
    assert _conv_template('{{telefone}}') == '{{var.telefone}}'


def test_conv_template_mantem_dot_notation():
    assert _conv_template('{{lead.nome}}') == '{{lead.nome}}'
    assert _conv_template('{{var.x}} e {{nodes.a.b}}') == '{{var.x}} e {{nodes.a.b}}'


def test_conv_config_renomeia_campo_e_converte_template():
    out = _conv_config('criar_tarefa', {'titulo': 'Follow {{lead_nome}}', 'tipo_tarefa': 'ligacao'})
    assert out['titulo'] == 'Follow {{var.lead_nome}}'
    assert out['tipo'] == 'ligacao'        # tipo_tarefa -> tipo
    assert 'tipo_tarefa' not in out


def test_map_saida_por_tipo_de_origem():
    assert _map_saida('evento', 'default') == 'default'
    assert _map_saida('delay', 'default') == 'default'
    assert _map_saida('criar_tarefa', 'default') == 'sucesso'   # ação default -> sucesso
    assert _map_saida('if', 'true') == 'true'
    assert _map_saida('if', 'false') == 'false'


def test_no_da_acao_suportada():
    avisos = []
    no = _no_da_acao('notificacao_sistema', {'titulo': 'x', 'mensagem': 'y'}, {'x': 0, 'y': 0}, avisos)
    assert no is not None and no['tipo'] == 'notificacao_sistema'
    assert avisos == []


def test_no_da_acao_sem_no_vira_aviso():
    avisos = []
    no = _no_da_acao('enviar_email', {}, {'x': 0, 'y': 0}, avisos)
    assert no is None
    assert len(avisos) == 1 and 'enviar_email' in avisos[0]
