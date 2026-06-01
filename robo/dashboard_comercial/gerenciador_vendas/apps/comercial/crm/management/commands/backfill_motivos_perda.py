"""T6 — Backfill historico via LLM: infere motivo de perda de oportunidades
que estao no estagio "Perdida" mas ainda nao tem motivo associado.

Usa OpenAI Chat Completions (gpt-4o-mini) pra classificar com base nas
ultimas mensagens da conversa do lead.

USO TIPICO:
    # Dry-run obrigatorio primeiro (default):
    python manage.py backfill_motivos_perda --tenant aurora-hq

    # Revisar amostra impressa. Se aprovar, aplicar:
    python manage.py backfill_motivos_perda --tenant aurora-hq --apply

FLAGS:
    --tenant <slug>           OBRIGATORIO. Sem isso, recusa rodar (proteca contra
                              backfill cross-tenant acidental).
    --apply                   Persiste no banco. Sem ele, --dry-run e default.
    --confidence-min 0.7      LLM com score abaixo disso vai pra "outro" + texto livre.
    --max-msgs-cliente 5      Quantas ultimas mensagens do cliente alimentar o LLM.
    --max-msgs-atendente 3    Quantas ultimas mensagens do atendente/bot alimentar.
    --limit N                 Limita quantas oportunidades processar (util pra testar).
    --sample-size 10          Tamanho da amostra exibida no fim do dry-run pra revisao.

Idempotente: so processa oportunidades onde motivo_perda_ref IS NULL.
"""
import json
import logging
import random
import time
from typing import Optional

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


def _resolver_api_key(tenant) -> Optional[str]:
    """Pega chave OpenAI do tenant ou cai pra Aurora HQ como fallback."""
    from apps.integracoes.models import IntegracaoAPI
    from apps.sistema.models import Tenant
    if tenant:
        ig = IntegracaoAPI.all_tenants.filter(
            tenant=tenant, tipo='openai', ativa=True,
        ).exclude(api_key='').exclude(api_key__isnull=True).first()
        if ig and ig.api_key:
            return ig.api_key
    aurora = Tenant.objects.filter(slug='aurora-hq').first()
    if not aurora:
        return None
    ig = IntegracaoAPI.all_tenants.filter(
        tenant=aurora, tipo='openai', ativa=True,
    ).exclude(api_key='').exclude(api_key__isnull=True).first()
    return ig.api_key if (ig and ig.api_key) else None


def _coletar_msgs(oportunidade, max_cliente: int, max_atendente: int):
    """Retorna lista de dicts {role, texto} ordenados cronologicamente.
    Pega ultimas N do cliente + ultimas M do atendente/bot e mescla.
    """
    try:
        from apps.inbox.models import Mensagem
    except Exception:
        return []
    lead = oportunidade.lead
    if not lead:
        return []
    qs = Mensagem.all_tenants.filter(
        tenant=oportunidade.tenant,
        conversa__lead=lead,
    ).order_by('-data_envio')

    msgs_cliente = []
    msgs_atendente = []
    for m in qs[:200]:  # buffer pra filtrar dentro
        tipo = (getattr(m, 'remetente_tipo', '') or '').lower()
        eh_cliente = tipo in ('contato', 'cliente', 'lead')
        if eh_cliente and len(msgs_cliente) < max_cliente:
            msgs_cliente.append(m)
        elif not eh_cliente and len(msgs_atendente) < max_atendente:
            msgs_atendente.append(m)
        if len(msgs_cliente) >= max_cliente and len(msgs_atendente) >= max_atendente:
            break

    todas = msgs_cliente + msgs_atendente
    todas.sort(key=lambda m: m.data_envio)
    return [
        {
            'role': 'CLIENTE' if ((getattr(m, 'remetente_tipo', '') or '').lower() in ('contato','cliente','lead')) else 'ATENDENTE',
            'texto': (getattr(m, 'conteudo', '') or '').strip()[:500],
            'quando': m.data_envio.strftime('%Y-%m-%d %H:%M'),
        }
        for m in todas if (getattr(m, 'conteudo', '') or '').strip()
    ]


def _classificar(api_key: str, motivos: list, mensagens: list) -> Optional[dict]:
    """Chama OpenAI gpt-4o-mini com prompt structured.
    Retorna {motivo_id: int|None, motivo_nome: str, justificativa: str, confidence: float} ou None se falhar.
    """
    import requests

    opcoes_txt = '\n'.join([f"  - id={m['id']}: {m['nome']}" for m in motivos])
    msgs_txt = '\n'.join([f"[{m['quando']}] {m['role']}: {m['texto']}" for m in mensagens])

    system = (
        "Voce e analista de CRM. Recebe trechos de conversa entre cliente e atendente "
        "de uma oportunidade que foi marcada como PERDIDA. Sua tarefa: identificar o "
        "motivo da perda escolhendo um dos motivos catalogados abaixo. Retorne JSON "
        "estritamente neste formato:\n"
        "{\"motivo_id\": <id ou null>, \"motivo_nome\": \"<nome do motivo escolhido>\", "
        "\"justificativa\": \"<frase curta explicando>\", \"confidence\": <float 0-1>}\n\n"
        "Se nao for possivel inferir com seguranca razoavel, retorne motivo_id=null e confidence baixo (<0.5).\n"
        f"Motivos catalogados:\n{opcoes_txt}"
    )
    user = f"Conversa:\n{msgs_txt or '(sem mensagens)'}"

    try:
        r = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': 'gpt-4o-mini',
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                'response_format': {'type': 'json_object'},
                'temperature': 0.1,
            },
            timeout=45,
        )
        if r.status_code != 200:
            logger.warning('OpenAI %s: %s', r.status_code, r.text[:200])
            return None
        content = r.json()['choices'][0]['message']['content']
        return json.loads(content)
    except Exception:
        logger.exception('Erro classificando via LLM')
        return None


class Command(BaseCommand):
    help = 'Backfill historico: infere motivo de perda de oportunidades sem motivo via LLM.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, required=True,
            help='Slug do tenant (obrigatorio).')
        parser.add_argument('--apply', action='store_true',
            help='Sem ele, roda em dry-run (nao persiste).')
        parser.add_argument('--confidence-min', type=float, default=0.7,
            help='Confidence minimo pra associar motivo catalogado (default 0.7). Abaixo vai pra "outro".')
        parser.add_argument('--max-msgs-cliente', type=int, default=5,
            help='Ultimas N msgs do cliente alimentadas no LLM (default 5).')
        parser.add_argument('--max-msgs-atendente', type=int, default=3,
            help='Ultimas N msgs do atendente alimentadas no LLM (default 3).')
        parser.add_argument('--limit', type=int, default=None,
            help='Limita quantas oportunidades processar.')
        parser.add_argument('--sample-size', type=int, default=10,
            help='Amostra exibida no fim do dry-run (default 10).')

    def handle(self, *args, **opts):
        from apps.comercial.crm.models import OportunidadeVenda, MotivoPerda
        from apps.sistema.models import Tenant

        tenant = Tenant.objects.filter(slug=opts['tenant']).first()
        if not tenant:
            self.stderr.write(self.style.ERROR(f'Tenant nao encontrado: {opts["tenant"]}'))
            return

        modo = 'APPLY' if opts['apply'] else 'DRY-RUN'
        self.stdout.write(self.style.WARNING(f'\n{"="*60}\nMODO: {modo}  tenant={opts["tenant"]}\n{"="*60}'))

        motivos = list(MotivoPerda.all_tenants.filter(tenant=tenant, ativo=True).order_by('ordem','nome').values('id','nome'))
        if not motivos:
            self.stderr.write(f'Tenant {opts["tenant"]} nao tem MotivoPerda cadastrado. Cadastre antes em /crm/motivos-perda/.')
            return
        self.stdout.write(f'Motivos catalogados: {len(motivos)} ({", ".join(m["nome"] for m in motivos[:6])}{"..." if len(motivos)>6 else ""})')

        api_key = _resolver_api_key(tenant)
        if not api_key:
            self.stderr.write(self.style.ERROR(f'Sem chave OpenAI pro tenant nem fallback Aurora. Abortando.'))
            return

        qs = OportunidadeVenda.all_tenants.filter(
            tenant=tenant, motivo_perda_ref__isnull=True, ativo=True,
        ).select_related('lead', 'estagio')
        if opts['limit']:
            qs = qs[:opts['limit']]
        total = qs.count()
        self.stdout.write(f'Oportunidades sem motivo: {total}\n')
        if not total:
            self.stdout.write(self.style.SUCCESS('Nada a processar.'))
            return

        outros_id = next((m['id'] for m in motivos if m['nome'].lower() == 'outro'), None)
        resultados = []
        ok = falha = baixa = 0
        t0 = time.time()

        for op in qs:
            mensagens = _coletar_msgs(op, opts['max_msgs_cliente'], opts['max_msgs_atendente'])
            if not mensagens:
                logger.info('op=%s sem mensagens; pulando', op.pk)
                continue

            resp = _classificar(api_key, motivos, mensagens)
            if not resp:
                falha += 1
                self.stderr.write(f'  [FALHA] op={op.pk}: LLM nao classificou')
                continue

            conf = float(resp.get('confidence') or 0.0)
            motivo_id = resp.get('motivo_id')
            motivo_nome = resp.get('motivo_nome') or '(nao informado)'
            justif = (resp.get('justificativa') or '').strip()[:400]

            if conf < opts['confidence_min'] or not motivo_id:
                baixa += 1
                motivo_id_final = outros_id  # cai em "Outro" se existe
                origem_obs = f'[BAIXA CONFIANCA {conf:.2f}] {justif} (sugerido: {motivo_nome})'
            else:
                motivo_id_final = motivo_id if any(m['id'] == motivo_id for m in motivos) else outros_id
                ok += 1
                origem_obs = f'[LLM-BACKFILL {conf:.2f}] {justif}'

            resultados.append({
                'op_id': op.pk,
                'lead_nome': op.lead.nome_razaosocial if op.lead else '?',
                'motivo_nome': motivo_nome,
                'motivo_id_final': motivo_id_final,
                'confidence': conf,
                'justificativa': justif,
            })

            if opts['apply']:
                OportunidadeVenda.all_tenants.filter(pk=op.pk).update(
                    motivo_perda_ref_id=motivo_id_final,
                    motivo_perda=origem_obs,
                    motivo_perda_origem='llm_backfill',
                )

        elapsed = time.time() - t0
        self.stdout.write(f'\nProcessadas: {len(resultados)}  ok={ok}  baixa_conf={baixa}  falhas={falha}  em {elapsed:.1f}s')

        # Distribuicao por motivo
        from collections import Counter
        dist = Counter(r['motivo_nome'] for r in resultados)
        self.stdout.write('\nDistribuicao por motivo:')
        for nome, qtd in dist.most_common():
            self.stdout.write(f'  {qtd:4d}  {nome}')

        # Amostra pra revisao no dry-run
        if not opts['apply']:
            sample = random.sample(resultados, min(opts['sample_size'], len(resultados))) if resultados else []
            self.stdout.write(self.style.WARNING(f'\n=== AMOSTRA RANDOM ({len(sample)} de {len(resultados)}) — REVISE ANTES DE --apply ==='))
            for r in sample:
                self.stdout.write(f"  op={r['op_id']} ({r['lead_nome'][:30]}): conf={r['confidence']:.2f}  motivo={r['motivo_nome']}")
                self.stdout.write(f"    > {r['justificativa']}")
            self.stdout.write(self.style.WARNING('\nNada foi persistido (dry-run). Se aprovou a amostra, rode novamente com --apply.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nPersistido. Reverter com:'))
            self.stdout.write(f'  UPDATE crm_oportunidades SET motivo_perda_ref_id=NULL, motivo_perda=NULL, motivo_perda_origem=\'humano\' '
                              f'WHERE tenant_id={tenant.id} AND motivo_perda_origem=\'llm_backfill\';')
