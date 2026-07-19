"""Migra flow.json do Matrix para o validador v2.

Estratégia:
- Substitui o `webhook_aurora` antigo pelo novo endpoint /ia/validar
- Em cada nó API que chamava o validador, atualiza:
    - URL → {api_url}/validar
    - body → {question, answer, cellphone, lead_id, question_id}
    - store → captura {valido, message, extracted_data.*, transbordo, intent}

O fluxo Matrix NÃO precisa ser reescrito do zero — só os 2 nós que chamavam o
webhook_aurora (api_consulta_cep id 5763, api_valida_resposta id 5784).

Adicionalmente, é necessário criar uma variável `question_id_atual` no Matrix
e setá-la antes de cada `sol_*` — esse trabalho é manual no editor visual.

Uso:
    python tools/migrar_flow_v2.py \\
        --entrada fluxos/flow.json \\
        --saida fluxos/flow_v2.json \\
        --api-url https://robovendas.megalinkpiaui.com.br/ia
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path


# Nós que chamavam o webhook_aurora antigo (descobertos via auditoria)
NODE_API_VALIDA_RESPOSTA = 5784   # validador genérico
NODE_API_CONSULTA_CEP = 5763      # consulta específica de CEP

# Nós N8N hardcoded antigos (também substituir)
NODE_API_15 = 6037
NODE_API_16 = 6050

# Variável do Matrix que aponta pra URL do validador
VAR_WEBHOOK_AURORA = 3620089

# Variáveis novas que o store captura (sobreescreve se existirem)
NEW_VARS = {
    'resp_valido':           9200001,
    'resp_message':          9200002,
    'resp_transbordo':       9200003,
    'resp_intent':           9200004,
    'resp_extracted_cpf':    9200005,
    'resp_extracted_cep':    9200006,
    'resp_extracted_cidade': 9200007,
    'resp_extracted_bairro': 9200008,
    'resp_extracted_rua':    9200009,
    'resp_extracted_estado': 9200010,
    'resp_regra':            9200011,
    'question_id_atual':     9200012,   # você seta antes de cada sol no Matrix
}


def _payload_validar_v2() -> dict:
    """Body que vai ser enviado pela API node do Matrix."""
    return {
        'question': '{#pergunta_cliente}',
        'answer': '{#resposta_cliente}',
        'cellphone': '{#CONTATO.TELEFONE}',
        'lead_id': '{#id_lead}',
        'question_id': '{#question_id_atual}',
    }


def _store_validar_v2(vars_map: dict[str, int]) -> dict:
    """Store que captura a resposta do /validar v2."""
    return {
        'filter': 1,
        'variable': [
            vars_map['resp_valido'],
            vars_map['resp_message'],
            vars_map['resp_transbordo'],
            vars_map['resp_intent'],
            vars_map['resp_extracted_cpf'],
            vars_map['resp_extracted_cep'],
            vars_map['resp_extracted_cidade'],
            vars_map['resp_extracted_bairro'],
            vars_map['resp_extracted_rua'],
            vars_map['resp_extracted_estado'],
            vars_map['resp_regra'],
        ],
        'returned': [
            'valido',
            'message',
            'transbordo',
            'intent',
            'extracted_data.cpf_cnpj',
            'extracted_data.cep',
            'extracted_data.cidade',
            'extracted_data.bairro',
            'extracted_data.rua',
            'extracted_data.estado',
            'regra_aplicada',
        ],
    }


def garantir_variaveis(flow: dict) -> dict[str, int]:
    """Adiciona variáveis novas se ainda não existirem."""
    variaveis = flow.setdefault('variaveis', {})
    existentes_por_nome = {
        v.get('name'): int(vid)
        for vid, v in variaveis.items() if isinstance(v, dict) and v.get('name')
    }
    resultado: dict[str, int] = {}
    for nome, id_sug in NEW_VARS.items():
        if nome in existentes_por_nome:
            resultado[nome] = existentes_por_nome[nome]
        else:
            variaveis[str(id_sug)] = {'name': nome, 'value': ''}
            resultado[nome] = id_sug
    return resultado


def atualizar_webhook_aurora_var(flow: dict, nova_url: str) -> bool:
    """Atualiza o set node (id 5004) que define webhook_aurora."""
    NODE_VAR_SERVIDOR = 5004
    for node in flow['flow']:
        if node.get('id') == NODE_VAR_SERVIDOR:
            data = node.get('data', {})
            variables = data.get('variables', [])
            values = data.get('values', [])
            for idx, vid in enumerate(variables):
                if vid == VAR_WEBHOOK_AURORA and idx < len(values):
                    values[idx] = nova_url
                    return True
    return False


def reescrever_api_node(
    flow: dict, node_id: int, nova_url: str, vars_map: dict[str, int],
    timeout: int = 25,
) -> bool:
    """Reescreve um nó de API (cod_componente 9) pra usar o validador v2."""
    for node in flow['flow']:
        if node.get('id') != node_id:
            continue
        data = node.setdefault('data', {})
        api = data.setdefault('api', {})
        api['url'] = nova_url
        api['method'] = 1   # POST
        api['timeout'] = timeout
        api['async'] = 0
        data['headers'] = {'key': ['Content-Type'], 'value': ['application/json']}
        data['body'] = {'body': json.dumps(_payload_validar_v2(), indent=2, ensure_ascii=False)}
        data['store'] = _store_validar_v2(vars_map)
        return True
    return False


def migrar(entrada: Path, saida: Path, api_url: str) -> None:
    api_url = api_url.rstrip('/')
    url_validar = f'{api_url}/validar'

    flow = json.loads(entrada.read_text(encoding='utf-8'))
    flow = deepcopy(flow)
    print(f'→ Lendo {entrada} ({len(flow.get("flow", []))} nodes)')

    vars_map = garantir_variaveis(flow)
    print(f'→ Variáveis garantidas: {", ".join(vars_map.keys())}')

    if atualizar_webhook_aurora_var(flow, url_validar):
        print(f'  ✓ var webhook_aurora → {url_validar}')

    for nid, desc in [
        (NODE_API_VALIDA_RESPOSTA, 'api_valida_resposta'),
        (NODE_API_CONSULTA_CEP, 'api_consulta_cep'),
        (NODE_API_15, 'api_15 (legado N8N)'),
        (NODE_API_16, 'api_16 (legado DynamicValidator)'),
    ]:
        if reescrever_api_node(flow, nid, url_validar, vars_map):
            print(f'  ✓ {desc} (id {nid}) → {url_validar}')
        else:
            print(f'  ⚠ {desc} (id {nid}) não encontrado — pulando')

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'\n✓ Gerado: {saida}')
    print('\n⚠️  PASSO MANUAL no editor Matrix:')
    print('   1. Antes de cada sol_*, crie um nó "set var" que defina')
    print('      {#question_id_atual} = "<id da regra correspondente>"')
    print('      (ex: "coleta_cpf", "coleta_cep", "coleta_nome", etc — ver Django admin)')
    print('   2. Adicione `id_lead` na variável global pra que `{#id_lead}` esteja preenchida.')
    print('   3. Configure decisões pós-API:')
    print('      - se {#resp_transbordo} == "true" → ser_humano')
    print('      - se {#resp_valido} == "false" → repetir pergunta com mensagem {#resp_message}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--entrada', type=Path, default=Path('fluxos/flow.json'))
    p.add_argument('--saida', type=Path, default=Path('fluxos/flow_v2.json'))
    p.add_argument('--api-url', default='https://robovendas.megalinkpiaui.com.br/ia')
    args = p.parse_args()

    if not args.entrada.exists():
        print(f'Erro: {args.entrada} não existe', file=sys.stderr)
        return 1
    migrar(args.entrada, args.saida, args.api_url)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
