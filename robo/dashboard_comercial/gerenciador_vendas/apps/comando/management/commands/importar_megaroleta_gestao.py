"""
Importa dados do modulo `gestao` do megaroleta legado pra `apps.comando`.

Modos de uso:

1) Conectar direto no Postgres do megaroleta (recomendado em prod com acesso):
       python manage.py importar_megaroleta_gestao --source-db-url='postgresql://user:pass@host:5432/megasorteio'

2) Importar de JSON ja exportado:
       python manage.py importar_megaroleta_gestao --from-json=/path/to/export.json

Outros flags:
    --dry-run    Mostra quantos registros viriam, nao grava nada
    --check      So conecta na fonte e valida que tabelas existem
    --truncate   Apaga dados existentes em apps.comando antes de importar (CUIDADO)

Idempotente: tenta criar com PK original; se ja existe, ignora (sem update).

Tabelas importadas (na ordem de dependencia):
  1. gestao_agente               -> comando.Agente
  2. gestao_toolagente           -> comando.ToolAgente
  3. gestao_logtool              -> comando.LogTool
  4. gestao_mensagemchat         -> comando.MensagemChat
  5. gestao_reuniao              -> comando.Reuniao
  6. gestao_mensagemreuniao      -> comando.MensagemReuniao
  7. gestao_automacao            -> comando.Automacao
  8. gestao_alerta               -> comando.Alerta
  9. gestao_proposta             -> comando.Proposta
  10. gestao_faqcategoria        -> comando.FAQCategoria
  11. gestao_faqitem             -> comando.FAQItem
"""
import json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.comando.models import (
    Agente, Alerta, Automacao, FAQCategoria, FAQItem,
    LogTool, MensagemChat, MensagemReuniao, Proposta, Reuniao, ToolAgente,
)


# Mapeamento: tabela megaroleta -> (model robo, lista de campos a copiar, post-processor opcional)
# Campos seguem nomes originais do megaroleta — se houver divergencia, ajustar abaixo.
TABELAS = [
    ('gestao_agente', Agente, [
        'id', 'slug', 'nome', 'descricao', 'icone', 'cor', 'time',
        'prompt', 'prompt_autonomo', 'modelo', 'ativo', 'ordem',
        'criado_em', 'atualizado_em',
    ]),
    ('gestao_toolagente', ToolAgente, [
        'id', 'slug', 'nome', 'descricao', 'icone', 'tipo',
        'prompt', 'exemplo', 'ativo', 'ordem',
        'criado_em', 'atualizado_em',
    ]),
    ('gestao_logtool', LogTool, [
        'id', 'tool_id', 'agente_id', 'tool_slug',
        'resultado', 'sucesso', 'tempo_ms', 'criado_em',
    ]),
    ('gestao_mensagemchat', MensagemChat, [
        'id', 'agente_id', 'role', 'conteudo', 'criado_em',
    ]),
    ('gestao_reuniao', Reuniao, [
        'id', 'nome', 'descricao', 'agentes', 'ativa', 'criado_em',
    ]),
    ('gestao_mensagemreuniao', MensagemReuniao, [
        'id', 'reuniao_id', 'tipo', 'agente_id', 'agente_nome',
        'conteudo', 'criado_em',
    ]),
    ('gestao_automacao', Automacao, [
        'id', 'modo', 'tool_id', 'agente_id', 'encaminhar_para_id',
        'intervalo_horas', 'status', 'ultima_execucao', 'ultimo_resultado',
        'ultima_analise', 'total_execucoes', 'total_erros', 'ativo',
        'criado_em', 'atualizado_em',
    ]),
    ('gestao_alerta', Alerta, [
        'id', 'tipo', 'severidade', 'titulo', 'descricao', 'dados_json',
        'agente_id', 'tool_id', 'lido', 'resolvido', 'criado_em',
    ]),
    ('gestao_proposta', Proposta, [
        'id', 'agente_id', 'tool_id', 'alerta_id', 'reuniao_id',
        'titulo', 'descricao', 'prioridade', 'status', 'dados_execucao',
        'motivo_rejeicao', 'resultado_execucao',
        'criado_em', 'data_decisao', 'data_execucao',
    ]),
    ('gestao_faqcategoria', FAQCategoria, [
        'id', 'nome', 'slug', 'icone', 'cor', 'ordem', 'ativo', 'criado_em',
    ]),
    ('gestao_faqitem', FAQItem, [
        'id', 'categoria_id', 'pergunta', 'resposta', 'ordem', 'ativo',
        'gerado_por_ia', 'hash_dados_fonte', 'criado_em', 'atualizado_em',
    ]),
]


class Command(BaseCommand):
    help = 'Importa dados do modulo gestao do megaroleta pra apps.comando.'

    def add_arguments(self, parser):
        parser.add_argument('--source-db-url', help='Connection string Postgres do megaroleta')
        parser.add_argument('--from-json', help='Arquivo JSON exportado previamente')
        parser.add_argument('--dry-run', action='store_true', help='Nao grava, soh conta')
        parser.add_argument('--check', action='store_true', help='So valida conexao e tabelas')
        parser.add_argument('--truncate', action='store_true', help='Apaga dados existentes antes')

    def handle(self, *args, **opts):
        url = opts.get('source_db_url')
        json_path = opts.get('from_json')
        dry = opts.get('dry_run')
        check_only = opts.get('check')
        truncate = opts.get('truncate')

        if not url and not json_path:
            raise CommandError('Passe --source-db-url ou --from-json. Ver help pra detalhes.')
        if url and json_path:
            raise CommandError('Use apenas um: --source-db-url OU --from-json.')

        # Carregar dados na memoria
        if url:
            dados = self._carregar_postgres(url, check_only)
        else:
            dados = self._carregar_json(json_path)

        if check_only:
            self.stdout.write(self.style.SUCCESS('\nCheck: OK. Tabelas encontradas:'))
            for nome, count in dados.items():
                self.stdout.write(f'  {nome}: {count} registros')
            return

        # Truncate se pedido
        if truncate and not dry:
            self.stdout.write(self.style.WARNING('\nTruncando tabelas comando antes de importar...'))
            for _, model, _ in reversed(TABELAS):
                n = model.objects.count()
                model.objects.all().delete()
                self.stdout.write(f'  - {model._meta.db_table}: {n} apagados')

        # Importar
        self.stdout.write(self.style.NOTICE('\nImportando...'))
        if dry:
            self.stdout.write(self.style.WARNING('(modo dry-run — nao grava no banco)'))

        total_criados = 0
        total_existentes = 0
        with transaction.atomic():
            for tabela, model, campos in TABELAS:
                rows = dados.get(tabela, [])
                if not rows:
                    self.stdout.write(f'  {tabela}: 0 registros (pulando)')
                    continue

                criados = 0
                existentes = 0
                for row in rows:
                    pk = row.get('id')
                    if not pk:
                        continue

                    if model.objects.filter(pk=pk).exists():
                        existentes += 1
                        continue

                    if dry:
                        criados += 1
                        continue

                    kwargs = {c: row.get(c) for c in campos if c in row}
                    try:
                        model.objects.create(**kwargs)
                        criados += 1
                    except Exception as e:
                        self.stderr.write(self.style.WARNING(
                            f'    erro em {tabela} id={pk}: {e}'
                        ))
                        continue

                self.stdout.write(
                    f'  {tabela}: +{criados} criados, {existentes} ja existiam'
                )
                total_criados += criados
                total_existentes += existentes

            if dry:
                # Em dry-run nao queremos commit acidental se algum side-effect
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f'\nTotal: {total_criados} criados, {total_existentes} ja existiam.'
        ))
        if dry:
            self.stdout.write(self.style.WARNING('Dry-run: nada foi gravado.'))
        else:
            self.stdout.write(self.style.SUCCESS('Importacao concluida.'))

    # ── Carregadores de dados ─────────────────────────────────────────────

    def _carregar_postgres(self, url, check_only):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            raise CommandError('psycopg2 nao instalado. Rode: pip install psycopg2-binary')

        self.stdout.write(self.style.NOTICE(f'Conectando em: {self._mask_url(url)}'))
        try:
            conn = psycopg2.connect(url)
        except Exception as e:
            raise CommandError(f'Falha ao conectar: {e}')

        dados = {}
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for tabela, _, _ in TABELAS:
                # Confirma que tabela existe
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = %s
                    )
                """, [tabela])
                exists = cur.fetchone()['exists']
                if not exists:
                    self.stdout.write(self.style.WARNING(
                        f'  {tabela}: tabela nao encontrada no banco fonte (ignorando)'
                    ))
                    dados[tabela] = []
                    continue

                if check_only:
                    cur.execute(f'SELECT COUNT(*) AS n FROM {tabela}')
                    dados[tabela] = cur.fetchone()['n']
                else:
                    cur.execute(f'SELECT * FROM {tabela}')
                    rows = cur.fetchall()
                    dados[tabela] = [self._normalizar_row(dict(r)) for r in rows]
        conn.close()
        return dados

    def _carregar_json(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
        except FileNotFoundError:
            raise CommandError(f'Arquivo nao encontrado: {path}')
        except json.JSONDecodeError as e:
            raise CommandError(f'JSON invalido: {e}')

        # Aceita 2 formatos: { tabela: [rows] } ou lista de dicts {table, rows}
        dados = {}
        if isinstance(raw, dict):
            for tabela, rows in raw.items():
                dados[tabela] = [self._normalizar_row(r) for r in rows]
        elif isinstance(raw, list):
            for entry in raw:
                tabela = entry.get('table')
                rows = entry.get('rows', [])
                if tabela:
                    dados[tabela] = [self._normalizar_row(r) for r in rows]
        else:
            raise CommandError('JSON em formato invalido. Esperado dict ou lista.')
        return dados

    # ── Helpers ────────────────────────────────────────────────────────────

    def _normalizar_row(self, row):
        """Converte tipos especiais (datetime ja vem do psycopg2; JSON vem como dict)."""
        # Datas em string -> datetime
        for k, v in list(row.items()):
            if isinstance(v, str) and ('em' in k or 'execucao' in k or 'decisao' in k):
                # Heuristica: campos *_em / *_execucao / *_decisao podem ser datetime
                try:
                    row[k] = datetime.fromisoformat(v.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    pass
        # dados_json e dados_execucao podem vir como string -> parse
        for k in ('dados_json', 'dados_execucao'):
            if k in row and isinstance(row[k], str):
                try:
                    row[k] = json.loads(row[k])
                except (ValueError, TypeError):
                    pass
        return row

    def _mask_url(self, url):
        # Esconde senha pra log
        if '@' not in url:
            return url
        prefix, rest = url.split('://', 1)
        if ':' in rest and '@' in rest:
            user, _ = rest.split(':', 1)
            host = rest.split('@', 1)[1]
            return f'{prefix}://{user}:****@{host}'
        return url
