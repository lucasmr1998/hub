from apps.cs.carteirinha.models import ModeloCarteirinha, RegraAtribuicao, CarteirinhaMembro


class CarteirinhaService:

    @staticmethod
    def obter_modelo_para_membro(membro):
        """
        Retorna o ModeloCarteirinha mais adequado para o membro,
        baseado nas regras de atribuicao ativas (maior prioridade vence).
        """
        # 1. Verificar se tem carteirinha manual ativa
        manual = CarteirinhaMembro.objects.filter(
            membro=membro, ativo=True
        ).select_related('modelo').first()
        if manual and manual.modelo.ativo:
            return manual.modelo

        # 2. Buscar regras automaticas (ordenadas por prioridade)
        regras = RegraAtribuicao.objects.filter(
            ativo=True, modelo__ativo=True
        ).select_related('modelo', 'nivel').order_by('-prioridade')

        for regra in regras:
            if regra.tipo == 'todos':
                return regra.modelo

            elif regra.tipo == 'nivel':
                if regra.nivel and membro.nivel_atual == regra.nivel.nome:
                    return regra.modelo

            elif regra.tipo == 'pontuacao_minima':
                if membro.xp_total >= regra.pontuacao_minima:
                    return regra.modelo

            elif regra.tipo == 'cidade':
                if membro.cidade and membro.cidade.lower() == regra.cidade.lower():
                    return regra.modelo

        # 3. Fallback: primeiro modelo ativo
        return ModeloCarteirinha.objects.filter(ativo=True).first()

    @staticmethod
    def obter_carteirinha_membro(membro):
        """
        Retorna o CarteirinhaMembro ativo ou cria um baseado na regra automatica.
        """
        # Carteirinha manual ativa
        existente = CarteirinhaMembro.objects.filter(
            membro=membro, ativo=True
        ).select_related('modelo').first()
        if existente and existente.modelo.ativo:
            return existente

        # Resolver modelo automatico
        modelo = CarteirinhaService.obter_modelo_para_membro(membro)
        if not modelo:
            return None

        # Criar ou atualizar carteirinha
        carteirinha, created = CarteirinhaMembro.objects.update_or_create(
            membro=membro,
            ativo=True,
            defaults={'modelo': modelo}
        )
        return carteirinha
