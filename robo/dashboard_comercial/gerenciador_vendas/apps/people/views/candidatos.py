"""
Ficha do candidato.

Duas abas, Perfil e Historico, no mesmo padrao da ficha do colaborador do DP
(pagina propria com tabs, e nao modal): quem chega pelo board clica no nome e
navega, e o botao Voltar traz de volta.

A ficha so mostra o que o candidato realmente informou. Campo em branco aparece
como travessao em vez de sumir, pra o RH saber que foi perguntado e nao
respondido, que e diferente de nao ter sido perguntado.
"""
import mimetypes

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from apps.people import estados_recrutamento as estados_rs
from apps.people.models import CampoCandidatura, Candidato
from apps.people.permissoes import pode_acessar, requer_people


def _respostas_custom(candidato):
    """
    As respostas dos campos do tenant, com o rotulo de cada uma.

    Resolve pelo `CampoCandidatura` pra mostrar o rotulo, e nao a chave crua do
    JSON. Resposta cujo campo foi apagado NAO aparece: sem o campo nao ha rotulo,
    e exibir "cnh_2: sim" e pior que omitir. Ela continua no banco, e a tela de
    campos e que impede apagar campo ja respondido.
    """
    dados = candidato.dados_custom or {}
    if not dados:
        return []

    campos = CampoCandidatura.all_tenants.filter(
        tenant_id=candidato.tenant_id, slug__in=list(dados)).order_by(
            'ordem', 'nome')
    return [{'rotulo': campo.nome, 'valor': dados.get(campo.slug)}
            for campo in campos]


@requer_people()
def detalhe(request, pk):
    candidato = get_object_or_404(
        Candidato.objects.select_related(
            'vaga', 'vaga__cargo', 'unidade', 'etapa', 'link_origem',
            'colaborador'),
        pk=pk)

    historico = (candidato.historico
                 .select_related('usuario')
                 .order_by('-criado_em'))

    tabs = [
        {'id': 'tab-perfil', 'label': 'Perfil', 'icon': 'bi-person',
         'active': True},
        {'id': 'tab-historico', 'label': 'Histórico', 'icon': 'bi-clock-history',
         'badge': str(historico.count()) if historico.exists() else ''},
    ]

    return render(request, 'people/candidato_detalhe.html', {
        'pagetitle': candidato.nome_completo,
        'candidato': candidato,
        'respostas_custom': _respostas_custom(candidato),
        # Sugestao pra etapa (ou saida) em que o candidato esta AGORA. Vazia
        # quando ninguem configurou mensagem pra esta fase, e ai o bloco some.
        'mensagem_sugerida': candidato.mensagem_sugerida(),
        'tem_whatsapp': bool(candidato.link_whatsapp()),
        'historico': historico,
        'tabs': tabs,
        'saidas': [{'valor': v, 'rotulo': r} for v, r in estados_rs.SAIDAS],
        'pode_mover': pode_acessar(request, 'people.gerir_vagas'),
    })


@requer_people()
def curriculo(request, pk):
    """
    Serve o curriculo do candidato.

    O arquivo vive em storage privado (PrivateCurriculoStorage), fora de
    MEDIA_ROOT, justamente porque a rota `/media/` serve qualquer arquivo sem
    autenticacao. Aqui passa pelo login, pela permissao do modulo e pelo escopo
    de tenant do `Candidato.objects`, entao um pk de outro tenant da 404 em vez
    de entregar o PDF.

    `?download=1` forca o Content-Disposition como attachment. Sem ele, abre no
    navegador: PDF e imagem sao os formatos que o RH quer so olhar.

    Mesmo desenho do `api_midia` do Inbox, que resolveu isto antes pra RG e
    comprovante.
    """
    candidato = get_object_or_404(Candidato.objects, pk=pk)

    if not candidato.curriculo:
        raise Http404('Candidato sem currículo')
    if candidato.anonimizado_em:
        # Expurgo LGPD ja apagou o arquivo; a linha sobrevive so como numero.
        raise Http404('Currículo removido por retenção')

    tipo = mimetypes.guess_type(candidato.curriculo.name)[0] or 'application/octet-stream'
    resposta = FileResponse(candidato.curriculo.open('rb'), content_type=tipo)

    extensao = candidato.curriculo.name.rsplit('.', 1)[-1]
    nome = f'curriculo-{candidato.nome_completo}.{extensao}'.replace(' ', '-')
    disposicao = 'attachment' if request.GET.get('download') else 'inline'
    resposta['Content-Disposition'] = f'{disposicao}; filename="{nome}"'
    return resposta
