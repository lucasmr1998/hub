"""Aplica os ajustes estruturais no flow_v5.json pra suportar o menu de
cliente Hubsoft existente e o pipeline dinâmico.

Mudanças:
1. red_inicia_venda: usa {#proxima_pergunta_id} em vez de hardcoded
   'coleta_nome' (assim respeita o que o backend retorna como 1ª pergunta).
2. dec_roteamento_inicial: adiciona ramo pra status_lead='cliente_ativo'
   → vai pro red_cliente_ativo (novo) que entra no msg_pergunta com o
   menu retornado pelo backend.
3. api_validar: além dos campos atuais, captura 'mensagem_resposta' (msg
   composta pelo engine ao validar — ex: info da OS).
4. dec_resultado: ramo "Padrão (válido)" passa por um NOVO msg_resultado
   (que exibe {#mensagem_resposta} se preenchido) ANTES de voltar pro
   api_proximo_passo.
5. Ramo "needsReception=true" passa pelo MESMO msg_resultado antes do
   transbordo final — assim cliente vê a msg específica (ex: "Vou te
   transferir pra falar sobre upgrade").

Esses ajustes permitem:
- Cliente Hubsoft detectado pós-CPF → bot reconhece, retorna sem
  transbordar, próximo proximo-passo retorna o MENU.
- Opção 3 (acompanhar OS) → engine retorna info da OS em mensagem_resposta
  + needsReception=true. Flow exibe a info E transborda em sequência.
- Opções 1/2/4 → mesma mecânica: msg específica + transbordo.

Uso:
    python patch_flow_v5.py
        → escreve ../fluxos/flow_v5_patched.json
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent  # ia_validacao/
ENTRADA = BASE / 'fluxos' / 'flow_v5.json'
SAIDA   = BASE / 'fluxos' / 'flow_v5_patched.json'


# IDs e variáveis usadas (referenciados pelo flow original)
VAR_MENSAGEM_RESPOSTA = 9300009  # novo: msg composta pelo engine no /validar
VAR_QUESTION_ID_ATUAL = 9200012  # já existe
VAR_STATUS_LEAD       = 9300001
VAR_PROXIMA_PERGUNTA  = 9300003
VAR_NEEDS_RECEPTION   = 3620080
VAR_RESPOSTA_CORRETA  = 3620068

# IDs de nodos novos (não devem colidir com existentes)
ID_RED_CLIENTE_ATIVO       = 9300205   # ATENÇÃO: já existe um bloco com este id (group)
ID_RED_CLIENTE_ATIVO_NEW   = 9302001
ID_MSG_RESULTADO           = 9302002
ID_RED_APOS_RESULTADO      = 9302003
ID_MSG_PRE_TRANSBORDO      = 9302004
ID_EDGE_CLIENTE_ATIVO      = 9302100
ID_EDGE_VALIDO_NEW         = 9302101
ID_EDGE_VALIDO_LOOP        = 9302102
ID_EDGE_TRANSBORDO_NEW     = 9302103
ID_EDGE_TRANSBORDO_LOOP    = 9302104


def carregar() -> dict:
    return json.loads(ENTRADA.read_text(encoding='utf-8'))


def salvar(data: dict) -> None:
    SAIDA.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                     encoding='utf-8')
    print(f'OK escrito: {SAIDA.relative_to(BASE.parent)}  '
          f'({SAIDA.stat().st_size:,} bytes)')


def achar_node(flow: list, **filtros) -> dict:
    """Acha o primeiro node que bate com TODOS os filtros.

    Pra `identifier`, busca em data.identifier OU data.api.identifier
    (componentes API usam o segundo).
    """
    for n in flow:
        ok = True
        for k, v in filtros.items():
            if k == 'identifier':
                data = n.get('data') or {}
                ident_direto = data.get('identifier') if isinstance(data, dict) else None
                ident_api    = ((data.get('api') or {}).get('identifier')
                                if isinstance(data, dict) else None)
                if v not in (ident_direto, ident_api):
                    ok = False; break
            elif n.get(k) != v:
                ok = False; break
        if ok:
            return n
    raise ValueError(f'Node não achado: {filtros}')


def remover_edge(flow: list, source: int, target: int) -> None:
    """Remove edge específica (source→target)."""
    flow[:] = [n for n in flow
               if not (n.get('edge') and n.get('source') == source
                       and n.get('target') == target)]


# ─────────────────────────────────────────────────────────────────────
# Mutações
# ─────────────────────────────────────────────────────────────────────

def aplicar_correcao_inicia_venda(flow: list) -> None:
    """red_inicia_venda: usa {#proxima_pergunta_id} em vez de hardcoded."""
    node = achar_node(flow, identifier='red_inicia_venda')
    node['data']['values'] = ['{#proxima_pergunta_id}']
    print('  ✓ red_inicia_venda: agora usa {#proxima_pergunta_id}')


def redirecionar_status_finalizados_pro_menu(flow: list) -> None:
    """red_ja_agendado aponta pra msg_pergunta (menu de cliente).

    instalacao_agendada agora retorna o menu pelo backend, então o redirect
    do Matrix deve ir pro msg_pergunta (que exibe {#mensagem_pergunta}).

    aguardando_assinatura NÃO entra aqui — esse cliente ainda não tem
    serviço/OS no Hubsoft, então mantém o transbordo direto (msg_1).
    """
    msg_pergunta_id = 9301001
    for ident in ('red_ja_agendado',):
        try:
            node = achar_node(flow, identifier=ident)
        except ValueError:
            print(f'  · {ident} não achado (skip)')
            continue
        old = node['data'].get('component')
        node['data']['component'] = msg_pergunta_id
        # Adiciona setter de question_id (variables/values) pra que msg_pergunta
        # saiba qual question_id seguir.
        node['data']['variables'] = [9200012]   # var question_id_atual
        node['data']['values'] = ['{#proxima_pergunta_id}']
        print(f'  ✓ {ident}: redireciona pra msg_pergunta '
              f'(antes apontava pra component={old})')


def adicionar_ramo_cliente_ativo(flow: list, parent_id: int) -> None:
    """Adiciona ramo cliente_ativo no dec_roteamento_inicial.

    Esse ramo aponta pro mesmo red_retomar_de_onde_parou (que já usa
    {#proxima_pergunta_id} → vira 'menu_cliente_existente' retornado
    pelo backend).
    """
    dec = achar_node(flow, identifier='dec_roteamento_inicial')
    retomar = achar_node(flow, identifier='red_retomar_de_onde_parou')

    edge = {
        'parent': parent_id,
        'id': ID_EDGE_CLIENTE_ATIVO,
        'edge': True,
        'cod_componente': '',
        'style': ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                  'exitX=0.5;exitY=1;entryX=0.5;entryY=0;jettySize=auto;'
                  'orthogonalLoop=1;fontColor=#9932CC;strokeColor=#9932CC;'),
        'source': dec['id'],
        'target': retomar['id'],
        'value': 'cliente_ativo',
        'data': {
            'cnt': {'type': 'option'},
            'opt': {'type': 1, 'variable': VAR_STATUS_LEAD,
                    'operator': 1, 'value': 'cliente_ativo', 'field_compare': ''},
        },
    }
    flow.append(edge)
    print('  ✓ dec_roteamento_inicial: ramo cliente_ativo → red_retomar_de_onde_parou')


def adicionar_captura_mensagem_resposta(flow: list) -> None:
    """api_validar: adiciona 'mensagem_resposta' nos campos capturados."""
    node = achar_node(flow, identifier='api_validar')
    store = node['data']['store']
    if VAR_MENSAGEM_RESPOSTA in store['variable']:
        print('  · api_validar: mensagem_resposta já capturado (skip)')
        return
    store['variable'].append(VAR_MENSAGEM_RESPOSTA)
    store['returned'].append('mensagem_resposta')
    print('  ✓ api_validar: captura mensagem_resposta')


def adicionar_msg_resultado_e_redirects(flow: list, parent_bloco_id: int) -> None:
    """Adiciona msg_resultado (exibe mensagem_resposta) entre dec_resultado e
    os destinos finais (transbordo e loop pro api_proximo_passo).

    Reorganiza:
      ANTES: dec_resultado → red_transbordo (transbordo) / red_volta_consulta (válido)
      DEPOIS: dec_resultado → msg_resultado → red_apos_resultado (decisão final via
              variável needsReception preservada)

    Como o componente Decisão do Matrix só ramifica uma vez (no dec_resultado),
    e queremos exibir a msg ANTES de transbordar OU voltar, vamos:
      1. dec_resultado ramo "needsReception=true" → msg_pre_transbordo → red_transbordo
      2. dec_resultado ramo "Padrão (válido)"     → msg_resultado     → red_volta_consulta
      3. dec_resultado ramo "resposta_correta=false" → msg_erro (sem mudança)

    Cada caminho exibe SUA OWN mensagem (mensagem_resposta no válido, mensagem_resposta
    no pré-transbordo — mas as msgs DIFERENTES vem do engine).
    """
    dec = achar_node(flow, identifier='dec_resultado')
    api_proximo = achar_node(flow, identifier='api_proximo_passo')
    msg_1 = achar_node(flow, identifier='msg_1')

    # Remove edges antigas que ligam dec_resultado direto aos redirecionadores
    # (red_transbordo e red_volta_consulta). Vamos substituir por edges que
    # passam pelos novos msg_resultado/msg_pre_transbordo.
    red_transbordo = achar_node(flow, identifier='red_transbordo')
    red_volta = achar_node(flow, identifier='red_volta_consulta')

    remover_edge(flow, dec['id'], red_transbordo['id'])
    remover_edge(flow, dec['id'], red_volta['id'])

    # ── 1) Novo msg_pre_transbordo (componente mensagem) ─────────────
    msg_pre_transbordo = {
        'parent': parent_bloco_id,
        'id': ID_MSG_PRE_TRANSBORDO,
        'quantityCon': 1,
        'edge': False,
        'cod_componente': 1,    # mensagem
        'height': 50, 'width': 50,
        'x': 370, 'y': 320,
        'relative': False, 'value': '',
        'data': {
            'identifier': 'msg_pre_transbordo',
            'retention': 0, 'bot_tts': 0, 'bot_tts_type_send': 1,
            'hsm': 0, 'force_hsm': 0, 'num_delay': 0,
            'tipo_mensagem': 0, 'msg_interativa': 0,
            'messages': ['{#mensagem_resposta}'],
        },
    }
    flow.append(msg_pre_transbordo)

    # ── 2) Novo msg_resultado (válido) ───────────────────────────────
    msg_resultado = {
        'parent': parent_bloco_id,
        'id': ID_MSG_RESULTADO,
        'quantityCon': 1,
        'edge': False,
        'cod_componente': 1,
        'height': 50, 'width': 50,
        'x': 540, 'y': 80,
        'relative': False, 'value': '',
        'data': {
            'identifier': 'msg_resultado',
            'retention': 0, 'bot_tts': 0, 'bot_tts_type_send': 1,
            'hsm': 0, 'force_hsm': 0, 'num_delay': 0,
            'tipo_mensagem': 0, 'msg_interativa': 0,
            'messages': ['{#mensagem_resposta}'],
        },
    }
    flow.append(msg_resultado)

    # ── 3) Edges novas ───────────────────────────────────────────────
    # dec_resultado → msg_pre_transbordo (needsReception=true)
    flow.append({
        'parent': parent_bloco_id, 'id': ID_EDGE_TRANSBORDO_NEW, 'edge': True,
        'cod_componente': '',
        'style': ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                  'exitX=0.5;exitY=1;entryX=0.5;entryY=0;jettySize=auto;'
                  'orthogonalLoop=1;fontColor=#FF0000;strokeColor=#FF0000;'),
        'source': dec['id'], 'target': msg_pre_transbordo['id'],
        'value': 'needsReception=true',
        'data': {
            'cnt': {'type': 'option'},
            'opt': {'type': 1, 'variable': VAR_NEEDS_RECEPTION,
                    'operator': 1, 'value': 'true', 'field_compare': ''},
        },
    })

    # msg_pre_transbordo → red_transbordo (componente edge simples)
    flow.append({
        'parent': parent_bloco_id, 'id': ID_EDGE_TRANSBORDO_LOOP, 'edge': True,
        'cod_componente': '',
        'style': ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                  'exitX=1;exitY=0.5;entryX=0;entryY=0.5;jettySize=auto;'
                  'orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;'),
        'source': msg_pre_transbordo['id'], 'target': red_transbordo['id'],
        'data': False,
    })

    # dec_resultado → msg_resultado (Padrão válido)
    flow.append({
        'parent': parent_bloco_id, 'id': ID_EDGE_VALIDO_NEW, 'edge': True,
        'cod_componente': '',
        'style': ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                  'exitX=1;exitY=0.5;entryX=0;entryY=0.5;jettySize=auto;'
                  'orthogonalLoop=1;fontColor=#008000;strokeColor=#008000;'),
        'source': dec['id'], 'target': msg_resultado['id'],
        'value': 'Padrão (válido)',
        'data': {
            'cnt': {'type': 'default'},
            'opt': {'type': 1, 'variable': VAR_RESPOSTA_CORRETA,
                    'operator': 1, 'value': 'false', 'field_compare': ''},
        },
    })

    # msg_resultado → red_volta_consulta
    flow.append({
        'parent': parent_bloco_id, 'id': ID_EDGE_VALIDO_LOOP, 'edge': True,
        'cod_componente': '',
        'style': ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                  'exitX=1;exitY=0.5;entryX=0;entryY=0.5;jettySize=auto;'
                  'orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;'),
        'source': msg_resultado['id'], 'target': red_volta['id'],
        'data': False,
    })

    print('  ✓ dec_resultado: passa por msg_resultado/msg_pre_transbordo antes dos redirects')


def adicionar_encerramento_atendimento_concluido(flow: list, parent_id: int) -> None:
    """Adiciona msg_despedida + red_encerrar + ramo atendimento_concluido.

    Quando o backend retornar status_lead='atendimento_concluido' (cliente
    escolheu encerrar após ver OS ou agendamento), o flow vai pro nó
    msg_despedida (exibe `{#mensagem_pergunta}`) → fin_1 (finalizar sem
    transbordar).
    """
    dec = achar_node(flow, identifier='dec_roteamento_inicial')
    try:
        fin_node = achar_node(flow, identifier='fin_1')
    except ValueError:
        print('  · fin_1 não achado — pulando encerramento')
        return

    ID_MSG_DESPEDIDA = 9303001
    ID_RED_ENCERRAR  = 9303002
    ID_EDGE_DESPEDIDA = 9303101
    ID_EDGE_RAMO_DEC = 9303102

    # Evita duplicação se rodar 2x
    if any((n.get('data') or {}).get('identifier') == 'red_encerrar' for n in flow):
        print('  · red_encerrar já existe (skip)')
        return

    # msg_despedida — exibe {#mensagem_pergunta} (composta pelo backend)
    flow.append({
        'parent': parent_id, 'id': ID_MSG_DESPEDIDA,
        'quantityCon': 1, 'edge': False, 'cod_componente': 1,
        'height': 50, 'width': 50, 'x': 200, 'y': 460, 'relative': False, 'value': '',
        'data': {
            'identifier': 'msg_despedida',
            'retention': 0, 'bot_tts': 0, 'bot_tts_type_send': 1,
            'hsm': 0, 'force_hsm': 0, 'num_delay': 0,
            'tipo_mensagem': 0, 'msg_interativa': 0,
            'messages': ['{#mensagem_pergunta}'],
        },
    })

    # red_encerrar (redirecionador pra msg_despedida)
    flow.append({
        'parent': parent_id, 'id': ID_RED_ENCERRAR,
        'quantityCon': 0, 'edge': False, 'cod_componente': 17,
        'height': 50, 'width': 50, 'x': 200, 'y': 540, 'relative': False, 'value': '',
        'data': {
            '3': '', '5': '',
            'identifier': 'red_encerrar', 'type': 1,
            'component': ID_MSG_DESPEDIDA, 'flow': '',
            'component_identifier': '',
        },
    })

    # Edge: msg_despedida → fin_1
    flow.append({
        'parent': parent_id, 'id': ID_EDGE_DESPEDIDA, 'edge': True,
        'cod_componente': '',
        'style': ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                  'exitX=1;exitY=0.5;entryX=0;entryY=0.5;jettySize=auto;'
                  'orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;'),
        'source': ID_MSG_DESPEDIDA, 'target': fin_node['id'],
        'data': False,
    })

    # Ramo no dec_roteamento_inicial: status_lead='atendimento_concluido' → red_encerrar
    flow.append({
        'parent': parent_id, 'id': ID_EDGE_RAMO_DEC, 'edge': True,
        'cod_componente': '',
        'style': ('edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;'
                  'exitX=0.5;exitY=1;entryX=0.5;entryY=0;jettySize=auto;'
                  'orthogonalLoop=1;fontColor=#1f497d;strokeColor=#1f497d;'),
        'source': dec['id'], 'target': ID_RED_ENCERRAR,
        'value': 'atendimento_concluido',
        'data': {
            'cnt': {'type': 'option'},
            'opt': {'type': 1, 'variable': 9300001,   # status_lead
                    'operator': 1, 'value': 'atendimento_concluido',
                    'field_compare': ''},
        },
    })
    print('  ✓ Encerramento: msg_despedida + red_encerrar + ramo atendimento_concluido')


def adicionar_variavel_mensagem_resposta(variaveis: dict) -> None:
    """Adiciona variável global mensagem_resposta."""
    key = str(VAR_MENSAGEM_RESPOSTA)
    if key in variaveis:
        print('  · variável mensagem_resposta já existe (skip)')
        return
    variaveis[key] = {'name': 'mensagem_resposta', 'value': ''}
    print(f'  ✓ variável global mensagem_resposta ({key}) criada')


# ─────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    data = carregar()
    flow = data['flow']

    parent_bloco_pergunta = 9300205   # bloco "Realizar uma Pergunta"
    parent_bloco_consulta = 6286       # bloco "Consulta_api"

    print(f'== Patching {ENTRADA.name} ({len(flow)} nodes) ==')

    aplicar_correcao_inicia_venda(flow)
    redirecionar_status_finalizados_pro_menu(flow)
    adicionar_ramo_cliente_ativo(flow, parent_bloco_consulta)
    adicionar_encerramento_atendimento_concluido(flow, parent_bloco_consulta)
    adicionar_captura_mensagem_resposta(flow)
    adicionar_msg_resultado_e_redirects(flow, parent_bloco_pergunta)
    adicionar_variavel_mensagem_resposta(data['variaveis'])

    print(f'== Resultado: {len(flow)} nodes ==')
    salvar(data)


if __name__ == '__main__':
    main()
