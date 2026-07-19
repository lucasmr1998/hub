"""Gera flow_dinamico.json — fluxo Matrix MÍNIMO que delega 100% pra API IA Validação.

Estrutura (~25 nós vs 538 do original):

  INICIO
    start → set_var → msg_boas_vindas → red_para_loop

  CONVERSA (loop)
    sol_loop → api_conversar → dec_destino
      ↓ tipo_acao == "pedir_imagem" → msg_pedir + sol_imagem → red_loop
      ↓ tipo_acao == "aguarda_hubsoft" → wait_20s → red_loop (faz poll)
      ↓ tipo_acao == "transbordo"   → red_transbordo
      ↓ tipo_acao == "fim"          → red_fim
      ↓ default (responder)         → msg_bot → red_loop

  FINALIZACAO: msg + fin
  TRANSBORDO HUMANO: msg + ser

A API IA decide tudo. O Matrix só executa.

Uso:
    python tools/gerar_flow_dinamico.py [--api-url URL] [--saida ARQUIVO]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


# IDs das variáveis novas (não devem colidir com flow original)
VAR_URL_IA = 9100001
VAR_MENSAGEM_BOT = 9100002
VAR_FIM_FLUXO = 9100003
VAR_TRANSBORDO = 9100004
VAR_INTENCAO = 9100005
VAR_TIPO_ACAO = 9100006
VAR_IMAGEM_URL = 9100007


def gerar(api_url: str) -> dict:
    api_url = api_url.rstrip('/')
    url_endpoint = f'{api_url}/conversar'

    flow = {
        'flow': [
            # ── raiz Matrix ──────────────────────────────────────────────
            {'parent': 1, 'id': 0, 'edge': False, 'cod_componente': '', 'data': False},
            {'parent': 0, 'id': 1, 'edge': False, 'cod_componente': '',
             'data': {
                 'name': 'aurora_dinamico', 'account': 2,
                 'bot_stt': 0, 'bot_tts': 0,
                 'error_handling': 1, 'service_check_hour': 0,
                 'integrate_genesys': 0,
                 'finish_message': '', 'service_hour_message': '',
                 'nom_msg_rodape': '', 'active': 1,
             }},

            # ── GRUPO 100: INÍCIO ────────────────────────────────────────
            {'collapsed': 0, 'parent': 1, 'id': 100,
             'edge': False, 'cod_componente': 18,
             'height': 200, 'width': 800, 'x': 10, 'y': 10, 'relative': False,
             'value': 'INICIO', 'data': False},

            {'parent': 100, 'id': 101, 'quantityCon': 1, 'edge': False,
             'cod_componente': 15, 'height': 85, 'width': 85,
             'x': 20, 'y': 60, 'relative': False, 'data': {'bot_stt': ''}},

            {'parent': 100, 'id': 102, 'quantityCon': 1, 'edge': False,
             'cod_componente': 13, 'height': 50, 'width': 50,
             'x': 200, 'y': 80, 'relative': False, 'value': '',
             'data': {
                 'identifier': 'var_url_ia',
                 'variables': [VAR_URL_IA, VAR_IMAGEM_URL],
                 'values': [url_endpoint, ''],
             }},

            {'parent': 100, 'id': 104, 'quantityCon': 0, 'edge': False,
             'cod_componente': 17, 'height': 50, 'width': 50,
             'x': 400, 'y': 80, 'relative': False, 'value': '',
             'data': {'identifier': 'red_para_loop', 'type': 1,
                      'component': 201, 'flow': '', 'component_identifier': ''}},

            {'parent': 100, 'id': 110, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 101, 'target': 102, 'data': False},
            {'parent': 100, 'id': 112, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 102, 'target': 104, 'data': False},

            # ── GRUPO 200: LOOP CONVERSA ─────────────────────────────────
            {'collapsed': 0, 'parent': 1, 'id': 200,
             'edge': False, 'cod_componente': 18,
             'height': 480, 'width': 1100, 'x': 10, 'y': 220, 'relative': False,
             'value': 'CONVERSA (loop)', 'data': False},

            # sol_loop — aguarda mensagem do cliente (texto OU imagem)
            {'parent': 200, 'id': 201, 'quantityCon': 3, 'edge': False,
             'cod_componente': 2, 'height': 50, 'width': 50,
             'x': 50, 'y': 60, 'relative': False, 'value': '',
             'data': {
                 'identifier': 'sol_loop',
                 'variable': 0,
                 'validation': 0, 'validation_regex': '',
                 'timeout': '{#tempo_de_inatividade}',
                 'update_db': 0, 'allow_upload': 1,
                 'mask': 0, 'bot_stt': 0,
             }},

            # api_conversar — POST /conversar (texto)
            {'parent': 200, 'id': 202, 'quantityCon': 1, 'edge': False,
             'cod_componente': 9, 'height': 50, 'width': 50,
             'x': 230, 'y': 60, 'relative': False, 'value': '',
             'data': {
                 'api': {
                     'identifier': 'api_conversar',
                     'url': url_endpoint,
                     'method': 1, 'async': 0, 'async_condition': '',
                     'timeout': 30,
                 },
                 'auth': {'auth_type': 0, 'access_key': '', 'secret_key': '',
                          'aws_region': '', 'service_name': '',
                          'username': '', 'password': '',
                          'username_ntlm': '', 'password_ntlm': ''},
                 'headers': {
                     'key': ['Content-Type'],
                     'value': ['application/json'],
                 },
                 'body': {
                     'body': json.dumps({
                         'telefone': '{#CONTATO.TELEFONE}',
                         'mensagem': '{#MENSAGEM}',
                         'url_imagem': '{#imagem_url}',
                     }, indent=2, ensure_ascii=False),
                 },
                 'store': {
                     'filter': 1,
                     'variable': [VAR_MENSAGEM_BOT, VAR_FIM_FLUXO,
                                  VAR_TRANSBORDO, VAR_INTENCAO, VAR_TIPO_ACAO],
                     'returned': ['mensagem_bot', 'fim_fluxo',
                                  'transbordo_humano', 'intencao', 'tipo_acao'],
                 },
             }},

            # dec_destino
            {'parent': 200, 'id': 203, 'edge': False,
             'cod_componente': 8, 'height': 50, 'width': 50,
             'x': 410, 'y': 60, 'relative': False, 'value': '',
             'data': {'identifier': 'dec_destino'}},

            # msg_bot (resposta default — Aurora respondeu algo)
            {'parent': 200, 'id': 204, 'quantityCon': 1, 'edge': False,
             'cod_componente': 1, 'height': 50, 'width': 50,
             'x': 590, 'y': 60, 'relative': False, 'value': '',
             'data': {
                 'identifier': 'msg_bot',
                 'retention': 0, 'bot_tts': 0, 'bot_tts_type_send': 1,
                 'hsm': 0, 'force_hsm': 0, 'num_delay': 0,
                 'tipo_mensagem': 0, 'msg_interativa': 0,
                 'messages': ['{#mensagem_bot_var}'],
             }},

            # var: zera imagem_url depois de cada envio (pra próximo turno default ser texto)
            {'parent': 200, 'id': 240, 'quantityCon': 1, 'edge': False,
             'cod_componente': 13, 'height': 50, 'width': 50,
             'x': 730, 'y': 60, 'relative': False, 'value': '',
             'data': {
                 'identifier': 'var_zera_imagem',
                 'variables': [VAR_IMAGEM_URL],
                 'values': [''],
             }},

            # red: msg_bot → volta pro sol_loop
            {'parent': 200, 'id': 205, 'quantityCon': 0, 'edge': False,
             'cod_componente': 17, 'height': 50, 'width': 50,
             'x': 870, 'y': 60, 'relative': False, 'value': '',
             'data': {'identifier': 'red_voltar_loop', 'type': 1,
                      'component': 201, 'flow': '', 'component_identifier': ''}},

            # red: → FIM (fim_fluxo == true OU tipo_acao == fim)
            {'parent': 200, 'id': 206, 'quantityCon': 0, 'edge': False,
             'cod_componente': 17, 'height': 50, 'width': 50,
             'x': 410, 'y': 380, 'relative': False, 'value': '',
             'data': {'identifier': 'red_fim', 'type': 1,
                      'component': 301, 'flow': '', 'component_identifier': ''}},

            # red: → TRANSBORDO
            {'parent': 200, 'id': 207, 'quantityCon': 0, 'edge': False,
             'cod_componente': 17, 'height': 50, 'width': 50,
             'x': 590, 'y': 380, 'relative': False, 'value': '',
             'data': {'identifier': 'red_transbordo', 'type': 1,
                      'component': 401, 'flow': '', 'component_identifier': ''}},

            # red: timeout do sol_loop → FIM
            {'parent': 200, 'id': 208, 'quantityCon': 0, 'edge': False,
             'cod_componente': 17, 'height': 50, 'width': 50,
             'x': 50, 'y': 380, 'relative': False, 'value': '',
             'data': {'identifier': 'red_timeout', 'type': 1,
                      'component': 301, 'flow': '', 'component_identifier': ''}},

            # red: sol inválido → transbordo (raro)
            {'parent': 200, 'id': 209, 'quantityCon': 0, 'edge': False,
             'cod_componente': 17, 'height': 50, 'width': 50,
             'x': 230, 'y': 380, 'relative': False, 'value': '',
             'data': {'identifier': 'red_invalido', 'type': 1,
                      'component': 401, 'flow': '', 'component_identifier': ''}},

            # wait 20s — usado quando tipo_acao == aguarda_hubsoft (espera antes de chamar /conversar de novo)
            {'parent': 200, 'id': 230, 'quantityCon': 1, 'edge': False,
             'cod_componente': 26, 'height': 50, 'width': 50,
             'x': 410, 'y': 200, 'relative': False, 'value': '',
             'data': {'identifier': 'wait_hubsoft', 'num_wait': 20}},

            # set: prepara nova chamada /conversar enquanto aguarda hubsoft (mensagem fake "verificar")
            {'parent': 200, 'id': 231, 'quantityCon': 1, 'edge': False,
             'cod_componente': 13, 'height': 50, 'width': 50,
             'x': 590, 'y': 200, 'relative': False, 'value': '',
             'data': {
                 'identifier': 'var_mensagem_poll',
                 # MENSAGEM não é settable, então usa um truque: dispara nova chamada /conversar
                 # com a etapa atual mantida (a API entende e re-polla hubsoft)
                 'variables': [VAR_IMAGEM_URL],
                 'values': [''],
             }},

            # red: aguarda_hubsoft → wait → api_conversar de novo
            {'parent': 200, 'id': 232, 'quantityCon': 0, 'edge': False,
             'cod_componente': 17, 'height': 50, 'width': 50,
             'x': 770, 'y': 200, 'relative': False, 'value': '',
             'data': {'identifier': 'red_poll_hubsoft', 'type': 1,
                      'component': 202, 'flow': '', 'component_identifier': ''}},

            # ── edges do loop ───────────────────────────────────────────
            # sol_loop → api_conversar (Validado)
            {'parent': 200, 'id': 220, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;exitX=1;exitY=0.5;entryX=0;entryY=0.5;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 201, 'target': 202, 'value': 'Validado',
             'data': {'validation_condition': 1}},

            # sol_loop → Inválido → transbordo
            {'parent': 200, 'id': 226, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#FF8C00;strokeColor=#FF8C00;',
             'source': 201, 'target': 209, 'value': 'Inválido',
             'data': {'validation_condition': 2}},

            # sol_loop → Timeout → fim
            {'parent': 200, 'id': 227, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#778899;strokeColor=#778899;',
             'source': 201, 'target': 208, 'value': 'Tempo de espera',
             'data': {'validation_condition': 3}},

            # api_conversar → dec_destino
            {'parent': 200, 'id': 221, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 202, 'target': 203, 'data': {'condition': 1}},

            # dec_destino → fim (fim_fluxo == true)
            {'parent': 200, 'id': 222, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 203, 'target': 206, 'value': 'fim_fluxo == true',
             'data': {'cnt': {'type': 'option'},
                      'opt': {'type': 1, 'variable': VAR_FIM_FLUXO,
                              'operator': 1, 'value': 'true', 'field_compare': ''}}},

            # dec_destino → transbordo
            {'parent': 200, 'id': 223, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 203, 'target': 207, 'value': 'transbordo == true',
             'data': {'cnt': {'type': 'option'},
                      'opt': {'type': 1, 'variable': VAR_TRANSBORDO,
                              'operator': 1, 'value': 'true', 'field_compare': ''}}},

            # dec_destino → aguarda_hubsoft (poll)
            {'parent': 200, 'id': 228, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#0066CC;strokeColor=#0066CC;',
             'source': 203, 'target': 204,
             'value': 'tipo_acao == aguarda_hubsoft',
             'data': {'cnt': {'type': 'option'},
                      'opt': {'type': 1, 'variable': VAR_TIPO_ACAO,
                              'operator': 1, 'value': 'aguarda_hubsoft', 'field_compare': ''}}},

            # dec_destino → default (responder/pedir_imagem) → msg_bot
            {'parent': 200, 'id': 224, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#008000;strokeColor=#008000;',
             'source': 203, 'target': 204, 'value': 'Padrão',
             'data': {'cnt': {'type': 'default'}, 'opt': []}},

            # msg_bot → zera imagem_url → loop
            {'parent': 200, 'id': 225, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 204, 'target': 240, 'data': False},
            {'parent': 200, 'id': 241, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 240, 'target': 205, 'data': False},

            # ── GRUPO 300: FINALIZAÇÃO ───────────────────────────────────
            {'collapsed': 0, 'parent': 1, 'id': 300,
             'edge': False, 'cod_componente': 18,
             'height': 200, 'width': 350, 'x': 10, 'y': 720, 'relative': False,
             'value': 'FINALIZACAO', 'data': False},

            {'parent': 300, 'id': 301, 'quantityCon': 1, 'edge': False,
             'cod_componente': 1, 'height': 50, 'width': 50,
             'x': 30, 'y': 50, 'relative': False, 'value': '',
             'data': {
                 'identifier': 'msg_fim',
                 'retention': 0, 'bot_tts': 0, 'bot_tts_type_send': 1,
                 'hsm': 0, 'force_hsm': 0, 'num_delay': 0,
                 'tipo_mensagem': 0, 'msg_interativa': 0,
                 'messages': ['{#mensagem_bot_var}'],
             }},

            {'parent': 300, 'id': 302, 'quantityCon': 0, 'edge': False,
             'cod_componente': 4, 'height': 50, 'width': 50,
             'x': 200, 'y': 50, 'relative': False, 'value': '',
             'data': {
                 'identifier': 'fin_fluxo', 'type': 1,
                 'categorization': 0, 'research': -1, 'research_text': '', 'tags': [],
             }},

            {'parent': 300, 'id': 310, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 301, 'target': 302, 'data': False},

            # ── GRUPO 400: TRANSBORDO ────────────────────────────────────
            {'collapsed': 0, 'parent': 1, 'id': 400,
             'edge': False, 'cod_componente': 18,
             'height': 200, 'width': 350, 'x': 400, 'y': 720, 'relative': False,
             'value': 'TRANSBORDO HUMANO', 'data': False},

            {'parent': 400, 'id': 401, 'quantityCon': 1, 'edge': False,
             'cod_componente': 1, 'height': 50, 'width': 50,
             'x': 30, 'y': 50, 'relative': False, 'value': '',
             'data': {
                 'identifier': 'msg_transbordo',
                 'retention': 0, 'bot_tts': 0, 'bot_tts_type_send': 1,
                 'hsm': 0, 'force_hsm': 0, 'num_delay': 0,
                 'tipo_mensagem': 0, 'msg_interativa': 0,
                 'messages': ['{#mensagem_bot_var}'],
             }},

            {'parent': 400, 'id': 402, 'quantityCon': 0, 'edge': False,
             'cod_componente': 7, 'height': 50, 'width': 50,
             'x': 200, 'y': 50, 'relative': False, 'value': '',
             'data': {
                 'identifier': 'ser_humano',
                 'service': 5, 'priority': 1,
                 'transbordo': 0, 'pesquisa': 0,
             }},

            {'parent': 400, 'id': 410, 'edge': True, 'cod_componente': '',
             'style': 'edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;jettySize=auto;orthogonalLoop=1;fontColor=#000000;strokeColor=#000000;',
             'source': 401, 'target': 402, 'data': False},
        ],

        'variaveis': {
            '3470002': {'name': 'tempo_de_inatividade', 'value': '10'},
            str(VAR_URL_IA): {'name': 'url_ia', 'value': url_endpoint},
            str(VAR_MENSAGEM_BOT): {'name': 'mensagem_bot_var', 'value': ''},
            str(VAR_FIM_FLUXO): {'name': 'fim_fluxo', 'value': ''},
            str(VAR_TRANSBORDO): {'name': 'transbordo_humano', 'value': ''},
            str(VAR_INTENCAO): {'name': 'intencao', 'value': ''},
            str(VAR_TIPO_ACAO): {'name': 'tipo_acao', 'value': ''},
            str(VAR_IMAGEM_URL): {'name': 'imagem_url', 'value': ''},
        },
        'atalhos': [],
        'bot': [],
    }
    return flow


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--api-url', default='https://robovendas.megalinkpiaui.com.br/ia',
                   help='URL base da API IA Validação (sem barra final)')
    p.add_argument('--saida', type=Path,
                   default=Path('fluxos/flow_dinamico.json'),
                   help='Caminho do arquivo gerado')
    args = p.parse_args()

    flow = gerar(args.api_url)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding='utf-8')

    n_nodes = len([x for x in flow['flow'] if not x.get('edge', False)])
    n_edges = len([x for x in flow['flow'] if x.get('edge', False)])
    print(f'✓ Gerado: {args.saida}')
    print(f'  → {n_nodes} nós + {n_edges} edges (vs 538 do flow original)')
    print(f'  → endpoint: {args.api_url}/conversar')


if __name__ == '__main__':
    raise SystemExit(main())
