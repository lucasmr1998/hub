"""
A ponte entre Recrutamento e Departamento Pessoal.

E o unico ponto do modulo onde um Candidato vira um Colaborador. Ate aqui os
dois subdominios sao independentes: recrutamento cuida de quem ainda nao tem
vinculo, DP cuida de quem tem.

COPIA, E NAO VINCULO. As condicoes da vaga (cargo, tipo de contratacao, turno)
sao COPIADAS pro colaborador no ato da admissao. Depois disso nao existe ligacao
viva entre os dois: mudar a vaga no mes que vem nao altera o que foi registrado
pra quem ja entrou. A semantica e a mesma que a origem descreve na propria tela,
e existe por um motivo trabalhista: o que valeu na contratacao tem que continuar
sendo o que valeu, mesmo que a vaga seja reaproveitada e editada depois.

NAO E O CANDIDATO QUE "VIRA" COLABORADOR. Os dois registros coexistem, ligados
por `Candidato.colaborador`, porque respondem perguntas diferentes: um e a pessoa
da casa, outro e o processo seletivo que a trouxe. Apagar o candidato depois
destruiria a analise de canal ("de onde vieram os que ficaram?").

SEM CPF, DE PROPOSITO. O formulario publico nao coleta CPF: a origem testou e
descartou por atrito de conversao. O colaborador nasce sem CPF e portanto com
`pendente_revisao=True`, e o caminho pra completar e o link de cadastro do DP,
que e onde a constraint de CPF ja mora. Ver o docstring de `Candidato`.
"""
from django.db import transaction

from apps.people import estados
from apps.people import estados_recrutamento as estados_rs
from apps.people.excecoes import PeopleError
from apps.people.services.colaboradores import registrar_colaborador
from apps.people.services.pipeline import dar_saida


class AdmissaoInvalida(PeopleError):
    """Faltou dado, ou o candidato nao esta em condicao de ser admitido."""


def _dados_copiados_da_vaga(candidato, cargo, data_inicio):
    """
    O retrato das condicoes no momento da admissao.

    Le da vaga, e o resultado e gravado no colaborador. Nao guarda referencia
    pra vaga: e copia.
    """
    vaga = candidato.vaga
    dados = {
        'nome_completo': candidato.nome_completo,
        'telefone': candidato.whatsapp or '',
        'email': candidato.email or '',
        'data_nascimento': candidato.data_nascimento,
        'cidade': candidato.cidade or '',
        'estado': candidato.estado or '',
        'bairro': candidato.bairro or '',
        'cargo': cargo,
        'data_admissao': data_inicio,
    }
    if vaga and vaga.tipo_contratacao:
        # `tipo_contratacao` da vaga e texto livre ("CLT", "PJ"); o do
        # colaborador e choices. So copia quando CASA com uma choice, pra nao
        # gravar lixo num campo que outras telas filtram. Nao casou, fica vazio
        # e o DP preenche na admissao, que e onde esse dado e conferido mesmo.
        from apps.people.models import REGIME_CONTRATACAO_CHOICES

        chave = vaga.tipo_contratacao.strip().lower()
        if chave in {valor for valor, _ in REGIME_CONTRATACAO_CHOICES}:
            dados['regime_contratacao'] = chave
    return dados


def admitir_candidato(candidato, *, cargo, data_inicio, usuario=None,
                      request=None):
    """
    Cria o colaborador a partir do candidato e fecha o processo seletivo dele.

    Devolve o `ResultadoCadastro` de `registrar_colaborador`, porque o chamador
    precisa saber se criou, reaproveitou ou bateu em conflito: a pessoa pode ja
    existir no DP (ex-funcionario voltando), e nesse caso o certo e readmitir a
    linha existente, e nao criar uma segunda. E a regra R1 do modulo.

    Tudo numa transacao: um colaborador criado sem o candidato ter sido fechado
    deixaria a pessoa aparecendo nos dois lugares como se fossem dois processos.
    """
    if candidato.colaborador_id:
        raise AdmissaoInvalida(
            f'{candidato.nome_completo} já foi enviado para o Departamento '
            f'Pessoal.')
    if candidato.anonimizado_em:
        raise AdmissaoInvalida(
            'Este candidato foi anonimizado pela política de retenção e não '
            'pode mais ser admitido.')
    if cargo is None:
        raise AdmissaoInvalida('Escolha o cargo da contratação.')
    if data_inicio is None:
        raise AdmissaoInvalida('Informe a data de início.')
    if cargo.tenant_id != candidato.tenant_id:
        raise AdmissaoInvalida('Cargo de outro tenant.')

    dados = _dados_copiados_da_vaga(candidato, cargo, data_inicio)

    with transaction.atomic():
        resultado = registrar_colaborador(
            candidato.tenant, candidato.unidade, dados,
            origem='recrutamento',
            # Entra em ADMISSAO, e nao em experiencia: falta CPF e documento, e
            # e justamente isso que a fase de admissao do DP existe pra coletar.
            situacao_inicial=estados.SITUACAO_EM_ADMISSAO,
            usuario=usuario, request=request)

        if not resultado.ok:
            # Conflito de dedup (a pessoa ja existe no DP). Nao inventa segunda
            # linha: devolve pro chamador decidir, que e o contrato do servico.
            return resultado

        candidato.colaborador = resultado.colaborador
        candidato.save(update_fields=['colaborador', 'atualizado_em'])

        dar_saida(candidato, estados_rs.SAIDA_ADMITIDO,
                  motivo=f'Admitido como {cargo.nome}.',
                  usuario=usuario)

    return resultado
