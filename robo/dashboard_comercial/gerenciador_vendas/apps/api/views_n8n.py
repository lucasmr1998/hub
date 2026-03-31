"""
Views DRF para integracao N8N / sistemas externos.

Autenticacao: APITokenAuthentication (Bearer token via header).
Nao usa SessionAuthentication — endpoints puramente machine-to-machine.
"""

import json
import re
import unicodedata
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.sistema.authentication import APITokenAuthentication

from apps.comercial.leads.models import (
    LeadProspecto,
    ImagemLeadProspecto,
    Prospecto,
    HistoricoContato,
)
from apps.comercial.atendimento.models import (
    FluxoAtendimento,
    QuestaoFluxo,
    AtendimentoFluxo,
    RespostaQuestao,
)

from .serializers_n8n import (
    LeadInputSerializer,
    LeadOutputSerializer,
    ImagemLeadInputSerializer,
    ImagemLeadOutputSerializer,
    ProspectoInputSerializer,
    ProspectoOutputSerializer,
    HistoricoContatoInputSerializer,
    HistoricoContatoOutputSerializer,
    FluxoAtendimentoOutputSerializer,
    QuestaoFluxoOutputSerializer,
    AtendimentoFluxoInputSerializer,
    AtendimentoFluxoOutputSerializer,
    RespostaQuestaoInputSerializer,
    RespostaQuestaoOutputSerializer,
)

logger = logging.getLogger(__name__)


# ── Mixin para autenticacao N8N ────────────────────────────────────────

class N8NAPIMixin:
    """Configuracao comum para todos os endpoints N8N."""
    authentication_classes = [APITokenAuthentication]
    permission_classes = [IsAuthenticated]


# =====================================================================
# 1. LeadAPIView  — POST (criar), PUT (atualizar por pk)
# =====================================================================

class LeadAPIView(N8NAPIMixin, APIView):

    def post(self, request):
        serializer = LeadInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        lead = serializer.save()
        return Response(
            {'success': True, 'lead': LeadOutputSerializer(lead).data},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, pk=None):
        if pk is None:
            return Response(
                {'success': False, 'error': 'ID do lead e obrigatorio na URL.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            lead = LeadProspecto.all_tenants.get(pk=pk)
        except LeadProspecto.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Lead nao encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = LeadInputSerializer(lead, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        lead = serializer.save()
        return Response(
            {'success': True, 'lead': LeadOutputSerializer(lead).data},
            status=status.HTTP_200_OK,
        )


# =====================================================================
# 2. LeadImagemAPIView  — POST (criar), GET (listar por lead), DELETE
# =====================================================================

class LeadImagemAPIView(N8NAPIMixin, APIView):

    def post(self, request):
        serializer = ImagemLeadInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        imagem = serializer.save()
        return Response(
            {'success': True, 'imagem': ImagemLeadOutputSerializer(imagem).data},
            status=status.HTTP_201_CREATED,
        )

    def get(self, request):
        lead_id = request.query_params.get('lead_id')
        if not lead_id:
            return Response(
                {'success': False, 'error': 'Parametro lead_id e obrigatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        imagens = ImagemLeadProspecto.all_tenants.filter(lead_id=lead_id)
        return Response(
            {'success': True, 'imagens': ImagemLeadOutputSerializer(imagens, many=True).data},
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk=None):
        if pk is None:
            return Response(
                {'success': False, 'error': 'ID da imagem e obrigatorio na URL.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            imagem = ImagemLeadProspecto.all_tenants.get(pk=pk)
        except ImagemLeadProspecto.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Imagem nao encontrada.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        imagem.delete()
        return Response(
            {'success': True, 'message': 'Imagem removida com sucesso.'},
            status=status.HTTP_200_OK,
        )


# =====================================================================
# 3. ProspectoAPIView  — POST (criar), PUT (atualizar)
# =====================================================================

class ProspectoAPIView(N8NAPIMixin, APIView):

    def post(self, request):
        serializer = ProspectoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        prospecto = serializer.save()
        return Response(
            {'success': True, 'prospecto': ProspectoOutputSerializer(prospecto).data},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, pk=None):
        if pk is None:
            return Response(
                {'success': False, 'error': 'ID do prospecto e obrigatorio na URL.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            prospecto = Prospecto.all_tenants.get(pk=pk)
        except Prospecto.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Prospecto nao encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ProspectoInputSerializer(prospecto, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        prospecto = serializer.save()
        return Response(
            {'success': True, 'prospecto': ProspectoOutputSerializer(prospecto).data},
            status=status.HTTP_200_OK,
        )


# =====================================================================
# 4. HistoricoContatoAPIView  — POST (criar), PUT (atualizar)
# =====================================================================

class HistoricoContatoAPIView(N8NAPIMixin, APIView):

    def post(self, request):
        serializer = HistoricoContatoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contato = serializer.save()
        return Response(
            {'success': True, 'contato': HistoricoContatoOutputSerializer(contato).data},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, pk=None):
        if pk is None:
            return Response(
                {'success': False, 'error': 'ID do contato e obrigatorio na URL.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            contato = HistoricoContato.all_tenants.get(pk=pk)
        except HistoricoContato.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Contato nao encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = HistoricoContatoInputSerializer(contato, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contato = serializer.save()
        return Response(
            {'success': True, 'contato': HistoricoContatoOutputSerializer(contato).data},
            status=status.HTTP_200_OK,
        )


# =====================================================================
# 5. AtendimentoN8NAPIView  — POST (iniciar), GET (consultar por id)
# =====================================================================

class AtendimentoN8NAPIView(N8NAPIMixin, APIView):

    def post(self, request):
        """Inicia um novo atendimento de fluxo para um lead."""
        serializer = AtendimentoFluxoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lead = serializer.validated_data['lead']
        fluxo = serializer.validated_data['fluxo']

        if not fluxo.pode_ser_usado():
            return Response(
                {'success': False, 'error': 'Fluxo nao esta disponivel para uso.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_questoes = fluxo.get_total_questoes()

        atendimento = AtendimentoFluxo(
            lead=lead,
            fluxo=fluxo,
            status='iniciado',
            questao_atual=1,
            total_questoes=total_questoes,
            max_tentativas=fluxo.max_tentativas,
        )
        atendimento.save()

        # Retornar atendimento com primeira questao
        primeira_questao = fluxo.get_questao_por_indice(1)
        data = AtendimentoFluxoOutputSerializer(atendimento).data
        if primeira_questao:
            data['questao'] = QuestaoFluxoOutputSerializer(primeira_questao).data

        return Response(
            {'success': True, 'atendimento': data},
            status=status.HTTP_201_CREATED,
        )

    def get(self, request, pk=None):
        """Consulta estado atual de um atendimento."""
        if pk is None:
            return Response(
                {'success': False, 'error': 'ID do atendimento e obrigatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            atendimento = AtendimentoFluxo.all_tenants.get(pk=pk)
        except AtendimentoFluxo.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Atendimento nao encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = AtendimentoFluxoOutputSerializer(atendimento).data
        questao_obj = atendimento.get_questao_atual_obj()
        if questao_obj:
            data['questao'] = QuestaoFluxoOutputSerializer(questao_obj).data

        return Response({'success': True, 'atendimento': data})


# =====================================================================
# 6. AtendimentoRespostaAPIView  — POST (responder questao)
# =====================================================================

class AtendimentoRespostaAPIView(N8NAPIMixin, APIView):

    def post(self, request, pk=None):
        """Registra resposta para a questao atual do atendimento."""
        if pk is None:
            return Response(
                {'success': False, 'error': 'ID do atendimento e obrigatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            atendimento = AtendimentoFluxo.all_tenants.get(pk=pk)
        except AtendimentoFluxo.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Atendimento nao encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if atendimento.status in ('completado', 'cancelado', 'abandonado'):
            return Response(
                {'success': False, 'error': f'Atendimento ja esta {atendimento.status}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        questao_obj = atendimento.get_questao_atual_obj()
        if not questao_obj:
            return Response(
                {'success': False, 'error': 'Nenhuma questao atual encontrada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resposta_texto = request.data.get('resposta_texto', '')
        if not resposta_texto and questao_obj.tipo_validacao == 'obrigatoria':
            return Response(
                {'success': False, 'error': 'Resposta obrigatoria para esta questao.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validar resposta usando logica da questao
        valido, msg_erro, dados_extras = questao_obj.validar_resposta(resposta_texto)

        # Salvar resposta
        resposta = RespostaQuestao(
            atendimento=atendimento,
            questao=questao_obj,
            resposta=resposta_texto,
            valida=valido,
            mensagem_erro=msg_erro if not valido else '',
        )
        resposta.save()

        if not valido:
            atendimento.tentativas_atual += 1
            atendimento.save(update_fields=['tentativas_atual'])
            return Response(
                {
                    'success': False,
                    'error': msg_erro,
                    'valida': False,
                    'tentativas_atual': atendimento.tentativas_atual,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Salvar resposta nos dados_respostas do atendimento
        if not atendimento.dados_respostas:
            atendimento.dados_respostas = {}
        atendimento.dados_respostas[str(questao_obj.indice)] = resposta_texto

        # Avancar para proxima questao
        proxima_questao, acao_especial, _ = questao_obj.get_proxima_questao_inteligente(
            resposta_texto
        )

        atendimento.questoes_respondidas += 1
        atendimento.tentativas_atual = 0

        response_data = {
            'success': True,
            'resposta': RespostaQuestaoOutputSerializer(resposta).data,
        }

        if acao_especial == 'finalizar_fluxo' or proxima_questao is None:
            atendimento.status = 'completado'
            atendimento.data_conclusao = timezone.now()
            if atendimento.data_inicio:
                delta = atendimento.data_conclusao - atendimento.data_inicio
                atendimento.tempo_total = int(delta.total_seconds())
            atendimento.save()
            response_data['fluxo_finalizado'] = True
            response_data['atendimento'] = AtendimentoFluxoOutputSerializer(atendimento).data
        else:
            atendimento.questao_atual = proxima_questao.indice
            atendimento.status = 'em_andamento'
            atendimento.save()
            response_data['proxima_questao'] = QuestaoFluxoOutputSerializer(proxima_questao).data
            response_data['fluxo_finalizado'] = False

        return Response(response_data, status=status.HTTP_200_OK)


# =====================================================================
# 7. AtendimentoFinalizarAPIView  — POST (finalizar manualmente)
# =====================================================================

class AtendimentoFinalizarAPIView(N8NAPIMixin, APIView):

    def post(self, request, pk=None):
        if pk is None:
            return Response(
                {'success': False, 'error': 'ID do atendimento e obrigatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            atendimento = AtendimentoFluxo.all_tenants.get(pk=pk)
        except AtendimentoFluxo.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Atendimento nao encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        motivo = request.data.get('motivo', 'finalizado_manualmente')
        atendimento.status = request.data.get('status', 'completado')
        atendimento.data_conclusao = timezone.now()
        if atendimento.data_inicio:
            delta = atendimento.data_conclusao - atendimento.data_inicio
            atendimento.tempo_total = int(delta.total_seconds())
        atendimento.observacoes = motivo
        atendimento.save()

        return Response(
            {
                'success': True,
                'atendimento': AtendimentoFluxoOutputSerializer(atendimento).data,
            },
            status=status.HTTP_200_OK,
        )


# =====================================================================
# 8. FluxoListAPIView  — GET (listar fluxos ativos)
# =====================================================================

class FluxoListAPIView(N8NAPIMixin, APIView):

    def get(self, request):
        fluxos = FluxoAtendimento.all_tenants.filter(
            status='ativo', ativo=True
        )
        return Response(
            {
                'success': True,
                'fluxos': FluxoAtendimentoOutputSerializer(fluxos, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


# =====================================================================
# 9. LeadBuscaAPIView  — GET (buscar lead por telefone)
# =====================================================================

class LeadBuscaAPIView(N8NAPIMixin, APIView):

    def get(self, request):
        telefone = request.query_params.get('telefone')
        if not telefone:
            return Response(
                {'success': False, 'error': 'Parametro telefone e obrigatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        leads = LeadProspecto.all_tenants.filter(telefone=telefone).order_by('-data_cadastro')
        if not leads.exists():
            return Response(
                {'success': True, 'encontrado': False, 'leads': []},
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                'success': True,
                'encontrado': True,
                'leads': LeadOutputSerializer(leads, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


# =====================================================================
# 10. CampanhaDeteccaoAPIView  — POST (detectar campanha em mensagem)
# =====================================================================

class CampanhaDeteccaoAPIView(N8NAPIMixin, APIView):

    def post(self, request):
        """
        Detecta campanha de trafego em mensagem de cliente.

        Payload esperado:
        {
            "telefone": "5589999999999",
            "mensagem": "Oi, vi o cupom50 no Instagram",
            "origem": "whatsapp"
        }
        """
        from apps.marketing.campanhas.models import CampanhaTrafego

        telefone = request.data.get('telefone')
        mensagem = request.data.get('mensagem')
        origem = request.data.get('origem', 'whatsapp')

        if not telefone or not mensagem:
            return Response(
                {'success': False, 'error': 'Telefone e mensagem sao obrigatorios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Normalizar mensagem para comparacao
        mensagem_normalizada = unicodedata.normalize('NFKD', mensagem.lower())
        mensagem_normalizada = mensagem_normalizada.encode('ASCII', 'ignore').decode('ASCII')

        campanhas_ativas = CampanhaTrafego.all_tenants.filter(ativa=True)

        melhor_score = 0
        melhor_campanha = None
        melhor_trecho = None

        for campanha in campanhas_ativas:
            if not campanha.esta_ativa:
                continue

            palavra = campanha.palavra_chave
            if not campanha.case_sensitive:
                palavra = palavra.lower()

            encontrado = False
            score = 0

            if campanha.tipo_match == 'exato':
                texto_busca = mensagem if campanha.case_sensitive else mensagem_normalizada
                if palavra in texto_busca:
                    encontrado = True
                    score = 100.0

            elif campanha.tipo_match == 'parcial':
                texto_busca = mensagem if campanha.case_sensitive else mensagem_normalizada
                if palavra in texto_busca:
                    encontrado = True
                    score = 80.0
                else:
                    # Similaridade basica
                    palavras_msg = texto_busca.split()
                    for p in palavras_msg:
                        if palavra in p or p in palavra:
                            encontrado = True
                            score = 60.0
                            break

            elif campanha.tipo_match == 'regex':
                try:
                    flags = 0 if campanha.case_sensitive else re.IGNORECASE
                    match = re.search(palavra, mensagem, flags)
                    if match:
                        encontrado = True
                        score = 90.0
                except re.error:
                    logger.warning(
                        'Regex invalida na campanha %s: %s',
                        campanha.id, palavra,
                    )

            if encontrado and score > melhor_score:
                melhor_score = score
                melhor_campanha = campanha
                melhor_trecho = palavra

        if not melhor_campanha:
            return Response(
                {
                    'success': True,
                    'campanha_detectada': None,
                    'score': 0,
                },
                status=status.HTTP_200_OK,
            )

        # Buscar ou criar lead
        lead = LeadProspecto.all_tenants.filter(
            telefone=telefone
        ).order_by('-data_cadastro').first()

        lead_criado = False
        if not lead:
            lead = LeadProspecto(
                nome_razaosocial=f'Lead {telefone}',
                telefone=telefone,
                origem=origem,
                status_api='pendente',
            )
            lead.save()
            lead_criado = True

        return Response(
            {
                'success': True,
                'campanha_detectada': {
                    'id': melhor_campanha.id,
                    'codigo': melhor_campanha.codigo,
                    'nome': melhor_campanha.nome,
                    'plataforma': melhor_campanha.plataforma,
                },
                'lead_id': lead.id,
                'score': melhor_score,
                'lead_criado': lead_criado,
                'trecho_detectado': melhor_trecho,
            },
            status=status.HTTP_200_OK,
        )
