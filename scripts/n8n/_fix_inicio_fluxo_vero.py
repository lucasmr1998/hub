"""
Ajusta o inicio do fluxo Vero V1 (fluxo id=23):
- nodo 'saudacao' vira saudacao + pergunta de intencao (classificador IA sim/nao)
- novo nodo 'cond_intencao'
- novo nodo 'pede_cep' (separado)
- novo nodo 'handoff_sem_interesse'
- reorganiza conexoes
"""
from django.db import transaction
from apps.sistema.models import Tenant
from apps.comercial.atendimento.models import (
    FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento
)

FLUXO_ID = 23
tenant = Tenant.objects.get(slug='tr-carrion')
fluxo = FluxoAtendimento.objects.get(id=FLUXO_ID, tenant=tenant)

# IDs dos nodos atuais (por subtipo+ordem)
def get_nodo(ordem):
    return NodoFluxoAtendimento.objects.get(fluxo=fluxo, ordem=ordem)

saudacao = get_nodo(2)
check_cobertura = get_nodo(3)

# pega IntegracaoAPI OpenAI (a unica no tenant)
from apps.integracoes.models import IntegracaoAPI
ia_id = IntegracaoAPI.objects.get(tenant=tenant, tipo='openai').id

with transaction.atomic():
    # 1. Refaz saudacao -> so saudacao + pergunta intent
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
            '- intencao_sim: respondeu afirmativamente (sim, quero, tenho interesse, quero contratar, claro, vamos, ok, pode ser, etc).\n'
            '- intencao_nao: respondeu negativamente (nao, nao quero, sem interesse, ja tenho, etc).'
        ),
    }
    saudacao.save()
    print(f"[OK] Nodo {saudacao.id} (saudacao) atualizado: vira saudacao + pergunta intent")

    # 2. cond_intencao
    cond_intencao = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='condicao', subtipo='campo_check',
        configuracao={
            'campo': 'var.intencao_status',
            'operador': 'igual',
            'valor': 'intencao_sim',
        },
        pos_x=350, pos_y=500, ordem=19,
    )
    print(f"[OK] Nodo cond_intencao criado: id={cond_intencao.id}")

    # 3. pede_cep (separado da saudacao)
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
                {'nome': 'var.cep', 'descricao': 'CEP brasileiro com 8 digitos', 'tipo': 'string'},
            ],
            'prompt_validacao': 'Extraia o CEP brasileiro (8 digitos, com ou sem traco).',
        },
        pos_x=600, pos_y=500, ordem=20,
    )
    print(f"[OK] Nodo pede_cep criado: id={pede_cep.id}")

    # 4. handoff_sem_interesse
    handoff_sem = NodoFluxoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo, tipo='transferir_humano', subtipo='transferir_humano',
        configuracao={
            'titulo': (
                'Tudo bem 😊 Se mudar de ideia ou tiver alguma dúvida, é só me chamar! '
                'Vou deixar um consultor disponível pra te ajudar quando quiser.'
            ),
            'motivo': 'sem_interesse_vero',
        },
        pos_x=350, pos_y=700, ordem=21,
    )
    print(f"[OK] Nodo handoff_sem_interesse criado: id={handoff_sem.id}")

    # 5. Refaz conexoes
    # Remove: saudacao -> check_cobertura (existia)
    ConexaoNodoAtendimento.objects.filter(
        fluxo=fluxo, nodo_origem=saudacao, nodo_destino=check_cobertura
    ).delete()
    print("[OK] Conexao antiga saudacao->check_cobertura removida")

    # Cria: saudacao -> cond_intencao
    ConexaoNodoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo,
        nodo_origem=saudacao, nodo_destino=cond_intencao,
        tipo_saida='default',
    )
    # cond_intencao true -> pede_cep
    ConexaoNodoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo,
        nodo_origem=cond_intencao, nodo_destino=pede_cep,
        tipo_saida='true',
    )
    # cond_intencao false -> handoff_sem
    ConexaoNodoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo,
        nodo_origem=cond_intencao, nodo_destino=handoff_sem,
        tipo_saida='false',
    )
    # pede_cep -> check_cobertura
    ConexaoNodoAtendimento.objects.create(
        tenant=tenant, fluxo=fluxo,
        nodo_origem=pede_cep, nodo_destino=check_cobertura,
        tipo_saida='default',
    )
    print("[OK] 4 conexoes novas criadas")

print()
print("=" * 60)
print("FLUXO V1 AJUSTADO")
print("=" * 60)
print(f"Fluxo {FLUXO_ID}: agora tem 21 nodos, fluxo de inicio em 3 etapas:")
print("  1) Saudacao + 'Voce deseja consultar planos?' (IA classifica)")
print("  2) Se SIM -> pede CEP")
print("  3) Se NAO -> handoff cordial (sem_interesse)")
print()
print(f"Editor: https://app.hubtrix.com.br/comercial/atendimento/fluxos/{FLUXO_ID}/editor/")
