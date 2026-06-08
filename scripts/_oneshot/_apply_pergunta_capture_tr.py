"""Aplica patch no workflow Vero Orquestrador TR Carrion: captura de perguntas-sem-resposta.

Insere pipeline de 6 nodos copiado do Nyvion entre "IA OK? (FALSE)" e "Router IA Tipo Erro":
  IA OK? FALSE
    → EntradaDuvidasTR (set: prepara contexto)
    → Identificar Duvida Key TR (lmChatOpenAi gpt-4o-mini)
    → Perguntando? TR (langchain.agent — classifica se eh pergunta real)
    → Output Validator TR (set: parseia JSON)
    → É Uma Pergunta? TR (if: isAQuestion === true)
    → SalvarPergunta Hubtrix TR (POST → /conhecimento/registrar-pergunta/)

A branch que vai pro Router IA Tipo Erro (Reasking) e PRESERVADA — adicionamos um
destino paralelo, nao substituimos.
"""
import json
import uuid
from pathlib import Path
from datetime import datetime
import sys
sys.path.insert(0, str(Path(__file__).parent))
from _n8n_api import N8N

WF_ID = 'Df1BgcXdg3HAUZwf'

# Token Bearer pra integ #24 Vero N8N (registrar-pergunta) — TR Carrion
TR_HUBTRIX_TOKEN = 'b73ec926b22e46b8aba261d101d81899ba45a53a0e744f539db16f9950ce49f4'

# Credencial OpenAI ja usada no Vero
OPENAI_CRED = {'openAiApi': {'id': '9sEcXDngJTTkRTIV', 'name': 'MEGALINK-Validação'}}


def make_id():
    return str(uuid.uuid4())


def build_new_nodes(base_x=4500, base_y=2200):
    """Retorna lista de nodos novos pra adicionar ao workflow."""
    nodes = []

    # 1. EntradaDuvidasTR — set node prepara variaveis
    nodes.append({
        'parameters': {
            'assignments': {
                'assignments': [
                    {'id': make_id(), 'name': 'answer',  'value': "={{ $('Entrada').first().json.mensagem }}", 'type': 'string'},
                    {'id': make_id(), 'name': 'question','value': "={{ $node['ResultadoIA'].json.response.errorMessage || 'pergunta do bot' }}", 'type': 'string'},
                    {'id': make_id(), 'name': 'cellphone','value': "={{ $('Entrada').first().json.telefone }}", 'type': 'string'},
                    {'id': make_id(), 'name': 'empresa', 'value': 'TR_CARRION', 'type': 'string'},
                ],
            },
            'includeOtherFields': True,
            'options': {},
        },
        'type': 'n8n-nodes-base.set',
        'typeVersion': 3.4,
        'position': [base_x, base_y],
        'id': make_id(),
        'name': 'EntradaDuvidasTR',
    })

    # 2. Identificar Duvida Key TR (sub-nodo lmChatOpenAi gpt-4o-mini)
    nodes.append({
        'parameters': {
            'model': {'__rl': True, 'mode': 'list', 'value': 'gpt-4o-mini'},
            'options': {},
        },
        'type': '@n8n/n8n-nodes-langchain.lmChatOpenAi',
        'typeVersion': 1.2,
        'position': [base_x + 200, base_y + 200],
        'id': make_id(),
        'name': 'Identificar Duvida Key TR',
        'credentials': OPENAI_CRED,
    })

    # 3. Perguntando? TR — agent IA classificador
    SYS_PROMPT = (
        "Se na resposta o usuário estiver fazendo uma pergunta retorne:\n"
        "{ \"isAQuestion\": true }\n\n"
        "Se NAO for pergunta (ex: 20/10/2000, CEP, CPF, nome, 'ok', 'sim'):\n"
        "{ \"isAQuestion\": false }\n\n"
        "Exemplo correto: 'A instalacao e de graca?' -> { \"isAQuestion\": true }\n"
        "Pedir 'so um momento' NAO e pergunta.\n"
        "Pedir por ajuda NAO conta como pergunta.\n"
        "Retorne SOMENTE JSON. Nada mais."
    )
    nodes.append({
        'parameters': {
            'promptType': 'define',
            'text': "=A mensagem do usuário foi:\n{{ $json.answer }}",
            'options': {'systemMessage': SYS_PROMPT},
        },
        'type': '@n8n/n8n-nodes-langchain.agent',
        'typeVersion': 1.6,
        'position': [base_x + 400, base_y],
        'id': make_id(),
        'name': 'Perguntando? TR',
    })

    # 4. Output Validator TR — parseia JSON do agent
    nodes.append({
        'parameters': {
            'assignments': {
                'assignments': [
                    {
                        'id': make_id(),
                        'name': 'response',
                        'value': "={{ JSON.parse($json.output) }}",
                        'type': 'object',
                    },
                ],
            },
            'options': {},
        },
        'type': 'n8n-nodes-base.set',
        'typeVersion': 3.4,
        'position': [base_x + 600, base_y],
        'id': make_id(),
        'name': 'Output Validator TR',
    })

    # 5. É Uma Pergunta? TR — if isAQuestion === true
    nodes.append({
        'parameters': {
            'conditions': {
                'options': {
                    'caseSensitive': True,
                    'leftValue': '',
                    'typeValidation': 'loose',
                    'version': 2,
                },
                'conditions': [
                    {
                        'id': make_id(),
                        'leftValue': "={{ $json.response.isAQuestion }}",
                        'rightValue': '',
                        'operator': {'type': 'boolean', 'operation': 'true', 'singleValue': True},
                    },
                ],
                'combinator': 'and',
            },
            'looseTypeValidation': True,
            'options': {},
        },
        'type': 'n8n-nodes-base.if',
        'typeVersion': 2.2,
        'position': [base_x + 800, base_y],
        'id': make_id(),
        'name': 'É Uma Pergunta? TR',
    })

    # 6. SalvarPergunta Hubtrix TR
    nodes.append({
        'parameters': {
            'method': 'POST',
            'url': 'https://app.hubtrix.com.br/api/public/n8n/conhecimento/registrar-pergunta/',
            'sendHeaders': True,
            'headerParameters': {
                'parameters': [
                    {'name': 'Authorization', 'value': f'Bearer {TR_HUBTRIX_TOKEN}'},
                ],
            },
            'sendBody': True,
            'bodyParameters': {
                'parameters': [
                    {'name': 'pergunta', 'value': "={{ $('EntradaDuvidasTR').first().json.answer }}"},
                ],
            },
            'options': {},
        },
        'type': 'n8n-nodes-base.httpRequest',
        'typeVersion': 4.2,
        'position': [base_x + 1000, base_y],
        'id': make_id(),
        'name': 'SalvarPergunta Hubtrix TR',
        'continueOnFail': True,
        'alwaysOutputData': True,
    })

    return nodes


def apply():
    n8n = N8N()
    wf = n8n.get_workflow(WF_ID)
    print(f'Workflow atual: {wf["name"]} | {len(wf["nodes"])} nodos | active={wf.get("active")}')

    # 1. Backup local pre-patch
    backup_path = Path(__file__).parent / f'_n8n_backup_{WF_ID}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    backup_path.write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Backup salvo: {backup_path.name}')

    # 2. Construir nodos novos
    new_nodes = build_new_nodes()
    print(f'\nNovos nodos ({len(new_nodes)}):')
    for n in new_nodes:
        print(f'  - {n["name"]} [{n["type"]}]')

    # 3. Patches no connections
    new_conn = json.loads(json.dumps(wf['connections']))  # deep copy

    # 3a. IA OK? branch FALSE (main[1]): ADICIONA destino EntradaDuvidasTR (mantem Router IA Tipo Erro)
    iaok_main = new_conn.setdefault('IA OK?', {}).setdefault('main', [[], []])
    while len(iaok_main) < 2:
        iaok_main.append([])
    iaok_main[1].append({'node': 'EntradaDuvidasTR', 'type': 'main', 'index': 0})

    # 3b. Pipeline interno
    new_conn['EntradaDuvidasTR'] = {'main': [[{'node': 'Perguntando? TR', 'type': 'main', 'index': 0}]]}
    new_conn['Identificar Duvida Key TR'] = {'ai_languageModel': [[{'node': 'Perguntando? TR', 'type': 'ai_languageModel', 'index': 0}]]}
    new_conn['Perguntando? TR'] = {'main': [[{'node': 'Output Validator TR', 'type': 'main', 'index': 0}]]}
    new_conn['Output Validator TR'] = {'main': [[{'node': 'É Uma Pergunta? TR', 'type': 'main', 'index': 0}]]}
    # IF TR: branch TRUE → SalvarPergunta. branch FALSE → fim (sem ação)
    new_conn['É Uma Pergunta? TR'] = {'main': [
        [{'node': 'SalvarPergunta Hubtrix TR', 'type': 'main', 'index': 0}],
        [],
    ]}
    # SalvarPergunta TR: termina aqui
    new_conn['SalvarPergunta Hubtrix TR'] = {'main': [[]]}

    # 4. Montar payload pro PUT
    # API public so aceita campos especificos em settings — filtra
    ALLOWED_SETTINGS = {
        'executionOrder', 'saveDataErrorExecution', 'saveDataSuccessExecution',
        'saveExecutionProgress', 'saveManualExecutions', 'timezone',
        'errorWorkflow', 'callerPolicy', 'callerIds',
    }
    safe_settings = {k: v for k, v in (wf.get('settings') or {}).items() if k in ALLOWED_SETTINGS}
    payload = {
        'name': wf['name'],
        'nodes': wf['nodes'] + new_nodes,
        'connections': new_conn,
        'settings': safe_settings,
    }

    print(f'\nTotal de nodes apos patch: {len(payload["nodes"])}')
    print('Edicao em connections:')
    print(f'  + IA OK? main[1] += EntradaDuvidasTR (mantem Router IA Tipo Erro)')
    print('  + 6 novas chaves de conexao pros nodos do pipeline')

    # 5. PUT
    print('\nAplicando PUT...')
    result = n8n.update_workflow(WF_ID, payload)
    print(f'OK: workflow id={result.get("id")} agora com {len(result.get("nodes", []))} nodos')
    print(f'   active={result.get("active")}, updatedAt={result.get("updatedAt")}')


if __name__ == '__main__':
    apply()
