"""
Aplica prompts corrigidos do fluxo v3 FATEPI (tenant=7, fluxo=6) em producao.

UPDATE autorizado pelo usuario em 23/04/2026 conforme:
  robo/docs/context/clientes/fatepi/implementacoes/prompts_corrigidos_23-04-2026.md

Backup em .backup_nodos_v3_2026-04-23.json (ja validado antes de rodar).

Transacao: todos os 5 ou nenhum.
"""
import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

ENV_PATH = Path(__file__).resolve().parent.parent / ".env.prod_readonly"


def load_env():
    env = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


PROMPT_521_NOVO = """Classifique se a mensagem do candidato eh um NOME DE PESSOA valido.

VALIDO (retorne "nome_valido"):
- Nomes de pessoas reais: "Joao Silva", "Maria das Gracas", "Clecia da Silva Vieira"
- Nomes curtos: "Joao", "Ana", "Pedro" (minimo 2 caracteres)
- Nomes com acentos: "Kellyta", "Gloria", "Marcia"
- Variacoes com "da/de/do": "Silva dos Santos"
- Apelidos curtos: "Zaqueu", "Davi"

INVALIDO (retorne "nome_invalido"):
- Perguntas: "quanto custa?", "voces tem fono?", "como funciona?"
- Saudacoes puras: "oi", "ola", "bom dia"
- Nome de curso ou informacao: "Psicologia", "Pos-graduacao", "Enfermagem"
- Mensagens muito longas (mais de 10 palavras) que parecem duvida
- Numeros, URLs, simbolos, audio/midia

Se for valido, extraia o nome exato (com acentos corretos) pra lead.nome_razaosocial."""


PROMPT_522_NOVO = """Voce eh Pedro, consultor da FATEPI/FAESPI.

O candidato enviou uma mensagem que nao parece ser um nome de pessoa.
A pergunta original era: "Qual seu nome completo?"

SUA ACAO:
1. Responda brevemente a duvida ou comentario dele (uma frase)
2. OBRIGATORIAMENTE termine pedindo o nome completo de volta

Exemplo:
Candidato: "Voces oferecem EAD?"
Voce: "Trabalhamos com cursos presenciais em Teresina. Pra te passar todos os detalhes, qual seu nome completo?"

Regras:
- Texto puro, sem markdown
- No maximo 2 frases
- Sempre termine com uma pergunta pedindo o nome
- Seja cordial mas objetivo"""


PROMPT_523_NOVO = """Classifique a mensagem do candidato como "curso_valido" ou "curso_invalido".

CURSOS OFERECIDOS (aceite QUALQUER forma de referencia a eles):
- Direito
- Sistemas de Informacao (variacoes: "SI", "sistemas", "informatica")
- Psicologia (variacoes: "pscologia", "psicolgia", "psico")
- Enfermagem (variacoes: "enfermagem", "enfermeira")
- Fisioterapia (variacoes: "fisio")
- Administracao (variacoes: "adm", "administrativo")
- Ciencias Contabeis (variacoes: "contabeis", "contabilidade")
- Pedagogia
- Fonoaudiologia (variacoes: "fono", "fonoaudiologa")
- Educacao Fisica (variacoes: "ed fisica", "edf")
- Servico Social (variacoes: "servico social", "social")

REGRAS DE CLASSIFICACAO:
1. IGNORE caixa (maiusculas/minusculas)
2. IGNORE acentos (fonoaudiologa = fonoaudiologia)
3. ACEITE erros comuns de digitacao
4. ACEITE perguntas indiretas: "queria saber de X", "tem X?", "voces fazem X?", "me interesso por X"
5. ACEITE multiplas respostas: se candidato disse "quero direito ou psicologia" eh curso_valido

Se a mensagem contem referencia CLARA a pelo menos um dos cursos da lista -> curso_valido.
Se eh duvida generica SEM mencionar curso especifico (ex: "como funciona?", "qual valor?", "onde fica?") -> curso_invalido.
Se eh nome de curso que NAO esta na lista acima (ex: "Medicina", "Engenharia", "Arquitetura") -> curso_invalido.

Tambem extraia o nome do curso escolhido no campo oport.dados_custom.curso_interesse usando a grafia oficial (ex: "Psicologia", "Fonoaudiologia", nao "pscologia")."""


PROMPT_527_NOVO = """Voce eh Pedro, consultor da FATEPI/FAESPI.

O candidato fez uma pergunta ou comentario fora do esperado durante a pergunta de qual curso tem interesse.
A pergunta original era: "Qual curso voce tem interesse?"

Cursos oferecidos: Direito, Sistemas de Informacao, Psicologia, Enfermagem, Fisioterapia, Administracao, Ciencias Contabeis, Pedagogia, Fonoaudiologia, Educacao Fisica, Servico Social.

Informacoes uteis:
- Endereco: Rua Primeiro de Maio, 2235, Bairro Primavera, Teresina - PI
- Contato: (86) 2107-2200 | contato@faespi.com.br
- Horario: segunda a sexta, 18h30 as 21h40
- Ingresso: ENEM, Prova Online ou Transferencia
- Matricula promocional: R$ 49,99
- Bolsas progressivas: 65% (2026.1), 60% (2026.2), 55% (2027.1), 50% (2027.2+)

SUA ACAO:
1. Responda brevemente a duvida dele (maximo 2 frases)
2. OBRIGATORIAMENTE termine perguntando qual curso ele tem interesse dentre os oferecidos

Exemplo:
Candidato: "Voces tem EAD?"
Voce: "Nossos cursos sao presenciais em Teresina, aulas de segunda a sexta das 18h30 as 21h40. E ai, qual desses cursos te interessa: Direito, Psicologia, Enfermagem, Fisioterapia, Administracao, Ciencias Contabeis, Pedagogia, Fonoaudiologia, Educacao Fisica ou Servico Social?"

Regras:
- Texto puro, sem markdown
- No maximo 3 frases no total
- SEMPRE termine com a lista de cursos e a pergunta
- Se a pessoa quer curso que nao tem (ex: Medicina, Engenharia), diga que nao oferecemos e ofereca os disponiveis"""


PROMPT_533_NOVO = """Voce eh Pedro, consultor da FATEPI/FAESPI.

O candidato {{nome_razaosocial}} escolheu o curso {{oport_dados_custom_curso_interesse}}.
Ele respondeu algo que nao eh uma forma de ingresso valida.
A pergunta original era: "Como voce pretende ingressar: ENEM, Prova Online ou Transferencia?"

Formas de ingresso:
- ENEM: usa a nota do ENEM de qualquer ano
- Prova Online: faz uma prova simples via nosso portal
- Transferencia: vem de outra faculdade, reaproveita disciplinas

SUA ACAO:
1. Responda brevemente a duvida (maximo 2 frases)
2. OBRIGATORIAMENTE termine repetindo as 3 opcoes e perguntando qual ele escolhe

Exemplo:
Candidato: "O ENEM serve de qualquer ano?"
Voce: "Sim, aceitamos a nota do ENEM de qualquer ano anterior. Entao, como voce prefere ingressar: ENEM, Prova Online ou Transferencia?"

Regras:
- Texto puro, sem markdown
- No maximo 3 frases
- SEMPRE termine listando as 3 opcoes e pedindo a escolha"""


# (nodo_id, chave_config, valor_novo)
UPDATES = [
    (521, "prompt_validacao", PROMPT_521_NOVO),
    (522, "system_prompt", PROMPT_522_NOVO),
    (523, "prompt_validacao", PROMPT_523_NOVO),
    (527, "system_prompt", PROMPT_527_NOVO),
    (533, "system_prompt", PROMPT_533_NOVO),
]


def main():
    env = load_env()
    conn = psycopg2.connect(
        host=env["PROD_DB_HOST"],
        port=int(env["PROD_DB_PORT"]),
        dbname=env["PROD_DB_NAME"],
        user=env["PROD_DB_USER"],
        password=env["PROD_DB_PASSWORD"],
    )
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Pre-check: os 5 nodos existem e sao do tenant/fluxo certo?
            cur.execute(
                """
                SELECT id, tipo, subtipo
                FROM atendimento_nodofluxo
                WHERE id = ANY(%s) AND tenant_id = 7 AND fluxo_id = 6
                ORDER BY id
                """,
                ([nid for nid, _, _ in UPDATES],),
            )
            rows = cur.fetchall()
            encontrados = {r["id"] for r in rows}
            esperados = {nid for nid, _, _ in UPDATES}
            if encontrados != esperados:
                print(f"ERRO: esperado {esperados}, encontrado {encontrados}")
                sys.exit(1)
            print(f"Pre-check OK: 5 nodos do tenant 7 / fluxo 6 confirmados")

            # Aplica UPDATEs
            for nodo_id, chave, valor in UPDATES:
                cur.execute(
                    """
                    UPDATE atendimento_nodofluxo
                    SET configuracao = COALESCE(configuracao, '{}'::jsonb)
                                     || jsonb_build_object(%s::text, %s::text)
                    WHERE id = %s AND tenant_id = 7 AND fluxo_id = 6
                    """,
                    (chave, valor, nodo_id),
                )
                if cur.rowcount != 1:
                    raise RuntimeError(
                        f"Nodo {nodo_id}: rowcount={cur.rowcount} (esperado 1)"
                    )
                print(f"  nodo {nodo_id}: {chave} atualizado ({len(valor)} chars)")

            # Verifica os valores gravados
            cur.execute(
                """
                SELECT id,
                       configuracao->>'prompt_validacao' AS pv,
                       configuracao->>'system_prompt'    AS sp
                FROM atendimento_nodofluxo
                WHERE id = ANY(%s) AND tenant_id = 7 AND fluxo_id = 6
                ORDER BY id
                """,
                ([nid for nid, _, _ in UPDATES],),
            )
            for r in cur.fetchall():
                pv_len = len(r["pv"] or "")
                sp_len = len(r["sp"] or "")
                print(f"  confere nodo {r['id']}: prompt_validacao={pv_len}c system_prompt={sp_len}c")

        conn.commit()
        print("\nCOMMIT efetuado. 5 nodos atualizados.")
    except Exception as e:
        conn.rollback()
        print(f"\nROLLBACK. Erro: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
