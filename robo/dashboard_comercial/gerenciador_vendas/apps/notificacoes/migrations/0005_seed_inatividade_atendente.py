"""Cria TipoNotificacao 'inatividade_atendente' pra todos os tenants ativos.

Usado pelo cron `cron_inatividade_atendente` (v3 reatribuicao).
"""
from django.db import migrations


def seed(apps, schema_editor):
    Tenant = apps.get_model('sistema', 'Tenant')
    TipoNotificacao = apps.get_model('notificacoes', 'TipoNotificacao')

    for tenant in Tenant.objects.filter(ativo=True):
        TipoNotificacao.objects.update_or_create(
            tenant=tenant,
            codigo='inatividade_atendente',
            defaults={
                'nome': 'Atendente Sem Resposta',
                'descricao': 'Atendente assumiu a conversa mas nao responde ha mais do limite configurado na fila. Notifica administradores.',
                'template_padrao': 'Conversa #{conversa_id} sem resposta ha {tempo_sem_responder_min}min. Atendente: {agente_nome}.',
                'prioridade_padrao': 'alta',
                'icone': 'fas fa-user-clock',
                'ativo': True,
            },
        )


def reverse(apps, schema_editor):
    TipoNotificacao = apps.get_model('notificacoes', 'TipoNotificacao')
    TipoNotificacao.objects.filter(codigo='inatividade_atendente').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('notificacoes', '0004_notificacaoleiturabroadcast'),
        ('sistema', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
