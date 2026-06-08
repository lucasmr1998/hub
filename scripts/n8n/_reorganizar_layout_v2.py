"""
Reorganiza posicoes do workflow Vero em grid limpo:

X (colunas, 240px):
   -1600  -1360  -1120  -880    -640    -400   -160    80    320    560    800   1040   1280   1520   1760   2000

Y (lanes por estado, 400px):
   -1200  aguarda_cep  (chain mais longa)
    -800  aguarda_email
    -400  inicio
       0  TRONCO (input + convergencia)
     400  aguarda_nome
     800  aguarda_plano
    1200  IA SHARED LAYER
"""
import json
import sys
import io
import requests
from dotenv import dotenv_values
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

env = dotenv_values('.env.n8n')
BASE = env['N8N_BASE_URL'].rstrip('/')
KEY = env['N8N_API_KEY']
HEADERS = {'X-N8N-API-KEY': KEY, 'Content-Type': 'application/json'}
WF_ID = 'Df1BgcXdg3HAUZwf'

POSITIONS = {
    # === TRONCO de entrada (Y=0) ===
    'Webhook Wazapi':                (-1600,    0),
    'Entrada':                       (-1360,    0),
    'Load Session':                  (-1120,    0),
    'Por Nodo Atual':                ( -880,    0),

    # === Lane inicio (Y=-400) ===
    'Step Inicio':                   ( -640, -400),

    # === Lane aguarda_email (Y=-800) ===
    'ValidarEmail':                  ( -640, -800),
    'Email Valido?':                 ( -400, -800),
    'Step Aguarda Email (Final)':    ( -160, -800),
    'Step Reasking Email':           ( -160, -650),  # dead (mantido por seguranca)

    # === Lane aguarda_cep (Y=-1200) — chain mais longa ===
    'ValidarCepFormato':             ( -640, -1200),
    'Formato CEP OK?':               ( -400, -1200),
    'HTTP ViaCEP':                   ( -160, -1200),
    'CEP Existe?':                   (   80, -1200),
    'Step Reasking CEP NaoExiste':   (   80, -1050),
    'HTTP Hubtrix Viabilidade':      (  320, -1200),
    'Atendido?':                     (  560, -1200),
    'Step Reasking CEP SemCobertura':(  560, -1050),
    'GerarCatalogoPlanos':           (  800, -1200),
    'Step Aguarda CEP':              ( 1040, -1200),
    'Step Reasking CEP Formato':     ( -400, -1050),  # dead

    # === Lane aguarda_nome (Y=400) ===
    'Step Aguarda Nome':             ( -640,  400),

    # === Lane aguarda_plano (Y=800) ===
    'ValidarEscolhaPlano':           ( -640,  800),
    'Plano Valido?':                 ( -400,  800),
    'Step Aguarda Plano':            ( -160,  800),

    # === IA SHARED LAYER (Y=1200+) ===
    'Contexto Email':                ( -160, 1200),
    'Contexto CEP':                  (   80, 1200),
    'Contexto Plano':                (  320, 1200),
    'OpenAI gpt-4o-mini':            (  640, 1400),   # LM (sub-nodo)
    'IA Validator Universal':        (  640, 1200),
    'ResultadoIA':                   (  880, 1200),
    'IA OK?':                        ( 1120, 1200),
    'Router IA Tipo':                ( 1360, 1050),
    'Router IA Tipo Erro':           ( 1360, 1350),

    # IA destinos (sucesso)
    'Step Aguarda Email (via IA)':   ( 1600,  900),
    'CEP Resolvido IA':              ( 1600, 1050),    # volta pra HTTP ViaCEP (loop)
    'Step Aguarda Plano (via IA)':   ( 1600, 1200),

    # IA destinos (erro)
    'Step Reasking Email (via IA)':  ( 1600, 1300),
    'Step Reasking CEP (via IA)':    ( 1600, 1400),
    'Step Reasking Plano':           ( 1600, 1500),

    # === Convergencia (Y=0) — direita ===
    'Save Session':                  ( 2000,    0),
    'Enviar Wazapi':                 ( 2240, -150),
    'Respond OK':                    ( 2480, -150),
    'Finalizou?':                    ( 2240,  150),
    'Enviar Lead Hubtrix':           ( 2480,  150),
}

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
r.raise_for_status()
wf = r.json()

moved = 0
unmoved = []
for n in wf['nodes']:
    name = n.get('name', '')
    if name in POSITIONS:
        x, y = POSITIONS[name]
        n['position'] = [x, y]
        moved += 1
    else:
        unmoved.append(name)

print(f'Reposicionados: {moved}')
if unmoved:
    print(f'Nao reposicionados (fora do mapa): {unmoved}')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution',
           'saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
src = wf.get('settings') or {}
clean = {k: v for k, v in src.items() if k in allowed}

payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT: {r.status_code} updatedAt={r.json().get("updatedAt") if r.status_code<300 else r.text[:300]}')
