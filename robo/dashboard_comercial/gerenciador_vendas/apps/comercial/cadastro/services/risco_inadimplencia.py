"""
Calculadora rule-based de score de risco de inadimplência pra novas vendas.

Score 0-100. Threshold sugerido:
  - 0-39: baixo risco
  - 40-69: risco médio
  - 70-100: alto risco (requer aprovação de gerente)

Sinais ponderados (todos opcionais):
  - Cliente novo (< 6 meses cadastrado): +15
  - Plano valor mensal > R$ 200: +10
  - Forma de cobrança = boleto (em vez de Pix/cartão): +10
  - Histórico: 2+ atrasos em pagamentos prévios: +30
  - Cliente cancelado e voltou: +20
  - Já tem inadimplência ativa em outro contrato: +25

Defensivo: sinais sem dados retornam 0. Quando módulos correspondentes não
estão configurados, score sai mais baixo (otimista).
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)


def calcular(lead, plano_valor=None, forma_cobranca=None):
    """
    Calcula score de risco de inadimplência pra uma venda em potencial.

    Args:
        lead: LeadProspecto sendo avaliado
        plano_valor: Decimal/float do valor mensal do plano (opcional)
        forma_cobranca: 'boleto' | 'pix' | 'cartao' (opcional)

    Returns:
        tuple (score 0-100, sinais_dict)
    """
    sinais = {}
    score = 0
    agora = timezone.now()

    # --- Cliente novo --------------------------------------------------------
    if lead.data_cadastro:
        meses = (agora - lead.data_cadastro).days / 30
        if meses < 6:
            sinais['lead_novo_menos_6m'] = 15
            score += 15

    # --- Valor do plano ------------------------------------------------------
    if plano_valor:
        try:
            valor = float(plano_valor)
            if valor > 200:
                sinais['plano_valor_alto'] = 10
                score += 10
        except (TypeError, ValueError):
            pass

    # --- Forma de cobrança ---------------------------------------------------
    if forma_cobranca and str(forma_cobranca).lower() in ('boleto', 'bol'):
        sinais['cobranca_boleto'] = 10
        score += 10

    # --- Histórico de atrasos do CPF/CNPJ -------------------------------------
    # Pesquisa em ClienteHubsoft com mesmo CPF: alguma vez teve alerta de cobrança?
    try:
        from apps.integracoes.models import ClienteHubsoft
        cpf = (lead.cpf_cnpj or '').strip()
        if cpf:
            historicos = ClienteHubsoft.all_tenants.filter(cpf_cnpj=cpf)
            atrasos = 0
            cancelado_e_voltou = False
            tem_outro_inadimplente = False
            for cli in historicos:
                msgs = ' '.join(cli.alerta_mensagens or []).lower() if cli.alerta_mensagens else ''
                if cli.alerta and any(p in msgs for p in ('atraso', 'cobranca', 'cobrança', 'inadimpl')):
                    atrasos += 1
                    if cli.ativo:
                        tem_outro_inadimplente = True
                if not cli.ativo:
                    # cliente foi cancelado
                    if any(c.ativo for c in historicos if c.id != cli.id):
                        cancelado_e_voltou = True
            if atrasos >= 2:
                sinais['historico_2plus_atrasos'] = 30
                score += 30
            elif atrasos == 1:
                sinais['historico_1_atraso'] = 10
                score += 10
            if cancelado_e_voltou:
                sinais['cancelou_e_voltou'] = 20
                score += 20
            if tem_outro_inadimplente:
                sinais['inadimplente_em_outro_contrato'] = 25
                score += 25
    except Exception as exc:
        logger.debug('Erro ao buscar histórico de atrasos pra lead %s: %s', lead.id, exc)

    score = min(100, score)
    return score, sinais


def classificar(score):
    """Retorna classe pelo score: 'baixo', 'medio', 'alto'."""
    if score is None:
        return 'sem_dados'
    if score < 40:
        return 'baixo'
    if score < 70:
        return 'medio'
    return 'alto'


def requer_aprovacao_gerente(score):
    """Vendas com risco >= 70 só podem ser aprovadas por gerente."""
    return score is not None and score >= 70
