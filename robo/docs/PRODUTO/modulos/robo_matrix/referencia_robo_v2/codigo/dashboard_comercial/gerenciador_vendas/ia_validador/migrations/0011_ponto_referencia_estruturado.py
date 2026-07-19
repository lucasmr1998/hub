"""Ajusta a regra `coleta_ponto_referencia` pra coletar endereço estruturado.

A pergunta no Matrix agora menciona os 3 cenários (casa térrea, apartamento,
condomínio fechado, empresa). O extractor no engine usa OpenAI pra:
1. Detectar o tipo de imóvel pela resposta livre
2. Extrair componentes (nome do edifício/condomínio, bloco, andar, apto/casa)
3. Montar string padronizada tipo:
   - [CASA] perto da padaria X
   - [APARTAMENTO] Edif. Aurora - Bloco B - 5º andar - Apto 502. Ref: ...
   - [CONDOMÍNIO] Cond. Jardim - Quadra 3 - Casa 12. Ref: ...
   - [EMPRESA] Edif. Centro Empresarial - 3º andar - Sala 305

Salva no campo `ponto_referencia` do LeadProspecto.
"""
from django.db import migrations


NOVA_PERGUNTA = (
    'Pra ajudar nosso time na instalação:\n'
    '\n'
    'Casa térrea / Empresa térrea: me passe um ponto de referência (perto de quê?)\n'
    'Apartamento: nome do edifício, bloco/torre, andar e número do apto\n'
    'Condomínio fechado: nome do condomínio, quadra/bloco e número da casa\n'
    '\n'
    'Pode mandar tudo em uma única mensagem.'
)


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')

    r = RegraValidacao.objects.filter(question_id='coleta_ponto_referencia').first()
    if not r:
        print('  ! coleta_ponto_referencia não encontrada — pulando')
        return

    r.pergunta_padrao = NOVA_PERGUNTA
    r.msg_sucesso = 'Anotado! ##263A## Vai ajudar bastante nossa equipe na instalação.'
    r.msg_erro = (
        'Pode descrever melhor? Pode ser só um ponto de referência (casa térrea/empresa) '
        'ou os detalhes do apartamento/condomínio (bloco, andar, apto/casa).'
    )
    # Aceita pular já estava em True — mantém
    r.save()
    print('  ✓ coleta_ponto_referencia: pergunta atualizada (estruturada via IA no engine)')


def reverter(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    r = RegraValidacao.objects.filter(question_id='coleta_ponto_referencia').first()
    if r:
        r.pergunta_padrao = 'Tem algum ponto de referência perto da sua casa?'
        r.msg_sucesso = 'Anotado, vai ajudar bastante! ##263A##'
        r.msg_erro = 'Pode descrever um ponto próximo (mercado, escola, etc)?'
        r.save()


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0010_docs_apos_confirmacao_status_pendente'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
