"""
Adiciona condicao 'score_externo igual aprovado' em todas as regras do tenant
Nuvyon que tenham acoes de contrato HubSoft ou abertura de OS.

Idempotente: nao duplica caso a condicao ja exista.

A1 — Aplicar a gate de score nas regras existentes pra que subam ja
protegidas, sem depender de edicao manual na UI.
"""
from django.db import migrations


CONDICAO_SCORE = {
    'tipo': 'score_externo',
    'campo': '',
    'operador': 'igual',
    'valor': 'aprovado',
}

ACOES_QUE_EXIGEM_SCORE = {
    'gerar_contrato_hubsoft',
    'assinar_contrato_hubsoft',
    'abrir_os_hubsoft',
}

TENANT_SLUG = 'nuvyon'


def adicionar_gate_score(apps, schema_editor):
    Tenant = apps.get_model('sistema', 'Tenant')
    Regra = apps.get_model('crm', 'RegraPipelineEstagio')

    tenant = Tenant.objects.filter(slug=TENANT_SLUG).first()
    if not tenant:
        return

    regras = Regra.objects.filter(tenant=tenant, ativo=True)
    for regra in regras:
        acoes = regra.acoes or []
        tipos_acao = {a.get('tipo') for a in acoes if isinstance(a, dict)}
        if not (tipos_acao & ACOES_QUE_EXIGEM_SCORE):
            continue

        condicoes = list(regra.condicoes or [])
        ja_tem = any(
            isinstance(c, dict) and c.get('tipo') == 'score_externo'
            for c in condicoes
        )
        if ja_tem:
            continue

        condicoes.append(dict(CONDICAO_SCORE))
        regra.condicoes = condicoes
        regra.save(update_fields=['condicoes'])


def remover_gate_score(apps, schema_editor):
    Tenant = apps.get_model('sistema', 'Tenant')
    Regra = apps.get_model('crm', 'RegraPipelineEstagio')

    tenant = Tenant.objects.filter(slug=TENANT_SLUG).first()
    if not tenant:
        return

    for regra in Regra.objects.filter(tenant=tenant):
        condicoes = list(regra.condicoes or [])
        novas = [c for c in condicoes if not (isinstance(c, dict) and c.get('tipo') == 'score_externo')]
        if len(novas) != len(condicoes):
            regra.condicoes = novas
            regra.save(update_fields=['condicoes'])


class Migration(migrations.Migration):
    dependencies = [
        ('crm', '0020_regrapipelineestagio_total_acoes_efetivas_and_more'),
        ('leads', '0007_leadprospecto_score_atualizado_em_and_more'),
    ]

    operations = [
        migrations.RunPython(adicionar_gate_score, reverse_code=remover_gate_score),
    ]
