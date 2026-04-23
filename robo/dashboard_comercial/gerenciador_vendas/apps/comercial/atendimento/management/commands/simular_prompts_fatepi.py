"""
Simula prompts ATUAL vs NOVO do fluxo v3 da FATEPI, usando as mesmas
funcoes do engine (com a key da IntegracaoAPI do banco).

Uso no servidor:
    python manage.py simular_prompts_fatepi

A key NUNCA sai do container — o engine lê direto do banco como faz em producao.

Custo: ~34 chamadas x gpt-4o-mini ≈ $0.003 total.
"""
from django.core.management.base import BaseCommand


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

REGRAS:
1. IGNORE caixa
2. IGNORE acentos
3. ACEITE typos
4. ACEITE perguntas indiretas: "queria saber de X", "tem X?", "vocês fazem X?"

Se contém referência CLARA a pelo menos um curso da lista → curso_valido.
Se é dúvida genérica SEM mencionar curso → curso_invalido.
Se é curso NÃO oferecido (Medicina, Engenharia) → curso_invalido.

Responda APENAS: "curso_valido" ou "curso_invalido"."""


FALLBACK_527_ATUAL = """Voce e o Pedro, consultor da FATEPI/FAESPI.
O candidato fez uma pergunta ou comentario fora do esperado.
Informacoes uteis:
- Localizacao: Rua Primeiro de Maio, 2235, Bairro Primavera, Teresina - PI
- Contatos: (86) 2107-2200 | contato@faespi.com.br
- Horario: segunda a sexta, 18h30 as 21h40"""

FALLBACK_527_NOVO = """Você é Pedro, consultor da FATEPI/FAESPI.

O candidato fez uma pergunta fora do esperado durante a pergunta de qual curso tem interesse.
A pergunta original era: "Qual curso você tem interesse?"

Cursos oferecidos: Direito, Sistemas de Informação, Psicologia, Enfermagem, Fisioterapia, Administração, Ciências Contábeis, Pedagogia, Fonoaudiologia, Educação Física, Serviço Social.

Informações:
- Endereço: Rua Primeiro de Maio, 2235, Bairro Primavera, Teresina - PI
- Contato: (86) 2107-2200 | contato@faespi.com.br
- Horário: seg-sex, 18h30 às 21h40
- Ingresso: ENEM, Prova Online ou Transferência

AÇÃO:
1. Responda brevemente a dúvida (máx 2 frases)
2. OBRIGATÓRIO terminar perguntando qual curso dentre os oferecidos

Regras: texto puro, máx 3 frases total, SEMPRE terminar com a pergunta de curso."""


CASOS_CURSO = [
    ("Psicologia", "curso_valido"),
    ("PSICOLOGIA", "curso_valido"),
    ("psicologia", "curso_valido"),
    ("Pscologia", "curso_valido"),
    ("Fonoaudiologia", "curso_valido"),
    ("FONOAUDIOLOGIA", "curso_valido"),
    ("Fonoaudiólogia", "curso_valido"),
    ("Queria saber de fonoaudióloga", "curso_valido"),
    ("Direito", "curso_valido"),
    ("quero fazer enfermagem", "curso_valido"),
    ("Medicina", "curso_invalido"),
    ("Engenharia", "curso_invalido"),
    ("qual o valor?", "curso_invalido"),
]

CASOS_FALLBACK = [
    "Vocês têm EAD?",
    "Qual o valor da mensalidade?",
    "Onde fica?",
    "Vi na propaganda que tem",
]


class Command(BaseCommand):
    help = 'Simula prompts ATUAL vs NOVO do fluxo v3 FATEPI (classificador + fallback)'

    def add_arguments(self, parser):
        parser.add_argument('--integracao-id', type=int, default=4,
                          help='ID da IntegracaoAPI (default 4 = OpenAI FATEPI)')
        parser.add_argument('--tenant-id', type=int, default=7,
                          help='ID do tenant (default 7 = Fatepi/Faespi)')
        parser.add_argument('--modelo', default='gpt-4o-mini',
                          help='Modelo LLM (default gpt-4o-mini)')

    def handle(self, *args, **opts):
        from apps.integracoes.models import IntegracaoAPI
        from apps.comercial.atendimento.engine import _chamar_llm_simples

        integracao = IntegracaoAPI.all_tenants.filter(
            id=opts['integracao_id'], tenant_id=opts['tenant_id'], ativa=True
        ).first()
        if not integracao:
            self.stderr.write(f"IntegracaoAPI id={opts['integracao_id']} tenant={opts['tenant_id']} nao encontrada")
            return

        modelo = opts['modelo']
        self.stdout.write(f"Modelo: {modelo}  |  IntegracaoAPI: {integracao.nome}\n")

        def chamar(system_prompt, user_msg):
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_msg},
            ]
            return _chamar_llm_simples(integracao, modelo, messages) or '(vazio)'

        # ===== CLASSIFICADOR =====
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('A. CLASSIFICADOR DE CURSO')
        self.stdout.write('=' * 80)

        atual_ok = novo_ok = 0
        for entrada, esperado in CASOS_CURSO:
            try:
                r_atual = chamar(PROMPT_CURSO_ATUAL, entrada)
            except Exception as e:
                r_atual = f'ERRO: {e}'
            try:
                r_novo = chamar(PROMPT_CURSO_NOVO, entrada)
            except Exception as e:
                r_novo = f'ERRO: {e}'

            n_atual = 'curso_valido' if 'curso_valido' in r_atual.lower() else ('curso_invalido' if 'curso_invalido' in r_atual.lower() else r_atual[:30])
            n_novo = 'curso_valido' if 'curso_valido' in r_novo.lower() else ('curso_invalido' if 'curso_invalido' in r_novo.lower() else r_novo[:30])

            ok_atual = n_atual == esperado
            ok_novo = n_novo == esperado
            if ok_atual: atual_ok += 1
            if ok_novo: novo_ok += 1

            self.stdout.write(f"\n  INPUT: {entrada!r}")
            self.stdout.write(f"    esperado: {esperado}")
            self.stdout.write(f"    ATUAL [{'OK' if ok_atual else 'ERR'}]: {n_atual}")
            self.stdout.write(f"    NOVO  [{'OK' if ok_novo else 'ERR'}]: {n_novo}")

        self.stdout.write(f"\n>> Placar: ATUAL {atual_ok}/{len(CASOS_CURSO)}  |  NOVO {novo_ok}/{len(CASOS_CURSO)}")

        # ===== FALLBACK 527 =====
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write('B. FALLBACK 527 (termina com pergunta de curso?)')
        self.stdout.write('=' * 80)

        for msg in CASOS_FALLBACK:
            self.stdout.write(f"\n  CANDIDATO: {msg!r}")
            try:
                r_atual = chamar(FALLBACK_527_ATUAL, msg)
            except Exception as e:
                r_atual = f'ERRO: {e}'
            try:
                r_novo = chamar(FALLBACK_527_NOVO, msg)
            except Exception as e:
                r_novo = f'ERRO: {e}'

            tem_pergunta_atual = any(t in r_atual.lower() for t in ['qual curso', 'que curso', 'interesse'])
            tem_pergunta_novo = any(t in r_novo.lower() for t in ['qual curso', 'que curso', 'interesse'])

            self.stdout.write(f"    ATUAL [{'OK' if tem_pergunta_atual else 'ERR'}]: {r_atual[:250]}")
            self.stdout.write(f"    NOVO  [{'OK' if tem_pergunta_novo else 'ERR'}]: {r_novo[:250]}")

        self.stdout.write(self.style.SUCCESS('\nSimulacao concluida.'))
