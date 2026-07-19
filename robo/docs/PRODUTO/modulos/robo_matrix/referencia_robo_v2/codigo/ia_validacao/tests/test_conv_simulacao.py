"""Suite de validação da camada conversacional (Fase 7) — OFFLINE.

Roda SEM rede e SEM IA: exercita os módulos próprios do /conv/turno
(motor, validacao, planos, respostas, retomada) simulando uma venda
completa e os casos de erro que antes davam loop/transbordo.

Também faz uma checagem de regressão: o núcleo determinístico
(onboarding/engine) não tem mais o desvio de retomar/recomeçar.

Uso:  .venv/bin/python3 tests/test_conv_simulacao.py
Sai com código 0 se tudo passar, 1 caso contrário.
"""
from __future__ import annotations

import sys

from src.conversacional import motor, validacao, planos, respostas, retomada

_falhas: list[str] = []


def checa(cond: bool, msg: str):
    marca = '✓' if cond else '✗'
    print(f'  {marca} {msg}')
    if not cond:
        _falhas.append(msg)


# ── Regras de teste (espelho enxuto da config real do Django) ──────────
REGRAS = {
    'coleta_cpf': {'question_id': 'coleta_cpf', 'extractor_tipo': 'cpf',
                   'campo_lead_atualizar': 'cpf_cnpj'},
    'coleta_nome': {'question_id': 'coleta_nome', 'extractor_tipo': 'nome',
                    'campo_lead_atualizar': 'nome_razaosocial'},
    'coleta_data_nascimento': {'question_id': 'coleta_data_nascimento',
                               'extractor_tipo': 'data_nascimento',
                               'campo_lead_atualizar': 'data_nascimento'},
    'coleta_email': {'question_id': 'coleta_email', 'extractor_tipo': 'email',
                     'campo_lead_atualizar': 'email'},
    'tipo_imovel': {'question_id': 'tipo_imovel', 'extractor_tipo': 'opcao',
                    'campo_lead_atualizar': 'tipo_imovel',
                    'extractor_config': {'opcoes': {'casa': ['1', 'casa', 'residencia'],
                                                    'empresa': ['2', 'empresa']}}},
    'coleta_cep': {'question_id': 'coleta_cep', 'extractor_tipo': 'cep',
                   'campo_lead_atualizar': 'cep'},
    'confirmacao_endereco': {'question_id': 'confirmacao_endereco',
                             'extractor_tipo': 'confirmacao',
                             'campo_lead_atualizar': 'endereco_confirmado'},
    'coleta_numero': {'question_id': 'coleta_numero', 'extractor_tipo': 'numero',
                      'campo_lead_atualizar': 'numero_residencia'},
    'coleta_tipo_residencia': {'question_id': 'coleta_tipo_residencia',
                               'extractor_tipo': 'opcao',
                               'campo_lead_atualizar': 'tipo_residencia',
                               'extractor_config': {'opcoes': {
                                   'casa_terrea': ['1', 'casa', 'térrea'],
                                   'apartamento': ['2', 'apartamento', 'ap'],
                                   'condominio': ['3', 'condomínio', 'condominio']}}},
    'coleta_ponto_referencia': {'question_id': 'coleta_ponto_referencia',
                                'extractor_tipo': 'texto_livre',
                                'campo_lead_atualizar': 'ponto_referencia'},
    'escolha_plano': {'question_id': 'escolha_plano', 'extractor_tipo': 'opcao',
                      'campo_lead_atualizar': 'id_plano_rp',
                      'extractor_config': {'opcoes': {'1649': ['1'], '1648': ['2']}}},
    'confirmacao_plano': {'question_id': 'confirmacao_plano',
                          'extractor_tipo': 'confirmacao',
                          'campo_lead_atualizar': 'plano_confirmado'},
    'dia_vencimento': {'question_id': 'dia_vencimento', 'extractor_tipo': 'opcao',
                       'campo_lead_atualizar': 'id_dia_vencimento',
                       'extractor_config': {'opcoes': {'5': ['1', '5'], '9': ['2', '10'],
                                                       '6': ['3', '20']}}},
    'confirmacao_dados': {'question_id': 'confirmacao_dados',
                          'extractor_tipo': 'confirmacao',
                          'campo_lead_atualizar': 'dados_confirmados'},
    'documentacao_selfie': {'question_id': 'documentacao_selfie',
                            'extractor_tipo': 'imagem',
                            'campo_lead_atualizar': 'doc_selfie_recebida'},
    'documentacao_frente_doc': {'question_id': 'documentacao_frente_doc',
                                'extractor_tipo': 'imagem',
                                'campo_lead_atualizar': 'doc_frente_recebida'},
    'documentacao_verso_doc': {'question_id': 'documentacao_verso_doc',
                               'extractor_tipo': 'imagem',
                               'campo_lead_atualizar': 'doc_verso_recebida'},
    'escolha_turno': {'question_id': 'escolha_turno', 'extractor_tipo': 'opcao',
                      'campo_lead_atualizar': 'turno_instalacao',
                      'extractor_config': {'opcoes': {'manha': ['1', 'manhã', 'manha'],
                                                      'tarde': ['2', 'tarde']}}},
    'escolha_data': {'question_id': 'escolha_data', 'extractor_tipo': 'opcao',
                     'campo_lead_atualizar': 'data_instalacao',
                     'extractor_config': {'opcoes': {}}},
}

# Resposta "boa" do cliente pra cada etapa (drive da venda completa).
RESPOSTAS = {
    'coleta_cpf': '111.444.777-35',
    'coleta_nome': 'Ana Paula Souza',
    'coleta_data_nascimento': '10/05/1990',
    'coleta_email': 'ana.paula@gmail.com',
    'tipo_imovel': '1',                  # casa
    'coleta_cep': '01001-000',           # ViaCEP real (Praça da Sé/SP)
    'confirmacao_endereco': 'sim',
    'coleta_numero': '123',
    'coleta_tipo_residencia': '1',       # casa térrea
    'coleta_ponto_referencia': 'ao lado da padaria',
    'escolha_plano': 'quero o de 99 reais',   # PLANO POR PREÇO
    'confirmacao_plano': 'com certeza',       # confirmação natural
    'dia_vencimento': '1',
    'confirmacao_dados': 'isso',
    'documentacao_selfie': 'https://x/selfie.jpg',
    'documentacao_frente_doc': 'https://x/frente.jpg',
    'documentacao_verso_doc': 'https://x/verso.jpg',
    'escolha_turno': '1',                # manhã
    'escolha_data': '1',                 # opção mapeada por hook (não testado offline)
}


def _analise_simulada(qid: str, resposta: str) -> dict:
    """Imita o que a IA devolveria, sem chamar a IA."""
    a = {'campos': {}, 'opcao_numerica': None, 'confirmacao': None,
         'tem_pergunta': False, 'pergunta_texto': '', 'intencao': 'responder'}
    tipo = REGRAS[qid]['extractor_tipo']
    r = resposta.strip().lower()
    if tipo == 'confirmacao':
        a['confirmacao'] = 'sim' if r not in ('2', 'nao', 'não') else 'nao'
    elif tipo == 'opcao' and r and r[0].isdigit():
        a['opcao_numerica'] = r[0]
    return a


def _valida_passo(qid: str, resposta: str, dados: dict) -> validacao.Resultado:
    """Replica a decisão do orquestrador._validar_passo (sem rede)."""
    regra = REGRAS[qid]
    analise = _analise_simulada(qid, resposta)
    if qid == 'escolha_plano' and not analise.get('opcao_numerica'):
        plano = planos.resolver_plano(resposta)
        if plano:
            return validacao.Resultado(
                True, campos={'id_plano_rp': plano['id_plano_rp'],
                              'valor': plano['valor']}, extra={'plano': plano})
    return validacao.validar(regra, resposta, analise)


def teste_venda_completa():
    print('\n[1] Venda completa (lead novo) — drive até o fim:')
    dados: dict = {'nome_razaosocial': 'Lead WhatsApp'}  # placeholder do WhatsApp
    passos = 0
    vistos = []
    while not motor.fluxo_completo(dados, em_new_service=False):
        etapa = motor.proxima_etapa(dados, em_new_service=False)
        qid = etapa.question_id
        vistos.append(qid)
        resp = RESPOSTAS.get(qid)
        if resp is None:
            _falhas.append(f'sem resposta de teste pra {qid}')
            break
        res = _valida_passo(qid, resp, dados)
        if not res.valido:
            _falhas.append(f'{qid} deu inválido: {res.motivo}')
            break
        # imagem: marca o campo bool de recebida
        if REGRAS[qid]['extractor_tipo'] == 'imagem':
            dados[REGRAS[qid]['campo_lead_atualizar']] = True
        else:
            dados.update(res.campos)
            # confirmações: garante bool no campo
            if REGRAS[qid]['extractor_tipo'] == 'confirmacao':
                dados[REGRAS[qid]['campo_lead_atualizar']] = res.extra.get('confirmacao', True)
        passos += 1
        if passos > 40:
            _falhas.append('LOOP: passou de 40 passos sem completar')
            break
    checa(motor.fluxo_completo(dados, em_new_service=False),
          f'fluxo completou em {passos} passos (sem loop)')
    checa(dados.get('cpf_cnpj') == '11144477735', 'CPF salvo e normalizado')
    checa(dados.get('id_plano_rp') == 1649, 'plano "99 reais" → id 1649 (620MB)')
    checa(dados.get('cidade'), f"endereço preenchido via ViaCEP (cidade={dados.get('cidade')})")
    checa('coleta_cpf' in vistos and 'escolha_turno' in vistos,
          'sequência cobriu do CPF ao turno')


def teste_new_service():
    print('\n[2] Novo Serviço (cliente Hubsoft) — começa do tipo de imóvel:')
    dados: dict = {}
    primeira = motor.proxima_pergunta_id(dados, em_new_service=True)
    checa(primeira == 'tipo_imovel', f'1ª pergunta do new_service = tipo_imovel ({primeira})')
    # não deve pedir CPF/nome/email/nascimento
    seq_qids = {e.question_id for e in motor.SEQUENCIA_NEW_SERVICE}
    checa('coleta_cpf' not in seq_qids and 'coleta_nome' not in seq_qids,
          'new_service não pede dados pessoais')


def teste_erros_especificos():
    print('\n[3] Erros: resposta específica que re-solicita (sem genérico):')
    r = validacao.validar(REGRAS['coleta_cpf'], '111.111.111-11', {})
    checa(not r.valido and r.motivo == 'cpf_invalido', 'CPF inválido detectado')
    msg = respostas.mensagem_erro(REGRAS['coleta_cpf'], r.motivo, tentativa=1)
    checa('CPF' in msg and 'verificação' in msg, f'msg de CPF específica: "{msg[:40]}..."')

    r2 = validacao.validar(REGRAS['coleta_nome'], 'ana', {})
    checa(not r2.valido and r2.motivo == 'sobrenome_faltando', 'nome sem sobrenome detectado')

    r3 = validacao.validar(REGRAS['coleta_data_nascimento'], '10/05/2015', {})
    checa(not r3.valido and r3.motivo == 'menor_de_idade', 'menor de idade detectado')

    # escalonamento → transbordo
    checa(not respostas.deve_transbordar(REGRAS['coleta_cpf'], 1), 'tentativa 1 não transborda')
    checa(respostas.deve_transbordar({'max_tentativas': 3}, 3), 'tentativa 3 transborda')


def teste_confirmacoes_naturais():
    print('\n[4] Confirmações em linguagem natural (antes davam loop):')
    for txt in ('com certeza', 'isso', 'pode ser', 'claro'):
        a = {'confirmacao': 'sim'}
        r = validacao.validar(REGRAS['confirmacao_plano'], txt, a)
        checa(r.valido and r.campos.get('plano_confirmado') is True,
              f'"{txt}" → confirmado')
    # opção com acento solto "1´"
    r = validacao.validar(REGRAS['escolha_turno'], '1´', {})
    checa(r.valido and r.campos.get('turno_instalacao') == 'manha', '"1´" → manhã (sem transbordo)')


def teste_planos_por_preco():
    print('\n[5] Plano por preço/velocidade:')
    casos = {'quero o de 99 reais': 1649, 'o de 129': 1648,
             'plano de 1 giga': 1648, '620 mega': 1649}
    for txt, esperado in casos.items():
        p = planos.resolver_plano(txt)
        checa(p and p['id_plano_rp'] == esperado, f'"{txt}" → {esperado}')


def teste_retomada():
    print('\n[6] Retomar/recomeçar (exclusivo do conv):')
    checa(not retomada.tem_progresso({}), 'sem dados → não pergunta retomar')
    dados = {'cpf_cnpj': '1', 'nome_razaosocial': 'Ana Paula', 'email': 'a@x.com',
             'tipo_imovel': 'casa'}
    checa(retomada.tem_progresso(dados), '4 campos → pergunta retomar')
    msg = retomada.montar_resumo(dados)
    checa('Continuar de onde parei' in msg and 'Começar de novo' in msg,
          'resumo tem as duas opções')


def teste_conversa_livre():
    print('\n[8] Conversa livre — correção e pergunta:')
    # mapa campo→question_id (usado pra rotear correção)
    from src.conversacional.fluxo import mapa_qid_para_campo
    campo_para_qid = {c: q for q, c in mapa_qid_para_campo().items()}
    checa(campo_para_qid.get('cep') == 'coleta_cep',
          '"mudar o cep" → roteia pra coleta_cep')
    checa(campo_para_qid.get('email') == 'coleta_email',
          '"corrigir email" → roteia pra coleta_email')
    checa(campo_para_qid.get('numero_residencia') == 'coleta_numero',
          '"trocar o número" → roteia pra coleta_numero')
    # extrator expõe campo_corrigir no schema de saída
    from src.conversacional.extrator import analisar_mensagem
    from src.conversacional.config import conv_config
    _orig = conv_config.PASSO2_EXTRACAO
    conv_config.PASSO2_EXTRACAO = False  # força o caminho "vazio" (sem IA/rede)
    vazio = analisar_mensagem('oi')
    conv_config.PASSO2_EXTRACAO = _orig
    checa('campo_corrigir' in vazio, 'extrator devolve campo_corrigir no schema')
    checa(vazio.get('campo_corrigir') is None, 'campo_corrigir default = None')


def teste_contrato_flow():
    print('\n[9] Contrato de resposta pro flow do Matrix (_mapear_resposta):')
    from src.conversacional.rotas import _mapear_resposta
    ok = _mapear_resposta({'valido': True, 'transbordo': False,
                           'mensagem': 'Qual seu CEP?', 'proxima_pergunta_id': 'coleta_cep',
                           'status_lead': 'lead_novo', 'is_cliente': False, 'encerrar': False})
    checa(ok['resposta_correta'] == 'true' and ok['message'] == 'Qual seu CEP?'
          and ok['retorno_erro_api'] == '',
          'sucesso → resposta_correta=true, message preenchido, retorno_erro_api vazio')
    er = _mapear_resposta({'valido': False, 'transbordo': False,
                           'mensagem': 'CPF inválido, confere?', 'proxima_pergunta_id': 'coleta_cpf'})
    checa(er['resposta_correta'] == 'false' and er['message'] == ''
          and er['retorno_erro_api'] == 'CPF inválido, confere?',
          'erro → resposta_correta=false, message vazio, retorno_erro_api preenchido')
    tr = _mapear_resposta({'valido': False, 'transbordo': True, 'mensagem': 'Transferindo'})
    checa(tr['needsReception'] == 'true' and tr['retorno_erro_api'] == '',
          'transbordo → needsReception=true, sem erro')
    en = _mapear_resposta({'valido': True, 'transbordo': False, 'mensagem': 'Tchau',
                           'encerrar': True, 'is_cliente': True})
    checa(en['encerrar'] == 'true' and en['isAClient'] == 'true',
          'encerrar/isAClient mapeados pra "true"')
    # campos que o store do flow lê devem existir
    for campo in ('resposta_correta', 'message', 'retorno_erro_api', 'needsReception',
                  'isAClient', 'proxima_pergunta_id', 'status_lead', 'proximo_passo'):
        checa(campo in ok, f'campo "{campo}" presente na resposta')


def teste_modos():
    print('\n[10] Detecção de modo (rotear vs validar) pelo body do Matrix:')
    from src.conversacional.rotas import TurnoRequest
    rotear = TurnoRequest(cellphone='559', ultima_mensagem='oi')
    checa(rotear.modo == 'rotear' and rotear.texto_cliente == 'oi',
          'api_proximo_passo (só ultima_mensagem) → rotear')
    validar = TurnoRequest(cellphone='559', lead_id='5', question='coleta_cpf',
                           answer='111.444.777-35', question_id='coleta_cpf')
    checa(validar.modo == 'validar' and validar.qid == 'coleta_cpf',
          'api_validar (answer+question_id) → validar')
    # saudação não deve ter answer → cai em rotear (não valida "oi")
    checa(TurnoRequest(cellphone='559', answer='').modo == 'rotear',
          'answer vazio → rotear (não valida saudação)')


def teste_regressao_nucleo():
    print('\n[7] Regressão: núcleo determinístico SEM retomar/recomeçar:')
    import src.onboarding as ob
    checa(not hasattr(ob, '_montar_resumo_retomada'),
          'onboarding não tem mais _montar_resumo_retomada')
    checa(not hasattr(ob, 'CAMPOS_RECOMECAR'),
          'onboarding não tem mais CAMPOS_RECOMECAR')
    import inspect
    src_decidir = inspect.getsource(ob.decidir_proximo_passo)
    checa('retomar_ou_recomecar' not in src_decidir,
          'decidir_proximo_passo não cita mais retomar_ou_recomecar')
    # sequências determinísticas intactas
    checa(hasattr(ob, 'SEQUENCIA_COLETA') and hasattr(ob, 'SEQUENCIA_NEW_SERVICE'),
          'SEQUENCIA_COLETA e SEQUENCIA_NEW_SERVICE preservadas')


def main():
    print('=' * 60)
    print('SUITE DE VALIDAÇÃO — camada conversacional (/conv/turno)')
    print('=' * 60)
    teste_venda_completa()
    teste_new_service()
    teste_erros_especificos()
    teste_confirmacoes_naturais()
    teste_planos_por_preco()
    teste_retomada()
    teste_conversa_livre()
    teste_contrato_flow()
    teste_modos()
    teste_regressao_nucleo()
    print('\n' + '=' * 60)
    if _falhas:
        print(f'❌ {len(_falhas)} FALHA(S):')
        for f in _falhas:
            print(f'   - {f}')
        return 1
    print('✅ TUDO PASSOU')
    return 0


if __name__ == '__main__':
    sys.exit(main())
