"""Backfill: gera embedding pra artigos da base de conhecimento que ainda
nao tem.

Uso:
    python manage.py backfill_embeddings_artigos
    python manage.py backfill_embeddings_artigos --tenant nuvyon
    python manage.py backfill_embeddings_artigos --force   (regera todos, mesmo os ja com embedding)

Idempotente: por padrao so processa artigos com embedding NULL.
"""
import logging
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Gera embeddings pros artigos da base de conhecimento que ainda nao tem.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=str, default=None,
            help='Slug do tenant. Sem isso, processa todos.')
        parser.add_argument('--force', action='store_true',
            help='Regera mesmo artigos que ja tem embedding.')
        parser.add_argument('--limit', type=int, default=None,
            help='Limita quantos processar (util pra teste).')

    def handle(self, *args, **opts):
        from apps.suporte.models import ArtigoConhecimento
        from apps.sistema.models import Tenant
        from apps.sistema.services.embeddings import gerar_embedding

        qs = ArtigoConhecimento.all_tenants.all()
        if opts['tenant']:
            t = Tenant.objects.filter(slug=opts['tenant']).first()
            if not t:
                self.stderr.write(f'Tenant nao encontrado: {opts["tenant"]}')
                return
            qs = qs.filter(tenant=t)

        if not opts['force']:
            qs = qs.filter(embedding__isnull=True)

        if opts['limit']:
            qs = qs[:opts['limit']]

        total = qs.count()
        self.stdout.write(f'Total a processar: {total}')

        ok = falha = 0
        t0 = time.time()
        for art in qs:
            tag_tenant = art.tenant.slug if art.tenant else '?'
            texto = art.texto_pra_embedding()
            emb = gerar_embedding(texto, tenant=art.tenant)
            if emb is None:
                falha += 1
                self.stderr.write(f'  [FALHA] artigo {art.pk} ({tag_tenant}/{art.slug}): nao gerou embedding')
                continue
            ArtigoConhecimento.all_tenants.filter(pk=art.pk).update(
                embedding=emb, embedding_atualizado_em=timezone.now(),
            )
            ok += 1
            self.stdout.write(f'  [OK] artigo {art.pk} ({tag_tenant}/{art.slug}): {art.titulo[:60]}')

        self.stdout.write(self.style.SUCCESS(
            f'\nProcessado: ok={ok} falha={falha} (em {time.time()-t0:.1f}s)'
        ))
