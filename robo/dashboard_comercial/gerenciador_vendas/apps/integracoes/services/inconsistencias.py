"""Inconsistencias entre as vendas do HubSoft e o nosso funil.

Responde uma pergunta so: das vendas que o HubSoft registrou no periodo, quantas
existem no nosso CRM e quantas nao?

CRITERIO, que custou duas tentativas erradas pra achar:
  - NAO e `data_cadastro_cliente`: traz 3838 em julho contra ~300 reais, porque
    cliente antigo tem o cadastro atualizado por migracao de plano e recadastro.
  - NAO e `servico.id_prospecto`: o HubSoft nao preenche esse campo. Vem None
    ate em venda que sabemos ter vindo do nosso funil.
  - E **`servico.data_venda` no periodo**, que e o mesmo criterio do relatorio
    que a Nuvyon usa.

O cruzamento e por CPF, com telefone como segunda tentativa. Medido em 22/07:
311 vendas, 230 com venda ganha aqui, 20 com lead mas sem venda marcada, e 61
que nunca passaram pelo Hubtrix.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

CACHE_SEGUNDOS = 30 * 60
ORIGEM_VAZIA = '(sem origem)'

# Teto de paginacao. A janela de cadastro do ano corrente deu 59 paginas em
# julho; 120 cobre o ano inteiro com folga e ainda impede loop infinito se a
# paginacao do HubSoft vier torta.
MAX_PAGINAS = 120

# Nao e venda nova: e troca de titular num contrato que ja existia. Entra no
# relatorio do HubSoft como se fosse venda, e inflava a conta em 13 casos.
ORIGEM_TITULARIDADE = 'TRANSFERENCIA DE TITULARIDADE'


def _so_digitos(valor) -> str:
    return re.sub(r'\D', '', str(valor or ''))


@dataclass
class Venda:
    codigo_cliente: int
    nome: str
    cpf_cnpj: str
    telefone: str
    origem: str
    plano: str
    data_venda: str
    status_servico: str
    lead_id: int | None = None
    lead_status: str | None = None
    casou_por: str = ''          # 'cpf' | 'telefone' | ''


@dataclass
class GrupoOrigem:
    origem: str
    vendas: list = field(default_factory=list)

    @property
    def quantidade(self) -> int:
        return len(self.vendas)

    @property
    def anomalia(self) -> bool:
        """Canal integrado que escapou. Venda que entra pelo WhatsApp da empresa
        deveria virar lead sozinha; quando nao vira, e furo nosso e nao canal
        descoberto."""
        o = (self.origem or '').upper()
        return 'MATRIX' in o or o.startswith('WHATSAPP EMPRESA')

    @property
    def nao_e_venda(self) -> bool:
        return (self.origem or '').upper().startswith('TRANSFER')


def _inicio_do_mes() -> date:
    from django.utils import timezone
    return timezone.localdate().replace(day=1)


def _buscar_vendas_hubsoft(tenant, inicio: date, fim: date) -> list:
    """Le /cliente/todos paginado e devolve so os SERVICOS vendidos no periodo.

    O filtro da API e por **cadastro do cliente**, nao por data da venda. Isso
    obriga a buscar uma janela de cadastro mais larga que o periodo pedido:
    cliente que virou cliente em marco e contratou outro servico em julho tem a
    venda em julho, mas o cadastro em marco.

    Medido em 22/07 com o periodo de julho:
        janela de cadastro so julho .... 311 vendas (39 paginas)
        janela desde 01/01 do ano ...... 348 vendas (59 paginas)
    As 37 de diferenca sao exatamente clientes cadastrados de janeiro a junho.

    LIMITE CONHECIDO, e a tela diz isso: cliente cadastrado ANTES do ano corrente
    que compre agora ainda escapa. Cobrir 2024 em diante custaria 165 paginas
    (~4 min), o que tornaria a leitura inviavel. Preferimos numero levemente
    incompleto e declarado a numero completo e inutilizavel.
    """
    from apps.integracoes.models import IntegracaoAPI
    from apps.integracoes.services.hubsoft import HubsoftService

    integracao = IntegracaoAPI.all_tenants.filter(
        tenant=tenant, tipo='hubsoft', ativa=True,
    ).first()
    if integracao is None:
        return []

    svc = HubsoftService(integracao)
    meses = {f'{m:02d}/{inicio.year}' for m in range(inicio.month, fim.month + 1)}
    # janela de CADASTRO alargada ate o inicio do ano — ver docstring
    cadastro_desde = date(inicio.year, 1, 1)
    vendas, pagina = [], 0

    while pagina < MAX_PAGINAS:
        resposta = svc.listar_clientes_todos(
            pagina=pagina, itens_por_pagina=100,
            data_inicio=cadastro_desde.isoformat(), data_fim=fim.isoformat(),
        )
        clientes = resposta.get('clientes') or []
        if not clientes:
            break
        for c in clientes:
            for s in (c.get('servicos') or []):
                dv = str(s.get('data_venda') or '')
                if len(dv) < 10 or dv[3:10] not in meses:
                    continue
                vendas.append(Venda(
                    codigo_cliente=c.get('codigo_cliente'),
                    nome=(c.get('nome_razaosocial') or '')[:60],
                    cpf_cnpj=_so_digitos(c.get('cpf_cnpj')),
                    telefone=_so_digitos(c.get('telefone_primario')),
                    origem=(c.get('origem_cliente') or '').strip() or ORIGEM_VAZIA,
                    plano=str(s.get('nome') or '')[:50],
                    data_venda=dv,
                    status_servico=str(s.get('status') or '')[:30],
                ))
        ultima = (resposta.get('paginacao') or {}).get('ultima_pagina', pagina)
        if pagina >= ultima:
            break
        pagina += 1

    return vendas


def _classificar(tenant, vendas: list) -> dict:
    """Cruza cada venda com os nossos leads: CPF primeiro, telefone depois."""
    from apps.comercial.leads.models import LeadProspecto
    from apps.comercial.crm.models import OportunidadeVenda

    por_cpf, por_tel = {}, {}
    for l in LeadProspecto.all_tenants.filter(tenant=tenant):
        cpf = _so_digitos(l.cpf_cnpj)
        if cpf:
            por_cpf.setdefault(cpf, l)
        tel = _so_digitos(l.telefone)
        if len(tel) >= 10:
            por_tel.setdefault(tel[-8:], l)

    ganhas = set(
        OportunidadeVenda.all_tenants
        .filter(tenant=tenant, estagio__is_final_ganho=True)
        .values_list('lead_id', flat=True)
    )

    com_venda, so_lead, sem_nada = [], [], []
    for v in vendas:
        lead = por_cpf.get(v.cpf_cnpj) if v.cpf_cnpj else None
        if lead:
            v.casou_por = 'cpf'
        elif len(v.telefone) >= 8:
            lead = por_tel.get(v.telefone[-8:])
            if lead:
                v.casou_por = 'telefone'
        if lead:
            v.lead_id, v.lead_status = lead.pk, lead.status_api
            (com_venda if lead.pk in ganhas else so_lead).append(v)
        else:
            sem_nada.append(v)

    return {'com_venda': com_venda, 'so_lead': so_lead, 'sem_nada': sem_nada}


def _agrupar_por_origem(vendas: list) -> list:
    grupos: dict[str, GrupoOrigem] = {}
    for v in vendas:
        grupos.setdefault(v.origem, GrupoOrigem(origem=v.origem)).vendas.append(v)
    # anomalia primeiro (exige acao nossa), titularidade por ultimo (nem e venda)
    return sorted(
        grupos.values(),
        key=lambda g: (g.nao_e_venda, not g.anomalia, -g.quantidade),
    )


def montar_pagina(tenant, inicio: date | None = None, fim: date | None = None,
                  forcar: bool = False) -> dict:
    """Tudo que a tela precisa. Cacheado, porque a leitura sao ~39 chamadas de
    API e a pagina ficaria inutilizavel a cada F5."""
    from django.core.cache import cache
    from django.utils import timezone

    inicio = inicio or _inicio_do_mes()
    fim = fim or timezone.localdate()
    chave = f'inconsistencias:{tenant.pk}:{inicio}:{fim}'

    cacheado = None if forcar else cache.get(chave)
    if cacheado is None:
        vendas = _buscar_vendas_hubsoft(tenant, inicio, fim)
        cacheado = {'vendas': vendas, 'lido_em': timezone.now()}
        cache.set(chave, cacheado, CACHE_SEGUNDOS)

    classes = _classificar(tenant, cacheado['vendas'])
    sem_nada = classes['sem_nada']
    titularidade = [v for v in sem_nada if v.origem.upper().startswith('TRANSFER')]

    return {
        'inicio': inicio,
        'fim': fim,
        'lido_em': cacheado['lido_em'],
        # a tela mostra ate onde a busca alcanca, pra ninguem ler o numero como
        # se fosse a totalidade das vendas
        'cadastro_desde': date(inicio.year, 1, 1),
        'total': len(cacheado['vendas']),
        'com_venda': len(classes['com_venda']),
        'so_lead_cpf': sum(1 for v in classes['so_lead'] if v.casou_por == 'cpf'),
        'so_lead_tel': sum(1 for v in classes['so_lead'] if v.casou_por == 'telefone'),
        'recuperaveis': classes['so_lead'],
        'sem_nada': sem_nada,
        'total_sem_nada': len(sem_nada),
        'titularidade': len(titularidade),
        'venda_real_fora': len(sem_nada) - len(titularidade),
        'grupos': _agrupar_por_origem(sem_nada),
    }
