from apps.cs.clube.models import MembroClube, RegraPontuacao, ExtratoPontuacao
from django.db import transaction
from django.db.models import F
from django.utils import timezone

class GamificationService:
    @staticmethod
    @transaction.atomic
    def atribuir_pontos(membro: MembroClube, gatilho: str, descricao_extra: str = "") -> tuple:
        """
        Adiciona pontos de Saldo e XP a um membro baseado em um gatilho cadastrado.
        Retorna (sucesso, mensagem).
        Usa select_for_update + F() para evitar race conditions.
        """
        try:
            regra = RegraPontuacao.objects.get(gatilho=gatilho, ativo=True)
        except RegraPontuacao.DoesNotExist:
            return False, f"Regra inativa ou inexistente para gatilho: {gatilho}"

        # Lock do membro para evitar race condition
        membro = MembroClube.objects.select_for_update().get(id=membro.id)

        # Verificar limites
        if regra.limite_por_membro > 0:
            qtd_vezes_ganhas = ExtratoPontuacao.objects.filter(membro=membro, regra=regra).count()
            if qtd_vezes_ganhas >= regra.limite_por_membro:
                return False, f"Membro já atingiu o limite para a regra: {regra.nome_exibicao}"

        # Efetivar pontuação com F() — atômico no banco
        MembroClube.objects.filter(id=membro.id).update(
            saldo=F('saldo') + regra.pontos_saldo,
            xp_total=F('xp_total') + regra.pontos_xp,
        )
        membro.refresh_from_db()

        # Registrar o extrato de pontuação
        ExtratoPontuacao.objects.create(
            membro=membro,
            regra=regra,
            pontos_saldo_ganhos=regra.pontos_saldo,
            pontos_xp_ganhos=regra.pontos_xp,
            descricao_extra=descricao_extra
        )

        return True, f"Ganhou {regra.pontos_saldo} saldo e {regra.pontos_xp} XP."
