"""Anonimizador de PII (LGPD) pra texto livre de atendimento.

Extraido de `apps/integracoes/management/commands/extrair_historico_matrix.py`
pra ser reusado por outros consumidores (ex: engine de automacao) sem duplicar
a logica. Comportamento identico ao original: mascara nome/cpf/telefone/email
do contato especifico, mais um passthrough generico via regex pra qualquer
PII que apareca no texto (digitado pelo proprio cliente, de terceiros, etc).
"""
import re

_CPF_RE = re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b')
_CNPJ_RE = re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b')
_TEL_RE = re.compile(r'\b(?:\+?55)?\s?\(?\d{2}\)?\s?\d{4,5}-?\d{4}\b')
_EMAIL_RE = re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b')


def construir_anonimizador(contato):
    """Cria funcao que anonimiza texto removendo PII do contato.

    Substitui ocorrencias de nome/cpf/telefone/email pelo placeholder
    correspondente. Tambem aplica regex pra capturar PII generico que
    apareca no texto (CPFs digitados, emails de terceiros, telefones).

    `contato`: dict com chaves `contato`/`nome`, `cpf`, `telefone`, `email`
    (formato das linhas do Matrix Brasil, tanto em `relAtAnalitico` quanto
    no bloco `contato` de `/rest/v1/atendimento`).
    """
    contato = contato or {}
    nome = (contato.get('contato') or contato.get('nome') or '').strip()
    cpf = re.sub(r'\D', '', str(contato.get('cpf') or ''))
    telefone = re.sub(r'\D', '', str(contato.get('telefone') or ''))
    email = (contato.get('email') or '').strip().lower()

    # Componentes do nome (so substitui token >= 3 chars, evita preposicoes)
    nome_partes = [p for p in re.split(r'\s+', nome) if len(p) >= 3]

    def _anon(texto):
        if not texto:
            return texto
        t = str(texto)
        # Anonimiza nome especifico do contato (palavra-a-palavra, case-insensitive)
        for parte in nome_partes:
            t = re.sub(rf'\b{re.escape(parte)}\b', '[NOME]', t, flags=re.IGNORECASE)
        # CPF/telefone especificos do contato
        if cpf and len(cpf) >= 11:
            t = t.replace(cpf, '[CPF]')
        if telefone and len(telefone) >= 10:
            t = t.replace(telefone, '[TELEFONE]')
        if email:
            t = re.sub(re.escape(email), '[EMAIL]', t, flags=re.IGNORECASE)
        # Generico — qualquer PII que aparecer no texto
        t = _CPF_RE.sub('[CPF]', t)
        t = _CNPJ_RE.sub('[CNPJ]', t)
        t = _TEL_RE.sub('[TELEFONE]', t)
        t = _EMAIL_RE.sub('[EMAIL]', t)
        return t

    return _anon


def anonimizar_texto(texto, contato=None):
    """Atalho pra anonimizar um texto avulso (sem manter a funcao/closure).

    Sem `contato`, aplica so as regras genericas (CPF/CNPJ/telefone/email
    digitados no texto). Pra anonimizar varias mensagens do mesmo contato,
    prefira `construir_anonimizador(contato)` uma vez e reusar a funcao.
    """
    return construir_anonimizador(contato)(texto)
