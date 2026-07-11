"""Extrai historico de atendimentos do Matrix Brasil pra analise (LGPD-aware).

Usa o endpoint /rest/v1/relAtAnalitico (paginado) pra listar atendimentos
de uma fila no periodo, depois chama /rest/v1/atendimento por codigo pra
puxar as mensagens detalhadas. Anonimiza PII (nome, cpf, telefone, email)
ANTES de gravar — o arquivo de saida nao deve conter dado pessoal claro.

Uso:
    python manage.py extrair_historico_matrix --tenant nuvyon
    python manage.py extrair_historico_matrix --tenant nuvyon --fila "NOVO CLIENTE" --dias 30
    python manage.py extrair_historico_matrix --tenant nuvyon --limite 50 --output /tmp/teste.json

Saida: JSON com {meta, atendimentos[]}. Cada atendimento tem mensagens[]
com texto anonimizado. Arquivo gitignored por padrao (prefixo `_historico_`).
NAO COMMITAR — apague apos analise.
"""
import json
import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from apps.sistema.models import Tenant
from apps.integracoes.services.anonimizador import construir_anonimizador
from apps.integracoes.services.matrix_brasil import (
    MatrixBrasilService, MatrixBrasilServiceError,
)


def _extrair_mensagens(detalhe, anon):
    """Extrai lista de mensagens do detalhe do atendimento (anonimizadas).

    Formato real Matrix /rest/v1/atendimento:
    - rec['mensagens'] = lista de {id_mensagem, data_msg, boleano_entrante,
      tip_msg, descricao_msg, autor}
    - boleano_entrante='1' -> cliente; '0' -> bot/agente (autor='BOT' = bot)
    - `autor` NAO copiado no output (LGPD: pode ter nome real de agente).
    """
    rec = detalhe[0] if isinstance(detalhe, list) and detalhe else detalhe
    if not isinstance(rec, dict):
        return []
    raw = rec.get('mensagens') or []
    if isinstance(raw, dict):
        raw = [raw]
    out = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        entrante = str(m.get('boleano_entrante') or '0')
        autor = (m.get('autor') or '').upper()
        if entrante == '1':
            tipo_norm = 'cliente'
        elif 'BOT' in autor:
            tipo_norm = 'bot'
        else:
            tipo_norm = 'agente'
        texto = m.get('descricao_msg') or ''
        out.append({
            'tipo': tipo_norm,
            'ts': m.get('data_msg') or '',
            'texto': anon(texto),
            'tipo_msg': m.get('tip_msg') or '',  # TEXTO, IMAGEM, AUDIO, ARQUIVO, etc
        })
    return out


class Command(BaseCommand):
    help = 'Extrai historico Matrix de uma fila (LGPD-anonimizado) pra analise.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', required=True,
            help='Slug do tenant (ex: nuvyon) — so usado como label se --base-url/--token vierem')
        parser.add_argument('--fila', default='NOVO CLIENTE',
            help='Nome da fila Matrix (default: NOVO CLIENTE)')
        parser.add_argument('--dias', type=int, default=30,
            help='Janela em dias retroativa (default: 30)')
        parser.add_argument('--limite', type=int, default=None,
            help='Maximo de atendimentos a processar (default: todos)')
        parser.add_argument('--rate-limit', type=float, default=0.2,
            help='Pausa em seg entre chamadas consultar_atendimento (default 0.2)')
        parser.add_argument('--output', default=None,
            help='Path do JSON de saida (default: _historicos/matrix_<slug>_<YYYYMMDD>.json)')
        parser.add_argument('--base-url', default=None,
            help='Override base URL Matrix (ex: https://artelecomprovedor.matrixdobrasil.ai) '
                 '— se nao vier, busca de IntegracaoAPI no DB do tenant')
        parser.add_argument('--token', default=None,
            help='Override token Matrix raw (sem Bearer). Util pra rodar local '
                 'sem configurar IntegracaoAPI no DB local.')

    def handle(self, *args, **opts):
        slug = opts['tenant']
        fila = opts['fila']
        dias = opts['dias']
        limite = opts['limite']
        pausa = opts['rate_limit']

        if opts.get('base_url') and opts.get('token'):
            svc = MatrixBrasilService(opts['base_url'], opts['token'])
        else:
            try:
                tenant = Tenant.objects.get(slug=slug, ativo=True)
            except Tenant.DoesNotExist:
                raise CommandError(
                    f'Tenant {slug!r} nao encontrado/ativo. '
                    f'Alternativa: passar --base-url e --token diretamente.'
                )
            try:
                svc = MatrixBrasilService.from_tenant(tenant)
            except MatrixBrasilServiceError as e:
                raise CommandError(str(e))

        hoje = datetime.utcnow().date()
        ini = (hoje - timedelta(days=dias)).strftime('%Y-%m-%d')
        fim = hoje.strftime('%Y-%m-%d')

        import os
        if opts['output']:
            out_path = opts['output']
        else:
            out_dir = '_historicos'
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f'matrix_{slug}_{hoje.strftime("%Y%m%d")}.json')

        self.stdout.write(f'Tenant: {slug} | Fila: {fila!r} | Periodo: {ini} a {fim}')
        self.stdout.write(f'Output: {out_path}')

        # 1) Listar todos os atendimentos da fila (paginado)
        todos = []
        page = 1
        while True:
            try:
                data = svc.listar_atendimentos_analitico(
                    data_inicial=ini, data_final=fim,
                    servico_nome=fila, page=page, limit=300,
                )
            except MatrixBrasilServiceError as e:
                self.stderr.write(self.style.ERROR(f'  page {page} ERR: {e}'))
                break
            rows = data.get('rows') or []
            todos.extend(rows)
            total_records = int(data.get('records') or 0)
            self.stdout.write(f'  page {page}: +{len(rows)} (acumulado {len(todos)}/{total_records})')
            if not rows or len(todos) >= total_records:
                break
            if limite and len(todos) >= limite:
                todos = todos[:limite]
                break
            page += 1

        if limite:
            todos = todos[:limite]
        self.stdout.write(f'\nAtendimentos a processar: {len(todos)}')

        # 2) Pra cada atendimento, busca mensagens detalhadas
        atendimentos_out = []
        for i, at in enumerate(todos, 1):
            cod = at.get('id_atendimento')
            if not cod:
                continue
            anon = construir_anonimizador(at)
            try:
                detalhe = svc.consultar_atendimento(cod)
                mensagens = _extrair_mensagens(detalhe, anon)
            except MatrixBrasilServiceError as e:
                self.stderr.write(f'  atend {cod} ERR: {e}')
                mensagens = []

            atendimentos_out.append({
                'cod': cod,
                'data_entrada': at.get('data_entrada'),
                'data_termino': at.get('data_termino'),
                'duracao_seg': at.get('tempo_atendimento'),
                'qtd_cliente': at.get('qtd_cliente'),
                'qtd_agente': at.get('qtd_agente'),
                'qtd_auto': at.get('qtd_auto'),
                'agente': at.get('agente'),
                'status': at.get('status'),
                'classificacao': at.get('id_classificacao'),
                'humor': at.get('humor'),
                'mensagens': mensagens,
            })
            if i % 25 == 0:
                self.stdout.write(f'  processados {i}/{len(todos)}')
            if pausa:
                time.sleep(pausa)

        # 3) Salva JSON
        saida = {
            'meta': {
                'tenant': slug,
                'fila': fila,
                'periodo': f'{ini} a {fim}',
                'total_listados': len(todos),
                'total_com_mensagens': sum(1 for a in atendimentos_out if a['mensagens']),
                'extraido_em': datetime.utcnow().isoformat() + 'Z',
                'anonimizado': True,
                'aviso': 'Mensagens anonimizadas (nome/cpf/telefone/email mascarados). NAO COMMITAR. Apague apos analise.',
            },
            'atendimentos': atendimentos_out,
        }
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(saida, f, ensure_ascii=False, indent=2)

        import os
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        self.stdout.write(self.style.SUCCESS(
            f'\nOK — {len(atendimentos_out)} atendimentos salvos em {out_path} ({size_mb:.2f} MB)'
        ))
        self.stdout.write(self.style.WARNING(
            'LGPD: arquivo anonimizado mas contem texto livre de clientes reais. NAO commitar.'
        ))
