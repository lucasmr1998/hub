"""Reconciliacao entre o funil do Hubtrix e o que veio do HubSoft.

Existe porque toda vez que o cliente questionava um numero ("o HubSoft mostra
276 vendas e o painel 240") a resposta exigia investigacao manual no banco.
Aqui a conta fica escrita uma vez so, e a tela chama.

Fonte do lado HubSoft: as tabelas espelho (`ClienteHubsoft`,
`ServicoClienteHubsoft`), populadas pelo sync. **Nao chama a API ao vivo** — o
HubSoft tem timeout de 30s com ate 3 tentativas, o que deixaria a pagina
inutilizavel. Em troca, `confiabilidade_espelho()` mede o quanto esse espelho
esta defasado, e a tela e obrigada a mostrar isso junto: sem esse contexto os
numeros mentem por omissao.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone


# Status de lead que significam "o prospecto existe no HubSoft mas o cadastro
# nunca foi completado do nosso lado". Ver 06-PROSPECTO-RASCUNHO-HUBSOFT.md.
STATUS_RASCUNHO = 'rascunho_hubsoft'
STATUS_ERRO = ('erro', 'cpf_invalido', 'vendedor_invalido', 'regra_negocio')


@dataclass
class Divergencia:
    """Uma linha da comparacao. `nossos`/`deles` sao contagens dos dois lados,
    e `explicacao` diz o que a diferenca significa — sem ela o numero vira
    ansiedade em vez de informacao."""
    titulo: str
    nossos: int
    deles: int
    rotulo_nossos: str = 'Hubtrix'
    rotulo_deles: str = 'HubSoft'
    intersecao: int | None = None
    explicacao: str = ''
    severidade: str = 'info'          # info | atencao | critico
    detalhes: list = field(default_factory=list)

    @property
    def diferenca(self) -> int:
        return self.deles - self.nossos

    def __post_init__(self):
        # Intersecao maior que um dos lados significa que os conjuntos comparados
        # nao sao o que a conta assume. Ja aconteceu: `comparar_espelho` usava o
        # total do espelho como intersecao, e o espelho inclui cliente da sync em
        # massa que nunca passou pelo funil, entao "so nossos" saia negativo na
        # tela. Falhar aqui e melhor que exibir numero impossivel.
        if self.intersecao is not None and self.intersecao > min(self.nossos, self.deles):
            raise ValueError(
                f'{self.titulo}: intersecao ({self.intersecao}) maior que um dos '
                f'lados (nossos={self.nossos}, deles={self.deles})'
            )

    @property
    def so_nossos(self) -> int | None:
        return None if self.intersecao is None else self.nossos - self.intersecao

    @property
    def so_deles(self) -> int | None:
        return None if self.intersecao is None else self.deles - self.intersecao


def _qs_leads(tenant):
    from apps.comercial.leads.models import LeadProspecto
    return LeadProspecto.all_tenants.filter(tenant=tenant)


def _qs_ops(tenant):
    from apps.comercial.crm.models import OportunidadeVenda
    return OportunidadeVenda.all_tenants.filter(tenant=tenant)


def _qs_clientes(tenant):
    from apps.integracoes.models import ClienteHubsoft
    return ClienteHubsoft.all_tenants.filter(tenant=tenant)


def confiabilidade_espelho(tenant) -> dict:
    """O quanto da pra confiar nos numeros do lado HubSoft.

    A tela DEVE mostrar isso junto das comparacoes. O espelho so recebe cliente
    de lead que chegou em `status_api='processado'`; lead parado em rascunho
    nunca entra, entao o lado "HubSoft" aparece menor do que a realidade.
    """
    clientes = _qs_clientes(tenant)
    ultima = clientes.order_by('-data_sync').values_list('data_sync', flat=True).first()
    leads = _qs_leads(tenant)
    presos = leads.filter(status_api=STATUS_RASCUNHO).count()

    horas = None
    if ultima:
        horas = (timezone.now() - ultima).total_seconds() / 3600

    if ultima is None:
        estado = 'sem_dados'
    elif horas is not None and horas > 48:
        estado = 'defasado'
    elif presos:
        estado = 'incompleto'
    else:
        estado = 'ok'

    return {
        'ultima_sync': ultima,
        'horas_desde_sync': round(horas, 1) if horas is not None else None,
        'clientes_espelhados': clientes.count(),
        'leads_presos_em_rascunho': presos,
        'estado': estado,
    }


def comparar_vendas(tenant, dias: int = 30) -> Divergencia:
    """Oportunidades ganhas no CRM x clientes com servico vendido no HubSoft.

    Os dois lados medem coisas diferentes de proposito: o CRM conta a venda que
    passou pelo nosso funil, o HubSoft conta o servico efetivamente vendido.
    Por isso `intersecao` importa mais que a diferenca bruta — foi o que
    mostrou, em 21/07, que 276 e 240 so se sobrepunham em 132.
    """
    corte = timezone.now() - timedelta(days=dias)

    ganhas = _qs_ops(tenant).filter(
        estagio__is_final_ganho=True, data_fechamento_real__gte=corte,
    )
    nossos = ganhas.count()

    # lead_id das ganhas que tem cliente espelhado = a intersecao real
    leads_ganhos = set(ganhas.exclude(lead__isnull=True).values_list('lead_id', flat=True))
    clientes_periodo = _qs_clientes(tenant).filter(data_cadastro_hubsoft__gte=corte)
    deles = clientes_periodo.count()
    leads_com_cliente = set(
        clientes_periodo.exclude(lead__isnull=True).values_list('lead_id', flat=True)
    )
    intersecao = len(leads_ganhos & leads_com_cliente)

    sem_cliente = len(leads_ganhos - leads_com_cliente)
    return Divergencia(
        titulo='Vendas no periodo',
        nossos=nossos, deles=deles, intersecao=intersecao,
        rotulo_nossos='Ganhas no CRM', rotulo_deles='Clientes novos no HubSoft',
        severidade='critico' if sem_cliente > nossos * 0.2 else 'atencao',
        explicacao=(
            'Os dois lados contam coisas diferentes: o CRM conta a venda que passou '
            'pelo nosso funil, o HubSoft conta o cliente que foi cadastrado la. '
            f'{sem_cliente} oportunidades ganhas nao tem cliente espelhado.'
        ),
        detalhes=[
            ('Ganhas sem cliente no HubSoft', sem_cliente),
            ('Clientes novos sem oportunidade ganha', len(leads_com_cliente - leads_ganhos)),
        ],
    )


def comparar_leads(tenant) -> Divergencia:
    """Leads nossos x prospectos criados no HubSoft.

    Cuidado ao comparar com o relatorio de CRM do HubSoft: aquele arquivo conta
    CARTAO, nao pessoa (em 21/07 eram 1226 linhas para 842 pessoas, porque 382
    cartoes nao tinham prospecto nenhum atras). Aqui o lado HubSoft e medido por
    `id_hubsoft` preenchido, que e prospecto de verdade.
    """
    leads = _qs_leads(tenant)
    nossos = leads.count()
    com_prospecto = leads.exclude(id_hubsoft__isnull=True).exclude(id_hubsoft='').count()
    sem_prospecto = nossos - com_prospecto

    return Divergencia(
        titulo='Leads x prospectos',
        nossos=nossos, deles=com_prospecto, intersecao=com_prospecto,
        rotulo_nossos='Leads no Hubtrix', rotulo_deles='Com prospecto no HubSoft',
        severidade='atencao' if sem_prospecto else 'info',
        explicacao=(
            f'{sem_prospecto} leads nunca geraram prospecto no HubSoft. '
            'Se estiver comparando com o relatorio de CRM do HubSoft, lembre que '
            'aquele arquivo conta cartao e nao pessoa.'
        ),
        detalhes=[('Leads sem prospecto no HubSoft', sem_prospecto)],
    )


def comparar_espelho(tenant) -> Divergencia:
    """Leads que deveriam ter virado cliente x os que realmente viraram.

    E a comparacao que revela a causa raiz das outras: lead que fica em
    `rascunho_hubsoft` nunca entra na fila do sync, entao nunca vira
    `ClienteHubsoft`, e some de todo relatorio que dependa do espelho.
    """
    leads = _qs_leads(tenant)
    por_status = dict(
        leads.values_list('status_api').annotate(n=Count('id')).values_list('status_api', 'n')
    )
    presos = por_status.get(STATUS_RASCUNHO, 0)
    processados = por_status.get('processado', 0)
    enviados = processados + presos

    clientes = _qs_clientes(tenant)
    # So conta como "virou cliente" quem esta amarrado a um lead nosso. O
    # espelho tambem recebe cliente da sync em massa, que nunca passou pelo
    # funil; incluir esses inflaria o lado HubSoft e produziria intersecao
    # maior que os proprios conjuntos.
    com_lead = clientes.exclude(lead__isnull=True)
    viraram_cliente = com_lead.values('lead_id').distinct().count()
    orfaos = clientes.filter(lead__isnull=True).count()

    ganhas_sem_cliente = _qs_ops(tenant).filter(
        estagio__is_final_ganho=True,
    ).exclude(
        lead_id__in=com_lead.values('lead_id')
    ).count()

    return Divergencia(
        titulo='Espelho de clientes',
        nossos=enviados, deles=viraram_cliente, intersecao=viraram_cliente,
        rotulo_nossos='Leads enviados ao HubSoft', rotulo_deles='Viraram cliente',
        severidade='critico' if presos > processados else 'atencao',
        explicacao=(
            f'{presos} leads estao parados em "{STATUS_RASCUNHO}": o prospecto foi '
            'criado no HubSoft mas o cadastro nunca foi completado aqui, entao o '
            'cron de sincronizacao (que so processa status "processado") nunca os '
            'transforma em cliente.'
        ),
        detalhes=[
            ('Presos em rascunho_hubsoft', presos),
            ('Em status de erro', sum(por_status.get(s, 0) for s in STATUS_ERRO)),
            ('Oportunidades ganhas sem cliente', ganhas_sem_cliente),
            ('Clientes no espelho sem lead vinculado', orfaos),
        ],
    )


def qualidade_campos(tenant) -> list:
    """Campos que fazem relatorio subcontar quando vem vazio.

    Nao e comparacao entre sistemas: e a saude do dado do nosso lado. Entra aqui
    porque foi a causa de tres numeros questionados pelo cliente (grafico de
    cidade, receita e ticket medio).
    """
    leads = _qs_leads(tenant)
    total_leads = leads.count()

    vazio = Q(cidade__isnull=True) | Q(cidade='')
    sem_cidade = leads.filter(vazio).count()
    sem_cpf = leads.filter(Q(cpf_cnpj__isnull=True) | Q(cpf_cnpj='')).count()
    sem_plano = leads.filter(id_plano_rp__isnull=True).count()

    ganhas = _qs_ops(tenant).filter(estagio__is_final_ganho=True)
    total_ganhas = ganhas.count()
    ganhas_sem_plano = ganhas.filter(lead__id_plano_rp__isnull=True).count()

    def _linha(rotulo, n, base, universo, impacto):
        # cada linha tem seu proprio denominador: medir "venda sem plano" contra
        # o total de LEADS daria um percentual bonito e errado
        pct = round(100 * n / base, 1) if base else 0.0
        return {
            'rotulo': rotulo, 'quantidade': n, 'base': base,
            'universo': universo, 'percentual': pct, 'impacto': impacto,
            'severidade': 'critico' if pct > 50 else ('atencao' if n else 'ok'),
        }

    return [
        _linha('Leads sem cidade', sem_cidade, total_leads, 'leads',
               'O grafico "Leads por cidade" ignora esses, entao mostra menos do que existe.'),
        _linha('Leads sem CPF/CNPJ', sem_cpf, total_leads, 'leads',
               'Sem documento o lead nao vira prospecto no HubSoft.'),
        _linha('Leads sem plano', sem_plano, total_leads, 'leads',
               'Plano vazio zera o valor do lead.'),
        _linha('Vendas ganhas sem plano', ganhas_sem_plano, total_ganhas, 'vendas ganhas',
               'Somam zero em "Receita gerada", entao a receita aparece menor do que foi.'),
    ]


def montar_reconciliacao(tenant, dias: int = 30) -> dict:
    """Tudo que a pagina precisa, numa chamada."""
    return {
        'tenant': tenant,
        'dias': dias,
        'confiabilidade': confiabilidade_espelho(tenant),
        'divergencias': [
            comparar_vendas(tenant, dias=dias),
            comparar_leads(tenant),
            comparar_espelho(tenant),
        ],
        'qualidade': qualidade_campos(tenant),
    }
