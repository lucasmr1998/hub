"""
Cria o fluxo de atendimento da FATEPI v2 completo e organizado.
Replica todas as etapas do fluxo original (v3) substituindo os IA Respondedores
individuais por um Agente IA central com tools especialistas.

Uso:
    python manage.py criar_fluxo_fatepi --settings=gerenciador_vendas.settings_local_pg
"""
from django.core.management.base import BaseCommand
from apps.sistema.models import Tenant
from apps.comercial.atendimento.models import (
    FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento
)
from apps.integracoes.models import IntegracaoAPI


TABELA_PRECOS = """Tabela de precos:
Direito: Integral R$ 1.500 | Vestibular R$ 199 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 525
Sistemas de Informacao: Integral R$ 1.000 | Vestibular R$ 149 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 350
Pedagogia: Integral R$ 840 | Vestibular R$ 139 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 294
Fonoaudiologia: Integral R$ 1.380 | Vestibular R$ 169 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 483
Psicologia: Integral R$ 1.630 | Vestibular R$ 199 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 570,50
Fisioterapia: Integral R$ 1.380 | Vestibular R$ 169 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 483
Educacao Fisica: Integral R$ 840 | Vestibular R$ 139 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 294
Enfermagem: Integral R$ 1.380 | Vestibular R$ 169 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 483
Administracao: Integral R$ 890 | Vestibular R$ 139 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 311,50
Ciencias Contabeis: Integral R$ 890 | Vestibular R$ 139 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 311,50
Servico Social: Integral R$ 840 | Vestibular R$ 139 | ENEM R$ 49,99 | Transferencia R$ 99,99 | Mensalidade R$ 294

Bolsas progressivas: 65% em 2026.1, 60% em 2026.2, 55% em 2027.1, 50% a partir de 2027.2."""

CURSOS_LISTA = "Direito, Sistemas de Informacao, Psicologia, Enfermagem, Fisioterapia, Administracao, Ciencias Contabeis, Pedagogia, Fonoaudiologia, Educacao Fisica, Servico Social"


class Command(BaseCommand):
    help = 'Cria o fluxo FATEPI v2 completo e organizado'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, default='fatepi',
                            help='Slug ou parte do nome do tenant')

    def handle(self, *args, **options):
        filtro = options['tenant'].lower()
        tenant = Tenant.objects.filter(nome__icontains=filtro).first()
        if not tenant:
            self.stderr.write(f'Tenant "{filtro}" nao encontrado.')
            return
        self.stdout.write(f'Tenant: {tenant.nome} (ID: {tenant.pk})')

        integracao = IntegracaoAPI.objects.filter(
            tenant=tenant, tipo__in=['openai', 'groq', 'anthropic', 'google_ai']
        ).first()
        ia_id = str(integracao.pk) if integracao else ''
        ia_id_int = integracao.pk if integracao else None
        self.stdout.write(f'Integracao IA: {integracao.nome} ({integracao.tipo})' if integracao else 'SEM IA')

        # Criar fluxo
        fluxo = FluxoAtendimento.objects.create(
            tenant=tenant,
            nome='FATEPI v2 - Qualificacao Completa',
            descricao='Fluxo completo: nome, curso, ingresso, valores, decisao, matricula. Agente IA centralizado para fallbacks.',
            tipo_fluxo='qualificacao',
            status='ativo',
            modo_fluxo=True,
            ativo=True,
            canal='qualquer',
            criado_por='sistema',
        )
        self.stdout.write(f'Fluxo: {fluxo.nome} (ID: {fluxo.pk})')

        n = {}  # nodes dict

        # ================================================================
        # ROW 1 (y=300): Fluxo principal
        # ROW 2 (y=550): Agente IA (fallback central)
        # ROW 3 (y=300, x>1800): Fluxo pos-decisao
        # ================================================================

        # --- 1. INICIO ---
        n['inicio'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='entrada', subtipo='inicio_fluxo',
            configuracao={'canal': 'qualquer'},
            pos_x=100, pos_y=300, ordem=1,
        )

        # --- 2. PERGUNTA NOME ---
        n['q_nome'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
            configuracao={
                'titulo': 'Ola! Sou o Pedro, consultor de ingresso da FATEPI/FAESPI. Para eu te passar os detalhes da bolsa, qual seu nome completo?',
                'espera_resposta': True,
                'salvar_em': 'nome_razaosocial',
                'validacao': 'texto',
                'max_tentativas': 3,
                'pular_se_preenchido': True,
                'integracao_ia_id': ia_id,
                'ia_acao': 'extrair',
                'ia_modelo': 'gpt-4o-mini',
                'ia_campos_extrair': [
                    {'nome': 'nome_razaosocial', 'descricao': 'Nome completo da pessoa', 'tipo': 'string'},
                ],
                'ia_salvar_no_lead': True,
                'prompt_validacao': 'Extraia o nome completo da pessoa. Se a mensagem nao for um nome de pessoa, retorne vazio.',
            },
            pos_x=350, pos_y=300, ordem=2,
        )

        # --- 3. PERGUNTA CURSO ---
        n['q_curso'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
            configuracao={
                'titulo': f'Prazer! Qual curso voce tem interesse? Nossos cursos: {CURSOS_LISTA}.',
                'espera_resposta': True,
                'validacao': 'texto',
                'max_tentativas': 3,
                'integracao_ia_id': ia_id,
                'ia_acao': 'classificar_extrair',
                'ia_modelo': 'gpt-4o-mini',
                'ia_categorias': ['curso_valido', 'curso_invalido'],
                'ia_variavel_saida': 'validacao_curso',
                'ia_campos_extrair': [
                    {'nome': 'oport.dados_custom.curso_interesse', 'descricao': 'Curso escolhido pelo candidato', 'tipo': 'string'},
                ],
                'ia_salvar_no_lead': True,
                'prompt_validacao': f'Cursos validos: {CURSOS_LISTA}. Se o candidato escolheu um curso valido, classifique como curso_valido. Se escolheu um curso que nao existe ou respondeu algo irrelevante, classifique como curso_invalido.',
            },
            pos_x=600, pos_y=300, ordem=3,
        )

        # --- 4. CONDICAO CURSO VALIDO ---
        n['cond_curso'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='condicao', subtipo='campo_check',
            configuracao={
                'campo': 'var.validacao_curso',
                'operador': 'igual',
                'valor': 'curso_valido',
            },
            pos_x=900, pos_y=300, ordem=4,
        )

        # --- 5. CURSO INVALIDO (re-ask) ---
        n['q_curso_invalido'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
            configuracao={
                'titulo': f'Desculpe, nao temos esse curso. Nossos cursos: {CURSOS_LISTA}. Qual te interessa?',
                'espera_resposta': True,
                'validacao': 'texto',
                'integracao_ia_id': ia_id,
                'ia_acao': 'classificar_extrair',
                'ia_modelo': 'gpt-4o-mini',
                'ia_categorias': ['curso_valido', 'curso_invalido'],
                'ia_variavel_saida': 'validacao_curso',
                'ia_campos_extrair': [
                    {'nome': 'oport.dados_custom.curso_interesse', 'descricao': 'Curso escolhido pelo candidato', 'tipo': 'string'},
                ],
                'ia_salvar_no_lead': True,
                'prompt_validacao': f'Cursos validos: {CURSOS_LISTA}.',
            },
            pos_x=900, pos_y=500, ordem=5,
        )

        # --- 6. CRIAR OPORTUNIDADE ---
        n['criar_oport'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='acao', subtipo='criar_oportunidade',
            configuracao={
                'titulo': '{{lead_nome}} - {{oport_dados_custom_curso_interesse}}',
            },
            pos_x=1150, pos_y=300, ordem=6,
        )

        # --- 7. MOVER ESTAGIO → qualificacao ---
        n['mover_qualificacao'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='acao', subtipo='mover_estagio',
            configuracao={'estagio': 'qualificacao'},
            pos_x=1400, pos_y=300, ordem=7,
        )

        # --- 8. PERGUNTA FORMA DE INGRESSO ---
        n['q_ingresso'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
            configuracao={
                'titulo': 'O curso e presencial, de segunda a sexta, das 18h30 as 21h40. Como voce pretende ingressar: Nota do ENEM, Prova Online ou Transferencia?',
                'espera_resposta': True,
                'validacao': 'texto',
                'integracao_ia_id': ia_id,
                'ia_acao': 'extrair',
                'ia_modelo': 'gpt-4o-mini',
                'ia_campos_extrair': [
                    {'nome': 'oport.dados_custom.forma_ingresso', 'descricao': 'Forma de ingresso: ENEM, Prova Online ou Transferencia', 'tipo': 'string'},
                ],
                'ia_salvar_no_lead': True,
                'prompt_validacao': 'Formas de ingresso validas: ENEM, Prova Online, Transferencia. Se a mensagem nao for sobre forma de ingresso, retorne vazio.',
            },
            pos_x=1650, pos_y=300, ordem=8,
        )

        # --- 9. MOVER ESTAGIO → qualificado ---
        n['mover_qualificado'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='acao', subtipo='mover_estagio',
            configuracao={'estagio': 'qualificado'},
            pos_x=1900, pos_y=300, ordem=9,
        )

        # --- 10. IA RESPONDEDOR (valores + pergunta decisao) ---
        n['ia_valores'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='ia_respondedor', subtipo='ia_respondedor',
            configuracao={
                'integracao_ia_id': ia_id_int,
                'modelo': 'gpt-4o-mini',
                'incluir_historico': True,
                'max_historico': 10,
                'system_prompt': (
                    'Voce e o Pedro, consultor da FATEPI/FAESPI.\n\n'
                    'O candidato {{nome_razaosocial}} escolheu {{oport_dados_custom_curso_interesse}} '
                    'e vai ingressar via {{oport_dados_custom_forma_ingresso}}.\n\n'
                    'Apresente os valores usando a coluna correta (ENEM, Vestibular/Prova Online, ou Transferencia).\n'
                    'Apresente: Valor Integral, Matricula Promocional e Mensalidade.\n'
                    'Bolsas progressivas: 65%% em 2026.1, 60%% em 2026.2, 55%% em 2027.1, 50%% a partir de 2027.2.\n\n'
                    'No final pergunte: Se garantirmos essa condicao hoje, voce consegue finalizar sua matricula?\n\n'
                    f'{TABELA_PRECOS}\n\n'
                    'Texto puro sem markdown.'
                ),
            },
            pos_x=2150, pos_y=300, ordem=10,
        )

        # --- 11. Q DECISAO (classificador silencioso) ---
        n['q_decisao'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
            configuracao={
                'titulo': '',
                'espera_resposta': False,
                'validacao': 'texto',
                'integracao_ia_id': ia_id,
                'ia_acao': 'classificar',
                'ia_modelo': 'gpt-4o-mini',
                'ia_categorias': ['sim', 'nao', 'duvida'],
                'ia_variavel_saida': 'decisao_matricula',
                'prompt_validacao': 'O candidato respondeu sobre fazer a matricula. Classifique a intencao: sim (quer matricular), nao (nao quer), duvida (ainda tem duvidas).',
            },
            pos_x=2400, pos_y=300, ordem=11,
        )

        # --- 12. CONDICAO DECISAO ---
        n['cond_decisao'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='condicao', subtipo='campo_check',
            configuracao={
                'campo': 'var.decisao_matricula',
                'operador': 'igual',
                'valor': 'sim',
            },
            pos_x=2650, pos_y=300, ordem=12,
        )

        # --- 13. MOVER ESTAGIO → agendado ---
        n['mover_agendado'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='acao', subtipo='mover_estagio',
            configuracao={'estagio': 'agendado'},
            pos_x=2900, pos_y=200, ordem=13,
        )

        # --- 14. Q PIX (pagamento) ---
        n['q_pix'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
            configuracao={
                'titulo': 'Excelente! Para garantir sua vaga, realize o pagamento pelo PIX abaixo:\n\nPIX: 00020126580014br.gov.bcb.pix013652d3c4c3-6213-459a-bd59-ac47480dd1945204000053039865802BR5925GILCIFRAN VIEIRA DE SOUSA6008TERESINA62070503***630427D9\n\nAssim que realizar o pagamento, me envie o comprovante!',
                'espera_resposta': True,
                'validacao': 'texto',
            },
            pos_x=3150, pos_y=200, ordem=14,
        )

        # --- 15. MOVER ESTAGIO → matriculado ---
        n['mover_matriculado'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='acao', subtipo='mover_estagio',
            configuracao={'estagio': 'matriculado'},
            pos_x=3400, pos_y=200, ordem=15,
        )

        # --- 16. FINALIZAR (sucesso) ---
        n['fim_sucesso'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='finalizacao', subtipo='finalizar',
            configuracao={
                'score': 10,
                'mensagem_final': 'Obrigado! Sua matricula foi registrada. Bem-vindo a FATEPI/FAESPI!',
            },
            pos_x=3650, pos_y=200, ordem=16,
        )

        # --- 17. FINALIZAR (nao quis) ---
        n['fim_nao'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='finalizacao', subtipo='finalizar',
            configuracao={
                'mensagem_final': 'Quando quiser retomar, estamos a disposicao. Ate logo!',
            },
            pos_x=2900, pos_y=500, ordem=17,
        )

        # --- 18. AGENTE IA (fallback central) ---
        n['agente'] = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='ia_agente', subtipo='ia_agente',
            configuracao={
                'integracao_ia_id': ia_id,
                'modelo': 'gpt-4o-mini',
                'system_prompt': (
                    'Voce e o Pedro, assistente virtual da FATEPI/FAESPI (Faculdade de Tecnologia de Teresina).\n'
                    'O candidato fez uma pergunta ou comentario durante o processo de inscricao.\n'
                    'Responda de forma clara, objetiva e educada. Texto puro sem markdown.\n'
                    'Use as tools disponiveis para responder com precisao sobre o tema.'
                ),
                'max_turnos': 10,
                'mensagem_timeout': 'Desculpe, nao consegui processar. Vamos continuar com a inscricao.',
                'tools_customizadas': [
                    {
                        'nome': 'consultor_comercial',
                        'descricao': 'Responde duvidas sobre valores, mensalidades, bolsas, descontos e formas de pagamento dos cursos',
                        'prompt': (
                            'Voce e o consultor comercial da FATEPI/FAESPI.\n'
                            'Responda duvidas sobre valores e condicoes comerciais.\n\n'
                            f'{TABELA_PRECOS}\n\n'
                            'Formas de ingresso e taxas:\n'
                            '- ENEM: R$ 49,99 (nota minima 400 pontos)\n'
                            '- Prova Online/Vestibular: R$ 139 a R$ 199 conforme curso\n'
                            '- Transferencia: R$ 99,99\n\n'
                            'Pagamento: boleto, cartao, PIX.\n'
                            'Texto puro sem markdown.'
                        ),
                    },
                    {
                        'nome': 'info_academica',
                        'descricao': 'Responde sobre cursos, horarios, grade curricular, duracao, localizacao e estrutura da faculdade',
                        'prompt': (
                            'Voce e o coordenador academico da FATEPI/FAESPI.\n'
                            f'Cursos disponiveis: {CURSOS_LISTA}.\n'
                            'Todos presenciais, noturno: segunda a sexta, 18h30 as 21h40.\n'
                            'Duracoes: Direito/Psicologia/Enfermagem/Fisioterapia (5 anos), demais (4 anos).\n'
                            'Localizacao: Rua Primeiro de Maio, 2235, Bairro Primavera, Teresina - PI.\n'
                            'Estrutura: laboratorios, biblioteca, quadra, estacionamento, cantina.\n'
                            'Contato: (86) 2107-2200 | contato@faespi.com.br\n'
                            'Texto puro sem markdown.'
                        ),
                    },
                    {
                        'nome': 'suporte_geral',
                        'descricao': 'Responde sobre processo seletivo, documentos necessarios, prazos e informacoes gerais da FATEPI',
                        'prompt': (
                            'Voce e o atendente da FATEPI/FAESPI.\n'
                            'Documentos para matricula: RG, CPF, comprovante de residencia, historico escolar, foto 3x4.\n'
                            'ENEM: envie o print da nota (minimo 400 pontos).\n'
                            'Prova Online: acesse prova.fatepifaespi.com.br, resultado em 48h.\n'
                            'Transferencia: envie historico academico + ementa das disciplinas.\n'
                            'Horario de atendimento: segunda a sexta, 8h as 21h.\n'
                            'Contato: (86) 2107-2200 | contato@faespi.com.br\n'
                            'Texto puro sem markdown.'
                        ),
                    },
                ],
                'tools_habilitadas': [],
            },
            pos_x=600, pos_y=600, ordem=18,
        )

        self.stdout.write(f'  {len(n)} nodos criados')

        # ================================================================
        # CONEXOES
        # ================================================================
        conexoes = [
            # Fluxo principal
            ('inicio', 'q_nome', 'default'),
            ('q_nome', 'q_curso', 'true'),
            ('q_curso', 'cond_curso', 'true'),
            ('cond_curso', 'criar_oport', 'true'),         # curso valido
            ('cond_curso', 'q_curso_invalido', 'false'),    # curso invalido
            ('q_curso_invalido', 'cond_curso', 'true'),     # volta pra condicao
            ('criar_oport', 'mover_qualificacao', 'default'),
            ('mover_qualificacao', 'q_ingresso', 'default'),
            ('q_ingresso', 'mover_qualificado', 'true'),
            ('mover_qualificado', 'ia_valores', 'default'),
            ('ia_valores', 'q_decisao', 'default'),
            ('q_decisao', 'cond_decisao', 'true'),

            # Decisao: sim → matricula
            ('cond_decisao', 'mover_agendado', 'true'),
            ('mover_agendado', 'q_pix', 'default'),
            ('q_pix', 'mover_matriculado', 'true'),
            ('mover_matriculado', 'fim_sucesso', 'default'),

            # Decisao: nao → encerrar
            ('cond_decisao', 'fim_nao', 'false'),

            # Fallbacks → Agente IA central
            ('q_nome', 'agente', 'false'),
            ('q_curso', 'agente', 'false'),
            ('q_curso_invalido', 'agente', 'false'),
            ('q_ingresso', 'agente', 'false'),
        ]

        for origem_key, destino_key, tipo_saida in conexoes:
            ConexaoNodoAtendimento.objects.create(
                tenant=tenant, fluxo=fluxo,
                nodo_origem=n[origem_key],
                nodo_destino=n[destino_key],
                tipo_saida=tipo_saida,
            )

        self.stdout.write(f'  {len(conexoes)} conexoes criadas')

        # Desativar fluxo anterior
        FluxoAtendimento.objects.filter(
            tenant=tenant, status='ativo'
        ).exclude(pk=fluxo.pk).update(status='inativo')
        self.stdout.write('  Fluxos anteriores desativados')

        self.stdout.write(self.style.SUCCESS(
            f'\nFluxo FATEPI v2 criado! ID: {fluxo.pk}\n'
            f'Editor: /suporte/configuracoes/fluxos/{fluxo.pk}/editor/\n\n'
            f'Estrutura:\n'
            f'  Inicio → Q Nome → Q Curso → Cond Curso Valido?\n'
            f'    ├─ Sim → Criar Oport → Mover qualificacao → Q Ingresso\n'
            f'    └─ Nao → Q "Nao temos" → volta\n'
            f'  Q Ingresso → Mover qualificado → IA Valores (apresenta precos)\n'
            f'  → Q Decisao (classifica) → Cond Quer Matricular?\n'
            f'    ├─ Sim → Mover agendado → Q PIX → Mover matriculado → Fim\n'
            f'    └─ Nao → Fim\n'
            f'  Fallbacks: Q Nome/Curso/Ingresso → Agente IA (3 tools) → volta pra pergunta'
        ))
