"""
Teste end-to-end do fluxo v3 FATEPI em producao.

- Cria LeadProspecto temp com nome_razaosocial contendo '__QA_TESTE__'
- Inicia AtendimentoFluxo via engine.iniciar_por_canal
- Simula candidato enviando: nome -> curso (Psicologia) -> ingresso (ENEM)
- Imprime nodo_atual a cada passo
- Limpa tudo no final
"""
from apps.sistema.models import Tenant
from apps.comercial.leads.models import LeadProspecto
from apps.comercial.atendimento.models import (
    FluxoAtendimento, AtendimentoFluxo, LogFluxoAtendimento,
)
from apps.comercial.atendimento.engine import (
    iniciar_fluxo_visual, processar_resposta_visual,
)

TENANT_ID = 7
FLUXO_ID = 6
TELEFONE = '+5586999990023'
NOME_MARCADOR = '__QA_TESTE_23_04_2026__'

tenant = Tenant.objects.get(id=TENANT_ID)
fluxo = FluxoAtendimento.all_tenants.get(id=FLUXO_ID, tenant=tenant)

print(f"Tenant: {tenant.nome}")
print(f"Fluxo: {fluxo.nome} (ativo={fluxo.ativo})")
print(f"Total nodos: {fluxo.nodos.count()}")

# Limpa qualquer lead/atendimento de teste anterior
leads_antigos = LeadProspecto.all_tenants.filter(tenant=tenant, telefone=TELEFONE)
for l in leads_antigos:
    AtendimentoFluxo.all_tenants.filter(lead=l).delete()
leads_antigos.delete()
print("Leads de teste antigos: limpos")

# Cria lead
lead = LeadProspecto.all_tenants.create(
    tenant=tenant,
    telefone=TELEFONE,
    nome_razaosocial=NOME_MARCADOR,
    origem='whatsapp',
    tipo_entrada='contato_whatsapp',
)
print(f"LeadProspecto criado: id={lead.id}")

# Cria atendimento manualmente (bypass pode_ser_usado que checa status='ativo')
print(f"Status fluxo: {fluxo.status!r} ativo={fluxo.ativo} modo_fluxo={fluxo.modo_fluxo}")
total_q = fluxo.nodos.filter(tipo='questao').count()
atendimento = AtendimentoFluxo.all_tenants.create(
    tenant=tenant,
    lead=lead,
    fluxo=fluxo,
    total_questoes=total_q,
    max_tentativas=fluxo.max_tentativas,
)
resultado = iniciar_fluxo_visual(atendimento)
print(f"Atendimento criado: id={atendimento.id}")
print(f"Resultado iniciar: tipo={resultado.get('tipo')}")
if resultado.get('tipo') == 'questao':
    print(f"  primeira pergunta: {resultado.get('questao', {}).get('titulo', '')[:120]}")

def step(msg, label):
    print(f"\n=== {label}: candidato envia {msg!r} ===")
    atendimento.refresh_from_db()
    print(f"  ANTES: nodo_atual={atendimento.nodo_atual_id} "
          f"quest_resp={atendimento.questoes_respondidas}")
    try:
        r = processar_resposta_visual(atendimento, msg)
    except Exception as e:
        import traceback
        print(f"  ERRO: {e}")
        traceback.print_exc()
        return
    atendimento.refresh_from_db()
    print(f"  DEPOIS: nodo_atual={atendimento.nodo_atual_id} "
          f"status={atendimento.status} "
          f"quest_resp={atendimento.questoes_respondidas}")
    if atendimento.nodo_atual:
        print(f"  nodo: tipo={atendimento.nodo_atual.tipo} subtipo={atendimento.nodo_atual.subtipo}")
    print(f"  resultado: tipo={r.get('tipo')}")
    pergunta = r.get('questao', {}).get('titulo', '') if r.get('questao') else r.get('mensagem', '')
    if pergunta:
        print(f"  proxima/msg: {pergunta[:200]}")

step('Lucas Teste QA', 'PASSO 1 (nome)')
step('Psicologia',      'PASSO 2 (curso)')
step('ENEM',            'PASSO 3 (ingresso)')

# Estado final
atendimento.refresh_from_db()
lead.refresh_from_db()
print("\n=== ESTADO FINAL ===")
print(f"  atendimento.status = {atendimento.status}")
print(f"  atendimento.nodo_atual_id = {atendimento.nodo_atual_id}")
if atendimento.nodo_atual:
    print(f"  nodo tipo={atendimento.nodo_atual.tipo} subtipo={atendimento.nodo_atual.subtipo}")
print(f"  questoes_respondidas = {atendimento.questoes_respondidas}")
print(f"  dados_respostas = {atendimento.dados_respostas}")
print(f"  lead.nome_razaosocial = {lead.nome_razaosocial!r}")

# Logs recentes
logs = LogFluxoAtendimento.all_tenants.filter(atendimento=atendimento).order_by('-id')[:8]
print(f"\n  Ultimos logs ({logs.count()}):")
for lg in reversed(list(logs)):
    print(f"    [{lg.status}] nodo={lg.nodo_id} {lg.mensagem[:150]}")

# LIMPEZA
print("\n=== LIMPEZA ===")
n_at = AtendimentoFluxo.all_tenants.filter(lead=lead).count()
n_logs = LogFluxoAtendimento.all_tenants.filter(atendimento__lead=lead).count()
AtendimentoFluxo.all_tenants.filter(lead=lead).delete()
lead.delete()
print(f"  {n_at} atendimento + {n_logs} logs removidos")
print(f"  Lead removido")
