"""Retomar ou recomeçar — EXCLUSIVO da camada conversacional.

Quando um cliente volta (primeira mensagem da sessão) e já tinha progresso
significativo de um atendimento anterior, mostramos o que já foi coletado e
perguntamos se quer continuar de onde parou ou começar de novo.

Antes isso vivia no núcleo (onboarding/engine) e era usado pelos dois
fluxos; foi movido pra cá pra deixar o determinístico no estado original.
A pergunta usa a regra 'retomar_ou_recomecar' (config no Django).
"""
from __future__ import annotations

from src.integracoes.robovendas import PLANOS
from src.conversacional import motor

# Quantos campos significativos já preenchidos pra valer a pena perguntar.
MIN_CAMPOS_PROGRESSO = 3

# Campos da coleta a limpar quando o cliente escolhe "começar de novo".
# Mantém cpf_cnpj (acabou de ser identificado) e status_api.
CAMPOS_RECOMECAR: dict = {
    'nome_razaosocial': '', 'data_nascimento': None, 'email': '',
    'tipo_imovel': '', 'tipo_residencia': '',
    'cep': '', 'rua': '', 'bairro': '', 'cidade': '', 'estado': '',
    'numero_residencia': '', 'ponto_referencia': '', 'endereco': '',
    'endereco_confirmado': None,
    'id_plano_rp': None, 'valor': None, 'plano_confirmado': None,
    'id_dia_vencimento': None,
    'dados_confirmados': None,
    'doc_selfie_recebida': None, 'doc_frente_recebida': None,
    'doc_verso_recebida': None,
    'turno_instalacao': '', 'data_instalacao': None,
}

# id_plano_rp → título (derivado da tabela oficial).
_PLANO_TITULO = {p['id_plano_rp']: p['titulo'] for p in PLANOS.values()}


def tem_progresso(dados: dict) -> bool:
    """True se há campos suficientes pra valer perguntar retomar/recomeçar."""
    preenchidos = motor.campos_preenchidos(dados, em_new_service=False)
    # nome_razaosocial genérico não conta como progresso real
    return len(preenchidos) >= MIN_CAMPOS_PROGRESSO


def montar_resumo(lead: dict) -> str:
    """Texto com o que já foi coletado + pergunta continuar/recomeçar."""
    linhas = []
    nome = (lead.get('nome_razaosocial') or '').strip()
    if nome and not motor.nome_eh_generico(nome):
        linhas.append(f'##1f464## *Nome:* {nome}')
    cpf = (lead.get('cpf_cnpj') or '').strip()
    if cpf:
        linhas.append(f'##1f194## *CPF:* {cpf}')
    nasc = lead.get('data_nascimento')
    if nasc:
        if hasattr(nasc, 'strftime'):
            nasc = nasc.strftime('%d/%m/%Y')
        linhas.append(f'##1f382## *Nascimento:* {nasc}')
    email = (lead.get('email') or '').strip()
    if email:
        linhas.append(f'##2709## *E-mail:* {email}')
    # Endereço (mostra o que tiver)
    rua = (lead.get('rua') or '').strip()
    num = (lead.get('numero_residencia') or '').strip()
    bairro = (lead.get('bairro') or '').strip()
    cidade = (lead.get('cidade') or '').strip()
    estado = (lead.get('estado') or '').strip()
    cep = (lead.get('cep') or '').strip()
    end_partes = []
    if rua:
        end_partes.append(f'{rua}{(", Nº " + num) if num else ""}')
    if bairro:
        end_partes.append(bairro)
    if cidade or estado:
        end_partes.append(f'{cidade}/{estado}' if (cidade and estado) else (cidade or estado))
    if cep:
        end_partes.append(f'CEP {cep}')
    if end_partes:
        linhas.append('##1f4cd## *Endereço:* ' + ' - '.join(end_partes))
    # Plano
    id_plano = lead.get('id_plano_rp')
    if id_plano:
        plano_lbl = _PLANO_TITULO.get(id_plano, 'Plano selecionado')
        linhas.append(f'##1f4e6## *Plano:* {plano_lbl}')

    corpo = '\n'.join(linhas) if linhas else '_(alguns dados básicos)_'
    return (
        '##1f44b## Vi que você já tinha um cadastro em andamento com a gente!\n\n'
        '*Já tenho estes dados seus:*\n'
        f'{corpo}\n\n'
        'Você quer *continuar de onde parou* ou *começar de novo*?\n\n'
        '*1)* ##25b6## Continuar de onde parei\n'
        '*2)* ##1f504## Começar de novo\n\n'
        '_Responda com o número da opção._'
    )
