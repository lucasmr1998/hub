"""Registry de varreduras — o que o gatilho `agenda` busca a cada rodada.

Espelha `opcoes.py`: cada varredura é uma função `fn(tenant, config) -> list[dict]`.
Cada dict do resultado é um "achado" e vira UMA execução do fluxo — traz pelo menos
uma entidade reconhecida por `gatilhos._contexto_do_evento` (`oportunidade`/`lead`;
mesmo contrato do contexto de evento), o resto são escalares que entram em `var.*`.

Tudo BLINDADO: uma varredura que falha devolve lista vazia/parcial + loga, nunca
levanta pra fora. É a primeira linha de defesa porque cada função fala com banco
ou API externa (o dispatcher em `gatilhos.py` também embrulha por cima).

Adicionar uma varredura = uma função + entrada em `VARREDURAS` (+ label em
`_LABELS`, usado por `opcoes_varreduras`).
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def _verdadeiro(valor):
    """Aceita bool Python OU string ('true'/'1'/'sim', case insensitive) como
    verdadeiro — config de fluxo sempre chega como string vinda do editor."""
    return str(valor).strip().lower() in ('true', '1', 'sim')


def _oportunidades_perdidas(tenant, config):
    """Oportunidades perdidas há pelo menos `janela_dias_min` dias (default 30).

    Filtros opcionais na `config`:
    - `motivo_categoria`: categoria legada do motivo de perda (`motivo_perda_categoria`).
    - `motivo_ref_id`: id do `MotivoPerda` (`motivo_perda_ref_id`).
    - `motivo_ref_nome`: nome do `MotivoPerda` (case insensitive). Preferível a
      `motivo_ref_id` em config portável entre tenants/ambientes (o id varia; o
      nome é o mesmo).
    - `pipeline`: slug do pipeline (`OportunidadeVenda.pipeline`).
    - `sem_marcador`: só entram oportunidades SEM essa chave em `dados_custom`
      (freio manual: o fluxo marca a op depois de processar, pra não repetir).
    - `exige_responsavel`: aceita True/'true'/'1'/'sim'. Quando ligado, só entram
      oportunidades COM `responsavel` definido — sem isso a tarefa criada pelo
      fluxo nasceria órfã (sem vendedora dona pra executar).
    - `sem_contato_dias`: int. Quando > 0, EXCLUI oportunidades cujo lead teve
      um `HistoricoContato` registrado nos últimos N dias (não insistir em
      "retomar contato" com quem a vendedora acabou de falar).

    Cada item devolvido também traz `motivo_perda_nome` (nome do `MotivoPerda`
    da op, string vazia se não tiver) — pronto pra usar no texto do fluxo.
    """
    from apps.comercial.crm.models import OportunidadeVenda

    try:
        janela_dias = int(config.get('janela_dias_min') or 30)
    except (TypeError, ValueError):
        janela_dias = 30
    corte = timezone.now() - timedelta(days=janela_dias)

    qs = OportunidadeVenda.all_tenants.filter(
        tenant=tenant, ativo=True,
        estagio__is_final_perdido=True,
        data_fechamento_real__isnull=False,
        data_fechamento_real__lte=corte,
    )

    motivo_categoria = (config.get('motivo_categoria') or '').strip()
    if motivo_categoria:
        qs = qs.filter(motivo_perda_categoria=motivo_categoria)

    motivo_ref_id = config.get('motivo_ref_id')
    if motivo_ref_id not in (None, ''):
        try:
            qs = qs.filter(motivo_perda_ref_id=int(motivo_ref_id))
        except (TypeError, ValueError):
            pass

    motivo_ref_nome = (config.get('motivo_ref_nome') or '').strip()
    if motivo_ref_nome:
        qs = qs.filter(motivo_perda_ref__nome__iexact=motivo_ref_nome)

    pipeline_slug = (config.get('pipeline') or '').strip()
    if pipeline_slug:
        qs = qs.filter(pipeline__slug=pipeline_slug)

    sem_marcador = (config.get('sem_marcador') or '').strip()
    if sem_marcador:
        qs = qs.exclude(dados_custom__has_key=sem_marcador)

    if _verdadeiro(config.get('exige_responsavel')):
        qs = qs.filter(responsavel__isnull=False)

    try:
        sem_contato_dias = int(config.get('sem_contato_dias') or 0)
    except (TypeError, ValueError):
        sem_contato_dias = 0
    if sem_contato_dias > 0:
        corte_contato = timezone.now() - timedelta(days=sem_contato_dias)
        qs = qs.exclude(
            lead__historico_contatos__data_hora_contato__gte=corte_contato,
        ).distinct()

    qs = qs.select_related('lead', 'pipeline', 'motivo_perda_ref').order_by('data_fechamento_real')[:1000]

    agora = timezone.now()
    out = []
    for op in qs:
        out.append({
            'oportunidade': op,
            'lead': op.lead,
            'dias_perdida': (agora - op.data_fechamento_real).days,
            'motivo_perda_nome': op.motivo_perda_ref.nome if op.motivo_perda_ref_id else '',
        })
    return out


def _atendimentos_matrix_finalizados(tenant, config):
    """Atendimentos Matrix finalizados nos últimos `janela_dias` (default 2) ainda
    sem análise.

    Casa cada linha da listagem analítica (`/rest/v1/relAtAnalitico`) pela
    oportunidade que guardou o id do atendimento em
    `dados_custom['id_atendimento_matrix']`, pulando quem já tem o `marcador`
    (default `analise_atendimento_matrix`) em `dados_custom` — evita repetir o
    mesmo atendimento em rodadas seguintes.

    Nomes de campo da linha seguem `extrair_historico_matrix` (mesmo endpoint):
    `id_atendimento`, `status`, `agente` (não há `id_agente` na listagem
    analítica — isso só existe no detalhe de `consultar_atendimento`).
    """
    from .services.matrix import matrix_do_tenant
    from apps.comercial.crm.models import OportunidadeVenda

    cliente = matrix_do_tenant(tenant)
    if cliente is None:
        return []

    try:
        janela_dias = int(config.get('janela_dias') or 2)
    except (TypeError, ValueError):
        janela_dias = 2
    # Marcadores da engine nascem com `_` na frente: é a convenção que o painel de
    # campos personalizados do CRM usa pra ocultar bookkeeping interno do usuário.
    marcador = (config.get('marcador') or '').strip() or '_analise_atendimento_matrix'
    servico_nome = (config.get('servico_nome') or '').strip() or None

    hoje = timezone.now().date()
    data_inicial = (hoje - timedelta(days=janela_dias)).strftime('%Y-%m-%d')
    data_final = hoje.strftime('%Y-%m-%d')

    linhas = []
    try:
        page = 1
        while page <= 20:  # teto de páginas por rodada — corta cedo se a Matrix cair
            resp = cliente.listar_atendimentos_analitico(
                data_inicial=data_inicial, data_final=data_final,
                servico_nome=servico_nome, page=page, limit=300,
            )
            if isinstance(resp, dict):
                rows = resp.get('rows') or []
                total = int(resp.get('records') or 0)
            elif isinstance(resp, list):
                rows = resp
                total = len(rows)
            else:
                rows = []
                total = 0
            linhas.extend(rows)
            if not rows or len(linhas) >= total:
                break
            page += 1
    except Exception:
        logger.exception(
            'varreduras: falha ao listar atendimentos Matrix (tenant=%s)', tenant.pk,
        )
        # segue com o que já foi acumulado (lista parcial, nunca levanta)

    out = []
    for linha in linhas:
        try:
            if not isinstance(linha, dict):
                continue
            status = str(linha.get('status') or '')
            if 'finalizado' not in status.lower():
                continue
            if not str(linha.get('agente') or '').strip():
                continue
            codigo = linha.get('id_atendimento')
            if not codigo:
                continue
            op = (
                OportunidadeVenda.all_tenants
                .filter(tenant=tenant, dados_custom__id_atendimento_matrix=str(codigo))
                .exclude(dados_custom__has_key=marcador)
                .select_related('lead')
                .first()
            )
            if op is None:
                continue
            out.append({'oportunidade': op, 'lead': op.lead, 'id_atendimento_matrix': str(codigo)})
        except Exception:
            logger.exception(
                'varreduras: falha ao processar linha de atendimento Matrix (tenant=%s)', tenant.pk,
            )
            continue
    return out


def _oportunidades_paradas(tenant, config):
    """Oportunidades vivas (estágio não final) paradas no estágio atual além do
    SLA por etapa (`PipelineEstagio.sla_horas`).

    Filtros/config opcionais:
    - `apenas_com_sla`: aceita True/'true'/'1'/'sim' (default TRUE). Quando
      ligado, só entram oportunidades cujo estágio TEM `sla_horas` preenchido
      (o valor da etapa é sempre quem manda quando existe). Estágio sem SLA
      próprio fica de fora até alguém preencher no CRM.
    - `sla_horas_padrao`: int opcional. Usado como SLA de FALLBACK pros
      estágios sem `sla_horas` quando `apenas_com_sla` está DESLIGADO.
      Estágio sem `sla_horas` e sem esse padrão fica de fora (sem limite não
      dá pra saber se "está parado demais").
    - `exige_responsavel`: aceita True/'true'/'1'/'sim' (default TRUE). Só
      entram oportunidades COM `responsavel` definido — sem isso a tarefa de
      follow-up nasceria órfã (sem vendedora dona pra executar).
    - `estagios`: CSV de slugs de `PipelineEstagio`. Quando informado,
      restringe a varredura a esses estágios; vazio = todos os não finais.
    - `max_ordem`: int opcional. Quando informado, só considera estágios com
      `ordem <= max_ordem` (ex: só as primeiras N colunas do funil).

    `cooldown_horas` NÃO é filtro desta função — é o freio padrão do
    dispatcher (`gatilhos._freio_bloqueia`), configurado no nó `agenda` do
    fluxo que consome esta varredura (evita recriar a mesma tarefa pro mesmo
    lead dentro da janela de cooldown). Por isso todo item devolvido aqui
    sempre traz `lead` — é nele que o freio ancora.

    Cada item devolvido traz `horas_paradas` (int, arredondado pra baixo),
    `estagio_nome`, `estagio_atual` (slug) e `sla_horas` (int, o limite que
    valeu pra aquela oportunidade: o da própria etapa ou o padrão).
    """
    from apps.comercial.crm.models import OportunidadeVenda

    try:
        qs = (
            OportunidadeVenda.all_tenants
            .filter(tenant=tenant, ativo=True)
            .exclude(estagio__is_final_perdido=True)
            .exclude(estagio__is_final_ganho=True)
            .select_related('estagio', 'lead', 'responsavel', 'pipeline')
        )

        if _verdadeiro(config.get('exige_responsavel', True)):
            qs = qs.filter(responsavel__isnull=False)

        estagios_csv = (config.get('estagios') or '').strip()
        if estagios_csv:
            slugs = [s.strip() for s in estagios_csv.split(',') if s.strip()]
            if slugs:
                qs = qs.filter(estagio__slug__in=slugs)

        max_ordem = config.get('max_ordem')
        if max_ordem not in (None, ''):
            try:
                qs = qs.filter(estagio__ordem__lte=int(max_ordem))
            except (TypeError, ValueError):
                pass

        apenas_com_sla = _verdadeiro(config.get('apenas_com_sla', True))
        sla_padrao = None
        if not apenas_com_sla:
            try:
                sla_padrao = int(config.get('sla_horas_padrao') or 0) or None
            except (TypeError, ValueError):
                sla_padrao = None

        # mais parado primeiro (data_entrada_estagio mais antiga primeiro); cap
        # defensivo pra rodada não crescer sem limite num tenant com funil grande.
        qs = qs.order_by('data_entrada_estagio')[:2000]
    except Exception:
        logger.exception(
            'varreduras: falha ao montar query de oportunidades paradas (tenant=%s)', tenant.pk,
        )
        return []

    agora = timezone.now()
    out = []
    for op in qs:
        try:
            sla = op.estagio.sla_horas or (sla_padrao if not apenas_com_sla else None)
            if not sla:
                continue
            horas_paradas = (agora - op.data_entrada_estagio).total_seconds() / 3600
            if horas_paradas < sla:
                continue
            out.append({
                'oportunidade': op,
                'lead': op.lead,
                'horas_paradas': int(horas_paradas),
                'estagio_nome': op.estagio.nome,
                'estagio_atual': op.estagio.slug,
                'sla_horas': int(sla),
            })
        except Exception:
            logger.exception(
                'varreduras: falha ao processar oportunidade parada pk=%s (tenant=%s)',
                getattr(op, 'pk', None), tenant.pk,
            )
            continue
    return out


def _prospectos_por_criterio(tenant, config):
    """Prospectos (leads) que casam com um critério, pra rotinas de escrita no
    HubSoft (conversão, novo serviço, upgrade). É o "start por vendedor OU por
    status" que essas rotinas pedem.

    Filtros da `config` (tudo chega como string do editor):
    - `vendedor_id`: id do vendedor no HubSoft (`id_vendedor_rp`). É o
      "todos os prospectos do vendedor X".
    - `status_api`: um status (`status_api=`) ou vários separados por vírgula
      (`status_api__in`).
    - `com_id_hubsoft`: quando ligado, só entram leads com `id_hubsoft` preenchido
      (pré-requisito da conversão: o prospecto precisa existir no HubSoft).
    - `exige_vendedor`: quando ligado, só entram leads com `id_vendedor_rp` definido.
    - `sem_marcador`: exclui leads que já têm essa chave em `dados_custom` (freio de
      idempotência: o fluxo marca o lead depois de processar, pra não repetir).
    - `limite`: teto de itens por rodada (default 200).

    Cada item traz o `lead` (entidade reconhecida por `gatilhos._contexto_do_evento`)
    + escalares úteis no texto do fluxo.
    """
    from apps.comercial.leads.models import LeadProspecto

    qs = LeadProspecto.all_tenants.filter(tenant=tenant, ativo=True)

    vendedor_id = (config.get('vendedor_id') or '').strip()
    if vendedor_id:
        try:
            qs = qs.filter(id_vendedor_rp=int(vendedor_id))
        except (TypeError, ValueError):
            pass

    status_api = (config.get('status_api') or '').strip()
    if status_api:
        valores = [s.strip() for s in status_api.split(',') if s.strip()]
        qs = qs.filter(status_api__in=valores) if len(valores) > 1 else qs.filter(status_api=valores[0])

    if _verdadeiro(config.get('com_id_hubsoft')):
        qs = qs.exclude(id_hubsoft__isnull=True).exclude(id_hubsoft='')

    if _verdadeiro(config.get('exige_vendedor')):
        qs = qs.filter(id_vendedor_rp__isnull=False)

    sem_marcador = (config.get('sem_marcador') or '').strip()
    if sem_marcador:
        qs = qs.exclude(dados_custom__has_key=sem_marcador)

    try:
        limite = int(config.get('limite') or 200)
    except (TypeError, ValueError):
        limite = 200
    limite = max(1, min(limite, 2000))

    qs = qs.order_by('id')[:limite]

    out = []
    for lead in qs:
        out.append({
            'lead': lead,
            'status_api': lead.status_api,
            'id_vendedor_rp': lead.id_vendedor_rp,
            'id_hubsoft': lead.id_hubsoft or '',
        })
    return out


VARREDURAS = {
    'oportunidades_perdidas': _oportunidades_perdidas,
    'atendimentos_matrix_finalizados': _atendimentos_matrix_finalizados,
    'oportunidades_paradas': _oportunidades_paradas,
    'prospectos_por_criterio': _prospectos_por_criterio,
}

_LABELS = {
    'oportunidades_perdidas': 'Oportunidades perdidas (win/loss)',
    'atendimentos_matrix_finalizados': 'Atendimentos Matrix finalizados (sem análise)',
    'oportunidades_paradas': 'Oportunidades paradas no estágio (SLA)',
    'prospectos_por_criterio': 'Prospectos por critério (vendedor/status)',
}


def opcoes_varreduras(tenant=None):
    """Opções pro dropdown do campo `varredura` do nó `agenda`.

    `tenant` não filtra (o catálogo de varreduras é global, não por tenant) —
    o parâmetro só existe pra seguir a assinatura padrão das fontes de opções
    (`opcoes.py:opcoes_de`, que sempre chama `fn(tenant)`).
    """
    return [{'value': k, 'label': _LABELS.get(k, k)} for k in VARREDURAS]
