"""
Seed do checklist "Venda de internet (bot WhatsApp)" — traz pra engine
(Checklist/ItemChecklist) o roteiro de perguntas do robô de vendas por WhatsApp
que já roda em produção na Megalink (plataforma Matrix). Etapa 1 da migração:
só as PERGUNTAS como dado configurável. A lógica de IA (validação semântica,
decisão de próximo passo, mensagens de erro geradas por IA) fica pra etapa 2 —
aqui só estrutura o roteiro estático.

FONTE DA VERDADE: `SEQUENCIA_COLETA` e `_msg_pergunta` (+ `confirmacao_plano_*`
e o resumo de `dados_confirmados`) do módulo `onboarding.py` do robô original
(Matrix/Megalink). Os 22 itens abaixo seguem a MESMA ordem de `SEQUENCIA_COLETA`
e os textos são cópia literal, incluindo os tokens de emoji `##hex##` (o Matrix
decodifica isso no envio pro WhatsApp — NÃO converter pra emoji unicode aqui) e
a formatação `*negrito*` / `_itálico_` do WhatsApp.

ADAPTAÇÕES (o roteiro é da Megalink, o tenant semeado é outro):

1. Nome da empresa — todo texto que citava "Megalink" usa o placeholder
   `{empresa}`, RESOLVIDO em tempo de seed pra `tenant.nome` (nunca fica
   hardcoded no dado de outro tenant). Só os itens 1 (boas-vindas) e 15 (venda
   do plano) citavam a empresa no original.
2. Planos (item 14, id_plano_rp) — a pergunta é MONTADA a partir do catálogo
   real do tenant (`ProdutoServico`, ativos, ordenados por `ordem`/`nome`).
   Só usa catálogo real quando o tenant tem PELO MENOS 3 produtos ativos;
   com menos que isso (0, 1 ou 2) cai pro placeholder completo — misturar
   produto real com placeholder ia confundir quem revisar/ativar o checklist
   depois. Preço e nome dos planos da Megalink (620 Mega R$99,90 / 1G Turbo
   R$129,90 / 1 Giga+Ponto R$149,90) NUNCA são copiados como se fossem do
   tenant sendo semeado.
3. Texto de venda do plano (item 15, plano_confirmado) — no original existem 3
   variantes (uma por plano, roteadas por `id_plano_rp` em tempo real). Aqui
   usa só a variante do MEIO como base (`ura_titulo='confirmacao_plano_1g'`,
   igual pedido), com `{plano}`/`{valor}` como placeholders LITERAIS (não
   resolvidos): a seleção da variante certa por plano do catálogo real do
   tenant é trabalho de etapa 2, documentado em `ajuda`.
4. Placeholders de RUNTIME — `{nome}` (primeiro nome do cliente), `{cep}` /
   `{rua}` / `{bairro}` / `{cidade}` (retorno do ViaCEP) e `{data1..3}` (datas
   da agenda do HubSoft) dependem do lead/consulta em tempo real: não dá pra
   resolver em seed, então ficam como tokens literais pra etapa 2 interpolar.

Idempotente por slug do checklist (`venda-internet-bot`): re-rodar ATUALIZA os
22 itens pela `chave` (identidade natural), nunca duplica. Tanto o checklist
quanto cada item nascem com `ativo` no default do model (checklist=False via
`ativo=False` explícito na criação; item=True, default do model) — em re-runs,
`ativo` NUNCA é tocado (nem do checklist, nem de item já existente), mesmo
padrão dos outros seeds da engine (ver `seed_fluxo_oportunidades_paradas.py`).

Uso:
    python manage.py seed_checklist_venda --tenant nuvyon \\
        --settings=gerenciador_vendas.settings_local
"""
from django.core.management.base import BaseCommand, CommandError

SLUG_CHECKLIST = 'venda-internet-bot'
NOME_CHECKLIST = 'Venda de internet (bot WhatsApp)'

# ── condições reutilizadas — operadores suportados em
#    apps/automacao/services/checklist.py::_condicao_bate (igual/diferente/existe/nao_existe) ──
_COND_ENDERECO_NAO_CONFIRMADO = {'chave': 'endereco_confirmado', 'operador': 'diferente', 'valor': 'sim'}
_COND_TIPO_IMOVEL_CASA = {'chave': 'tipo_imovel', 'operador': 'igual', 'valor': 'casa'}

# Mensagem de erro genérica pra perguntas de múltipla escolha (o robô original só
# aceita o número da opção; qualquer outra coisa é resposta inválida).
_MSG_ERRO_OPCAO = 'Não entendi sua resposta. Responda apenas com o número da opção.'


def _pergunta_planos(linhas_planos):
    """Monta o texto da pergunta de planos (item 14): mesma estrutura visual do
    roteiro original (emoji por posição, preço indentado embaixo do nome)."""
    emojis = ['##1f680##', '##26a1##', '##1f4f6##']
    linhas = ['##1f4e6## *Nossos planos disponíveis:*', '']
    for i, (nome, linha_preco) in enumerate(linhas_planos):
        linhas.append(f'*{i + 1})* {emojis[i]} *{nome}*')
        linhas.append(f'      {linha_preco}')
        linhas.append('')
    linhas.append('_##1f4cc## Responda apenas com o *número* do plano (*1*, *2* ou *3*)._')
    return '\n'.join(linhas)


def _opcoes_planos_do_tenant(tenant):
    """Resolve a pergunta + opções do item 14 (id_plano_rp): catálogo real do
    tenant quando há >= 3 `ProdutoServico` ativos; placeholder completo caso
    contrário. Devolve dict com `pergunta`, `opcoes` e `usa_catalogo_real`
    (usado no resumo impresso pelo command e no `ajuda` do item)."""
    from apps.comercial.crm.models import ProdutoServico

    produtos = list(
        ProdutoServico.all_tenants.filter(tenant=tenant, ativo=True).order_by('ordem', 'nome')[:3]
    )
    if len(produtos) >= 3:
        linhas_planos = []
        opcoes = []
        for p in produtos:
            preco_fmt = f'{p.preco:.2f}'.replace('.', ',')
            linhas_planos.append((p.nome, f'##1f4b0## R$ {preco_fmt}/mês'))
            valor = (p.id_externo or str(p.pk)).strip()
            opcoes.append({'texto': f'{p.nome} (R$ {preco_fmt}/mês)', 'valor': valor})
        return {
            'pergunta': _pergunta_planos(linhas_planos),
            'opcoes': opcoes,
            'usa_catalogo_real': True,
        }

    linhas_planos = [(f'Plano {i + 1} (configurar)', '##1f4b0## Valor a definir') for i in range(3)]
    opcoes = [{'texto': f'Plano {i + 1} (configurar)', 'valor': f'plano_{i + 1}'} for i in range(3)]
    return {
        'pergunta': _pergunta_planos(linhas_planos),
        'opcoes': opcoes,
        'usa_catalogo_real': False,
    }


def _construir_itens(tenant):
    """Monta os 22 itens (ordem = `SEQUENCIA_COLETA` do robô original). Só o
    item 14 depende do catálogo do tenant; o resto é texto fixo com `{empresa}`
    já resolvido — os demais placeholders (`{nome}`, `{cep}`... `{plano}`,
    `{valor}`, `{data1..3}`) ficam literais de propósito (ver docstring)."""
    empresa = tenant.nome
    planos = _opcoes_planos_do_tenant(tenant)

    pergunta_cpf = (
        f'Oi! Que bom ter você aqui na *{empresa}* ##1f680##\n\n'
        'Pra começar, pode me informar seu *CPF*? ##1f194##\n\n'
        '_Exemplo: 999.999.999-99_\n\n'
        'Vou usar pra verificar se você já tem cadastro com a gente.'
    )

    pergunta_endereco_confirmado = (
        '##1f4cd## *Confira o endereço que encontrei:*\n\n'
        '##1f3f7## *CEP:* {cep}\n'
        '##1f6e3## *Rua:* {rua}\n'
        '##1f3d8## *Bairro:* {bairro}\n'
        '##1f306## *Cidade:* {cidade}\n\n'
        'Está tudo certo?\n\n'
        '*1)* ##2705## Sim, está correto\n'
        '*2)* ##274c## Não, preciso corrigir'
    )

    pergunta_plano_confirmado = (
        '##1f4e3## *Ótima notícia, {nome}!*\n\n'
        f'Temos uma promoção exclusiva da *{empresa}* válida somente neste mês, '
        'com condições especiais para pagamento até a data de vencimento.\n\n'
        '##1f4f6## *Internet que você pode confiar*\n\n'
        'Contrate o *{plano}* e tenha uma conexão rápida e estável para toda a sua casa.\n\n'
        '##1f4b0## *Apenas R$ {valor} por mês*\n'
        '_(valor com desconto de pontualidade)_\n\n'
        '##1f680## *Ideal para:*\n'
        '- Assistir filmes e séries sem travar\n'
        '- Jogos online com mais estabilidade\n'
        '- Chamadas de vídeo e home office\n\n'
        '*Confirma a contratação desse plano?*\n\n'
        '*1)* ##2705## Sim, quero esse plano\n'
        '*2)* ##274c## Não, quero ver outro'
    )

    pergunta_dados_confirmados = '\n'.join([
        '*Confirme seus dados, por favor:* ##1f4dd##',
        'Revise as informações antes de finalizarmos seu cadastro.',
        '',
        '*Plano Selecionado*',
        '##1f4e6## Plano: {plano}',
        '##1f4b0## Valor: R$ {valor}',
        '##1f4c5## Vencimento: Dia {vencimento}',
        '',
        '*Dados Pessoais*',
        '##1f464## Nome: {nome}',
        '##1f194## CPF: {cpf}',
        '##1f382## Nascimento: {nascimento}',
        '##2709## E-mail: {email}',
        '',
        '*Endereço*',
        '##1f3f7## CEP: {cep}',
        '##1f6e3## Rua: {rua}, Nº {numero}',
        '##1f3d8## Bairro: {bairro}',
        '##1f306## Cidade: {cidade}/{estado}',
        '',
        '_Este plano possui fidelidade de 12 meses. O valor com desconto '
        'é válido para pagamentos realizados até a data de vencimento._',
        '',
        '*Está tudo certo com essas informações?*',
        '',
        '*1)* ##2705## Sim, pode prosseguir',
        '*2)* ##274c## Não, preciso ajustar',
    ])

    pergunta_data_instalacao = (
        '##1f4c5## *Essas são as próximas datas disponíveis pra instalação:*\n\n'
        '*1)* {data1}\n'
        '*2)* {data2}\n'
        '*3)* {data3}\n\n'
        '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._'
    )

    ajuda_planos = (
        'Opções geradas do catálogo real do tenant (ProdutoServico ativos, 3 primeiros).'
        if planos['usa_catalogo_real'] else
        'Tenant sem catálogo de produtos suficiente (menos de 3 ativos). Opções placeholder, '
        'configurar planos reais antes de ativar o checklist.'
    )

    return [
        {
            'chave': 'cpf_cnpj', 'ordem': 1, 'pergunta': pergunta_cpf,
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'cpf_cnpj', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3,
            'mensagem_erro': 'Esse CPF ou CNPJ não parece válido. Confira os números e envie novamente.',
            'mensagem_sucesso': '',
            'ajuda': 'Combina a saudação inicial com a pergunta do CPF (1ª mensagem do roteiro original).',
        },
        {
            'chave': 'nome_razaosocial', 'ordem': 2, 'pergunta': 'Agora me passa seu *nome completo*?',
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': '', 'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'data_nascimento', 'ordem': 3,
            'pergunta': 'Informe sua *data de nascimento*.\n\n_Formato: 01/01/2000_',
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'data', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3,
            'mensagem_erro': 'Não consegui entender essa data. Envie no formato 01/01/2000.',
            'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'email', 'ordem': 4,
            'pergunta': 'Pode me informar seu *e-mail*?\n\n_Exemplo: nome@exemplo.com_',
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'email', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3,
            'mensagem_erro': 'Esse email não parece válido. Confira e envie novamente.',
            'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'tipo_imovel', 'ordem': 5,
            'pergunta': (
                '##1f3e0## *A internet será para qual tipo de imóvel?*\n\n'
                '*1)* ##1f3e1## Casa\n'
                '*2)* ##1f3e2## Empresa\n\n'
                '_##1f4cc## Responda apenas com o *número* da opção (*1* ou *2*)._'
            ),
            'tipo_resposta': 'opcoes',
            'opcoes': [{'texto': 'Casa', 'valor': 'casa'}, {'texto': 'Empresa', 'valor': 'empresa'}],
            'ura_titulo': '', 'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': _MSG_ERRO_OPCAO, 'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'cep', 'ordem': 6,
            'pergunta': 'Pode me passar o *CEP* da sua residência? ##1f3e0##\n\n_Formato: 64000-000_',
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'cep', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3,
            'mensagem_erro': 'Não encontrei esse CEP. Confira o número e envie novamente.',
            'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'endereco_confirmado', 'ordem': 7, 'pergunta': pergunta_endereco_confirmado,
            'tipo_resposta': 'opcoes',
            'opcoes': [
                {'texto': 'Sim, está correto', 'valor': 'sim'},
                {'texto': 'Não, preciso corrigir', 'valor': 'nao'},
            ],
            'ura_titulo': '', 'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': _MSG_ERRO_OPCAO, 'mensagem_sucesso': '',
            'ajuda': 'Placeholders {cep}/{rua}/{bairro}/{cidade}: a IA (etapa 2) preenche com o retorno do ViaCEP.',
        },
        {
            'chave': 'cidade', 'ordem': 8, 'pergunta': 'Em qual *cidade* você reside?',
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'nenhuma', 'obrigatorio': True,
            'condicao': dict(_COND_ENDERECO_NAO_CONFIRMADO),
            'max_tentativas': 3, 'mensagem_erro': '', 'mensagem_sucesso': '',
            'ajuda': 'Só pergunta se o endereço do ViaCEP não foi confirmado.',
        },
        {
            'chave': 'bairro', 'ordem': 9, 'pergunta': 'Qual é o *bairro*?',
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'nenhuma', 'obrigatorio': True,
            'condicao': dict(_COND_ENDERECO_NAO_CONFIRMADO),
            'max_tentativas': 3, 'mensagem_erro': '', 'mensagem_sucesso': '',
            'ajuda': 'Só pergunta se o endereço do ViaCEP não foi confirmado.',
        },
        {
            'chave': 'rua', 'ordem': 10, 'pergunta': 'Qual é o *nome da sua rua*?',
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'nenhuma', 'obrigatorio': True,
            'condicao': dict(_COND_ENDERECO_NAO_CONFIRMADO),
            'max_tentativas': 3, 'mensagem_erro': '', 'mensagem_sucesso': '',
            'ajuda': 'Só pergunta se o endereço do ViaCEP não foi confirmado.',
        },
        {
            'chave': 'numero_residencia', 'ordem': 11,
            'pergunta': 'Qual o *número da residência*?\n\n_Se não tiver, envie *S/N*_',
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': '', 'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'tipo_residencia', 'ordem': 12,
            'pergunta': (
                '##1f3e0## *Qual o tipo de imóvel?*\n\n'
                '*1)* ##1f3d8## Casa térrea / sobrado\n'
                '*2)* ##1f3e2## Apartamento\n'
                '*3)* ##1f3df## Condomínio fechado\n\n'
                '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._'
            ),
            'tipo_resposta': 'opcoes',
            'opcoes': [
                {'texto': 'Casa térrea / sobrado', 'valor': 'casa'},
                {'texto': 'Apartamento', 'valor': 'apartamento'},
                {'texto': 'Condomínio fechado', 'valor': 'condominio'},
            ],
            'ura_titulo': '', 'tipo_validacao': 'nenhuma', 'obrigatorio': True,
            'condicao': dict(_COND_TIPO_IMOVEL_CASA),
            'max_tentativas': 3, 'mensagem_erro': _MSG_ERRO_OPCAO, 'mensagem_sucesso': '',
            'ajuda': 'Só pergunta pra imóvel residencial (empresa não passa por aqui).',
        },
        {
            'chave': 'ponto_referencia', 'ordem': 13,
            'pergunta': (
                '##1f3d8## *Tem algum ponto de referência perto da sua casa?* ##263A##\n\n'
                '_Exemplo: perto da padaria do João, em frente à praça._'
            ),
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': '', 'mensagem_sucesso': '',
            'ajuda': 'Texto da variante CASA. Variantes por tipo de residência (apartamento, '
                     'condomínio) chegam na etapa 2.',
        },
        {
            'chave': 'id_plano_rp', 'ordem': 14, 'pergunta': planos['pergunta'],
            'tipo_resposta': 'opcoes', 'opcoes': planos['opcoes'],
            'ura_titulo': '', 'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': _MSG_ERRO_OPCAO, 'mensagem_sucesso': '',
            'ajuda': ajuda_planos,
        },
        {
            'chave': 'plano_confirmado', 'ordem': 15, 'pergunta': pergunta_plano_confirmado,
            'tipo_resposta': 'opcoes',
            'opcoes': [
                {'texto': 'Sim, quero esse plano', 'valor': 'sim'},
                {'texto': 'Não, quero ver outro', 'valor': 'nao'},
            ],
            'ura_titulo': 'confirmacao_plano_1g', 'tipo_validacao': 'nenhuma', 'obrigatorio': True,
            'condicao': None, 'max_tentativas': 3, 'mensagem_erro': _MSG_ERRO_OPCAO,
            'mensagem_sucesso': '',
            'ajuda': 'Texto adaptado da variante do meio (1G) do roteiro original. Placeholders '
                     '{plano} e {valor}: a variação específica por plano do catálogo real do '
                     'tenant chega na etapa 2.',
        },
        {
            'chave': 'id_dia_vencimento', 'ordem': 16,
            'pergunta': (
                '##1f4c5## *Qual o melhor dia pro vencimento da fatura?*\n\n'
                '*1)* Dia 1\n'
                '*2)* Dia 5\n'
                '*3)* Dia 15\n'
                '*4)* Dia 20\n\n'
                '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2*, *3* ou *4*)._'
            ),
            'tipo_resposta': 'opcoes',
            'opcoes': [
                {'texto': 'Dia 1', 'valor': '1'}, {'texto': 'Dia 5', 'valor': '5'},
                {'texto': 'Dia 15', 'valor': '15'}, {'texto': 'Dia 20', 'valor': '20'},
            ],
            'ura_titulo': '', 'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': _MSG_ERRO_OPCAO, 'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'dados_confirmados', 'ordem': 17, 'pergunta': pergunta_dados_confirmados,
            'tipo_resposta': 'opcoes',
            'opcoes': [
                {'texto': 'Sim, pode prosseguir', 'valor': 'sim'},
                {'texto': 'Não, preciso ajustar', 'valor': 'nao'},
            ],
            'ura_titulo': '', 'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': _MSG_ERRO_OPCAO, 'mensagem_sucesso': '',
            'ajuda': 'Resumo com placeholders de todos os dados coletados; a IA (etapa 2) '
                     'substitui pelos dados reais do lead.',
        },
        {
            'chave': 'doc_selfie_recebida', 'ordem': 18,
            'pergunta': (
                '##1f4f8## *Pra finalizar, preciso de 3 fotos.*\n\n'
                '*1ª foto:* envie uma *SELFIE* segurando seu RG ou CNH ao lado do rosto.\n\n'
                '_Mande a foto como anexo no chat._'
            ),
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': '', 'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'doc_frente_recebida', 'ordem': 19,
            'pergunta': (
                '##1f4f7## *2ª foto:* envie a *FRENTE* do seu documento (RG ou CNH).\n\n'
                '_Confira se as informações estão legíveis antes de enviar._'
            ),
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': '', 'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'doc_verso_recebida', 'ordem': 20,
            'pergunta': (
                '##1f4f7## *3ª foto:* envie o *VERSO* do seu documento.\n\n'
                '_Última foto, depois finalizamos!_'
            ),
            'tipo_resposta': 'texto_livre', 'opcoes': [], 'ura_titulo': '',
            'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': '', 'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'turno_instalacao', 'ordem': 21,
            'pergunta': (
                '##23f0## *Qual o melhor turno pra instalação?*\n\n'
                '*1)* ##1f305## Manhã\n'
                '*2)* ##2600## Tarde\n\n'
                '_##1f4cc## Responda apenas com o *número* da opção (*1* ou *2*)._'
            ),
            'tipo_resposta': 'opcoes',
            'opcoes': [{'texto': 'Manhã', 'valor': 'manha'}, {'texto': 'Tarde', 'valor': 'tarde'}],
            'ura_titulo': '', 'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': _MSG_ERRO_OPCAO, 'mensagem_sucesso': '', 'ajuda': '',
        },
        {
            'chave': 'data_instalacao', 'ordem': 22, 'pergunta': pergunta_data_instalacao,
            'tipo_resposta': 'opcoes',
            'opcoes': [
                {'texto': 'Primeira data disponível (definida na hora pelo bot)', 'valor': 'data_1'},
                {'texto': 'Segunda data disponível (definida na hora pelo bot)', 'valor': 'data_2'},
                {'texto': 'Terceira data disponível (definida na hora pelo bot)', 'valor': 'data_3'},
            ],
            'ura_titulo': '', 'tipo_validacao': 'nenhuma', 'obrigatorio': True, 'condicao': None,
            'max_tentativas': 3, 'mensagem_erro': _MSG_ERRO_OPCAO, 'mensagem_sucesso': '',
            'ajuda': 'As datas são dinâmicas, vêm da agenda do HubSoft. Opções placeholder até a '
                     'etapa 2 conectar a consulta real.',
        },
    ]


def _upsert_checklist(tenant):
    """`ativo` só é setado na CRIAÇÃO (nasce False); num checklist que já existe
    o campo nunca é tocado (mesmo padrão dos outros seeds da engine)."""
    from apps.automacao.models import Checklist

    checklist = Checklist.all_tenants.filter(tenant=tenant, slug=SLUG_CHECKLIST).first()
    criado = checklist is None
    if checklist is None:
        return Checklist.all_tenants.create(
            tenant=tenant, slug=SLUG_CHECKLIST, nome=NOME_CHECKLIST,
            contexto='bot_vendas', modo_preenchimento='ia', entidade_alvo='lead',
            ativo=False,
        ), criado

    checklist.nome = NOME_CHECKLIST
    checklist.contexto = 'bot_vendas'
    checklist.modo_preenchimento = 'ia'
    checklist.entidade_alvo = 'lead'
    checklist.save()
    return checklist, criado


class Command(BaseCommand):
    help = (
        'Seed do checklist de venda de internet via bot WhatsApp (roteiro migrado do robô '
        'Matrix/Megalink, etapa 1: só as perguntas). Idempotente por slug, nasce INATIVO.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True, help='Slug do tenant (obrigatório).')

    def handle(self, *args, **opts):
        from apps.automacao.models import ItemChecklist
        from apps.sistema.models import Tenant

        slug = (opts.get('tenant') or '').strip()
        tenant = Tenant.objects.filter(slug=slug).first()
        if tenant is None:
            raise CommandError(f"Tenant '{slug}' não encontrado.")

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Seed checklist de venda, tenant: {tenant.slug}'))

        checklist, criado_checklist = _upsert_checklist(tenant)
        self.stdout.write(
            f'  {"criado" if criado_checklist else "atualizado"}: checklist "{checklist.nome}" '
            f'(id={checklist.pk}, ativo={checklist.ativo})')

        itens = _construir_itens(tenant)
        criados, atualizados = 0, 0
        usa_catalogo_real = None
        for definicao in itens:
            chave = definicao.pop('chave')
            if chave == 'id_plano_rp':
                usa_catalogo_real = 'catálogo real' in definicao['ajuda']
            defaults = {**definicao, 'tenant': tenant, 'checklist': checklist}
            # `ativo` de propósito FORA de `defaults`: update_or_create só toca os campos
            # listados aqui, então um item já desativado manualmente continua desativado.
            _item, item_criado = ItemChecklist.all_tenants.update_or_create(
                checklist=checklist, chave=chave, defaults=defaults,
            )
            if item_criado:
                criados += 1
            else:
                atualizados += 1

        self.stdout.write(f'  itens: {criados} criado(s), {atualizados} atualizado(s), {len(itens)} no total')
        self.stdout.write(self.style.WARNING(
            '  planos: catálogo real do tenant' if usa_catalogo_real else
            '  planos: PLACEHOLDER (tenant sem >=3 produtos ativos) — conferir antes de ativar'))
        self.stdout.write(self.style.SUCCESS(
            'Seed concluído. Checklist nasce INATIVO — revisar os planos (item id_plano_rp) e '
            'ligar manualmente quando validado.'))
