"""
Varredura de codigo: garante que o resto do sistema respeita o contrato do
modulo People.

Existe porque as duas regras mais importantes do modulo nao sao verificaveis em
tempo de execucao a partir de dentro dele:

1. A guarda de `situacao` no model pega `save()`, mas NAO pega
   `queryset.update(situacao=...)`, que nao passa por save(). Trigger de
   Postgres resolveria, mas o repo nao tem precedente disso e o custo de
   manutencao e alto. Uma varredura em CI e barata e pega o caso real: alguem
   com pressa, em outro app, meses depois.

2. O dedup so protege quem passa por `registrar_colaborador`. Criar
   `Colaborador` direto em outra Tool fura a regra de fonte unica sem que nada
   reclame, e a duplicata so aparece num relatorio errado semanas depois.

Se um destes testes falhar, a correcao quase nunca e adicionar excecao aqui: e
usar o servico.
"""
import re
from pathlib import Path

import pytest


RAIZ_APPS = Path(__file__).resolve().parent.parent / 'apps'

# Onde cada coisa pode acontecer
SO_NOS_SERVICOS = 'apps/people/services'
SO_DENTRO_DE_PEOPLE = 'apps/people'

PADRAO_UPDATE_SITUACAO = re.compile(r'\.update\([^)]*\bsituacao\s*=')
PADRAO_CRIACAO_DIRETA = re.compile(
    r'Colaborador\.(objects|all_tenants)\.(create|bulk_create|get_or_create|update_or_create)\b'
)
PADRAO_CONSTRUTOR = re.compile(r'(?<!class )\bColaborador\s*\(')
PADRAO_FILTRO_SITUACAO = re.compile(r'\.(filter|exclude)\([^)]*\bsituacao\s*=')


def _arquivos_python():
    for caminho in RAIZ_APPS.rglob('*.py'):
        partes = caminho.parts
        if '__pycache__' in partes or 'migrations' in partes:
            continue
        yield caminho


def _relativo(caminho):
    return caminho.as_posix().split('/gerenciador_vendas/')[-1]


def _varrer(padrao, permitido_em):
    """Retorna [(arquivo, linha, texto)] fora do caminho permitido."""
    achados = []
    for caminho in _arquivos_python():
        rel = _relativo(caminho)
        if permitido_em in rel:
            continue
        try:
            texto = caminho.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        if 'Colaborador' not in texto and 'situacao' not in texto:
            continue
        for numero, linha in enumerate(texto.splitlines(), start=1):
            despido = linha.strip()
            if despido.startswith('#') or despido.startswith('"""') or despido.startswith("'''"):
                continue
            if padrao.search(linha):
                achados.append((rel, numero, despido[:100]))
    return achados


def _formatar(achados):
    return '\n'.join(f'  {arq}:{num}  {txt}' for arq, num, txt in achados)


def test_ninguem_muda_situacao_por_update_cru():
    """
    `queryset.update()` nao passa pelo save(), entao escapa da guarda e nao gera
    historico nem telemetria. A transicao fica invisivel: o card se move no
    board e ninguem sabe quem moveu, quando, nem por que.
    """
    achados = _varrer(PADRAO_UPDATE_SITUACAO, SO_NOS_SERVICOS)
    assert not achados, (
        'Mudanca de situacao por update() cru, fora de apps/people/services/.\n'
        'Use mover_situacao(), que valida a transicao e grava historico.\n'
        + _formatar(achados)
    )


def test_ninguem_cria_colaborador_fora_do_servico():
    """
    Criar direto pula o dedup, e a duplicata so aparece num relatorio errado
    semanas depois. Use registrar_colaborador(), que pesquisa antes de criar.
    """
    achados = _varrer(PADRAO_CRIACAO_DIRETA, SO_NOS_SERVICOS)
    assert not achados, (
        'Criacao de Colaborador fora de apps/people/services/.\n'
        'Use registrar_colaborador(), que tem o dedup embutido.\n'
        + _formatar(achados)
    )


def test_ninguem_instancia_colaborador_fora_do_servico():
    achados = _varrer(PADRAO_CONSTRUTOR, SO_NOS_SERVICOS)
    assert not achados, (
        'Instanciacao de Colaborador fora de apps/people/services/.\n'
        + _formatar(achados)
    )


def test_ninguem_filtra_por_situacao_fora_de_people():
    """
    Se cada Tool escrever seu proprio filter(situacao=...), o vocabulario racha:
    uma considera "em experiencia" so quem esta em experiencia, outra inclui
    admissao no mesmo conceito, e duas telas passam a discordar. E exatamente o
    defeito que a reconstrucao veio corrigir.

    Use as funcoes de apps/people/consultas.py.
    """
    achados = _varrer(PADRAO_FILTRO_SITUACAO, SO_DENTRO_DE_PEOPLE)
    assert not achados, (
        'Filtro por situacao fora de apps/people/.\n'
        'Use as consultas nomeadas de apps.people.consultas.\n'
        + _formatar(achados)
    )


# ──────────────────────────────────────────────
# A varredura precisa funcionar de verdade
# ──────────────────────────────────────────────

def test_a_varredura_acha_o_que_deveria_achar():
    """
    Meta teste. Uma varredura quebrada passa calada e da falsa seguranca, que e
    pior que nao ter varredura nenhuma.
    """
    assert PADRAO_UPDATE_SITUACAO.search('Colaborador.objects.filter(pk=1).update(situacao="x")')
    assert PADRAO_CRIACAO_DIRETA.search('Colaborador.objects.create(nome_completo="x")')
    assert PADRAO_CRIACAO_DIRETA.search('Colaborador.all_tenants.get_or_create(cpf="1")')
    assert PADRAO_CONSTRUTOR.search('col = Colaborador(tenant=t)')
    assert PADRAO_FILTRO_SITUACAO.search('qs.filter(situacao="efetivado")')
    assert PADRAO_FILTRO_SITUACAO.search('qs.exclude(situacao="desligado")')


def test_a_varredura_nao_acusa_o_que_e_legitimo():
    assert not PADRAO_CONSTRUTOR.search('class Colaborador(TenantMixin):')
    assert not PADRAO_UPDATE_SITUACAO.search('col.save(update_fields=["cargo"])')
    assert not PADRAO_FILTRO_SITUACAO.search('qs.filter(unidade=u)')
    # tipagem e anotacao nao sao instanciacao
    assert not PADRAO_CRIACAO_DIRETA.search('def f(c: Colaborador) -> Colaborador:')


def test_a_varredura_realmente_le_arquivos():
    """Se o caminho da raiz mudar, os testes acima passariam por nao achar nada."""
    arquivos = list(_arquivos_python())
    assert len(arquivos) > 50, f'So {len(arquivos)} arquivos varridos, caminho errado?'
    assert any('apps/people/services/colaboradores.py' in _relativo(a) for a in arquivos)
