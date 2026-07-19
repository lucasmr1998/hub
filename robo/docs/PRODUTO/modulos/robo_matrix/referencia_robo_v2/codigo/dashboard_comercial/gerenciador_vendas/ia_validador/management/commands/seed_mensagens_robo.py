"""Semeia as MensagemRobo (chave→texto) com os textos PADRÃO atuais do engine.

Idempotente e SEGURO: se a chave já existe, NÃO sobrescreve o `texto` (preserva
a edição feita na ferramenta) — atualiza metadados (rótulo/grupo/descrição/
placeholders/ordem) e o `texto_padrao` (usado pelo botão "Restaurar padrão").
O engine lê essas chaves via mensagens_client.texto(chave, default); texto
vazio cai no default embutido no código.

    manage.py seed_mensagens_robo
"""
from django.core.management.base import BaseCommand

# Cada item: (chave, grupo, rotulo, descricao, placeholders, texto_padrao, ordem)
MENSAGENS = [
    # ═══ INÍCIO & BOAS-VINDAS ════════════════════════════════════════
    ('boasvindas_lead_novo', 'inicio', 'Boas-vindas (1º contato)',
     'Primeira frase para quem NUNCA falou com o robô — vem antes do pedido de CPF.', '',
     'Oi! Que bom ter você aqui na *Megalink* ##1f680##', 10),
    ('pergunta_cpf_cnpj', 'inicio', 'Pedir CPF',
     'Pedido de CPF (vem logo após as boas-vindas, e também na re-coleta).', '',
     'Pra começar, pode me informar seu *CPF*? ##1f194##\n\n'
     '_Exemplo: 999.999.999-99_\n\n'
     'Vou usar pra verificar se você já tem cadastro com a gente.', 20),
    ('menu_cpf_corpo', 'inicio', 'Confirmar CPF (mesmo ou outro?)',
     'Cliente já conhecido abre atendimento: pergunta se é o CPF do número ou outro. '
     'MANTENHA as opções 1 e 2.', '{cpf} = CPF mascarado',
     'Vi que este número já tem cadastro com a gente.\n\n'
     'Este atendimento é para o *CPF {cpf}* (atrelado a este '
     'número) ou para um *outro CPF*?\n\n'
     '*1)* ##2705## Sim, é esse CPF\n'
     '*2)* ##1f194## Outro CPF\n\n'
     '_##1f4cc## Responda com *1* ou *2*._', 30),

    # ═══ COLETA DE DADOS (PERGUNTAS) ═════════════════════════════════
    ('pergunta_nome_razaosocial', 'boas_vindas_coleta', 'Pedir nome completo',
     'Coleta do nome (o robô SEMPRE pergunta — nome do WhatsApp não vale).', '',
     'Agora me passa seu *nome completo*?', 10),
    ('pergunta_data_nascimento', 'boas_vindas_coleta', 'Pedir data de nascimento',
     'Coleta da data de nascimento.', '',
     'Informe sua *data de nascimento*.\n\n_Formato: 01/01/2000_', 20),
    ('pergunta_email', 'boas_vindas_coleta', 'Pedir e-mail',
     'Coleta do e-mail.', '',
     'Pode me informar seu *e-mail*?\n\n_Exemplo: nome@exemplo.com_', 30),
    ('pergunta_tipo_imovel', 'boas_vindas_coleta', 'Tipo de imóvel (casa/empresa)',
     'Casa ou empresa — empresa transborda p/ consultor. MANTENHA as opções 1 e 2.', '',
     '##1f3e0## *A internet será para qual tipo de imóvel?*\n\n'
     '*1)* ##1f3e1## Casa\n'
     '*2)* ##1f3e2## Empresa\n\n'
     '_##1f4cc## Responda apenas com o *número* da opção (*1* ou *2*)._', 40),
    ('pergunta_id_dia_vencimento', 'boas_vindas_coleta', 'Dia de vencimento',
     'MANTENHA as 4 opções (dias 1, 5, 15 e 20).', '',
     '##1f4c5## *Qual o melhor dia pro vencimento da fatura?*\n\n'
     '*1)* Dia 1\n*2)* Dia 5\n*3)* Dia 15\n*4)* Dia 20\n\n'
     '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2*, *3* ou *4*)._', 50),

    # ═══ ENDEREÇO ════════════════════════════════════════════════════
    ('pergunta_cep', 'endereco', 'Pedir CEP',
     'Coleta do CEP (dispara a busca automática do endereço).', '',
     'Pode me passar o *CEP* da sua residência? ##1f3e0##\n\n_Formato: 64000-000_', 10),
    ('confirmacao_endereco_titulo', 'endereco', 'Confirmação do endereço — título',
     'Cabeçalho antes das linhas de CEP/Rua/Bairro/Cidade encontradas.', '',
     '##1f4cd## *Confira o endereço que encontrei:*', 20),
    ('confirmacao_endereco_rodape', 'endereco', 'Confirmação do endereço — pergunta',
     'Pergunta final da confirmação. MANTENHA as opções 1 e 2.', '',
     'Está tudo certo?\n\n'
     '*1)* ##2705## Sim, está correto\n'
     '*2)* ##274c## Não, preciso corrigir', 30),
    ('pergunta_cidade', 'endereco', 'Pedir cidade',
     'Quando a busca do CEP não preencheu / cliente quer corrigir.', '',
     'Em qual *cidade* você reside?', 40),
    ('pergunta_bairro', 'endereco', 'Pedir bairro', '', '', 'Qual é o *bairro*?', 50),
    ('pergunta_rua', 'endereco', 'Pedir rua', '', '', 'Qual é o *nome da sua rua*?', 60),
    ('pergunta_numero_residencia', 'endereco', 'Pedir número da residência', '', '',
     'Qual o *número da residência*?\n\n_Se não tiver, envie *S/N*_', 70),
    ('pergunta_tipo_residencia', 'endereco', 'Tipo de residência',
     'Casa térrea / apartamento / condomínio — muda o que pedimos no ponto de referência. '
     'MANTENHA as opções 1, 2 e 3.', '',
     '##1f3e0## *Qual o tipo de imóvel?*\n\n'
     '*1)* ##1f3d8## Casa térrea / sobrado\n'
     '*2)* ##1f3e2## Apartamento\n'
     '*3)* ##1f3df## Condomínio fechado\n\n'
     '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._', 80),
    ('pergunta_ponto_ref_casa', 'endereco', 'Ponto de referência — casa',
     'Pedido de ponto de referência quando o imóvel é casa térrea/sobrado.', '',
     '##1f3d8## *Tem algum ponto de referência perto da sua casa?* ##263A##\n\n'
     '_Exemplo: perto da padaria do João, em frente à praça._', 90),
    ('pergunta_ponto_ref_apartamento', 'endereco', 'Detalhes — apartamento',
     'Pedido de detalhes quando o imóvel é apartamento.', '',
     '##1f3e2## *Pra ajudar nosso time na instalação, me passe '
     'os detalhes do seu apartamento:*\n\n'
     '- Nome do *edifício*\n'
     '- *Bloco/torre* (se houver)\n'
     '- *Andar*\n'
     '- *Número do apartamento*\n'
     '- *Ponto de referência* externo (opcional, ex: perto da padaria X)\n\n'
     '_Pode mandar tudo em uma única mensagem ##263A##_', 100),
    ('pergunta_ponto_ref_condominio', 'endereco', 'Detalhes — condomínio',
     'Pedido de detalhes quando o imóvel é condomínio fechado.', '',
     '##1f3df## *Pra ajudar nosso time na instalação, me passe '
     'os detalhes do seu condomínio:*\n\n'
     '- Nome do *condomínio*\n'
     '- *Quadra/bloco* (se houver)\n'
     '- *Número da casa*\n'
     '- *Ponto de referência* externo (opcional, ex: portaria 2)\n\n'
     '_Pode mandar tudo em uma única mensagem ##263A##_', 110),

    # ═══ PLANOS & VITRINE ════════════════════════════════════════════
    ('pergunta_id_plano_rp', 'planos', 'Vitrine de planos (URA)',
     'Lista dos planos oferecidos. MANTENHA os números 1, 2 e 3.', '',
     '##1f4e6## *Nossos planos disponíveis:*\n\n'
     '*1)* ##1f680## *Plano 620 Mega*\n'
     '      ##1f4b0## R$ 99,90/mês\n\n'
     '*2)* ##26a1## *Plano 1G Turbo*\n'
     '      ##1f4b0## R$ 129,90/mês\n\n'
     '*3)* ##1f4f6## *1 Giga + Ponto Adicional*\n'
     '      ##1f4b0## R$ 149,90/mês\n\n'
     '_##1f4cc## Responda apenas com o *número* do plano (*1*, *2* ou *3*)._', 10),
    ('confirmacao_plano_620', 'planos', 'Texto do plano 620 Mega',
     'Descrição rica enviada quando o cliente escolhe o 620 Mega. '
     'MANTENHA as opções 1 e 2 no final.', '{nome} = primeiro nome do cliente',
     '##1f4e3## *Ótima notícia, {nome}!*\n\n'
     'Temos uma promoção exclusiva da *Megalink* válida somente '
     'neste mês, com condições especiais para pagamento até a '
     'data de vencimento.\n\n'
     '##1f4f6## *Internet que você pode confiar*\n\n'
     'Contrate *620 Mega* de velocidade e tenha internet rápida '
     'e estável para toda a sua casa.\n\n'
     '##1f4b0## *Apenas R$ 99,90 por mês*\n'
     '_(valor com desconto de pontualidade)_\n\n'
     '##1f680## *Ideal para:*\n'
     '- Assistir filmes e séries sem travar\n'
     '- Jogos online com mais estabilidade\n'
     '- Chamadas de vídeo e home office\n\n'
     '*Confirma a contratação desse plano?*\n\n'
     '*1)* ##2705## Sim, quero esse plano\n'
     '*2)* ##274c## Não, quero ver outro', 20),
    ('confirmacao_plano_1g', 'planos', 'Texto do plano 1G Turbo',
     'Descrição rica enviada quando o cliente escolhe o 1G Turbo. '
     'MANTENHA as opções 1 e 2 no final.', '{nome} = primeiro nome do cliente',
     '##1f4e3## *Ótima notícia, {nome}!*\n\n'
     'Temos uma promoção exclusiva da *Megalink* válida somente '
     'neste mês, com condições especiais para pagamento até a '
     'data de vencimento.\n\n'
     '##1f4f6## *Internet que você pode confiar*\n\n'
     'Contrate o *Plano de 1GB Turbo* e tenha uma conexão ultra '
     'rápida e estável para toda a sua casa.\n\n'
     '##1f4b0## *Apenas R$ 129,90 por mês*\n'
     '_(valor com desconto de pontualidade)_\n\n'
     '##1f680## *Ideal para:*\n'
     '- Assistir filmes e séries em alta qualidade sem travar\n'
     '- Jogos online com máxima performance\n'
     '- Chamadas de vídeo e home office sem interrupções\n'
     '- Vários dispositivos conectados ao mesmo tempo\n\n'
     '*Confirma a contratação desse plano?*\n\n'
     '*1)* ##2705## Sim, quero esse plano\n'
     '*2)* ##274c## Não, quero ver outro', 30),
    ('confirmacao_plano_1g_ponto_adc', 'planos', 'Texto do plano 1 Giga + Ponto Adicional',
     'Descrição rica enviada quando o cliente escolhe o 1G + Ponto. '
     'MANTENHA as opções 1 e 2 no final.', '{nome} = primeiro nome do cliente',
     '##1f4e3## *Ótima notícia, {nome}!*\n\n'
     'Temos uma promoção exclusiva da *Megalink* válida somente '
     'neste mês, com condições especiais para pagamento até a '
     'data de vencimento.\n\n'
     '##1f4f6## *Internet que você pode confiar*\n\n'
     'Contrate o *1 Giga + Ponto Adicional* e tenha conexão ultra '
     'rápida com um *segundo ponto de Wi-Fi* para cobrir toda a casa.\n\n'
     '##1f4b0## *Apenas R$ 149,90 por mês*\n'
     '_(valor com desconto de pontualidade)_\n\n'
     '##1f680## *Ideal para:*\n'
     '- Casas grandes ou de dois andares (Wi-Fi em todo canto)\n'
     '- Filmes, séries e jogos em vários cômodos ao mesmo tempo\n'
     '- Home office com estabilidade em qualquer ambiente\n\n'
     '*Confirma a contratação desse plano?*\n\n'
     '*1)* ##2705## Sim, quero esse plano\n'
     '*2)* ##274c## Não, quero ver outro', 40),
    ('confirmacao_plano_generica', 'planos', 'Confirmação de plano (genérica)',
     'Usada apenas se o plano escolhido não tiver texto próprio.', '',
     'Confirma o plano escolhido?\n\n'
     '*1)* ##2705## Sim\n'
     '*2)* ##274c## Não, quero ver outro', 50),

    # ═══ DOCUMENTOS (FOTOS) ══════════════════════════════════════════
    ('pergunta_doc_selfie_recebida', 'documentos', '1ª foto — selfie com documento',
     'Pedido da selfie segurando o documento.', '',
     '##1f4f8## *Pra finalizar, preciso de 3 fotos.*\n\n'
     '*1ª foto:* envie uma *SELFIE* segurando seu RG ou CNH ao lado do rosto.\n\n'
     '_Mande a foto como anexo no chat._', 10),
    ('pergunta_doc_frente_recebida', 'documentos', '2ª foto — frente do documento',
     '', '',
     '##1f4f7## *2ª foto:* envie a *FRENTE* do seu documento (RG ou CNH).\n\n'
     '_Confira se as informações estão legíveis antes de enviar._', 20),
    ('pergunta_doc_verso_recebida', 'documentos', '3ª foto — verso do documento',
     '', '',
     '##1f4f7## *3ª foto:* envie o *VERSO* do seu documento.\n\n'
     '_Última foto, depois finalizamos!_', 30),

    # ═══ AGENDAMENTO ═════════════════════════════════════════════════
    ('pergunta_turno_instalacao', 'agendamento', 'Turno da instalação',
     'MANTENHA as opções 1 (manhã) e 2 (tarde).', '',
     '##23f0## *Qual o melhor turno pra instalação?*\n\n'
     '*1)* ##1f305## Manhã\n*2)* ##2600## Tarde\n\n'
     '_##1f4cc## Responda apenas com o *número* da opção (*1* ou *2*)._', 10),

    # ═══ CONFIRMAÇÕES & ERROS ════════════════════════════════════════
    ('pergunta_o_que_ajustar', 'confirmacoes_erros', 'O que ajustar? (dados negados)',
     'Cliente disse que os dados NÃO estão certos — pergunta o que corrigir. '
     'MANTENHA as opções 1, 2 e 3.', '',
     'Sem problema! O que você quer ajustar? ##1f527##\n\n'
     '*1)* ##1f4cd## Endereço\n'
     '*2)* ##1f464## Dados pessoais\n'
     '*3)* ##1f4e6## Plano selecionado\n\n'
     '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._', 10),

    # ═══ MENU DO CLIENTE ═════════════════════════════════════════════
    ('menu_saudacao_pergunta', 'menu_cliente', 'Pergunta do menu',
     'Frase antes das opções do menu ("Como posso te ajudar hoje?").', '',
     'Como posso te ajudar hoje?', 10),
    ('menu_opcao_novo_servico', 'menu_cliente', 'Opção 1 — novo serviço', '', '',
     'Contratar um novo serviço', 20),
    ('menu_opcao_upgrade_plano', 'menu_cliente', 'Opção — upgrade de plano',
     'Só aparece para quem tem serviço habilitado.', '',
     'Fazer upgrade de plano', 30),
    ('menu_opcao_acompanhar_os', 'menu_cliente', 'Opção — acompanhar instalação', '', '',
     'Acompanhar status da instalação', 40),
    ('menu_opcao_atendimento', 'menu_cliente', 'Opção — falar com atendimento', '', '',
     'Falar com Atendimento', 50),
    ('menu_opcao_finalizar', 'menu_cliente', 'Opção — finalizar', '', '',
     'Finalizar atendimento', 60),
    ('intro_novo_servico', 'menu_cliente', 'Início do fluxo de novo serviço',
     'Enviada quando o cliente escolhe "Contratar um novo serviço".', '',
     'Que bom que você quer expandir conosco! ##1f389##\n\n'
     'Vamos cadastrar seu *novo serviço*. Vou precisar de alguns dados '
     'do *endereço da nova instalação*, escolha do *plano* e fotos do '
     'seu *documento*.', 70),
    ('intro_upgrade', 'menu_cliente', 'Início do fluxo de upgrade',
     'Enviada quando o cliente escolhe "Fazer upgrade de plano".', '',
     'Boa! ##1f4c8## Vamos fazer seu *upgrade de plano*. É rapidinho!', 80),
    ('pergunta_finalizar', 'menu_cliente', 'Mais alguma coisa? (fim do atendimento)',
     'Após concluir uma consulta (ex.: status da O.S.). MANTENHA as opções 1 e 2.', '',
     'Posso te ajudar com mais alguma coisa? ##263A##\n\n'
     '*1)* ##1f504## Sim, voltar ao menu\n'
     '*2)* ##2705## Não, obrigado!', 90),

    # ═══ RECONTATO ═══════════════════════════════════════════════════
    ('recontato_1', 'recontato', 'Recontato — 1ª tentativa',
     'Primeiro silêncio do cliente. Sem emojis (viram "?" no canal).',
     '{saud} = "Oi, Nome!" (mantenha no início)',
     '{saud}Vi que você parou por aqui. Ainda consigo te ajudar? '
     'É só me mandar um *oi* que a gente continua de onde parou.', 10),
    ('recontato_2', 'recontato', 'Recontato — 2ª tentativa',
     'Segundo silêncio.', '{saud} = "Oi, Nome!" (mantenha no início)',
     '{saud}Não quero tomar seu tempo. Em poucos minutos a gente finaliza seu '
     'atendimento. Ainda está por aí? Me responde que eu sigo com você.', 20),
    ('recontato_3', 'recontato', 'Recontato — 3ª (última) tentativa',
     'Terceiro silêncio — última mensagem antes da pausa.',
     '{saud} = "Oi, Nome!" (mantenha no início)',
     '{saud}Essa é a última mensagem por aqui. Se ainda tiver interesse, é só me '
     'responder que eu retomo na hora, de onde a gente parou.', 30),
    ('recontato_despedida', 'recontato', 'Recontato — despedida/pausa',
     'Após esgotar as tentativas: pausa o atendimento (enviada uma única vez).',
     '{saud} = "Oi, Nome!"',
     '{saud}Vou pausar seu atendimento por enquanto. Quando quiser retomar, é só '
     'me chamar de novo que a gente continua de onde parou. Até breve!', 40),

    # ═══ RETOMADA ════════════════════════════════════════════════════
    ('retomada_corpo', 'retomada', 'Retomada — continuar/recomeçar/outro CPF',
     'Cliente reabre um cadastro em andamento. A saudação "Oi, Nome!" é '
     'automática. MANTENHA as opções 1, 2 e 3.', '',
     'Vi que a gente já tinha começado seu atendimento. '
     'Como você quer seguir? ##1f504##\n\n'
     '*1)* Continuar de onde paramos ##25b6##\n'
     '*2)* Recomeçar do início ##1f501##\n'
     '*3)* É para outro CPF ##1f194##\n\n'
     '_##1f4cc## Responda apenas com o *número* da opção (*1*, *2* ou *3*)._', 10),

    # ═══ TRANSBORDO & ENCERRAMENTO ═══════════════════════════════════
    ('transbordo_empresa', 'transbordo_encerramento', 'Transbordo — imóvel empresarial',
     'Cliente escolheu "Empresa" — transferimos para consultor.', '',
     'Entendi! Pra atendimento *empresarial* eu vou te transferir '
     'pra um consultor especializado em planos comerciais. ##1f4f1##\n\n'
     'Aguarde um momentinho ##263A##', 10),
    ('transbordo_sem_viabilidade', 'transbordo_encerramento', 'Transbordo — sem cobertura',
     'Endereço confirmado fora da área de cobertura.', '',
     'Poxa, verifiquei aqui e ainda não temos viabilidade técnica '
     'confirmada nesse endereço. ##1f622##\n\n'
     'Vou te transferir pra um atendente conferir as opções pra sua '
     'região. Aguarde um momentinho ##263A##', 20),
    ('transbordo_atendimento', 'transbordo_encerramento', 'Transbordo — pediu atendente',
     'Cliente escolheu "Falar com Atendimento" no menu.', '',
     'Vou te transferir pra um atendente agora. ##1f4f1##', 30),
    ('transbordo_novo_servico', 'transbordo_encerramento', 'Transbordo — novo serviço (fallback)',
     'Usada quando o fluxo automático de novo serviço não pôde iniciar.', '',
     'Beleza! Vou te transferir pra um atendente falar sobre novos serviços. ##1f680##', 40),
    ('transbordo_upgrade', 'transbordo_encerramento', 'Transbordo — upgrade (fallback)',
     'Usada quando o fluxo automático de upgrade não pôde iniciar.', '',
     'Show! Vou te transferir pra um atendente falar sobre upgrade de plano. ##1f4c8##', 50),
    ('transbordo_generico', 'transbordo_encerramento', 'Transbordo — genérico', '', '',
     'Vou te transferir pra um atendente.', 60),
    ('despedida_encerramento', 'transbordo_encerramento', 'Despedida (fim do atendimento)',
     'Enviada quando o cliente encerra o atendimento.', '',
     'Obrigada pelo contato com a *Megalink*! ##1f499##\n\n'
     'Estamos sempre à disposição. Tenha um ótimo dia! ##1f31f##', 70),
]


class Command(BaseCommand):
    help = "Semeia as mensagens do robô (preserva textos já editados)"

    def handle(self, *args, **opts):
        from ia_validador.models import MensagemRobo
        criadas = atualizadas = 0
        for chave, grupo, rotulo, desc, ph, padrao, ordem in MENSAGENS:
            obj, criada = MensagemRobo.objects.get_or_create(
                chave=chave,
                defaults={'grupo': grupo, 'rotulo': rotulo, 'descricao': desc,
                          'placeholders': ph, 'texto': padrao,
                          'texto_padrao': padrao, 'ordem': ordem, 'ativo': True},
            )
            if criada:
                criadas += 1
            else:
                # Preserva texto/ativo (edição do usuário); atualiza o resto.
                obj.grupo, obj.rotulo, obj.descricao = grupo, rotulo, desc
                obj.placeholders, obj.ordem = ph, ordem
                obj.texto_padrao = padrao
                obj.save(update_fields=['grupo', 'rotulo', 'descricao',
                                        'placeholders', 'ordem', 'texto_padrao'])
                atualizadas += 1
        self.stdout.write(self.style.SUCCESS(
            f'Mensagens do robô: {criadas} criadas, {atualizadas} atualizadas '
            f'(textos editados preservados).'))
