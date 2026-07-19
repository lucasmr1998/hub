import logging

from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='vendas_web.LeadProspecto')
def _marcar_contrato_aceito_novo(sender, instance, **kwargs):
    """Marca se contrato_aceito acabou de virar True (para webhook Clube)."""
    if not instance.pk:
        instance._contrato_aceito_novo = bool(instance.contrato_aceito)
        return
    try:
        from vendas_web.models import LeadProspecto
        anterior = LeadProspecto.objects.filter(pk=instance.pk).values_list(
            'contrato_aceito', flat=True
        ).first()
        instance._contrato_aceito_novo = bool(instance.contrato_aceito) and not bool(anterior)
    except Exception:  # noqa: BLE001
        instance._contrato_aceito_novo = bool(instance.contrato_aceito)


@receiver(post_save, sender='vendas_web.LeadProspecto')
def notificar_clube_contrato_aceito(sender, instance, created, **kwargs):
    """Notifica o Clube quando o lead de indicação aceita o contrato."""
    if created or not instance.contrato_aceito:
        return
    if not getattr(instance, '_contrato_aceito_novo', False):
        return
    try:
        from integracoes.services.clube_indicacoes import notificar_clube_contrato_aceito_indicacao
        notificar_clube_contrato_aceito_indicacao(
            instance,
            data_contrato_aceito=getattr(instance, 'data_aceite_contrato', None),
        )
    except Exception as e:  # noqa: BLE001
        logger.warning('[CRM] Falha ao notificar Clube (contrato) lead %s: %s', instance.pk, e)


@receiver(post_save, sender='vendas_web.LeadProspecto')
def mover_indicacao_contrato_assinado(sender, instance, created, **kwargs):
    """Avança o card de indicação quando o lead aceita o contrato."""
    if created or not instance.contrato_aceito:
        return
    if not getattr(instance, '_contrato_aceito_novo', False):
        return
    canais = {(instance.origem or ''), (instance.canal_entrada or '')}
    if 'indicacao' in canais:
        try:
            from crm.services.indicacao_pipeline import sincronizar_indicacao_do_lead
            sincronizar_indicacao_do_lead(instance.pk)
        except Exception as e:  # noqa: BLE001
            logger.warning('[CRM] Falha ao mover indicação (contrato) lead %s: %s', instance.pk, e)
    if 'wifeed' in canais:
        try:
            from crm.services.wifeed_pipeline import sincronizar_wifeed_do_lead
            sincronizar_wifeed_do_lead(instance.pk)
        except Exception as e:  # noqa: BLE001
            logger.warning('[CRM] Falha ao mover wifeed (contrato) lead %s: %s', instance.pk, e)


# ============================================================================
# CRIAÇÃO AUTOMÁTICA DE OPORTUNIDADE (mantido)
# ============================================================================

@receiver(post_save, sender='vendas_web.LeadProspecto')
def criar_oportunidade_automatica(sender, instance, created, **kwargs):
    """
    Cria OportunidadeVenda automaticamente para todo lead.
    Após criar, dispara avaliação de regras para posicionar no estágio correto.
    """
    from crm.models import OportunidadeVenda, ConfiguracaoCRM

    # Evitar loop de signals
    if getattr(instance, '_skip_crm_signal', False):
        return
    if getattr(instance, '_skip_rules_evaluation', False):
        return

    # Lead de INDICAÇÃO (pipeline operado por pessoas): tem oportunidade própria
    # no funil de indicações e NÃO gera a de aquisição (não passa pela esteira
    # automática — o operador conduz manualmente).
    if getattr(instance, 'canal_entrada', None) == 'indicacao':
        _garantir_oportunidade_indicacao(instance)
        return

    # Lead do WIFEED (portal WiFi): mesmo processo da indicação, pipeline próprio.
    # Também tem oportunidade própria e NÃO gera a de aquisição.
    if getattr(instance, 'canal_entrada', None) == 'wifeed':
        _garantir_oportunidade_wifeed(instance)
        return

    # Oportunidade de AQUISIÇÃO (uma por lead). Pós-venda (novo serviço,
    # upgrade) tem oportunidades próprias, criadas pelos signals abaixo.
    if OportunidadeVenda.objects.filter(lead=instance, tipo='aquisicao').exists():
        _avaliar_regras_seguro(instance.pk)
        return

    try:
        config = ConfiguracaoCRM.get_config()
    except Exception:
        return

    if not config.criar_oportunidade_automatico:
        return

    if not config.estagio_inicial_padrao:
        return

    try:
        OportunidadeVenda.objects.create(
            lead=instance,
            tipo='aquisicao',
            estagio=config.estagio_inicial_padrao,
            valor_estimado=getattr(instance, 'valor', None),
            origem_crm='automatico',
            probabilidade=config.estagio_inicial_padrao.probabilidade_padrao,
        )
        logger.info(f"[CRM] OportunidadeVenda criada para LeadProspecto id={instance.pk}")

        # Avaliar regras para posicionar no estágio correto
        _avaliar_regras_seguro(instance.pk)

        # Notifica quem opera o funil de Aquisição (entrada no pipeline).
        if created:
            try:
                from vendas_web.notificacoes_service import notificar_por_capacidade
                notificar_por_capacidade(
                    'ver_pipeline_aquisicao', 'lead_novo', 'Novo lead no funil',
                    f'{instance.nome_razaosocial or "Lead"} entrou no funil de aquisição.',
                    contexto={'lead_id': instance.pk}, chave=f'lead_novo_{instance.pk}')
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:
        logger.error(f"[CRM] Erro ao criar OportunidadeVenda para lead {instance.pk}: {e}")


def _garantir_oportunidade_indicacao(lead):
    """Cria (uma vez) a oportunidade no funil de INDICAÇÕES, no 1º estágio.

    Sem avaliação de regras: o pipeline de indicação é movido à mão pelos
    operadores (converter em cliente, abrir atendimento/O.S., etc.).
    """
    from crm.models import OportunidadeVenda, PipelineEstagio

    if OportunidadeVenda.objects.filter(lead=lead, tipo='indicacao').exists():
        return
    estagio = (PipelineEstagio.objects
               .filter(pipeline_tipo='indicacao', ativo=True)
               .order_by('ordem').first())
    if not estagio:
        logger.warning('[CRM] Sem estágios de indicação — rode a migration/seed.')
        return
    try:
        opp = OportunidadeVenda.objects.create(
            lead=lead,
            tipo='indicacao',
            estagio=estagio,
            titulo=lead.nome_razaosocial or f'Indicação #{lead.pk}',
            valor_estimado=getattr(lead, 'valor', None),
            origem_crm='manual',
            probabilidade=estagio.probabilidade_padrao,
        )
        try:
            from crm.services.posvenda_sync import aplicar_tags_etapa
            aplicar_tags_etapa(opp, estagio.slug)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[CRM] Falha ao aplicar tags de indicação lead {lead.pk}: {e}")
        # Notifica os operadores do pipeline de Indicação (entrada no pipeline).
        try:
            from vendas_web.notificacoes_service import notificar_por_capacidade
            notificar_por_capacidade(
                'ver_pipeline_indicacao', 'indicacao_nova', 'Nova indicação recebida',
                f'{lead.nome_razaosocial or "Indicação"} entrou no pipeline de indicações'
                + (f' (indicado por {lead.id_indicador}).' if lead.id_indicador else '.'),
                contexto={'oportunidade_id': opp.id, 'url': f'/crm/oportunidades/{opp.id}/'},
                prioridade='alta', chave=f'ind_nova_{opp.id}')
        except Exception:  # noqa: BLE001
            pass
        logger.info(f"[CRM] Oportunidade de INDICAÇÃO criada para lead id={lead.pk}")
    except Exception as e:
        logger.error(f"[CRM] Erro ao criar oportunidade de indicação lead {lead.pk}: {e}")


def _garantir_oportunidade_wifeed(lead):
    """Cria (uma vez) a oportunidade no funil WIFEED, no 1º estágio.

    Sem avaliação de regras: mesmo processo da indicação, movido à mão pelos
    operadores (converter em cliente, abrir atendimento/O.S., etc.).
    """
    from crm.models import OportunidadeVenda, PipelineEstagio

    if OportunidadeVenda.objects.filter(lead=lead, tipo='wifeed').exists():
        return
    estagio = (PipelineEstagio.objects
               .filter(pipeline_tipo='wifeed', ativo=True)
               .order_by('ordem').first())
    if not estagio:
        logger.warning('[CRM] Sem estágios de wifeed — rode a migration/seed.')
        return
    try:
        opp = OportunidadeVenda.objects.create(
            lead=lead,
            tipo='wifeed',
            estagio=estagio,
            titulo=lead.nome_razaosocial or f'Wifeed #{lead.pk}',
            valor_estimado=getattr(lead, 'valor', None),
            origem_crm='automatico',
            probabilidade=estagio.probabilidade_padrao,
        )
        try:
            from crm.services.posvenda_sync import aplicar_tags_etapa
            aplicar_tags_etapa(opp, estagio.slug)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[CRM] Falha ao aplicar tags de wifeed lead {lead.pk}: {e}")
        try:
            from crm.services.wifeed_fontes import aplicar_tag_fonte
            aplicar_tag_fonte(opp, lead)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[CRM] Falha ao aplicar tag de fonte wifeed lead {lead.pk}: {e}")
        try:
            from vendas_web.notificacoes_service import notificar_por_capacidade
            notificar_por_capacidade(
                'ver_pipeline_wifeed', 'wifeed_novo', 'Novo lead Wifeed',
                f'{lead.nome_razaosocial or "Lead Wifeed"} entrou no pipeline Wifeed.',
                contexto={'oportunidade_id': opp.id, 'url': f'/crm/oportunidades/{opp.id}/'},
                prioridade='alta', chave=f'wf_novo_{opp.id}')
        except Exception:  # noqa: BLE001
            pass
        logger.info(f"[CRM] Oportunidade WIFEED criada para lead id={lead.pk}")
    except Exception as e:
        logger.error(f"[CRM] Erro ao criar oportunidade wifeed lead {lead.pk}: {e}")


# ============================================================================
# SIGNALS QUE DISPARAM AVALIAÇÃO DE REGRAS
# ============================================================================

@receiver(post_save, sender='vendas_web.HistoricoContato')
def avaliar_regras_apos_historico(sender, instance, created, **kwargs):
    """Quando um HistoricoContato é criado, avaliar regras do pipeline."""
    if not created:
        return
    lead = getattr(instance, 'lead', None)
    if not lead:
        return
    _avaliar_regras_seguro(lead.pk)


@receiver(post_save, sender='integracoes.ServicoClienteHubsoft')
def avaliar_regras_apos_servico(sender, instance, **kwargs):
    """Quando ServicoClienteHubsoft muda, avaliar regras do pipeline."""
    cliente = instance.cliente
    if not cliente or not cliente.lead_id:
        return
    _avaliar_regras_seguro(cliente.lead_id)

    try:
        from crm.services.indicacao_pipeline import sincronizar_indicacao_do_lead
        sincronizar_indicacao_do_lead(cliente.lead_id)
    except Exception as e:  # noqa: BLE001
        logger.warning('[CRM] Falha ao sincronizar indicação lead %s: %s', cliente.lead_id, e)

    try:
        from crm.services.wifeed_pipeline import sincronizar_wifeed_do_lead
        sincronizar_wifeed_do_lead(cliente.lead_id)
    except Exception as e:  # noqa: BLE001
        logger.warning('[CRM] Falha ao sincronizar wifeed lead %s: %s', cliente.lead_id, e)

    if instance.status_prefixo == 'servico_habilitado':
        try:
            from integracoes.services.clube_indicacoes import notificar_clube_habilitacao_indicacao
            notificar_clube_habilitacao_indicacao(
                cliente.lead,
                valor_venda=instance.valor,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning('[CRM] Falha ao notificar Clube (habilitação) lead %s: %s', cliente.lead_id, e)


# ============================================================================
# PÓS-VENDA — oportunidades próprias para Novo Serviço e Upgrade
# (transições via ORM. As do webdriver/polling, que rodam via SQL cru, são
#  capturadas pelo management command `crm_reconciliar_posvenda`.)
# ============================================================================

@receiver(post_save, sender='vendas_web.NewService')
def crm_sync_new_service(sender, instance, created, **kwargs):
    """Cria/move a oportunidade de Novo Serviço conforme o progresso."""
    try:
        from crm.services.posvenda_sync import sincronizar_new_service
        sincronizar_new_service(instance)
    except Exception as e:
        logger.error(f"[CRM] Erro ao sincronizar NewService {instance.pk}: {e}")


@receiver(post_save, sender='vendas_web.UpgradePlano')
def crm_sync_upgrade(sender, instance, created, **kwargs):
    """Cria/move a oportunidade de Upgrade conforme o progresso."""
    try:
        from crm.services.posvenda_sync import sincronizar_upgrade
        sincronizar_upgrade(instance)
    except Exception as e:
        logger.error(f"[CRM] Erro ao sincronizar UpgradePlano {instance.pk}: {e}")


@receiver(post_save, sender='integracoes.AgendamentoInstalacaoIA')
def sincronizar_indicacao_apos_agendamento(sender, instance, **kwargs):
    """Avança indicação para Atendimento/O.S. quando o agendamento conclui."""
    if instance.status != 'agendado':
        return
    try:
        from crm.services.indicacao_pipeline import sincronizar_indicacao_do_lead
        sincronizar_indicacao_do_lead(instance.lead_id)
    except Exception as e:  # noqa: BLE001
        logger.warning('[CRM] Falha ao sincronizar indicação após agendamento lead %s: %s',
                       instance.lead_id, e)
    try:
        from crm.services.wifeed_pipeline import sincronizar_wifeed_do_lead
        sincronizar_wifeed_do_lead(instance.lead_id)
    except Exception as e:  # noqa: BLE001
        logger.warning('[CRM] Falha ao sincronizar wifeed após agendamento lead %s: %s',
                       instance.lead_id, e)


def _conectar_signal_tags():
    """Conecta signal m2m_changed para tags da OportunidadeVenda."""
    from crm.models import OportunidadeVenda

    @receiver(m2m_changed, sender=OportunidadeVenda.tags.through)
    def avaliar_regras_apos_tag_change(sender, instance, action, **kwargs):
        """Quando tags são adicionadas/removidas, avaliar regras."""
        if action not in ('post_add', 'post_remove', 'post_clear'):
            return
        if getattr(instance, '_skip_rules_evaluation', False):
            return
        lead_id = getattr(instance, 'lead_id', None)
        if lead_id:
            _avaliar_regras_seguro(lead_id)


# Conectar ao importar o módulo
_conectar_signal_tags()


@receiver(post_save, sender='crm.OportunidadeVenda')
def tags_origem_canal_ao_criar(sender, instance, created, **kwargs):
    """TODA oportunidade nova recebe as tags de ORIGEM e CANAL DE ENTRADA do
    lead ('Origem: WhatsApp', 'Canal: Indicação'). Signal no post_save da
    própria oportunidade → cobre todos os caminhos de criação (aquisição,
    indicação manual, novo serviço, upgrade, atendimento)."""
    if not created:
        return
    aplicar_tags_origem_canal(instance)


# Contas do MATRIX (cod → título) — usadas para traduzir origem/canal tipo
# "conta 4" para o TÍTULO da conta na tag do CRM ("Megalink Vendas 0067").
# Fonte: cadastro de contas do Matrix. Ao criar conta nova lá, adicionar aqui.
CONTAS_MATRIX = {
    1:  '89 22210171 Megalink Empresas',
    2:  'MegalinkAtendimento 0068',
    3:  '0800BJFibra',
    4:  'Megalink Vendas 0067',
    5:  '86 9447-4769',
    6:  'Atendimento Frota24',
    7:  'NOC FTTH - 863114-0010',
    12: 'Conta Teste 0011',
    13: 'Atendimento B2B',
    14: 'Provedor Max Web',
}

_RE_CONTA = None  # compilado sob demanda


def _traduzir_conta(valor: str) -> str | None:
    """'conta 4' / 'conta_4' / 'Conta 12' → título da conta Matrix (ou None)."""
    global _RE_CONTA
    import re as _re
    if _RE_CONTA is None:
        _RE_CONTA = _re.compile(r'^conta[_\s]*(\d+)$', _re.I)
    m = _RE_CONTA.match((valor or '').strip())
    if not m:
        return None
    return CONTAS_MATRIX.get(int(m.group(1)))


def aplicar_tags_origem_canal(opp):
    """Aplica as tags 'Origem: X' e 'Canal: Y' do lead na oportunidade.
    Idempotente (get_or_create + M2M add). Rótulo: título da conta Matrix
    quando o valor é 'conta N'; senão o display dos choices do lead; senão
    Title Case."""
    try:
        from crm.models import TagCRM
        lead = getattr(opp, 'lead', None)
        if not lead:
            return
        rotulos = dict(type(lead)._meta.get_field('origem').choices or [])
        rotulos.update(dict(type(lead)._meta.get_field('canal_entrada').choices or []))
        pares = []
        if (lead.origem or '').strip():
            pares.append(('Origem', lead.origem.strip(), '#0891b2'))
        if (lead.canal_entrada or '').strip():
            pares.append(('Canal', lead.canal_entrada.strip(), '#d97706'))
        for prefixo, valor, cor in pares:
            rotulo = (_traduzir_conta(valor)
                      or rotulos.get(valor)
                      or valor.replace('_', ' ').title())
            nome = f'{prefixo}: {rotulo}'[:50]
            tag, _ = TagCRM.objects.get_or_create(nome=nome, defaults={'cor_hex': cor})
            opp.tags.add(tag)
    except Exception as e:
        logger.error(f"[CRM] Erro ao aplicar tags de origem/canal na opp {getattr(opp, 'pk', '?')}: {e}")


# ============================================================================
# HELPERS
# ============================================================================

def _atualizar_tags_lead(lead):
    """Atualiza tags Comercial/Documental/Endereço com base nos dados do lead."""
    try:
        from crm.models import OportunidadeVenda, TagCRM

        opp = OportunidadeVenda.objects.filter(lead=lead, tipo='aquisicao', ativo=True).first()
        if not opp:
            return

        def preenchido(v):
            return v is not None and str(v).strip() != ''

        TAG_DEFS = {
            'Comercial': (lead.id_plano_rp is not None or lead.id_dia_vencimento is not None),
            'Endereço': (preenchido(lead.rua) and preenchido(lead.numero_residencia) and preenchido(lead.bairro) and preenchido(lead.cep)),
            'Documental': (preenchido(lead.cpf_cnpj) or lead.documentacao_completa or lead.documentacao_validada),
        }

        CORES = {'Comercial': '#667eea', 'Endereço': '#f39c12', 'Documental': '#0ea5e9'}

        for nome_tag, deve_ter in TAG_DEFS.items():
            tag_obj, _ = TagCRM.objects.get_or_create(nome=nome_tag, defaults={'cor_hex': CORES.get(nome_tag, '#667eea')})
            tem = opp.tags.filter(pk=tag_obj.pk).exists()
            if deve_ter and not tem:
                opp.tags.add(tag_obj)
            elif not deve_ter and tem:
                opp.tags.remove(tag_obj)

    except Exception as e:
        logger.error(f"[CRM] Erro ao atualizar tags para lead {lead.pk}: {e}")


def _avaliar_regras_seguro(lead_id):
    """Wrapper seguro para avaliação de regras."""
    try:
        from crm.services.regras_engine import processar_lead
        processar_lead(lead_id)
    except Exception as e:
        logger.error(f"[CRM Engine] Erro ao avaliar regras para lead {lead_id}: {e}")
