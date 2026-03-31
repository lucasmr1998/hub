from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.comercial.cadastro.models import (
    ConfiguracaoCadastro,
    PlanoInternet,
    OpcaoVencimento,
)
from apps.comercial.viabilidade.models import CidadeViabilidade
from apps.marketing.campanhas.models import CampanhaTrafego
from apps.notificacoes.models import (
    TipoNotificacao,
    CanalNotificacao,
    TemplateNotificacao,
)

from .serializers_panel import (
    ConfiguracaoCadastroSerializer,
    PlanoInternetSerializer,
    OpcaoVencimentoSerializer,
    CidadeViabilidadeSerializer,
    CampanhaTrafegoSerializer,
    TipoNotificacaoSerializer,
    CanalNotificacaoSerializer,
    TemplateNotificacaoSerializer,
)


# ============================================================================
# COMERCIAL — CADASTRO
# ============================================================================

class PlanoInternetViewSet(ModelViewSet):
    """CRUD de planos de internet."""
    serializer_class = PlanoInternetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PlanoInternet.objects.all()  # TenantManager handles filtering


class OpcaoVencimentoViewSet(ModelViewSet):
    """CRUD de opcoes de vencimento de fatura."""
    serializer_class = OpcaoVencimentoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return OpcaoVencimento.objects.all()


class ConfiguracaoCadastroViewSet(ModelViewSet):
    """CRUD de configuracoes da pagina de cadastro."""
    serializer_class = ConfiguracaoCadastroSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ConfiguracaoCadastro.objects.all()


# ============================================================================
# COMERCIAL — VIABILIDADE
# ============================================================================

class CidadeViabilidadeViewSet(ModelViewSet):
    """CRUD de cidades com viabilidade tecnica."""
    serializer_class = CidadeViabilidadeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CidadeViabilidade.objects.all()


# ============================================================================
# MARKETING — CAMPANHAS
# ============================================================================

class CampanhaTrafegoViewSet(ModelViewSet):
    """CRUD de campanhas de trafego pago."""
    serializer_class = CampanhaTrafegoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CampanhaTrafego.objects.all()


# ============================================================================
# NOTIFICACOES
# ============================================================================

class TipoNotificacaoViewSet(ReadOnlyModelViewSet):
    """Listagem (read-only) de tipos de notificacao."""
    serializer_class = TipoNotificacaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TipoNotificacao.objects.all()


class CanalNotificacaoViewSet(ReadOnlyModelViewSet):
    """Listagem de canais de notificacao com acao para alternar ativo/inativo."""
    serializer_class = CanalNotificacaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CanalNotificacao.objects.all()

    @action(detail=True, methods=['post'], url_path='toggle-ativo')
    def toggle_ativo(self, request, pk=None):
        """Alterna o estado ativo/inativo de um canal de notificacao."""
        canal = self.get_object()
        canal.ativo = not canal.ativo
        canal.save(update_fields=['ativo'])
        serializer = self.get_serializer(canal)
        return Response(serializer.data)


class TemplateNotificacaoViewSet(ModelViewSet):
    """CRUD de templates de notificacao."""
    serializer_class = TemplateNotificacaoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TemplateNotificacao.objects.select_related(
            'tipo_notificacao', 'canal'
        ).all()
