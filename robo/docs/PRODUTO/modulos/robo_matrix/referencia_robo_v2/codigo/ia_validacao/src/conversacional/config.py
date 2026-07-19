"""Configuração da camada conversacional (IA por cima do núcleo determinístico).

Tudo aqui é ISOLADO do fluxo atual. As rotas /ia/validar e /ia/proximo-passo
não são afetadas. Esta camada só é ativada via a rota nova /conv/turno.
"""
import os


class ConvConfig:
    # ── Modelo de IA pra conversação ──────────────────────────────────
    # gpt-4o é bem superior ao mini em entender linguagem natural,
    # extrair múltiplos campos e responder de forma fluida. Configurável.
    MODELO_CONVERSA = os.getenv('OPENAI_MODEL_CONVERSA', 'gpt-4o')
    # Modelo barato pra tarefas simples (extração estruturada quando dá)
    MODELO_RAPIDO = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    TIMEOUT = int(os.getenv('OPENAI_CONV_TIMEOUT', '30'))

    # ── Flags de cada passo (liga/desliga independente) ───────────────
    PASSO1_HUMANIZAR = os.getenv('CONV_PASSO1_HUMANIZAR', 'true').lower() == 'true'
    PASSO2_EXTRACAO  = os.getenv('CONV_PASSO2_EXTRACAO', 'true').lower() == 'true'
    PASSO3_FAQ       = os.getenv('CONV_PASSO3_FAQ', 'true').lower() == 'true'

    PERSONA_NOME = os.getenv('PERSONA_NOME', 'Aurora')
    PERSONA_EMPRESA = os.getenv('PERSONA_EMPRESA', 'Megalink')


conv_config = ConvConfig()


# ──────────────────────────────────────────────────────────────────────
# Base de conhecimento (FAQ) — usada no Passo 3.
# Quando o cliente pergunta algo no meio do fluxo, a IA responde a partir
# DESTES fatos (não inventa). Edite conforme as políticas reais.
# ──────────────────────────────────────────────────────────────────────
FAQ_BASE = """
FATOS SOBRE A MEGALINK (use apenas o que está aqui; se não souber, diga que
um atendente confirma):

PLANOS E PREÇOS:
- Plano 620 Mega: R$ 99,90/mês (com desconto de pontualidade)
- Plano 1GB Turbo: R$ 129,90/mês (com desconto de pontualidade)
- O desconto de pontualidade vale para pagamento até a data de vencimento.

FIDELIDADE E CONTRATO:
- Os planos têm fidelidade de 12 meses.
- O valor com desconto é válido para pagamentos em dia.

INSTALAÇÃO:
- A instalação é agendada por turno (manhã 08-12h ou tarde 13-17h).
- O prazo de instalação é de até 48h, podendo ser antes.
- A instalação é feita por técnico próprio da Megalink.

VENCIMENTO:
- O cliente escolhe o dia do vencimento da fatura (1, 5, 15 ou 20).

PAGAMENTO:
- A cobrança é mensal, via boleto/carnê.

DOCUMENTAÇÃO:
- Para finalizar, pedimos 3 fotos: selfie com documento, frente e verso
  do RG ou CNH.

COBERTURA:
- A disponibilidade depende do CEP. Confirmamos a cobertura ao informar o CEP.
"""
