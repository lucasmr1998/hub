"""
Helpers de DocumentoLead — recalculo de flag `documentacao_validada` no lead.

Documentos obrigatorios pra considerar a documentacao do lead "validada":
selfie + doc_frente + doc_verso (mesma regra do admin).
"""
from django.utils import timezone

DOCS_OBRIGATORIOS = ['selfie', 'doc_frente', 'doc_verso']


def recalcular_documentacao_validada(lead):
    """
    Recalcula `lead.documentacao_validada` baseado nos DocumentoLead aprovados.

    - True se TODOS os tipos obrigatorios tem ao menos um doc aprovado.
    - False caso contrario.

    Retorna o valor novo (True / False).
    """
    docs = lead.documentos.all()
    todos_aprovados = all(
        any(d.tipo_documento == tipo and d.status == 'aprovado' for d in docs)
        for tipo in DOCS_OBRIGATORIOS
    )

    if todos_aprovados:
        if not lead.documentacao_validada:
            lead.documentacao_validada = True
            lead.data_documentacao_validada = timezone.now()
            lead.save(update_fields=['documentacao_validada', 'data_documentacao_validada'])
    else:
        if lead.documentacao_validada:
            lead.documentacao_validada = False
            lead.save(update_fields=['documentacao_validada'])

    return lead.documentacao_validada
