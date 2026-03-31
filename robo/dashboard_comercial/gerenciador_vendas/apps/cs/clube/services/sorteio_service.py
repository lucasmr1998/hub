import random

class SorteioService:
    @staticmethod
    def executar_giro_roleta(membro, premios_disponiveis: list, custo_giro: int):
        """
        Subtrai o saldo do membro, roda o cálculo de probabilidade com pesos 
        para os prêmios disponíveis no estoque e retorna:
        (novo_saldo, premio_selecionado, posicao_engrenagem)
        
        ATENÇÃO: o decremento do estoque é feito atomicamente na view via F(),
        NÃO aqui — para evitar duplo-decremento e race conditions.
        """
        # Deduz saldo logicamente (persistido na view pai dentro de transaction)
        novo_saldo = membro.saldo - custo_giro

        # Sorteio matemático com pesos de probabilidade
        pesos = [p.probabilidade for p in premios_disponiveis]
        premio_selecionado = random.choices(premios_disponiveis, weights=pesos, k=1)[0]

        # Converte as posições válidas
        try:
            pos_list = [int(x.strip()) for x in premio_selecionado.posicoes.split(',')]
        except Exception:
            pos_list = [4, 7]  # Fallback de emergência

        roleta_pos = random.choice(pos_list)

        return novo_saldo, premio_selecionado, roleta_pos
