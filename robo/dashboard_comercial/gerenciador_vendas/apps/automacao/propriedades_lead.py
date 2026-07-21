"""Registry de propriedades escreviveis do lead.

Espelho de `propriedades_oportunidade.py`, mesmo principio: escrever uma
propriedade e UM no so (`nodes/definir_propriedade_lead.py`) com a
propriedade escolhida em dropdown, nunca um no dedicado por atributo. Isso
viraria uma dezena de nos quase identicos. No dedicado fica reservado pra
COMPORTAMENTO, nao pra par chave/valor.

Contrato de erro identico ao da oportunidade: handler NUNCA levanta excecao
pra caso de negocio (campo ja preenchido, valor invalido, formato que nao
parseia). Isso e sempre `aplicado=False` com `motivo_skip`, so bug real sobe
como excecao. Motivo: erro deterministico nao deve acionar retry, reexecutar
nao muda o resultado.

Por que existe: o bot de venda coletava CPF, nome, email e endereco e nada
disso chegava na ficha do lead. As respostas ficavam so na tabela do
checklist, entao a vendedora abria o lead e via os campos vazios.

`somente_se_vazio` nasce LIGADO de proposito. O bot pode reperguntar um item
(o cliente corrige o que digitou) e uma segunda passada nao deve sobrescrever
dado que um humano ajustou na ficha no meio do caminho.
"""
import re
from datetime import datetime

# Campos simples de texto: mesmo handler, so muda o atributo. Manter o
# `max_length` em mente nao e necessario aqui: o `full_clean` do save nao roda,
# mas os campos do model sao folgados o bastante pro que o bot coleta.
_CAMPOS_TEXTO = {
    'nome_razaosocial': 'Nome ou razao social',
    'email': 'Email',
    'rg': 'RG',
    'cep': 'CEP',
    'rua': 'Rua',
    'numero_residencia': 'Numero',
    'bairro': 'Bairro',
    'cidade': 'Cidade',
    'estado': 'UF',
    'ponto_referencia': 'Ponto de referencia',
}

_FORMATOS_DATA = ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y')


def _resultado(aplicado, motivo_skip=None, detalhe=''):
    return {'aplicado': aplicado, 'motivo_skip': motivo_skip, 'detalhe': detalhe}


def _escrever(lead, atributo, valor, somente_se_vazio, *, detalhe=''):
    atual = getattr(lead, atributo, None)
    if somente_se_vazio and atual not in (None, ''):
        return _resultado(False, 'ja_preenchido', f'{atributo} já tinha valor')
    if atual == valor:
        return _resultado(False, 'sem_mudanca', f'{atributo} já era esse valor')
    setattr(lead, atributo, valor)
    lead.save(update_fields=[atributo])
    return _resultado(True, None, detalhe or f'{atributo} = {valor}')


def _texto(atributo):
    def handler(tenant, lead, valor, *, chave='', somente_se_vazio=True):
        texto = str(valor or '').strip()
        if not texto:
            return _resultado(False, 'valor_vazio', f'nada a gravar em {atributo}')
        return _escrever(lead, atributo, texto, somente_se_vazio)
    return handler


def _cpf_cnpj(tenant, lead, valor, *, chave='', somente_se_vazio=True):
    """Grava SO os digitos: e o formato que o HubSoft espera na consulta por
    `termo_busca`, e o que a busca de lead duplicado compara. Deixar a
    pontuacao aqui faria o mesmo CPF nao casar consigo mesmo entre origens."""
    digitos = re.sub(r'\D', '', str(valor or ''))
    if len(digitos) not in (11, 14):
        return _resultado(False, 'formato_invalido',
                          f'{len(digitos)} dígitos, esperado 11 (CPF) ou 14 (CNPJ)')
    return _escrever(lead, 'cpf_cnpj', digitos, somente_se_vazio)


def _data_nascimento(tenant, lead, valor, *, chave='', somente_se_vazio=True):
    """Aceita o formato que o cliente digita no WhatsApp (01/01/1990) e o ISO
    que a cascata de validacao ja normaliza (1990-01-01)."""
    texto = str(valor or '').strip()
    if not texto:
        return _resultado(False, 'valor_vazio', 'data vazia')
    for formato in _FORMATOS_DATA:
        try:
            data = datetime.strptime(texto, formato).date()
        except ValueError:
            continue
        return _escrever(lead, 'data_nascimento', data, somente_se_vazio)
    return _resultado(False, 'formato_invalido', f'não reconheci a data {texto!r}')


def _dado_custom(tenant, lead, valor, *, chave='', somente_se_vazio=True):
    """Campo livre em `dados_custom`, pro que nao tem coluna propria. Exige
    `chave`, igual ao Marcador da oportunidade."""
    slug = str(chave or '').strip()
    if not slug:
        return _resultado(False, 'sem_chave', 'dado custom exige uma chave')
    atuais = lead.dados_custom or {}
    if somente_se_vazio and atuais.get(slug) not in (None, ''):
        return _resultado(False, 'ja_preenchido', f'dados_custom[{slug}] já tinha valor')
    lead.dados_custom = {**atuais, slug: valor}
    lead.save(update_fields=['dados_custom'])
    return _resultado(True, None, f'dados_custom[{slug}] = {valor}')


PROPRIEDADES = {
    'cpf_cnpj': {'label': 'CPF ou CNPJ', 'usa_chave': False, 'handler': _cpf_cnpj},
    'data_nascimento': {'label': 'Data de nascimento', 'usa_chave': False,
                        'handler': _data_nascimento},
    'dado_custom': {'label': 'Dado custom (dados_custom)', 'usa_chave': True,
                    'handler': _dado_custom},
    **{
        nome: {'label': label, 'usa_chave': False, 'handler': _texto(nome)}
        for nome, label in _CAMPOS_TEXTO.items()
    },
}


def opcoes_propriedades(tenant=None):
    """Opcoes pro dropdown do campo `propriedade` do no `definir_propriedade_lead`.

    `tenant` nao filtra (o catalogo e global). O parametro so existe pra seguir
    a assinatura padrao das fontes de opcoes (`opcoes.py:opcoes_de`).
    """
    return [{'value': k, 'label': v['label']} for k, v in PROPRIEDADES.items()]
