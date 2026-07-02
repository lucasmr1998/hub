"""Testes do comparador de paridade (núcleo puro, sem DB)."""
from apps.automacao.comparador_pipeline import comparar_op, resumir


def _pulso(): return {'acao': 'motor_disparado', 'ts': 0, 'rules': set()}
def _mover(rid): return {'acao': 'mover_regra', 'ts': 1, 'rules': {rid}}
def _acoes(rid): return {'acao': 'acoes_regra', 'ts': 1, 'rules': {rid}}
def _shadow(rules): return {'acao': 'shadow_fluxo', 'ts': 1, 'rules': set(rules)}


def test_pulso_com_paridade_total():
    pulsos = comparar_op([_pulso(), _mover(5), _shadow({5})])
    assert len(pulsos) == 1
    assert pulsos[0]['match'] is True
    assert pulsos[0]['so_antigo'] == set() and pulsos[0]['so_novo'] == set()


def test_novo_faria_a_mais():
    pulsos = comparar_op([_pulso(), _mover(5), _shadow({5, 6})])
    assert pulsos[0]['match'] is False
    assert pulsos[0]['so_novo'] == {6} and pulsos[0]['so_antigo'] == set()


def test_novo_perderia():
    # antigo executou ação da regra 7; shadow não disparou nada → novo perderia 7
    pulsos = comparar_op([_pulso(), _acoes(7)])
    assert pulsos[0]['antigo'] == {7} and pulsos[0]['novo'] == set()
    assert pulsos[0]['so_antigo'] == {7} and pulsos[0]['match'] is False


def test_eventos_antes_do_primeiro_pulso_ignorados():
    pulsos = comparar_op([_shadow({9}), _mover(9), _pulso(), _mover(5), _shadow({5})])
    assert len(pulsos) == 1  # só o pulso âncora conta
    assert pulsos[0]['match'] is True


def test_dois_pulsos_separados():
    pulsos = comparar_op([
        _pulso(), _mover(5), _shadow({5}),
        _pulso(), _acoes(8), _shadow({8, 9}),
    ])
    assert len(pulsos) == 2
    assert pulsos[0]['match'] is True
    assert pulsos[1]['match'] is False and pulsos[1]['so_novo'] == {9}


def test_resumir_agrega():
    pulsos = comparar_op([
        _pulso(), _mover(5), _shadow({5}),        # match
        _pulso(), _acoes(7),                      # divergente (so_antigo 7)
        _pulso(), _shadow({6}),                   # divergente (so_novo 6)
    ])
    r = resumir(pulsos)
    assert r['pulsos'] == 3
    assert r['divergentes'] == 2
    assert r['regras_so_antigo'] == [7]
    assert r['regras_so_novo'] == [6]
    assert abs(r['paridade'] - 1/3) < 0.01
