"""Servicos do app cron: parser/matcher de expressao cron classica (5 campos)."""
from typing import Tuple


_HUMAN_NAMES = {
    '* * * * *': 'a cada 1 min',
    '*/5 * * * *': 'a cada 5 min',
    '*/10 * * * *': 'a cada 10 min',
    '*/15 * * * *': 'a cada 15 min',
    '*/30 * * * *': 'a cada 30 min',
    '0 * * * *': 'a cada hora',
    '0 */2 * * *': 'a cada 2 horas',
    '0 2 * * *': 'todo dia 02:00',
    '0 3 * * *': 'todo dia 03:00',
}


def cron_humanizar(expr: str) -> str:
    """Devolve uma string humana pra schedules comuns; senao volta a propria expr."""
    return _HUMAN_NAMES.get(expr.strip(), expr)


def cron_match(expr: str, dt) -> bool:
    """Confere se a expressao cron de 5 campos bate com o `dt` (datetime).

    Campos: minuto hora dia-do-mes mes dia-da-semana.
    Operadores suportados em cada campo: `*`, `N`, `*/N`, `N-M`, `N,M,P`.
    Dia-da-semana: 0=Domingo .. 6=Sabado (padrao cron classico). 7 tambem aceito como Domingo.
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"expressao cron invalida: {expr!r} (esperados 5 campos)")
    minute, hour, dom, month, dow = parts

    # python weekday: Mon=0 .. Sun=6 → cron weekday: Sun=0 .. Sat=6
    dow_cron = (dt.weekday() + 1) % 7

    return (
        _match_field(minute, dt.minute, 0, 59)
        and _match_field(hour, dt.hour, 0, 23)
        and _match_field(dom, dt.day, 1, 31)
        and _match_field(month, dt.month, 1, 12)
        and _match_field(dow, dow_cron, 0, 6, dow=True)
    )


def _match_field(spec: str, val: int, mn: int, mx: int, dow: bool = False) -> bool:
    spec = spec.strip()
    if spec == '*':
        return True
    if ',' in spec:
        return any(_match_field(s, val, mn, mx, dow=dow) for s in spec.split(','))
    if spec.startswith('*/'):
        try:
            step = int(spec[2:])
        except ValueError:
            return False
        return step > 0 and (val - mn) % step == 0
    if '-' in spec:
        try:
            a, b = spec.split('-', 1)
            a_i, b_i = _to_int(a, dow), _to_int(b, dow)
            return a_i <= val <= b_i
        except ValueError:
            return False
    try:
        return val == _to_int(spec, dow)
    except ValueError:
        return False


def _to_int(s: str, dow: bool) -> int:
    n = int(s)
    if dow and n == 7:
        return 0
    return n


def validar_expressao(expr: str) -> Tuple[bool, str]:
    """Tenta casar com agora; valida formato sem inspecionar match real."""
    try:
        parts = expr.strip().split()
        if len(parts) != 5:
            return False, 'precisa de 5 campos'
        # garante que cada campo individualmente parseia
        from datetime import datetime
        cron_match(expr, datetime(2026, 1, 1, 0, 0))
        return True, ''
    except ValueError as e:
        return False, str(e)
