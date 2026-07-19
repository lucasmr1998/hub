"""Migra o flow.json do Matrix substituindo webhooks N8N pela nova API IA Validação.

Uso:
    python tools/migrar_flow.py \
        --entrada fluxos/flow.json \
        --saida fluxos/flow_megalink_v2.json \
        --api-url https://robovendas.megalinkpiaui.com.br:8090

O script:
1. Atualiza a variável `webhook_aurora` (set node 5004) para apontar para a nova API
2. Reescreve api_15 (id 6037) e api_16 (id 6050) para usar /validar (com etapa, fluxo)
3. Reconfigura o store dos nós API para capturar a resposta JSON da nova API
4. Adiciona variáveis de saída (resposta_valida, mensagem_bot, proxima_etapa, intencao)
   caso não existam ainda.

Nada é destruído: o output é um arquivo novo. O flow.json original fica intacto.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path


# IDs dos nós (descobertos via inspeção do flow.json original)
NODE_VAR_SERVIDOR = 5004      # set var_servidor (contém URL do webhook_aurora)
NODE_API_CONSULTA_CEP = 5763  # api_consulta_cep — usa {#webhook_aurora}
NODE_API_VALIDA_RESPOSTA = 5784  # api_valida_resposta — usa {#webhook_aurora}
NODE_API_15 = 6037            # webhook geral hardcoded N8N
NODE_API_16 = 6050            # DynamicValidator hardcoded N8N

# IDs das variáveis Matrix usadas pelos nós
VAR_WEBHOOK_AURORA = 3620089
# Variáveis novas que precisamos garantir (mapeamento: nome → id sugerido)
NEW_VARS = {
    'resposta_valida': 9000001,
    'mensagem_bot':    9000002,
    'proxima_etapa':   9000003,
    'intencao':        9000004,
    'cpf_extraido':    9000005,
    'cidade_extraida': 9000006,
    'cep_extraido':    9000007,
    'tentativas':      9000008,
    'etapa_atual':     9000009,
}


def garantir_variaveis(flow: dict) -> dict[str, int]:
    """Adiciona variáveis novas se não existirem. Retorna mapping nome→id usado."""
    variaveis = flow.setdefault('variaveis', {})
    # Indexa por nome para detectar existentes
    existentes_por_nome = {
        v.get('name'): int(vid)
        for vid, v in variaveis.items()
        if isinstance(v, dict) and v.get('name')
    }

    resultado: dict[str, int] = {}
    for nome, id_sugerido in NEW_VARS.items():
        if nome in existentes_por_nome:
            resultado[nome] = existentes_por_nome[nome]
        else:
            variaveis[str(id_sugerido)] = {'name': nome, 'value': ''}
            resultado[nome] = id_sugerido
    return resultado


def atualizar_var_servidor(flow: dict, nova_url: str) -> bool:
    """Atualiza o set node que define webhook_aurora para a nova API."""
    for node in flow['flow']:
        if node.get('id') == NODE_VAR_SERVIDOR:
            data = node.get('data', {})
            variables = data.get('variables', [])
            values = data.get('values', [])
            for idx, vid in enumerate(variables):
                if vid == VAR_WEBHOOK_AURORA and idx < len(values):
                    values[idx] = f'{nova_url}/validar/matrix'
                    return True
    return False


def _store_padrao(vars_map: dict[str, int]) -> dict:
    """Retorna config de store que captura os campos da resposta da nova API."""
    return {
        'filter': 1,
        'variable': [
            vars_map['resposta_valida'],
            vars_map['mensagem_bot'],
            vars_map['proxima_etapa'],
            vars_map['intencao'],
            vars_map['cpf_extraido'],
            vars_map['cidade_extraida'],
            vars_map['cep_extraido'],
            vars_map['tentativas'],
        ],
        'returned': [
            'valido',
            'mensagem_bot',
            'proxima_etapa',
            'intencao_detectada',
            'dados_extraidos.cpf',
            'dados_extraidos.cidade',
            'dados_extraidos.cep',
            'tentativas',
        ],
    }


def atualizar_node_api(
    flow: dict,
    node_id: int,
    nova_url: str,
    body: dict,
    vars_map: dict[str, int],
    timeout: int = 25,
) -> bool:
    """Reescreve um nó de API: URL, body, headers e store."""
    for node in flow['flow']:
        if node.get('id') == node_id:
            data = node.setdefault('data', {})
            api = data.setdefault('api', {})
            api['url'] = nova_url
            api['method'] = 1  # POST
            api['timeout'] = timeout
            api['async'] = 0

            data['headers'] = {
                'key': ['Content-Type'],
                'value': ['application/json'],
            }
            data['body'] = {'body': json.dumps(body, indent=2, ensure_ascii=False)}
            data['store'] = _store_padrao(vars_map)
            return True
    return False


def migrar(entrada: Path, saida: Path, api_url: str) -> None:
    api_url = api_url.rstrip('/')
    flow = json.loads(entrada.read_text(encoding='utf-8'))
    flow = deepcopy(flow)  # nunca modificar in-place

    print(f'→ Lendo {entrada} ({len(flow.get("flow", []))} nodes)')

    vars_map = garantir_variaveis(flow)
    print(f'→ Variáveis garantidas: {", ".join(vars_map.keys())}')

    if atualizar_var_servidor(flow, api_url):
        print(f'  ✓ webhook_aurora → {api_url}/validar/matrix')
    else:
        print('  ⚠ webhook_aurora set node não encontrado')

    # api_15: substituir por chamada genérica /validar/matrix
    if atualizar_node_api(
        flow, NODE_API_15,
        nova_url=f'{api_url}/validar/matrix',
        body={
            'question': '{#pergunta_cliente}',
            'answer': '{#resposta_cliente}',
            'telefone': '{#CONTATO.TELEFONE}',
        },
        vars_map=vars_map,
    ):
        print(f'  ✓ api_15 → {api_url}/validar/matrix')

    # api_16: endpoint principal /validar com etapa do fluxo
    if atualizar_node_api(
        flow, NODE_API_16,
        nova_url=f'{api_url}/validar',
        body={
            'telefone': '{#CONTATO.TELEFONE}',
            'etapa': '{#etapa_atual}',
            'pergunta': '{#pergunta_cliente}',
            'resposta': '{#resposta_cliente}',
            'fluxo': 'vendas_megalink',
        },
        vars_map=vars_map,
    ):
        print(f'  ✓ api_16 → {api_url}/validar')

    # api_consulta_cep: redirecionar para /validar com etapa=coleta_cep
    if atualizar_node_api(
        flow, NODE_API_CONSULTA_CEP,
        nova_url=f'{api_url}/validar',
        body={
            'telefone': '{#CONTATO.TELEFONE}',
            'etapa': 'coleta_cep',
            'pergunta': 'Você pode me passar o CEP do local?',
            'resposta': '{#prospecto_cep}',
            'fluxo': 'vendas_megalink',
        },
        vars_map=vars_map,
        timeout=30,
    ):
        print(f'  ✓ api_consulta_cep → {api_url}/validar (etapa=coleta_cep)')

    # api_valida_resposta: redirecionar para /validar com etapa=livre (genérico)
    if atualizar_node_api(
        flow, NODE_API_VALIDA_RESPOSTA,
        nova_url=f'{api_url}/validar',
        body={
            'telefone': '{#CONTATO.TELEFONE}',
            'etapa': '{#etapa_atual}',
            'pergunta': '{#pergunta_cliente}',
            'resposta': '{#resposta_cliente}',
            'fluxo': 'vendas_megalink',
        },
        vars_map=vars_map,
    ):
        print(f'  ✓ api_valida_resposta → {api_url}/validar')

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n✓ Gerado: {saida}')
    print(f'  → Importe no Matrix como um fluxo de teste antes de substituir o atual.')


def main() -> int:
    p = argparse.ArgumentParser(description='Migra flow.json do Matrix para usar a nova API IA Validação')
    p.add_argument('--entrada', type=Path, default=Path('fluxos/flow.json'),
                   help='Caminho do flow.json original')
    p.add_argument('--saida', type=Path, default=Path('fluxos/flow_megalink_v2.json'),
                   help='Caminho do flow.json migrado')
    p.add_argument('--api-url', default='https://robovendas.megalinkpiaui.com.br:8090',
                   help='URL base da nova API IA Validação')
    args = p.parse_args()

    if not args.entrada.exists():
        print(f'Erro: arquivo de entrada não encontrado: {args.entrada}', file=sys.stderr)
        return 1

    migrar(args.entrada, args.saida, args.api_url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
