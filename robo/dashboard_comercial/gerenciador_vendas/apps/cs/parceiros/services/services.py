import uuid
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from apps.cs.parceiros.models import CupomDesconto, ResgateCupom


class CupomService:

    @staticmethod
    @transaction.atomic
    def resgatar_cupom(membro, cupom_id):
        """
        Resgata um cupom para o membro.
        Retorna (sucesso, mensagem, resgate_ou_none)
        """
        try:
            cupom = CupomDesconto.objects.select_for_update().get(id=cupom_id, ativo=True)
        except CupomDesconto.DoesNotExist:
            return False, "Cupom não encontrado ou inativo.", None

        now = timezone.now()

        # Validar validade
        if now < cupom.data_inicio or now > cupom.data_fim:
            return False, "Cupom fora do período de validade.", None

        # Validar estoque
        if cupom.quantidade_total > 0 and cupom.quantidade_resgatada >= cupom.quantidade_total:
            return False, "Cupom esgotado.", None

        # Validar limite por membro
        resgates_membro = ResgateCupom.objects.filter(
            membro=membro, cupom=cupom
        ).exclude(status='cancelado').count()
        if resgates_membro >= cupom.limite_por_membro:
            return False, "Você já atingiu o limite de resgates para este cupom.", None

        # Validar cidade
        if cupom.cidades_permitidas.exists():
            if not cupom.cidades_permitidas.filter(nome__iexact=membro.cidade).exists():
                return False, "Cupom não disponível para sua cidade.", None

        # Validar por modalidade
        pontos_gastos = 0
        if cupom.modalidade == 'pontos':
            if membro.saldo < cupom.custo_pontos:
                return False, f"Saldo insuficiente. Necessário: {cupom.custo_pontos} pts.", None
            pontos_gastos = cupom.custo_pontos
        elif cupom.modalidade == 'nivel':
            if cupom.nivel_minimo:
                if membro.xp_total < cupom.nivel_minimo.xp_necessario:
                    return False, f"Nível insuficiente. Necessário: {cupom.nivel_minimo.nome}.", None

        # Debitar pontos se necessário
        if pontos_gastos > 0:
            membro.saldo = F('saldo') - pontos_gastos
            membro.save(update_fields=['saldo'])
            membro.refresh_from_db()

        # Incrementar quantidade resgatada
        CupomDesconto.objects.filter(id=cupom.id).update(
            quantidade_resgatada=F('quantidade_resgatada') + 1
        )

        # Gerar código único
        codigo_unico = uuid.uuid4().hex[:12].upper()

        # Criar resgate
        resgate = ResgateCupom.objects.create(
            membro=membro,
            cupom=cupom,
            codigo_unico=codigo_unico,
            pontos_gastos=pontos_gastos,
        )

        return True, f"Cupom resgatado! Código: {codigo_unico}", resgate

    @staticmethod
    def cupons_disponiveis(membro):
        """Retorna cupons disponíveis para o membro."""
        now = timezone.now()
        from django.db.models import Q

        qs = CupomDesconto.objects.filter(
            ativo=True,
            status_aprovacao='aprovado',
            data_inicio__lte=now,
            data_fim__gte=now,
        ).select_related('parceiro', 'nivel_minimo')

        # Filtrar por cidade
        qs = qs.filter(
            Q(cidades_permitidas__isnull=True) |
            Q(cidades_permitidas__nome__iexact=membro.cidade)
        ).distinct()

        # Filtrar com estoque
        resultado = []
        for cupom in qs:
            if cupom.quantidade_total > 0 and cupom.quantidade_resgatada >= cupom.quantidade_total:
                continue
            resultado.append(cupom)

        return resultado
