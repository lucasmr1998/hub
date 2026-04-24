"""
Exporta um FluxoAtendimento como JSON autossuficiente.

Formato do output:
{
  "fluxo": {nome, canal, ativo, status, modo_fluxo, max_tentativas, ...},
  "nodos": [{id_original, tipo, subtipo, ordem, configuracao}, ...],
  "conexoes": [{id_origem, id_destino, tipo_saida}, ...]
}

IDs originais sao preservados so como chave — quem importa pode gerar
IDs novos. Configuracoes (prompts, categorias IA, etc) vem inteiras.

Uso:
    python manage.py exportar_fluxo <fluxo_id> > tests/fixtures/fluxo_X.json
    python manage.py exportar_fluxo <fluxo_id> --output tests/fixtures/fluxo_X.json

Serve pra gerar fixtures reproduziveis pra testes e2e.
"""
import json
from django.core.management.base import BaseCommand, CommandError

from apps.comercial.atendimento.models import (
    FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento,
)


class Command(BaseCommand):
    help = 'Exporta fluxo de atendimento como JSON (nodos + conexoes)'

    def add_arguments(self, parser):
        parser.add_argument('fluxo_id', type=int)
        parser.add_argument('--output', '-o', default=None,
                          help='Arquivo de saida (default: stdout)')
        parser.add_argument('--tenant-id', type=int, default=None,
                          help='Filtrar por tenant')

    def handle(self, *args, **opts):
        fid = opts['fluxo_id']
        qs = FluxoAtendimento.all_tenants.filter(id=fid)
        if opts['tenant_id']:
            qs = qs.filter(tenant_id=opts['tenant_id'])
        fluxo = qs.first()
        if not fluxo:
            raise CommandError(f'Fluxo {fid} nao encontrado')

        nodos = NodoFluxoAtendimento.all_tenants.filter(fluxo=fluxo).order_by('id')
        conexoes = ConexaoNodoAtendimento.all_tenants.filter(fluxo=fluxo).order_by('id')

        data = {
            'fluxo': {
                'nome': fluxo.nome,
                'descricao': fluxo.descricao or '',
                'canal': fluxo.canal,
                'tipo_fluxo': fluxo.tipo_fluxo,
                'ativo': fluxo.ativo,
                'status': fluxo.status,
                'modo_fluxo': fluxo.modo_fluxo,
                'max_tentativas': fluxo.max_tentativas,
                'base_conhecimento_ativa': fluxo.base_conhecimento_ativa,
            },
            'nodos': [
                {
                    'id_original': n.id,
                    'tipo': n.tipo,
                    'subtipo': n.subtipo,
                    'ordem': n.ordem,
                    'configuracao': n.configuracao or {},
                } for n in nodos
            ],
            'conexoes': [
                {
                    'id_origem': c.nodo_origem_id,
                    'id_destino': c.nodo_destino_id,
                    'tipo_saida': c.tipo_saida,
                } for c in conexoes
            ],
        }

        payload = json.dumps(data, indent=2, ensure_ascii=False)

        if opts['output']:
            with open(opts['output'], 'w', encoding='utf-8') as f:
                f.write(payload)
            self.stdout.write(self.style.SUCCESS(
                f'Fluxo {fid} exportado: {len(data["nodos"])} nodos, '
                f'{len(data["conexoes"])} conexoes -> {opts["output"]}'
            ))
        else:
            self.stdout.write(payload)
