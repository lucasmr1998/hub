"""Fecha atendimento(s) (e a O.S. vinculada) via API interna do HubSoft.

Portado de migracao_megalink/fechar_atendimentos/fechar_atendimento_api.py.
Fluxo: POST /api/v1/atendimento/consultar/paginado/50 (busca=protocolo) → objeto
completo → modifica status_fechamento/motivo → POST /api/v1/atendimento/fechar.
Fechar o atendimento como "Resolvido" encerra a O.S. de instalação junto.

    manage.py hubsoft_fechar_atendimento --protocolo 2026... [--protocolo ...]
    manage.py hubsoft_fechar_atendimento --id 1354351 1354377   (resolve protocolo no banco)

Sem --executar é DRY-RUN (só mostra o que faria). Use --executar p/ fechar de fato.
"""
import datetime as _dt
import time

from django.core.management.base import BaseCommand

DESCRICAO_FECHAMENTO = 'atendimento e o.s abertas indevidamente'
ID_MOTIVO_FECHAMENTO = 224          # 'Normalizado sem intervenção técnica'
STATUS_FECHAMENTO = 'concluido'     # prefixo
ID_STATUS_RESOLVIDO = 3             # atendimento_status: Resolvido (= Concluído)
PERIODO_AMPLO_DIAS = 365
_MOTIVO_DESC = {224: 'Normalizado sem intervenção técnica'}

# Fechamento de O.S. (descoberto via captura CDP + diff com OS finalizada):
# POST /api/v1/ordem_servico/fechar?id={id} com o objeto da OS + status_fechamento
# + datas/horas executadas + motivo nos 3 campos (id_motivo_fechamento singular,
# motivo_fechamento objeto, motivos_fechamento[ obj+pivot ]) + tipo completo.
ID_MOTIVO_OS = 27                   # motivo_fechamento: 'OS CONCLUÍDA'
DESCRICAO_FECHAMENTO_OS = 'O.S. de instalacao aberta indevidamente em teste.'


class Command(BaseCommand):
    help = 'Fecha atendimento(s) + O.S. via API interna do HubSoft'

    def add_arguments(self, parser):
        parser.add_argument('--protocolo', action='append', default=[])
        parser.add_argument('--id', nargs='+', type=int, default=[],
                            help='ids de atendimento (resolve protocolo no banco)')
        parser.add_argument('--executar', action='store_true',
                            help='fecha de fato (sem isso é dry-run)')
        parser.add_argument('--conta-admin', action='store_true',
                            help='usa DELLINK_USUARIO/SENHA do .env da migração '
                                 '(conta com permissão de fechar atendimento)')

    def handle(self, *args, **o):
        from posvenda_hubsoft.services.ambiente import preparar_ambiente_webdriver
        preparar_ambiente_webdriver()
        from posvenda_hubsoft.webdriver.main_novo_servico import _conn

        # alvos = [(id_atendimento, protocolo)] — resolve ambos p/ fechar OS antes
        c = _conn('HUBSOFT'); cur = c.cursor()
        alvos = []
        if o['id']:
            cur.execute('SELECT id_atendimento, protocolo FROM atendimento '
                        'WHERE id_atendimento = ANY(%s)', (o['id'],))
            alvos += [(ida, str(p)) for ida, p in cur.fetchall()]
        if o['protocolo']:
            cur.execute('SELECT id_atendimento, protocolo FROM atendimento '
                        'WHERE protocolo = ANY(%s)', (o['protocolo'],))
            alvos += [(ida, str(p)) for ida, p in cur.fetchall()]
        c.close()
        if not alvos:
            self.stderr.write('informe --protocolo ou --id (não encontrados)'); return
        for ida, proto in alvos:
            self.stdout.write(f'  atendimento {ida} → protocolo {proto}')

        if not o['executar']:
            self.stdout.write(self.style.WARNING(
                f'DRY-RUN — fecharia {len(alvos)} atendimento(s) + suas O.S.\n'
                f'  O.S.→finalizado/concluido (motivo {ID_MOTIVO_OS}); '
                f'atendimento→Resolvido(3) (motivo {ID_MOTIVO_FECHAMENTO})\n'
                f'  use --executar p/ aplicar'))
            return

        import os as _os
        if o['conta_admin']:
            # conta com permissão de fechar atendimento — configurada no
            # .env.production do v2 (HUBSOFT_PAINEL_ADMIN_USUARIO/SENHA).
            u = _os.environ.get('HUBSOFT_PAINEL_ADMIN_USUARIO')
            s = _os.environ.get('HUBSOFT_PAINEL_ADMIN_SENHA')
            if not (u and s):
                self.stderr.write(
                    'HUBSOFT_PAINEL_ADMIN_USUARIO/SENHA não configurados no '
                    '.env.production. Adicione a conta com permissão de fechar.')
                return
            _os.environ['USUARIO'], _os.environ['SENHA'] = u, s
            self.stdout.write(f'  usando conta admin: {u}')

        from posvenda_hubsoft.api_interna.cliente_http import ClienteHTTP
        cli = ClienteHTTP(headless=True)
        cli.login()
        ok = falha = 0
        try:
            for ida, proto in alvos:
                t0 = time.time()
                try:
                    # 1) fecha as O.S. abertas do atendimento (pré-requisito)
                    for oid in self._os_abertas(ida):
                        self._fechar_os(cli, oid)
                        self.stdout.write(self.style.SUCCESS(f'  ✓ O.S. {oid} finalizada'))
                    # 2) fecha o atendimento
                    msg = self._fechar(cli, self._buscar(cli, proto))
                    ok += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ atend {proto} fechado ({int((time.time()-t0)*1000)}ms) {msg[:50]}'))
                except Exception as e:  # noqa: BLE001
                    falha += 1
                    self.stdout.write(self.style.ERROR(f'  ✗ {proto}: {e}'))
        finally:
            cli.close()
        self.stdout.write(self.style.SUCCESS(f'FIM. ✓{ok} ✗{falha}'))

    def _os_abertas(self, id_atendimento):
        from posvenda_hubsoft.webdriver.main_novo_servico import _conn
        c = _conn('HUBSOFT'); cur = c.cursor()
        cur.execute("SELECT id_ordem_servico FROM ordem_servico "
                    "WHERE id_atendimento=%s AND status<>'finalizado'", (id_atendimento,))
        ids = [r[0] for r in cur.fetchall()]; c.close()
        return ids

    def _carrega_row(self, tabela, idcol, idval):
        from posvenda_hubsoft.webdriver.main_novo_servico import _conn
        c = _conn('HUBSOFT'); cur = c.cursor()
        cur.execute(f'SELECT * FROM {tabela} WHERE {idcol}=%s', (idval,))
        cols = [d.name for d in cur.description]; row = cur.fetchone(); c.close()
        if not row:
            return {}
        return {k: (v.isoformat() + 'Z' if hasattr(v, 'isoformat') else v)
                for k, v in zip(cols, row)}

    def _fechar_os(self, cli, oid):
        import time as _t
        obj = (cli._get(f'/api/v1/ordem_servico/{oid}').json() or {}).get('ordem_servico') or {}
        if not obj:
            raise RuntimeError(f'O.S. {oid} não encontrada')
        if obj.get('status') == 'finalizado':
            return
        hoje = _t.strftime('%Y-%m-%d')
        mot = self._carrega_row('motivo_fechamento', 'id_motivo_fechamento', ID_MOTIVO_OS)
        mot_item = dict(mot); mot_item['pivot'] = {'id_ordem_servico': oid,
                                                   'id_motivo_fechamento': ID_MOTIVO_OS}
        obj.update({
            'status_fechamento': 'concluido',
            'descricao_fechamento': DESCRICAO_FECHAMENTO_OS,
            'data_inicio_executado': hoje, 'data_termino_executado': hoje,
            'hora_inicio_executado': '12:00:00', 'hora_termino_executado': '13:30:00',
            'utilizacao_equipamento': False,
            'id_motivo_fechamento': ID_MOTIVO_OS, 'motivo_fechamento': mot,
            'motivos_fechamento': [mot_item],
        })
        tipo = dict(obj.get('tipo_ordem_servico') or {})
        full = self._carrega_row('tipo_ordem_servico', 'id_tipo_ordem_servico',
                                 obj.get('id_tipo_ordem_servico'))
        for k, v in full.items():
            tipo.setdefault(k, v)
        obj['tipo_ordem_servico'] = tipo
        r = cli._post(f'/api/v1/ordem_servico/fechar?id={oid}', obj)
        j = r.json() if r.content else {}
        if not r.ok or j.get('status') != 'success':
            raise RuntimeError(f"fechar O.S. {oid}: {j.get('msg', r.text[:150])} "
                               f"{j.get('errors', '')}")

    def _buscar(self, cli, protocolo):
        hoje = _dt.datetime.now()
        inicio = hoje - _dt.timedelta(days=PERIODO_AMPLO_DIAS)
        body = {
            'usuario_abertura': None, 'usuarios_responsaveis': [],
            'tipo_data': 'data_cadastro', 'order_by': 'data_cadastro',
            'order_by_key': 'DESC',
            'data_inicio': inicio.strftime('%Y-%m-%dT00:00:00.000Z'),
            'data_fim': hoje.strftime('%Y-%m-%dT23:59:59.000Z'),
            'status_atendimento': [], 'tipo_pessoa': None,
            'disponibilidade_atendimento': [], 'destino': None,
            'fluxo_atendimento': [], 'etapas_fluxo': [], 'busca': str(protocolo),
        }
        r = cli._post('/api/v1/atendimento/consultar/paginado/50?page=1', body)
        if not r.ok:
            raise RuntimeError(f'paginado HTTP {r.status_code}: {r.text[:200]}')
        data = (r.json().get('atendimentos') or {}).get('data') or []
        if not data:
            raise RuntimeError(f'protocolo {protocolo} não encontrado')
        return data[0]

    def _motivo_para_tipo(self, tipo_id):
        """Motivo de fechamento válido p/ o tipo de atendimento (prefere 'concluí')."""
        from posvenda_hubsoft.webdriver.main_novo_servico import _conn
        c = _conn('HUBSOFT'); cur = c.cursor()
        cur.execute("""SELECT mfa.id_motivo_fechamento_atendimento, mfa.descricao
            FROM tipo_atendimento_motivo_fechamento j
            JOIN motivo_fechamento_atendimento mfa
              ON mfa.id_motivo_fechamento_atendimento=j.id_motivo_fechamento_atendimento
            WHERE j.id_tipo_atendimento=%s ORDER BY mfa.id_motivo_fechamento_atendimento""",
                    (tipo_id,))
        rows = cur.fetchall(); c.close()
        if not rows:
            return ID_MOTIVO_FECHAMENTO, _MOTIVO_DESC[ID_MOTIVO_FECHAMENTO]
        prefer = next((r for r in rows if 'conclu' in (r[1] or '').lower()), rows[0])
        return prefer[0], prefer[1]

    def _carrega_tipo(self, tipo_id):
        from posvenda_hubsoft.webdriver.main_novo_servico import _conn
        c = _conn('HUBSOFT'); cur = c.cursor()
        cur.execute("""SELECT id_tipo_atendimento, descricao, permite_multiplas_os,
                          contabilizar_sla, prazo_execucao, checklists,
                          quantidade_minima_descricao_fechamento, permite_avaliacao,
                          permite_vincular_atendimento, permite_notificar_cliente,
                          exibir_central, permissao_encerramento, destino,
                          id_setor_responsavel
                       FROM tipo_atendimento WHERE id_tipo_atendimento=%s""", (tipo_id,))
        cols = [d.name for d in cur.description]; row = cur.fetchone(); c.close()
        return dict(zip(cols, row)) if row else {}

    def _fechar(self, cli, atendimento_obj):
        obj = dict(atendimento_obj)
        obj['descricao_fechamento'] = DESCRICAO_FECHAMENTO
        obj['status_fechamento'] = STATUS_FECHAMENTO
        obj['id_atendimento_status'] = ID_STATUS_RESOLVIDO
        tipo_id = obj.get('id_tipo_atendimento')
        # motivo de fechamento precisa pertencer ao tipo do atendimento
        mid, mdesc = self._motivo_para_tipo(tipo_id)
        obj['id_motivo_fechamento_atendimento'] = mid
        if tipo_id:
            tipo_atual = dict(obj.get('tipo_atendimento') or {})
            for k, v in self._carrega_tipo(tipo_id).items():
                tipo_atual.setdefault(k, v)
            obj['tipo_atendimento'] = tipo_atual
        obj['motivo_fechamento_atendimento'] = {
            'id_motivo_fechamento_atendimento': mid, 'descricao': mdesc,
        }
        defaults = {
            'alertas': [], 'anexos': [], 'atendimento_mensagem': [], 'tarefas': [],
            'ligacao': [], 'disponibilidade_atendimento': [], 'checklists': None,
            'contato': None, 'diagnostico': None, 'email_contato': None,
            'fluxo_atendimento_etapa_item_count': 0, 'id_origem_contato': None,
            'id_revenda': None, 'id_setor_responsavel': None, 'ip_cadastro': '0.0.0.0',
            'nome_contato': None, 'telefone_contato': None, 'origem_contato': None,
            'push_notification_enviado': False, 'destino': 'usuario',
            'ordem_servico': {'data': []}, 'usuario_abertura': None,
            'usuario_fechamento': None,
        }
        for k, v in defaults.items():
            obj.setdefault(k, v)
        r = cli._post('/api/v1/atendimento/fechar', obj)
        if not r.ok:
            raise RuntimeError(f'fechar HTTP {r.status_code}: {r.text[:200]}')
        j = r.json()
        if j.get('status') != 'success':
            raise RuntimeError(f"status={j.get('status')} {j.get('msg','')[:200]}")
        return j.get('msg', '')
