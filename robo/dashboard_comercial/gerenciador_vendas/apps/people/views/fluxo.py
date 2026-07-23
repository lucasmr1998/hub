"""
Configuracao do fluxo do processo seletivo.

A tela que faltava pro desenho fazer sentido: `EtapaPipeline` sempre foi dado
("etapa e configuracao, saida e codigo"), mas sem tela o cliente ficava preso
nas sete etapas que o seed criou, o que e o mesmo que ter etapa em codigo.

Escopo por unidade, no padrao `config_efetiva` do DP: sem unidade escolhida
edita o fluxo do tenant; com unidade, o fluxo daquela loja. Criar a primeira
etapa de uma unidade faz ela parar de herdar o do tenant, e a tela avisa isso
ANTES, porque e o tipo de efeito que surpreende.
"""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.people import estados_recrutamento as estados_rs
from apps.people.models import (
    Candidato, EtapaPipeline, MensagemRecrutamento, Unidade,
)
from apps.people.permissoes import pode_acessar, requer_people
from apps.sistema.utils import registrar_acao


def _unidade_do_request(request):
    """Unidade em edicao, ou None pro fluxo do tenant."""
    unidade_id = (request.GET.get('unidade') or request.POST.get('unidade') or '').strip()
    if unidade_id.isdigit():
        return Unidade.objects.filter(pk=int(unidade_id)).first()
    return None


def _voltar(unidade, tab='etapas'):
    """
    Volta pro hub de configuracoes, na aba certa.

    O `tab` importa porque as tabs sao client-side: sem ele, salvar uma mensagem
    devolveria o usuario pra aba Etapas, e ele leria isso como "cadê o que eu
    salvei". A unidade viaja junto pra nao perder o escopo do fluxo no caminho.
    """
    destino = f'/people/fluxo/?tab={tab}'
    if unidade:
        destino += f'&unidade={unidade.pk}'
    return redirect(destino)


@requer_people()
def contexto_fluxo(request, unidade):
    """
    Contexto das abas Etapas e Mensagens, namespaceado.

    Vive separado da view porque o hub de Configuracoes reune quatro abas numa
    tela so, e as chaves genericas (`linhas`) colidiriam entre elas. Prefixo
    `etapas_` deixa cada aba dona das suas chaves.
    """
    # Todas, inclusive inativas: a tela e onde se reativa.
    etapas = list(EtapaPipeline.do_escopo(request.tenant, unidade,
                                          somente_ativas=False)
                  .order_by('ordem', 'id'))

    # Quantos candidatos em cada etapa, pra tela avisar antes de desativar.
    ocupacao = dict(
        Candidato.objects.filter(saida='', anonimizado_em__isnull=True)
        .values_list('etapa').annotate(n=Count('id')))

    # Mensagem sugerida de cada etapa e de cada saida. Uma consulta so, e nao
    # uma por linha: a tela lista sete etapas mais quatro saidas.
    mensagens = list(MensagemRecrutamento.objects.all())
    por_etapa = {m.etapa_id: m for m in mensagens if m.etapa_id}
    por_saida = {m.saida: m for m in mensagens if m.saida}

    # `dados_edicao` sai pro template via json_script, e nao num atributo
    # data-*: roteiro e checklist tem QUEBRA DE LINHA, e newline dentro de
    # atributo HTML gera markup e JSON invalidos. O json_script escapa certo.
    linhas = [{
        'etapa': e,
        'candidatos': ocupacao.get(e.pk, 0),
        'mensagem': por_etapa.get(e.pk),
        'id_json': f'etapa-dados-{e.pk}',
        'dados_edicao': {
            'pk': str(e.pk),
            'nome': e.nome,
            'cor': e.cor,
            'sla': str(e.sla_dias or ''),
            'blocos': list(e.blocos or []),
            'roteiro': chr(10).join(e.roteiro or []),
            'checklist': chr(10).join(e.checklist or []),
        },
    } for e in etapas]

    # A unidade esta herdando o fluxo do tenant, ou ja tem o proprio?
    herda = bool(unidade) and not EtapaPipeline.all_tenants.filter(
        tenant=request.tenant, unidade=unidade).exists()

    return {
        'etapas_linhas': linhas,
        'unidade': unidade,
        'herda_do_tenant': herda,
        'unidades_opcoes': list(
            Unidade.objects.filter(ativo=True).values_list('pk', 'nome')),
        'cores': estados_rs.CORES_ETAPA,
        'blocos_disponiveis': estados_rs.BLOCOS,
        'saidas': [
            {'valor': v, 'rotulo': r, 'cor': estados_rs.COR_DA_SAIDA.get(v, ''),
             'mensagem': por_saida.get(v)}
            for v, r in estados_rs.SAIDAS
        ],
    }


# Abas validas do hub, e a ordem em que aparecem. Lista, e nao set, porque a
# ordem importa e um `tab=` invalido cai na primeira.
ABAS = ['etapas', 'mensagens', 'campos', 'captacao']


def configurar(request):
    """
    Hub de Configuracoes do recrutamento: Etapas, Mensagens, Campos, Captacao.

    Antes eram tres telas soltas no menu (Fluxo, Campos, Captacao continua).
    Aqui viram abas de uma pagina so, client-side: trocar de aba nao recarrega,
    porque recarregar numa troca de aba incomoda tanto quanto no filtro do board.
    """
    from apps.people.views import campos, vagas

    unidade = _unidade_do_request(request)
    aba = request.GET.get('tab')
    if aba not in ABAS:
        aba = 'etapas'

    contexto = {
        'pagetitle': 'Configurações do recrutamento',
        'aba_ativa': aba,
        'pode_gerir': pode_acessar(request, 'people.gerir_vagas'),
    }
    contexto.update(contexto_fluxo(request, unidade))
    contexto.update(campos.contexto_campos(request))
    contexto.update(vagas.contexto_captacao(request))
    return render(request, 'people/config_recrutamento.html', contexto)


@require_POST
@requer_people('people.gerir_vagas')
def etapa_salvar(request):
    """Cria ou edita uma etapa. Um handler so, porque o formulario e o mesmo."""
    unidade = _unidade_do_request(request)
    pk = (request.POST.get('pk') or '').strip()
    nome = ' '.join((request.POST.get('nome') or '').split())
    cor = (request.POST.get('cor') or '').strip()
    sla = (request.POST.get('sla_dias') or '').strip()

    if not nome:
        messages.error(request, 'A etapa precisa de um nome.')
        return _voltar(unidade)

    # A unique do banco ja barraria, com IntegrityError na cara do usuario.
    duplicada = EtapaPipeline.all_tenants.filter(
        tenant=request.tenant, unidade=unidade, nome__iexact=nome)
    if pk.isdigit():
        duplicada = duplicada.exclude(pk=int(pk))
    if duplicada.exists():
        messages.error(request, f'Já existe uma etapa chamada "{nome}" neste fluxo.')
        return _voltar(unidade)

    # So aceita bloco que o codigo conhece: POST forjado nao inventa bloco, e
    # bloco removido do codigo nao fica gravado esperando quebrar a tela.
    blocos = [b for b in request.POST.getlist('blocos')
              if b in estados_rs.VALORES_BLOCOS]

    def _linhas(campo):
        """Uma por linha, sem vazias e sem repetida."""
        vistas = []
        for linha in (request.POST.get(campo) or '').splitlines():
            texto = ' '.join(linha.split())
            if texto and texto not in vistas:
                vistas.append(texto)
        return vistas

    dados = {
        'nome': nome,
        'cor': cor if cor in estados_rs.HEX_POR_COR else '',
        'sla_dias': int(sla) if sla.isdigit() else None,
        'blocos': blocos,
        'roteiro': _linhas('roteiro'),
        'checklist': _linhas('checklist'),
    }

    if pk.isdigit():
        etapa = get_object_or_404(EtapaPipeline.objects, pk=int(pk))
        for campo, valor in dados.items():
            setattr(etapa, campo, valor)
        etapa.save()
        acao = 'editada'
    else:
        ultima = (EtapaPipeline.all_tenants
                  .filter(tenant=request.tenant, unidade=unidade)
                  .order_by('-ordem').first())
        if not dados['blocos']:
            # Etapa sem bloco teria aba vazia. O minimo util serve pra qualquer
            # coisa e nao inventa comportamento que ninguem pediu.
            dados['blocos'] = [estados_rs.BLOCO_ANOTACAO,
                               estados_rs.BLOCO_MENSAGEM]
        etapa = EtapaPipeline.all_tenants.create(
            tenant=request.tenant, unidade=unidade,
            ordem=(ultima.ordem + 1) if ultima else 1, ativa=True, **dados)
        acao = 'criada'

    registrar_acao('people', 'editar', 'etapa_pipeline', etapa.pk,
                   f'Etapa "{etapa.nome}" {acao}.', request=request)
    messages.success(request, f'Etapa "{etapa.nome}" {acao}.')
    return _voltar(unidade)


@require_POST
@requer_people('people.gerir_vagas')
def etapa_alternar(request, pk):
    """
    Liga e desliga a etapa.

    Nao apaga, e nao esconde quem esta nela: candidato em etapa desativada
    aparece no board num agrupamento "Fora de etapa", pra ser realocado. A tela
    avisa quantos serao afetados antes.
    """
    unidade = _unidade_do_request(request)
    etapa = get_object_or_404(EtapaPipeline.objects, pk=pk)

    etapa.ativa = not etapa.ativa
    etapa.save(update_fields=['ativa', 'atualizado_em'])

    estado = 'ativada' if etapa.ativa else 'desativada'
    registrar_acao('people', 'editar', 'etapa_pipeline', etapa.pk,
                   f'Etapa "{etapa.nome}" {estado}.', request=request)
    messages.success(request, f'Etapa "{etapa.nome}" {estado}.')
    return _voltar(unidade)


@require_POST
@requer_people('people.gerir_vagas')
def etapa_mover(request, pk):
    """
    Sobe ou desce a etapa na ordem.

    Troca a ordem com a vizinha em vez de reescrever a lista inteira: menos
    escrita e sem risco de deixar buraco na sequencia.
    """
    unidade = _unidade_do_request(request)
    etapa = get_object_or_404(EtapaPipeline.objects, pk=pk)
    direcao = request.POST.get('direcao')

    irmas = list(EtapaPipeline.all_tenants
                 .filter(tenant=request.tenant, unidade=unidade)
                 .order_by('ordem', 'id'))
    posicao = next((i for i, e in enumerate(irmas) if e.pk == etapa.pk), None)
    if posicao is None:
        return _voltar(unidade)

    alvo = posicao - 1 if direcao == 'cima' else posicao + 1
    if not (0 <= alvo < len(irmas)):
        return _voltar(unidade)   # ja e a primeira ou a ultima

    vizinha = irmas[alvo]
    with transaction.atomic():
        etapa.ordem, vizinha.ordem = vizinha.ordem, etapa.ordem
        etapa.save(update_fields=['ordem'])
        vizinha.save(update_fields=['ordem'])

    return _voltar(unidade)


@require_POST
@requer_people('people.gerir_vagas')
def etapa_remover(request, pk):
    """
    Apaga a etapa, e SO se estiver vazia.

    Etapa com candidato nao se apaga: o historico guarda o nome da etapa como
    texto e sobreviveria, mas o candidato ficaria orfao no board. Pra tirar de
    circulacao com gente dentro, o caminho e desativar.
    """
    unidade = _unidade_do_request(request)
    etapa = get_object_or_404(EtapaPipeline.objects, pk=pk)

    dentro = Candidato.objects.filter(etapa=etapa, saida='').count()
    if dentro:
        messages.error(
            request,
            f'"{etapa.nome}" tem {dentro} candidato{"s" if dentro > 1 else ""} '
            f'dentro. Mova essas pessoas antes, ou apenas desative a etapa.')
        return _voltar(unidade)

    nome = etapa.nome
    etapa.delete()
    registrar_acao('people', 'excluir', 'etapa_pipeline', pk,
                   f'Etapa "{nome}" removida.', request=request)
    messages.success(request, f'Etapa "{nome}" removida.')
    return _voltar(unidade)


@require_POST
@requer_people('people.gerir_vagas')
def resetar_padrao(request):
    """
    Volta o fluxo do escopo pras sete etapas padrao.

    So funciona com o fluxo vazio de candidatos: resetar com gente no meio do
    processo deixaria todo mundo fora de etapa de uma vez.
    """
    unidade = _unidade_do_request(request)

    etapas = EtapaPipeline.all_tenants.filter(tenant=request.tenant, unidade=unidade)
    ocupadas = Candidato.objects.filter(
        etapa__in=etapas, saida='').count()
    if ocupadas:
        messages.error(
            request,
            f'Há {ocupadas} candidato(s) no fluxo. Resetar deixaria todos fora '
            f'de etapa. Conclua ou mova essas pessoas antes.')
        return _voltar(unidade)

    with transaction.atomic():
        etapas.delete()
        EtapaPipeline.semear_padrao(request.tenant, unidade)

    registrar_acao('people', 'editar', 'etapa_pipeline', 0,
                   'Fluxo resetado pro padrao.', request=request)
    messages.success(request, 'Fluxo restaurado para o padrão.')
    return _voltar(unidade)


@require_POST
@requer_people('people.gerir_vagas')
def mensagem_salvar(request):
    """
    Grava a mensagem sugerida de uma etapa ou de uma saida.

    Texto vazio APAGA a mensagem, em vez de guardar uma linha em branco. Uma
    mensagem vazia configurada e indistinguivel de nao ter mensagem, e deixar as
    duas formas conviverem faria a ficha ter que checar as duas.
    """
    unidade = _unidade_do_request(request)
    etapa_pk = (request.POST.get('etapa') or '').strip()
    saida = (request.POST.get('saida') or '').strip()
    texto = (request.POST.get('texto') or '').strip()

    # Exatamente um dos dois, igual a constraint do banco. Checar aqui evita
    # devolver IntegrityError na cara do usuario.
    if bool(etapa_pk) == bool(saida):
        messages.error(request, 'Escolha uma etapa ou uma saída.')
        return _voltar(unidade, 'mensagens')

    if saida and saida not in estados_rs.ROTULOS_SAIDA:
        messages.error(request, 'Saída inválida.')
        return _voltar(unidade, 'mensagens')

    filtro = {'etapa_id': int(etapa_pk)} if etapa_pk else {'saida': saida}
    if etapa_pk:
        # get_object_or_404 pelo manager filtrado: etapa de outro tenant nao
        # pode receber mensagem deste.
        get_object_or_404(EtapaPipeline.objects, pk=int(etapa_pk))

    existente = MensagemRecrutamento.objects.filter(**filtro).first()

    if not texto:
        if existente:
            existente.delete()
            messages.success(request, 'Mensagem removida.')
        return _voltar(unidade, 'mensagens')

    if existente:
        existente.texto = texto
        existente.save(update_fields=['texto', 'atualizado_em'])
    else:
        MensagemRecrutamento.all_tenants.create(
            tenant=request.tenant, texto=texto,
            etapa_id=int(etapa_pk) if etapa_pk else None,
            saida=saida)

    registrar_acao('people', 'editar', 'mensagem_recrutamento', 0,
                   'Mensagem do fluxo de recrutamento ajustada.', request=request)
    messages.success(request, 'Mensagem salva.')
    return _voltar(unidade, 'mensagens')
