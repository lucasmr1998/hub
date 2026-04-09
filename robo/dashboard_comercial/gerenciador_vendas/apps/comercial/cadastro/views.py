# ============================================================================
# IMPORTS
# ============================================================================
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import models
from django_ratelimit.decorators import ratelimit

import json
import traceback
import logging

logger = logging.getLogger(__name__)

# Models
from apps.comercial.cadastro.models import (
    ConfiguracaoCadastro,
    PlanoInternet,
    OpcaoVencimento,
    CadastroCliente,
    DocumentoLead,
)
from apps.comercial.leads.models import LeadProspecto


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_client_ip(request):
    """Função para obter o IP real do cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# ============================================================================
# VIEWS DE CADASTRO
# ============================================================================

@xframe_options_sameorigin
def cadastro_cliente_view(request):
    """View para a página de cadastro de clientes"""
    try:
        # Buscar configuração ativa
        config = ConfiguracaoCadastro.objects.filter(ativo=True).first()
        if not config:
            # Configuração padrão se não houver nenhuma
            config = {
                'titulo_pagina': 'Cadastro de Cliente - Megalink',
                'subtitulo_pagina': 'Preencha seus dados para começar',
                'telefone_suporte': '(89) 2221-0068',
                'whatsapp_suporte': '558922210068',
                'email_suporte': 'contato@megalinkpiaui.com.br',
                'mostrar_selecao_plano': True,
                'cpf_obrigatorio': True,
                'email_obrigatorio': True,
                'telefone_obrigatorio': True,
                'endereco_obrigatorio': True,
                'validar_cep': True,
                'validar_cpf': True,
                'mostrar_progress_bar': True,
                'numero_etapas': 6,
                'mensagem_sucesso': 'Parabéns! Seu cadastro foi realizado com sucesso.',
                'instrucoes_pos_cadastro': 'Em breve nossa equipe entrará em contato para agendar a instalação.',
                'criar_lead_automatico': True,
                'origem_lead_padrao': 'site',
                # Configurações visuais
                'logo_url': 'https://i.ibb.co/q3MyCdBZ/Ativo-33.png',
                'background_type': 'gradient',
                'background_color_1': '#667eea',
                'background_color_2': '#764ba2',
                'background_image_url': '',
                'primary_color': '#667eea',
                'secondary_color': '#764ba2',
                'success_color': '#2ecc71',
                'error_color': '#e74c3c',
                # Configurações de documentação
                'solicitar_documentacao': True,
                'texto_instrucao_selfie': 'Por favor, tire uma selfie segurando seu documento de identificação próximo ao rosto',
                'texto_instrucao_doc_frente': 'Tire uma foto nítida da frente do seu documento',
                'texto_instrucao_doc_verso': 'Tire uma foto nítida do verso do seu documento',
                'tamanho_max_arquivo_mb': 5,
                'formatos_aceitos': 'jpg,jpeg,png,webp',
                # Configurações de contrato
                'exibir_contrato': True,
                'titulo_contrato': 'Termos de Serviço e Contrato',
                'texto_contrato': '''CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE INTERNET

1. DAS PARTES
Este contrato é celebrado entre a EMPRESA (prestadora) e o CLIENTE (contratante).

2. DO OBJETO
O presente contrato tem por objeto a prestação de serviços de internet banda larga.

3. DAS OBRIGAÇÕES DA PRESTADORA
- Fornecer o serviço de internet conforme o plano contratado
- Manter a qualidade e estabilidade da conexão
- Prestar suporte técnico quando necessário

4. DAS OBRIGAÇÕES DO CONTRATANTE
- Pagar pontualmente as mensalidades
- Zelar pelos equipamentos fornecidos em comodato
- Utilizar o serviço de forma legal e ética

5. DO PRAZO
Este contrato tem prazo indeterminado, podendo ser rescindido por qualquer das partes.

6. DO FORO
Fica eleito o foro da comarca local para dirimir quaisquer questões.

Ao aceitar este contrato, você concorda com todos os termos descritos.''',
                'tempo_minimo_leitura_segundos': 30,
                'texto_aceite_contrato': 'Li e concordo com os termos do contrato'
            }

        # Buscar planos ativos
        planos = PlanoInternet.objects.filter(ativo=True).order_by('ordem_exibicao', 'valor_mensal')

        # Buscar opções de vencimento
        vencimentos = OpcaoVencimento.objects.filter(ativo=True).order_by('ordem_exibicao', 'dia_vencimento')

        context = {
            'config': config,
            'planos': planos,
            'vencimentos': vencimentos
        }

        return render(request, 'comercial/cadastro/cadastro.html', context)

    except Exception as e:
        # Log do erro
        logger.error("Erro na view de cadastro: %s", e, exc_info=True)
        return render(request, 'comercial/cadastro/cadastro.html', {
            'error': 'Erro ao carregar configurações. Tente novamente.'
        })


@ratelimit(key='ip', rate='10/m', method='ALL', block=True)
@csrf_exempt
@require_http_methods(["POST"])
def api_cadastro_cliente(request):
    """API para processar cadastro de clientes"""
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info("=== INICIANDO CADASTRO DE CLIENTE ===")
        logger.info(f"Content-Length: {request.META.get('CONTENT_LENGTH', 'unknown')}")
        logger.info(f"Content-Type: {request.META.get('CONTENT_TYPE', 'unknown')}")

        data = json.loads(request.body)
        logger.info(f"Dados recebidos: {list(data.keys())}")

        # Extrair dados do request
        ip_cliente = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Criar instância do cadastro
        cadastro = CadastroCliente(
            nome_completo=data.get('nome_completo', '').strip(),
            cpf=data.get('cpf', '').replace('.', '').replace('-', ''),
            rg=data.get('rg', '').strip() if data.get('rg') else None,
            email=data.get('email', '').strip().lower(),
            telefone=data.get('telefone', '').replace('(', '').replace(')', '').replace('-', '').replace(' ', ''),
            data_nascimento=data.get('data_nascimento'),
            cep=data.get('cep', '').replace('-', ''),
            endereco=data.get('endereco', '').strip(),
            numero=data.get('numero', '').strip(),
            bairro=data.get('bairro', '').strip(),
            cidade=data.get('cidade', '').strip(),
            estado=data.get('estado', '').strip().upper(),
            ip_cliente=ip_cliente,
            user_agent=user_agent,
            origem_cadastro=data.get('origem_cadastro', 'site')
        )

        # Definir plano se selecionado
        if data.get('plano_id'):
            try:
                plano = PlanoInternet.objects.get(id=data['plano_id'], ativo=True)
                cadastro.plano_selecionado = plano
            except PlanoInternet.DoesNotExist:
                pass

        # Definir vencimento se selecionado
        if data.get('vencimento_id'):
            try:
                vencimento = OpcaoVencimento.objects.get(id=data['vencimento_id'], ativo=True)
                cadastro.vencimento_selecionado = vencimento
            except OpcaoVencimento.DoesNotExist:
                pass

        # Validar dados pessoais
        erros_pessoais = cadastro.validar_dados_pessoais()
        if erros_pessoais:
            return JsonResponse({
                'success': False,
                'errors': erros_pessoais,
                'step': 'dados_pessoais'
            }, status=400)

        # Validar endereço
        erros_endereco = cadastro.validar_endereco()
        if erros_endereco:
            return JsonResponse({
                'success': False,
                'errors': erros_endereco,
                'step': 'endereco'
            }, status=400)

        # Processar dados do contrato
        if data.get('contrato_aceito'):
            cadastro.contrato_aceito = True
            cadastro.data_aceite_contrato = timezone.now()
            cadastro.ip_aceite_contrato = ip_cliente
            cadastro.tempo_leitura_contrato = data.get('tempo_leitura_contrato', 0)

        # Processar aceite dos termos
        if data.get('termos_aceitos'):
            cadastro.termos_aceitos = True
            cadastro.data_aceite_termos = timezone.now()

        # Salvar cadastro
        cadastro.save()

        # Atualizar status para finalizado
        cadastro.status = 'finalizado'
        cadastro.data_finalizacao = timezone.now()
        cadastro.save()

        # Finalizar cadastro (gera lead e histórico)
        if cadastro.finalizar_cadastro():
            lead = cadastro.lead_gerado

            # Atualizar dados do lead com informações completas
            if lead:
                # Atualizar campos básicos do lead
                lead.nome_razaosocial = cadastro.nome_completo
                lead.email = cadastro.email
                lead.telefone = cadastro.telefone
                lead.cpf_cnpj = cadastro.cpf
                lead.rg = cadastro.rg
                lead.data_nascimento = cadastro.data_nascimento

                # Atualizar endereço
                lead.cep = cadastro.cep
                lead.endereco = f"{cadastro.endereco}, {cadastro.numero}"
                lead.rua = cadastro.endereco
                lead.numero_residencia = cadastro.numero
                lead.bairro = cadastro.bairro
                lead.cidade = cadastro.cidade
                lead.estado = cadastro.estado

                # Atualizar plano e vencimento
                if cadastro.plano_selecionado:
                    lead.id_plano_rp = cadastro.plano_selecionado.id_sistema_externo
                    lead.valor = cadastro.plano_selecionado.valor_mensal

                if cadastro.vencimento_selecionado:
                    # Usar a descrição do vencimento (que contém o ID do sistema externo)
                    lead.id_dia_vencimento = cadastro.vencimento_selecionado.descricao

                # Definir origem
                lead.origem = 'site'

                # Definir IDs customizáveis da configuração
                config = ConfiguracaoCadastro.objects.filter(ativo=True).first()
                if config:
                    lead.id_origem = config.id_origem
                    lead.id_origem_servico = config.id_origem_servico
                    lead.id_vendedor_rp = config.id_vendedor
                else:
                    # Valores padrão se não houver configuração
                    lead.id_origem = data.get('id_origem', 148)
                    lead.id_origem_servico = data.get('id_origem_servico', 63)
                    lead.id_vendedor_rp = data.get('id_vendedor', 901)

                lead.save()

            # Processar documentos se existirem
            if data.get('documentos') and lead:
                documentos = data.get('documentos', {})
                for tipo_doc, doc_data in documentos.items():
                    if doc_data and isinstance(doc_data, dict):
                        try:
                            DocumentoLead.objects.create(
                                lead=lead,
                                tipo_documento=tipo_doc,
                                arquivo_base64=doc_data.get('base64', ''),
                                nome_arquivo=doc_data.get('name', ''),
                                tamanho_arquivo=doc_data.get('size', 0),
                                formato_arquivo=doc_data.get('type', '')
                            )
                        except Exception as e:
                            logger.error(f"Erro ao salvar documento {tipo_doc}: {str(e)}")

                # Atualizar status de documentação do lead
                lead.documentacao_completa = True
                lead.data_documentacao_completa = timezone.now()
                lead.save()

            # Processar aceite de contrato no lead
            if data.get('contrato_aceito') and lead:
                lead.contrato_aceito = True
                lead.data_aceite_contrato = timezone.now()
                lead.ip_aceite_contrato = ip_cliente
                lead.save()

            return JsonResponse({
                'success': True,
                'message': 'Cadastro realizado com sucesso!',
                'cadastro_id': cadastro.id,
                'lead_id': lead.id if lead else None
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Erro ao finalizar cadastro. Tente novamente.',
                'errors': cadastro.erros_validacao if hasattr(cadastro, 'erros_validacao') else ['Erro interno']
            }, status=500)

    except json.JSONDecodeError as e:
        logger.error(f"Erro JSON Decode: {str(e)}")
        logger.error(f"Body: {request.body[:500]}")
        return JsonResponse({
            'success': False,
            'message': 'Dados inválidos enviados.'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao processar cadastro: {str(e)}")
        logger.error(f"Traceback: ", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'Erro interno: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_planos_internet(request):
    """API para buscar planos de internet"""
    try:
        planos = PlanoInternet.objects.filter(ativo=True).order_by('ordem_exibicao', 'valor_mensal')

        planos_data = []
        for plano in planos:
            planos_data.append({
                'id': plano.id,
                'nome': plano.nome,
                'descricao': plano.descricao,
                'velocidade_download': plano.velocidade_download,
                'velocidade_upload': plano.velocidade_upload,
                'valor_mensal': float(plano.valor_mensal),
                'valor_formatado': plano.get_valor_formatado(),
                'velocidade_formatada': plano.get_velocidade_formatada(),
                'wifi_6': plano.wifi_6,
                'suporte_prioritario': plano.suporte_prioritario,
                'suporte_24h': plano.suporte_24h,
                'upload_simetrico': plano.upload_simetrico,
                'destaque': plano.destaque,
                'ordem_exibicao': plano.ordem_exibicao
            })

        return JsonResponse({
            'success': True,
            'planos': planos_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao buscar planos: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def api_vencimentos(request):
    """API para buscar opções de vencimento"""
    try:
        vencimentos = OpcaoVencimento.objects.filter(ativo=True).order_by('ordem_exibicao', 'dia_vencimento')

        vencimentos_data = []
        for vencimento in vencimentos:
            vencimentos_data.append({
                'id': vencimento.id,
                'dia_vencimento': vencimento.dia_vencimento,
                'descricao': vencimento.descricao,
                'ordem_exibicao': vencimento.ordem_exibicao
            })

        return JsonResponse({
            'success': True,
            'vencimentos': vencimentos_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Erro ao buscar vencimentos: {str(e)}'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_upload_documento(request):
    """
    API para upload de documentos durante cadastro
    """
    try:
        data = json.loads(request.body.decode('utf-8'))

        # Validar campos obrigatórios
        required_fields = ['tipo_documento', 'arquivo_base64', 'nome_arquivo', 'tamanho_arquivo', 'formato_arquivo']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'message': f'Campo obrigatório ausente: {field}'
                }, status=400)

        # Validar tipo de documento
        tipos_validos = ['selfie', 'doc_frente', 'doc_verso', 'comprovante_residencia', 'contrato_assinado']
        if data['tipo_documento'] not in tipos_validos:
            return JsonResponse({
                'success': False,
                'message': 'Tipo de documento inválido'
            }, status=400)

        # Validar tamanho do arquivo
        max_size = 5 * 1024 * 1024  # 5MB
        if data.get('tamanho_arquivo', 0) > max_size:
            return JsonResponse({
                'success': False,
                'message': f'Arquivo muito grande. Máximo permitido: {max_size/1024/1024}MB'
            }, status=400)

        # Retornar sucesso (o documento será salvo quando o lead for criado)
        return JsonResponse({
            'success': True,
            'message': 'Documento validado com sucesso'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'JSON inválido'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao processar upload de documento: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Erro ao processar documento: {str(e)}'
        }, status=500)


@ratelimit(key='ip', rate='10/m', method='ALL', block=True)
@csrf_exempt
@require_http_methods(["GET"])
def api_consulta_cep(request, cep):
    """
    API para consultar CEP usando múltiplas fontes para melhor resultado
    """
    try:
        import requests
        import json as json_lib
        import urllib3

        # Desabilitar warnings de SSL
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Limpar CEP (remover caracteres especiais)
        cep_limpo = cep.replace('-', '').replace('.', '').strip()

        logger.info(f"=== Iniciando consulta de CEP: {cep_limpo} ===")

        # Validar formato do CEP
        if not cep_limpo.isdigit() or len(cep_limpo) != 8:
            logger.warning(f"CEP inválido: {cep_limpo}")
            response = JsonResponse({
                'success': False,
                'message': 'CEP deve conter 8 dígitos'
            }, status=400)
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            return response

        # Verificar cache local (em produção, usar Redis ou similar)
        cache_key = f"cep_cache_{cep_limpo}"
        # Por simplicidade, vamos usar um cache em memória
        # Em produção, implementar com Redis ou banco de dados

        # Lista de APIs para tentar em sequência
        apis_cep = [
            {
                'name': 'ViaCEP',
                'url': f"https://viacep.com.br/ws/{cep_limpo}/json/",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('logradouro', ''),
                    'complemento': data.get('complemento', ''),
                    'bairro': data.get('bairro', ''),
                    'localidade': data.get('localidade', ''),
                    'uf': data.get('uf', ''),
                    'ibge': data.get('ibge', ''),
                    'gia': data.get('gia', ''),
                    'ddd': data.get('ddd', ''),
                    'siafi': data.get('siafi', '')
                },
                'error_check': lambda data: data.get('erro')
            },
            {
                'name': 'CepAPI',
                'url': f"https://cep.awesomeapi.com.br/json/{cep_limpo}",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('address', ''),
                    'complemento': '',
                    'bairro': data.get('district', ''),
                    'localidade': data.get('city', ''),
                    'uf': data.get('state', ''),
                    'ibge': data.get('city_ibge', ''),
                    'gia': '',
                    'ddd': data.get('ddd', ''),
                    'siafi': ''
                },
                'error_check': lambda data: data.get('status') == 400
            },
            {
                'name': 'BrasilAPI',
                'url': f"https://brasilapi.com.br/api/cep/v1/{cep_limpo}",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('street', ''),
                    'complemento': '',
                    'bairro': data.get('neighborhood', ''),
                    'localidade': data.get('city', ''),
                    'uf': data.get('state', ''),
                    'ibge': '',
                    'gia': '',
                    'ddd': '',
                    'siafi': ''
                },
                'error_check': lambda data: 'errors' in data
            },
            {
                'name': 'Postmon',
                'url': f"https://api.postmon.com.br/v1/cep/{cep_limpo}",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('logradouro', ''),
                    'complemento': '',
                    'bairro': data.get('bairro', ''),
                    'localidade': data.get('cidade', ''),
                    'uf': data.get('estado', ''),
                    'ibge': '',
                    'gia': '',
                    'ddd': '',
                    'siafi': ''
                },
                'error_check': lambda data: False  # Postmon não retorna erro específico
            },
            {
                'name': 'OpenCEP',
                'url': f"https://opencep.com/v1/{cep_limpo}",
                'timeout': 10,
                'headers': {'User-Agent': 'Mozilla/5.0 (compatible; CEP-Service/1.0)'},
                'parser': lambda data: {
                    'cep': cep_limpo,
                    'logradouro': data.get('address', ''),
                    'complemento': '',
                    'bairro': data.get('district', ''),
                    'localidade': data.get('city', ''),
                    'uf': data.get('state', ''),
                    'ibge': data.get('ibge', ''),
                    'gia': '',
                    'ddd': data.get('ddd', ''),
                    'siafi': ''
                },
                'error_check': lambda data: 'error' in data
            }
        ]

        # Tentar cada API em sequência
        for api in apis_cep:
            try:
                logger.info(f"Tentando consultar CEP {cep_limpo} via {api['name']} - URL: {api['url']}")

                # Fazer requisição com timeout e headers
                response = requests.get(
                    api['url'],
                    headers=api.get('headers', {}),
                    timeout=api['timeout'],
                    verify=False  # Desabilitar verificação SSL para evitar erros
                )

                logger.info(f"Status HTTP {response.status_code} da API {api['name']}")

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Resposta da API {api['name']}: {json_lib.dumps(data, ensure_ascii=False)[:200]}")

                    # Verificar se houve erro na API
                    if api['error_check'](data):
                        logger.warning(f"API {api['name']} retornou erro para CEP {cep_limpo}: {data}")
                        continue

                    # Processar dados com sucesso
                    endereco_data = api['parser'](data)
                    logger.info(f"Dados processados: {json_lib.dumps(endereco_data, ensure_ascii=False)}")

                    # Validar se os dados essenciais estão presentes
                    if endereco_data.get('localidade') and endereco_data.get('uf'):
                        logger.info(f"CEP {cep_limpo} encontrado via {api['name']}")

                        response_json = JsonResponse({
                            'success': True,
                            'data': endereco_data,
                            'fonte': api['name']
                        })
                        response_json['Access-Control-Allow-Origin'] = '*'
                        response_json['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
                        response_json['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
                        return response_json
                    else:
                        logger.warning(f"API {api['name']} retornou dados incompletos para CEP {cep_limpo}: localidade={endereco_data.get('localidade')}, uf={endereco_data.get('uf')}")
                        continue
                else:
                    logger.warning(f"API {api['name']} retornou status {response.status_code} para CEP {cep_limpo}")
                    if response.status_code == 404:
                        logger.warning(f"CEP {cep_limpo} não encontrado na {api['name']}")
                    continue

            except requests.Timeout:
                logger.warning(f"Timeout na API {api['name']} para CEP {cep_limpo}")
                continue

            except requests.ConnectionError as e:
                logger.warning(f"Erro de conexão na API {api['name']} para CEP {cep_limpo}: {str(e)}")
                continue

            except requests.RequestException as e:
                logger.warning(f"Erro de requisição na API {api['name']} para CEP {cep_limpo}: {str(e)}")
                continue

            except Exception as e:
                logger.error(f"Erro inesperado na API {api['name']} para CEP {cep_limpo}: {str(e)}")
                logger.error(traceback.format_exc())
                continue

        # Se nenhuma API funcionou
        logger.error(f"Nenhuma das {len(apis_cep)} APIs conseguiu consultar o CEP {cep_limpo}")
        logger.error(f"APIs tentadas: {', '.join([api['name'] for api in apis_cep])}")
        response = JsonResponse({
            'success': False,
            'message': f'CEP {cep_limpo} não encontrado. Verifique se o CEP está correto ou tente novamente mais tarde.',
            'cep': cep_limpo,
            'apis_tentadas': [api['name'] for api in apis_cep]
        }, status=404)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    except ImportError as e:
        response = JsonResponse({
            'success': False,
            'message': f'Erro de importação: {str(e)}'
        }, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response


# ============================================================================
# VIEWS DE CONFIGURAÇÃO DE CADASTRO
# ============================================================================

@login_required
def configuracoes_cadastro_view(request):
    """View para gerenciar configurações de cadastro"""
    configuracoes = ConfiguracaoCadastro.objects.all()
    return render(request, 'comercial/cadastro/configuracoes/cadastro.html', {
        'configuracoes': configuracoes
    })

@login_required
@require_http_methods(["POST"])
def salvar_configuracoes_cadastro_view(request):
    """API para salvar configurações de cadastro via AJAX"""
    try:
        import json
        data = json.loads(request.body)

        # Obter ou criar configuração
        config, created = ConfiguracaoCadastro.objects.get_or_create(
            empresa='Megalink',
            defaults={
                'titulo_pagina': 'Cadastro de Cliente',
                'subtitulo_pagina': 'Preencha seus dados para começar'
            }
        )

        # Atualizar configurações visuais
        if 'logoUrl' in data:
            config.logo_url = data.get('logoUrl', config.logo_url)
        if 'backgroundType' in data:
            config.background_type = data.get('backgroundType', config.background_type)
        if 'backgroundColor1' in data:
            config.background_color_1 = data.get('backgroundColor1', config.background_color_1)
        if 'backgroundColor2' in data:
            config.background_color_2 = data.get('backgroundColor2', config.background_color_2)
        if 'backgroundImageUrl' in data:
            config.background_image_url = data.get('backgroundImageUrl', config.background_image_url)
        if 'primaryColor' in data:
            config.primary_color = data.get('primaryColor', config.primary_color)
        if 'secondaryColor' in data:
            config.secondary_color = data.get('secondaryColor', config.secondary_color)
        if 'successColor' in data:
            config.success_color = data.get('successColor', config.success_color)
        if 'errorColor' in data:
            config.error_color = data.get('errorColor', config.error_color)

        # Atualizar configurações de conteúdo
        if 'mainTitle' in data:
            config.titulo_pagina = data.get('mainTitle', config.titulo_pagina)
        if 'subtitle' in data:
            config.subtitulo_pagina = data.get('subtitle', config.subtitulo_pagina)
        if 'successMessage' in data:
            config.mensagem_sucesso = data.get('successMessage', config.mensagem_sucesso)
        if 'postInstructions' in data:
            config.instrucoes_pos_cadastro = data.get('postInstructions', config.instrucoes_pos_cadastro)

        # Atualizar configurações de contato
        if 'supportPhone' in data:
            config.telefone_suporte = data.get('supportPhone', config.telefone_suporte)
        if 'supportWhatsapp' in data:
            config.whatsapp_suporte = data.get('supportWhatsapp', config.whatsapp_suporte)
        if 'supportEmail' in data:
            config.email_suporte = data.get('supportEmail', config.email_suporte)

        # Atualizar configurações de campos obrigatórios
        if 'cpfRequired' in data:
            config.cpf_obrigatorio = data.get('cpfRequired', False)
        if 'emailRequired' in data:
            config.email_obrigatorio = data.get('emailRequired', False)
        if 'phoneRequired' in data:
            config.telefone_obrigatorio = data.get('phoneRequired', False)
        if 'addressRequired' in data:
            config.endereco_obrigatorio = data.get('addressRequired', False)

        # Atualizar configurações de validação
        if 'validateCep' in data:
            config.validar_cep = data.get('validateCep', False)
        if 'validateCpf' in data:
            config.validar_cpf = data.get('validateCpf', False)
        if 'showProgressBar' in data:
            config.mostrar_progress_bar = data.get('showProgressBar', False)
        if 'numberOfSteps' in data:
            config.numero_etapas = data.get('numberOfSteps', 4)

        # Atualizar configurações avançadas
        if 'autoCreateLead' in data:
            config.criar_lead_automatico = data.get('autoCreateLead', False)
        if 'leadOrigin' in data:
            config.origem_lead_padrao = data.get('leadOrigin', 'site')
        if 'sendEmailConfirmation' in data:
            config.enviar_email_confirmacao = data.get('sendEmailConfirmation', False)
        if 'sendWhatsappConfirmation' in data:
            config.enviar_whatsapp_confirmacao = data.get('sendWhatsappConfirmation', False)

        config.save()

        return JsonResponse({
            'success': True,
            'message': 'Configurações salvas com sucesso!',
            'created': created
        })

    except Exception as e:
        logger.error(f'Erro ao salvar configurações de cadastro: {str(e)}')
        return JsonResponse({
            'success': False,
            'message': f'Erro ao salvar configurações: {str(e)}'
        })


@login_required
def planos_internet_view(request):
    """View para gerenciar planos de internet"""
    planos = PlanoInternet.objects.all().order_by('ordem_exibicao', 'nome')
    return render(request, 'comercial/cadastro/configuracoes/planos.html', {
        'planos': planos
    })


@login_required
def opcoes_vencimento_view(request):
    """View para gerenciar opções de vencimento"""
    opcoes = OpcaoVencimento.objects.all().order_by('ordem_exibicao', 'dia_vencimento')
    return render(request, 'comercial/cadastro/configuracoes/vencimentos.html', {
        'opcoes': opcoes
    })


# ============================================================================
# APIS DE GERENCIAMENTO - CONFIGURAÇÕES DE CADASTRO
# ============================================================================

@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_configuracoes_cadastro(request):
    """API para gerenciar configurações de cadastro"""
    try:
        if request.method == 'GET':
            configuracoes = ConfiguracaoCadastro.objects.all()
            data = []
            for config in configuracoes:
                data.append({
                    'id': config.id,
                    'empresa': config.empresa,
                    'titulo_pagina': config.titulo_pagina,
                    'subtitulo_pagina': config.subtitulo_pagina,
                    'ativo': config.ativo,
                    'mostrar_selecao_plano': config.mostrar_selecao_plano,
                    'criar_lead_automatico': config.criar_lead_automatico,
                    'data_atualizacao': config.data_atualizacao.strftime('%d/%m/%Y %H:%M:%S')
                })
            return JsonResponse({'success': True, 'data': data})

        elif request.method == 'POST':
            data = json.loads(request.body)
            config = ConfiguracaoCadastro.objects.create(
                empresa=data.get('empresa'),
                titulo_pagina=data.get('titulo_pagina'),
                subtitulo_pagina=data.get('subtitulo_pagina', ''),
                ativo=data.get('ativo', True),
                mostrar_selecao_plano=data.get('mostrar_selecao_plano', True),
                criar_lead_automatico=data.get('criar_lead_automatico', True)
            )
            return JsonResponse({
                'success': True,
                'message': 'Configuração criada com sucesso!',
                'id': config.id
            })

        elif request.method == 'PUT':
            data = json.loads(request.body)
            config_id = data.get('id')
            config = ConfiguracaoCadastro.objects.get(id=config_id)

            config.empresa = data.get('empresa', config.empresa)
            config.titulo_pagina = data.get('titulo_pagina', config.titulo_pagina)
            config.subtitulo_pagina = data.get('subtitulo_pagina', config.subtitulo_pagina)
            config.ativo = data.get('ativo', config.ativo)
            config.mostrar_selecao_plano = data.get('mostrar_selecao_plano', config.mostrar_selecao_plano)
            config.criar_lead_automatico = data.get('criar_lead_automatico', config.criar_lead_automatico)
            config.save()

            return JsonResponse({
                'success': True,
                'message': 'Configuração atualizada com sucesso!'
            })

        elif request.method == 'DELETE':
            data = json.loads(request.body)
            config_id = data.get('id')
            config = ConfiguracaoCadastro.objects.get(id=config_id)
            config.delete()

            return JsonResponse({
                'success': True,
                'message': 'Configuração excluída com sucesso!'
            })

    except Exception as e:
        logger.error(f"Erro na API de configurações de cadastro: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_planos_internet_gerencia(request):
    """API para gerenciar planos de internet"""
    try:
        if request.method == 'GET':
            planos = PlanoInternet.objects.all().order_by('ordem_exibicao', 'nome')
            data = []
            for plano in planos:
                data.append({
                    'id': plano.id,
                    'nome': plano.nome,
                    'descricao': plano.descricao,
                    'velocidade_download': plano.velocidade_download,
                    'velocidade_upload': plano.velocidade_upload,
                    'valor_mensal': float(plano.valor_mensal),
                    'destaque': plano.destaque,
                    'ativo': plano.ativo,
                    'ordem_exibicao': plano.ordem_exibicao,
                    'wifi_6': plano.wifi_6,
                    'suporte_prioritario': plano.suporte_prioritario,
                    'suporte_24h': plano.suporte_24h,
                    'upload_simetrico': plano.upload_simetrico
                })
            return JsonResponse({'success': True, 'data': data})

        elif request.method == 'POST':
            data = json.loads(request.body)
            plano = PlanoInternet.objects.create(
                nome=data.get('nome'),
                descricao=data.get('descricao', ''),
                velocidade_download=data.get('velocidade_download'),
                velocidade_upload=data.get('velocidade_upload'),
                valor_mensal=data.get('valor_mensal'),
                destaque=data.get('destaque', False),
                ativo=data.get('ativo', True),
                ordem_exibicao=data.get('ordem_exibicao', 0),
                wifi_6=data.get('wifi_6', False),
                suporte_prioritario=data.get('suporte_prioritario', False),
                suporte_24h=data.get('suporte_24h', False),
                upload_simetrico=data.get('upload_simetrico', False)
            )
            return JsonResponse({
                'success': True,
                'message': 'Plano criado com sucesso!',
                'id': plano.id
            })

        elif request.method == 'PUT':
            data = json.loads(request.body)
            plano_id = data.get('id')
            plano = PlanoInternet.objects.get(id=plano_id)

            plano.nome = data.get('nome', plano.nome)
            plano.descricao = data.get('descricao', plano.descricao)
            plano.velocidade_download = data.get('velocidade_download', plano.velocidade_download)
            plano.velocidade_upload = data.get('velocidade_upload', plano.velocidade_upload)
            plano.valor_mensal = data.get('valor_mensal', plano.valor_mensal)
            plano.destaque = data.get('destaque', plano.destaque)
            plano.ativo = data.get('ativo', plano.ativo)
            plano.ordem_exibicao = data.get('ordem_exibicao', plano.ordem_exibicao)
            plano.wifi_6 = data.get('wifi_6', plano.wifi_6)
            plano.suporte_prioritario = data.get('suporte_prioritario', plano.suporte_prioritario)
            plano.suporte_24h = data.get('suporte_24h', plano.suporte_24h)
            plano.upload_simetrico = data.get('upload_simetrico', plano.upload_simetrico)
            plano.save()

            return JsonResponse({
                'success': True,
                'message': 'Plano atualizado com sucesso!'
            })

        elif request.method == 'DELETE':
            data = json.loads(request.body)
            plano_id = data.get('id')
            plano = PlanoInternet.objects.get(id=plano_id)
            plano.delete()

            return JsonResponse({
                'success': True,
                'message': 'Plano excluído com sucesso!'
            })

    except Exception as e:
        logger.error(f"Erro na API de planos de internet: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def api_opcoes_vencimento_gerencia(request):
    """API para gerenciar opções de vencimento"""
    try:
        if request.method == 'GET':
            opcoes = OpcaoVencimento.objects.all().order_by('ordem_exibicao', 'dia_vencimento')
            data = []
            for opcao in opcoes:
                data.append({
                    'id': opcao.id,
                    'dia_vencimento': opcao.dia_vencimento,
                    'descricao': opcao.descricao,
                    'ordem_exibicao': opcao.ordem_exibicao,
                    'ativo': opcao.ativo
                })
            return JsonResponse({'success': True, 'data': data})

        elif request.method == 'POST':
            data = json.loads(request.body)
            opcao = OpcaoVencimento.objects.create(
                dia_vencimento=data.get('dia_vencimento'),
                descricao=data.get('descricao', ''),
                ordem_exibicao=data.get('ordem_exibicao', 0),
                ativo=data.get('ativo', True)
            )
            return JsonResponse({
                'success': True,
                'message': 'Opção de vencimento criada com sucesso!',
                'id': opcao.id
            })

        elif request.method == 'PUT':
            data = json.loads(request.body)
            opcao_id = data.get('id')
            opcao = OpcaoVencimento.objects.get(id=opcao_id)

            opcao.dia_vencimento = data.get('dia_vencimento', opcao.dia_vencimento)
            opcao.descricao = data.get('descricao', opcao.descricao)
            opcao.ordem_exibicao = data.get('ordem_exibicao', opcao.ordem_exibicao)
            opcao.ativo = data.get('ativo', opcao.ativo)
            opcao.save()

            return JsonResponse({
                'success': True,
                'message': 'Opção de vencimento atualizada com sucesso!'
            })

        elif request.method == 'DELETE':
            data = json.loads(request.body)
            opcao_id = data.get('id')
            opcao = OpcaoVencimento.objects.get(id=opcao_id)
            opcao.delete()

            return JsonResponse({
                'success': True,
                'message': 'Opção de vencimento excluída com sucesso!'
            })

    except Exception as e:
        logger.error(f"Erro na API de opções de vencimento: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
