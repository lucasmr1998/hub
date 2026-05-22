# -*- coding: utf-8 -*-
"""
Recupera a midia de mensagens antigas do Inbox que foram registradas ANTES do
fix de midia (quando o JSON cru do WhatsApp caia no campo `conteudo` e o
arquivo nao era baixado).

Pra cada mensagem cujo `conteudo` ainda e o objeto de midia serializado:
  1. Sanitiza o `conteudo` pro label limpo (📷 Imagem / 📎 arquivo).
  2. Se o fileEncSHA256 estiver no mapa MSGID_POR_SHA, baixa o arquivo
     decriptado no Uazapi e anexa ao campo `arquivo`.

One-off pos-deploy. Rodar no EasyPanel:
    python manage.py recuperar_midia_inbox --tenant=tr-carrion
"""
import json

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Recupera midia de mensagens antigas do Inbox (sanitiza + baixa arquivo).'

    # messageid do WhatsApp por prefixo de fileEncSHA256 — extraido das
    # execucoes do N8N (mensagens nao guardavam o messageid na epoca).
    MSGID_POR_SHA = {
        'oBt1llNLox': '3A43DFADC719D4484C3B',   # Flavia — RG/CNH frente (JPEG)
        '1g6gOH5ENy': '3A83D4FB09E245464187',   # Flavia — e-CNH PDF (frente-tentativa + verso)
    }

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='tr-carrion', help='slug do tenant')
        parser.add_argument('--dry-run', action='store_true', help='so mostra, nao grava')

    def handle(self, *args, **opts):
        from apps.sistema.models import Tenant
        from apps.inbox.models import Mensagem
        from apps.integracoes.models import IntegracaoAPI
        from apps.integracoes.services.uazapi import UazapiService
        from apps.integracoes.views_n8n_webhook import _sanitizar_conteudo_midia, _ext_de_mime

        dry = opts['dry_run']
        tenant = Tenant.objects.filter(slug=opts['tenant']).first()
        if not tenant:
            self.stderr.write(f'Tenant {opts["tenant"]!r} nao encontrado.')
            return

        integ = IntegracaoAPI.objects.filter(tenant=tenant, tipo='uazapi', ativa=True).first()
        svc = UazapiService(integracao=integ) if integ else None
        if not svc:
            self.stdout.write('AVISO: sem integracao uazapi ativa — so vou sanitizar, sem baixar arquivo.')

        qs = Mensagem.all_tenants.filter(tenant=tenant).filter(conteudo__startswith='{')
        total, sanit, baixados = 0, 0, 0
        for msg in qs:
            raw = (msg.conteudo or '').strip()
            if '"mimetype"' not in raw and '"directPath"' not in raw:
                continue
            try:
                obj = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                continue
            total += 1

            novo_c, novo_t, url, nome = _sanitizar_conteudo_midia(
                raw, msg.tipo_conteudo, msg.arquivo_url, msg.arquivo_nome)
            sha = str(obj.get('fileEncSHA256') or '')
            mid = next((v for k, v in self.MSGID_POR_SHA.items() if sha.startswith(k)), None)

            arq_status = 'sem msgid'
            if dry:
                arq_status = f'baixaria ({mid})' if (mid and svc) else 'sem msgid'
            elif mid and svc and not msg.arquivo:
                try:
                    conteudo_bytes, mime = svc.baixar_midia(mid)
                    if conteudo_bytes:
                        msg.arquivo.save(f'{mid}{_ext_de_mime(mime)}',
                                         ContentFile(conteudo_bytes), save=False)
                        msg.arquivo_tamanho = len(conteudo_bytes)
                        arq_status = f'baixado ({len(conteudo_bytes)} bytes)'
                        baixados += 1
                    else:
                        arq_status = 'download vazio'
                except Exception as e:
                    arq_status = f'erro: {e}'
            elif msg.arquivo:
                arq_status = 'ja tinha arquivo'

            if not dry:
                msg.conteudo = novo_c
                msg.tipo_conteudo = novo_t
                msg.arquivo_nome = nome[:255]
                msg.save(update_fields=['conteudo', 'tipo_conteudo', 'arquivo_nome',
                                        'arquivo', 'arquivo_tamanho'])
                sanit += 1

            self.stdout.write(f'  msg {msg.id} [conversa {msg.conversa_id}]: '
                              f'{novo_c!r} | arquivo: {arq_status}')

        prefixo = '[DRY-RUN] ' if dry else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefixo}{total} mensagens de midia | {sanit} sanitizadas | {baixados} arquivos baixados'))
