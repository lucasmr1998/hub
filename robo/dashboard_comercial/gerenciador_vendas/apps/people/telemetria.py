"""
Telemetria do modulo People. Ponto unico de emissao.

A spec de origem nao tinha NENHUM evento instrumentado: os contratos de
conclusao diziam literalmente "event name TBD, confirm during instrumentation".
A lacuna nasce fechada aqui, e a regra e simples: toda transicao de fase emite,
com nome estavel, e ninguem emite de outro lugar.

Tres canais, em ordem de confiabilidade:

1. `HistoricoSituacao` (gravado pelo servico) e a FONTE PRIMARIA. Queryavel,
   com timestamp e snapshot. "Tempo medio de cadastro ate efetivado" sai dali
   com um group by, sem ferramenta externa e sem depender de nada estar ligado.
2. `LogSistema` via registrar_acao, que aparece em /aurora-admin/logs/.
3. A engine de automacao via disparar_evento, pro cliente montar fluxo.

Os dois ultimos sao derivados. Se ambos falharem, o funil continua reconstituivel
a partir do primeiro. E de proposito.
"""
import logging

from apps.people import estados

logger = logging.getLogger(__name__)


# ── Nomes de evento ──────────────────────────────────────────────────────────
#
# Namespace com ponto. As chaves antigas do catalogo da automacao nao tem
# namespace (`lead_criado`), mas People e modulo comercializavel e vai acumular
# dezenas de eventos: sem prefixo eles se misturariam com os do comercial no
# editor de fluxos. Renomear depois que um cliente configurou fluxo e migracao
# de dados, entao a escolha e agora.

EVENTO_CRIADO = 'people.colaborador.criado'
EVENTO_REAPROVEITADO = 'people.colaborador.reaproveitado'
EVENTO_READMITIDO = 'people.colaborador.readmitido'
EVENTO_DUPLICATA_BLOQUEADA = 'people.colaborador.duplicata_bloqueada'
EVENTO_ADMISSAO_INICIADA = 'people.colaborador.admissao_iniciada'
EVENTO_EXPERIENCIA_INICIADA = 'people.colaborador.experiencia_iniciada'
EVENTO_EXPERIENCIA_PRORROGADA = 'people.colaborador.experiencia_prorrogada'
EVENTO_EFETIVADO = 'people.colaborador.efetivado'
EVENTO_DESLIGAMENTO_INICIADO = 'people.colaborador.desligamento_iniciado'
EVENTO_DESLIGADO = 'people.colaborador.desligado'
EVENTO_VIROU_FREELANCER = 'people.colaborador.virou_freelancer'
EVENTO_VOLTOU_PRA_CADASTRO = 'people.colaborador.voltou_pra_cadastro'

# Qual evento cada destino da maquina de estados emite.
EVENTO_POR_SITUACAO = {
    estados.SITUACAO_CADASTRO:        EVENTO_VOLTOU_PRA_CADASTRO,
    estados.SITUACAO_EM_ADMISSAO:     EVENTO_ADMISSAO_INICIADA,
    estados.SITUACAO_EM_EXPERIENCIA:  EVENTO_EXPERIENCIA_INICIADA,
    estados.SITUACAO_EFETIVADO:       EVENTO_EFETIVADO,
    estados.SITUACAO_EM_DESLIGAMENTO: EVENTO_DESLIGAMENTO_INICIADO,
    estados.SITUACAO_DESLIGADO:       EVENTO_DESLIGADO,
    estados.SITUACAO_FREELANCER:      EVENTO_VIROU_FREELANCER,
}

# Eventos que merecem WARNING no log em vez de INFO.
NIVEL_POR_EVENTO = {
    EVENTO_DUPLICATA_BLOQUEADA: 'WARNING',
}


def evento_da_transicao(de, para):
    """
    Nome do evento que a transicao emite.

    Prorrogacao tem evento proprio porque a situacao nao muda: sem isso, o unico
    registro de que a experiencia foi esticada seria o contador, e ninguem
    conseguiria montar alerta em cima.
    """
    if estados.eh_prorrogacao(de, para):
        return EVENTO_EXPERIENCIA_PRORROGADA
    return EVENTO_POR_SITUACAO.get(para)


def contexto_do_colaborador(colaborador, **extras):
    """
    Contexto do evento, so com escalar.

    A fila da engine aceita instancia de model apenas pras entidades que ela
    conhece (lead, oportunidade, conversa). Colaborador nao esta na lista, e
    estender aquela tupla so faz sentido quando existirem nos de People no
    editor. Ate la, escalar resolve e nao acopla nada.

    O CPF vai MASCARADO. Contexto de evento circula por fluxo do cliente, por
    log e por integracao externa, e documento inteiro nao tem por que passear
    por ali.
    """
    unidade = getattr(colaborador, 'unidade', None)
    contexto = {
        'colaborador_id': colaborador.pk,
        'colaborador_nome': colaborador.nome_completo,
        'nome': colaborador.nome_completo,
        'telefone': colaborador.telefone or '',
        'email': colaborador.email or '',
        'cpf_mascarado': colaborador.cpf_mascarado,
        'situacao': colaborador.situacao,
        'situacao_rotulo': colaborador.situacao_rotulo,
        'cargo': colaborador.cargo or '',
        'unidade_id': getattr(unidade, 'pk', None),
        'unidade_nome': getattr(unidade, 'nome', ''),
        'ponto_entrada': colaborador.ponto_entrada,
        'origem_cadastro': colaborador.origem_cadastro,
    }
    contexto.update(extras)
    return contexto


def emitir(evento, colaborador, *, mensagem='', request=None, usuario=None,
           extras=None, nivel=None):
    """
    Emite nos dois canais derivados. Blindado: telemetria nunca derruba a
    operacao que a gerou.

    Um cadastro que falha porque o log de auditoria falhou seria uma troca
    pessima. O `HistoricoSituacao` ja foi gravado pelo servico antes de chegar
    aqui, entao mesmo o silencio total deixa rastro.
    """
    if not evento or colaborador is None:
        return

    extras = extras or {}
    acao = evento.rsplit('.', 1)[-1]
    tenant = getattr(colaborador, 'tenant', None)

    try:
        from apps.sistema.utils import registrar_acao
        registrar_acao(
            'people', acao, 'colaborador', colaborador.pk,
            mensagem or _mensagem_padrao(evento, colaborador),
            request=request,
            dados_extras={'evento': evento, **extras},
            nivel=nivel or NIVEL_POR_EVENTO.get(evento, 'INFO'),
            tenant=tenant,
        )
    except Exception:  # noqa: BLE001
        logger.exception('people.telemetria: registrar_acao falhou (evento=%s)', evento)

    try:
        from apps.automacao.hub import disparar_evento
        disparar_evento(evento, contexto_do_colaborador(colaborador, **extras),
                        tenant=tenant)
    except Exception:  # noqa: BLE001
        logger.exception('people.telemetria: disparar_evento falhou (evento=%s)', evento)


def emitir_duplicata_bloqueada(tenant, *, motivo, candidatos, request=None, extras=None):
    """
    Caso especial: nao ha colaborador criado pra pendurar o evento.

    Vale medir mesmo assim. Volume alto de duplicata bloqueada num link publico
    e sinal de que o formulario esta confuso ou de que alguem esta abusando, e
    esse numero nao existe em lugar nenhum se nao for registrado aqui.
    """
    try:
        from apps.sistema.utils import registrar_acao
        alvo = candidatos[0].colaborador if candidatos else None
        registrar_acao(
            'people', 'duplicata_bloqueada', 'colaborador',
            getattr(alvo, 'pk', None),
            f'Cadastro recusado por possivel duplicata ({motivo}).',
            request=request, nivel='WARNING', tenant=tenant,
            dados_extras={
                'evento': EVENTO_DUPLICATA_BLOQUEADA,
                'motivo': motivo,
                'candidatos': [
                    {'id': c.colaborador.pk, 'forca': c.forca, 'match': c.motivo}
                    for c in candidatos
                ],
                **(extras or {}),
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception('people.telemetria: duplicata_bloqueada falhou')


def _mensagem_padrao(evento, colaborador):
    return f'{colaborador.nome_completo}: {evento.rsplit(".", 1)[-1].replace("_", " ")}.'
