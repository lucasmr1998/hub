"""
Fix dos 3 erros de validacao no fluxo Vero (id=23):
1. Webhook sem URL -> trocar pra notificacao_sistema
2. Nodos transferir_humano sem saida -> conectar todos a um nodo de finalizacao
3. Sem nodo finalizacao -> criar
"""
from django.db import transaction
from apps.sistema.models import Tenant
from apps.comercial.atendimento.models import (
    FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento
)

FLUXO_ID = 23
tenant = Tenant.objects.get(slug='tr-carrion')
fluxo = FluxoAtendimento.objects.get(id=FLUXO_ID, tenant=tenant)

with transaction.atomic():
    # 1. Webhook -> notificacao_sistema (sem URL)
    webhooks = NodoFluxoAtendimento.objects.filter(fluxo=fluxo, tipo='acao', subtipo='webhook')
    n_webhook = webhooks.count()
    for w in webhooks:
        # preserva o template ja escrito (template fica em configuracao)
        # so muda subtipo
        w.subtipo = 'notificacao_sistema'
        cfg = w.configuracao or {}
        # garante que tem template + titulo
        if 'titulo' not in cfg:
            cfg['titulo'] = 'Nova solicitacao Vero (Agente IA)'
        # remove campos especificos de webhook
        for k in ['url', 'metodo']:
            cfg.pop(k, None)
        w.configuracao = cfg
        w.save()
        print(f"[OK] Nodo {w.id} convertido: webhook -> notificacao_sistema")
    print(f"[OK] {n_webhook} webhook(s) convertido(s)")

    # 2. Cria nodo finalizacao (se nao existir)
    fim = NodoFluxoAtendimento.objects.filter(fluxo=fluxo, tipo='finalizacao').first()
    if not fim:
        # proxima ordem disponivel
        ultima_ordem = NodoFluxoAtendimento.objects.filter(fluxo=fluxo).order_by('-ordem').first()
        ordem_nova = (ultima_ordem.ordem + 1) if ultima_ordem else 100
        fim = NodoFluxoAtendimento.objects.create(
            tenant=tenant, fluxo=fluxo, tipo='finalizacao', subtipo='fim_fluxo',
            configuracao={'titulo': 'Fim do fluxo'},
            pos_x=4200, pos_y=300, ordem=ordem_nova,
        )
        print(f"[OK] Nodo finalizacao criado: id={fim.id}, ordem={ordem_nova}")
    else:
        print(f"[OK] Nodo finalizacao ja existia: id={fim.id}")

    # 3. Conecta todos os transferir_humano sem saida ao nodo fim
    handoffs = NodoFluxoAtendimento.objects.filter(fluxo=fluxo, tipo='transferir_humano')
    conectados = 0
    for h in handoffs:
        ja_tem_saida = ConexaoNodoAtendimento.objects.filter(fluxo=fluxo, nodo_origem=h).exists()
        if not ja_tem_saida:
            ConexaoNodoAtendimento.objects.create(
                tenant=tenant, fluxo=fluxo,
                nodo_origem=h, nodo_destino=fim, tipo_saida='default',
            )
            conectados += 1
            print(f"[OK] Conectado: transferir_humano #{h.id} -> fim #{fim.id}")
    print(f"[OK] {conectados} conexoes adicionadas pros handoffs")


print()
print("=" * 60)
print("VALIDACAO FIXADA")
print("=" * 60)
print(f"Total nodos:    {NodoFluxoAtendimento.objects.filter(fluxo=fluxo).count()}")
print(f"Total conexoes: {ConexaoNodoAtendimento.objects.filter(fluxo=fluxo).count()}")
print()
print(f"Editor: https://app.hubtrix.com.br/comercial/atendimento/fluxos/{FLUXO_ID}/editor/")
