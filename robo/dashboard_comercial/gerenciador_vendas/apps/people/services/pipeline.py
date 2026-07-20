"""
Movimentacao de candidato no pipeline.

Caminho unico de mudanca de etapa e de saida, no mesmo espirito do
`mover_situacao` do DP: a view nao decide nada, delega pra ca, e aqui e o unico
lugar que grava HistoricoCandidato. Sem isso o funil ficaria cego a cada
movimento feito por fora.

Diferenca em relacao ao DP: la a maquina de transicoes e fixa e rica. Aqui
mover ENTRE etapas e livre (etapa e so ordem, o RH sabe quando pular Teste
Pratico), e a unica regra dura e a SAIDA, que exige motivo e, no caso de
admitido ja vinculado, trava. Ver estados_recrutamento.
"""
from django.db import transaction

from apps.people import estados_recrutamento as estados_rs
from apps.people.models import Candidato, EtapaPipeline, HistoricoCandidato


# Campos que uma movimentacao pode mexer. Depois de gravar na linha travada,
# reflete de volta no objeto que o chamador segurou, senao ele fica com dado
# velho: o mesmo bug que o mover_situacao do DP ja teve.
_CAMPOS_SINCRONIZADOS = ('saida', 'motivo_saida', 'etapa_id')


def _sincronizar(destino, fonte):
    for campo in _CAMPOS_SINCRONIZADOS:
        setattr(destino, campo, getattr(fonte, campo))


def mover_para_etapa(candidato, etapa, *, usuario=None, origem='painel'):
    """
    Move o candidato pra uma etapa intermediaria.

    Mover entre etapas e livre de proposito: etapa e configuracao, nao maquina.
    O que este servico garante e a integridade do escopo (a etapa e do tenant e
    da unidade certa) e a trilha no historico.
    """
    if etapa.tenant_id != candidato.tenant_id:
        raise ValueError('Etapa de outro tenant.')

    de = candidato.etapa.nome if candidato.etapa_id else ''

    with transaction.atomic():
        travado = (Candidato.all_tenants
                   .select_for_update()
                   .get(pk=candidato.pk))

        # `de` sai do objeto travado, e nao do passado: o chamador pode estar
        # com uma copia velha (garantir_etapa_inicial chama mover em sequencia),
        # e ai o de_etapa do historico sairia errado.
        de = travado.etapa.nome if travado.etapa_id else de

        # Reabrir: se estava numa saida, voltar pro pipeline limpa a saida. A
        # regra de PODE reabrir e do estados_rs, e ja foi checada na view; aqui
        # so aplicamos a consequencia.
        travado.saida = ''
        travado.motivo_saida = ''
        travado.etapa = etapa
        travado.save(update_fields=['saida', 'motivo_saida', 'etapa',
                                    'atualizado_em'])

        HistoricoCandidato.all_tenants.create(
            tenant=travado.tenant, candidato=travado,
            de_etapa=de, para_etapa=etapa.nome,
            usuario=usuario, origem=origem,
        )

    _sincronizar(candidato, travado)
    return candidato


def dar_saida(candidato, saida, *, motivo='', usuario=None, origem='painel'):
    """
    Tira o candidato do pipeline por uma saida terminal.

    Toda a regra de dominio (saida existe, motivo obrigatorio, admitido
    vinculado nao reabre) vive em estados_recrutamento e e validada aqui, num
    lugar so, pra que a view nao precise conhecer a maquina.
    """
    estados_rs.validar_saida(saida, motivo)

    with transaction.atomic():
        travado = (Candidato.all_tenants
                   .select_for_update()
                   .get(pk=candidato.pk))

        de = travado.etapa.nome if travado.etapa_id else ''

        travado.saida = saida
        travado.motivo_saida = motivo
        travado.save(update_fields=['saida', 'motivo_saida', 'atualizado_em'])

        HistoricoCandidato.all_tenants.create(
            tenant=travado.tenant, candidato=travado,
            de_etapa=de, para_saida=saida, motivo=motivo,
            usuario=usuario, origem=origem,
        )

    _sincronizar(candidato, travado)
    return candidato


def reabrir(candidato, etapa, *, usuario=None, origem='painel'):
    """
    Traz o candidato de volta pra uma etapa a partir de uma saida.

    Valida contra a regra de reabertura ANTES de mover: admitido que ja virou
    colaborador nao volta, senao ficaria uma pessoa contratada dentro do
    processo seletivo.
    """
    estados_rs.validar_reabertura(
        candidato.saida,
        tem_colaborador_vinculado=bool(candidato.colaborador_id))

    return mover_para_etapa(candidato, etapa, usuario=usuario, origem=origem)


def garantir_etapa_inicial(candidato, *, usuario=None):
    """
    Poe o candidato na primeira etapa do pipeline, se ele ainda nao tem etapa.

    Chamado quando o candidato chega pelo formulario publico: ele nasce sem
    etapa (a submissao nao sabe de pipeline) e precisa cair na porta de entrada
    pra aparecer no board. Sem etapa nenhuma configurada, fica fora do board e
    aparece numa area de "sem etapa", em vez de sumir.
    """
    if candidato.etapa_id:
        return candidato

    primeira = (EtapaPipeline.do_escopo(candidato.tenant, candidato.unidade)
                .order_by('ordem', 'id').first())
    if primeira is None:
        return candidato

    return mover_para_etapa(candidato, primeira, usuario=usuario,
                            origem='link_publico')
