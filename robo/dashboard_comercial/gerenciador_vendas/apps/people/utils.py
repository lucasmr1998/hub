"""
Normalizacao de dado de pessoa.

Tudo que entra no cadastro passa por aqui antes de encostar no banco. Dedup so
funciona sobre dado normalizado: "123.456.789-01" e "12345678901" sao a mesma
pessoa, e "(86) 99999-8888" e "5586999998888" tambem.

Python puro, sem Django, pra poder ser testado sozinho.
"""
import re
import unicodedata


DDI_PADRAO = '55'


def normalizar_cpf(valor):
    """
    So digitos, ou None.

    None e nao string vazia de proposito: a unique de CPF por tenant depende de
    ausencia ser NULL, porque no Postgres NULL nao colide com NULL. Com '' a
    segunda pessoa sem CPF quebraria.
    """
    digitos = re.sub(r'\D', '', valor or '')
    return digitos if len(digitos) == 11 else None


def cpf_tem_digito_valido(cpf):
    """
    Confere os dois digitos verificadores.

    Serve pra marcar o cadastro pra revisao, NAO pra bloquear. Bloquear no
    formulario publico faz a pessoa desistir e o RH cadastrar por fora, o que
    reintroduz a duplicata que o dedup existe pra impedir. CPF errado numa fila
    de revisao e melhor que cadastro paralelo.
    """
    digitos = normalizar_cpf(cpf)
    if digitos is None:
        return False
    if digitos == digitos[0] * 11:
        return False

    for tamanho in (9, 10):
        soma = sum(int(digitos[i]) * (tamanho + 1 - i) for i in range(tamanho))
        resto = (soma * 10) % 11
        esperado = 0 if resto == 10 else resto
        if esperado != int(digitos[tamanho]):
            return False
    return True


def normalizar_e164(valor, ddi_padrao=DDI_PADRAO):
    """
    Telefone em E.164 sem o mais. Ex: 5586999998888.

    Numero brasileiro sem DDI ganha o 55. Numero que ja parece internacional
    passa direto, porque a spec de origem cita operacao fora do Brasil.
    """
    digitos = re.sub(r'\D', '', valor or '')
    if not digitos:
        return ''

    # 10 (fixo com DDD) ou 11 (celular com DDD): falta o DDI
    if len(digitos) in (10, 11):
        return f'{ddi_padrao}{digitos}'

    return digitos


def normalizar_nome(valor):
    """Tira espaco das pontas e colapsa espaco repetido no meio."""
    return re.sub(r'\s+', ' ', (valor or '').strip())


def chave_nome(valor):
    """
    Nome reduzido a uma chave comparavel: sem acento, minusculo, espaco unico.

    Usada so no match fraco do dedup. "José da Silva" e "jose da  silva" viram a
    mesma chave, mas isso nunca reaproveita cadastro sozinho: gera conflito pra
    um humano decidir.
    """
    nome = normalizar_nome(valor).lower()
    sem_acento = unicodedata.normalize('NFKD', nome)
    return ''.join(c for c in sem_acento if not unicodedata.combining(c))


def normalizar_email(valor):
    return (valor or '').strip().lower()


def normalizar_estado(valor):
    return (valor or '').strip().upper()[:2]


def normalizar_cep(valor):
    digitos = re.sub(r'\D', '', valor or '')
    if len(digitos) != 8:
        return (valor or '').strip()
    return f'{digitos[:5]}-{digitos[5:]}'


def mascarar_cpf(cpf):
    """CPF pra log e telemetria, sem expor o documento inteiro."""
    digitos = normalizar_cpf(cpf)
    if digitos is None:
        return ''
    return f'***.***.**{digitos[-3:-2]}-{digitos[-2:]}'
