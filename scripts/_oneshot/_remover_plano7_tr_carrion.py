"""
Remove Plano 7 (800 Mega + Globoplay Canais + Chip 20GB) do fluxo Vero da TR Carrion.
Renumera planos 8-11 -> 7-10 e atualiza textos de validacao de "1 a 11" para "1 a 10".

Rodar em producao:
  python manage.py shell < scripts/_remover_plano7_tr_carrion.py
"""
import json
from apps.sistema.models import Tenant
from apps.comercial.atendimento.models import NodoFluxoAtendimento, FluxoAtendimento

TENANT_SLUG = 'tr-carrion'
FLUXO_NOME = 'Atendimento Vero - V1'

NOVA_LISTA = (
    '1. 550 Mega + Wi-Fi 6 — R$ 113,90/mês\n'
    '2. 550 Mega + Chip 10GB — R$ 118,90/mês\n'
    '3. 750 Mega + Wi-Fi 6 — R$ 122,90/mês\n'
    '4. 800 Mega + YouTube Premium — R$ 134,90/mês\n'
    '5. 800 Mega + Max — R$ 134,90/mês\n'
    '6. 800 Mega + Telecine — R$ 134,90/mês\n'
    '7. 800 Mega + Disney Padrão + Chip 20GB — R$ 139,90/mês\n'
    '8. 800 Mega + Globoplay Canais Premium + HBO Max + Chip 60GB — R$ 149,90/mês\n'
    '9. 800 Mega + Premiere — R$ 150,00/mês\n'
    '10. 800 Mega + Disney Plus — R$ 155,00/mês'
)

try:
    tenant = Tenant.objects.get(slug=TENANT_SLUG)
    fluxo = FluxoAtendimento.objects.get(tenant=tenant, nome=FLUXO_NOME)
except Tenant.DoesNotExist:
    print(f"ERRO: tenant '{TENANT_SLUG}' nao encontrado.")
    raise SystemExit(1)
except FluxoAtendimento.DoesNotExist:
    print(f"ERRO: fluxo '{FLUXO_NOME}' nao encontrado no tenant.")
    raise SystemExit(1)

nodos = NodoFluxoAtendimento.objects.filter(tenant=tenant, fluxo=fluxo)
atualizados = 0

for nodo in nodos:
    cfg = nodo.configuracao or {}
    mudou = False

    # Nodo apresenta_planos: atualiza system_prompt com nova lista
    if nodo.tipo == 'ia_respondedor' and 'system_prompt' in cfg:
        prompt = cfg['system_prompt']
        if '7. 800 Mega + Globoplay Canais + Chip 20GB' in prompt:
            # Substitui o bloco de planos inteiro
            inicio = prompt.find('1. 550 Mega')
            fim = prompt.find('\n\nMe responde')
            if inicio != -1 and fim != -1:
                cfg['system_prompt'] = prompt[:inicio] + NOVA_LISTA + prompt[fim:]
                mudou = True
                print(f"[OK] Nodo {nodo.id} ({nodo.tipo}): lista de planos atualizada.")

    # Nodo escolha_plano: atualiza descricao e prompt_validacao de "1 a 11" -> "1 a 10"
    if '1 a 11' in json.dumps(cfg):
        cfg_str = json.dumps(cfg).replace('1 a 11', '1 a 10')
        cfg = json.loads(cfg_str)
        mudou = True
        print(f"[OK] Nodo {nodo.id} ({nodo.tipo}): range atualizado de '1 a 11' para '1 a 10'.")

    if mudou:
        nodo.configuracao = cfg
        nodo.save()
        atualizados += 1

print(f"\nConcluido: {atualizados} nodo(s) atualizado(s).")
