"""Renomeia os marcadores da engine em `OportunidadeVenda.dados_custom` pro padrão
interno (prefixo `_`).

Motivo: o painel "Dados personalizados" do CRM lista as chaves de `dados_custom`
pro usuário e OCULTA as que começam com `_` (convenção que já existia no template).
Os marcadores da engine são bookkeeping (data em que o fluxo processou aquela
oportunidade), não são dado do cliente, e estavam vazando pra tela.

CRÍTICO: as varreduras usam essas chaves como freio ("não reprocessar quem já tem o
marcador"). Renomear só o seed sem renomear os dados existentes faria a engine
reanalisar tudo de novo (nota duplicada + custo de LLM). Por isso a renomeação dos
dados vem junto, no mesmo deploy.

Idempotente: só toca em quem tem a chave antiga; reversível.
"""
from django.db import migrations

RENOMEAR = {
    'analise_atendimento_matrix': '_analise_atendimento_matrix',
    'recuperacao_enviada': '_recuperacao_iniciada',   # nome antigo do fluxo de recuperação
    'recuperacao_iniciada': '_recuperacao_iniciada',
}


def _migrar(apps, chaves):
    Oportunidade = apps.get_model('crm', 'OportunidadeVenda')
    total = 0
    for antiga, nova in chaves.items():
        qs = Oportunidade.objects.filter(dados_custom__has_key=antiga)
        for op in qs.iterator(chunk_size=200):
            dados = op.dados_custom or {}
            if antiga not in dados:
                continue
            dados[nova] = dados.pop(antiga)
            op.dados_custom = dados
            op.save(update_fields=['dados_custom'])
            total += 1
    return total


def frente(apps, schema_editor):
    _migrar(apps, RENOMEAR)


def tras(apps, schema_editor):
    # Volta só o par canônico (os dois nomes antigos colapsaram em um).
    _migrar(apps, {'_analise_atendimento_matrix': 'analise_atendimento_matrix',
                   '_recuperacao_iniciada': 'recuperacao_iniciada'})


class Migration(migrations.Migration):
    dependencies = [
        ('automacao', '0011_fluxo_agenda_intervalo_minutos_and_more'),
        ('crm', '0029_herdar_atribuicao_do_lead'),
    ]
    operations = [
        migrations.RunPython(frente, tras),
    ]
