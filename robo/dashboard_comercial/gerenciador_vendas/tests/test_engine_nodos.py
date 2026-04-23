"""
Testes unitarios do engine de fluxos — por tipo de nodo.

Foco: traversal, branches (true/false), comportamento de pausa, avaliacao de
condicoes, injecao de contexto. Chamadas LLM reais sao mockadas.

Cobertura:
- ContextoLogado (wrapper)
- Nodo entrada
- Nodo condicao (simples e composta)
- Nodo acao (sucesso e erro com branch)
- Nodo finalizacao (motivo + interpolacao)
- Nodo questao (sem IA)
- _seguir_conexoes (default, true, false, branch_forcado)
"""
import pytest
from unittest.mock import patch

from apps.sistema.middleware import set_current_tenant
from apps.comercial.atendimento.models import (
    FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento,
    AtendimentoFluxo, LogFluxoAtendimento,
)
from apps.comercial.atendimento import engine as eng
from apps.comercial.atendimento.engine_contexto import ContextoLogado

from tests.factories import (
    TenantFactory, ConfigEmpresaFactory, LeadProspectoFactory,
)


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════

def criar_fluxo_simples(tenant, nome='Fluxo Teste'):
    return FluxoAtendimento.objects.create(
        tenant=tenant,
        nome=nome,
        canal='qualquer',
        ativo=True,
        status='ativo',
        modo_fluxo=True,
        max_tentativas=3,
    )


def criar_nodo(fluxo, tipo, **config):
    subtipo = config.pop('subtipo', 'default')
    return NodoFluxoAtendimento.objects.create(
        tenant=fluxo.tenant,
        fluxo=fluxo,
        tipo=tipo,
        subtipo=subtipo,
        configuracao=config or {},
    )


def conectar(origem, destino, tipo_saida='default'):
    return ConexaoNodoAtendimento.objects.create(
        tenant=origem.fluxo.tenant,
        fluxo=origem.fluxo,
        nodo_origem=origem,
        nodo_destino=destino,
        tipo_saida=tipo_saida,
    )


@pytest.fixture
def setup_flow(db):
    tenant = TenantFactory()
    set_current_tenant(tenant)
    ConfigEmpresaFactory(tenant=tenant)
    fluxo = criar_fluxo_simples(tenant)
    lead = LeadProspectoFactory.build(tenant=tenant)
    lead._skip_crm_signal = True
    lead._skip_automacao = True
    lead.save()
    atend = AtendimentoFluxo.objects.create(
        tenant=tenant, fluxo=fluxo, lead=lead,
        total_questoes=0, max_tentativas=3,
    )
    return {'tenant': tenant, 'fluxo': fluxo, 'lead': lead, 'atend': atend}


# ══════════════════════════════════════════════════════════════════
# ContextoLogado
# ══════════════════════════════════════════════════════════════════

class TestContextoLogado:

    def test_comportamento_dict(self):
        c = ContextoLogado({'a': 1})
        c['b'] = 2
        assert c['a'] == 1
        assert c['b'] == 2
        assert 'a' in c
        assert len(c) == 2
        assert set(c.keys()) == {'a', 'b'}

    def test_spread_funciona(self):
        c = ContextoLogado({'a': 1})
        d = {**c, 'b': 2}
        assert d == {'a': 1, 'b': 2}

    def test_loga_set(self):
        c = ContextoLogado({'a': 1})
        c.set_nodo_atual(10)
        c['b'] = 'x'
        eventos = c.historico()
        assert len(eventos) == 1
        assert eventos[0]['op'] == 'set'
        assert eventos[0]['chave'] == 'b'
        assert eventos[0]['nodo'] == 10

    def test_nao_loga_valor_igual(self):
        c = ContextoLogado({'a': 1})
        c['a'] = 1  # mesmo valor
        assert c.historico() == []

    def test_loga_del(self):
        c = ContextoLogado({'a': 1})
        c.set_nodo_atual(20)
        del c['a']
        eventos = c.historico()
        assert eventos[0]['op'] == 'del'

    def test_historico_por_nodo(self):
        c = ContextoLogado()
        c.set_nodo_atual(1)
        c['a'] = 1
        c.set_nodo_atual(2)
        c['b'] = 2
        assert len(c.historico_por_nodo(1)) == 1
        assert len(c.historico_por_nodo(2)) == 1


# ══════════════════════════════════════════════════════════════════
# Nodo entrada
# ══════════════════════════════════════════════════════════════════

class TestNodoEntrada:

    def test_passa_direto(self, setup_flow):
        fluxo = setup_flow['fluxo']
        atend = setup_flow['atend']
        entrada = criar_nodo(fluxo, 'entrada')
        final = criar_nodo(fluxo, 'finalizacao', mensagem_final='Fim')
        conectar(entrada, final)

        resultado = eng.iniciar_fluxo_visual(atend)
        assert resultado['tipo'] == 'finalizado'


# ══════════════════════════════════════════════════════════════════
# Nodo condicao
# ══════════════════════════════════════════════════════════════════

class TestNodoCondicao:

    def test_condicao_simples_true(self, setup_flow):
        lead = setup_flow['lead']
        lead.score_qualificacao = 8
        lead.save(update_fields=['score_qualificacao'])

        fluxo = setup_flow['fluxo']
        atend = setup_flow['atend']
        atend.refresh_from_db()

        entrada = criar_nodo(fluxo, 'entrada')
        # Usar lead_score (campo direto do contexto) ou var para evitar acesso atraves do objeto lead
        cond = criar_nodo(fluxo, 'condicao',
                          campo='lead_score', operador='maior_igual', valor='7')
        fim_true = criar_nodo(fluxo, 'finalizacao', mensagem_final='Quente')
        fim_false = criar_nodo(fluxo, 'finalizacao', mensagem_final='Frio')
        conectar(entrada, cond)
        conectar(cond, fim_true, 'true')
        conectar(cond, fim_false, 'false')

        resultado = eng.iniciar_fluxo_visual(atend)
        assert resultado['mensagem'] == 'Quente'

    def test_condicao_composta_and(self, setup_flow):
        fluxo = setup_flow['fluxo']
        contexto = ContextoLogado({'score': 8, 'origem': 'whatsapp'})
        nodo = criar_nodo(fluxo, 'condicao')
        nodo.configuracao = {
            'operador_logico': 'and',
            'condicoes': [
                {'campo': 'score', 'operador': 'maior_igual', 'valor': '7'},
                {'campo': 'origem', 'operador': 'igual', 'valor': 'whatsapp'},
            ],
        }
        nodo.save()

        assert eng._avaliar_condicao(nodo, contexto) is True

    def test_condicao_composta_and_falha(self, setup_flow):
        fluxo = setup_flow['fluxo']
        contexto = ContextoLogado({'score': 3, 'origem': 'whatsapp'})
        nodo = criar_nodo(fluxo, 'condicao')
        nodo.configuracao = {
            'operador_logico': 'and',
            'condicoes': [
                {'campo': 'score', 'operador': 'maior_igual', 'valor': '7'},
                {'campo': 'origem', 'operador': 'igual', 'valor': 'whatsapp'},
            ],
        }
        nodo.save()

        assert eng._avaliar_condicao(nodo, contexto) is False

    def test_condicao_composta_or(self, setup_flow):
        fluxo = setup_flow['fluxo']
        contexto = ContextoLogado({'score': 3, 'origem': 'whatsapp'})
        nodo = criar_nodo(fluxo, 'condicao')
        nodo.configuracao = {
            'operador_logico': 'or',
            'condicoes': [
                {'campo': 'score', 'operador': 'maior_igual', 'valor': '7'},
                {'campo': 'origem', 'operador': 'igual', 'valor': 'whatsapp'},
            ],
        }
        nodo.save()

        assert eng._avaliar_condicao(nodo, contexto) is True

    def test_operador_vazio(self, setup_flow):
        fluxo = setup_flow['fluxo']
        contexto = ContextoLogado({'nome': ''})
        nodo = criar_nodo(fluxo, 'condicao', campo='nome', operador='vazio', valor='')
        assert eng._avaliar_condicao(nodo, contexto) is True

        contexto2 = ContextoLogado({'nome': 'Maria'})
        assert eng._avaliar_condicao(nodo, contexto2) is False

    def test_operador_inicia_com(self, setup_flow):
        fluxo = setup_flow['fluxo']
        contexto = ContextoLogado({'texto': 'Dr. Joao Silva'})
        nodo = criar_nodo(fluxo, 'condicao',
                          campo='texto', operador='inicia_com', valor='dr.')
        assert eng._avaliar_condicao(nodo, contexto) is True


# ══════════════════════════════════════════════════════════════════
# Nodo acao — branch erro
# ══════════════════════════════════════════════════════════════════

class TestNodoAcao:

    def test_branch_erro_em_falha(self, setup_flow):
        fluxo = setup_flow['fluxo']
        atend = setup_flow['atend']

        entrada = criar_nodo(fluxo, 'entrada')
        acao = NodoFluxoAtendimento.objects.create(
            tenant=fluxo.tenant, fluxo=fluxo, tipo='acao', subtipo='webhook',
            configuracao={'url': 'http://invalid-host-xxxxxxxx-nao-existe.local'},
        )
        fim_ok = criar_nodo(fluxo, 'finalizacao', mensagem_final='OK')
        fim_err = criar_nodo(fluxo, 'finalizacao', mensagem_final='ERRO')
        conectar(entrada, acao)
        conectar(acao, fim_ok, 'default')
        conectar(acao, fim_err, 'erro')

        # Patch: fazer webhook falhar
        with patch('apps.comercial.atendimento.engine.requests.post', side_effect=Exception('fail')):
            resultado = eng.iniciar_fluxo_visual(atend)

        # Branch erro deve ter sido tomado
        assert resultado['mensagem'] == 'ERRO'


# ══════════════════════════════════════════════════════════════════
# Nodo finalizacao
# ══════════════════════════════════════════════════════════════════

class TestNodoFinalizacao:

    def test_motivo_configuravel(self, setup_flow):
        fluxo = setup_flow['fluxo']
        atend = setup_flow['atend']

        entrada = criar_nodo(fluxo, 'entrada')
        fim = criar_nodo(fluxo, 'finalizacao',
                        mensagem_final='Vendido!',
                        motivo_finalizacao='ganho')
        conectar(entrada, fim)

        eng.iniciar_fluxo_visual(atend)
        atend.refresh_from_db()
        assert atend.motivo_finalizacao == 'ganho'

    def test_interpolacao_mensagem_final(self, setup_flow):
        fluxo = setup_flow['fluxo']
        atend = setup_flow['atend']

        entrada = criar_nodo(fluxo, 'entrada')
        fim = criar_nodo(fluxo, 'finalizacao',
                        mensagem_final='Obrigado, {{lead_nome}}!')
        conectar(entrada, fim)

        resultado = eng.iniciar_fluxo_visual(atend)
        assert setup_flow['lead'].nome_razaosocial in resultado['mensagem']


# ══════════════════════════════════════════════════════════════════
# _seguir_conexoes
# ══════════════════════════════════════════════════════════════════

class TestSeguirConexoes:

    def test_branch_forcado_encontra(self, setup_flow):
        fluxo = setup_flow['fluxo']
        atend = setup_flow['atend']

        entrada = criar_nodo(fluxo, 'entrada')
        fim_categoria = criar_nodo(fluxo, 'finalizacao', mensagem_final='CAT_A')
        fim_default = criar_nodo(fluxo, 'finalizacao', mensagem_final='DEFAULT')
        conectar(entrada, fim_categoria, 'cat_a')
        conectar(entrada, fim_default, 'default')

        contexto = ContextoLogado({})
        resultado = eng._seguir_conexoes(atend, entrada, contexto, branch_forcado='cat_a')
        assert resultado['mensagem'] == 'CAT_A'

    def test_branch_forcado_fallback_default(self, setup_flow):
        fluxo = setup_flow['fluxo']
        atend = setup_flow['atend']

        entrada = criar_nodo(fluxo, 'entrada')
        fim = criar_nodo(fluxo, 'finalizacao', mensagem_final='DEFAULT')
        conectar(entrada, fim, 'default')

        contexto = ContextoLogado({})
        # Tipo_saida inexistente deve cair no default
        resultado = eng._seguir_conexoes(atend, entrada, contexto, branch_forcado='inexistente')
        assert resultado['mensagem'] == 'DEFAULT'


# ══════════════════════════════════════════════════════════════════
# _resolver_campo_contexto — dot notation + ContextoLogado
#
# Bug em producao (23/04/2026, fluxo v3 FATEPI): toda condicao `var.X == Y`
# retornava false porque isinstance(ContextoLogado, dict) eh False, o loop
# caia no fallback e contexto.get('var_X') devolvia None. Afetou todo
# fluxo que usa ia_classificador/ia_extrator antes de condicao.
# ══════════════════════════════════════════════════════════════════

class TestResolverCampoContexto:

    def test_chave_simples_dict(self):
        contexto = {'nome': 'Maria'}
        assert eng._resolver_campo_contexto('nome', contexto) == 'Maria'

    def test_chave_simples_contexto_logado(self):
        contexto = ContextoLogado({'nome': 'Maria'})
        assert eng._resolver_campo_contexto('nome', contexto) == 'Maria'

    def test_dot_notation_var_em_contexto_logado(self):
        """Regressao do bug: var.X tem que resolver quando contexto eh ContextoLogado."""
        contexto = ContextoLogado({
            'var': {'validacao_curso': 'curso_valido', 'tipo_fallback': 'outro'},
        })
        assert eng._resolver_campo_contexto('var.validacao_curso', contexto) == 'curso_valido'
        assert eng._resolver_campo_contexto('var.tipo_fallback', contexto) == 'outro'

    def test_dot_notation_var_em_dict_legacy(self):
        """Nao quebrar caminho antigo com dict puro."""
        contexto = {'var': {'validacao_curso': 'curso_valido'}}
        assert eng._resolver_campo_contexto('var.validacao_curso', contexto) == 'curso_valido'

    def test_dot_notation_chave_inexistente_retorna_none(self):
        contexto = ContextoLogado({'var': {'outra': 'x'}})
        assert eng._resolver_campo_contexto('var.validacao_curso', contexto) is None

    def test_flat_key_fallback(self):
        """Quando nao ha estrutura aninhada, aceitar var_validacao_curso como chave flat."""
        contexto = ContextoLogado({'var_validacao_curso': 'curso_valido'})
        assert eng._resolver_campo_contexto('var.validacao_curso', contexto) == 'curso_valido'


class TestCondicaoComVarContextoLogado:
    """Nivel acima: garantir que o roteamento por var.X numa condicao funciona.
    Cobre a classe de bug que deixou o fluxo FATEPI v3 preso — candidato
    com classificacao valida caindo no branch 'false' da condicao.
    """

    def test_condicao_var_valida_retorna_true(self, setup_flow):
        fluxo = setup_flow['fluxo']
        contexto = ContextoLogado({
            'var': {'validacao_curso': 'curso_valido'},
        })
        nodo = criar_nodo(
            fluxo, 'condicao',
            campo='var.validacao_curso',
            operador='igual',
            valor='curso_valido',
        )
        assert eng._avaliar_condicao(nodo, contexto) is True

    def test_condicao_var_invalida_retorna_false(self, setup_flow):
        fluxo = setup_flow['fluxo']
        contexto = ContextoLogado({
            'var': {'validacao_curso': 'curso_invalido'},
        })
        nodo = criar_nodo(
            fluxo, 'condicao',
            campo='var.validacao_curso',
            operador='igual',
            valor='curso_valido',
        )
        assert eng._avaliar_condicao(nodo, contexto) is False

    def test_roteamento_branch_true_com_var_valida(self, setup_flow):
        """E2E micro: entrada -> condicao(var.X == val) -> true/false.
        Mesmo formato de nodo que quebrou no FATEPI v3.
        """
        fluxo = setup_flow['fluxo']
        atend = setup_flow['atend']

        entrada = criar_nodo(fluxo, 'entrada')
        cond = criar_nodo(
            fluxo, 'condicao',
            campo='var.validacao_curso',
            operador='igual',
            valor='curso_valido',
        )
        fim_true = criar_nodo(fluxo, 'finalizacao', mensagem_final='CURSO_OK')
        fim_false = criar_nodo(fluxo, 'finalizacao', mensagem_final='CURSO_INVALIDO')
        conectar(entrada, cond)
        conectar(cond, fim_true, 'true')
        conectar(cond, fim_false, 'false')

        # Injetar var.validacao_curso via dados_respostas + reconstruir contexto
        atend.dados_respostas = {'variaveis': {'validacao_curso': 'curso_valido'}}
        atend.save(update_fields=['dados_respostas'])

        resultado = eng.iniciar_fluxo_visual(atend)
        assert resultado['mensagem'] == 'CURSO_OK', (
            f"Com validacao_curso=curso_valido devia rotear pro branch true. "
            f"Deu: {resultado}"
        )

    def test_roteamento_branch_false_com_var_invalida(self, setup_flow):
        fluxo = setup_flow['fluxo']
        atend = setup_flow['atend']

        entrada = criar_nodo(fluxo, 'entrada')
        cond = criar_nodo(
            fluxo, 'condicao',
            campo='var.validacao_curso',
            operador='igual',
            valor='curso_valido',
        )
        fim_true = criar_nodo(fluxo, 'finalizacao', mensagem_final='CURSO_OK')
        fim_false = criar_nodo(fluxo, 'finalizacao', mensagem_final='CURSO_INVALIDO')
        conectar(entrada, cond)
        conectar(cond, fim_true, 'true')
        conectar(cond, fim_false, 'false')

        atend.dados_respostas = {'variaveis': {'validacao_curso': 'curso_invalido'}}
        atend.save(update_fields=['dados_respostas'])

        resultado = eng.iniciar_fluxo_visual(atend)
        assert resultado['mensagem'] == 'CURSO_INVALIDO'
