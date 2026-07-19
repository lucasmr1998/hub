"""Sincroniza os planos e vencimentos da PÁGINA WEB de cadastro com o que o
bot do WhatsApp realmente usa.

Fonte da verdade = config das RegraValidacao do ia_validador:
  - 'escolha_plano'  → extractor_config.opcoes/descricao_opcoes, chaveado pelo
                       id do plano no RP/HubSoft (vira lead.id_plano_rp)
  - 'dia_vencimento' → extractor_config.opcoes, chaveado pelo id do vencimento
                       no RP (vira lead.id_dia_vencimento)

Mapeamento web → lead (vendas_web/models.py: CadastroCliente.gerar_lead):
  PlanoInternet.id_sistema_externo  → lead.id_plano_rp
  OpcaoVencimento.descricao         → lead.id_dia_vencimento

Por isso aqui gravamos o id do RP em PlanoInternet.id_sistema_externo e em
OpcaoVencimento.descricao — assim a venda pela web cai no MESMO plano/vencimento
do HubSoft que a venda pelo WhatsApp.

Uso:
    python manage.py sincronizar_planos_bot            # aplica
    python manage.py sincronizar_planos_bot --dry-run  # só mostra
"""
import re
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from ia_validador.models import RegraValidacao
from vendas_web.models import PlanoInternet, OpcaoVencimento, ConfiguracaoCadastro


def _parse_preco(label):
    m = re.search(r'R\$\s*([\d.]+,\d{2})', label or '')
    if not m:
        return None
    return Decimal(m.group(1).replace('.', '').replace(',', '.'))


def _parse_velocidade(texto):
    """Retorna velocidade em Mbps a partir de '300MB', '1GB', '1 Giga', '2G'."""
    t = (texto or '').lower()
    m = re.search(r'(\d+)\s*(g|giga|gb)', t)
    if m:
        return int(m.group(1)) * 1000
    m = re.search(r'(\d+)\s*(m|mb|mega)', t)
    if m:
        return int(m.group(1))
    return None


def _nome_plano(velocidade):
    if velocidade and velocidade >= 1000 and velocidade % 1000 == 0:
        return f'Fibra {velocidade // 1000} Giga'
    if velocidade:
        return f'Fibra {velocidade} Mega'
    return 'Plano de Internet'


class Command(BaseCommand):
    help = 'Sincroniza planos/vencimentos da página web com os do bot WhatsApp'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Só mostra o que faria')

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options['dry_run']
        if dry:
            self.stdout.write(self.style.WARNING('DRY-RUN — nada será gravado'))

        # ── PLANOS ──────────────────────────────────────────────────────────
        regra_plano = RegraValidacao.objects.filter(question_id='escolha_plano').first()
        if not regra_plano:
            self.stdout.write(self.style.ERROR("Regra 'escolha_plano' não encontrada."))
            return

        cfg = regra_plano.extractor_config or {}
        descricoes = cfg.get('descricao_opcoes', {})
        opcoes = cfg.get('opcoes', {})

        self.stdout.write(self.style.MIGRATE_HEADING('Planos (fonte: bot escolha_plano)'))
        planos_parse = []
        for rp_id, label in descricoes.items():
            preco = _parse_preco(label)
            # velocidade: tenta no label, depois nos aliases
            vel = _parse_velocidade(label)
            if not vel:
                for alias in opcoes.get(rp_id, []):
                    vel = _parse_velocidade(alias)
                    if vel:
                        break
            planos_parse.append((rp_id, label, vel, preco))

        # ordem de exibição por preço
        planos_parse.sort(key=lambda x: (x[3] or Decimal('0')))
        for ordem, (rp_id, label, vel, preco) in enumerate(planos_parse, start=1):
            nome = _nome_plano(vel)
            self.stdout.write(
                f'  rp={rp_id}  {nome}  {vel or "?"}Mbps  R$ {preco if preco is not None else "?"}'
            )
            if dry:
                continue
            # descrição p/ o card: tira o "(R$ ..)" redundante (o preço já é exibido)
            descricao = re.sub(r'\s*\(R\$[^)]*\)', '', label or '').strip()
            # Só DADOS (preço/nome/velocidade) são sincronizados do bot.
            dados = {
                'nome': nome,
                'descricao': descricao,
                'velocidade_download': vel or 0,
                'velocidade_upload': vel or 0,
                'valor_mensal': preco if preco is not None else Decimal('0'),
            }
            existente = PlanoInternet.objects.filter(id_sistema_externo=str(rp_id)).first()
            if existente:
                # NÃO mexe em `ativo` nem em `ordem_exibicao`: a vitrine da página
                # web é curada manualmente no admin (pode diferir do bot, ex.: plano
                # web-only "1G + Ponto Adicional", ou esconder 300/2G).
                for k, v in dados.items():
                    setattr(existente, k, v)
                existente.save(update_fields=list(dados.keys()))
            else:
                # Plano novo no bot entra visível por padrão (admin esconde se quiser)
                PlanoInternet.objects.create(
                    id_sistema_externo=str(rp_id), ativo=True, ordem_exibicao=ordem, **dados,
                )

        # ── VENCIMENTOS ─────────────────────────────────────────────────────
        regra_venc = RegraValidacao.objects.filter(question_id='dia_vencimento').first()
        if not regra_venc:
            self.stdout.write(self.style.ERROR("Regra 'dia_vencimento' não encontrada."))
            return

        venc_opcoes = (regra_venc.extractor_config or {}).get('opcoes', {})
        self.stdout.write(self.style.MIGRATE_HEADING('Vencimentos (fonte: bot dia_vencimento)'))
        dias_parse = []
        for rp_id, aliases in venc_opcoes.items():
            dia = None
            for alias in aliases:
                m = re.search(r'dia\s*(\d+)', str(alias).lower())
                if m:
                    dia = int(m.group(1))
                    break
            if dia is None:
                # fallback: maior número "puro" que não seja índice de menu (1-4)
                nums = [int(a) for a in aliases if str(a).isdigit() and int(a) > 4]
                dia = max(nums) if nums else None
            if dia is None:
                self.stdout.write(self.style.WARNING(f'  rp={rp_id}: dia indefinido — pulei'))
                continue
            dias_parse.append((rp_id, dia))

        dias_parse.sort(key=lambda x: x[1])
        rp_ids_web = []
        for ordem, (rp_id, dia) in enumerate(dias_parse, start=1):
            self.stdout.write(f'  rp={rp_id}  → dia {dia}')
            if dry:
                continue
            venc, _ = OpcaoVencimento.objects.update_or_create(
                descricao=str(rp_id),   # vira lead.id_dia_vencimento
                defaults={
                    'dia_vencimento': dia,
                    'ordem_exibicao': ordem,
                    'ativo': True,
                },
            )
            rp_ids_web.append(str(rp_id))

        if not dry and rp_ids_web:
            obsoletos = OpcaoVencimento.objects.exclude(descricao__in=rp_ids_web)
            n = obsoletos.update(ativo=False)
            if n:
                self.stdout.write(f'  {n} vencimento(s) fora do bot → desativados')

        # ── CONFIG DA PÁGINA (cria default se faltar) ───────────────────────
        if not dry and not ConfiguracaoCadastro.objects.filter(ativo=True).exists():
            ConfiguracaoCadastro.objects.create(ativo=True)
            self.stdout.write('  ConfiguracaoCadastro padrão criada (não existia)')

        if dry:
            transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS('Planos/vencimentos sincronizados com o bot.'))
