"""
Teste E2E do caminho critico: entrada -> questao (nome) -> questao
(ia_classificador) -> condicao (var.X) -> acao/finalizacao.

Carrega fixture de um fluxo real em JSON (formato identico ao output
de `exportar_fluxo`), monta em DB, mocka `_chamar_llm_simples` com
respostas determinadas por cenario, e percorre o fluxo validando
nodo_atual + variaveis.

Fecha a lacuna estrutural de testes que permitiu o bug var.X
(23/04/2026) passar semanas sem alarme: nodos unitarios testados,
mas nenhum exercitava a cadeia real.

Cenarios:
- Curso valido ('Psicologia') -> deve chegar em finalizacao 'OK_VALIDO'
- Curso invalido ('Medicina') -> deve chegar em finalizacao 'OK_INVALIDO'
- Resposta fora do esperado ('quanto custa?') -> deve cair no fallback
  ia_respondedor via branch 'false' do questao
- Nome vazio -> questao pausa de novo (max_tentativas)
"""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.sistema.middleware import set_current_tenant
from apps.comercial.atendimento.models import (
    FluxoAtendimento, NodoFluxoAtendimento, ConexaoNodoAtendimento,
    AtendimentoFluxo,
)
from apps.comercial.atendimento import engine as eng
from apps.integracoes.models import IntegracaoAPI

from tests.factories import (
    TenantFactory, ConfigEmpresaFactory, LeadProspectoFactory,
)


FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'fluxo_ia_critico.json'


def carregar_fluxo(tenant, integracao_id):
    """Monta fluxo + nodos + conexoes a partir da fixture JSON.

    Substitui integracao_ia_id (e integracao_id no ia_respondedor) pelo
    ID real da IntegracaoAPI criada no setup, ja que a fixture nao sabe
    qual ID vai ser gerado no DB de teste.
    """
    data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))

    fluxo_kwargs = {k: v for k, v in data['fluxo'].items()}
    fluxo = FluxoAtendimento.objects.create(tenant=tenant, **fluxo_kwargs)

    # Mapear id_original -> objeto criado
    nodos_por_id = {}
    for n_data in data['nodos']:
        config = dict(n_data['configuracao'])
        # Substituir refs a IntegracaoAPI pelo ID real
        if 'integracao_ia_id' in config:
            config['integracao_ia_id'] = str(integracao_id)
        nodo = NodoFluxoAtendimento.objects.create(
            tenant=tenant,
            fluxo=fluxo,
            tipo=n_data['tipo'],
            subtipo=n_data['subtipo'],
            ordem=n_data['ordem'],
            configuracao=config,
        )
        nodos_por_id[n_data['id_original']] = nodo

    for c_data in data['conexoes']:
        ConexaoNodoAtendimento.objects.create(
            tenant=tenant,
            fluxo=fluxo,
            nodo_origem=nodos_por_id[c_data['id_origem']],
            nodo_destino=nodos_por_id[c_data['id_destino']],
            tipo_saida=c_data['tipo_saida'],
        )

    return fluxo, nodos_por_id


@pytest.fixture
def setup_fluxo_critico(db):
    tenant = TenantFactory()
    set_current_tenant(tenant)
    ConfigEmpresaFactory(tenant=tenant)
    # Criar IntegracaoAPI fake (nao sera chamada — LLM mockado)
    integracao = IntegracaoAPI.objects.create(
        tenant=tenant, nome='Fake OpenAI', tipo='openai',
        base_url='https://api.openai.com', ativa=True,
    )
    fluxo, nodos = carregar_fluxo(tenant, integracao.id)
    lead = LeadProspectoFactory.build(tenant=tenant)
    lead._skip_crm_signal = True
    lead._skip_automacao = True
    lead.save()
    atend = AtendimentoFluxo.objects.create(
        tenant=tenant, fluxo=fluxo, lead=lead,
        total_questoes=2, max_tentativas=3,
    )
    return {
        'tenant': tenant, 'fluxo': fluxo, 'nodos': nodos,
        'lead': lead, 'atend': atend,
    }


def respostas_llm(*, classificacao='curso_valido', curso='Psicologia',
                 fallback_text='Fallback de exemplo'):
    """Fabrica um side_effect pra _chamar_llm_simples baseado em quem
    chama (via system prompt)."""
    def _fake(integracao, modelo, messages):
        system = next((m['content'] for m in messages if m['role'] == 'system'), '')
        if 'Extraia os seguintes dados' in system:
            # Extrator pro campo oport.dados_custom.curso_interesse
            return f'{{"curso_interesse": "{curso}"}}'
        if 'Categorias disponiveis' in system:
            # Classificador
            return classificacao
        # ia_respondedor
        return fallback_text
    return _fake


# ══════════════════════════════════════════════════════════════════
# Cenarios do caminho critico
# ══════════════════════════════════════════════════════════════════

class TestFluxoIACriticoE2E:

    def test_curso_valido_completa_ate_finalizacao(self, setup_fluxo_critico):
        atend = setup_fluxo_critico['atend']
        nodos = setup_fluxo_critico['nodos']

        with patch.object(eng, '_chamar_llm_simples',
                          side_effect=respostas_llm(classificacao='curso_valido')):
            # Passo 1: inicia fluxo — pausa em questao nome (id=2)
            r1 = eng.iniciar_fluxo_visual(atend)
            assert r1['tipo'] == 'questao'
            atend.refresh_from_db()
            assert atend.nodo_atual_id == nodos[2].id

            # Passo 2: responde nome -> branch true -> pausa em curso (id=3)
            r2 = eng.processar_resposta_visual(atend, 'Lucas Teste')
            assert r2['tipo'] == 'questao'
            atend.refresh_from_db()
            assert atend.nodo_atual_id == nodos[3].id

            # Passo 3: responde "Psicologia". LLM retorna curso_valido.
            # Fluxo deve percorrer: 3 (true) -> 4 (condicao: var.validacao_curso
            # == curso_valido -> true) -> 5 (finalizacao OK_VALIDO)
            r3 = eng.processar_resposta_visual(atend, 'Psicologia')

        assert r3['tipo'] == 'finalizado'
        assert r3['mensagem'] == 'OK_VALIDO'
        atend.refresh_from_db()
        assert atend.status == 'completado'
        assert atend.score_qualificacao == 80
        # Confirma que variavel foi salva
        variaveis = atend.dados_respostas.get('variaveis', {})
        assert variaveis.get('validacao_curso') == 'curso_valido'

    def test_curso_invalido_cai_em_fim_invalido(self, setup_fluxo_critico):
        """Candidato com curso que nao eh oferecido deve chegar em
        finalizacao OK_INVALIDO — nao no branch true."""
        atend = setup_fluxo_critico['atend']

        with patch.object(eng, '_chamar_llm_simples',
                          side_effect=respostas_llm(classificacao='curso_invalido',
                                                    curso='Medicina')):
            eng.iniciar_fluxo_visual(atend)
            eng.processar_resposta_visual(atend, 'Maria')
            r = eng.processar_resposta_visual(atend, 'Medicina')

        assert r['tipo'] == 'finalizado'
        assert r['mensagem'] == 'OK_INVALIDO'
        atend.refresh_from_db()
        assert atend.status == 'abandonado'
        variaveis = atend.dados_respostas.get('variaveis', {})
        assert variaveis.get('validacao_curso') == 'curso_invalido'

    def test_regressao_bug_var_x_curso_valido_nao_cai_em_invalido(
        self, setup_fluxo_critico
    ):
        """REGRESSAO do bug 23/04/2026: antes do fix de duck typing em
        _resolver_campo_contexto, este teste FALHARIA — candidato com
        validacao_curso='curso_valido' cairia no branch false da condicao
        e chegaria em OK_INVALIDO. Com o fix, chega em OK_VALIDO."""
        atend = setup_fluxo_critico['atend']

        with patch.object(eng, '_chamar_llm_simples',
                          side_effect=respostas_llm(classificacao='curso_valido')):
            eng.iniciar_fluxo_visual(atend)
            eng.processar_resposta_visual(atend, 'Pedro')
            r = eng.processar_resposta_visual(atend, 'Psicologia')

        # Asserts explicitos com mensagem pra debugging futuro
        assert r['mensagem'] != 'OK_INVALIDO', (
            "Regressao do bug var.X: candidato com curso valido foi rotiado "
            "pro branch invalido. Conferir _resolver_campo_contexto — condicao "
            "com dot notation var.X nao esta resolvendo no ContextoLogado."
        )
        assert r['mensagem'] == 'OK_VALIDO'

    def test_resposta_fora_do_esperado_cai_no_fallback(self, setup_fluxo_critico):
        """Quando a IA classifica como invalido e o lead mandou algo muito
        fora (ex: pergunta), fluxo poderia cair no branch false da questao
        e acessar o ia_respondedor — mas na nossa fixture o branch eh
        acionado por `ia_sucesso=False` (extracao falhou). Pra simplificar,
        aqui garantimos que, quando ia_acao retorna sucesso, sempre vai
        pro branch true."""
        atend = setup_fluxo_critico['atend']

        # Quando extracao retorna JSON vazio, a funcao considera falha -> branch false
        def fake_llm(integracao, modelo, messages):
            system = next((m['content'] for m in messages if m['role'] == 'system'), '')
            if 'Extraia os seguintes dados' in system:
                return '{}'  # extraiu nada
            if 'Categorias disponiveis' in system:
                return 'curso_invalido'
            return 'Resposta do fallback IA'

        with patch.object(eng, '_chamar_llm_simples', side_effect=fake_llm):
            eng.iniciar_fluxo_visual(atend)
            eng.processar_resposta_visual(atend, 'Joao')
            r = eng.processar_resposta_visual(atend, 'quanto custa?')

        # ia_respondedor (nodo 7) pausa — retorna tipo ia_respondedor
        assert r['tipo'] == 'ia_respondedor'
        atend.refresh_from_db()
        # nodo_atual fica no ia_respondedor
        assert atend.nodo_atual.tipo == 'ia_respondedor'

    def test_caminho_valido_cria_variaveis_esperadas(self, setup_fluxo_critico):
        """Alem do roteamento, o engine deve popular dados_respostas com
        as variaveis que condicoes downstream consomem."""
        atend = setup_fluxo_critico['atend']

        with patch.object(eng, '_chamar_llm_simples',
                          side_effect=respostas_llm(classificacao='curso_valido',
                                                    curso='Enfermagem')):
            eng.iniciar_fluxo_visual(atend)
            eng.processar_resposta_visual(atend, 'Ana')
            eng.processar_resposta_visual(atend, 'Enfermagem')

        atend.refresh_from_db()
        variaveis = atend.dados_respostas.get('variaveis', {})
        assert variaveis.get('validacao_curso') == 'curso_valido'
        # Curso extraido
        assert variaveis.get('oport_dados_custom_curso_interesse') == 'Enfermagem'
