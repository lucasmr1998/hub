"""
Reaplica configuracoes de IA nos nodos do fluxo Vero V1 (id=23).
Necessario quando o editor zera os campos extras (ia_acao, integracao_ia_id, etc).

Estrategia: identificar cada nodo pelo titulo/subtipo e re-aplicar config completa.
ia_id = 15 (integracao OpenAI da TR Carrion).
"""
from django.db import transaction
from apps.sistema.models import Tenant
from apps.comercial.atendimento.models import (
    FluxoAtendimento, NodoFluxoAtendimento
)

FLUXO_ID = 23
IA_ID = 15  # corrigido
tenant = Tenant.objects.get(slug='tr-carrion')
fluxo = FluxoAtendimento.objects.get(id=FLUXO_ID, tenant=tenant)


# ============================================================================
# Mapeia: substring no titulo -> nova config completa do nodo
# ============================================================================
CONFIGS = []

# 1. SAUDACAO + intent
CONFIGS.append({
    'match_titulo': 'Voce deseja consultar planos',  # com ou sem cedilha
    'match_titulo_alt': 'Você deseja consultar planos',
    'tipo': 'questao', 'subtipo': 'texto',
    'config': {
        'titulo': (
            'Oi! Tudo bem? 😊\n'
            'Sou a assistente virtual da Vero.\n'
            'Vou te ajudar a consultar planos de internet para o seu endereço.\n\n'
            'Você deseja consultar planos de internet para o seu endereço?'
        ),
        'espera_resposta': True,
        'integracao_ia_id': IA_ID,
        'ia_acao': 'classificar',
        'ia_modelo': 'gpt-4o-mini',
        'ia_categorias': ['intencao_sim', 'intencao_nao'],
        'ia_variavel_saida': 'intencao_status',
        'prompt_validacao': (
            'O cliente respondeu se deseja consultar planos de internet. '
            'Classifique:\n'
            '- intencao_sim: sim, quero, tenho interesse, quero contratar, claro, ok, pode ser, etc.\n'
            '- intencao_nao: nao, sem interesse, ja tenho, etc.'
        ),
    },
})

# 2. PEDE CEP
CONFIGS.append({
    'match_titulo': 'Me manda seu CEP',
    'tipo': 'questao', 'subtipo': 'texto',
    'config': {
        'titulo': 'Perfeito 😊\nMe manda seu CEP, por favor, para eu consultar sua região.',
        'espera_resposta': True,
        'salvar_em': 'var.cep',
        'integracao_ia_id': IA_ID,
        'ia_acao': 'extrair',
        'ia_modelo': 'gpt-4o-mini',
        'ia_campos_extrair': [
            {'nome': 'var.cep', 'descricao': 'CEP brasileiro (8 digitos)', 'tipo': 'string'},
        ],
        'prompt_validacao': 'Extraia o CEP brasileiro (8 digitos, com ou sem traco).',
    },
})

# 3. CHECK COBERTURA (ia_classificador)
CONFIGS.append({
    'tipo': 'ia_classificador',
    'config': {
        'integracao_ia_id': IA_ID,
        'modelo': 'gpt-4o-mini',
        'categorias': ['cobertura_ok', 'fora_cobertura'],
        'variavel_saida': 'cobertura_status',
        'system_prompt': (
            'A Vero atende as seguintes cidades: Bauru/SP, Marília/SP, Sorocaba/SP, Campinas/SP, São Paulo/SP.\n'
            'Dado o CEP {{var.cep}}, classifique:\n'
            '- cobertura_ok: se o CEP corresponde a uma das cidades acima\n'
            '- fora_cobertura: caso contrario\n\n'
            'Use seu conhecimento de CEPs brasileiros para determinar a cidade.'
        ),
    },
})

# 4. APRESENTA PLANOS (ia_respondedor) - identifica pelo conteudo do system_prompt ou ordem
PLANOS_LISTA = (
    '1. 550 Mega + Wi-Fi 6 — R$ 113,90/mês\n'
    '2. 550 Mega + Chip 10GB — R$ 118,90/mês\n'
    '3. 750 Mega + Wi-Fi 6 — R$ 122,90/mês\n'
    '4. 800 Mega + YouTube Premium — R$ 134,90/mês\n'
    '5. 800 Mega + Max — R$ 134,90/mês\n'
    '6. 800 Mega + Telecine — R$ 134,90/mês\n'
    '7. 800 Mega + Globoplay Canais + Chip 20GB — R$ 139,90/mês\n'
    '8. 800 Mega + Disney Padrão + Chip 20GB — R$ 139,90/mês\n'
    '9. 800 Mega + Globoplay Canais Premium + HBO Max + Chip 60GB — R$ 149,90/mês\n'
    '10. 800 Mega + Premiere — R$ 150,00/mês\n'
    '11. 800 Mega + Disney Plus — R$ 155,00/mês'
)
APRESENTA_PLANOS_PROMPT = (
    'Voce e a assistente virtual da Vero. Seja calorosa e direta.\n'
    'Envie esta mensagem:\n\n'
    '"Boa notícia 😊 Sua região aparece dentro da área de atendimento da Vero. '
    'A disponibilidade final será confirmada pelo endereço completo, mas já vou te mostrar os planos disponíveis:\n\n'
    f'{PLANOS_LISTA}\n\n'
    'Me responde com o número do plano que você quer 😊"\n\n'
    'Texto puro, sem markdown.'
)

# 5. ESCOLHA PLANO
CONFIGS.append({
    'match_titulo': '',  # sem titulo (campo titulo vazio) — identifica por contexto
    'tipo': 'questao', 'subtipo': 'texto',
    'identificador_extra': 'plano_escolhido',
    'config': {
        'titulo': '',
        'espera_resposta': True,
        'integracao_ia_id': IA_ID,
        'ia_acao': 'extrair',
        'ia_modelo': 'gpt-4o-mini',
        'ia_campos_extrair': [
            {'nome': 'oport.dados_custom.plano_escolhido', 'descricao': 'Numero do plano de 1 a 11', 'tipo': 'string'},
        ],
        'ia_salvar_no_lead': True,
        'prompt_validacao': 'Extraia o numero do plano escolhido (1 a 11). Se nao for numero valido, retorne vazio.',
    },
})

# 6. CONFIRMA PLANO (ia_respondedor com PLANOS_MAP)
PLANOS_MAP = (
    '1=550 Mega + Wi-Fi 6 (R$ 113,90/mês), '
    '2=550 Mega + Chip 10GB (R$ 118,90/mês), '
    '3=750 Mega + Wi-Fi 6 (R$ 122,90/mês), '
    '4=800 Mega + YouTube Premium (R$ 134,90/mês), '
    '5=800 Mega + Max (R$ 134,90/mês), '
    '6=800 Mega + Telecine (R$ 134,90/mês), '
    '7=800 Mega + Globoplay Canais + Chip 20GB (R$ 139,90/mês), '
    '8=800 Mega + Disney Padrão + Chip 20GB (R$ 139,90/mês), '
    '9=800 Mega + Globoplay Canais Premium + HBO Max + Chip 60GB (R$ 149,90/mês), '
    '10=800 Mega + Premiere (R$ 150,00/mês), '
    '11=800 Mega + Disney Plus (R$ 155,00/mês)'
)

# 7. PEDE ENDERECO
CONFIGS.append({
    'match_titulo': 'preciso do seu endereço completo',
    'tipo': 'questao', 'subtipo': 'texto',
    'config': {
        'titulo': (
            'Perfeito! 😊\n\n'
            'Agora preciso do seu endereço completo para seguir com a conferência.\n\n'
            'Me manda assim, por favor:\n'
            'Rua:\nNúmero:\nBairro:\nCidade:\nComplemento (se tiver):'
        ),
        'espera_resposta': True,
        'integracao_ia_id': IA_ID,
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
})

# 8. PEDE DADOS
CONFIGS.append({
    'match_titulo': 'preciso de alguns dados',
    'tipo': 'questao', 'subtipo': 'texto',
    'config': {
        'titulo': (
            'Perfeito, obrigado 😊\n\n'
            'Agora preciso de alguns dados para iniciar sua solicitação:\n\n'
            '1. Nome completo\n'
            '2. E-mail\n'
            '3. Melhor dia de vencimento da fatura\n'
            '4. Deseja débito automático? (Sim ou não)'
        ),
        'espera_resposta': True,
        'integracao_ia_id': IA_ID,
        'ia_acao': 'extrair',
        'ia_modelo': 'gpt-4o-mini',
        'ia_campos_extrair': [
            {'nome': 'nome_razaosocial', 'descricao': 'Nome completo do cliente', 'tipo': 'string'},
            {'nome': 'email', 'descricao': 'Email do cliente', 'tipo': 'string'},
            {'nome': 'oport.dados_custom.dia_vencimento', 'descricao': 'Dia de vencimento (1 a 31)', 'tipo': 'string'},
            {'nome': 'oport.dados_custom.debito_automatico', 'descricao': 'sim ou nao', 'tipo': 'string'},
        ],
        'ia_salvar_no_lead': True,
        'prompt_validacao': 'Extraia nome, email, dia de vencimento e preferencia por debito automatico.',
    },
})

# 9. LGPD
CONFIGS.append({
    'match_titulo': 'autoriza usar os dados',
    'tipo': 'questao', 'subtipo': 'texto',
    'config': {
        'titulo': (
            'Pra continuar, autoriza usar os dados que você enviou para a contratação? '
            'Responda Sim ou Não 🔐'
        ),
        'espera_resposta': True,
        'integracao_ia_id': IA_ID,
        'ia_acao': 'classificar',
        'ia_modelo': 'gpt-4o-mini',
        'ia_categorias': ['lgpd_sim', 'lgpd_nao'],
        'ia_variavel_saida': 'lgpd_status',
        'prompt_validacao': 'Classifique: lgpd_sim se autorizou, lgpd_nao se nao.',
    },
})


# ============================================================================
# Aplica configuracoes
# ============================================================================
nodos = list(NodoFluxoAtendimento.objects.filter(fluxo=fluxo).order_by('ordem'))
print(f"[INFO] {len(nodos)} nodos no fluxo {FLUXO_ID}")

with transaction.atomic():
    aplicados = []
    for nodo in nodos:
        cfg_atual = nodo.configuracao or {}
        titulo_atual = cfg_atual.get('titulo', '')
        system_atual = cfg_atual.get('system_prompt', '')
        ja_tem_ia = cfg_atual.get('integracao_ia_id')

        # tenta achar match
        for cfg_spec in CONFIGS:
            if cfg_spec.get('tipo') and cfg_spec['tipo'] != nodo.tipo:
                continue
            if cfg_spec.get('subtipo') and cfg_spec['subtipo'] != nodo.subtipo:
                continue
            # match por titulo (subset)
            mt = cfg_spec.get('match_titulo', '')
            mta = cfg_spec.get('match_titulo_alt', '')
            id_extra = cfg_spec.get('identificador_extra', '')

            matched = False
            if cfg_spec['tipo'] == 'ia_classificador':
                # so 1 ia_classificador no fluxo (check_cobertura)
                matched = True
            elif id_extra and id_extra in (system_atual or '') + (titulo_atual or ''):
                matched = True
            elif mt and (mt in titulo_atual or (mta and mta in titulo_atual)):
                matched = True
            elif mt == '' and not titulo_atual and cfg_spec.get('subtipo') == 'texto' and id_extra == 'plano_escolhido':
                # nodo de escolha de plano (titulo vazio) — pega por ordem
                matched = True

            if matched:
                # preserva pos_x, pos_y, ordem
                nodo.configuracao = cfg_spec['config']
                nodo.save()
                aplicados.append((nodo.id, nodo.tipo, nodo.subtipo, titulo_atual[:60]))
                break

    # apresenta_planos e confirma_plano: identifica por system_prompt
    for nodo in nodos:
        if nodo.tipo != 'ia_respondedor':
            continue
        sp_atual = (nodo.configuracao or {}).get('system_prompt', '')
        if 'Boa notícia' in sp_atual or 'planos disponíveis' in sp_atual or 'apresenta_planos' in (nodo.configuracao or {}).get('_marker', ''):
            nodo.configuracao = {
                'integracao_ia_id': IA_ID,
                'modelo': 'gpt-4o-mini',
                'system_prompt': APRESENTA_PLANOS_PROMPT,
            }
            nodo.save()
            aplicados.append((nodo.id, nodo.tipo, nodo.subtipo, 'apresenta_planos'))
        elif 'escolheu o plano' in sp_atual or 'Voce escolheu' in sp_atual or '📶' in sp_atual:
            nodo.configuracao = {
                'integracao_ia_id': IA_ID,
                'modelo': 'gpt-4o-mini',
                'system_prompt': (
                    'Voce e a assistente virtual da Vero.\n'
                    'O cliente escolheu o plano numero {{oport_dados_custom_plano_escolhido}}.\n'
                    f'Tabela: {PLANOS_MAP}.\n\n'
                    'Envie esta mensagem (substitua os valores reais):\n'
                    '"Perfeito! Você escolheu este plano:\n\n'
                    '📶 [nome do plano]\n'
                    '💰 [valor]/mês\n\n'
                    'Agora preciso do seu endereço completo para seguir com a conferência."\n\n'
                    'Texto puro, sem markdown.'
                ),
            }
            nodo.save()
            aplicados.append((nodo.id, nodo.tipo, nodo.subtipo, 'confirma_plano'))

    print(f"\n[OK] {len(aplicados)} nodos atualizados:")
    for a in aplicados:
        print(f"  - id={a[0]} {a[1]}/{a[2]} titulo='{a[3]}'")

print()
print("=" * 60)
print(f"CONFIG IA REAPLICADA NO FLUXO {FLUXO_ID} COM ia_id={IA_ID}")
print("=" * 60)
print("Lembrete: NAO salve pelo editor entre testes, ou as configs IA somem de novo.")
