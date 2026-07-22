"""Matriz funil x funil: nossas oportunidades x os cards do CRM do HubSoft.

Nao existe API de cards do HubSoft (o /crm/all so lista boards, todo drill da
404), entao a unica fonte do lado deles e o export .xlsx da Gabi. Este service:

  1. parseia a planilha (parse_planilha)
  2. classifica a etapa deles em ganho/aberto/perdido (situacao_deles)
  3. cruza por id_prospecto contra as nossas OportunidadeVenda AO VIVO e monta a
     matriz de concordancia, os duplicados e o que so existe de um lado
     (montar_aba)

A planilha e um retrato do momento do envio; o NOSSO lado e recalculado a cada
visita, entao movimentacao no CRM aparece na hora e a matriz nunca fica velha
do nosso lado.

Chave de cruzamento: o `id_prospecto` do card contra o `id_hubsoft` do nosso
lead (que E o id do prospecto que criamos no HubSoft: foi assim que 24211 do
nosso lado casou com o card 24210). Custou uma sessao provar que ela e melhor
que CPF (casou 763 contra 232), porque a maioria dos cards nao tem CPF.
"""
from __future__ import annotations

import re

# Situacoes canonicas da etapa do HubSoft (usadas em situacao_deles). A
# comparacao de situacao funil x funil saiu (a Nuvyon opera no nosso CRM), mas o
# mapa fica: a etapa ainda e util pra rotular o card e pode voltar a servir.
GANHO, ABERTO, PERDIDO = 'ganho', 'aberto', 'perdido'

# Colunas que o parser aproveita da planilha. As demais (email, valor, plano,
# a data_cadastro_prospecto duplicada) sao ignoradas de proposito.
COLUNAS = (
    'id_prospecto', 'crm', 'crm_etapa', 'status_prospecto', 'nome_cartao',
    'nome_prospecto', 'prospecto_cpf_cnpj', 'prospecto_telefone', 'tag',
    'usuario', 'data_cadastro_cartao',
)

# Etapas do HubSoft que contam como perda. O resto que nao e "CADASTRO APROVADO"
# fica em aberto (negociacao viva): ASSUNTOS COMERCIAIS, LOJA VIRTUAL NUVYON,
# CAPTACAO DE CLIENTE, ANALISE DE VIABILIDADE.
_PERDIDO_EXATO = {'CREDITO NEGADO', 'VIABILIDADE NEGATIVA'}


def _digitos(v) -> str:
    return re.sub(r'\D', '', str(v or ''))


def _norm_id(v) -> str:
    """id_prospecto vem numero na planilha (24291 ou 24291.0) e texto no nosso
    lead. Normaliza os dois pro mesmo formato so digitos."""
    s = str(v or '').strip()
    if s.endswith('.0'):
        s = s[:-2]
    return _digitos(s)


def situacao_deles(crm_etapa: str) -> str:
    """Traduz a etapa do CRM deles nas nossas tres situacoes."""
    e = (crm_etapa or '').strip().upper()
    if e == 'CADASTRO APROVADO':
        return GANHO
    if e.startswith('DESIST') or e in _PERDIDO_EXATO:
        return PERDIDO
    return ABERTO


def parse_planilha(arquivo) -> list[dict]:
    """Le o .xlsx do CRM e devolve um card normalizado por linha.

    Tolerante a coluna faltando (outro export pode nao ter `tag`/`usuario`) e a
    header repetido (a planilha traz `data_cadastro_prospecto` duas vezes): usa
    a primeira ocorrencia de cada nome. Descarta linha sem id_prospecto, que nao
    da pra casar.
    """
    import openpyxl

    wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    linhas = ws.iter_rows(values_only=True)
    try:
        cabecalho = [str(h).strip() if h is not None else '' for h in next(linhas)]
    except StopIteration:
        return []

    # primeira ocorrencia de cada coluna que interessa
    idx = {}
    for col in COLUNAS:
        if col in cabecalho:
            idx[col] = cabecalho.index(col)

    def val(linha, col):
        i = idx.get(col)
        if i is None or i >= len(linha):
            return ''
        return '' if linha[i] is None else str(linha[i]).strip()

    cards = []
    for linha in linhas:
        idp = _norm_id(val(linha, 'id_prospecto'))
        if not idp:
            continue
        etapa = val(linha, 'crm_etapa')
        cards.append({
            'id_prospecto': idp,
            'crm': val(linha, 'crm'),
            'crm_etapa': etapa,
            'situacao': situacao_deles(etapa),
            'status_prospecto': val(linha, 'status_prospecto'),
            'nome_cartao': val(linha, 'nome_cartao'),
            'nome_prospecto': val(linha, 'nome_prospecto'),
            'cpf': _digitos(val(linha, 'prospecto_cpf_cnpj')),
            'telefone': _digitos(val(linha, 'prospecto_telefone')),
            'tag': val(linha, 'tag'),
            'usuario': val(linha, 'usuario'),
            'data_cadastro_cartao': val(linha, 'data_cadastro_cartao'),
        })
    wb.close()
    return cards


def _importacao_atual(tenant):
    from apps.integracoes.models import ImportacaoCRMHubsoft
    return (ImportacaoCRMHubsoft.all_tenants
            .filter(tenant=tenant).order_by('-enviado_em').first())


def _indices_nossos(tenant):
    """Nossos indices, lidos uma vez: o conjunto de id_hubsoft das nossas
    oportunidades (o id_hubsoft do lead E o id do prospecto que criamos, entao
    casa direto com o id_prospecto do card), e lead por cpf/telefone pra achar
    duplicata."""
    from apps.comercial.crm.models import OportunidadeVenda
    from apps.comercial.leads.models import LeadProspecto

    op_ids = set()
    for o in (OportunidadeVenda.all_tenants
              .filter(tenant=tenant).values_list('lead__id_hubsoft', flat=True)):
        idp = _norm_id(o)
        if idp:
            op_ids.add(idp)

    lead_por_cpf, lead_por_tel = {}, {}
    for lead in LeadProspecto.all_tenants.filter(tenant=tenant):
        info = {'lead_id': lead.pk, 'nome': lead.nome_razaosocial or '',
                'id_hubsoft': _norm_id(lead.id_hubsoft)}
        cpf = _digitos(lead.cpf_cnpj)
        if cpf:
            lead_por_cpf.setdefault(cpf, info)
        tel = _digitos(lead.telefone)
        if len(tel) >= 10:
            lead_por_tel.setdefault(tel[-8:], info)
    return op_ids, lead_por_cpf, lead_por_tel


def montar_aba(tenant) -> dict:
    """Tudo que a aba Oportunidades precisa. Sem cache: e leitura local (DB +
    JSON), rapida, e o valor e refletir o nosso funil ao vivo.

    Nao compara mais situacao (matriz funil x funil): a Nuvyon opera no NOSSO
    CRM, entao os cards do CRM do HubSoft sao retrato congelado e "divergencia"
    virava so defasagem. Sobrou o que independe de qual CRM usam: qualidade de
    dado (prospecto duplicado, card sem prospecto) e cobertura de captura.
    """
    imp = _importacao_atual(tenant)
    if imp is None:
        return {'tem_import': False}

    todos = imp.cards or []

    # id_prospecto = 0 e o card aberto direto no CRM sem nunca linkar um prospecto
    # no HubSoft (cpf "Nao Possui prospecto", sem telefone). Nao tem chave nenhuma
    # pra casar, entao vira bucket proprio em vez de inchar "so existem la" e a
    # cobertura. Na planilha de 21/07 eram 382 dos 1226.
    sem_prospecto = [c for c in todos if c['id_prospecto'] in ('', '0')]
    cards = [c for c in todos if c['id_prospecto'] not in ('', '0')]

    op_ids, lead_por_cpf, lead_por_tel = _indices_nossos(tenant)

    duplicados, so_deles = [], []
    casados = 0

    for c in cards:
        if c['id_prospecto'] in op_ids:
            casados += 1
            continue

        # nao casou por id_prospecto: a pessoa existe aqui com OUTRO id (duplicata)?
        lead = (lead_por_cpf.get(c['cpf']) if c['cpf'] else None)
        if lead is None and len(c['telefone']) >= 10:
            lead = lead_por_tel.get(c['telefone'][-8:])
        if lead and lead['id_hubsoft'] and lead['id_hubsoft'] != c['id_prospecto']:
            duplicados.append({**c,
                               'lead_id': lead['lead_id'],
                               'nosso_id_hubsoft': lead['id_hubsoft'],
                               'nosso_nome': lead['nome']})
        else:
            so_deles.append(c)

    # cobertura sobre os cards REAIS (com prospecto), nao sobre os 1226 crus, pra
    # os 382 sem_prospecto nao derrubarem o percentual
    total = len(cards)
    so_nossos = len(op_ids - {c['id_prospecto'] for c in cards})

    # Uma lista unica de problemas, com a categoria por linha, pra a tela usar UMA
    # datatable com chips (mesmo padrao da aba Vendas).
    problemas = _unificar(duplicados, so_deles, sem_prospecto)
    chips = [
        {'slug': 'Duplicado', 'total': len(duplicados)},
        {'slug': 'Só existe lá', 'total': len(so_deles)},
        {'slug': 'Sem prospecto', 'total': len(sem_prospecto)},
    ]

    return {
        'tem_import': True,
        'enviado_em': imp.enviado_em,
        'nome_arquivo': imp.nome_arquivo,
        'total_cards': len(todos),
        'total': total,
        'casados': casados,
        'cobertura_pct': round(100.0 * casados / total) if total else 0,
        'total_so_deles': len(so_deles),
        'total_duplicados': len(duplicados),
        'total_sem_prospecto': len(sem_prospecto),
        'so_nossos': so_nossos,
        'problemas': problemas,
        'total_problemas': len(problemas),
        'chips': [c for c in chips if c['total']],
    }


def _linha(card, categoria, detalhe='', lead_id=None, tag=None):
    return {
        'categoria': categoria,
        'nome': card.get('nome_cartao') or card.get('nome_prospecto') or '',
        'id_prospecto': card['id_prospecto'],
        'crm_etapa': card['crm_etapa'],
        'detalhe': detalhe,
        'tag': card.get('tag', '') if tag is None else tag,
        'usuario': card.get('usuario', ''),
        'lead_id': lead_id,
    }


def _unificar(duplicados, so_deles, sem_prospecto) -> list:
    """Achata os tres baldes numa lista so, cada linha com sua categoria e um
    campo `detalhe` que carrega o que e especifico de cada tipo (nosso lead,
    telefone ou equipe)."""
    linhas = []
    for x in duplicados:
        linhas.append(_linha(x, 'Duplicado',
                             detalhe=f"Nosso lead #{x['lead_id']} (id_hs {x['nosso_id_hubsoft']})",
                             lead_id=x.get('lead_id')))
    for x in so_deles:
        linhas.append(_linha(x, 'Só existe lá',
                             detalhe=f"tel {x['telefone']}" if x.get('telefone') else ''))
    for x in sem_prospecto:
        # sem prospecto nao tem tag util; a equipe (board) e o que importa
        linhas.append(_linha(x, 'Sem prospecto', detalhe=x.get('crm', ''), tag=x.get('crm', '')))
    return linhas
