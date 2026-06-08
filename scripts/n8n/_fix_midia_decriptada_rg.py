"""Fix: bot usa URL .enc (criptografada) do WhatsApp pra IA Vision e registro
de RG -> falha (OpenAI nao baixa .enc, registro recebe JSON quebrado).

Solucao (opcao A): inserir nó HTTP que chama POST /message/download do Uazapi
(retorna fileURL decriptada e hospedada), entre 'Imagem RG X OK?' e 'IA Vision
RG X'. IA Vision e Registrar passam a usar a fileURL decriptada.

Idempotente: pula se o nó de download ja existe. Faz backup.
"""
import sys, json, uuid, datetime
sys.path.insert(0, 'scripts')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _n8n_api import N8N

WID = 'Df1BgcXdg3HAUZwf'
UAZAPI_DOWNLOAD = 'https://consulteplus.uazapi.com/message/download'
CRED = {'httpHeaderAuth': {'id': 'qdWluYpx0ExpQ6kX', 'name': 'Uazapi TR Carrion'}}

# (lado, ValidarNode, ImagemOKNode, IAVisionNode, RegistrarNode, posicao)
BRANCHES = [
    ('Frente', 'ValidarImagemRGFrente', 'Imagem RG Frente OK?',
     'IA Vision RG Frente', 'Registrar RG Frente Hubtrix', [-200, 1900]),
    ('Verso', 'ValidarImagemRGVerso', 'Imagem RG Verso OK?',
     'IA Vision RG Verso', 'Registrar RG Verso Hubtrix', [-200, 2200]),
]

n = N8N()
w = n.get_workflow(WID)
nodes = w['nodes']
conns = w['connections']
by_name = {nd['name']: nd for nd in nodes}

# Backup
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
bk = f'scripts/_backup_orquestrador_{ts}.json'
json.dump(w, open(bk, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('Backup:', bk)


def download_node(nome, pos):
    return {
        'parameters': {
            'method': 'POST',
            'url': UAZAPI_DOWNLOAD,
            'authentication': 'genericCredentialType',
            'genericAuthType': 'httpHeaderAuth',
            'sendHeaders': True,
            'headerParameters': {'parameters': [
                {'name': 'Content-Type', 'value': 'application/json'}]},
            'sendBody': True,
            'specifyBody': 'json',
            'jsonBody': "={ \"id\": {{ JSON.stringify($node['Entrada'].json.wa_msg_id) }} }",
            'options': {'timeout': 20000},
        },
        'type': 'n8n-nodes-base.httpRequest',
        'typeVersion': 4.2,
        'position': pos,
        'id': str(uuid.uuid4()),
        'name': nome,
        'credentials': CRED,
        'continueOnFail': True,
        'onError': 'continueRegularOutput',
        'retryOnFail': True,
        'maxTries': 3,
        'waitBetweenTries': 2000,
    }


mudou = False
for lado, validar, imagem_ok, ia_vision, registrar, pos in BRANCHES:
    dl_nome = f'Uazapi Download RG {lado}'
    if dl_nome in by_name:
        print(f'SKIP: {dl_nome} ja existe')
        continue
    for req in (imagem_ok, ia_vision, registrar, validar):
        if req not in by_name:
            print(f'ERRO: {req} nao existe — abortando')
            sys.exit(1)

    # 1. cria nó de download
    nd = download_node(dl_nome, pos)
    nodes.append(nd)
    by_name[dl_nome] = nd

    # 2. rewire: Imagem OK? output[0] (true) -> Download -> IA Vision
    main = conns.get(imagem_ok, {}).get('main', [])
    while len(main) < 1:
        main.append([])
    # output 0 deveria apontar pra ia_vision; troca pra download
    novo_out0 = []
    achou = False
    for c in main[0]:
        if c.get('node') == ia_vision:
            achou = True
            novo_out0.append({'node': dl_nome, 'type': 'main', 'index': 0})
        else:
            novo_out0.append(c)
    if not achou:
        print(f'AVISO: {imagem_ok} output0 nao apontava pra {ia_vision}; adicionando download mesmo assim')
        novo_out0.append({'node': dl_nome, 'type': 'main', 'index': 0})
    main[0] = novo_out0
    conns[imagem_ok] = {'main': main}
    conns[dl_nome] = {'main': [[{'node': ia_vision, 'type': 'main', 'index': 0}]]}

    # 3. IA Vision body: usa fileURL decriptada
    iav = by_name[ia_vision]['parameters']
    body = iav.get('jsonBody', '')
    novo_body = body.replace('{{ $json.url_imagem }}',
                             f"{{{{ $node['{dl_nome}'].json.fileURL }}}}")
    if novo_body == body:
        print(f'AVISO: nao achei url_imagem no body de {ia_vision}')
    iav['jsonBody'] = novo_body

    # 4. Registrar body: usa fileURL decriptada
    reg = by_name[registrar]['parameters']
    rbody = reg.get('jsonBody', '')
    ref_antiga = f"$node['{validar}'].json.url_imagem"
    ref_nova = f"$node['{dl_nome}'].json.fileURL"
    novo_rbody = rbody.replace(ref_antiga, ref_nova)
    if novo_rbody == rbody:
        print(f'AVISO: nao achei {ref_antiga} no body de {registrar}')
    reg['jsonBody'] = novo_rbody

    print(f'OK {lado}: +{dl_nome}, {imagem_ok}->{dl_nome}->{ia_vision}, '
          f'IA Vision e Registrar usando fileURL')
    mudou = True

if not mudou:
    print('\nNada a fazer.')
    sys.exit(0)

settings_orig = w.get('settings', {})
settings_limpo = {k: settings_orig[k] for k in (
    'executionOrder','saveManualExecutions','saveExecutionProgress',
    'saveDataErrorExecution','saveDataSuccessExecution','executionTimeout',
    'errorWorkflow','timezone','callerPolicy') if k in settings_orig}
payload = {'name': w['name'], 'nodes': nodes,
           'connections': conns, 'settings': settings_limpo}
print('\nEnviando PUT...')
res = n.update_workflow(WID, payload)
print('OK. nodes:', len(res.get('nodes', nodes)))
