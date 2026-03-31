"""
Popula os planos com features conforme documentação GTM/08-PRECIFICACAO.md
Uso: python manage.py seed_planos --settings=gerenciador_vendas.settings_local
"""
from django.core.management.base import BaseCommand
from apps.sistema.models import Plano, FeaturePlano


FEATURES = {
    # ── COMERCIAL ──────────────────────────────────────────────────────────
    ('comercial', 'starter'): [
        ('leads', 'Gestao de leads', 'core'),
        ('atendimento-bot', 'Bot de atendimento (N8N)', 'core'),
        ('cadastro-cliente', 'Cadastro de clientes', 'core'),
        ('viabilidade', 'Consulta de viabilidade tecnica', 'core'),
        ('docs-validacao', 'Validacao de documentos', 'core'),
        ('hubsoft-sync', 'Integracao HubSoft (sync clientes)', 'integracao'),
        ('hubsoft-contrato', 'Envio automatico de contrato ao HubSoft', 'integracao'),
        ('dashboard-basico', 'Dashboard basico', 'relatorios'),
        ('relatorios-leads', 'Relatorio de leads', 'relatorios'),
        ('com-usuarios-2', '1 a 2 usuarios', 'suporte'),
    ],
    ('comercial', 'start'): [
        ('leads', 'Gestao de leads', 'core'),
        ('atendimento-bot', 'Bot de atendimento (N8N)', 'core'),
        ('cadastro-cliente', 'Cadastro de clientes', 'core'),
        ('viabilidade', 'Consulta de viabilidade tecnica', 'core'),
        ('docs-validacao', 'Validacao de documentos', 'core'),
        ('hubsoft-sync', 'Integracao HubSoft (sync clientes)', 'integracao'),
        ('hubsoft-contrato', 'Envio automatico de contrato ao HubSoft', 'integracao'),
        ('dashboard-basico', 'Dashboard basico', 'relatorios'),
        ('relatorios-leads', 'Relatorio de leads', 'relatorios'),
        ('campanhas', 'Campanhas de trafego pago', 'core'),
        ('notificacoes', 'Sistema de notificacoes', 'core'),
        ('automacoes-followup', 'Automacoes de follow-up', 'automacao'),
        ('relatorios-vendas', 'Relatorio de vendas', 'relatorios'),
        ('relatorios-atendimentos', 'Relatorio de atendimentos', 'relatorios'),
        ('com-usuarios-5', 'Ate 5 usuarios', 'suporte'),
    ],
    ('comercial', 'pro'): [
        ('leads', 'Gestao de leads', 'core'),
        ('atendimento-bot', 'Bot de atendimento (N8N)', 'core'),
        ('cadastro-cliente', 'Cadastro de clientes', 'core'),
        ('viabilidade', 'Consulta de viabilidade tecnica', 'core'),
        ('docs-validacao', 'Validacao de documentos', 'core'),
        ('hubsoft-sync', 'Integracao HubSoft (sync clientes)', 'integracao'),
        ('hubsoft-contrato', 'Envio automatico de contrato ao HubSoft', 'integracao'),
        ('dashboard-basico', 'Dashboard basico', 'relatorios'),
        ('relatorios-leads', 'Relatorio de leads', 'relatorios'),
        ('campanhas', 'Campanhas de trafego pago', 'core'),
        ('notificacoes', 'Sistema de notificacoes', 'core'),
        ('automacoes-followup', 'Automacoes de follow-up', 'automacao'),
        ('relatorios-vendas', 'Relatorio de vendas', 'relatorios'),
        ('relatorios-atendimentos', 'Relatorio de atendimentos', 'relatorios'),
        ('crm-pipeline', 'CRM Pipeline Kanban', 'crm'),
        ('crm-oportunidades', 'Oportunidades de venda', 'crm'),
        ('crm-tarefas', 'Tarefas e atividades', 'crm'),
        ('crm-metas', 'Metas de vendas', 'crm'),
        ('crm-segmentos', 'Segmentacao de leads', 'crm'),
        ('crm-retencao', 'Alertas de retencao', 'crm'),
        ('crm-desempenho', 'Dashboard de desempenho', 'crm'),
        ('validacao-ia', 'Validacao de documentos com IA', 'core'),
        ('automacoes-avancadas', 'Automacoes avancadas', 'automacao'),
        ('relatorios-conversao', 'Relatorio de conversao por etapa', 'relatorios'),
        ('relatorios-funil', 'Funil insights', 'relatorios'),
        ('com-usuarios-ilimitados', 'Usuarios ilimitados', 'suporte'),
        ('com-suporte-prioritario', 'Suporte prioritario', 'suporte'),
    ],

    # ── MARKETING ──────────────────────────────────────────────────────────
    ('marketing', 'starter'): [
        ('mkt-disparos-whatsapp', 'Disparos de WhatsApp', 'core'),
        ('mkt-disparos-email', 'Disparos de e-mail', 'core'),
        ('mkt-reguas-padrao', 'Reguas padrao prontas (16 fluxos)', 'automacao'),
        ('mkt-templates-msg', 'Templates de mensagens', 'core'),
        ('mkt-dashboard-basico', 'Dashboard basico de marketing', 'relatorios'),
        ('mkt-usuarios-2', '1 a 2 usuarios', 'suporte'),
    ],
    ('marketing', 'start'): [
        ('mkt-disparos-whatsapp', 'Disparos de WhatsApp', 'core'),
        ('mkt-disparos-email', 'Disparos de e-mail', 'core'),
        ('mkt-reguas-padrao', 'Reguas padrao prontas (16 fluxos)', 'automacao'),
        ('mkt-templates-msg', 'Templates de mensagens', 'core'),
        ('mkt-dashboard-basico', 'Dashboard basico de marketing', 'relatorios'),
        ('mkt-fluxos-personalizados', 'Fluxos de automacao personalizados', 'automacao'),
        ('mkt-rastreamento-campanhas', 'Rastreamento de campanhas de trafego', 'core'),
        ('mkt-segmentacao-base', 'Segmentacao de base de leads', 'core'),
        ('mkt-relatorios-campanha', 'Relatorios por campanha', 'relatorios'),
        ('mkt-usuarios-5', 'Ate 5 usuarios', 'suporte'),
    ],
    ('marketing', 'pro'): [
        ('mkt-disparos-whatsapp', 'Disparos de WhatsApp', 'core'),
        ('mkt-disparos-email', 'Disparos de e-mail', 'core'),
        ('mkt-reguas-padrao', 'Reguas padrao prontas (16 fluxos)', 'automacao'),
        ('mkt-templates-msg', 'Templates de mensagens', 'core'),
        ('mkt-dashboard-basico', 'Dashboard basico de marketing', 'relatorios'),
        ('mkt-fluxos-personalizados', 'Fluxos de automacao personalizados', 'automacao'),
        ('mkt-rastreamento-campanhas', 'Rastreamento de campanhas de trafego', 'core'),
        ('mkt-segmentacao-base', 'Segmentacao de base de leads', 'core'),
        ('mkt-relatorios-campanha', 'Relatorios por campanha', 'relatorios'),
        ('mkt-nutricao-avancada', 'Nutricao avancada de leads', 'automacao'),
        ('mkt-upsell-sva', 'Upsell de SVA automatizado', 'automacao'),
        ('mkt-otimizacao-trafego-ia', 'Otimizacao de trafego com IA', 'core'),
        ('mkt-relatorios-atribuicao', 'Relatorios de atribuicao', 'relatorios'),
        ('mkt-relatorios-cac-roas', 'Relatorios CAC, ROAS e LTV', 'relatorios'),
        ('mkt-usuarios-ilimitados', 'Usuarios ilimitados', 'suporte'),
        ('mkt-suporte-prioritario', 'Suporte prioritario', 'suporte'),
    ],

    # ── CS ─────────────────────────────────────────────────────────────────
    ('cs', 'starter'): [
        ('cs-clube-beneficios', 'Clube de Beneficios', 'core'),
        ('cs-reguas-retencao-basica', 'Reguas basicas de retencao (via Marketing)', 'automacao'),
        ('cs-carteirinha-digital', 'Carteirinha digital do cliente', 'core'),
        ('cs-parceiros-clube', 'Gestao de parceiros do clube', 'core'),
        ('cs-dashboard-basico', 'Dashboard basico de CS', 'relatorios'),
        ('cs-usuarios-2', '1 a 2 usuarios', 'suporte'),
    ],
    ('cs', 'start'): [
        ('cs-clube-beneficios', 'Clube de Beneficios', 'core'),
        ('cs-reguas-retencao-basica', 'Reguas basicas de retencao (via Marketing)', 'automacao'),
        ('cs-carteirinha-digital', 'Carteirinha digital do cliente', 'core'),
        ('cs-parceiros-clube', 'Gestao de parceiros do clube', 'core'),
        ('cs-dashboard-basico', 'Dashboard basico de CS', 'relatorios'),
        ('cs-nps-automatizado', 'NPS automatizado', 'core'),
        ('cs-relatorios-saude', 'Relatorios de saude da base', 'relatorios'),
        ('cs-alertas-inadimplencia', 'Alertas de inadimplencia', 'automacao'),
        ('cs-indicacoes', 'Programa de indicacoes', 'core'),
        ('cs-usuarios-5', 'Ate 5 usuarios', 'suporte'),
    ],
    ('cs', 'pro'): [
        ('cs-clube-beneficios', 'Clube de Beneficios', 'core'),
        ('cs-reguas-retencao-basica', 'Reguas basicas de retencao (via Marketing)', 'automacao'),
        ('cs-carteirinha-digital', 'Carteirinha digital do cliente', 'core'),
        ('cs-parceiros-clube', 'Gestao de parceiros do clube', 'core'),
        ('cs-dashboard-basico', 'Dashboard basico de CS', 'relatorios'),
        ('cs-nps-automatizado', 'NPS automatizado', 'core'),
        ('cs-relatorios-saude', 'Relatorios de saude da base', 'relatorios'),
        ('cs-alertas-inadimplencia', 'Alertas de inadimplencia', 'automacao'),
        ('cs-indicacoes', 'Programa de indicacoes', 'core'),
        ('cs-churn-prevention-ia', 'Prevencao de churn com IA', 'automacao'),
        ('cs-upsell-automatizado', 'Upsell automatizado', 'automacao'),
        ('cs-relatorios-avancados', 'Relatorios avancados de retencao', 'relatorios'),
        ('cs-sorteios', 'Sorteios e campanhas do clube', 'core'),
        ('cs-usuarios-ilimitados', 'Usuarios ilimitados', 'suporte'),
        ('cs-suporte-prioritario', 'Suporte prioritario', 'suporte'),
    ],
}


class Command(BaseCommand):
    help = 'Popula features dos planos conforme documentacao GTM.'

    def handle(self, *args, **options):
        NOMES = {
            ('comercial', 'starter'): 'Comercial Starter',
            ('comercial', 'start'): 'Comercial Start',
            ('comercial', 'pro'): 'Comercial Pro',
            ('marketing', 'starter'): 'Marketing Starter',
            ('marketing', 'start'): 'Marketing Start',
            ('marketing', 'pro'): 'Marketing Pro',
            ('cs', 'starter'): 'CS Starter',
            ('cs', 'start'): 'CS Start',
            ('cs', 'pro'): 'CS Pro',
        }

        for (modulo, tier), features in FEATURES.items():
            plano, created = Plano.objects.get_or_create(
                modulo=modulo,
                tier=tier,
                defaults={'nome': NOMES.get((modulo, tier), f'{modulo} {tier}'.title())},
            )
            if created:
                self.stdout.write(self.style.WARNING(f'Plano {modulo}/{tier} criado.'))

            plano.features.all().delete()
            for slug, nome, cat in features:
                FeaturePlano.objects.create(plano=plano, nome=nome, slug=slug, categoria=cat)

            self.stdout.write(self.style.SUCCESS(
                f'{plano.nome}: {len(features)} features'
            ))

        self.stdout.write(self.style.SUCCESS('\nSeed concluido.'))
