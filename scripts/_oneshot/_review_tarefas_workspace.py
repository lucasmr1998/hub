"""Lista tarefas em aberto do Workspace (tenant Aurora HQ id=3) - read-only."""
from apps.workspace.models import Tarefa

abertas = Tarefa.objects.filter(tenant_id=3).exclude(status="concluida").order_by("-id")
print(f"Total em aberto: {abertas.count()}\n")

por_status = {}
for t in abertas:
    por_status.setdefault(t.status, []).append(t)

for status in sorted(por_status.keys()):
    tarefas = por_status[status]
    print(f"== {status.upper()} ({len(tarefas)}) ==")
    for t in tarefas:
        prio = getattr(t, "prioridade", "?")
        titulo = (t.titulo or "")[:90]
        print(f"  #{t.id} [{prio}] {titulo}")
    print()
