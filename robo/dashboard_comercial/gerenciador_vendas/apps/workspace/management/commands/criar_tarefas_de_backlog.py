"""
Cria Tarefas reais no Kanban do projeto Hubtrix Desenvolvimento a partir
dos docs em '10. Tarefas/Backlog' (e opcionalmente Finalizadas).

Cada doc vira uma Tarefa com:
  - titulo: extraido do frontmatter (`name`) ou do H1 do markdown
  - descricao: extraida do frontmatter (`description`) ou primeiras linhas
  - prioridade: parseada do frontmatter (alta/media/baixa/critica)
  - status: pendente (backlog) ou concluida (finalizadas)
  - documento_processo: aponta pro Documento original

Idempotente: se ja existe Tarefa com mesmo titulo no projeto, atualiza.

Uso:
    python manage.py criar_tarefas_de_backlog [--projeto 'Hubtrix Desenvolvimento']
                                              [--tenant 'Aurora HQ']
                                              [--incluir-finalizadas]
                                              [--dry-run]
"""
import re

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.sistema.models import Tenant
from apps.workspace.models import PastaDocumento, Projeto, Tarefa


PRIORIDADE_MAP = {
    'critica': 'critica', 'critical': 'critica',
    'alta': 'alta', 'high': 'alta',
    'media': 'media', 'média': 'media', 'medium': 'media',
    'baixa': 'baixa', 'low': 'baixa',
    '🔴': 'critica',
    '🟠': 'alta',
    '🟡': 'media',
    '🟢': 'baixa',
}


# Mapeamento de seções H2 (heading nivel 2) -> campos do Tarefa
# Aceita variações: case-insensitive, com/sem acento, sinonimos
SECAO_MAP = {
    # alvo: descricao
    'descricao':                    'descricao',
    'descrição':                    'descricao',
    'description':                  'descricao',
    'sobre':                        'descricao',
    'visao geral':                  'descricao',
    'visão geral':                  'descricao',
    'overview':                     'descricao',
    # alvo: objetivo
    'objetivo':                     'objetivo',
    'why':                          'objetivo',
    'motivacao':                    'objetivo',
    'motivação':                    'objetivo',
    # alvo: contexto
    'contexto':                     'contexto',
    'contexto e referencias':       'contexto',
    'contexto e referências':       'contexto',
    'referencias':                  'contexto',
    'referências':                  'contexto',
    'background':                   'contexto',
    # alvo: passos (checklist / todos)
    'tarefas':                      'passos',
    'checklist':                    'passos',
    'passos':                       'passos',
    'steps':                        'passos',
    'plano':                        'passos',
    'plano de execucao':            'passos',
    'plano de execução':            'passos',
    'todo':                         'passos',
    'subtarefas':                   'passos',
    # alvo: entregavel
    'entregavel':                   'entregavel',
    'entregável':                   'entregavel',
    'entregaveis':                  'entregavel',
    'entregáveis':                  'entregavel',
    'deliverable':                  'entregavel',
    'output':                       'entregavel',
    'resultado esperado':           'entregavel',
    'expected':                     'entregavel',
    # alvo: criterios_aceite
    'criterios de aceite':          'criterios_aceite',
    'critérios de aceite':          'criterios_aceite',
    'criterios_aceite':             'criterios_aceite',
    'definition of done':           'criterios_aceite',
    'dod':                          'criterios_aceite',
    'aceite':                       'criterios_aceite',
}


class Command(BaseCommand):
    help = 'Cria Tarefas reais a partir dos docs em 10. Tarefas/Backlog.'

    def add_arguments(self, parser):
        parser.add_argument('--projeto', default='Hubtrix Desenvolvimento')
        parser.add_argument('--tenant', default='Aurora HQ')
        parser.add_argument('--incluir-finalizadas', action='store_true',
            help='Traz tambem docs de Finalizadas como tarefas concluidas')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        try:
            tenant = Tenant.objects.get(nome=opts['tenant'])
        except Tenant.DoesNotExist:
            raise CommandError(f'Tenant nao encontrado: {opts["tenant"]}')

        # Encontrar pastas Backlog e (opcional) Finalizadas
        backlog = PastaDocumento.all_tenants.filter(tenant=tenant, slug='10-tarefas-backlog').first()
        if not backlog:
            raise CommandError('Pasta "10. Tarefas/Backlog" nao encontrada. Rode importar_docs_drive primeiro.')

        finalizadas = None
        if opts['incluir_finalizadas']:
            finalizadas = PastaDocumento.all_tenants.filter(tenant=tenant, slug='10-tarefas-finalizadas').first()
            if not finalizadas:
                self.stdout.write(self.style.WARNING('Pasta Finalizadas nao encontrada — pulando.'))

        dry = opts['dry_run']

        with transaction.atomic():
            # Encontrar/criar projeto
            projeto, criado = Projeto.all_tenants.get_or_create(
                tenant=tenant, nome=opts['projeto'],
                defaults={
                    'descricao': 'Projeto guarda-chuva do desenvolvimento do produto Hubtrix.',
                    'status': 'em_andamento',
                    'prioridade': 'alta',
                    'objetivo': 'Construir e evoluir o produto Hubtrix.',
                    'ativo': True,
                    'responsavel': User.objects.filter(is_superuser=True).first(),
                },
            )
            if criado:
                self.stdout.write(self.style.SUCCESS(f'Projeto criado: {projeto.nome} (id={projeto.pk})'))
            else:
                self.stdout.write(f'Projeto existente: {projeto.nome} (id={projeto.pk})')

            # Backlog → status pendente
            self.stdout.write(self.style.NOTICE(f'\nProcessando backlog ({backlog.documentos.count()} docs)...'))
            stats_b = self._processar_pasta(backlog, projeto, tenant, status='pendente', dry=dry)

            # Finalizadas → status concluida
            stats_f = {'criadas': 0, 'atualizadas': 0}
            if finalizadas:
                self.stdout.write(self.style.NOTICE(f'\nProcessando finalizadas ({finalizadas.documentos.count()} docs)...'))
                stats_f = self._processar_pasta(finalizadas, projeto, tenant, status='concluida', dry=dry)

            self.stdout.write(self.style.SUCCESS(
                f'\nBacklog: +{stats_b["criadas"]} criadas, ~{stats_b["atualizadas"]} atualizadas.'
            ))
            if finalizadas:
                self.stdout.write(self.style.SUCCESS(
                    f'Finalizadas: +{stats_f["criadas"]} criadas, ~{stats_f["atualizadas"]} atualizadas.'
                ))

            total_no_projeto = projeto.tarefas.count() if not dry else stats_b['criadas'] + stats_f['criadas']
            self.stdout.write(self.style.SUCCESS(
                f'\nTotal de tarefas no projeto "{projeto.nome}": {total_no_projeto}'
            ))

            if dry:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('Dry-run: nada gravado.'))

    # ── Helpers ────────────────────────────────────────────────────────────

    def _processar_pasta(self, pasta, projeto, tenant, status, dry):
        criadas = 0
        atualizadas = 0
        admin = User.objects.filter(is_superuser=True).first()

        for doc in pasta.documentos.all().order_by('titulo'):
            meta = self._parse_frontmatter(doc.conteudo)
            titulo = meta.get('name') or doc.titulo
            titulo = self._limpar_titulo(titulo)[:200]
            prioridade = self._inferir_prioridade(meta.get('prioridade', ''))

            # Parse das secoes H2 do markdown
            secoes = self._parse_secoes(doc.conteudo)

            descricao = secoes.get('descricao') or meta.get('description') or doc.resumo or ''
            descricao = descricao[:2000]

            data_limite = self._extrair_data(doc.conteudo)
            data_conclusao = timezone.now() if status == 'concluida' else None

            defaults = {
                'descricao': descricao,
                'status': status,
                'prioridade': prioridade,
                'documento_processo': doc,
                'responsavel': admin,
                'data_conclusao': data_conclusao,
                'data_limite': data_limite,
                # Campos ricos extraidos do briefing
                'objetivo':         secoes.get('objetivo', ''),
                'contexto':         secoes.get('contexto', ''),
                'passos':           secoes.get('passos', ''),
                'entregavel':       secoes.get('entregavel', ''),
                'criterios_aceite': secoes.get('criterios_aceite', ''),
            }

            if dry:
                criadas += 1
                continue

            tarefa, created = Tarefa.all_tenants.get_or_create(
                tenant=tenant, projeto=projeto, titulo=titulo,
                defaults=defaults,
            )
            if not created:
                for k, v in defaults.items():
                    setattr(tarefa, k, v)
                tarefa.save()
                atualizadas += 1
            else:
                criadas += 1

        return {'criadas': criadas, 'atualizadas': atualizadas}

    def _parse_secoes(self, conteudo):
        """
        Parse markdown por secoes H2. Retorna dict {campo_tarefa: texto_consolidado}.
        Lookups por nome normalizado da secao.
        Sub-secoes H3 ficam dentro do bloco H2 pai.
        """
        # Pular frontmatter
        body = conteudo
        if body.startswith('---'):
            partes = body.split('---', 2)
            if len(partes) >= 3:
                body = partes[2].lstrip()

        # Parse: encontra todas as secoes ## e captura conteudo ate proxima ##
        result = {}  # campo -> lista de blobs (caso multiplas H2 mapearem pro mesmo campo)
        current_section = None
        current_buffer = []

        def flush():
            nonlocal current_section, current_buffer
            if current_section and current_buffer:
                campo = self._mapear_secao(current_section)
                if campo:
                    texto = '\n'.join(current_buffer).strip()
                    if texto:
                        result.setdefault(campo, []).append(texto)
            current_buffer = []

        for ln in body.split('\n'):
            m = re.match(r'^##\s+(.+?)\s*$', ln)
            if m:
                flush()
                current_section = m.group(1).strip()
                # remove emojis no inicio
                current_section = re.sub(r'^[\U0001F300-\U0001FAFF\U00002600-\U000027BF\s]+', '', current_section)
                continue
            # linhas que nao sao H2 vao pro buffer da secao atual
            if current_section is not None:
                current_buffer.append(ln)
        flush()

        # Consolida (se mesmo campo aparece varias vezes, junta)
        consolidado = {}
        for campo, blobs in result.items():
            consolidado[campo] = '\n\n'.join(blobs)[:3000]
        return consolidado

    def _mapear_secao(self, nome_secao):
        """Recebe titulo de secao (ex: 'Critérios de aceite'), devolve campo da Tarefa."""
        # Normaliza: lower, remove acentos, sem pontuacao no final
        norm = nome_secao.lower().rstrip(':').rstrip('.').strip()
        # Replace acentos comuns
        for a, b in [('á','a'),('â','a'),('ã','a'),('é','e'),('ê','e'),('í','i'),('ó','o'),('ô','o'),('õ','o'),('ú','u'),('ç','c')]:
            norm = norm.replace(a, b)
        return SECAO_MAP.get(norm)

    def _extrair_data(self, conteudo):
        """Tenta extrair data do markdown. Padroes: '**Data:** DD/MM/AAAA' ou frontmatter."""
        m = re.search(r'\*\*Data:\*\*\s*(\d{1,2})/(\d{1,2})/(\d{4})', conteudo)
        if m:
            try:
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                from datetime import date
                return date(y, mo, d)
            except (ValueError, TypeError):
                pass
        return None

    def _parse_frontmatter(self, conteudo):
        """Parser simples de YAML frontmatter. Retorna dict de strings."""
        if not conteudo.startswith('---'):
            return {}
        partes = conteudo.split('---', 2)
        if len(partes) < 3:
            return {}
        bloco = partes[1]
        result = {}
        for ln in bloco.split('\n'):
            m = re.match(r'^\s*([a-zA-Z_]+)\s*:\s*(.+?)\s*$', ln)
            if m:
                key = m.group(1).strip()
                value = m.group(2).strip()
                # Remove aspas
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                result[key] = value
        return result

    def _limpar_titulo(self, t):
        # Remove emojis comuns no inicio
        t = re.sub(r'^[\U0001F300-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF\s]+', '', t).strip()
        return t or 'Sem titulo'

    def _inferir_prioridade(self, raw):
        if not raw:
            return 'media'
        raw_lower = raw.lower()
        for key, val in PRIORIDADE_MAP.items():
            if key in raw_lower:
                return val
        return 'media'
