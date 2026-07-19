"""Atualiza mensagens das regras de documentação (selfie/frente/verso).

A IA, ao validar com sucesso, chama POST /api/leads/imagens/ pra registrar.
O extractor de imagem agora aceita filename do WhatsApp e constrói a URL
Matrix automaticamente (https://megalink.matrixdobrasil.ai/.../msgs/YYYY/MM/{filename}).

Se cliente responder texto (não imagem), msg_erro pede pra reenviar a foto.
"""
from django.db import migrations


REGRAS_DOCS = {
    'documentacao_selfie': {
        'descricao_imagem': 'selfie_com_doc',
        'msg_sucesso':       'Selfie recebida! ##263A##',
        'msg_erro':          'Não consegui identificar uma imagem. Pode enviar a *foto* como anexo no chat?',
        'msg_max_tentativas':'Houve dificuldade com a imagem. Vou transferir pra um atendente concluir.',
    },
    'documentacao_frente_doc': {
        'descricao_imagem': 'frente_doc',
        'msg_sucesso':       'Frente recebida! ##263A##',
        'msg_erro':          'Não consegui identificar uma imagem. Envie a *foto da frente* do documento como anexo.',
        'msg_max_tentativas':'Houve dificuldade. Vou transferir pra um atendente.',
    },
    'documentacao_verso_doc': {
        'descricao_imagem': 'verso_doc',
        'msg_sucesso':       'Documentação completa! ##1f680##',
        'msg_erro':          'Não consegui identificar uma imagem. Envie a *foto do verso* do documento como anexo.',
        'msg_max_tentativas':'Houve dificuldade. Vou transferir pra um atendente.',
    },
}


def aplicar(apps, schema_editor):
    RegraValidacao = apps.get_model('ia_validador', 'RegraValidacao')
    atualizadas = 0
    for qid, campos in REGRAS_DOCS.items():
        try:
            r = RegraValidacao.objects.get(question_id=qid)
            for k, v in campos.items():
                setattr(r, k, v)
            r.save()
            atualizadas += 1
        except RegraValidacao.DoesNotExist:
            print(f'  ⚠ regra {qid!r} não existe')
    print(f'  ✓ {atualizadas} regras de documentação atualizadas')


def reverter(apps, schema_editor):
    pass  # mensagens são informativas, sem reverter


class Migration(migrations.Migration):
    dependencies = [
        ('ia_validador', '0006_confirmacao_endereco_apos_cep'),
    ]
    operations = [
        migrations.RunPython(aplicar, reverter),
    ]
