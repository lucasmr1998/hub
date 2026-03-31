app_name = 'vendas_web'

# ============================================================================
# TODAS AS ROTAS FORAM MIGRADAS PARA OS APPS MODULARES:
#
# - apps.sistema.urls             (auth, configuracoes, usuarios)
# - apps.comercial.leads.urls     (leads, prospectos, historicos, vendas)
# - apps.comercial.atendimento.urls (fluxos, questoes, atendimentos, N8N)
# - apps.comercial.cadastro.urls  (cadastro, planos, vencimentos, CEP)
# - apps.comercial.viabilidade.urls (viabilidade tecnica)
# - apps.notificacoes.urls        (notificacoes, templates, canais, whatsapp)
# - apps.marketing.campanhas.urls (campanhas de trafego)
# - apps.dashboard.urls           (dashboard, relatorios, analise, docs)
#
# Este arquivo sera removido quando a migracao estiver completa.
# ============================================================================

urlpatterns = [
]
