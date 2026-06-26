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
from datetime import datetime, date
from typing import Any, Optional

from django.db.models import Count, Sum, Avg, F, Q
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear

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

    def __init__(self, widget, tenant=None):
        self.widget = widget
        self.tenant = tenant
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
        for f in (self.widget.filtros or []):
            campo = f.get('campo')
            operador = f.get('operador', 'igual')
            valor = f.get('valor')
            if not self._validar_campo(campo) or operador not in OPERADORES_VALIDOS:
                continue
            try:
                qs = qs.filter(OPERADORES_VALIDOS[operador](campo, valor))
            except Exception:
                continue
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

        return ResultadoQuery(
            labels=labels,
            series=[{'name': self._label_metrica(metrica), 'data': data}],
            total=sum(data) if data else 0,
            meta={'data_source': self.data_source.slug, 'metrica': metrica, 'dimensao': dimensao},
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
        """
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

            # "Passou por X" = qualquer indicio de ter estado em X:
            # - estagio_atual = X (ainda esta)
            # - historico.estagio_novo = X (mudou pra X)
            # - historico.estagio_anterior = X (saiu de X)
            #
            # Sem o estagio_anterior, o primeiro estagio onde a op NASCEU
            # (sem gerar historico como destino) some do funil — bug do
            # "Novo Lead: 4" quando o total real eh 200.
            historicos = HistoricoPipelineEstagio.all_tenants.filter(
                tenant=self.tenant, oportunidade_id__in=op_ids,
            ).values_list('oportunidade_id', 'estagio_novo_id', 'estagio_anterior_id')
            passou_por = {}
            for op_id, est_novo, est_ant in historicos:
                if est_novo:
                    passou_por.setdefault(est_novo, set()).add(op_id)
                if est_ant:
                    passou_por.setdefault(est_ant, set()).add(op_id)

            # Estagio atual de cada op
            for op_id, est_id_atual in qs.values_list('id', 'estagio_id'):
                if est_id_atual:
                    passou_por.setdefault(est_id_atual, set()).add(op_id)

            # Primeiro estagio do pipeline recebe TODAS as ops (toda op passou
            # pelo inicio, mesmo que nao tenha historico nem esteja la agora).
            # Sem isso, ops criadas direto em estagios avancados (importadas)
            # mantem o "Novo Lead" subnumerado.
            primeiros_por_pipeline = {}
            for est in estagios:
                cur = primeiros_por_pipeline.get(est.pipeline_id)
                if cur is None or est.ordem < cur.ordem:
                    primeiros_por_pipeline[est.pipeline_id] = est
            for pid, est_primeiro in primeiros_por_pipeline.items():
                ops_do_pipeline = set(qs.filter(pipeline_id=pid).values_list('id', flat=True))
                passou_por.setdefault(est_primeiro.id, set()).update(ops_do_pipeline)

            # Monta funil — agrupa is_final_ganho como 'Contratacao' e
            # is_final_perdido como 'Perdido'. Etapa 1 = total de ops.
            ganhos_set, perdidos_set = set(), set()
            etapas_intermediarias = []  # [(ordem, nome, count)]
            for est in estagios:
                ops_passou = passou_por.get(est.id, set())
                if est.is_final_ganho:
                    ganhos_set |= ops_passou
                elif est.is_final_perdido:
                    perdidos_set |= ops_passou
                else:
                    etapas_intermediarias.append((est.ordem, est.nome, len(ops_passou)))

            etapas_intermediarias.sort(key=lambda x: x[0])
            labels = [n for _, n, _ in etapas_intermediarias]
            data = [float(c) for _, _, c in etapas_intermediarias]
            # Apend finais
            labels.append('Contratacao')
            data.append(float(len(ganhos_set)))
            labels.append('Perdido')
            data.append(float(len(perdidos_set)))

        return labels, data

    def _label_metrica(self, metrica: dict) -> str:
        tipo = (metrica or {}).get('tipo', 'count')
        campo = (metrica or {}).get('campo')
        return {
            'count': 'Total',
            'sum':   f'Soma de {campo}',
            'avg':   f'Media de {campo}',
        }.get(tipo, 'Valor')
