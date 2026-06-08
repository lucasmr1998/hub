"""
Reorganiza layout do workflow Vero em grid claro.

Estrutura:
  TRONCO horizontal (Y=0): Webhook -> Entrada -> Buffer -> Load Session -> Switch
  Lanes superiores (Y < 0): aguarda_cep, confirmacao_cep, aguarda_email, aguarda_plano
  Lanes inferiores (Y > 0): aguarda_nome, aguarda_cpf, data_nasc, RG, confirmacao_final, humano, correcao
  IA SHARED LAYER (Y mais embaixo)
  Convergencia (X mais a direita)
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
    # === TRONCO horizontal Y=0 ===
    'Webhook Wazapi':              (-2200,    0),
    'Mensagem de Cliente?':        (-2000,    0),
    'Entrada':                     (-1800,    0),
    'BufferInserir':               (-1600,    0),
    'Aguardar 2s':                 (-1400,    0),
    'Ser Ultima Query':            (-1200,    0),
    'Sou a Ultima?':               (-1000,    0),
    'RegistrarMsgCliente':         ( -800,    0),
    'Load Session':                ( -600,    0),
    'DetectarReset':               ( -400,    0),
    'DetectarPedidoHumano':        ( -200,    0),
    'Ja em Humano?':               (    0,    0),
    'Por Nodo Atual':              (  200,    0),

    # === Respond terminais ===
    'Respond Ignored':             (-2000,  200),
    'Respond Buffered':            (-1000,  200),
    'Respond Humano Silencioso':   (    0,  200),

    # === Lane aguarda_cep (Y=-1500) ===
    'ValidarCepFormato':           (  450, -1500),
    'Formato CEP OK?':             (  700, -1500),
    'HTTP ViaCEP':                 (  950, -1500),
    'CEP Existe?':                 ( 1200, -1500),
    'Step Reasking CEP NaoExiste': ( 1200, -1300),
    'HTTP Hubtrix Viabilidade':    ( 1450, -1500),
    'Atendido?':                   ( 1700, -1500),
    'Step Reasking CEP SemCobertura': (1700, -1300),
    'GerarCatalogoPlanos':         ( 1950, -1500),
    'Step Aguarda CEP':            ( 2200, -1500),

    # === Lane aguarda_confirmacao_cep (Y=-1100) ===
    'ClassificarConfirmacao':      (  450, -1100),
    'Confirmou?':                  (  700, -1100),
    'Step Confirma Sim':           (  950, -1050),
    'Step Confirma Nao':           (  950, -1100),
    'Step Reasking Confirma':      (  950, -1150),

    # === Lane aguarda_numero + complemento (Y=-800) ===
    'Step Aguarda Numero':         (  450, -800),
    'GerarCatalogoPlanos2':        (  700, -800),
    'Step Aguarda Complemento':    (  950, -800),

    # === Lane aguarda_plano (Y=-500) ===
    'ValidarEscolhaPlano':         (  450, -500),
    'Plano Valido?':               (  700, -500),
    'Step Aguarda Plano':          (  950, -500),

    # === Lane aguarda_email (Y=-200) ===
    'ValidarEmail':                (  450, -200),
    'Email Valido?':               (  700, -200),
    'Step Aguarda Email (Final)':  (  950, -200),

    # === Lane aguarda_nome / inicio (Y=300) ===
    'Step Inicio':                 (  450,  300),
    'Step Aguarda Nome':           (  700,  300),

    # === Lane aguarda_cpf (Y=600) ===
    'ValidarCPF':                  (  450,  600),
    'CPF Valido?':                 (  700,  600),
    'Step Aguarda CPF':            (  950,  600),

    # === Lane aguarda_data_nasc (Y=900) ===
    'ValidarDataDeNascimento':     (  450,  900),
    'Data Valida?':                (  700,  900),
    'Step Aguarda Data Nasc':      (  950,  900),

    # === Lane RG frente + verso (Y=1200) ===
    'ValidarImagemRGFrente':       (  450, 1200),
    'Imagem RG Frente OK?':        (  700, 1200),
    'Step Aguarda RG Frente':      (  950, 1200),
    'Step Reasking RG Frente':     (  950, 1300),
    'ValidarImagemRGVerso':        ( 1200, 1200),
    'Imagem RG Verso OK?':         ( 1450, 1200),
    'Step Aguarda RG Verso':       ( 1700, 1200),
    'Step Reasking RG Verso':      ( 1700, 1300),

    # === Lane confirmacao_final (Y=1600) ===
    'ClassificarConfirmacaoFinal': (  450, 1600),
    'Confirmou Final?':            (  700, 1600),
    'Step Final Concluido':        (  950, 1550),
    'Step Final Reiniciar':        (  950, 1650),
    'Step Reasking Confirma Final':(  950, 1750),

    # === Lane aguarda_humano + concluido (Y=1950) ===
    'Step Aguarda Humano':         (  450, 1950),
    'ClassificarPosConcluido':     (  450, 2100),
    'Decisao Pos Concluido?':      (  700, 2100),
    'Step Pergunta Pos Concluido': (  700, 1950),
    'Step Novo Pedido':            (  950, 2050),
    'Step Humano Pos Concluido':   (  950, 2100),
    'Step Reasking Pos Concluido': (  950, 2150),

    # === Lane correcao (Y=2300+) ===
    'ClassificarCampoCorrigir':    (  450, 2300),
    'Router Correcao':             (  700, 2300),
    'Step Corrigir Nome':          (  950, 2250),
    'Step Corrigir Cep':           (  950, 2300),
    'Step Corrigir Numero':        (  950, 2350),
    'Step Corrigir Complemento':   (  950, 2400),
    'Step Corrigir Plano':         (  950, 2450),
    'Step Corrigir Cpf':           (  950, 2500),
    'Step Corrigir Data nasc':     (  950, 2550),
    'Step Corrigir Email':         (  950, 2600),
    'Step Corrigir Rg':            (  950, 2650),
    'Step Reasking Corrigir':      (  950, 2700),

    # === IA Validator Universal e contextos (Y=-300, fora do tronco) ===
    'Contexto Email':              ( 1400, -200),
    'Contexto CEP':                ( 1400, -1500),
    'Contexto Plano':              ( 1400, -500),
    'Contexto CPF':                ( 1400,  600),
    'Contexto Data Nasc':          ( 1400,  900),
    'IA Validator Universal':      ( 1700, -300),
    'OpenAI gpt-4o-mini':          ( 1700, -100),  # sub-nodo do agent
    'ResultadoIA':                 ( 1900, -300),
    'IA OK?':                      ( 2100, -300),
    'Router IA Tipo':              ( 2300, -400),
    'Router IA Tipo Erro':         ( 2300, -200),

    # === Steps via IA (right side of routers) ===
    'Step Aguarda Email (via IA)': ( 2500, -300),
    'Step Reasking Email (via IA)':( 2500, -200),
    'CEP Resolvido IA':            ( 2500, -1500),  # volta pra HTTP ViaCEP (loop visual)
    'Step Reasking CEP (via IA)':  ( 2500, -1100),
    'Step Aguarda Plano (via IA)': ( 2500, -500),
    'Step Reasking Plano':         ( 2500, -600),
    'Step Aguarda CPF (via IA)':   ( 2500,  600),
    'Step Reasking CPF':           ( 2500,  700),
    'Step Aguarda Data Nasc (via IA)': (2500, 900),
    'Step Reasking Data Nasc':     ( 2500, 1000),

    # === Convergencia (X=2800+) ===
    'SmartSkip':                   ( 2800,    0),
    'Save Session':                ( 3000,    0),
    'PegarRespostaBot':            ( 3200,    0),
    'RegistrarMsgBot':             ( 3400,    0),
    'Enviar Wazapi':               ( 3600, -150),
    'Respond OK':                  ( 3800, -150),
    'Finalizou?':                  ( 3600,  150),
    'Enviar Lead Hubtrix':         ( 3800,  150),
}

r = requests.get(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, timeout=15)
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

print(f'Reposicionados: {moved}/{len(wf["nodes"])}')
if unmoved:
    print(f'NAO mapeados: {len(unmoved)}')
    for n in unmoved:
        print(f'  - {n}')

allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF_ID}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT {r.status_code}')
