"""
vendas_web/models.py — Re-exports

Este arquivo existia como God Object com 27 models e 5.349 linhas.
Agora os models vivem nos novos apps modulares.

Este arquivo re-exporta tudo para que imports existentes
(views, signals, admin, services) continuem funcionando sem alteração.

Migração em andamento — será removido quando todos os imports
forem atualizados para apontar diretamente aos novos apps.
"""

# ── Compatibilidade: monkey-patch do User (será removido com PerfilUsuario) ──
from django.db import models
from django.contrib.auth.models import User
User.add_to_class('telefone', models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefone"))

# ── Sistema (base) ────────────────────────────────────────────────────────────
from apps.sistema.models import (  # noqa: F401
    ConfiguracaoEmpresa,
    ConfiguracaoSistema,
    ConfiguracaoRecontato,
    StatusConfiguravel,
    LogSistema,
)

# ── Comercial > Leads ─────────────────────────────────────────────────────────
from apps.comercial.leads.models import (  # noqa: F401
    LeadProspecto,
    ImagemLeadProspecto,
    Prospecto,
    HistoricoContato,
)

# ── Comercial > Atendimento ───────────────────────────────────────────────────
from apps.comercial.atendimento.models import (  # noqa: F401
    FluxoAtendimento,
    QuestaoFluxo,
    TentativaResposta,
    AtendimentoFluxo,
    RespostaQuestao,
)

# ── Comercial > Cadastro ──────────────────────────────────────────────────────
from apps.comercial.cadastro.models import (  # noqa: F401
    ConfiguracaoCadastro,
    PlanoInternet,
    OpcaoVencimento,
    DocumentoLead,
    CadastroCliente,
)

# ── Comercial > Viabilidade ───────────────────────────────────────────────────
from apps.comercial.viabilidade.models import (  # noqa: F401
    CidadeViabilidade,
)

# ── Notificações ──────────────────────────────────────────────────────────────
from apps.notificacoes.models import (  # noqa: F401
    TipoNotificacao,
    CanalNotificacao,
    PreferenciaNotificacao,
    Notificacao,
    TemplateNotificacao,
)

# ── Marketing > Campanhas ─────────────────────────────────────────────────────
from apps.marketing.campanhas.models import (  # noqa: F401
    CampanhaTrafego,
    DeteccaoCampanha,
)
