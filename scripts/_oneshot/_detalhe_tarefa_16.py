"""Detalhe COMPLETO da tarefa #16."""
from apps.workspace.models import Tarefa

t = Tarefa.objects.get(id=16)
print(f"#{t.id} | {t.titulo}")
print(f"Status: {t.status} | Prio: {getattr(t, 'prioridade', '?')} | Tenant: {t.tenant_id}")
print(f"Criado: {t.criado_em.strftime('%Y-%m-%d')}")
print(f"Tamanho descricao: {len(t.descricao or '')} chars")
print()
print("=" * 70)
print("DESCRICAO COMPLETA:")
print("=" * 70)
print(t.descricao or "(vazia)")
