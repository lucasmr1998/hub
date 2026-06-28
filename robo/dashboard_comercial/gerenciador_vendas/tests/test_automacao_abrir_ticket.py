"""
Testes da tool `abrir_ticket` (delega ao service `criar_ticket`).

Unit puro: o service é mockado (sem DB). Cobre schema (obrigatórios + prioridade
derivada do modelo, não hardcoded), delegação tenant-safe e erro que não levanta.
"""
from types import SimpleNamespace
from unittest import mock

from apps.automacao.services import ia_tools


def test_schema_obrigatorios_e_prioridade_vem_do_modelo():
    schema = ia_tools.schema_openai(['abrir_ticket'])
    fn = schema[0]['function']
    assert fn['name'] == 'abrir_ticket'
    assert fn['parameters']['required'] == ['titulo', 'descricao']
    enum = fn['parameters']['properties']['prioridade']['enum']
    from apps.suporte.models import Ticket
    assert enum == [v for v, _ in Ticket.PRIORIDADE_CHOICES]  # derivado, nada hardcoded


def test_delega_ao_service_tenant_safe():
    ctx = SimpleNamespace(tenant=SimpleNamespace(pk=3), lead=None)
    fake = SimpleNamespace(numero=12, prioridade='alta', categoria=SimpleNamespace(nome='Bug'))
    with mock.patch('apps.automacao.services.tickets.criar_ticket', return_value=fake) as mc:
        out = ia_tools.despachar('abrir_ticket', {
            'titulo': 'Erro ao salvar', 'descricao': 'quebrou no passo 3',
            'categoria': 'Bug', 'prioridade': 'alta'}, ctx)
    assert '#12' in out and 'Bug' in out
    args, kw = mc.call_args
    assert args[0] is ctx.tenant          # tenant explícito
    assert kw['categoria'] == 'Bug'
    assert kw['prioridade'] == 'alta'


def test_erro_do_service_nao_levanta():
    ctx = SimpleNamespace(tenant=SimpleNamespace(pk=3))
    with mock.patch('apps.automacao.services.tickets.criar_ticket', side_effect=ValueError('sem user')):
        out = ia_tools.despachar('abrir_ticket', {'titulo': 't', 'descricao': 'd'}, ctx)
    assert 'não foi possível' in out.lower()
