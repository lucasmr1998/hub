"""Inconsistencias entre o funil do Hubtrix e a base do HubSoft.

Diferente de `reconciliacao.py`, que resume numeros, aqui a saida e caso a caso,
pra alguem agir.

Motivacao (apurado em 22/07/2026 na base da Nuvyon): das 270 vendas de julho que
o HubSoft registrou, 126 nao tinham par no nosso funil. A maior parte se resolveu
ligando lead a cliente, mas 51 nunca passaram pelo Hubtrix — e a origem delas
explica por que: 16 vieram de "WhatsApp Ativo" (a vendedora inicia do numero
dela, sem passar pelo bot), 15 de canais sem conversa digital (presencial,
indicacao, ligacao) e 11 sem origem preenchida.

Essa visao so existe se o espelho estiver atualizado, e ai esta o problema que
motivou o modulo: **`/cliente/todos` nunca tinha sido chamado em prod**. Os 1006
clientes sem lead entraram numa carga unica entre 03/06 e 18/06 e nada os
atualizava desde entao.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db.models import Count, Q


@dataclass
class VendaSemCard:
    """Cliente que existe no HubSoft e nunca virou lead aqui."""
    codigo_cliente: int
    id_cliente: int
    nome: str
    cpf_cnpj: str
    origem: str
    cadastrado_em: date | None
    telefone: str


@dataclass
class GrupoOrigem:
    """As vendas de uma origem. A tela agrupa por aqui porque a origem e o que
    diz se o caso e recuperavel: 'WhatsApp Empresa' devia ter entrado e nao
    entrou (anomalia), enquanto 'Presencial Loja' nunca teve conversa digital
    (canal que o Hubtrix nao cobre)."""
    origem: str
    vendas: list = field(default_factory=list)

    @property
    def quantidade(self) -> int:
        return len(self.vendas)

    @property
    def anomalia(self) -> bool:
        """Origem que passa pelo canal integrado deveria ter virado lead. Quando
        nao vira, e furo nosso, nao processo do cliente."""
        o = (self.origem or '').upper()
        return 'MATRIX' in o or o.startswith('WHATSAPP EMPRESA')


ORIGEM_VAZIA = '(origem em branco)'


def _inicio_do_mes(hoje: date | None = None) -> date:
    from django.utils import timezone
    hoje = hoje or timezone.localdate()
    return hoje.replace(day=1)


def vendas_sem_card(tenant, inicio: date | None = None, fim: date | None = None) -> list:
    """Clientes do HubSoft sem lead nosso, agrupados por origem.

    Le so o espelho local — nao chama a API. Se o espelho estiver desatualizado
    a lista vem curta, e por isso a tela mostra a data da ultima sincronizacao
    junto: sem esse contexto o vazio parece "esta tudo certo" quando na verdade
    e "nao perguntei".
    """
    from apps.integracoes.models import ClienteHubsoft
    from django.utils import timezone

    inicio = inicio or _inicio_do_mes()
    fim = fim or timezone.localdate()

    qs = (
        ClienteHubsoft.all_tenants
        .filter(tenant=tenant, lead__isnull=True,
                data_cadastro_hubsoft__date__gte=inicio,
                data_cadastro_hubsoft__date__lte=fim)
        .order_by('-data_cadastro_hubsoft')
    )

    grupos: dict[str, GrupoOrigem] = {}
    for c in qs:
        origem = (c.origem_cliente or '').strip() or ORIGEM_VAZIA
        grupos.setdefault(origem, GrupoOrigem(origem=origem)).vendas.append(
            VendaSemCard(
                codigo_cliente=c.codigo_cliente,
                id_cliente=c.id_cliente,
                nome=c.nome_razaosocial or '',
                cpf_cnpj=c.cpf_cnpj or '',
                origem=origem,
                cadastrado_em=(c.data_cadastro_hubsoft.date()
                               if c.data_cadastro_hubsoft else None),
                telefone=c.telefone_primario or '',
            )
        )

    # anomalia primeiro: e o que exige acao nossa, o resto e canal descoberto
    return sorted(grupos.values(), key=lambda g: (not g.anomalia, -g.quantidade))


def estado_do_espelho(tenant) -> dict:
    """Quando o espelho foi atualizado pela ultima vez, e o quanto ele cobre.

    A tela DEVE mostrar isso junto da lista. Sem essa informacao, lista vazia
    parece "nenhuma inconsistencia" quando pode ser "o espelho esta parado ha
    um mes" — que foi exatamente o caso na Nuvyon ate 22/07.
    """
    from apps.integracoes.models import ClienteHubsoft
    from django.utils import timezone

    qs = ClienteHubsoft.all_tenants.filter(tenant=tenant)
    ultima = qs.order_by('-data_sync').values_list('data_sync', flat=True).first()
    agregado = qs.aggregate(
        total=Count('id'),
        sem_lead=Count('id', filter=Q(lead__isnull=True)),
    )

    horas = None
    if ultima:
        horas = round((timezone.now() - ultima).total_seconds() / 3600, 1)

    return {
        'ultima_sync': ultima,
        'horas_desde_sync': horas,
        'total': agregado['total'],
        'sem_lead': agregado['sem_lead'],
        'desatualizado': horas is None or horas > 24,
    }


def atualizar_espelho(tenant, desde: date | None = None) -> dict:
    """Puxa do HubSoft os clientes modificados desde `desde` e grava no espelho.

    ESTA FUNCAO ESCREVE. Faz upsert de ClienteHubsoft (e dos servicos). E o
    comportamento do `sincronizar_base_clientes` que ja existe; a tela avisa
    disso antes do clique em vez de esconder.

    Escopo curto de proposito: com `modificados_desde` no inicio do mes sao ~3
    paginas de 100, em vez das ~13 da base inteira.
    """
    from datetime import datetime, time as _time

    from apps.integracoes.models import IntegracaoAPI
    from apps.integracoes.services.hubsoft_relatorios import sincronizar_base_clientes

    integracao = IntegracaoAPI.all_tenants.filter(
        tenant=tenant, tipo='hubsoft', ativa=True,
    ).first()
    if integracao is None:
        return {'ok': False, 'erro': 'Nenhuma integracao HubSoft ativa neste tenant.'}

    desde = desde or _inicio_do_mes()
    res = sincronizar_base_clientes(
        integracao,
        modificados_desde=datetime.combine(desde, _time.min),
        itens_por_pagina=100,
    )
    return {
        'ok': getattr(res, 'ok', True),
        'criados': getattr(res, 'criados', 0),
        'atualizados': getattr(res, 'atualizados', 0),
        'total_registros': getattr(res, 'total_registros', 0),
        'erros': getattr(res, 'erros', 0),
        'mensagens_erro': getattr(res, 'mensagens_erro', [])[:3],
    }


def montar_pagina(tenant, inicio: date | None = None, fim: date | None = None) -> dict:
    from django.utils import timezone
    inicio = inicio or _inicio_do_mes()
    fim = fim or timezone.localdate()
    grupos = vendas_sem_card(tenant, inicio, fim)
    return {
        'inicio': inicio,
        'fim': fim,
        'espelho': estado_do_espelho(tenant),
        'grupos': grupos,
        'total_sem_card': sum(g.quantidade for g in grupos),
        'total_anomalia': sum(g.quantidade for g in grupos if g.anomalia),
    }
