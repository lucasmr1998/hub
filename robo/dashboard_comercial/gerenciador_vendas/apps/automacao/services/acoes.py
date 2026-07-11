"""
Executores de domínio compartilhados pela engine de automação.

São a **fonte única** de cada ação: o nó da engine nova chama daqui e, na
convergência, o `_acao_*` do motor de marketing passa a delegar pra cá também —
em vez de manter uma 2ª/3ª cópia da lógica.

Contrato: recebem parâmetros **já resolvidos** (templates interpolados pelo
chamador) + `tenant` explícito + as entidades (`lead`/`oportunidade`) como
objetos. Nunca tocam em `request`/thread-local (a engine roda em cron/signal).
"""
from datetime import timedelta

from django.utils import timezone


def criar_tarefa(tenant, *, titulo, tipo='followup', prioridade='normal',
                 lead=None, oportunidade=None, responsavel=None, prazo_dias=1):
    """Cria uma `TarefaCRM`. Se `responsavel` não vier, resolve um default
    (lead.responsavel → staff do tenant → superuser). Devolve a TarefaCRM.

    Levanta `ValueError` se não houver nenhum responsável possível (o campo é
    obrigatório no model).
    """
    from django.contrib.auth.models import User
    from apps.comercial.crm.models import TarefaCRM
    from apps.sistema.models import PerfilUsuario

    if responsavel is None and lead is not None:
        responsavel = getattr(lead, 'responsavel', None)
    if responsavel is None:
        perfil = PerfilUsuario.objects.filter(tenant=tenant, user__is_staff=True).first()
        responsavel = perfil.user if perfil else User.objects.filter(is_superuser=True).first()
    if responsavel is None:
        raise ValueError('Nenhum responsável disponível para a tarefa.')

    tarefa = TarefaCRM(
        tenant=tenant,
        titulo=titulo,
        tipo=tipo or 'followup',
        prioridade=prioridade or 'normal',
        status='pendente',
        lead=lead if (lead is not None and getattr(lead, 'pk', None)) else None,
        oportunidade=oportunidade if (oportunidade is not None and getattr(oportunidade, 'pk', None)) else None,
        responsavel=responsavel,
        data_vencimento=timezone.now() + timedelta(days=prazo_dias or 1),
    )
    tarefa.save()
    return tarefa


def notificar(tenant, *, titulo, mensagem, codigo_tipo='sistema_geral'):
    """Cria uma notificação **broadcast** (a equipe inteira do tenant vê).

    Reusa o service de domínio `apps.notificacoes.services.criar_notificacao`.
    Devolve a Notificacao, ou `None` se o tipo não estiver cadastrado pro tenant
    (nesse caso o chamador trata — ex: rodar `seedar_notificacoes`).
    """
    from apps.notificacoes.services import criar_notificacao
    return criar_notificacao(
        tenant=tenant, codigo_tipo=codigo_tipo,
        titulo=titulo, mensagem=mensagem, destinatario=None,
    )


def mover_estagio(tenant, *, oportunidade, estagio_slug):
    """Move a `oportunidade` pro estágio (slug) dentro do pipeline dela. Devolve o estágio."""
    from apps.comercial.crm.models import PipelineEstagio
    if oportunidade is None:
        raise ValueError('Sem oportunidade para mover.')
    if not (estagio_slug or '').strip():
        raise ValueError('Estágio não especificado.')
    estagio = PipelineEstagio.all_tenants.filter(
        tenant=tenant, pipeline=oportunidade.pipeline, slug=estagio_slug.strip(),
    ).first()
    if estagio is None:
        raise ValueError(f'Estágio "{estagio_slug}" não encontrado no pipeline.')
    oportunidade.estagio = estagio
    oportunidade.save(update_fields=['estagio'])
    return estagio


def criar_oportunidade(tenant, *, lead, titulo=None, pipeline_slug='', estagio_slug=''):
    """Cria uma OportunidadeVenda pro lead. Idempotente (não duplica). Devolve (oport, criada)."""
    from apps.comercial.crm.models import OportunidadeVenda, Pipeline, PipelineEstagio
    if lead is None or not getattr(lead, 'pk', None):
        raise ValueError('Lead não encontrado.')

    existente = OportunidadeVenda.all_tenants.filter(tenant=tenant, lead=lead).first()
    if existente:
        return existente, False

    pipeline = None
    if (pipeline_slug or '').strip():
        pipeline = Pipeline.all_tenants.filter(tenant=tenant, slug=pipeline_slug.strip()).first()
    if pipeline is None:
        pipeline = (Pipeline.all_tenants.filter(tenant=tenant, padrao=True).first()
                    or Pipeline.all_tenants.filter(tenant=tenant).first())
    if pipeline is None:
        raise ValueError('Nenhum pipeline encontrado pro tenant.')

    estagio = None
    if (estagio_slug or '').strip():
        estagio = PipelineEstagio.all_tenants.filter(
            tenant=tenant, pipeline=pipeline, slug=estagio_slug.strip()).first()
    if estagio is None:
        estagio = PipelineEstagio.all_tenants.filter(
            tenant=tenant, pipeline=pipeline).order_by('ordem').first()
    if estagio is None:
        raise ValueError('Nenhum estágio encontrado no pipeline.')

    oport = OportunidadeVenda(
        tenant=tenant, lead=lead, pipeline=pipeline, estagio=estagio,
        titulo=(titulo or '').strip() or getattr(lead, 'nome', '') or 'Oportunidade',
        valor_estimado=getattr(lead, 'valor', None),
        origem_crm='automatico',
    )
    oport.save()
    return oport, True


def criar_venda(tenant, *, lead):
    """Cria uma Venda pendente-ERP pro lead. Idempotente. Devolve (venda, criada)."""
    from apps.comercial.crm.models import OportunidadeVenda, Venda
    if lead is None or not getattr(lead, 'pk', None):
        raise ValueError('Lead não encontrado.')

    existente = Venda.all_tenants.filter(tenant=tenant, lead=lead).first()
    if existente:
        return existente, False

    oport = OportunidadeVenda.all_tenants.filter(tenant=tenant, lead=lead).first()
    venda = Venda(
        tenant=tenant, lead=lead, oportunidade=oport,
        plano=oport.plano_interesse if oport else None,
        valor=oport.valor_estimado if oport else None,
        status=Venda.STATUS_PENDENTE_ERP,
    )
    venda.save()
    return venda, True


def dar_pontos(tenant, *, cpf, pontos, motivo=''):
    """Soma `pontos` ao saldo do MembroClube com aquele CPF (do tenant). Devolve o membro."""
    from apps.cs.clube.models import MembroClube
    cpf_limpo = (cpf or '').replace('.', '').replace('-', '').replace('/', '').strip()[:14]
    if not cpf_limpo:
        raise ValueError('CPF não informado.')
    membro = MembroClube.all_tenants.filter(tenant=tenant, cpf=cpf_limpo).first()
    if membro is None:
        raise ValueError(f'Membro do clube não encontrado para o CPF {cpf}.')
    membro.saldo = (membro.saldo or 0) + int(pontos)
    membro.save(update_fields=['saldo'])
    return membro


def atribuir_responsavel(tenant, *, oportunidade=None, lead=None, modo='round-robin', username=''):
    """Atribui responsável à oportunidade. `modo`='round-robin' (menos carregado) ou
    'fixo' (username). Devolve o User atribuído."""
    from django.contrib.auth.models import User
    from apps.comercial.crm.models import OportunidadeVenda
    from apps.sistema.models import PerfilUsuario

    if oportunidade is None and lead is not None and getattr(lead, 'pk', None):
        oportunidade = OportunidadeVenda.all_tenants.filter(tenant=tenant, lead=lead).first()
    if oportunidade is None:
        raise ValueError('Sem oportunidade para atribuir.')

    if modo == 'fixo':
        responsavel = (User.objects.filter(
            is_staff=True, username__icontains=(username or '').strip()).first()
            if (username or '').strip() else None)
        if responsavel is None:
            raise ValueError(f'Responsável não encontrado: {username}')
    else:
        perfis = PerfilUsuario.objects.filter(
            tenant=tenant, user__is_staff=True, user__is_active=True).select_related('user')
        if not perfis.exists():
            raise ValueError('Nenhum agente disponível para round-robin.')
        counts = {
            p.user_id: OportunidadeVenda.all_tenants.filter(
                tenant=tenant, responsavel=p.user, ativo=True).count()
            for p in perfis
        }
        responsavel = User.objects.get(pk=min(counts, key=counts.get))

    oportunidade.responsavel = responsavel
    oportunidade.save(update_fields=['responsavel'])
    return responsavel


def mover_para_perdido_sem_viabilidade(tenant, *, oportunidade, motivo_template=''):
    """Move a `oportunidade` pro estágio `is_final_perdido` do pipeline dela e preenche
    `motivo_perda` (categoria 'viabilidade'), registrando o HistoricoPipelineEstagio.
    Idempotente (não move se já está em perdido). Devolve `(estagio_perdido, movido: bool)`.

    `motivo_template` aceita placeholders {cep}/{cidade}/{uf} (do lead.dados_custom['viabilidade']);
    vazio usa o padrão. Portado de `crm.services.automacao_pipeline._acao_mover_para_perdido_sem_viabilidade`
    (motor novo autossuficiente — não importa do antigo)."""
    from apps.comercial.crm.models import PipelineEstagio, HistoricoPipelineEstagio
    if oportunidade is None:
        raise ValueError('Sem oportunidade para mover.')
    if oportunidade.estagio and oportunidade.estagio.is_final_perdido:
        return oportunidade.estagio, False  # já perdido

    estagio_perdido = PipelineEstagio.all_tenants.filter(
        tenant=tenant, pipeline=oportunidade.pipeline, is_final_perdido=True, ativo=True,
    ).order_by('ordem').first()
    if estagio_perdido is None:
        raise ValueError('Nenhum estágio is_final_perdido no pipeline.')

    lead = oportunidade.lead
    via = (getattr(lead, 'dados_custom', None) or {}).get('viabilidade') or {}
    cep = via.get('cep_consultado') or getattr(lead, 'cep', '') or ''
    cidade = via.get('cidade') or '—'
    uf = via.get('uf') or '—'
    template = (motivo_template or '').strip() or 'CEP {cep} sem cobertura tecnica em {cidade}/{uf}'
    try:
        motivo = template.format(cep=cep, cidade=cidade, uf=uf)
    except (KeyError, IndexError, ValueError):
        motivo = template  # placeholder inválido no template → usa cru, sem quebrar

    estagio_anterior = oportunidade.estagio
    oportunidade.estagio = estagio_perdido
    oportunidade.data_entrada_estagio = timezone.now()
    oportunidade.motivo_perda_categoria = 'viabilidade'
    oportunidade.motivo_perda = motivo
    oportunidade.save(update_fields=[
        'estagio', 'data_entrada_estagio', 'motivo_perda_categoria', 'motivo_perda',
    ])
    HistoricoPipelineEstagio.objects.create(
        tenant=tenant, oportunidade=oportunidade,
        estagio_anterior=estagio_anterior, estagio_novo=estagio_perdido,
        movido_por=None, motivo=f'Automacao: {motivo}',
    )
    return estagio_perdido, True


def adicionar_item_oportunidade(tenant, *, oportunidade, quantidade=1):
    """Vincula o plano escolhido pelo cliente (via `lead.id_plano_rp`, gravado pelo
    flow Matrix) como `ItemOportunidade` na oportunidade. Idempotente (não duplica o
    mesmo produto). Devolve `(item, criado, motivo)`:
    - criado=True → `item` é o ItemOportunidade novo, `motivo`=''
    - criado=False → `item`=None, `motivo` ∈ {'lead_sem_plano','produto_nao_encontrado','ja_vinculado'}

    `id_plano_rp` é o id_servico do HubSoft; casa com `ProdutoServico.id_externo` no
    catálogo do tenant. Portado de `crm.services.automacao_pipeline._acao_adicionar_item_oportunidade`
    (motor novo autossuficiente — não importa do antigo)."""
    from apps.comercial.crm.models import ProdutoServico, ItemOportunidade
    if oportunidade is None:
        raise ValueError('Sem oportunidade para adicionar item.')

    lead = getattr(oportunidade, 'lead', None)
    if lead is None or not getattr(lead, 'id_plano_rp', None):
        return None, False, 'lead_sem_plano'

    produto = ProdutoServico.all_tenants.filter(
        tenant=tenant, id_externo=str(lead.id_plano_rp),
    ).first()
    if not produto:
        return None, False, 'produto_nao_encontrado'

    if oportunidade.itens.filter(produto=produto).exists():
        return None, False, 'ja_vinculado'

    try:
        qtd = int(quantidade or 1)
    except (TypeError, ValueError):
        qtd = 1
    qtd = max(qtd, 1)

    item = ItemOportunidade.all_tenants.create(
        tenant=tenant, oportunidade=oportunidade, produto=produto,
        quantidade=qtd, valor_unitario=produto.preco or 0, desconto=0,
    )
    return item, True, ''


def criar_nota(tenant, *, oportunidade, texto, titulo=''):
    """Cria uma `NotaInterna` vinculada à `oportunidade`. O model não tem campo de
    título; quando `titulo` vem preenchido, ele é prefixado no `conteudo`. Autor
    resolve por default (oportunidade.responsavel → staff do tenant → superuser),
    mesmo padrão de `criar_tarefa`. Devolve a NotaInterna.

    Levanta `ValueError` se não houver oportunidade, conteúdo vazio, ou nenhum autor
    possível.
    """
    from django.contrib.auth.models import User
    from apps.comercial.crm.models import NotaInterna
    from apps.sistema.models import PerfilUsuario

    if oportunidade is None:
        raise ValueError('Sem oportunidade para anotar.')

    conteudo = (texto or '').strip()
    if (titulo or '').strip():
        conteudo = f'{titulo.strip()}\n\n{conteudo}' if conteudo else titulo.strip()
    if not conteudo:
        raise ValueError('Nota sem conteúdo.')

    autor = getattr(oportunidade, 'responsavel', None)
    if autor is None:
        perfil = PerfilUsuario.objects.filter(tenant=tenant, user__is_staff=True).first()
        autor = perfil.user if perfil else User.objects.filter(is_superuser=True).first()
    if autor is None:
        raise ValueError('Nenhum autor disponível para a nota.')

    nota = NotaInterna(tenant=tenant, oportunidade=oportunidade, autor=autor, conteudo=conteudo)
    nota.save()
    return nota


def definir_motivo_perda(tenant, *, oportunidade, motivo_nome, texto='', somente_se_vazio=True):
    """Resolve um `MotivoPerda` ativo do tenant por nome (case-insensitive) e vincula
    em `oportunidade.motivo_perda_ref`. Se `texto` vier, também preenche o
    `motivo_perda` (texto livre). Com `somente_se_vazio=True` (default), não sobrescreve
    se a op já tiver um `motivo_perda_ref`, devolve `(motivo_atual, False)` sem tocar.
    Devolve `(motivo, alterou: bool)`.

    Levanta `ValueError` se não houver oportunidade, `motivo_nome` vazio, ou nenhum
    MotivoPerda ativo do tenant com esse nome (lista os disponíveis na mensagem).
    """
    from apps.comercial.crm.models import MotivoPerda
    if oportunidade is None:
        raise ValueError('Sem oportunidade para definir motivo de perda.')
    nome = (motivo_nome or '').strip()
    if not nome:
        raise ValueError('Motivo de perda não especificado.')

    motivo = MotivoPerda.all_tenants.filter(tenant=tenant, ativo=True, nome__iexact=nome).first()
    if motivo is None:
        disponiveis = ', '.join(
            MotivoPerda.all_tenants.filter(tenant=tenant, ativo=True)
            .order_by('ordem').values_list('nome', flat=True)
        ) or 'nenhum cadastrado'
        raise ValueError(f'Motivo de perda "{motivo_nome}" não encontrado. Disponíveis: {disponiveis}')

    if somente_se_vazio and oportunidade.motivo_perda_ref_id:
        return oportunidade.motivo_perda_ref, False

    oportunidade.motivo_perda_ref = motivo
    campos = ['motivo_perda_ref']
    if (texto or '').strip():
        oportunidade.motivo_perda = texto.strip()
        campos.append('motivo_perda')
    oportunidade.save(update_fields=campos)
    return motivo, True


def reabrir_oportunidade(tenant, *, oportunidade, estagio_slug, motivo=''):
    """Reabre uma oportunidade que estava em estágio perdido (`is_final_perdido=True`),
    movendo pro `estagio_slug` informado dentro do mesmo pipeline. Idempotente: se a op
    não está perdida, não é erro, devolve `(None, False)` sem tocar. MANTÉM
    motivo_perda/motivo_perda_ref/responsavel (auditoria da perda anterior) e limpa
    `data_fechamento_real`. Registra `HistoricoPipelineEstagio` + `LogSistema`. Devolve
    `(estagio_novo, reabriu: bool)`.

    Levanta `ValueError` se `estagio_slug` não vier ou não existir no pipeline da op.
    """
    from apps.comercial.crm.models import PipelineEstagio, HistoricoPipelineEstagio
    from apps.sistema.utils import registrar_acao

    if oportunidade is None:
        raise ValueError('Sem oportunidade para reabrir.')
    if not (oportunidade.estagio and oportunidade.estagio.is_final_perdido):
        return None, False  # não está perdida, idempotente

    if not (estagio_slug or '').strip():
        raise ValueError('Estágio de reabertura não especificado.')
    estagio_novo = PipelineEstagio.all_tenants.filter(
        tenant=tenant, pipeline=oportunidade.pipeline, slug=estagio_slug.strip(),
    ).first()
    if estagio_novo is None:
        raise ValueError(f'Estágio "{estagio_slug}" não encontrado no pipeline.')

    estagio_anterior = oportunidade.estagio
    oportunidade.estagio = estagio_novo
    oportunidade.data_entrada_estagio = timezone.now()
    oportunidade.data_fechamento_real = None
    oportunidade.save(update_fields=['estagio', 'data_entrada_estagio', 'data_fechamento_real'])

    HistoricoPipelineEstagio.objects.create(
        tenant=tenant, oportunidade=oportunidade,
        estagio_anterior=estagio_anterior, estagio_novo=estagio_novo,
        movido_por=None, motivo=f'Automacao: {motivo or "reabertura"}',
    )
    try:
        registrar_acao(
            'crm', 'reabrir', 'oportunidade', oportunidade.pk,
            f'Oportunidade reaberta para "{estagio_novo.nome}"',
            dados_extras={'estagio_anterior': estagio_anterior.slug if estagio_anterior else None,
                          'estagio_novo': estagio_novo.slug, 'motivo': motivo or ''},
            tenant=tenant,
        )
    except Exception:
        pass
    return estagio_novo, True


def marcar_dados_custom(tenant, *, oportunidade, chave, valor=None):
    """Grava `valor` em `oportunidade.dados_custom[chave]`. Sem `valor` (None ou
    vazio), grava o timestamp atual (ISO 8601), útil pra marcar "processado em".
    Devolve o valor gravado.

    Levanta `ValueError` se `oportunidade` ou `chave` (após strip) não vierem.
    """
    if oportunidade is None:
        raise ValueError('Sem oportunidade para marcar dado customizado.')
    chave_limpa = (chave or '').strip()
    if not chave_limpa:
        raise ValueError('Chave não especificada.')

    valor_gravado = valor if (valor is not None and valor != '') else timezone.now().isoformat()
    oportunidade.dados_custom = {**(oportunidade.dados_custom or {}), chave_limpa: valor_gravado}
    oportunidade.save(update_fields=['dados_custom'])
    return valor_gravado
