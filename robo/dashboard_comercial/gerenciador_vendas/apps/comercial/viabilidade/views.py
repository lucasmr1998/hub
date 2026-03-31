# ============================================================================
# Views migradas de vendas_web.views (Phase 3B)
# ============================================================================
import unicodedata
import logging

import requests as req_ext
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from apps.comercial.viabilidade.models import CidadeViabilidade

logger = logging.getLogger(__name__)


@login_required
def api_viabilidade(request):
    """
    GET /api/viabilidade/
    Consulta regiões com viabilidade técnica.

    Parâmetros opcionais (query string):
        cidade  — filtra pelo nome da cidade (parcial, sem distinção de maiúsculas)
        cep     — filtra pelo CEP (exato ou por cidade correspondente)
        uf      — filtra pelo estado (sigla, ex: PI)

    Comportamento do campo `cep`:
      1. Busca registros onde o CEP informado está cadastrado diretamente.
      2. Normaliza o CEP (somente dígitos) e consulta a API pública ViaCEP
         para obter cidade/estado, então verifica se essa cidade já consta
         na lista de viabilidade (mesmo sem CEP específico cadastrado).
      3. Retorna campo `viavel_pela_cidade` indicando quando a cobertura
         é válida via cidade (e não por CEP cadastrado diretamente).

    Sem nenhum parâmetro → retorna todas as cidades/CEPs com viabilidade.
    """
    def normalizar(texto):
        if not texto:
            return ''
        nfkd = unicodedata.normalize('NFKD', texto.lower())
        return nfkd.encode('ASCII', 'ignore').decode('ASCII').strip()

    cidade_param = request.GET.get('cidade', '').strip()
    cep_param    = request.GET.get('cep', '').replace('-', '').strip()
    uf_param     = request.GET.get('uf', '').upper().strip()

    qs = CidadeViabilidade.objects.filter(ativo=True)

    if uf_param:
        qs = qs.filter(estado=uf_param)

    if cidade_param:
        qs = qs.filter(cidade__icontains=cidade_param)

    # ── Modo busca por CEP ────────────────────────────────────────────────
    if cep_param:
        if len(cep_param) != 8 or not cep_param.isdigit():
            return JsonResponse(
                {'sucesso': False, 'erro': 'CEP inválido. Informe 8 dígitos numéricos.'},
                status=400,
            )

        cep_formatado = f"{cep_param[:5]}-{cep_param[5:]}"

        # 1. Busca direta pelo CEP cadastrado
        qs_cep_direto = CidadeViabilidade.objects.filter(
            ativo=True,
            cep=cep_formatado,
        )
        if uf_param:
            qs_cep_direto = qs_cep_direto.filter(estado=uf_param)

        resultados_diretos = list(qs_cep_direto)

        # 2. Consulta ViaCEP para obter cidade/UF do CEP informado
        cidade_via_cep = None
        uf_via_cep     = None
        erro_viacep    = None
        try:
            resp = req_ext.get(
                f'https://viacep.com.br/ws/{cep_param}/json/',
                timeout=5,
            )
            dados_cep = resp.json()
            if not dados_cep.get('erro'):
                cidade_via_cep = dados_cep.get('localidade', '')
                uf_via_cep     = dados_cep.get('uf', '')
        except Exception as exc:
            erro_viacep = str(exc)

        # 3. Busca por cidade retornada pelo ViaCEP
        resultados_por_cidade = []
        if cidade_via_cep and uf_via_cep:
            qs_cidade = CidadeViabilidade.objects.filter(
                ativo=True,
                cidade__iexact=cidade_via_cep,
                estado=uf_via_cep,
            )
            # Exclui os que já apareceram na busca direta
            ids_diretos = {r.pk for r in resultados_diretos}
            resultados_por_cidade = [r for r in qs_cidade if r.pk not in ids_diretos]

        def serializar(obj, viavel_pela_cidade=False):
            return {
                'id':                  obj.pk,
                'cidade':              obj.cidade,
                'estado':              obj.estado,
                'cep':                 obj.cep,
                'bairro':              obj.bairro,
                'observacao':          obj.observacao,
                'viavel_pelo_cep':     bool(obj.cep),
                'viavel_pela_cidade':  viavel_pela_cidade,
            }

        registros = (
            [serializar(r, viavel_pela_cidade=False) for r in resultados_diretos]
            + [serializar(r, viavel_pela_cidade=True) for r in resultados_por_cidade]
        )

        tem_viabilidade = bool(registros)

        return JsonResponse({
            'sucesso':          True,
            'cep_consultado':   cep_formatado,
            'cidade_do_cep':    cidade_via_cep,
            'uf_do_cep':        uf_via_cep,
            'tem_viabilidade':  tem_viabilidade,
            'total':            len(registros),
            'registros':        registros,
            'aviso_viacep':     erro_viacep,
        })

    # ── Modo listagem / busca por cidade ─────────────────────────────────
    def serializar_lista(obj):
        return {
            'id':         obj.pk,
            'cidade':     obj.cidade,
            'estado':     obj.estado,
            'cep':        obj.cep,
            'bairro':     obj.bairro,
            'observacao': obj.observacao,
        }

    registros = [serializar_lista(r) for r in qs.order_by('estado', 'cidade', 'cep')]

    return JsonResponse({
        'sucesso':  True,
        'total':    len(registros),
        'registros': registros,
    })
