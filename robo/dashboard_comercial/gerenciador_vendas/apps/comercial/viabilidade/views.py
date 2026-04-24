# ============================================================================
# Views migradas de vendas_web.views (Phase 3B)
# ============================================================================
import json
import unicodedata
import logging

import requests as req_ext
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

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


# ============================================================================
# Gestao server-side (pagina interna do Hubtrix)
# ============================================================================

@login_required
def cidades_lista(request):
    """Pagina de gestao das cidades/CEPs com viabilidade do tenant."""
    q = (request.GET.get('q') or '').strip()
    uf = (request.GET.get('uf') or '').strip().upper()
    status = (request.GET.get('status') or '').strip()

    qs = CidadeViabilidade.objects.all()
    if q:
        qs = qs.filter(cidade__icontains=q) | qs.filter(cep__icontains=q) | qs.filter(bairro__icontains=q)
    if uf:
        qs = qs.filter(estado=uf)
    if status == 'ativo':
        qs = qs.filter(ativo=True)
    elif status == 'inativo':
        qs = qs.filter(ativo=False)

    qs = qs.order_by('estado', 'cidade', 'cep')

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'cidades': page_obj.object_list,
        'page_obj': page_obj,
        'total': qs.count(),
        'estados': CidadeViabilidade.ESTADO_CHOICES,
        'filtro_q': q,
        'filtro_uf': uf,
        'filtro_status': status,
        'modulo_atual': 'comercial',
    }
    return render(request, 'viabilidade/cidades.html', context)


@login_required
@require_http_methods(["POST"])
def cidade_salvar(request):
    """Cria ou atualiza uma CidadeViabilidade do tenant atual."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    cidade = (data.get('cidade') or '').strip()
    estado = (data.get('estado') or '').strip().upper()
    if not cidade or not estado:
        return JsonResponse({'error': 'Cidade e estado sao obrigatorios.'}, status=400)

    ufs_validas = {c for c, _ in CidadeViabilidade.ESTADO_CHOICES}
    if estado not in ufs_validas:
        return JsonResponse({'error': f'UF invalida: {estado}'}, status=400)

    pk = data.get('id')
    campos = {
        'cidade': cidade,
        'estado': estado,
        'cep': (data.get('cep') or '').strip() or None,
        'bairro': (data.get('bairro') or '').strip() or None,
        'observacao': (data.get('observacao') or '').strip() or None,
        'ativo': bool(data.get('ativo', True)),
    }

    if pk:
        obj = get_object_or_404(CidadeViabilidade, pk=pk)
        for k, v in campos.items():
            setattr(obj, k, v)
        try:
            obj.full_clean()
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
        obj.save()
        msg = 'Cidade atualizada.'
    else:
        campos['tenant'] = request.tenant
        obj = CidadeViabilidade(**campos)
        try:
            obj.full_clean()
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
        obj.save()
        msg = 'Cidade cadastrada.'

    return JsonResponse({
        'success': True,
        'message': msg,
        'cidade': {
            'id': obj.pk,
            'cidade': obj.cidade,
            'estado': obj.estado,
            'cep': obj.cep,
            'bairro': obj.bairro,
            'observacao': obj.observacao,
            'ativo': obj.ativo,
        },
    })


@login_required
@require_http_methods(["POST"])
def cidade_toggle(request, pk):
    """Alterna o flag ativo da cidade."""
    obj = get_object_or_404(CidadeViabilidade, pk=pk)
    obj.ativo = not obj.ativo
    obj.save(update_fields=['ativo', 'data_atualizacao'])
    return JsonResponse({'success': True, 'ativo': obj.ativo})


@login_required
@require_http_methods(["DELETE"])
def cidade_excluir(request, pk):
    """Remove uma cidade do tenant."""
    obj = get_object_or_404(CidadeViabilidade, pk=pk)
    obj.delete()
    return JsonResponse({'success': True, 'message': 'Cidade removida.'})
