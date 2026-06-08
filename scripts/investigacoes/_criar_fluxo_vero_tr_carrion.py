"""
Cria primeira versao do fluxo de atendimento Vero no tenant tr-carrion (prod).

Inclui:
- 5 cidades de cobertura exemplo (CidadeViabilidade)
- 1 IntegracaoAPI OpenAI (placeholder de api_key)
- 1 FluxoAtendimento 'Atendimento Vero - V1' (status=rascunho)
- ~15 nodos cobrindo o fluxo de 10 etapas (com IA pra extrair/classificar)
- Conexoes entre nodos

Idempotente: aborta se fluxo com mesmo nome ja existir no tenant.
"""
from django.db import transaction
from apps.sistema.models import Tenant
from apps.integracoes.models import IntegracaoAPI
from apps.comercial.viabilidade.models import CidadeViabilidade
from apps.comercial.atendimento.models import (
    FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento
)

TENANT_SLUG = 'tr-carrion'
FLUXO_NOME = 'Atendimento Vero - V1'

# ============================================================================
# 1. Tenant
# ============================================================================
try:
    tenant = Tenant.objects.get(slug=TENANT_SLUG)
except Tenant.DoesNotExist:
    print(f"ERRO: tenant '{TENANT_SLUG}' nao existe. Aborte.")
    raise SystemExit(1)

if FluxoAtendimento.objects.filter(tenant=tenant, nome=FLUXO_NOME).exists():
    print(f"ERRO: fluxo '{FLUXO_NOME}' ja existe no tenant. Aborte.")
    raise SystemExit(1)

print(f"[OK] Tenant: {tenant.nome} (id={tenant.id})")


# ============================================================================
# 2. Cidades de cobertura Vero (exemplos — user ajusta depois)
# ============================================================================
CIDADES_VERO = [
    ('Bauru', 'SP'),
    ('Marília', 'SP'),
    ('Sorocaba', 'SP'),
    ('Campinas', 'SP'),
    ('São Paulo', 'SP'),
]

with transaction.atomic():
    cidades_criadas = []
    for nome, uf in CIDADES_VERO:
        c, criado = CidadeViabilidade.objects.get_or_create(
            tenant=tenant, cidade=nome, estado=uf, cep=None,
            defaults={'ativo': True, 'observacao': 'Cobertura Vero (seed inicial)'},
        )
        if criado:
            cidades_criadas.append(f"{nome}/{uf}")
    print(f"[OK] Cidades cobertura: {len(cidades_criadas)} criadas ({', '.join(cidades_criadas) or 'nenhuma nova'})")

    # ========================================================================
    # 3. IntegracaoAPI OpenAI placeholder
    # ========================================================================
    integ_openai, criado = IntegracaoAPI.objects.get_or_create(
        tenant=tenant, tipo='openai', nome='OpenAI (TR Carrion)',
        defaults={
            'api_key': 'sk-COLOQUE-SUA-CHAVE-AQUI',
            'client_id': '-', 'client_secret': '-',
            'username': '-', 'password': '-',
            'ativa': True,
        },
    )
    print(f"[OK] IntegracaoAPI OpenAI: id={integ_openai.id} {'(criada)' if criado else '(ja existia)'}")
    print(f"     -> ATENCAO: preencha a chave OpenAI real em /configuracoes/integracoes/{integ_openai.id}/")

    ia_id = integ_openai.id  # usar como integracao_ia_id nos nodos

    # ========================================================================
    # 4. FluxoAtendimento
    # ========================================================================
    fluxo = FluxoAtendimento.objects.create(
        tenant=tenant,
        nome=FLUXO_NOME,
        descricao='Fluxo de qualificacao de leads Vero — V1 (rascunho). Captura CEP, valida cobertura, apresenta planos, coleta dados/docs e gera oportunidade.',
        tipo_fluxo='qualificacao',
        status='rascunho',
        ativo=True,
        canal='whatsapp',
        criado_por='seed_vero_v1',
    )
    print(f"[OK] Fluxo criado: id={fluxo.id}, status=rascunho")

    # ========================================================================
    # 5. Nodos
    # ========================================================================
    n = {}

    # --- 1. INICIO ---
    n['inicio'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='entrada', subtipo='inicio_fluxo',
        configuracao={'canal': 'whatsapp'},
        pos_x=100, pos_y=300, ordem=1,
    )

    # --- 2. SAUDACAO ---
    n['saudacao'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': 'Oi! Tudo bem? 😊\nSou a assistente virtual da Vero.\nVou te ajudar a consultar planos de internet para o seu endereço.\n\nMe manda seu CEP, por favor, para eu consultar sua região.',
            'espera_resposta': True,
            'salvar_em': 'var.cep',
            'integracao_ia_id': ia_id,
            'ia_acao': 'classificar_extrair',
            'ia_modelo': 'gpt-4o-mini',
            'ia_categorias': ['cep_valido', 'cep_invalido'],
            'ia_variavel_saida': 'cep_status',
            'ia_campos_extrair': [
                {'nome': 'var.cep', 'descricao': 'CEP brasileiro no formato 00000-000', 'tipo': 'string'},
            ],
            'prompt_validacao': 'Extraia o CEP brasileiro (8 digitos, com ou sem traco). Se nao for CEP, classifique como cep_invalido.',
        },
        pos_x=350, pos_y=300, ordem=2,
    )

    # --- 3. VERIFICA COBERTURA (IA classifica usando lista do prompt) ---
    cidades_str = ', '.join(f'{c}/{u}' for c, u in CIDADES_VERO)
    n['check_cobertura'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='ia_classificador', subtipo='ia_classificador',
        configuracao={
            'integracao_ia_id': ia_id,
            'modelo': 'gpt-4o-mini',
            'categorias': ['cobertura_ok', 'fora_cobertura'],
            'variavel_saida': 'cobertura_status',
            'system_prompt': (
                f'A Vero atende as seguintes cidades: {cidades_str}.\n'
                'Dado o CEP {{var.cep}}, classifique:\n'
                '- cobertura_ok: se o CEP corresponde a uma das cidades acima\n'
                '- fora_cobertura: caso contrario\n\n'
                'Use seu conhecimento de CEPs brasileiros para determinar a cidade.'
            ),
        },
        pos_x=600, pos_y=300, ordem=3,
    )

    # --- 4. COND COBERTURA ---
    n['cond_cobertura'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='condicao', subtipo='campo_check',
        configuracao={
            'campo': 'var.cobertura_status',
            'operador': 'igual',
            'valor': 'cobertura_ok',
        },
        pos_x=850, pos_y=300, ordem=4,
    )

    # --- 5. APRESENTA PLANOS (IA respondedor) ---
    planos_lista = (
        '1. 550 Mega + Wi-Fi 6 — R$ 113,90/mês\n'
        '2. 550 Mega + Chip 10GB — R$ 118,90/mês\n'
        '3. 750 Mega + Wi-Fi 6 — R$ 122,90/mês\n'
        '4. 800 Mega + YouTube Premium — R$ 134,90/mês\n'
        '5. 800 Mega + Max — R$ 134,90/mês\n'
        '6. 800 Mega + Telecine — R$ 134,90/mês\n'
        '7. 800 Mega + Disney Padrão + Chip 20GB — R$ 139,90/mês\n'
        '8. 800 Mega + Globoplay Canais Premium + HBO Max + Chip 60GB — R$ 149,90/mês\n'
        '9. 800 Mega + Premiere — R$ 150,00/mês\n'
        '10. 800 Mega + Disney Plus — R$ 155,00/mês'
    )
    n['apresenta_planos'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='ia_respondedor', subtipo='ia_respondedor',
        configuracao={
            'integracao_ia_id': ia_id,
            'modelo': 'gpt-4o-mini',
            'system_prompt': (
                'Voce e a assistente virtual da Vero. Seja calorosa e direta.\n'
                'Envie esta mensagem:\n\n'
                '"Boa notícia 😊 Sua região aparece dentro da área de atendimento da Vero. '
                'A disponibilidade final será confirmada pelo endereço completo, mas já vou te mostrar os planos disponíveis:\n\n'
                f'{planos_lista}\n\n'
                'Me responde com o número do plano que você quer 😊"\n\n'
                'Texto puro, sem markdown.'
            ),
        },
        pos_x=1100, pos_y=200, ordem=5,
    )

    # --- 6. ESCOLHA PLANO ---
    n['escolha_plano'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': '',
            'espera_resposta': True,
            'integracao_ia_id': ia_id,
            'ia_acao': 'extrair',
            'ia_modelo': 'gpt-4o-mini',
            'ia_campos_extrair': [
                {'nome': 'oport.dados_custom.plano_escolhido', 'descricao': 'Numero do plano de 1 a 10', 'tipo': 'string'},
            ],
            'ia_salvar_no_lead': True,
            'prompt_validacao': 'Extraia o numero do plano escolhido (1 a 10). Se nao for numero valido, retorne vazio.',
        },
        pos_x=1350, pos_y=200, ordem=6,
    )

    # --- 7. CONFIRMA ESCOLHA + PEDE ENDERECO ---
    n['pede_endereco'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': (
                'Perfeito! 😊\n\n'
                'Agora preciso do seu endereço completo para seguir com a conferência.\n\n'
                'Me manda assim, por favor:\n'
                'Rua:\n'
                'Número:\n'
                'Bairro:\n'
                'Cidade:\n'
                'Complemento (se tiver):'
            ),
            'espera_resposta': True,
            'integracao_ia_id': ia_id,
            'ia_acao': 'extrair',
            'ia_modelo': 'gpt-4o-mini',
            'ia_campos_extrair': [
                {'nome': 'oport.dados_custom.endereco_rua', 'descricao': 'Nome da rua', 'tipo': 'string'},
                {'nome': 'oport.dados_custom.endereco_numero', 'descricao': 'Numero da casa/apto', 'tipo': 'string'},
                {'nome': 'oport.dados_custom.endereco_bairro', 'descricao': 'Bairro', 'tipo': 'string'},
                {'nome': 'oport.dados_custom.endereco_cidade', 'descricao': 'Cidade', 'tipo': 'string'},
                {'nome': 'oport.dados_custom.endereco_complemento', 'descricao': 'Complemento (opcional)', 'tipo': 'string'},
            ],
            'ia_salvar_no_lead': True,
            'prompt_validacao': 'Extraia os campos do endereco residencial brasileiro.',
        },
        pos_x=1600, pos_y=200, ordem=7,
    )

    # --- 8. PEDE DADOS CADASTRAIS ---
    n['pede_dados'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': (
                'Perfeito, obrigado 😊\n\n'
                'Agora preciso de alguns dados para iniciar sua solicitação:\n\n'
                '1. Nome completo\n'
                '2. E-mail\n'
                '3. Melhor dia de vencimento da fatura\n'
                '4. Deseja débito automático? (Sim ou não)'
            ),
            'espera_resposta': True,
            'integracao_ia_id': ia_id,
            'ia_acao': 'extrair',
            'ia_modelo': 'gpt-4o-mini',
            'ia_campos_extrair': [
                {'nome': 'nome_razaosocial', 'descricao': 'Nome completo do cliente', 'tipo': 'string'},
                {'nome': 'email', 'descricao': 'Email do cliente', 'tipo': 'string'},
                {'nome': 'oport.dados_custom.dia_vencimento', 'descricao': 'Dia de vencimento da fatura (1 a 31)', 'tipo': 'string'},
                {'nome': 'oport.dados_custom.debito_automatico', 'descricao': 'sim ou nao', 'tipo': 'string'},
            ],
            'ia_salvar_no_lead': True,
            'prompt_validacao': 'Extraia nome, email, dia de vencimento e preferencia por debito automatico.',
        },
        pos_x=1850, pos_y=200, ordem=8,
    )

    # --- 9. LGPD CONSENT ---
    n['lgpd'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': (
                'Antes de seguir, preciso da sua autorização 🔐\n\n'
                'Os dados que você enviar (incluindo documentos) serão usados '
                'pela Vero somente para validação e contratação do plano. '
                'Posso prosseguir? (Sim ou não)'
            ),
            'espera_resposta': True,
            'integracao_ia_id': ia_id,
            'ia_acao': 'classificar',
            'ia_modelo': 'gpt-4o-mini',
            'ia_categorias': ['lgpd_sim', 'lgpd_nao'],
            'ia_variavel_saida': 'lgpd_status',
            'prompt_validacao': 'Classifique se o cliente autorizou (lgpd_sim) ou nao (lgpd_nao) o uso dos dados.',
        },
        pos_x=2100, pos_y=200, ordem=9,
    )

    # --- 10. COND LGPD ---
    n['cond_lgpd'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='condicao', subtipo='campo_check',
        configuracao={
            'campo': 'var.lgpd_status',
            'operador': 'igual',
            'valor': 'lgpd_sim',
        },
        pos_x=2350, pos_y=200, ordem=10,
    )

    # --- 11. PEDE DOCS ---
    n['pede_docs'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': (
                'Perfeito! Para finalizar, vou precisar das fotos do seu documento (RG ou CNH).\n\n'
                'Pode me enviar a foto da frente, e depois a foto do verso, por favor 😊'
            ),
            'espera_resposta': True,
            'aguarda_anexo': True,
        },
        pos_x=2600, pos_y=200, ordem=11,
    )

    # --- 12. RESUMO + CONFIRMACAO ---
    n['resumo'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='ia_respondedor', subtipo='ia_respondedor',
        configuracao={
            'integracao_ia_id': ia_id,
            'modelo': 'gpt-4o-mini',
            'system_prompt': (
                'Voce e a assistente virtual da Vero. Gere um resumo dos dados coletados '
                'em formato amigavel e pergunte se esta tudo certo.\n\n'
                'Dados:\n'
                '- Nome: {{nome_razaosocial}}\n'
                '- Email: {{email}}\n'
                '- Endereço: {{oport_dados_custom_endereco_rua}}, {{oport_dados_custom_endereco_numero}}, '
                '{{oport_dados_custom_endereco_bairro}}, {{oport_dados_custom_endereco_cidade}}\n'
                '- Plano: numero {{oport_dados_custom_plano_escolhido}}\n'
                '- Vencimento dia {{oport_dados_custom_dia_vencimento}}\n'
                '- Débito automático: {{oport_dados_custom_debito_automatico}}\n\n'
                'Pergunte ao final: "Está tudo certo? Posso seguir? (Sim/Não)"\n'
                'Texto puro, sem markdown.'
            ),
        },
        pos_x=2850, pos_y=200, ordem=12,
    )

    # --- 13. CLASSIFICA CONFIRMACAO ---
    n['confirma'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': '',
            'espera_resposta': True,
            'integracao_ia_id': ia_id,
            'ia_acao': 'classificar',
            'ia_modelo': 'gpt-4o-mini',
            'ia_categorias': ['confirma_sim', 'confirma_nao'],
            'ia_variavel_saida': 'confirma_status',
            'prompt_validacao': 'Classifique se o cliente confirmou os dados (confirma_sim) ou nao (confirma_nao).',
        },
        pos_x=3100, pos_y=200, ordem=13,
    )

    # --- 14. COND CONFIRMACAO ---
    n['cond_confirma'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='condicao', subtipo='campo_check',
        configuracao={
            'campo': 'var.confirma_status',
            'operador': 'igual',
            'valor': 'confirma_sim',
        },
        pos_x=3350, pos_y=200, ordem=14,
    )

    # --- 15. CRIA OPORTUNIDADE ---
    n['criar_oport'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='acao', subtipo='criar_oportunidade',
        configuracao={
            'titulo': 'Vero - {{nome_razaosocial}} - Plano {{oport_dados_custom_plano_escolhido}}',
        },
        pos_x=3600, pos_y=150, ordem=15,
    )

    # --- 16. HANDOFF CONSULTOR ---
    n['handoff'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='transferir_humano', subtipo='transferir_humano',
        configuracao={
            'titulo': 'Perfeito 👍 Vou encaminhar sua solicitação para um consultor finalizar o cadastro. Em breve alguém entra em contato!',
            'motivo': 'lead_qualificado_vero',
        },
        pos_x=3850, pos_y=150, ordem=16,
    )

    # --- 17. HANDOFF FORA COBERTURA ---
    n['handoff_fora'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='transferir_humano', subtipo='transferir_humano',
        configuracao={
            'titulo': (
                'No momento, não consegui localizar sua região na lista de cobertura automática.\n'
                'Vou encaminhar para um consultor verificar alternativas disponíveis para você 😊'
            ),
            'motivo': 'fora_cobertura_vero',
        },
        pos_x=1100, pos_y=500, ordem=17,
    )

    # --- 18. HANDOFF LGPD RECUSADA ---
    n['handoff_lgpd'] = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='transferir_humano', subtipo='transferir_humano',
        configuracao={
            'titulo': 'Sem problemas. Vou passar pra um consultor te ajudar pessoalmente 😊',
            'motivo': 'lgpd_recusada_vero',
        },
        pos_x=2350, pos_y=400, ordem=18,
    )

    print(f"[OK] Nodos criados: {len(n)} ({', '.join(n.keys())})")

    # ========================================================================
    # 6. Conexoes
    # ========================================================================
    def conectar(origem_key, destino_key, tipo_saida='default'):
        return ConexaoNodoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo,
            nodo_origem=n[origem_key], nodo_destino=n[destino_key],
            tipo_saida=tipo_saida,
        )

    conexoes = [
        ('inicio', 'saudacao'),
        ('saudacao', 'check_cobertura'),
        ('check_cobertura', 'cond_cobertura'),
        ('cond_cobertura', 'apresenta_planos', 'true'),
        ('cond_cobertura', 'handoff_fora', 'false'),
        ('apresenta_planos', 'escolha_plano'),
        ('escolha_plano', 'pede_endereco'),
        ('pede_endereco', 'pede_dados'),
        ('pede_dados', 'lgpd'),
        ('lgpd', 'cond_lgpd'),
        ('cond_lgpd', 'pede_docs', 'true'),
        ('cond_lgpd', 'handoff_lgpd', 'false'),
        ('pede_docs', 'resumo'),
        ('resumo', 'confirma'),
        ('confirma', 'cond_confirma'),
        ('cond_confirma', 'criar_oport', 'true'),
        ('cond_confirma', 'pede_dados', 'false'),  # volta pra ajustar dados
        ('criar_oport', 'handoff'),
    ]

    for c in conexoes:
        conectar(*c)

    print(f"[OK] Conexoes criadas: {len(conexoes)}")


# ============================================================================
# RESUMO FINAL
# ============================================================================
print()
print("=" * 70)
print("FLUXO VERO V1 CRIADO COM SUCESSO")
print("=" * 70)
print(f"Tenant:        {tenant.nome} (slug={tenant.slug})")
print(f"Fluxo ID:      {fluxo.id}")
print(f"Status:        rascunho (nao dispara automaticamente)")
print(f"Nodos:         {NodoFluxoAtendimento.objects.filter(fluxo=fluxo).count()}")
print(f"Conexoes:      {ConexaoNodoAtendimento.objects.filter(fluxo=fluxo).count()}")
print(f"Cidades:       {CidadeViabilidade.objects.filter(tenant=tenant).count()} cadastradas")
print(f"Integracao IA: OpenAI id={ia_id} (CHAVE PLACEHOLDER!)")
print()
print("PROXIMOS PASSOS:")
print("1. Editar fluxo:")
print(f"   https://app.hubtrix.com.br/comercial/atendimento/fluxos/{fluxo.id}/editor/")
print(f"2. Configurar chave OpenAI real:")
print(f"   https://app.hubtrix.com.br/configuracoes/integracoes/{ia_id}/")
print(f"3. Testar no simulador (botao no canto superior direito do editor)")
print("=" * 70)
