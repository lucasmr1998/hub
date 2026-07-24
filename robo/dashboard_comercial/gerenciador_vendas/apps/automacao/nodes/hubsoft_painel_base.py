"""Base compartilhada dos nós de ESCRITA no painel HubSoft (conversao, novo
servico, upgrade).

Estes nós usam a API interna do painel (nao a oficial), via
`HubsoftPainelService`, e sao guardados por `PerfilConversaoHubsoft`: o perfil
carrega os IDs do HubSoft do tenant, o template do payload e, principalmente, o
guard `dry_run_forcado` + allowlist de CPF. Enquanto o guard estiver ligado, so os
CPFs liberados escrevem de verdade; todo o resto monta o payload e para (saida
`dry_run`).

Cada nó concreto declara `_campos_extra()` e implementa `executar`. Os campos
comuns (perfil, forcar dry run, conta do painel) sao anexados aqui. `retry_seguro`
nasce False: escrita no ERP nao e idempotente, entao a engine nunca reexecuta
sozinha depois de um erro (evita cliente/servico duplicado).
"""
from .base import BaseNode
from .hubsoft_base import integ_id_de  # mesma chave 'integracao_id'


def campo_conta_painel():
    """Seletor da credencial de operador do painel (IntegracaoAPI hubsoft_painel)."""
    return {'nome': 'integracao_id', 'label': 'Conta (HubSoft painel)', 'tipo': 'texto',
            'fonte': 'integracoes_hubsoft_painel',
            'ajuda': 'Credencial do operador do painel. Vazio = a primeira ativa do tenant.'}


def campo_perfil():
    """Seletor do PerfilConversaoHubsoft (IDs do tenant + template + guard)."""
    return {'nome': 'perfil', 'label': 'Perfil de conversao', 'tipo': 'texto',
            'fonte': 'perfis_conversao_hubsoft', 'obrigatorio': True,
            'ajuda': 'Perfil com os IDs do HubSoft do tenant, o template do payload e o guard de dry run.'}


def campo_dry_run():
    """Interruptor de simulacao do nó. Ligado (padrao) = so monta o payload."""
    return {'nome': 'dry_run', 'label': 'Forcar simulacao (dry run)', 'tipo': 'booleano',
            'ajuda': ('Ligado = so monta o payload e para (nada escrito). Desligado = tenta a '
                      'escrita real, mas ainda gated pela allowlist de CPF do perfil.')}


def flag(valor, default: bool) -> bool:
    """Coage um campo booleano do editor pra bool. Ausente/vazio = default.

    Trata as strings de "desligado" ('false', '0', 'nao', 'off') como False, porque
    o editor as vezes serializa booleano como texto e um `bool('false')` seria True.
    """
    if valor is None:
        return default
    if isinstance(valor, bool):
        return valor
    s = str(valor).strip().lower()
    if s in ('', 'none'):
        return default
    return s not in ('false', '0', 'nao', 'não', 'off', 'no')


def perfil_do_tenant(tenant, nome: str):
    """Carrega o PerfilConversaoHubsoft ativo do tenant pelo nome, ou None."""
    from apps.integracoes.models import PerfilConversaoHubsoft
    if not nome:
        return None
    return (PerfilConversaoHubsoft.all_tenants
            .filter(tenant=tenant, nome=nome, ativo=True).first())


def cliente_hubsoft_do_lead(lead):
    """Espelho ClienteHubsoft do lead (carrega o id_cliente do HubSoft), ou None.

    Novo servico e upgrade operam sobre um cliente que JA existe no ERP; o vinculo
    lead -> cliente e o espelho gravado na conversao/sincronizacao."""
    from apps.integracoes.models import ClienteHubsoft
    return (ClienteHubsoft.all_tenants
            .filter(tenant=lead.tenant, lead=lead).order_by('-data_sync').first())


def resolver_endereco_cadastral(svc, id_cliente):
    """Le o cliente no painel e devolve (id_endereco_numero, endereco_numero_obj) do
    endereco cadastral, pro payload de servico. (None, None) se nao achar."""
    try:
        corpo = svc.get_cliente(int(id_cliente)) or {}
    except Exception:
        return None, None
    cliente = corpo.get('cliente', corpo) if isinstance(corpo, dict) else {}
    enderecos = (cliente.get('enderecos') if isinstance(cliente, dict) else None) or []
    if not enderecos:
        return None, None
    cad = next((e for e in enderecos if (e.get('pivot') or {}).get('tipo') == 'cadastral'),
               enderecos[0])
    id_en = cad.get('id_endereco_numero')
    obj = cad.get('endereco_numero') or cad
    return id_en, obj


def resolver_forma_cobranca(svc, perfil):
    """Objeto da forma de cobranca pro payload: usa o capturado no perfil, senao
    busca pelo id no schema do painel. Pode devolver None (o no decide o erro)."""
    if perfil.forma_cobranca_obj:
        return perfil.forma_cobranca_obj
    return svc.forma_cobranca_do_schema(perfil.forma_cobranca_id)


def mascara_cpf(cpf: str) -> str:
    """CPF/CNPJ mascarado pro output do nó (LGPD): mantem so os 3 ultimos digitos."""
    d = ''.join(c for c in str(cpf or '') if c.isdigit())
    if len(d) < 4:
        return '***'
    return '*' * (len(d) - 3) + d[-3:]


class HubsoftPainelNode(BaseNode):
    """Base dos nós de escrita no painel. Saidas: sucesso | erro | dry_run."""
    categoria = "comercial"
    grupo = "Integrações"
    subgrupo = "HubSoft (painel)"
    saidas = ["sucesso", "erro", "dry_run"]
    retry_seguro = False   # escrita no ERP nao e idempotente: nunca reexecutar sozinho

    def _campos_extra(self) -> list:
        return []

    def campos_config(self) -> list:
        return [campo_perfil(), *self._campos_extra(), campo_dry_run(), campo_conta_painel()]


__all__ = ['HubsoftPainelNode', 'campo_conta_painel', 'campo_perfil', 'campo_dry_run',
           'flag', 'perfil_do_tenant', 'mascara_cpf', 'integ_id_de',
           'cliente_hubsoft_do_lead', 'resolver_endereco_cadastral', 'resolver_forma_cobranca']
