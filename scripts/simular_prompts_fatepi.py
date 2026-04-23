"""
Simula os prompts corrigidos do fluxo v3 da FATEPI contra casos reais que falharam.

Uso:
  export OPENAI_API_KEY="sk-..."
  python scripts/simular_prompts_fatepi.py

Ou com .env:
  echo 'OPENAI_API_KEY=sk-...' > .env.openai_test
  OPENAI_API_KEY=$(cat .env.openai_test | cut -d= -f2) python scripts/simular_prompts_fatepi.py

Custo aproximado: ~20 chamadas × gpt-4o-mini ≈ $0.002 total.
"""
import os
import json
from openai import OpenAI

API_KEY = os.environ.get('OPENAI_API_KEY', '').strip()
if not API_KEY:
    print("ERRO: defina OPENAI_API_KEY no env antes de rodar")
    exit(1)

client = OpenAI(api_key=API_KEY)
MODEL = 'gpt-4o-mini'


# ============================================================================
# PROMPTS — ATUAL vs NOVO
# ============================================================================

PROMPT_CURSO_ATUAL = """Cursos validos: Direito, Sistemas de Informacao, Psicologia, Enfermagem, Fisioterapia, Administracao, Ciencias Contabeis, Pedagogia, Fonoaudiologia, Educacao Fisica, Servico Social."""

PROMPT_CURSO_NOVO = """Classifique a mensagem do candidato como "curso_valido" ou "curso_invalido".

CURSOS OFERECIDOS (aceite QUALQUER forma de referência a eles):
- Direito
- Sistemas de Informação (variações: "SI", "sistemas", "informática")
- Psicologia (variações: "pscologia", "psicolgia", "psico")
- Enfermagem (variações: "enfermagem", "enfermeira")
- Fisioterapia (variações: "fisio")
- Administração (variações: "adm", "administrativo")
- Ciências Contábeis (variações: "contábeis", "contabilidade")
- Pedagogia
- Fonoaudiologia (variações: "fono", "fonoaudiológa", "fonoaudiologa")
- Educação Física (variações: "ed física", "edf")
- Serviço Social (variações: "serviço social", "social")

REGRAS DE CLASSIFICAÇÃO:
1. IGNORE caixa (maiúsculas/minúsculas)
2. IGNORE acentos (fonoaudióloga = fonoaudiologa = fonoaudiologia)
3. ACEITE erros comuns de digitação
4. ACEITE perguntas indiretas: "queria saber de X", "tem X?", "vocês fazem X?", "me interesso por X"
5. ACEITE múltiplas respostas: se candidato disse "quero direito ou psicologia" é curso_valido

Se a mensagem contém referência CLARA a pelo menos um dos cursos da lista → curso_valido.
Se é dúvida genérica SEM mencionar curso específico → curso_invalido.
Se é nome de curso que NÃO está na lista acima (ex: "Medicina") → curso_invalido.

Responda APENAS: "curso_valido" ou "curso_invalido" """


FALLBACK_527_ATUAL = """Voce e o Pedro, consultor da FATEPI/FAESPI.
O candidato fez uma pergunta ou comentario fora do esperado.
Informacoes uteis:
- Localizacao: Rua Primeiro de Maio, 2235, Bairro Primavera, Teresina - PI
- Contatos: (86) 2107-2200 | contato@faespi.com.br
- Horario: segunda a sexta, 18h30 as 21h40"""

FALLBACK_527_NOVO = """Você é Pedro, consultor da FATEPI/FAESPI.

O candidato fez uma pergunta ou comentário fora do esperado durante a pergunta de qual curso tem interesse.
A pergunta original era: "Qual curso você tem interesse?"

Cursos oferecidos: Direito, Sistemas de Informação, Psicologia, Enfermagem, Fisioterapia, Administração, Ciências Contábeis, Pedagogia, Fonoaudiologia, Educação Física, Serviço Social.

Informações úteis:
- Endereço: Rua Primeiro de Maio, 2235, Bairro Primavera, Teresina - PI
- Contato: (86) 2107-2200 | contato@faespi.com.br
- Horário: segunda a sexta, 18h30 às 21h40
- Ingresso: ENEM, Prova Online ou Transferência

SUA AÇÃO:
1. Responda brevemente a dúvida dele (máximo 2 frases)
2. OBRIGATORIAMENTE termine perguntando qual curso ele tem interesse dentre os oferecidos

Regras:
- Texto puro, sem markdown
- No máximo 3 frases no total
- SEMPRE termine com a lista de cursos e a pergunta"""


# ============================================================================
# CASOS REAIS QUE FALHARAM
# ============================================================================

CASOS_CURSO = [
    ("Psicologia", "curso_valido (esta na lista)"),
    ("PSICOLOGIA", "curso_valido (caixa alta)"),
    ("psicologia", "curso_valido (minusculo)"),
    ("Pscologia", "curso_valido (typo)"),
    ("Fonoaudiologia", "curso_valido (esta na lista)"),
    ("FONOAUDIOLOGIA", "curso_valido"),
    ("Fonoaudiólogia", "curso_valido (typo com acento)"),
    ("Queria saber de fonoaudióloga", "curso_valido (pergunta indireta)"),
    ("Direito", "curso_valido"),
    ("quero fazer enfermagem", "curso_valido"),
    ("Medicina", "curso_invalido (nao oferecido)"),
    ("Engenharia", "curso_invalido"),
    ("qual o valor?", "curso_invalido (duvida generica)"),
]

CASOS_FALLBACK = [
    "Vocês têm EAD?",
    "Qual o valor da mensalidade?",
    "Onde fica?",
    "Vi na propaganda que tem",
]


def chamar_llm(system_prompt, user_msg, temperature=0):
    r = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=temperature,
        max_tokens=200,
    )
    return r.choices[0].message.content.strip()


def simular_classificador():
    print("=" * 80)
    print("A. CLASSIFICADOR DE CURSO — Prompt ATUAL vs NOVO")
    print("=" * 80)

    atual_ok = novo_ok = 0
    for entrada, esperado in CASOS_CURSO:
        esperado_label = esperado.split(' ')[0]
        try:
            r_atual = chamar_llm(PROMPT_CURSO_ATUAL, entrada)
        except Exception as e:
            r_atual = f"ERRO: {e}"
        try:
            r_novo = chamar_llm(PROMPT_CURSO_NOVO, entrada)
        except Exception as e:
            r_novo = f"ERRO: {e}"

        # Normaliza output (pode vir "curso_valido" ou texto maior)
        n_atual = 'curso_valido' if 'curso_valido' in r_atual.lower() else ('curso_invalido' if 'curso_invalido' in r_atual.lower() else r_atual[:30])
        n_novo = 'curso_valido' if 'curso_valido' in r_novo.lower() else ('curso_invalido' if 'curso_invalido' in r_novo.lower() else r_novo[:30])

        marca_atual = 'OK' if n_atual == esperado_label else 'ERR'
        marca_novo = 'OK' if n_novo == esperado_label else 'ERR'
        if marca_atual == 'OK': atual_ok += 1
        if marca_novo == 'OK': novo_ok += 1

        print(f"\n  INPUT: {entrada[:50]!r}")
        print(f"    esperado: {esperado}")
        print(f"    ATUAL   [{marca_atual}]: {n_atual}")
        print(f"    NOVO    [{marca_novo}]: {n_novo}")

    print()
    print(f"RESULTADO: ATUAL {atual_ok}/{len(CASOS_CURSO)} | NOVO {novo_ok}/{len(CASOS_CURSO)}")
    return atual_ok, novo_ok


def simular_fallback():
    print()
    print("=" * 80)
    print("B. FALLBACK 527 — Prompt ATUAL vs NOVO (termina com pergunta de curso?)")
    print("=" * 80)

    for msg in CASOS_FALLBACK:
        print(f"\n  CANDIDATO: {msg!r}")
        try:
            r_atual = chamar_llm(FALLBACK_527_ATUAL, msg, temperature=0.3)
        except Exception as e:
            r_atual = f"ERRO: {e}"
        try:
            r_novo = chamar_llm(FALLBACK_527_NOVO, msg, temperature=0.3)
        except Exception as e:
            r_novo = f"ERRO: {e}"

        atual_pergunta = any(c.lower() in r_atual.lower() for c in ['qual curso', 'que curso', 'direito, psicologia', 'interesse'])
        novo_pergunta = any(c.lower() in r_novo.lower() for c in ['qual curso', 'que curso', 'direito, psicologia', 'interesse'])

        print(f"    ATUAL [{'OK' if atual_pergunta else 'ERR'}]: {r_atual[:200]}")
        print(f"    NOVO  [{'OK' if novo_pergunta else 'ERR'}]: {r_novo[:200]}")


if __name__ == '__main__':
    print(f"Usando modelo: {MODEL}\n")
    simular_classificador()
    simular_fallback()
    print("\nSimulacao concluida.")
