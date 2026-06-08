"""Inventaria o que existe pra tenant=9 (Gigamax) no DB local."""
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'robo', 'dashboard_comercial', 'gerenciador_vendas'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'gerenciador_vendas.settings_local'
django.setup()

from django.apps import apps as django_apps

TENANT_ID = 9

# Apps considerados "config" (não operacionais)
APPS_CONFIG = [
    'sistema',
    'integracoes',
    'inbox',
    'crm',  # apps.comercial.crm tem app_label='crm'
    'atendimento',  # apps.comercial.atendimento → fluxos podem entrar como config
    'cadastro',
    'leads',  # leads operacionais — vou listar mas não migrar por padrão
    'campanhas',
    'automacoes',
    'emails',
    'workspace',
    'notificacoes',
    'suporte',
    'clube',
    'parceiros',
    'indicacoes',
    'carteirinha',
    'nps',
    'retencao',
]

# Models que NÃO devem ser migrados (operacionais ou globais)
EXCLUIR = {
    # logs/operacionais grandes
    'LogIntegracao', 'LogSistema', 'ImagemLeadProspecto',
    # operacionais
    'AtendimentoFluxo', 'Conversa', 'Mensagem', 'NotaInternaConversa',
    'AvaliacaoAtendimento', 'TarefaCRM', 'HistoricoCRM', 'Nota',
    'Oportunidade', 'OportunidadeVenda', 'ItemOportunidade',
    'Notificacao', 'NotificacaoLeituraBroadcast',
    'ClienteHubsoft', 'ServicoClienteHubsoft', 'ClienteSGP', 'ClienteConsolidado',
    'Documento', 'AnexoDocumento', 'Tarefa',  # workspace operacional
    # globais (não filtra por tenant ou já existe em prod)
    'Funcionalidade',
    # leads operacionais
    'LeadProspecto', 'Prospecto', 'HistoricoContato',
    # CS operacional
    'MembroClube', 'Indicacao',
    # campanhas operacionais (envios)
    'EnvioCampanha', 'EnvioEmail',
}

print(f'=== Inventário tenant=9 (Gigamax) — local ===\n')

total = 0
modelos_com_dados = []

for model in django_apps.get_models():
    if model._meta.app_label not in APPS_CONFIG:
        continue
    if model.__name__ in EXCLUIR:
        continue
    if not hasattr(model, 'tenant'):
        continue

    try:
        # Tenta usar all_tenants se existir (TenantManager filtra por padrão)
        manager = getattr(model, 'all_tenants', model.objects)
        qtd = manager.filter(tenant_id=TENANT_ID).count()
        if qtd > 0:
            modelos_com_dados.append((model._meta.app_label, model.__name__, qtd))
            total += qtd
    except Exception as exc:
        print(f'  [erro] {model._meta.label}: {exc}')

# Ordenar por quantidade
modelos_com_dados.sort(key=lambda x: -x[2])

for app, name, qtd in modelos_com_dados:
    print(f'  {app}.{name:35s} {qtd:>5}')

print(f'\nTotal de registros (sem operacionais): {total}')
print(f'Models com dados: {len(modelos_com_dados)}')
