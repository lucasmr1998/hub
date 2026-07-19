"""Passo 2 — Extração multi-campo da mensagem do cliente.

Analisa a resposta livre e tenta extrair TODOS os campos que o cliente
mencionou (não só o da etapa atual), além de detectar se o cliente fez
uma pergunta. Os campos extraídos depois passam pela validação
determinística (CPF dígito, ViaCEP, etc) — a IA só sugere, o núcleo valida.
"""
from __future__ import annotations

import logging

from src.conversacional.cliente_llm import chat_json
from src.conversacional.config import conv_config

logger = logging.getLogger(__name__)


# Catálogo de campos que a IA pode extrair de uma fala do cliente.
# Mantido enxuto e alinhado aos campos do lead que o núcleo sabe validar.
CATALOGO_CAMPOS = """
- cpf_cnpj: CPF (11 dígitos) ou CNPJ do titular
- nome_razaosocial: nome completo da pessoa
- data_nascimento: data de nascimento (formato DD/MM/AAAA)
- email: e-mail
- tipo_imovel: "casa" ou "empresa"
- tipo_residencia: "casa_terrea", "apartamento" ou "condominio"
- cep: CEP (8 dígitos)
- numero_residencia: número da casa/imóvel
- ponto_referencia: complemento/ponto de referência do endereço
- id_plano_rp: plano escolhido. 1649 = "620 mega/620MB", 1648 = "1 giga/1GB/1000 mega"
- id_dia_vencimento: dia de vencimento da fatura (1, 5, 15 ou 20)
- turno_instalacao: "manha" ou "tarde"
"""

_SYSTEM_EXTRAIR = (
    "Você analisa mensagens de clientes de uma provedora de internet no "
    "WhatsApp, durante um cadastro de venda. Responda SEMPRE com JSON puro.\n\n"
    "Sua tarefa tem 2 partes:\n"
    "1. EXTRAIR os campos que o cliente informou na mensagem (pode ser mais "
    "de um, ou nenhum). Use APENAS os campos do catálogo abaixo.\n"
    "2. DETECTAR se o cliente fez alguma PERGUNTA (dúvida sobre plano, preço, "
    "fidelidade, instalação, etc).\n\n"
    f"CATÁLOGO DE CAMPOS:\n{CATALOGO_CAMPOS}\n"
    "REGRAS:\n"
    "- Extraia só o que o cliente REALMENTE disse. NÃO invente.\n"
    "- Para id_plano_rp e id_dia_vencimento, devolva o NÚMERO do id.\n"
    "- Datas no formato DD/MM/AAAA.\n"
    "- Se o cliente respondeu apenas um número de opção (ex: '1', '2'), "
    "coloque em 'opcao_numerica' (o sistema mapeia conforme a etapa atual).\n"
    "- 'tem_pergunta' = true sempre que o cliente FIZER UMA PERGUNTA ou pedir "
    "algo (ex: 'é possível?', 'pode?', 'quanto custa?', 'como funciona?', "
    "'tem fidelidade?', 'dá pra parcelar?'). Coloque a dúvida em "
    "'pergunta_texto'.\n"
    "- 'campo_corrigir': se o cliente quer MUDAR/CORRIGIR um dado que já "
    "informou antes (ex: 'quero mudar o cep', 'o email tá errado', 'troca o "
    "número', 'na verdade é outro plano'), devolva o NOME do campo do "
    "catálogo a corrigir (ex: 'cep', 'email', 'numero_residencia'). Senão null.\n"
    "- 'confirmacao': SE a pergunta atual for um SIM/NÃO (confirmar plano, "
    "confirmar dados, confirmar endereço, continuar/recomeçar), interprete a "
    "resposta do cliente: 'sim' (concordou: 'com certeza', 'claro', 'pode', "
    "'aceito', 'isso', etc) ou 'nao' (recusou: 'não', 'quero ver outro', "
    "'trocar', 'começar de novo', etc). Senão, null.\n"
    "- 'intencao': 'responder' (respondeu a pergunta atual), 'perguntar' (fez "
    "uma dúvida), 'corrigir' (quer mudar um dado anterior), 'ambos' (respondeu "
    "E perguntou), 'saudacao' (oi/olá), 'outro'.\n\n"
    "Formato de saída:\n"
    "{\n"
    '  "campos": { "campo": "valor", ... },   // só os encontrados\n'
    '  "opcao_numerica": "1" | null,\n'
    '  "confirmacao": "sim" | "nao" | null,\n'
    '  "tem_pergunta": true|false,\n'
    '  "pergunta_texto": "a dúvida do cliente, ou vazio",\n'
    '  "campo_corrigir": "cep" | null,\n'
    '  "intencao": "responder" | "perguntar" | "corrigir" | "ambos" | "saudacao" | "outro"\n'
    "}"
)


def analisar_mensagem(
    mensagem: str,
    *,
    campo_atual: str = '',
    pergunta_atual: str = '',
) -> dict:
    """Extrai campos + detecta pergunta. Fallback seguro (dict vazio)."""
    vazio = {
        'campos': {}, 'opcao_numerica': None, 'confirmacao': None,
        'tem_pergunta': False, 'pergunta_texto': '', 'campo_corrigir': None,
        'intencao': 'outro',
    }
    if not conv_config.PASSO2_EXTRACAO or not (mensagem or '').strip():
        return vazio

    user = (
        f'Etapa atual do cadastro: {campo_atual or "—"}\n'
        f'Pergunta que o bot acabou de fazer: "{pergunta_atual or "—"}"\n\n'
        f'Mensagem do cliente: """{mensagem}"""'
    )
    res = chat_json(_SYSTEM_EXTRAIR, user, temperatura=0.1, max_tokens=400)
    if not res:
        return vazio

    # Normaliza/saneia
    conf = res.get('confirmacao')
    if conf not in ('sim', 'nao'):
        conf = None
    campo_corrigir = (res.get('campo_corrigir') or '').strip() or None
    return {
        'campos': res.get('campos') or {},
        'opcao_numerica': res.get('opcao_numerica'),
        'confirmacao': conf,
        'tem_pergunta': bool(res.get('tem_pergunta')),
        'pergunta_texto': (res.get('pergunta_texto') or '').strip(),
        'campo_corrigir': campo_corrigir,
        'intencao': res.get('intencao') or 'outro',
    }
