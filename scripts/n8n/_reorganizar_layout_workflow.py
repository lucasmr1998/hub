"""
Reorganiza posicoes dos nodos do workflow Vero pra eliminar sobreposicoes.

Layout em lanes horizontais (Y) por estado da maquina:
   Y = -800: aguarda_cep   (chain mais longa: 8 nodos)
   Y = -400: aguarda_email (chain media: 4 nodos)
   Y =    0: inicio
   Y =  300: aguarda_nome
   Y =  600: aguarda_plano

Reasking nodes vao 200px abaixo da lane principal (mesma Y +200, X igual ao IF que deu falso).
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

# Coordenadas grid: cada coluna = 240px, cada lane = 300px de altura
POSITIONS = {
    # Linha de input (Y=0)
    'Webhook Wazapi':                  (-1440,    0),
    'Entrada':                         (-1200,    0),
    'Load Session':                    ( -960,    0),
    'Por Nodo Atual':                  ( -720,    0),

    # Lane inicio (Y=0)
    'Step Inicio':                     ( -480,    0),

    # Lane aguarda_nome (Y=300)
    'Step Aguarda Nome':               ( -480,  300),

    # Lane aguarda_plano (Y=600)
    'Step Aguarda Plano':              ( -480,  600),

    # Lane aguarda_email (Y=-400)
    'ValidarEmail':                    ( -480, -400),
    'Email Valido?':                   ( -240, -400),
    'Step Aguarda Email (Final)':      (    0, -400),
    'Step Reasking Email':             ( -240, -200),   # offset 200 below IF

    # Lane aguarda_cep (Y=-800)
    'ValidarCepFormato':               ( -480, -800),
    'Formato CEP OK?':                 ( -240, -800),
    'HTTP ViaCEP':                     (    0, -800),
    'CEP Existe?':                     (  240, -800),
    'HTTP Hubtrix Viabilidade':        (  480, -800),
    'Atendido?':                       (  720, -800),
    'Step Aguarda CEP':                (  960, -800),
    'Step Reasking CEP Formato':       ( -240, -600),
    'Step Reasking CEP NaoExiste':     (  240, -600),
    'Step Reasking CEP SemCobertura':  (  720, -600),

    # Convergencia (Save Session + envio)
    'Save Session':                    ( 1200,    0),
    'Enviar Wazapi':                   ( 1440, -150),
    'Respond OK':                      ( 1680, -150),
    'Finalizou?':                      ( 1440,  150),
    'Enviar Lead Hubtrix':             ( 1680,  150),
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
