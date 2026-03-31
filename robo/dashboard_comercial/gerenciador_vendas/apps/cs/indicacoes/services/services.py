from django.db import transaction
from django.utils import timezone
from apps.cs.indicacoes.models import Indicacao
from apps.cs.clube.services.gamification_service import GamificationService


class IndicacaoService:

    @staticmethod
    def criar_indicacao(membro_indicador, nome, telefone, cpf='', cidade=''):
        """
        Cria uma indicação.
        Retorna (sucesso, mensagem, indicacao_ou_none)
        """
        # Validar que não está indicando a si mesmo
        if membro_indicador.telefone and telefone == membro_indicador.telefone:
            return False, "Você não pode indicar a si mesmo.", None

        # Verificar duplicata
        if Indicacao.objects.filter(
            membro_indicador=membro_indicador,
            telefone_indicado=telefone
        ).exists():
            return False, "Você já indicou essa pessoa.", None

        indicacao = Indicacao.objects.create(
            membro_indicador=membro_indicador,
            nome_indicado=nome,
            telefone_indicado=telefone,
            cpf_indicado=cpf,
            cidade_indicado=cidade,
        )

        return True, "Indicação registrada com sucesso!", indicacao

    @staticmethod
    @transaction.atomic
    def confirmar_conversao(indicacao_id):
        """
        Confirma que o indicado virou cliente e credita pontos ao indicador.
        Retorna (sucesso, mensagem)
        """
        try:
            indicacao = Indicacao.objects.select_for_update().get(id=indicacao_id)
        except Indicacao.DoesNotExist:
            return False, "Indicação não encontrada."

        if indicacao.status == 'convertido':
            return False, "Indicação já foi convertida."

        if indicacao.pontos_creditados:
            return False, "Pontos já foram creditados."

        indicacao.status = 'convertido'
        indicacao.data_conversao = timezone.now()
        indicacao.save()

        # Creditar pontos ao indicador
        sucesso, msg = GamificationService.atribuir_pontos(
            membro=indicacao.membro_indicador,
            gatilho='indicacao_convertida',
            descricao_extra=f"Indicou {indicacao.nome_indicado} ({indicacao.telefone_indicado})"
        )

        if sucesso:
            indicacao.pontos_creditados = True
            indicacao.save(update_fields=['pontos_creditados'])

        return True, f"Indicação convertida! {msg}"
