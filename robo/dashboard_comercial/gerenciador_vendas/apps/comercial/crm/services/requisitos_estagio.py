"""
Validacao de campos obrigatorios para entrar em um estagio do pipeline.

Cada PipelineEstagio tem `campos_obrigatorios` (JSON list) tipo:
  ["lead.cpf_cnpj", "lead.cep", "oportunidade.valor_estimado"]

Antes de mover uma oportunidade pra esse estagio, o sistema verifica se
todos os campos listados estao preenchidos. Se algum faltar, a transicao
e bloqueada.

Configurado pelo operador na UI (`/crm/configuracoes/`).
"""


# Lista de campos disponiveis pra serem marcados como obrigatorios na UI.
# Cada item: (codigo, label, modulo).
CAMPOS_DISPONIVEIS = [
    # Lead — identificacao
    ('lead.nome_razaosocial', 'Nome / Razao social', 'Lead'),
    ('lead.email',            'E-mail',             'Lead'),
    ('lead.telefone',         'Telefone',           'Lead'),
    ('lead.cpf_cnpj',         'CPF / CNPJ',         'Lead'),
    ('lead.rg',               'RG',                 'Lead'),
    ('lead.data_nascimento',  'Data de nascimento', 'Lead'),
    # Lead — endereco
    ('lead.cep',              'CEP',                'Endereco'),
    ('lead.rua',              'Rua',                'Endereco'),
    ('lead.numero_residencia','Numero',             'Endereco'),
    ('lead.bairro',           'Bairro',             'Endereco'),
    ('lead.cidade',           'Cidade',             'Endereco'),
    ('lead.estado',           'Estado (UF)',        'Endereco'),
    # Lead — qualificacao
    ('lead.empresa',          'Empresa',            'Qualificacao'),
    ('lead.score_qualificacao','Score (1-10)',      'Qualificacao'),
    # Lead — gates externos
    ('lead.score_status_aprovado',  'Score externo APROVADO',     'Gate externo'),
    ('lead.documentacao_validada',  'Documentacao validada',      'Gate externo'),
    ('lead.contrato_aceito',        'Contrato aceito',            'Gate externo'),
    # Oportunidade
    ('oportunidade.valor_estimado', 'Valor estimado',             'Oportunidade'),
    ('oportunidade.probabilidade',  'Probabilidade (%)',          'Oportunidade'),
    ('oportunidade.data_fechamento_previsto', 'Data fechamento prevista', 'Oportunidade'),
    ('oportunidade.responsavel',    'Responsavel atribuido',      'Oportunidade'),
    # Oportunidade - Perda (campos pra exigir ao mover pra "Perdido")
    ('oportunidade.motivo_perda_ref',       'Motivo da perda (lista)',       'Perda'),
    ('oportunidade.motivo_perda_categoria', 'Motivo da perda (categoria)',   'Perda'),
    ('oportunidade.motivo_perda',           'Motivo da perda (texto livre)', 'Perda'),
]


CAMPOS_DISPONIVEIS_DICT = {codigo: (label, modulo) for codigo, label, modulo in CAMPOS_DISPONIVEIS}


def _resolver_valor(oportunidade, codigo_campo):
    """Resolve o valor de um codigo de campo (ex: 'lead.cpf_cnpj') na oportunidade."""
    if codigo_campo == 'oportunidade.responsavel':
        return oportunidade.responsavel_id
    if codigo_campo.startswith('oportunidade.'):
        return getattr(oportunidade, codigo_campo.split('.', 1)[1], None)
    if codigo_campo.startswith('lead.'):
        lead = oportunidade.lead
        if not lead:
            return None
        # Casos especiais (booleanos derivados)
        if codigo_campo == 'lead.score_status_aprovado':
            return getattr(lead, 'score_status', None) == 'aprovado'
        return getattr(lead, codigo_campo.split('.', 1)[1], None)
    return None


def _valor_preenchido(valor):
    """Considera preenchido se nao for None/vazio/0 (False -> nao preenchido)."""
    if valor is None:
        return False
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str) and not valor.strip():
        return False
    return True


def campos_faltando(oportunidade, estagio_destino):
    """
    Retorna lista de tuplas (codigo, label) dos campos faltantes.
    Lista vazia = OK pra mover.
    """
    if not estagio_destino:
        return []
    obrigatorios = estagio_destino.campos_obrigatorios or []
    faltando = []
    for codigo in obrigatorios:
        valor = _resolver_valor(oportunidade, codigo)
        if not _valor_preenchido(valor):
            label = CAMPOS_DISPONIVEIS_DICT.get(codigo, (codigo, ''))[0]
            faltando.append((codigo, label))
    return faltando


def validar_avanco(oportunidade, estagio_destino):
    """
    Levanta `ValueError` se faltarem campos obrigatorios.
    Caso contrario, retorna True.

    Uso pelo `api_mover_oportunidade` / engine de automacao.
    """
    faltando = campos_faltando(oportunidade, estagio_destino)
    if faltando:
        labels = ', '.join(l for _, l in faltando)
        raise ValueError(f'Campos obrigatorios faltando para mover pra "{estagio_destino.nome}": {labels}')
    return True
