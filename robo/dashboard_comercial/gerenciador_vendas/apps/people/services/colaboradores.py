"""
O unico caminho de escrita em `Colaborador`.

Tres funcoes, e todas as Tools do modulo (Feedback, Recrutamento, Treinamento)
passam por elas:

  buscar_colaborador     o "pesquisar antes de criar"
  registrar_colaborador  cria, reaproveita ou readmite, com dedup embutido
  mover_situacao         a unica forma de mudar de fase

A regra que sustenta o modulo inteiro diz que qualquer fluxo que crie pessoa
precisa pesquisar antes, reutilizar quem ja existe, impedir duplicidade por
documento e nunca criar cadastro paralelo. Aqui ela e codigo, nao recomendacao:
a constraint no banco impede o CPF repetido, e este servico e o unico lugar que
sabe o que fazer quando o dedup encontra alguem.
"""
from dataclasses import dataclass, field
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.people import estados, telemetria
from apps.people.excecoes import CampoObrigatorioFaltando, TransicaoInvalida
from apps.people.models import Colaborador, HistoricoSituacao
from apps.people.services.configuracao import config_efetiva
from apps.people.utils import (
    chave_nome, cpf_tem_digito_valido, normalizar_cep, normalizar_cpf,
    normalizar_e164, normalizar_email, normalizar_estado, normalizar_nome,
)


# Campos pessoais que `registrar_colaborador` aceita em `dados`. Whitelist: o
# que nao esta aqui e ignorado em silencio, e de proposito, porque um dos
# chamadores e um formulario publico que qualquer um na internet pode postar.
CAMPOS_PESSOAIS = (
    'nome_completo', 'primeiro_nome', 'cpf', 'rg', 'pis',
    'data_nascimento', 'telefone', 'email',
    'cep', 'rua', 'numero', 'complemento', 'bairro', 'cidade', 'estado',
    'tipo_chave_pix', 'chave_pix',
    'cargo', 'regime_contratacao', 'data_admissao',
)

# Campos que o auto cadastro NAO pode tocar num registro que ja existe, nem
# quando estao vazios. Sao decisao do RH, nao do colaborador.
CAMPOS_SO_DO_RH = ('cargo', 'regime_contratacao', 'data_admissao')


@dataclass
class Candidato:
    """Alguem que o dedup encontrou, e quao confiante ele esta."""

    colaborador: Colaborador
    forca: str   # 'forte' (CPF) ou 'fraco' (telefone, nome mais nascimento)
    motivo: str  # 'cpf' | 'telefone' | 'nome_nascimento'


@dataclass
class ResultadoCadastro:
    """
    O que aconteceu no registro.

    Duplicata NAO levanta excecao: devolve `acao='conflito'` com os candidatos,
    porque quem decide se e a mesma pessoa e o chamador. O RH ve uma pergunta na
    tela; o formulario publico ve uma recusa generica. Sao respostas diferentes
    pro mesmo achado, e o servico nao deve escolher por eles.
    """

    colaborador: Colaborador = None
    acao: str = 'criado'  # criado | reaproveitado | reativado | conflito
    conflitos: list = field(default_factory=list)
    motivo_conflito: str = ''

    @property
    def ok(self):
        return self.acao != 'conflito'


def _limpar_dados(dados):
    """Normaliza e filtra pela whitelist. Chave desconhecida cai fora."""
    limpo = {}
    for campo in CAMPOS_PESSOAIS:
        if campo not in dados:
            continue
        valor = dados[campo]
        if campo == 'cpf':
            valor = normalizar_cpf(valor)
        elif campo == 'telefone':
            valor = normalizar_e164(valor)
        elif campo == 'email':
            valor = normalizar_email(valor)
        elif campo == 'estado':
            valor = normalizar_estado(valor)
        elif campo == 'cep':
            valor = normalizar_cep(valor)
        elif campo in ('nome_completo', 'primeiro_nome'):
            valor = normalizar_nome(valor)
        limpo[campo] = valor
    return limpo


def buscar_colaborador(tenant, *, cpf=None, telefone=None, email=None,
                       nome=None, data_nascimento=None, excluir_id=None):
    """
    O "pesquisar antes de criar" da regra de fonte unica.

    Devolve candidatos ordenados por forca do match, os fortes primeiro. Busca
    em TODAS as situacoes, inclusive desligado, porque encontrar quem saiu e
    justamente o que permite readmitir em vez de duplicar.

    E esta a funcao que Feedback e Recrutamento chamam antes de qualquer coisa.
    """
    base = Colaborador.all_tenants.filter(tenant=tenant)
    if excluir_id:
        base = base.exclude(pk=excluir_id)

    candidatos = []
    vistos = set()

    def adicionar(colaborador, forca, motivo):
        if colaborador.pk in vistos:
            return
        vistos.add(colaborador.pk)
        candidatos.append(Candidato(colaborador=colaborador, forca=forca, motivo=motivo))

    # Match forte: CPF. E o unico sem ambiguidade, e o unico que o servico
    # resolve sozinho.
    cpf_limpo = normalizar_cpf(cpf)
    if cpf_limpo:
        for achado in base.filter(cpf=cpf_limpo):
            adicionar(achado, 'forte', 'cpf')

    # Match fraco: nunca reaproveita sozinho, so levanta a mao.
    telefone_limpo = normalizar_e164(telefone)
    if telefone_limpo:
        for achado in base.filter(telefone=telefone_limpo):
            adicionar(achado, 'fraco', 'telefone')

    if nome and data_nascimento:
        alvo = chave_nome(nome)
        for achado in base.filter(data_nascimento=data_nascimento):
            if chave_nome(achado.nome_completo) == alvo:
                adicionar(achado, 'fraco', 'nome_nascimento')

    candidatos.sort(key=lambda c: 0 if c.forca == 'forte' else 1)
    return candidatos


@transaction.atomic
def registrar_colaborador(tenant, unidade, dados, *, origem,
                          situacao_inicial=estados.SITUACAO_CADASTRO,
                          usuario=None, request=None,
                          colaborador_id=None, permitir_reativacao=True):
    """
    Cria, reaproveita ou readmite. E o unico caminho de criacao do modulo.

    `colaborador_id` resolve um conflito anterior: o RH viu a pergunta "e essa
    pessoa?" e respondeu. `permitir_reativacao=False` forca conflito em vez de
    readmitir sozinho.
    """
    if situacao_inicial not in estados.SITUACOES_DE_ENTRADA:
        raise TransicaoInvalida(
            f'"{situacao_inicial}" nao e situacao de entrada. '
            f'Validas: {sorted(estados.SITUACOES_DE_ENTRADA)}.'
        )
    if unidade.tenant_id != tenant.id:
        raise ValueError('A unidade e de outro tenant.')

    limpo = _limpar_dados(dados)
    if not limpo.get('nome_completo'):
        raise ValueError('nome_completo e obrigatorio.')

    cpf = limpo.get('cpf')
    cpf_ok = cpf_tem_digito_valido(cpf) if cpf else False

    # O RH ja disse quem e. Nao pesquisa de novo.
    if colaborador_id:
        alvo = Colaborador.all_tenants.select_for_update().filter(
            tenant=tenant, pk=colaborador_id).first()
        if alvo is None:
            raise ValueError(f'Colaborador {colaborador_id} nao existe neste tenant.')
        return _reaproveitar(alvo, limpo, unidade, situacao_inicial, origem,
                             usuario, request, permitir_reativacao)

    candidatos = buscar_colaborador(
        tenant, cpf=cpf, telefone=limpo.get('telefone'),
        nome=limpo.get('nome_completo'), data_nascimento=limpo.get('data_nascimento'),
    )
    forte = next((c for c in candidatos if c.forca == 'forte'), None)

    if forte is not None:
        alvo = Colaborador.all_tenants.select_for_update().get(pk=forte.colaborador.pk)
        return _reaproveitar(alvo, limpo, unidade, situacao_inicial, origem,
                             usuario, request, permitir_reativacao)

    # Match fraco nunca vira reaproveitamento automatico. Telefone se repete
    # (familia, telefone da loja) e homonimo com mesma data de nascimento
    # existe. Quem decide e gente.
    if candidatos:
        telemetria.emitir_duplicata_bloqueada(
            tenant, motivo='possivel_duplicata', candidatos=candidatos,
            request=request, extras={'origem_cadastro': origem},
        )
        return ResultadoCadastro(
            colaborador=None, acao='conflito', conflitos=candidatos,
            motivo_conflito='possivel_duplicata',
        )

    return _criar(tenant, unidade, limpo, cpf_ok, situacao_inicial, origem,
                  usuario, request)


def _criar(tenant, unidade, limpo, cpf_ok, situacao_inicial, origem, usuario, request):
    """Cria de fato. Trata a corrida de duas submissoes simultaneas."""
    ponto_entrada = _ponto_entrada_de(situacao_inicial, origem)

    colaborador = Colaborador(
        tenant=tenant, unidade=unidade,
        situacao=situacao_inicial, ponto_entrada=ponto_entrada,
        origem_cadastro=origem, criado_por=usuario,
        cpf_valido=cpf_ok,
        pendente_revisao=(limpo.get('cpf') is None or not cpf_ok),
        **{k: v for k, v in limpo.items() if v is not None},
    )

    try:
        with transaction.atomic():
            colaborador.save()
    except IntegrityError:
        # Duas submissoes do mesmo link no mesmo instante. Um link de loja com
        # 20 admissoes no mesmo dia exercita isto. A constraint fez o trabalho,
        # so precisamos reencontrar quem venceu a corrida.
        existente = Colaborador.all_tenants.filter(
            tenant=tenant, cpf=limpo.get('cpf')).first()
        if existente is None:
            raise
        return _reaproveitar(existente, limpo, unidade, situacao_inicial, origem,
                             usuario, request, permitir_reativacao=True)

    _registrar_historico(
        colaborador, de='', para=situacao_inicial,
        motivo='Cadastro inicial', usuario=usuario,
        origem=_origem_transicao(origem),
        dados={'ponto_entrada': ponto_entrada, 'origem_cadastro': origem},
    )
    telemetria.emitir(
        telemetria.EVENTO_CRIADO, colaborador, request=request, usuario=usuario,
        extras={'pendente_revisao': colaborador.pendente_revisao,
                'cpf_valido': colaborador.cpf_valido},
    )
    return ResultadoCadastro(colaborador=colaborador, acao='criado')


def _reaproveitar(alvo, limpo, unidade, situacao_inicial, origem, usuario,
                  request, permitir_reativacao):
    """
    A pessoa ja existe. Decide entre readmitir, completar ou recusar.

    A regra de ouro do preenchimento: o auto cadastro PREENCHE LACUNA, nunca
    sobrescreve dado que o RH digitou. Quem esta com o celular na mao na porta
    da loja nao tem autoridade sobre o cadastro que o RH ja conferiu.
    """
    e_publico = origem == 'link_publico'

    if alvo.situacao == estados.SITUACAO_DESLIGADO:
        for motivo_recusa, condicao in (
            ('nao_elegivel_recontratacao', not alvo.elegivel_recontratacao),
            ('reativacao_nao_permitida', not permitir_reativacao),
        ):
            if condicao:
                candidatos = [Candidato(alvo, 'forte', 'cpf')]
                telemetria.emitir_duplicata_bloqueada(
                    alvo.tenant, motivo=motivo_recusa, candidatos=candidatos,
                    request=request, extras={'origem_cadastro': origem},
                )
                return ResultadoCadastro(
                    colaborador=None, acao='conflito', conflitos=candidatos,
                    motivo_conflito=motivo_recusa,
                )

        _completar_lacunas(alvo, limpo, e_publico)
        unidade_anterior = alvo.unidade_id
        alvo.unidade = unidade
        alvo.save()
        # A transicao nao emite sozinha: readmissao e UM acontecimento, e dois
        # eventos pro mesmo ato poluiriam tanto o log quanto o editor de fluxos.
        atualizado = mover_situacao(
            alvo, situacao_inicial, motivo='Readmissao',
            usuario=usuario, request=request, origem=_origem_transicao(origem),
            emitir_telemetria=False,
        )
        telemetria.emitir(
            telemetria.EVENTO_READMITIDO, atualizado, request=request, usuario=usuario,
            extras={'situacao_de': estados.SITUACAO_DESLIGADO,
                    'situacao_para': situacao_inicial,
                    'mudou_de_unidade': unidade_anterior != unidade.pk},
        )
        return ResultadoCadastro(colaborador=atualizado, acao='reativado')

    # Pessoa ativa: completa o que falta e nao mexe em fase nem em unidade.
    # Mudanca de loja e transferencia, tem decisao de gestor por tras, e nao
    # pode acontecer como efeito colateral de alguem reenviar um formulario.
    _completar_lacunas(alvo, limpo, e_publico)
    alvo.save()
    telemetria.emitir(
        telemetria.EVENTO_REAPROVEITADO, alvo, request=request, usuario=usuario,
        extras={'origem_cadastro': origem},
    )
    return ResultadoCadastro(colaborador=alvo, acao='reaproveitado')


def _completar_lacunas(alvo, limpo, e_publico):
    """Preenche so o que esta vazio. Nunca sobrescreve."""
    for campo, valor in limpo.items():
        if valor in (None, ''):
            continue
        if e_publico and campo in CAMPOS_SO_DO_RH:
            continue
        if not getattr(alvo, campo, None):
            setattr(alvo, campo, valor)

    if limpo.get('cpf') and not alvo.cpf_valido:
        alvo.cpf_valido = cpf_tem_digito_valido(limpo['cpf'])


def _ponto_entrada_de(situacao_inicial, origem):
    if origem == 'link_publico':
        return estados.ENTRADA_LINK_PUBLICO
    for chave, destino in estados.PONTOS_ENTRADA.items():
        if destino == situacao_inicial and chave != estados.ENTRADA_LINK_PUBLICO:
            return chave
    return estados.ENTRADA_SO_CADASTRO


def _origem_transicao(origem_cadastro):
    """Origem do cadastro e origem da transicao usam vocabularios proximos mas
    nao iguais. Traduz em vez de deixar o caller adivinhar."""
    return {
        'rh': 'painel',
        'link_publico': 'link_publico',
        'importacao': 'importacao',
        'api': 'automacao',
    }.get(origem_cadastro, 'painel')


@transaction.atomic
def mover_situacao(colaborador, para, *, motivo='', usuario=None, request=None,
                   origem='painel', dados=None, emitir_telemetria=True):
    """
    A unica forma de mudar de fase.

    Valida a transicao, exige os campos que a fase pede, calcula os derivados,
    limpa o que ficou obsoleto, grava historico e devolve o colaborador.

    Trava a linha com select_for_update porque dois gestores arrastando o mesmo
    card no kanban e cenario real, nao hipotese.

    `emitir_telemetria=False` serve pra quando a transicao e parte de um
    acontecimento maior que ja tem evento proprio (readmissao). O historico e
    gravado de qualquer jeito: ele e a fonte primaria e nao se desliga.
    """
    dados = dados or {}

    travado = Colaborador.all_tenants.select_for_update().get(pk=colaborador.pk)
    de = travado.situacao

    estados.validar_transicao(de, para)

    # Whitelist: `dados` nao e um save() disfarcado.
    aceitos = estados.campos_aceitos(para)
    aplicados = {}
    for campo, valor in dados.items():
        if campo in aceitos and valor is not None:
            setattr(travado, campo, valor)
            aplicados[campo] = _serializavel(valor)

    faltando = [
        campo for campo in estados.campos_exigidos(de, para)
        if not getattr(travado, campo, None)
    ]
    if faltando:
        raise CampoObrigatorioFaltando(faltando, de, para)

    prorrogacao = estados.eh_prorrogacao(de, para)
    calculados = _aplicar_calculos(travado, de, para, dados, prorrogacao)

    limpos = {}
    for campo in estados.campos_a_limpar(de, para):
        anterior = getattr(travado, campo, None)
        if anterior not in (None, ''):
            limpos[campo] = _serializavel(anterior)
        setattr(travado, campo, None if 'data' in campo else '')

    travado.situacao = para
    travado._transicao_autorizada = True
    travado.save()

    snapshot = {}
    if aplicados:
        snapshot['aplicados'] = aplicados
    if calculados:
        snapshot['calculados'] = calculados
    if limpos:
        snapshot['limpos'] = limpos
    if prorrogacao:
        snapshot['prorrogacao'] = travado.prorrogacoes_experiencia

    _registrar_historico(travado, de=de, para=para, motivo=motivo,
                         usuario=usuario, origem=origem, dados=snapshot)

    # Sincroniza o objeto que o caller tem em maos com o que foi gravado.
    #
    # A transicao trabalha numa instancia travada por select_for_update, entao a
    # instancia do caller fica velha: ela nao enxerga o que a transicao calculou
    # nem o que limpou. Copiar tudo de volta evita a classe inteira de bug em
    # que alguem le `colaborador.data_desligamento` depois de readmitir e recebe
    # o valor antigo. Cai nessa armadilha quem escreveu isto aqui, na primeira
    # versao, e o teste de readmissao pegou.
    for campo in travado._meta.concrete_fields:
        setattr(colaborador, campo.attname, getattr(travado, campo.attname))
    colaborador._situacao_carregada = travado.situacao

    if emitir_telemetria:
        telemetria.emitir(
            telemetria.evento_da_transicao(de, para), travado,
            mensagem=motivo or None, request=request, usuario=usuario,
            extras={'situacao_de': de, 'situacao_para': para,
                    'origem_transicao': origem, **snapshot},
        )

    return travado


def _aplicar_calculos(colaborador, de, para, dados, prorrogacao):
    """
    Deriva o que a fase calcula. Hoje so a data de fim da experiencia.

    Entrada na experiencia marca o fim do PRIMEIRO periodo (o 45 de um 45 mais
    45), nao o total: e nesse marco que o gestor decide prorrogar, efetivar ou
    dispensar. Prorrogar empurra pro total. Data explicita em `dados` sempre
    vence o calculo, porque a operacao real tem excecao.
    """
    calculados = {}
    if 'data_fim_experiencia' not in estados.campos_calculados(para):
        return calculados

    if dados.get('data_fim_experiencia'):
        return calculados  # ja foi aplicado pela whitelist

    config = config_efetiva(colaborador.unidade)
    if prorrogacao:
        dias = config.dias_experiencia_padrao
        colaborador.prorrogacoes_experiencia = (colaborador.prorrogacoes_experiencia or 0) + 1
    else:
        dias = config.dias_primeiro_periodo_experiencia
        colaborador.prorrogacoes_experiencia = 0

    if colaborador.data_admissao:
        nova = colaborador.data_admissao + timedelta(days=dias)
        colaborador.data_fim_experiencia = nova
        calculados['data_fim_experiencia'] = nova.isoformat()
        calculados['dias'] = dias

    return calculados


def _registrar_historico(colaborador, *, de, para, motivo, usuario, origem, dados):
    return HistoricoSituacao.all_tenants.create(
        tenant=colaborador.tenant, colaborador=colaborador,
        de=de, para=para, motivo=motivo or '',
        dados=dados or {}, usuario=usuario, origem=origem,
    )


def _serializavel(valor):
    """JSONField nao aceita date nem datetime crus."""
    if hasattr(valor, 'isoformat'):
        return valor.isoformat()
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    return str(valor)


def marcar_revisado(colaborador, *, usuario=None):
    """Tira o colaborador da fila de revisao do RH."""
    colaborador.pendente_revisao = False
    colaborador.save(update_fields=['pendente_revisao', 'atualizado_em'])
    return colaborador


def data_hoje():
    """Data local do servidor. Isolada pra facilitar teste."""
    return timezone.localdate()
