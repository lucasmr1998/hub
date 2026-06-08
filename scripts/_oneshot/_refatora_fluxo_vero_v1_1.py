"""
Refatora fluxo Vero V1 (id=23) pra alinhar 100% com o spec original.

Mudancas:
1. Saudacao + pergunta de intent (separa do CEP)
2. cond_intencao + pede_cep + handoff_sem_interesse (novos)
3. confirma_plano (eco do plano escolhido)
4. Docs em 3 etapas: pede_frente -> confirma_frente_pede_verso -> confirma_verso
5. notifica_equipe (mensagem ficha formatada antes do handoff)
6. Remove: resumo, confirma, cond_confirma, pede_docs (substituido por 3 novos)
7. LGPD reformulado (mais discreto)

Tudo em transaction.atomic.
"""
from django.db import transaction
from apps.sistema.models import Tenant
from apps.integracoes.models import IntegracaoAPI
from apps.comercial.atendimento.models import (
    FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento
)

FLUXO_ID = 23
tenant = Tenant.objects.get(slug='tr-carrion')
fluxo = FluxoAtendimento.objects.get(id=FLUXO_ID, tenant=tenant)
ia_id = IntegracaoAPI.objects.get(tenant=tenant, tipo='openai').id

def by_ordem(o):
    return NodoFluxoAtendimento.objects.get(fluxo=fluxo, ordem=o)

# referencia aos nodos existentes (V1)
inicio = by_ordem(1)
saudacao = by_ordem(2)
check_cobertura = by_ordem(3)
cond_cobertura = by_ordem(4)
apresenta_planos = by_ordem(5)
escolha_plano = by_ordem(6)
pede_endereco = by_ordem(7)
pede_dados = by_ordem(8)
lgpd = by_ordem(9)
cond_lgpd = by_ordem(10)
pede_docs = by_ordem(11)
resumo = by_ordem(12)
confirma = by_ordem(13)
cond_confirma = by_ordem(14)
criar_oport = by_ordem(15)
handoff = by_ordem(16)
handoff_fora = by_ordem(17)
handoff_lgpd = by_ordem(18)


with transaction.atomic():
    # ========================================================================
    # 1. Limpa todas as conexoes existentes (vamos recriar tudo)
    # ========================================================================
    n_old = ConexaoNodoAtendimento.objects.filter(fluxo=fluxo).count()
    ConexaoNodoAtendimento.objects.filter(fluxo=fluxo).delete()
    print(f"[OK] {n_old} conexoes antigas removidas")

    # ========================================================================
    # 2. SAUDACAO -> vira saudacao + pergunta intent
    # ========================================================================
    saudacao.configuracao = {
        'titulo': (
            'Oi! Tudo bem? 😊\n'
            'Sou a assistente virtual da Vero.\n'
            'Vou te ajudar a consultar planos de internet para o seu endereço.\n\n'
            'Você deseja consultar planos de internet para o seu endereço?'
        ),
        'espera_resposta': True,
        'integracao_ia_id': ia_id,
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
    }
    saudacao.save()
    print(f"[OK] Saudacao (id={saudacao.id}) reformulada")

    # ========================================================================
    # 3. Novos nodos: cond_intencao, pede_cep, handoff_sem_interesse
    # ========================================================================
    cond_intencao = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='condicao', subtipo='campo_check',
        configuracao={'campo': 'var.intencao_status', 'operador': 'igual', 'valor': 'intencao_sim'},
        pos_x=350, pos_y=500, ordem=19,
    )
    pede_cep = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': 'Perfeito 😊\nMe manda seu CEP, por favor, para eu consultar sua região.',
            'espera_resposta': True,
            'salvar_em': 'var.cep',
            'integracao_ia_id': ia_id,
            'ia_acao': 'extrair',
            'ia_modelo': 'gpt-4o-mini',
            'ia_campos_extrair': [
                {'nome': 'var.cep', 'descricao': 'CEP brasileiro (8 digitos)', 'tipo': 'string'},
            ],
            'prompt_validacao': 'Extraia o CEP brasileiro (8 digitos, com ou sem traco).',
        },
        pos_x=600, pos_y=500, ordem=20,
    )
    handoff_sem_interesse = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='transferir_humano', subtipo='transferir_humano',
        configuracao={
            'titulo': 'Tudo bem 😊 Se mudar de ideia ou tiver alguma dúvida, é só me chamar! Vou deixar um consultor disponível pra te ajudar quando quiser.',
            'motivo': 'sem_interesse_vero',
        },
        pos_x=350, pos_y=700, ordem=21,
    )
    print(f"[OK] Novos nodos do inicio: cond_intencao={cond_intencao.id}, pede_cep={pede_cep.id}, handoff_sem={handoff_sem_interesse.id}")

    # ========================================================================
    # 4. confirma_plano (eco do plano escolhido) entre escolha_plano e pede_endereco
    # ========================================================================
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
    confirma_plano = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='ia_respondedor', subtipo='ia_respondedor',
        configuracao={
            'integracao_ia_id': ia_id,
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
        },
        pos_x=1475, pos_y=200, ordem=22,
    )
    print(f"[OK] confirma_plano criado: id={confirma_plano.id}")

    # ========================================================================
    # 5. LGPD reformulado (mais discreto)
    # ========================================================================
    lgpd.configuracao = {
        'titulo': (
            'Pra continuar, autoriza usar os dados que você enviou para a contratação? '
            'Responda Sim ou Não 🔐'
        ),
        'espera_resposta': True,
        'integracao_ia_id': ia_id,
        'ia_acao': 'classificar',
        'ia_modelo': 'gpt-4o-mini',
        'ia_categorias': ['lgpd_sim', 'lgpd_nao'],
        'ia_variavel_saida': 'lgpd_status',
        'prompt_validacao': 'Classifique: lgpd_sim se autorizou, lgpd_nao se nao.',
    }
    lgpd.save()
    print(f"[OK] LGPD (id={lgpd.id}) reformulado")

    # ========================================================================
    # 6. Docs em 3 etapas separadas
    # ========================================================================
    pede_frente = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': (
                'Para seguir com o cadastro, vou precisar das fotos do seu documento.\n\n'
                'Pode me enviar primeiro a foto da frente do documento, por favor?'
            ),
            'espera_resposta': True,
            'aguarda_anexo': True,
        },
        pos_x=2600, pos_y=200, ordem=23,
    )
    confirma_frente_pede_verso = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': 'Recebi a frente do documento, obrigado 😊\nAgora me envia a foto do verso, por favor.',
            'espera_resposta': True,
            'aguarda_anexo': True,
        },
        pos_x=2850, pos_y=200, ordem=24,
    )
    confirma_verso = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='questao', subtipo='texto',
        configuracao={
            'titulo': 'Perfeito, recebi os documentos 👍\nVou encaminhar sua solicitação para conferência de disponibilidade e finalização com um consultor.',
            'espera_resposta': False,
        },
        pos_x=3100, pos_y=200, ordem=25,
    )
    print(f"[OK] Docs em 3 etapas: pede_frente={pede_frente.id}, confirma_frente_pede_verso={confirma_frente_pede_verso.id}, confirma_verso={confirma_verso.id}")

    # ========================================================================
    # 7. notifica_equipe (ficha formatada pra equipe)
    # ========================================================================
    notifica_equipe = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='acao', subtipo='webhook',
        configuracao={
            # webhook interno: posta ficha formatada como nota na oportunidade
            # (no MVP, pode ser ajustado depois pra notificar via canal interno)
            'url': '',  # placeholder — quando implementar handoff team, completar
            'metodo': 'POST',
            'titulo': 'Notificacao para equipe (ficha)',
            'template': (
                '📂📂📂📂📂📂📂📂📂📂\n\n'
                'Nova solicitação feita pelo Agente de IA.\n'
                'Fonte: WhatsApp Vero\n\n'
                'Telefone do cliente: {{lead_telefone}}\n\n'
                'Nome do cliente: {{nome_razaosocial}}\n'
                'Email: {{email}}\n'
                'Dados: RG e CPF enviados, frente e verso inclusos\n'
                'Endereço completo: {{oport_dados_custom_endereco_rua}}, {{oport_dados_custom_endereco_numero}}, '
                '{{oport_dados_custom_endereco_bairro}}, {{oport_dados_custom_endereco_cidade}} - CEP {{var_cep}}\n'
                'Plano: número {{oport_dados_custom_plano_escolhido}}\n'
                'Cidade: {{oport_dados_custom_endereco_cidade}}\n'
                'Data de vencimento: {{oport_dados_custom_dia_vencimento}}\n'
                'Débito automático: {{oport_dados_custom_debito_automatico}}\n\n'
                'Ação: conferir cobertura final, validar cadastro e finalizar venda.'
            ),
        },
        pos_x=3700, pos_y=150, ordem=26,
    )
    print(f"[OK] notifica_equipe criado: id={notifica_equipe.id}")

    # ========================================================================
    # 8. Remove nodos descartados: resumo, confirma, cond_confirma, pede_docs
    # ========================================================================
    for n in [resumo, confirma, cond_confirma, pede_docs]:
        n.delete()
    print("[OK] Removidos: resumo, confirma, cond_confirma, pede_docs")

    # ========================================================================
    # 9. Recria todas as conexoes (fluxo coerente)
    # ========================================================================
    def conn(o, d, t='default'):
        ConexaoNodoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo,
            nodo_origem=o, nodo_destino=d, tipo_saida=t,
        )

    conn(inicio, saudacao)
    conn(saudacao, cond_intencao)
    conn(cond_intencao, pede_cep, 'true')
    conn(cond_intencao, handoff_sem_interesse, 'false')
    conn(pede_cep, check_cobertura)
    conn(check_cobertura, cond_cobertura)
    conn(cond_cobertura, apresenta_planos, 'true')
    conn(cond_cobertura, handoff_fora, 'false')
    conn(apresenta_planos, escolha_plano)
    conn(escolha_plano, confirma_plano)
    conn(confirma_plano, pede_endereco)
    conn(pede_endereco, pede_dados)
    conn(pede_dados, lgpd)
    conn(lgpd, cond_lgpd)
    conn(cond_lgpd, pede_frente, 'true')
    conn(cond_lgpd, handoff_lgpd, 'false')
    conn(pede_frente, confirma_frente_pede_verso)
    conn(confirma_frente_pede_verso, confirma_verso)
    conn(confirma_verso, criar_oport)
    conn(criar_oport, notifica_equipe)
    conn(notifica_equipe, handoff)
    print("[OK] 21 conexoes recriadas")


# ============================================================================
# RESUMO
# ============================================================================
total_nodos = NodoFluxoAtendimento.objects.filter(fluxo=fluxo).count()
total_conexoes = ConexaoNodoAtendimento.objects.filter(fluxo=fluxo).count()

print()
print("=" * 60)
print("FLUXO VERO V1.1 ATUALIZADO")
print("=" * 60)
print(f"Total nodos:    {total_nodos}")
print(f"Total conexoes: {total_conexoes}")
print()
print("Estrutura final do fluxo:")
print("  1. inicio")
print("  2. saudacao + pergunta intent  -> cond_intencao")
print("       sim -> pede_cep -> check_cobertura -> cond_cobertura")
print("                                                  sim -> apresenta_planos -> escolha_plano")
print("                                                  nao -> handoff_fora")
print("       nao -> handoff_sem_interesse")
print("  3. escolha_plano -> confirma_plano (eco) -> pede_endereco -> pede_dados -> lgpd -> cond_lgpd")
print("       sim -> pede_frente -> confirma_frente_pede_verso -> confirma_verso")
print("              -> criar_oport -> notifica_equipe -> handoff")
print("       nao -> handoff_lgpd")
print()
print(f"Editor: https://app.hubtrix.com.br/comercial/atendimento/fluxos/{FLUXO_ID}/editor/")
