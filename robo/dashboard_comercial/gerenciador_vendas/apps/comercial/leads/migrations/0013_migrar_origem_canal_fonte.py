"""Migra dados antigos de `origem` e `canal_entrada` pros novos
campos `canal` e `fonte` no LeadProspecto.

Mapeamento (regra de classificacao):
- canais fisicos (whatsapp, telefone, email, site, sms) -> canal
- fontes/plataformas (facebook, instagram, google, indicacao, outros) -> fonte

Logica: usa `canal_entrada` primeiro se preenchido, senao usa `origem`.
Eh idempotente: se canal/fonte ja preenchidos, nao sobrescreve.

Fase 1 do refactor do modelo de origem. Ver
docs/PRODUTO/modulos/comercial/modelo_origem_lead_e_oportunidade.md
"""
from django.db import migrations


# Valor antigo -> (campo_destino, valor_novo)
# Cobre valores reais observados em dev + prod (consulta 2026-06-29).
MAPA_VALORES = {
    # Canais fisicos
    'whatsapp':     ('canal', 'whatsapp'),
    'whatsapp_n8n': ('canal', 'whatsapp'),  # variante via bot N8N
    'telefone':     ('canal', 'telefone'),
    'email':        ('canal', 'email'),
    'site':         ('canal', 'site'),
    'simulador':    ('canal', 'site'),  # simulador eh formulario do site
    'widget':       ('canal', 'site'),  # widget de chat no site
    'manual':       ('canal', 'manual'),
    # Fontes (plataformas)
    'facebook':  ('fonte', 'facebook'),
    'instagram': ('fonte', 'instagram'),
    'google':    ('fonte', 'google'),
    'indicacao': ('fonte', 'indicacao'),
    'outros':    ('fonte', 'outros'),
}


def migrar_origem_canal_fonte(apps, schema_editor):
    """Forward: popula canal/fonte a partir de canal_entrada e origem."""
    Lead = apps.get_model('leads', 'LeadProspecto')
    total = 0
    atualizados = 0
    for lead in Lead.objects.all():
        total += 1
        if lead.canal and lead.fonte:
            continue  # ja preenchido (idempotente)

        # Prefere canal_entrada (mais recente), fallback origem
        valor_antigo = (lead.canal_entrada or lead.origem or '').strip().lower()
        if not valor_antigo or valor_antigo not in MAPA_VALORES:
            continue

        campo_destino, valor_novo = MAPA_VALORES[valor_antigo]
        if campo_destino == 'canal' and not lead.canal:
            lead.canal = valor_novo
            atualizados += 1
        elif campo_destino == 'fonte' and not lead.fonte:
            lead.fonte = valor_novo
            atualizados += 1
        lead.save(update_fields=['canal', 'fonte'])

    print(f'  Total leads: {total} | Atualizados: {atualizados}')


def reverter(apps, schema_editor):
    """Reverse: nao faz nada (dados antigos ainda em origem/canal_entrada)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0012_leadprospecto_canal_leadprospecto_fonte'),
    ]

    operations = [
        migrations.RunPython(migrar_origem_canal_fonte, reverter),
    ]
