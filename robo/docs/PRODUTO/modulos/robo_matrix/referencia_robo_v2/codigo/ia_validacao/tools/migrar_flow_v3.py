"""Migra flow.json para v3:

FASE 2 (esta operação):
- Insere um nó `set var question_id_atual = "<id>"` antes de cada sol_*
- Reconecta os edges/redirects que apontavam pro sol pra apontarem pro set_var
- Adiciona edge set_var → sol
- Atualiza var webhook_aurora pra /ia/validar

FASE 3 (também aplicada aqui se --remover-apis-redundantes):
- Remove APIs que a IA dispara em background (atualizar_lead, tags, imagens, histórico granular)
- Conecta direto o nó anterior ao próximo
- MANTÉM: api_8 (registrar lead inicial), api_14 (consultar),
  api_email_nas_ven/api_finaliza_lead (mudanças críticas de status_api),
  api_21/22/23/24/25 (hubsoft + agendamento)

Uso:
    python tools/migrar_flow_v3.py \\
        --entrada ../flow.json \\
        --saida fluxos/flow_v3.json \\
        --api-url https://robovendas.megalinkpiaui.com.br/ia \\
        [--remover-apis-redundantes]
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path


# ── mapeamento sol_id → question_id da regra (de acordo com seed Django) ────
MAPEAMENTO_SOLS: dict[int, str] = {
    5570: 'coleta_nome',                # sol_2 (primeiro nome do cliente)
    5577: 'coleta_cidade',              # sol_cidade
    5580: 'coleta_rua',                 # sol_rua
    5582: 'coleta_bairro',              # sol_bairro
    5586: 'coleta_cep',                 # sol_7
    5593: 'coleta_numero',              # sol_13 número
    5596: 'coleta_ponto_referencia',    # sol_13 ponto_ref
    5598: 'coleta_nome',                # sol_13 nome completo
    5600: 'coleta_data_nascimento',     # sol_13 nascimento
    5601: 'coleta_email',               # sol_13 email
    5604: 'coleta_cpf',                 # sol_13 CPF (com validation:1 nativa)
    5823: 'coleta_rua',                 # sol_12 rua manual
    5835: 'coleta_bairro',              # sol_bairro manual
    5843: 'coleta_cidade',              # sol_cidade manual
    5851: 'coleta_cep',                 # sol_cep manual
    5919: 'documentacao_selfie',        # sol_16 selfie
    5921: 'documentacao_frente_doc',    # sol_17 frente doc
    5924: 'documentacao_verso_doc',     # sol_18 verso doc
    # 6040 (sol_19) é um nó de teste — pular
    6083: 'coleta_rg',                  # sol_20 RG (tem validation:5)
    6145: 'coleta_cidade',              # sol_21 UF (sem regra dedicada — usa cidade)
}

# Variáveis Matrix
VAR_WEBHOOK_AURORA = 3620089
VAR_QUESTION_ID_ATUAL = 9200012   # mesma ID usada no flow_v2.json

# APIs redundantes que a IA já dispara em background (Fase 3)
APIS_REDUNDANTES = {
    5750: 'api_2',              # registrar_historico fluxo_inicializado
    5972: 'api_13',             # registrar_historico fluxo_inicializado (alt branch)
    5886: 'api_7',              # registrar_historico transferido_humano (dentro horário)
    5889: 'api_7',              # registrar_historico transferido_humano (fora horário)
    6096: 'api_17',             # registrar_historico resposta
    5956: 'api_9',              # atualizar_lead plano/valor
    5958: 'api_10',             # atualizar_lead endereço completo
    5960: 'api_11',             # atualizar_lead nome/numero/rg/ponto_ref
    6253: 'api_26',             # adicionar tag Comercial
    6255: 'api_27',             # adicionar tag Endereço
    6257: 'api_28',             # adicionar tag Assinado
    6117: 'api_18',             # registrar imagem selfie
    6126: 'api_19',             # registrar imagem frente
    6133: 'api_20',             # registrar imagem verso
}

# APIs que NÃO devem ser removidas (mudanças de status críticas + hubsoft)
APIS_MANTIDAS = {
    5939: 'api_8',                  # registrar lead inicial (cria id_lead)
    5975: 'api_14',                 # consultar lead por telefone
    5752: 'api_fluxo_finalizado',   # historico fluxo_finalizado
    5941: 'api_finaliza_lead',      # status_api=pendente (FINAL)
    5962: 'api_email_nas_ven',      # status_api=aguardando_assinatura
    # Hubsoft & apimatrix:
    6162: 'api_21_hubsoft',
    6178: 'api_22_consultar_agenda',
    6197: 'api_23_abrir_atendimento',
    6210: 'api_24_abrir_os',
    6216: 'api_25_consultar_datas',
}


def garantir_variavel_question_id(flow: dict):
    """Adiciona a variável question_id_atual se ainda não existe."""
    variaveis = flow.setdefault('variaveis', {})
    if str(VAR_QUESTION_ID_ATUAL) not in variaveis:
        variaveis[str(VAR_QUESTION_ID_ATUAL)] = {'name': 'question_id_atual', 'value': ''}


def atualizar_webhook_aurora(flow: dict, nova_url: str) -> bool:
    """Atualiza o set node (id 5004) que define webhook_aurora."""
    for node in flow['flow']:
        if node.get('id') == 5004:
            d = node.get('data', {})
            for idx, vid in enumerate(d.get('variables', [])):
                if vid == VAR_WEBHOOK_AURORA and idx < len(d.get('values', [])):
                    d['values'][idx] = nova_url
                    return True
    return False


def reescrever_api_validar(flow: dict, nova_url: str):
    """Reescreve api_valida_resposta (5784), api_consulta_cep (5763), api_15 (6037), api_16 (6050)
    com URL v2, payload v2 e store v2.

    O store mapeia direto pras variáveis LEGADAS do flow (3620xxx) que as
    decisões dec_3/dec_4/dec_5/dec_8/dec_9 já consomem. Sem isso o Matrix
    mostra os dropdowns vazios (IDs 9200xxx não existem em `variaveis`).
    """
    # Body genérico (api_valida_resposta) — usa as vars que os reds setam
    body_v2 = {
        'question': '{#pergunta_cliente}',
        'answer': '{#resposta_cliente}',
        'cellphone': '{#CONTATO.TELEFONE}',
        'lead_id': '{#id_lead}',
        'question_id': '{#question_id_atual}',
    }
    # Bodies HARDCODED — chamadas que vêm DIRETO de sol_* (sem red intermediário).
    # O sol guarda input em sua própria variable, então usamos ela direto.
    body_cep_direto = {
        'question': 'Qual o CEP do seu endereço?',
        'answer': '{#prospecto_cep}',
        'cellphone': '{#CONTATO.TELEFONE}',
        'lead_id': '{#id_lead}',
        'question_id': 'coleta_cep',
    }
    # (variable_id, returned_path) — ordem importa.
    # SÓ campos que a API IA retorna (engine.py:legados + extracted_data).
    # As vars dinamica_*, registro_historico, prox_pass_historico, qtd_*,
    # img_doc* etc. são setadas por red nodes ou sol.variable — NÃO entram aqui.
    mapeamento_store = [
        # ── Flags de decisão (dec_3, dec_4, dec_5, dec_8, dec_9) ──
        (3620068, 'resposta_correta'),         # dec_4
        (3620067, 'resposta_sem_erro_api'),    # dec_3
        (3620074, 'retorno_erro_api'),         # msg_16 exibe
        (3620080, 'needsReception'),           # dec_3 avançado
        (3620081, 'isAClient'),                # dec_5
        (3620082, 'cancelado'),                # dec_5
        (3620094, 'viabilidade_cep'),          # decisão do CEP
        (3620088, 'time_instalacao'),          # dec_9
        (3620066, 'api_cep'),                  # dec_8 + msg_21
        # ── CEP resolvido (ura_7 + red_50/51 manuais) ──
        (3620069, 'ret_cep'),
        (3620070, 'ret_bairro'),
        (3620071, 'ret_cidade'),
        (3620072, 'ret_estado'),
        (3620073, 'ret_rua'),
        # ── Dados normalizados (chaves únicas por extractor) ──
        (3620055, 'extracted_data.cpf_cnpj'),         # prospecto_cpf
        (3620060, 'extracted_data.nome_razaosocial'), # prospecto_nome_completo
        (3620079, 'extracted_data.email'),            # prospecto_email
        (3620057, 'extracted_data.data_nascimento'),  # prospecto_nascimento
        (3620054, 'extracted_data.numero_residencia'),# prospecto_n_resisdencia
    ]
    store_v2 = {
        'filter': 1,
        'variable': [v for v, _ in mapeamento_store],
        'returned': [r for _, r in mapeamento_store],
    }
    # Mapa: api_id → body que deve ser usado
    # 5784 (api_valida_resposta): body genérico (vem de reds que setam pergunta/resposta_cliente)
    # 5763 (api_consulta_cep): body hardcoded de CEP (vem DIRETO de sol_7)
    # 6037, 6050 (api_15/api_16 em grupo de teste): genérico também
    body_por_api = {
        5784: body_v2,
        5763: body_cep_direto,
        6037: body_v2,
        6050: body_v2,
    }
    for node_id, body in body_por_api.items():
        for node in flow['flow']:
            if node.get('id') == node_id:
                d = node.setdefault('data', {})
                api = d.setdefault('api', {})
                api['url'] = nova_url
                api['method'] = 1
                api['timeout'] = 25
                api['async'] = 0
                d['headers'] = {'key': ['Content-Type'], 'value': ['application/json']}
                d['body'] = {'body': json.dumps(body, indent=2, ensure_ascii=False)}
                d['store'] = store_v2
                break


def _redirecionar_referencias(flow: dict, de_id: int, para_id: int):
    """Toda referência a `de_id` agora vira `para_id`.

    Inclui:
    - Edges com target=de_id
    - Reds (cod_componente:17) com data.component=de_id
    """
    for node in flow['flow']:
        # edges: source/target
        if node.get('edge') and node.get('target') == de_id:
            node['target'] = para_id
        # reds (cod 17) com data.component
        if not node.get('edge') and node.get('cod_componente') == 17:
            d = node.get('data', {})
            if isinstance(d, dict) and d.get('component') == de_id:
                d['component'] = para_id


def inserir_set_var_antes_de_sols(flow: dict, mapeamento: dict[int, str]) -> int:
    """Insere um nó `set var question_id_atual` antes de cada sol mapeado.

    Para cada (sol_id, question_id):
    1. Cria novo nó set_var (cod 13) no mesmo parent do sol
    2. Redireciona todas as edges/reds que apontavam pro sol pra apontarem
       pro novo set_var
    3. Cria edge set_var → sol

    Retorna número de sols processados.
    """
    # Map de sols existentes
    sols = {n['id']: n for n in flow['flow']
            if not n.get('edge') and n.get('cod_componente') == 2}

    next_id = 9500000  # nova faixa pra evitar colisão
    inseridos = 0

    for sol_id, question_id in mapeamento.items():
        sol = sols.get(sol_id)
        if not sol:
            print(f'  ⚠ sol id={sol_id} não encontrado — pulando')
            continue

        parent_id = sol.get('parent')
        set_var_id = next_id
        next_id += 1
        edge_id = next_id
        next_id += 1

        # Nó set_var
        set_var = {
            'parent': parent_id,
            'id': set_var_id,
            'quantityCon': 1,
            'edge': False,
            'cod_componente': 13,
            'height': 30,
            'width': 30,
            'x': max(0, (sol.get('x', 0)) - 80),
            'y': sol.get('y', 0),
            'relative': False,
            'value': '',
            'data': {
                'identifier': f'var_qid_{sol_id}',
                'variables': [VAR_QUESTION_ID_ATUAL],
                'values': [question_id],
            },
        }

        # Edge set_var → sol
        edge = {
            'parent': parent_id,
            'id': edge_id,
            'edge': True,
            'cod_componente': '',
            'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
            'source': set_var_id,
            'target': sol_id,
            'data': False,
        }

        # Redireciona referências (mas só antes de adicionar os novos!)
        _redirecionar_referencias(flow, sol_id, set_var_id)

        # Adiciona os novos nós ao flow
        flow['flow'].append(set_var)
        flow['flow'].append(edge)

        # Remove a auto-referência criada pelo redirect (set_var.target=set_var nada)
        # Como a edge nova set_var→sol foi adicionada DEPOIS do redirect, está OK.

        inseridos += 1

    return inseridos


def desambiguar_identifiers(flow: dict) -> int:
    """Identifiers duplicados podem causar redirects type=2 imprevisíveis.
    Renomeia nós conflitantes que recebem redirects dinâmicos.
    """
    nodes = flow['flow']
    contagem = {}
    for n in nodes:
        if n.get('edge'): continue
        d = n.get('data') or {}
        if isinstance(d, dict) and d.get('identifier'):
            contagem.setdefault(d['identifier'], []).append(n['id'])

    # Lista vars que setam identifier dinamicamente
    vars_redirect = {3620077, 3620078, 3620065, 3620016, 3620093}
    referenciados = set()
    for n in nodes:
        if n.get('edge') or n.get('cod_componente') != 17: continue
        d = n.get('data') or {}
        if not isinstance(d, dict): continue
        for v, val in zip(d.get('variables') or [], d.get('values') or []):
            if v in vars_redirect and isinstance(val, str):
                referenciados.add(val)

    # Renomeações específicas (id → novo identifier) para conflitos críticos
    renomear = {
        6016: 'msg_retomar_resposta',  # grupo dec_7, conflitava com msg_33 (5952 - CEP)
    }
    n_fix = 0
    for nid, novo_ident in renomear.items():
        for n in nodes:
            if n.get('id') == nid:
                d = n.setdefault('data', {})
                d['identifier'] = novo_ident
                n_fix += 1
    return n_fix


def garantir_identifier_apis(flow: dict) -> int:
    """API nodes têm `data.api.identifier` mas não `data.identifier`.
    Reds type=2 fazem lookup por `data.identifier` — sem isso, redirects
    para 'api_X' falham silenciosamente. Copia api.identifier → data.identifier.
    """
    n_fix = 0
    for node in flow['flow']:
        if node.get('edge') or node.get('cod_componente') != 9:
            continue
        d = node.setdefault('data', {})
        api_id = (d.get('api') or {}).get('identifier')
        if api_id and not d.get('identifier'):
            d['identifier'] = api_id
            n_fix += 1
    return n_fix


def corrigir_referencias_apis_removidas(flow: dict, apis_remover: set[int]) -> int:
    """Reds setavam dinamica_prox_pass='api_X' apontando pra um API que foi
    removido. Substitui o valor pelo identifier do PRIMEIRO sucessor mantido.
    """
    nodes = flow['flow']
    by_id = {n['id']: n for n in nodes}
    apis_remover = set(apis_remover)

    # cache api_identifier → id
    apiident_to_id = {}
    for n in nodes:
        if n.get('edge') or n.get('cod_componente') != 9:
            continue
        d = n.get('data') or {}
        ai = (d.get('api') or {}).get('identifier')
        if ai:
            apiident_to_id[ai] = n['id']

    # Conta quantos nós têm cada identifier (pra evitar identifiers ambíguos)
    contagem_identifier = {}
    for n in nodes:
        if n.get('edge'): continue
        d = n.get('data') or {}
        if isinstance(d, dict) and d.get('identifier'):
            contagem_identifier[d['identifier']] = contagem_identifier.get(d['identifier'], 0) + 1

    def primeiro_sucessor_mantido(node_id, visited=None):
        """Segue: pula APIs removidas E reds (type=1) até um nó com identifier ÚNICO."""
        if visited is None: visited = set()
        if node_id in visited: return None
        visited.add(node_id)

        node = by_id.get(node_id)
        if not node:
            return None
        d = node.get('data') or {}

        # red type=1 simplesmente redireciona — segue para o component
        if (not node.get('edge') and node.get('cod_componente') == 17
                and isinstance(d, dict) and d.get('type') == 1 and d.get('component')):
            return primeiro_sucessor_mantido(d['component'], visited)

        # se está em apis_remover, segue pela saída
        if node_id in apis_remover:
            saidas = [e for e in nodes if e.get('edge') and e.get('source') == node_id]
            if saidas:
                return primeiro_sucessor_mantido(saidas[0]['target'], visited)
            return None

        # nó "real" — precisa ter identifier único
        ident = d.get('identifier') if isinstance(d, dict) else None
        if ident and contagem_identifier.get(ident, 0) == 1:
            return node_id
        # identifier ambíguo ou ausente — tenta seguir uma saída
        saidas = [e for e in nodes if e.get('edge') and e.get('source') == node_id]
        if saidas:
            return primeiro_sucessor_mantido(saidas[0]['target'], visited)
        return None

    n_fix = 0
    for n in nodes:
        if n.get('edge') or n.get('cod_componente') != 17:
            continue
        d = n.get('data') or {}
        if not isinstance(d, dict): continue
        vals = d.get('values') or []
        for idx, v in enumerate(vals):
            if not isinstance(v, str): continue
            api_id_node = apiident_to_id.get(v)  # nó com data.api.identifier=v
            if api_id_node and api_id_node in apis_remover:
                # api removido — buscar sucessor
                sucessor = primeiro_sucessor_mantido(api_id_node)
                if sucessor:
                    sd = by_id[sucessor].get('data') or {}
                    novo_ident = sd.get('identifier') if isinstance(sd, dict) else None
                    if novo_ident:
                        d['values'][idx] = novo_ident
                        n_fix += 1
    return n_fix


def remover_validations_nativas(flow: dict, sol_ids: set[int]) -> int:
    """Zera `validation` e `validation_regex` dos sols mapeados.

    A API IA agora valida TUDO — a validação nativa do Matrix estava
    rejeitando inputs (ex: CPF) antes mesmo do api_valida_resposta ser
    chamado, fazendo o bot repetir a pergunta silenciosamente.
    """
    alterados = 0
    for node in flow['flow']:
        if (not node.get('edge') and node.get('cod_componente') == 2
                and node.get('id') in sol_ids):
            d = node.setdefault('data', {})
            if d.get('validation') not in (0, None, '') or d.get('validation_regex'):
                d['validation'] = 0
                d['validation_regex'] = ''
                alterados += 1
    return alterados


def remover_apis_redundantes(flow: dict, apis_remover: dict[int, str]) -> int:
    """Remove nós API redundantes — reconecta o predecessor ao próximo nó.

    Estratégia:
    Para cada api_id a remover:
    1. Encontra o(s) edge(s) que ENTRA(M) (target=api_id) — preserva o `source`
    2. Encontra o edge que SAI (source=api_id) — preserva o `target`
    3. Cria novos edges: source_entrada → target_saída
    4. Remove o nó API e seus edges adjacentes
    5. Reds (cod 17) com data.component=api_id são redirecionados pro target_saída
    """
    removidos = 0
    for api_id in list(apis_remover.keys()):
        # Encontrar entradas e saídas
        entradas = [n for n in flow['flow'] if n.get('edge') and n.get('target') == api_id]
        saidas = [n for n in flow['flow'] if n.get('edge') and n.get('source') == api_id]

        if not saidas:
            # Sem saída — só remove o nó (pode acontecer com APIs em grupos)
            flow['flow'] = [n for n in flow['flow'] if n.get('id') != api_id]
            removidos += 1
            continue

        # Pega a saída principal (geralmente só uma)
        target_saida = saidas[0].get('target')

        # Redireciona referências (reds e edges entrando) pro target_saida
        for n in flow['flow']:
            if n.get('edge') and n.get('target') == api_id:
                n['target'] = target_saida
            if not n.get('edge') and n.get('cod_componente') == 17:
                d = n.get('data', {})
                if isinstance(d, dict) and d.get('component') == api_id:
                    d['component'] = target_saida

        # Remove o nó API e seus edges de saída
        ids_remover = {api_id}
        for s in saidas:
            ids_remover.add(s.get('id'))
        flow['flow'] = [n for n in flow['flow'] if n.get('id') not in ids_remover]

        removidos += 1

    return removidos


def migrar(entrada: Path, saida: Path, api_url: str, remover_redundantes: bool = False):
    api_url = api_url.rstrip('/')
    url_validar = f'{api_url}/validar'

    flow = json.loads(entrada.read_text(encoding='utf-8'))
    flow = deepcopy(flow)
    print(f'→ Lendo {entrada} ({len(flow["flow"])} nodes)')

    # 1. Garantir variável question_id_atual
    garantir_variavel_question_id(flow)
    print('  ✓ variável question_id_atual garantida')

    # 2. Atualizar var webhook_aurora
    if atualizar_webhook_aurora(flow, url_validar):
        print(f'  ✓ webhook_aurora → {url_validar}')

    # 3. Reescrever os nós API que chamam o validador
    reescrever_api_validar(flow, url_validar)
    print(f'  ✓ api_valida_resposta + api_consulta_cep + api_15 + api_16 → {url_validar}')

    # 4. FASE 2: inserir set_var antes de cada sol mapeado
    inseridos = inserir_set_var_antes_de_sols(flow, MAPEAMENTO_SOLS)
    print(f'  ✓ {inseridos} set_var question_id_atual inseridos antes dos sols')

    # 4b. Remover validation nativa dos sols — IA valida tudo
    n_val = remover_validations_nativas(flow, set(MAPEAMENTO_SOLS.keys()))
    print(f'  ✓ {n_val} sols com validation nativa zerada (IA valida tudo)')

    # 5. FASE 3 (opcional): remover APIs redundantes
    if remover_redundantes:
        # 5a) corrige referências PRIMEIRO (antes de remover, pra traçar sucessor)
        n_ref = corrigir_referencias_apis_removidas(flow, set(APIS_REDUNDANTES.keys()))
        print(f'  ✓ {n_ref} redirects para APIs removidas reapontados pro sucessor')
        n = remover_apis_redundantes(flow, APIS_REDUNDANTES)
        print(f'  ✓ {n} APIs redundantes removidas (IA dispara em background)')

    # 6. Garantir data.identifier nos nós API (reds type=2 precisam)
    n_ident = garantir_identifier_apis(flow)
    print(f'  ✓ {n_ident} nós API com data.identifier garantido')

    # 7. Desambiguar identifiers duplicados que são alvo de redirect
    n_dup = desambiguar_identifiers(flow)
    print(f'  ✓ {n_dup} identifier(s) duplicado(s) renomeado(s)')

    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding='utf-8')

    final_nodes = [n for n in flow['flow'] if not n.get('edge')]
    final_edges = [n for n in flow['flow'] if n.get('edge')]
    print(f'\n✓ Gerado: {saida}')
    print(f'  → {len(final_nodes)} nodes + {len(final_edges)} edges')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--entrada', type=Path, default=Path('../flow.json'))
    p.add_argument('--saida', type=Path, default=Path('fluxos/flow_v3.json'))
    p.add_argument('--api-url', default='https://robovendas.megalinkpiaui.com.br/ia')
    p.add_argument('--remover-apis-redundantes', action='store_true',
                   help='Aplica Fase 3 — remove APIs duplicadas que a IA faz em background')
    args = p.parse_args()

    if not args.entrada.exists():
        print(f'Erro: {args.entrada} não existe', file=sys.stderr)
        return 1

    migrar(args.entrada, args.saida, args.api_url, args.remover_apis_redundantes)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
