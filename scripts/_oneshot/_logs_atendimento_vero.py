"""Read-only logs do fluxo 23 (sem expor credenciais)."""
from apps.comercial.atendimento.models import (
    FluxoAtendimento, AtendimentoFluxo, LogFluxoAtendimento, NodoFluxoAtendimento
)

fluxo = FluxoAtendimento.objects.get(id=23)
ats = list(AtendimentoFluxo.objects.filter(fluxo=fluxo).order_by("-id")[:2])
for at in ats:
    print(f"== Atendimento #{at.id} ==")
    print(f"   status: {at.status}")
    print(f"   nodo_atual_id: {at.nodo_atual_id}")
    var = getattr(at, "variaveis_contexto", None)
    if var is None:
        var = getattr(at, "dados_respostas", None)
    print(f"   variaveis/dados: {var}")
    logs = LogFluxoAtendimento.objects.filter(atendimento=at).order_by("id")
    print(f"   {logs.count()} logs:")
    for log in logs:
        ninfo = ""
        if log.nodo_id:
            try:
                n = NodoFluxoAtendimento.objects.get(id=log.nodo_id)
                ninfo = f"{n.tipo}/{n.subtipo}[id={n.id}]"
            except Exception:
                ninfo = f"id={log.nodo_id}"
        ts = log.data_execucao.strftime("%H:%M:%S") if log.data_execucao else 'N/A'
        print(f"     [{ts}] {ninfo} status={log.status} msg={log.mensagem[:150]}")
        if log.dados:
            d = str(log.dados)[:500]
            print(f"        dados: {d}")
    print()
