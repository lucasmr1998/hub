"""
Engine que resolve a query de 1 Widget contra o registry de Data Sources.

Sempre via Django ORM (nunca SQL cru). Filtros validados contra schema do
DataSource — campo nao existente eh ignorado. Multi-tenant automatico
via manager `objects` (que ja filtra por request.tenant).

Saida: dict `{labels: [...], series: [{name, data: [...]}], total?, meta}`
compativel com Chart.js.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Optional

from django.db.models import Count, Sum, Avg, F, Q
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear
from django.utils import timezone

from apps.relatorios import data_sources as ds_registry


OPERADORES_VALIDOS = {
    'igual':       lambda c, v: Q(**{c: v}),
    'diferente':   lambda c, v: ~Q(**{c: v}),
    'maior':       lambda c, v: Q(**{f'{c}__gt': v}),
    'maior_igual': lambda c, v: Q(**{f'{c}__gte': v}),
    'menor':       lambda c, v: Q(**{f'{c}__lt': v}),
    'menor_igual': lambda c, v: Q(**{f'{c}__lte': v}),
    'contem':      lambda c, v: Q(**{f'{c}__icontains': v}),
    'comeca':      lambda c, v: Q(**{f'{c}__istartswith': v}),
    'em':          lambda c, v: Q(**{f'{c}__in': v if isinstance(v, list) else [v]}),
    'existe':      lambda c, v: ~Q(**{f'{c}__isnull': True}) & ~Q(**{c: ''}),
    'nao_existe':  lambda c, v: Q(**{f'{c}__isnull': True}) | Q(**{c: ''}),
    'entre':       lambda c, v: Q(**{f'{c}__range': v}) if isinstance(v, (list, tuple)) and len(v) == 2 else Q(),
    'ultimos_dias': lambda c, v: Q(**{f'{c}__gte': timezone.now() - timedelta(days=int(v))}),
    # Data mais antiga que N dias atras (ex: "parado no estagio ha mais de 7 dias")
    'ha_mais_de_dias': lambda c, v: Q(**{f'{c}__lt': timezone.now() - timedelta(days=int(v))}),
}


TRUNC_BY_GRAN = {
    'dia':    TruncDay,
    'semana': TruncWeek,
    'mes':    TruncMonth,
    'ano':    TruncYear,
}


@dataclass
class ResultadoQuery:
    labels: list = field(default_factory=list)
    series: list = field(default_factory=list)
    total: Optional[float] = None
    meta: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            'labels': self.labels,
            'series': self.series,
            'total': self.total,
            'meta': self.meta,
        }


class WidgetQueryError(Exception):
    pass


class WidgetQueryBuilder:
    """
    Constroi e executa a query de um Widget.

    Uso:
        builder = WidgetQueryBuilder(widget, tenant=request.tenant)
        resultado = builder.build()   # ResultadoQuery
    """

    def __init__(self, widget, tenant=None, overrides=None):
        self.widget = widget
        self.tenant = tenant
        # Filtros globais do dashboard (barra no topo). Suporta:
        #   {'dias': 7|30|90|'tudo', 'fonte': 'facebook'|'organico'}
        # 'dias' substitui o valor de filtros `ultimos_dias` existentes no
        # widget ('tudo' remove o filtro). 'fonte' injeta filtro de origem
        # de trafego nos data sources que tem o campo.
        self.overrides = overrides or {}
        self.data_source = ds_registry.get(widget.data_source)
        if not self.data_source:
            raise WidgetQueryError(f'Data source desconhecido: {widget.data_source}')

    # ------------- API publica -------------

    def build(self) -> ResultadoQuery:
        qs = self._base_queryset()
        qs = self._aplicar_filtros(qs)
        metrica = self.widget.metrica or {'tipo': 'count'}
        agrupamento = self.widget.agrupamento or {}

        # Caso 1: numero unico (sem agrupamento) ou widget tipo=numero
        if self.widget.visualizacao == 'numero' or not agrupamento:
            return self._calcular_numero(qs, metrica)

        # Caso 2: agrupado (com ou sem serie temporal)
        return self._calcular_agrupado(qs, metrica, agrupamento)

    # ------------- internos -------------

    def _base_queryset(self):
        Model = self.data_source.resolve_model()
        manager = self.data_source.manager
        qs = getattr(Model, manager).all()
        # Se manager nao filtra por tenant automaticamente, filtra manual
        if self.tenant and hasattr(Model, 'tenant'):
            try:
                qs = qs.filter(tenant=self.tenant)
            except Exception:
                pass  # 'objects' ja deve estar filtrando
        return qs

    def _validar_campo(self, campo: str) -> bool:
        if not campo:
            return False
        return campo in (self.data_source.campos or {})

    def _aplicar_filtros(self, qs):
        dias_override = self.overrides.get('dias')
        for f in (self.widget.filtros or []):
            campo = f.get('campo')
            operador = f.get('operador', 'igual')
            valor = f.get('valor')
            if not self._validar_campo(campo) or operador not in OPERADORES_VALIDOS:
                continue
            # Override global de periodo: substitui valor dos ultimos_dias;
            # 'tudo' remove o filtro de data por completo
            if operador == 'ultimos_dias' and dias_override:
                if dias_override == 'tudo':
                    continue
                valor = dias_override
            try:
                qs = qs.filter(OPERADORES_VALIDOS[operador](campo, valor))
            except Exception:
                continue

        # Override global de fonte de trafego
        fonte = self.overrides.get('fonte')
        if fonte:
            campo_fonte = None
            if 'lead__fonte' in (self.data_source.campos or {}):
                campo_fonte = 'lead__fonte'
            elif 'fonte' in (self.data_source.campos or {}):
                campo_fonte = 'fonte'
            if campo_fonte:
                try:
                    if fonte == 'organico':
                        qs = qs.exclude(**{campo_fonte: 'facebook'})
                    else:
                        qs = qs.filter(**{campo_fonte: fonte})
                except Exception:
                    pass
        return qs

    def _agg_expr(self, metrica: dict):
        tipo = (metrica or {}).get('tipo', 'count')
        campo = (metrica or {}).get('campo')
        if tipo == 'count':
            return Count('id')
        if tipo == 'sum' and campo:
            return Sum(campo)
        if tipo == 'avg' and campo:
            return Avg(campo)
        return Count('id')

    def _calcular_numero(self, qs, metrica: dict) -> ResultadoQuery:
        agg = self._agg_expr(metrica)
        result = qs.aggregate(valor=agg)
        valor = result.get('valor') or 0
        return ResultadoQuery(
            labels=['Total'],
            series=[{'name': self._label_metrica(metrica), 'data': [float(valor)]}],
            total=float(valor),
            meta={'data_source': self.data_source.slug, 'metrica': metrica},
        )

    def _calcular_agrupado(self, qs, metrica: dict, agrupamento: dict) -> ResultadoQuery:
        dimensao = agrupamento.get('dimensao')
        granularidade = agrupamento.get('granularidade')
        if not self._validar_campo(dimensao):
            raise WidgetQueryError(f'Dimensao invalida: {dimensao}')

        agg = self._agg_expr(metrica)

        # Serie temporal: aplica Trunc se dimensao eh datetime + granularidade
        spec = self.data_source.campos.get(dimensao)
        eh_datetime = spec and spec.tipo in ('datetime', 'date')
        if eh_datetime and granularidade in TRUNC_BY_GRAN:
            trunc = TRUNC_BY_GRAN[granularidade](dimensao)
            qs2 = qs.annotate(_bucket=trunc).values('_bucket').annotate(_valor=agg).order_by('_bucket')
            labels = []
            data = []
            for row in qs2:
                bucket = row['_bucket']
                if isinstance(bucket, (datetime, date)):
                    labels.append(bucket.strftime('%d/%m/%Y' if granularidade in ('dia','semana') else '%m/%Y' if granularidade == 'mes' else '%Y'))
                else:
                    labels.append(str(bucket) if bucket else '—')
                data.append(float(row['_valor'] or 0))
            return ResultadoQuery(
                labels=labels,
                series=[{'name': self._label_metrica(metrica), 'data': data}],
                total=sum(data) if data else 0,
                meta={'data_source': self.data_source.slug, 'metrica': metrica,
                      'dimensao': dimensao, 'granularidade': granularidade},
            )

        # Agrupamento categorico (string/choice)
        qs2 = qs.values(dimensao).annotate(_valor=agg).order_by('-_valor')[:50]
        labels, data = [], []
        for row in qs2:
            valor_label = row[dimensao]
            labels.append(str(valor_label) if valor_label is not None else '—')
            data.append(float(row['_valor'] or 0))

        # Pos-processamento opcional (transform). Permite manipular resultados
        # antes de retornar — util pro funil comercial que agrupa varios
        # estagios finais ganhos como uma unica linha "Contratacao".
        transform = (agrupamento or {}).get('transform')
        if transform:
            labels, data = self._aplicar_transform(transform, dimensao, qs, labels, data)

        meta_out = {'data_source': self.data_source.slug, 'metrica': metrica, 'dimensao': dimensao}
        if transform:
            meta_out['transform'] = transform
            # funil_macro deixa os numeros crus pro front renderizar como fluxo
            if getattr(self, '_macro_meta', None):
                meta_out['macro'] = self._macro_meta

        return ResultadoQuery(
            labels=labels,
            series=[{'name': self._label_metrica(metrica), 'data': data}],
            total=sum(data) if data else 0,
            meta=meta_out,
        )

    def _aplicar_transform(self, transform: str, dimensao: str, qs, labels: list, data: list):
        """Pos-processa resultado do agrupamento aplicando uma transformacao.

        Transforms disponiveis:
        - 'funil_comercial': quando dimensao=estagio__nome, agrupa estagios
          `is_final_ganho` como 'Contratacao' e `is_final_perdido` como
          'Perdido'. Mantem snapshot atual (ops EM cada estagio agora).
          Ordena pelo `ordem` do estagio.
        - 'funil_cumulativo': funil classico de marketing. Etapa 1 = total
          de oportunidades; cada etapa subsequente = quantas passaram por
          aquele estagio (via HistoricoPipelineEstagio). Finais agrupados
          em 'Contratacao' e 'Perdido'. IGNORA o resultado original do
          queryset — recalcula via historico.
        - 'funil_macro': funil de NEGOCIO cross-modelo:
          Atendimentos -> Leads -> Oportunidades -> Vendas | Perdidas.
          IGNORA o queryset — conta direto nos models, janela de N dias
          (agrupamento['dias'], default 30). Percentual de conversao vs
          etapa anterior vai no label. "Vendas" = ops em estagio
          is_final_ganho fechadas no periodo (fonte: CRM, decisao 06/07).
        """
        if transform == 'funil_macro':
            from apps.comercial.leads.models import LeadProspecto, HistoricoContato
            from apps.comercial.crm.models import OportunidadeVenda
            from django.utils import timezone as dj_tz
            from datetime import timedelta as td

            dias = 30
            try:
                dias = int((self.widget.agrupamento or {}).get('dias') or 30)
            except (TypeError, ValueError):
                pass
            # Override global de periodo (barra do dashboard)
            dias_override = self.overrides.get('dias')
            if dias_override == 'tudo':
                cutoff = None
            elif dias_override:
                dias = int(dias_override)
                cutoff = dj_tz.now() - td(days=dias)
            else:
                cutoff = dj_tz.now() - td(days=dias)

            # Override global de fonte: filtra leads/ops/vendas/perdidas.
            # Atendimentos (HistoricoContato) nao tem atribuicao de fonte —
            # fica sempre com o total do periodo.
            fonte = self.overrides.get('fonte')

            def _fonte_q_lead(qs):
                if fonte == 'organico':
                    return qs.exclude(fonte='facebook')
                if fonte:
                    return qs.filter(fonte=fonte)
                return qs

            def _fonte_q_op(qs):
                if fonte == 'organico':
                    return qs.exclude(lead__fonte='facebook')
                if fonte:
                    return qs.filter(lead__fonte=fonte)
                return qs

            atend_qs = HistoricoContato.all_tenants.filter(
                tenant=self.tenant, status='fluxo_inicializado',
            )
            leads_qs = _fonte_q_lead(LeadProspecto.all_tenants.filter(tenant=self.tenant))
            ops_qs = _fonte_q_op(OportunidadeVenda.all_tenants.filter(tenant=self.tenant))
            vendas_qs = _fonte_q_op(OportunidadeVenda.all_tenants.filter(
                tenant=self.tenant, estagio__is_final_ganho=True))
            perdidas_qs = _fonte_q_op(OportunidadeVenda.all_tenants.filter(
                tenant=self.tenant, estagio__is_final_perdido=True))

            if cutoff:
                atend_qs = atend_qs.filter(data_hora_contato__gte=cutoff)
                leads_qs = leads_qs.filter(data_cadastro__gte=cutoff)
                ops_qs = ops_qs.filter(data_criacao__gte=cutoff)
                vendas_qs = vendas_qs.filter(data_fechamento_real__gte=cutoff)
                perdidas_qs = perdidas_qs.filter(data_fechamento_real__gte=cutoff)

            atendimentos = atend_qs.count()
            leads_n = leads_qs.count()
            ops_n = ops_qs.count()
            ops_ads = ops_qs.filter(lead__fonte='facebook').count()
            ops_organico = ops_n - ops_ads
            vendas = vendas_qs.count()
            perdidas = perdidas_qs.count()

            def _pct(parte, todo):
                return round(parte / todo * 100) if todo else 0

            # Numeros crus pro front renderizar como fluxo horizontal
            self._macro_meta = {
                'dias': dias,
                'etapas': [
                    {'label': 'Atendimentos', 'valor': atendimentos, 'pct': None},
                    {'label': 'Leads', 'valor': leads_n, 'pct': _pct(leads_n, atendimentos)},
                    {'label': 'Oportunidades', 'valor': ops_n, 'pct': _pct(ops_n, leads_n),
                     'quebra': [
                         {'label': 'Meta Ads', 'valor': ops_ads, 'pct': _pct(ops_ads, ops_n)},
                         {'label': 'Organico', 'valor': ops_organico, 'pct': _pct(ops_organico, ops_n)},
                     ]},
                ],
                'vendas': {'valor': vendas, 'pct': _pct(vendas, ops_n)},
                'perdidas': {'valor': perdidas, 'pct': _pct(perdidas, ops_n)},
            }

            labels = [
                'Atendimentos',
                f'Leads ({_pct(leads_n, atendimentos)}%)',
                f'Oportunidades ({_pct(ops_n, leads_n)}%)',
                f'Vendas: {vendas} ({_pct(vendas, ops_n)}%) | Perdidas: {perdidas} ({_pct(perdidas, ops_n)}%)',
            ]
            data = [float(atendimentos), float(leads_n), float(ops_n), float(vendas + perdidas)]
            return labels, data

        if transform == 'funil_comercial' and dimensao == 'estagio__nome':
            from apps.comercial.crm.models import PipelineEstagio
            ests = {e.nome: (e.ordem, e.is_final_ganho, e.is_final_perdido)
                    for e in PipelineEstagio.all_tenants.filter(tenant=self.tenant)}
            agg_map = {}
            for lbl, valor in zip(labels, data):
                meta_est = ests.get(lbl)
                if meta_est:
                    ordem, ganho, perdido = meta_est
                    if ganho:
                        label_final = 'Contratacao'; ordem_ord = 9000
                    elif perdido:
                        label_final = 'Perdido'; ordem_ord = 9999
                    else:
                        label_final = lbl; ordem_ord = ordem
                else:
                    label_final = lbl; ordem_ord = 9500
                cur = agg_map.get(label_final, (ordem_ord, 0))
                agg_map[label_final] = (min(cur[0], ordem_ord), cur[1] + valor)
            ordenado = sorted(agg_map.items(), key=lambda kv: kv[1][0])
            labels = [k for k, _ in ordenado]
            data = [v[1] for _, v in ordenado]

        elif transform == 'funil_cumulativo':
            # Funil classico: pra cada estagio do pipeline (ordenado por ordem),
            # quantas oportunidades JA PASSARAM por aquele estagio (incluindo
            # as que ja avancaram). Usa HistoricoPipelineEstagio.estagio_novo
            # distintos por oportunidade.
            #
            # Filtra estagios SO dos pipelines presentes no queryset filtrado.
            # Sem isso, tenants com 2+ pipelines (Nuvyon: "Atendimento Bot" +
            # "CRM Mococa") misturariam estagios diferentes no mesmo funil.
            from apps.comercial.crm.models import (
                PipelineEstagio, HistoricoPipelineEstagio,
            )
            pipeline_ids = list(qs.values_list('pipeline_id', flat=True).distinct())
            pipeline_ids = [p for p in pipeline_ids if p]
            if not pipeline_ids:
                return [], []
            estagios = list(PipelineEstagio.all_tenants.filter(
                tenant=self.tenant, ativo=True, pipeline_id__in=pipeline_ids,
            ).order_by('ordem'))

            # qs eh OportunidadeVenda ja filtrado pelo _aplicar_filtros.
            op_ids = list(qs.values_list('id', flat=True))
            if not op_ids:
                return [], []

            # Pra funil ser monotonicamente descendente: cada etapa N conta
            # as ops que ALCANCARAM N OU qualquer etapa POSTERIOR (chegaram
            # pelo menos ate N).
            #
            # Passo 1: descobrir o maior `ordem` que cada op ja alcancou,
            # via estagio_atual + historico (estagio_novo + estagio_anterior).
            est_meta = {e.id: (e.pipeline_id, e.ordem, e.is_final_ganho, e.is_final_perdido)
                        for e in estagios}

            # ordem_max por op
            ordem_max_por_op = {}
            def _registrar(op_id, est_id):
                if not est_id or est_id not in est_meta:
                    return
                ord_ = est_meta[est_id][1]
                cur = ordem_max_por_op.get(op_id)
                if cur is None or ord_ > cur:
                    ordem_max_por_op[op_id] = ord_

            historicos = HistoricoPipelineEstagio.all_tenants.filter(
                tenant=self.tenant, oportunidade_id__in=op_ids,
            ).values_list('oportunidade_id', 'estagio_novo_id', 'estagio_anterior_id')
            for op_id, est_novo, est_ant in historicos:
                _registrar(op_id, est_novo)
                _registrar(op_id, est_ant)

            # Estagio atual + garantir que toda op tenha pelo menos o estagio inicial
            for op_id, est_id_atual in qs.values_list('id', 'estagio_id'):
                _registrar(op_id, est_id_atual)
                # Op sem historico nem estagio reconhecido — assume ordem 1
                ordem_max_por_op.setdefault(op_id, 1)

            # Sinaliza ops que JA chegaram em estagio final (ganho/perdido)
            # via QUALQUER ponto da jornada (atual ou historico). Necessario
            # porque a "ordem" do estagio final pode estar abaixo da ordem
            # de etapas intermediarias avancadas (varia por pipeline).
            ops_ganhas = set()
            ops_perdidas = set()
            def _check_final(op_id, est_id):
                if est_id and est_id in est_meta:
                    _, _, ganho, perdido = est_meta[est_id]
                    if ganho:
                        ops_ganhas.add(op_id)
                    if perdido:
                        ops_perdidas.add(op_id)
            for op_id, est_novo, est_ant in historicos:
                _check_final(op_id, est_novo)
                _check_final(op_id, est_ant)
            for op_id, est_id_atual in qs.values_list('id', 'estagio_id'):
                _check_final(op_id, est_id_atual)

            # Inclui TODAS as ops (ganhas, perdidas, em andamento). Topo
            # do funil = total de ops do periodo; etapas intermediarias
            # descendem cumulativamente; final = Contratacao | Perdido
            # em 1 linha.
            todas_ops = set(ordem_max_por_op.keys())

            # Monta funil — etapas intermediarias (nao finais), ordenadas por ordem.
            # Cada etapa N: count(ops cujo ordem_max >= N).
            etapas_intermediarias = []
            etagios_nao_finais = [e for e in estagios if not e.is_final_ganho and not e.is_final_perdido]
            etagios_nao_finais.sort(key=lambda e: e.ordem)
            for est in etagios_nao_finais:
                count = sum(1 for o in todas_ops if ordem_max_por_op[o] >= est.ordem)
                etapas_intermediarias.append((est.ordem, est.nome, count))

            etapas_intermediarias.sort(key=lambda x: x[0])
            labels = [n for _, n, _ in etapas_intermediarias]
            data = [float(c) for _, _, c in etapas_intermediarias]
            # Linha final = Contratacao + Perdido lado a lado
            n_ganhos = len(ops_ganhas)
            n_perdidos = len(ops_perdidas)
            labels.append(f'Contratacao: {n_ganhos} | Perdido: {n_perdidos}')
            data.append(float(n_ganhos + n_perdidos))

        return labels, data

    def _label_metrica(self, metrica: dict) -> str:
        tipo = (metrica or {}).get('tipo', 'count')
        campo = (metrica or {}).get('campo')
        return {
            'count': 'Total',
            'sum':   f'Soma de {campo}',
            'avg':   f'Media de {campo}',
        }.get(tipo, 'Valor')
