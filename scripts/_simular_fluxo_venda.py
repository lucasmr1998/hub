"""
Simula o fluxo completo de criação de uma Venda via automação:

  LeadProspecto + Imagens → validar docs → signal docs_validados
  → RegraAutomacao criar_venda → Venda em /vendas/crm/

Rodar (direto, sem pipe):
  cd robo/dashboard_comercial/gerenciador_vendas
  python ..\..\..\scripts\_simular_fluxo_venda.py
"""
import os
import sys
import django

# Adiciona o projeto ao path e configura Django
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'robo', 'dashboard_comercial', 'gerenciador_vendas')
sys.path.insert(0, os.path.abspath(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gerenciador_vendas.settings_local')
django.setup()

# ---------------------------------------------------------------------------
# 1. TENANT
# ---------------------------------------------------------------------------
from apps.sistema.models import Tenant

TENANT_SLUG = None  # None = primeiro tenant disponível; ex: 'aurora-hq'

if TENANT_SLUG:
    tenant = Tenant.objects.get(slug=TENANT_SLUG)
else:
    tenant = Tenant.objects.first()

if not tenant:
    print("ERRO: nenhum tenant encontrado.")
    sys.exit(1)

print(f"\n[TENANT] {tenant.nome} (slug={tenant.slug})")

# ---------------------------------------------------------------------------
# 2. REGRA DE AUTOMAÇÃO: docs_validados → criar_venda
# ---------------------------------------------------------------------------
from apps.marketing.automacoes.models import RegraAutomacao, AcaoRegra

regra, criada_regra = RegraAutomacao.all_tenants.get_or_create(
    tenant=tenant,
    nome='[TESTE] docs_validados → criar_venda',
    defaults={'evento': 'docs_validados', 'ativa': True, 'modo_fluxo': False},
)
if not criada_regra:
    regra.evento = 'docs_validados'
    regra.ativa = True
    regra.save(update_fields=['evento', 'ativa'])

print(f"[REGRA]  {'Criada' if criada_regra else 'Reutilizada'}: {regra.nome} (id={regra.pk})")

acao, criada_acao = AcaoRegra.all_tenants.get_or_create(
    tenant=tenant, regra=regra, tipo='criar_venda',
    defaults={'ordem': 0},
)
print(f"[ACAO]   {'Criada' if criada_acao else 'Reutilizada'}: tipo=criar_venda (id={acao.pk})")

# ---------------------------------------------------------------------------
# 3. LEAD DE TESTE
# ---------------------------------------------------------------------------
from apps.comercial.leads.models import LeadProspecto

lead = LeadProspecto.all_tenants.create(
    tenant=tenant,
    nome_razaosocial='Lead Teste Simulacao Venda',
    telefone='11999990001',
    email='teste.venda@simulacao.local',
    origem='whatsapp',
)
print(f"\n[LEAD]   Criado: {lead.nome_razaosocial} (id={lead.pk})")

# ---------------------------------------------------------------------------
# 4. OPORTUNIDADE DE TESTE
# ---------------------------------------------------------------------------
from apps.comercial.crm.models import OportunidadeVenda, PipelineEstagio

estagio = PipelineEstagio.all_tenants.filter(tenant=tenant, ativo=True).first()
oport = None
if estagio:
    oport = OportunidadeVenda.all_tenants.create(
        tenant=tenant,
        lead=lead,
        pipeline=estagio.pipeline,
        estagio=estagio,
        valor_estimado='99.90',
        origem_crm='manual',
    )
    print(f"[OPORT]  Criada: {estagio.pipeline.nome} / {estagio.nome} (id={oport.pk})")
else:
    print("[OPORT]  Nenhum estágio ativo — oportunidade não criada (ok)")

# ---------------------------------------------------------------------------
# 5. DOCUMENTOS PENDENTES
# ---------------------------------------------------------------------------
from apps.comercial.leads.models import ImagemLeadProspecto

img1 = ImagemLeadProspecto.all_tenants.create(
    tenant=tenant, lead=lead,
    link_url='https://example.com/rg_frente.jpg',
    descricao='RG Frente',
    status_validacao=ImagemLeadProspecto.STATUS_PENDENTE,
)
img2 = ImagemLeadProspecto.all_tenants.create(
    tenant=tenant, lead=lead,
    link_url='https://example.com/rg_verso.jpg',
    descricao='RG Verso',
    status_validacao=ImagemLeadProspecto.STATUS_PENDENTE,
)
print(f"[DOCS]   img1={img1.pk} (pendente)  img2={img2.pk} (pendente)")

# ---------------------------------------------------------------------------
# 6. VALIDAR SÓ img1 — Venda NÃO deve ser criada
# ---------------------------------------------------------------------------
from apps.comercial.crm.models import Venda

print("\n[PASSO 1] Validando img1 — docs_validados NÃO deve disparar (img2 ainda pendente)")
img1.status_validacao = ImagemLeadProspecto.STATUS_VALIDO
img1.save(update_fields=['status_validacao'])

n = Venda.all_tenants.filter(tenant=tenant, lead=lead).count()
print(f"          Vendas criadas: {n} (esperado: 0) {'OK' if n == 0 else 'FALHOU'}")

# ---------------------------------------------------------------------------
# 7. VALIDAR img2 — TODOS validados → signal → Venda criada
# ---------------------------------------------------------------------------
print("\n[PASSO 2] Validando img2 — TODOS os docs válidos → deve disparar docs_validados")
img2.status_validacao = ImagemLeadProspecto.STATUS_VALIDO
img2.save(update_fields=['status_validacao'])

# ---------------------------------------------------------------------------
# 8. RESULTADO
# ---------------------------------------------------------------------------
venda = Venda.all_tenants.filter(tenant=tenant, lead=lead).first()

print()
if venda:
    print("=" * 60)
    print("  VENDA CRIADA COM SUCESSO!")
    print("=" * 60)
    print(f"  ID venda    : {venda.pk}")
    print(f"  Lead        : {lead.nome_razaosocial} (id={lead.pk})")
    print(f"  Oportunidade: {venda.oportunidade_id or '—'}")
    print(f"  Plano       : {venda.plano or '—'}")
    print(f"  Valor       : {venda.valor or '—'}")
    print(f"  Status ERP  : {venda.status}")
    print(f"  Data        : {venda.data_venda.strftime('%d/%m/%Y %H:%M')}")
    print("=" * 60)
else:
    print("FALHA: Venda NÃO foi criada.")
    print("Verifique se a regra está ativa e o evento docs_validados está configurado.")

# ---------------------------------------------------------------------------
# 9. LIMPEZA
# ---------------------------------------------------------------------------
print()
resposta = input("Remover dados de teste? (s/n): ").strip().lower()
if resposta == 's':
    if venda:
        venda.delete()
    img1.delete()
    img2.delete()
    if oport:
        oport.delete()
    lead.delete()
    if criada_acao:
        acao.delete()
    if criada_regra:
        regra.delete()
    print("Dados removidos.")
else:
    print("Dados mantidos. Acesse /vendas/crm/ para ver a venda.")
