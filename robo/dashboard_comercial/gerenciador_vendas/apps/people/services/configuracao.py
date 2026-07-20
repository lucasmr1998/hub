"""
Resolucao de configuracao do People.

Regra: configuracao e global do tenant com override por unidade. Nenhum lugar
do codigo le `unidade.dias_experiencia_padrao` direto, porque nulo ali significa
"herda", nao "zero". Tudo passa por `config_efetiva()`.

Hoje sao 3 knobs e o override mora em campo nulo na propria Unidade. Se passar
de uns 6, promover pra tabela ConfiguracaoUnidade sem mudar a assinatura daqui.
"""
from dataclasses import dataclass

from apps.people.models import ConfiguracaoPeople, Unidade


CODIGO_UNIDADE_SENTINELA = 'sem-unidade'
NOME_UNIDADE_SENTINELA = 'Sem unidade definida'

# Campos que a Unidade pode sobrescrever. Nulo na unidade significa herdar.
CAMPOS_COM_OVERRIDE = (
    'dias_experiencia_padrao',
    'dias_primeiro_periodo_experiencia',
    'exige_cpf_no_autocadastro',
)


@dataclass(frozen=True)
class ConfigEfetiva:
    """Configuracao ja resolvida (tenant mais override da unidade)."""

    dias_experiencia_padrao: int
    dias_primeiro_periodo_experiencia: int
    exige_cpf_no_autocadastro: bool
    texto_consentimento_lgpd: str
    versao_consentimento_lgpd: str
    link_expira_em_dias: int


def config_efetiva(unidade=None, tenant=None):
    """
    Retorna a configuracao valendo pra essa unidade.

    Passe a unidade sempre que houver uma. `tenant` sozinho serve pros casos
    sem unidade no contexto (ex: tela de configuracao do tenant).
    """
    if unidade is None and tenant is None:
        raise ValueError('Informe unidade ou tenant.')

    if tenant is None:
        tenant = unidade.tenant

    base = ConfiguracaoPeople.get_config(tenant)

    valores = {
        'dias_experiencia_padrao': base.dias_experiencia_padrao,
        'dias_primeiro_periodo_experiencia': base.dias_primeiro_periodo_experiencia,
        'exige_cpf_no_autocadastro': base.exige_cpf_no_autocadastro,
        'texto_consentimento_lgpd': base.texto_consentimento_lgpd,
        'versao_consentimento_lgpd': base.versao_consentimento_lgpd,
        'link_expira_em_dias': base.link_expira_em_dias,
    }

    if unidade is not None:
        for campo in CAMPOS_COM_OVERRIDE:
            override = getattr(unidade, campo, None)
            if override is not None:
                valores[campo] = override

    return ConfigEfetiva(**valores)


def unidade_sentinela(tenant):
    """
    Unidade de fallback do tenant, criada sob demanda.

    Existe porque `Colaborador.unidade` e obrigatoria, e as Tools que vao entrar
    depois (Recrutamento principalmente) precisam criar pessoa antes de saber a
    loja. Melhor uma unidade explicita e visivel do que uma FK nula que espalha
    `if unidade is None` pelo modulo inteiro.

    Criada sob demanda de proposito, nao por data migration: tenant que nunca
    usar People nao ganha linha orfa, e tenant criado no futuro tambem funciona.
    """
    unidade, _ = Unidade.all_tenants.get_or_create(
        tenant=tenant,
        codigo=CODIGO_UNIDADE_SENTINELA,
        defaults={'nome': NOME_UNIDADE_SENTINELA},
    )
    return unidade
