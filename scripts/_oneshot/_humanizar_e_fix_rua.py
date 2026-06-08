"""
1. FIX: salva 'rua' (logradouro do ViaCEP) na sessao + exibe no resumo.
2. HUMANIZA: textos do bot mais carinhosos, identidade 'Ana / New World Telecom'.
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
WF = 'Df1BgcXdg3HAUZwf'

DPH = "$node['DetectarPedidoHumano'].json.dados"

# resposta_bot novos por Step
TEXTOS = {
    'Step Inicio': (
        "Oi! Tudo bem? 😊 Eu sou a Ana, da New World Telecom, "
        "estou aqui pra te ajudar da melhor forma 💙 Qual é o seu nome?"
    ),
    'Step Aguarda Nome': (
        "=Que bom falar com você, {{ $node['ValidarNome'].json.nome_formatado }}! 😊\n"
        "Me envia seu CEP, por favor? Assim consigo verificar a disponibilidade "
        "e as melhores opções pra você 💙"
    ),
    'Step Aguarda Complemento': (
        "=Ótimo! 😊💙 Verifiquei aqui os planos disponíveis em "
        "{{ " + DPH + ".cidade }} e tenho algumas opções que podem combinar "
        "com o que você precisa:\n\n"
        "{{ $node['GerarCatalogoPlanos2'].json.lista_formatada }}\n\n"
        "Qual dessas opções mais te interessou? Pode me mandar o número do plano "
        "ou descrever 😊"
    ),
    'Step Aguarda Plano': (
        "Ótima escolha! 😊💙\nAgora, pra darmos continuidade à contratação, "
        "me envia seu CPF, por favor? ✨"
    ),
    'Step Aguarda Plano (via IA)': (
        "Ótima escolha! 😊💙\nAgora, pra darmos continuidade à contratação, "
        "me envia seu CPF, por favor? ✨"
    ),
    'Step Aguarda CPF': (
        "Ótimo! 😊\nPode me informar sua data de nascimento, por favor?\n"
        "📅 Formato: dd/mm/aaaa ✨"
    ),
    'Step Aguarda CPF (via IA)': (
        "Ótimo! 😊\nPode me informar sua data de nascimento, por favor?\n"
        "📅 Formato: dd/mm/aaaa ✨"
    ),
    'Step Aguarda Data Nasc': (
        "Quase pronto! 😊💙 Pra fechar, qual o seu e-mail?"
    ),
    'Step Aguarda Data Nasc (via IA)': (
        "Quase pronto! 😊💙 Pra fechar, qual o seu e-mail?"
    ),
    'Step Aguarda Email (Final)': (
        "Perfeito! 😊💙 Agora preciso de uma foto da *frente* do seu RG "
        "(ou CNH) pra finalizar seu cadastro. Pode enviar aqui pelo WhatsApp? ✨"
    ),
    'Step Aguarda Email (via IA)': (
        "Perfeito! 😊💙 Agora preciso de uma foto da *frente* do seu RG "
        "(ou CNH) pra finalizar seu cadastro. Pode enviar aqui pelo WhatsApp? ✨"
    ),
    'Step Aguarda RG Frente': (
        "Recebi a frente! 📸✅ Agora me envia uma foto do *verso* do RG "
        "(ou CNH), por favor 💙"
    ),
    'Step Final Concluido': (
        "Perfeito! ✅ Seus dados foram registrados com sucesso 💙 "
        "Um consultor da New World Telecom entra em contato em até 24h "
        "pra finalizar a contratação. Muito obrigada! 😊"
    ),
    'Step Aguarda Humano': (
        "=Tudo bem! 😊 Vou anotar suas informações com carinho e em alguns "
        "minutos um consultor da New World Telecom entra em contato direto "
        "com você por aqui 💙\n\n"
        "Pode mandar qualquer detalhe extra que eu já deixo guardado pro vendedor."
    ),
}

# Resumo final (Step Aguarda RG Verso) — agora com rua
RESUMO_RG_VERSO = (
    "=Perfeito! 😊💙 Recebi tudo certinho!\n\n"
    "Antes de finalizar, dá uma conferida nas informações pra garantir que "
    "está tudo correto ✨\n\n"
    f"👤 *Nome:* {{{{ {DPH}.nome }}}}\n"
    f"📧 *Email:* {{{{ {DPH}.email }}}}\n"
    f"🆔 *CPF:* {{{{ {DPH}.cpf }}}}\n"
    f"🎂 *Nascimento:* {{{{ {DPH}.data_nascimento }}}}\n\n"
    "📍 *Endereço:*\n"
    f"   {{{{ {DPH}.rua || '(rua nao informada)' }}}}, {{{{ {DPH}.numero }}}}"
    f"{{{{ {DPH}.complemento ? ' - ' + {DPH}.complemento : '' }}}}\n"
    f"   {{{{ {DPH}.bairro }}}} - {{{{ {DPH}.cidade }}}}/{{{{ {DPH}.estado }}}}\n"
    f"   CEP: {{{{ {DPH}.cep }}}}\n\n"
    f"📡 *Plano:* {{{{ {DPH}.plano_interesse }}}}\n\n"
    "📎 RG frente + verso recebidos ✅\n\n"
    "Posso confirmar? (sim/nao)"
)

r = requests.get(f'{BASE}/api/v1/workflows/{WF}', headers=HEADERS, timeout=15)
wf = r.json()

def set_resposta(node, texto):
    for a in node['parameters']['assignments']['assignments']:
        if a.get('name') == 'resposta_bot':
            a['value'] = texto
            return True
    return False

mud = 0
for n in wf['nodes']:
    nm = n['name']
    if nm in TEXTOS:
        if set_resposta(n, TEXTOS[nm]):
            print(f'  texto: {nm}')
            mud += 1
    if nm == 'Step Aguarda RG Verso':
        if set_resposta(n, RESUMO_RG_VERSO):
            print(f'  resumo: {nm} (com rua)')
            mud += 1
    # FIX RUA — Step Aguarda CEP salva logradouro
    if nm == 'Step Aguarda CEP':
        for a in n['parameters']['assignments']['assignments']:
            if a.get('name') == 'novas_vars':
                a['value'] = (
                    "={{ Object.assign({}, $node['DetectarPedidoHumano'].json.dados, "
                    "{ cep: $node['ValidarCepFormato'].json.cep_limpo, "
                    "rua: $node['HTTP ViaCEP'].json.logradouro, "
                    "cidade: $node['HTTP ViaCEP'].json.localidade, "
                    "estado: $node['HTTP ViaCEP'].json.uf, "
                    "bairro: $node['HTTP ViaCEP'].json.bairro }) }}"
                )
                print(f'  fix rua: {nm} novas_vars salva logradouro')
                mud += 1

# SmartSkip — resumo com rua
for n in wf['nodes']:
    if n['name'] == 'SmartSkip':
        code = n['parameters']['jsCode']
        if 'const rua =' not in code:
            code = code.replace(
                "const complemento = dados.complemento ? ` - ${dados.complemento}` : '';",
                "const complemento = dados.complemento ? ` - ${dados.complemento}` : '';\n"
                "  const rua = dados.rua ? `${dados.rua}, ` : '';"
            )
            code = code.replace("`   ${dados.numero}${complemento}\n`", "`   ${rua}${dados.numero}${complemento}\n`")
            n['parameters']['jsCode'] = code
            print('  fix rua: SmartSkip resumo')
            mud += 1

print(f'\nTotal mudancas: {mud}')
allowed = {'saveExecutionProgress','saveManualExecutions','saveDataErrorExecution','saveDataSuccessExecution','executionTimeout','errorWorkflow','timezone','executionOrder'}
clean = {k:v for k,v in (wf.get('settings') or {}).items() if k in allowed}
payload = {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'], 'settings': clean}
r = requests.put(f'{BASE}/api/v1/workflows/{WF}', headers=HEADERS, data=json.dumps(payload), timeout=20)
print(f'PUT {r.status_code}')
if r.status_code >= 300:
    print(r.text[:500])
