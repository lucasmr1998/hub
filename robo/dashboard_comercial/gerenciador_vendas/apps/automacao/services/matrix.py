"""Resolvedor do Matrix Brasil por tenant pra engine de automação.

Espelha o padrão de `services/whatsapp.py:uazapi_do_tenant`: o nó nunca fala com
a API direto — pede o cliente por tenant aqui. Se o tenant não tem integração
Matrix ativa, devolve None (o nó vira erro controlado).
"""


def matrix_do_tenant(tenant):
    """Devolve um `MatrixBrasilService` do tenant, ou None se não houver
    integração Matrix ativa configurada."""
    from apps.integracoes.services.matrix_brasil import (
        MatrixBrasilService, MatrixBrasilServiceError,
    )
    try:
        return MatrixBrasilService.from_tenant(tenant)
    except MatrixBrasilServiceError:
        return None


def consultar_atendimento(tenant, codigo):
    """Consulta um atendimento Matrix por código (mensagens, contato, status...).

    Delega pro `MatrixBrasilService.consultar_atendimento` do tenant. Levanta
    `ValueError` se o tenant não tiver integração Matrix ativa configurada
    (o nó chamador vira erro controlado); erros de rede/HTTP propagam como
    `MatrixBrasilServiceError`.
    """
    svc = matrix_do_tenant(tenant)
    if svc is None:
        raise ValueError('tenant sem integração Matrix ativa')
    return svc.consultar_atendimento(codigo)


def _tipo_mensagem(mensagem):
    """Classifica a mensagem em cliente/bot/agente, mesma regra do command
    `extrair_historico_matrix._extrair_mensagens`: `boleano_entrante='1'` →
    cliente; senão, `autor` contendo 'BOT' → bot; resto → agente."""
    entrante = str(mensagem.get('boleano_entrante') or '0')
    if entrante == '1':
        return 'cliente'
    autor = (mensagem.get('autor') or '').upper()
    return 'bot' if 'BOT' in autor else 'agente'


def _hora_mensagem(data_msg):
    """Extrai a hora (HH:MM:SS) de um timestamp Matrix ('YYYY-MM-DD HH:MM:SS'
    ou com 'T'). Se não achar separador, devolve o valor bruto."""
    s = str(data_msg or '').strip()
    if not s:
        return '?'
    s = s.replace('T', ' ')
    partes = s.split(' ', 1)
    return partes[1][:8] if len(partes) > 1 else partes[0]


def formatar_transcript(mensagens, anonimizar=True, max_mensagens=0):
    """Monta o texto legível do atendimento a partir das `mensagens[]` do
    payload Matrix (`descricao_msg`/`data_msg`/`boleano_entrante`/`autor`).

    Cada linha fica no formato `[cliente|agente|bot] <hora>: <texto>`.
    `anonimizar=True` mascara PII genérico do texto (CPF/CNPJ/telefone/email)
    via `anonimizar_texto`. `max_mensagens > 0` corta pras últimas N mensagens.
    """
    from apps.integracoes.services.anonimizador import anonimizar_texto

    lista = mensagens or []
    if isinstance(lista, dict):
        lista = [lista]
    if max_mensagens and max_mensagens > 0:
        lista = lista[-max_mensagens:]

    linhas = []
    for m in lista:
        if not isinstance(m, dict):
            continue
        tipo = _tipo_mensagem(m)
        texto = m.get('descricao_msg') or ''
        if anonimizar:
            texto = anonimizar_texto(texto)
        hora = _hora_mensagem(m.get('data_msg'))
        linhas.append(f'[{tipo}] {hora}: {texto}')
    return '\n'.join(linhas)
