"""
Varredura dos templates do projeto.

Existe por um motivo especifico: `{# ... #}` do Django SO funciona numa linha.
Aberto numa linha e fechado noutra, ele nao e comentario, e texto: o Django
renderiza as chaves e o conteudo direto na pagina, no meio da interface, em
producao.

E um erro que nao quebra nada. O template compila, os testes de view passam com
200, e o unico jeito de notar e abrindo a pagina e lendo. Aconteceu tres vezes
no mesmo modulo antes desta varredura existir.

Multi-linha e sempre `{% comment %} ... {% endcomment %}`.
"""
import pathlib
import re

import pytest


RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Palavras que aparecem em texto de interface e precisam de acento. Nao e
# corretor ortografico: e a lista curta do que ja escapou pra tela mais de uma
# vez. Identificador, slug e nome de campo continuam sem acento de proposito,
# por isso a varredura olha SO texto visivel (ver _texto_visivel).
ACENTOS_OBRIGATORIOS = {
    'historico': 'histórico', 'situacao': 'situação', 'transicao': 'transição',
    'admissao': 'admissão', 'experiencia': 'experiência', 'aplicavel': 'aplicável',
    'configuracao': 'configuração', 'configuracoes': 'configurações',
    'informacao': 'informação', 'informacoes': 'informações',
    'observacao': 'observação', 'observacoes': 'observações',
    'documentacao': 'documentação', 'comunicacao': 'comunicação',
    'formulario': 'formulário', 'periodo': 'período', 'usuario': 'usuário',
    'codigo': 'código', 'numero': 'número', 'proprio': 'próprio', 'proxima': 'próxima',
    'proximas': 'próximas', 'obrigatorio': 'obrigatório',
    'obrigatoria': 'obrigatória', 'automatico': 'automático',
    'publico': 'público', 'unico': 'único', 'ultima': 'última', 'ultimo': 'último',
    'rescisao': 'rescisão', 'submissao': 'submissão', 'submissoes': 'submissões',
    'expiracao': 'expiração', 'duracao': 'duração', 'padrao': 'padrão',
    'acao': 'ação', 'acoes': 'ações', 'atencao': 'atenção',
    'nao': 'não', 'sao': 'são', 'voce': 'você', 'sera': 'será',
    'ninguem': 'ninguém', 'alem': 'além', 'ja': 'já',
    'varios': 'vários', 'varias': 'várias', 'tambem': 'também',
    'apos': 'após', 'tres': 'três', 'ate': 'até', 'porem': 'porém',
    'disponivel': 'disponível', 'disponiveis': 'disponíveis',
    'responsavel': 'responsável', 'responsaveis': 'responsáveis',
    'minimo': 'mínimo', 'maximo': 'máximo', 'media': 'média', 'area': 'área',
    'vinculo': 'vínculo', 'endereco': 'endereço', 'servico': 'serviço',
    'salario': 'salário', 'horario': 'horário', 'relatorio': 'relatório',
    'criterio': 'critério', 'gestao': 'gestão', 'opcao': 'opção',
    'opcoes': 'opções', 'versao': 'versão', 'razao': 'razão',
    'descricao': 'descrição', 'selecao': 'seleção', 'excecao': 'exceção',
    'condicao': 'condição', 'funcao': 'função', 'posicao': 'posição',
    'revisao': 'revisão', 'decisao': 'decisão', 'conclusao': 'conclusão',
    'referencia': 'referência', 'aniversario': 'aniversário',
    'ha': 'há', 'la': 'lá', 'so': 'só', 'comecou': 'começou',
    'comeca': 'começa', 'servicos': 'serviços', 'inicio': 'início',
    'senao': 'senão', 'entao': 'então', 'nivel': 'nível',
    'automatica': 'automática', 'propria': 'própria', 'proprios': 'próprios',
    'unica': 'única', 'publica': 'pública', 'obrigatorios': 'obrigatórios',
}


def _apagar_preservando_linhas(fonte, padrao):
    """
    Troca o trecho por espaco, mantendo os \\n.

    O detalhe importa: a varredura reporta numero de linha, entao remover um
    bloco de comentario de 4 linhas deslocaria todo o resto do arquivo. Apagar
    o conteudo sem apagar as quebras mantem a numeracao honesta.
    """
    return re.sub(padrao,
                  lambda m: re.sub(r'[^\n]', ' ', m.group(0)),
                  fonte, flags=re.S | re.I)


def _texto_visivel(fonte):
    """
    So o que o usuario le. Fora: comentario, style, script, tag, e as
    expressoes do Django.

    Recebe o ARQUIVO inteiro, nunca uma linha: comentario e <style> abrem numa
    linha e fecham noutra, e olhando linha a linha nenhum dos dois seria
    reconhecido. Primeira versao deste teste cometia esse erro e acusava o
    proprio comentario que explicava o codigo.

    Comentario fica de fora de proposito: o repo escreve comentario sem acento
    (ver os docstrings de apps/people/estados.py) e acentuar comentario nao e o
    que este teste defende.

    Atributo que vira texto na tela (title, placeholder, aria-label) e mantido,
    porque tooltip errado e tao visivel quanto paragrafo errado.
    """
    for padrao in (r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}',
                   r'\{#.*?#\}',
                   r'<style\b.*?</style>',
                   r'<script\b.*?</script>'):
        fonte = _apagar_preservando_linhas(fonte, padrao)

    # Atributo visivel vira texto solto na mesma linha, antes de a tag sumir,
    # pra nao perder o numero da linha.
    def _promover_atributos(linha):
        visiveis = re.findall(r'(?:title|placeholder|aria-label)="([^"]*)"', linha)
        return ' '.join([linha] + visiveis)

    fonte = '\n'.join(_promover_atributos(l) for l in fonte.split('\n'))

    # Tag some no arquivo inteiro, nao linha a linha: <textarea id="descricao"
    # rows="5"> abre numa linha e fecha na seguinte, e por linha o `descricao`
    # de dentro do atributo passava por texto de tela.
    fonte = _apagar_preservando_linhas(fonte, r'<[^>]*>')

    # Literal dentro de {{ }} e {% %} tambem vira tela, mas so alguns: o
    # `label` de um include e lido pelo usuario, o `name` do mesmo include e
    # identificador de campo. Promover todo literal indiscriminadamente acusava
    # name="numero" e type="number", ruido que faria alguem desligar o teste.
    # Por isso a lista e nomeada, e cresce quando um componente novo trouxer
    # parametro de texto novo.
    PARAMS_VISIVEIS = ('label', 'helper', 'placeholder', 'title', 'text',
                       'footnote', 'meta', 'confirm_label', 'cancel_label',
                       'blank_label', 'pct_label', 'empty_text', 'subtitle')

    def _promover_literais(linha):
        expressoes = ' '.join(re.findall(r'\{\{.*?\}\}|\{%.*?%\}', linha))
        literais = re.findall(
            rf'\b(?:{"|".join(PARAMS_VISIVEIS)})="([^"]+)"', expressoes)
        # default de filtro: {{ x|default:"Cargo nao definido" }}
        literais += re.findall(r'\|default:"([^"]+)"', expressoes)
        return ' '.join([linha] + literais)

    fonte = '\n'.join(_promover_literais(l) for l in fonte.split('\n'))
    return re.sub(r'\{\{.*?\}\}|\{%.*?%\}', ' ', fonte)


def _templates():
    """Todos os .html do projeto: raiz de templates e os de cada app."""
    raizes = [
        RAIZ / 'templates',
        *(RAIZ / 'apps').glob('*/templates'),
        *(RAIZ / 'apps').glob('*/*/templates'),
    ]
    for raiz in raizes:
        if raiz.exists():
            yield from raiz.rglob('*.html')


def _relativo(caminho):
    return caminho.as_posix().split('/gerenciador_vendas/')[-1]


def test_nenhum_comentario_django_multilinha():
    """
    `{#` precisa fechar com `#}` na MESMA linha.

    Se este teste falhar, o conteudo do comentario esta aparecendo pro usuario.
    A correcao e trocar por {% comment %}, nunca adicionar excecao aqui.
    """
    achados = []
    for caminho in _templates():
        texto = caminho.read_text(encoding='utf-8', errors='replace')
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if '{#' not in linha:
                continue
            depois_da_abertura = linha.split('{#', 1)[1]
            if '#}' not in depois_da_abertura:
                achados.append(f'  {_relativo(caminho)}:{numero}  {linha.strip()[:70]}')

    assert not achados, (
        'Comentario {# #} aberto sem fechar na mesma linha. O Django vai '
        'renderizar isso como TEXTO na pagina.\n'
        'Use {% comment %} ... {% endcomment %} pra multi-linha.\n'
        + '\n'.join(achados)
    )


def test_a_varredura_pega_o_caso_real():
    """
    Meta teste. Uma varredura quebrada passa calada e da falsa seguranca.
    """
    uma_linha = '{# comentario normal #}'
    multi_linha = '{# comentario que abre'

    assert '#}' in uma_linha.split('{#', 1)[1]
    assert '#}' not in multi_linha.split('{#', 1)[1]


def test_texto_visivel_do_people_esta_acentuado():
    """
    Acento em texto de interface no modulo People.

    Escopo em apps/people de proposito: e o modulo onde este erro voltou tres
    vezes seguidas, uma delas indo parar num print que o usuario mandou de
    volta. Ampliar pro projeto inteiro exigiria varrer templates de outras
    sessoes e o custo cairia em quem nao pediu. Pra estender, e so somar uma
    raiz aqui.
    """
    raiz = RAIZ / 'apps' / 'people' / 'templates'
    achados = []
    for caminho in sorted(raiz.rglob('*.html')):
        visivel_do_arquivo = _texto_visivel(caminho.read_text(encoding='utf-8'))
        for numero, visivel in enumerate(visivel_do_arquivo.split('\n'), 1):
            for errada, certa in ACENTOS_OBRIGATORIOS.items():
                if re.search(rf'\b{errada}\b', visivel, re.I):
                    achados.append(f'  {_relativo(caminho)}:{numero}  {errada} -> {certa}')

    assert not achados, (
        'Texto de interface sem acento (o usuario le isso na tela):\n'
        + '\n'.join(achados)
    )


def test_a_varredura_de_acento_distingue_texto_de_comentario():
    """
    Meta teste. Uma varredura que acusa comentario vira ruido e alguem desliga.
    Uma que ignora paragrafo nao serve pra nada. Prova os dois lados.
    """
    fonte = (
        '{% comment %}\n'
        'aqui o historico e escrito sem acento de proposito\n'
        '{% endcomment %}\n'
        '<p>O historico do colaborador</p>\n'
        '<button title="Preserva o historico">Ok</button>\n'
    )
    linhas = _texto_visivel(fonte).split('\n')

    assert 'historico' not in linhas[1], 'comentario nao devia ser varrido'
    assert 'historico' in linhas[3], 'paragrafo devia ser varrido'
    assert 'historico' in linhas[4], 'title vira tooltip, devia ser varrido'
    # A numeracao tem que sobreviver ao apagamento do comentario
    assert len(linhas) == 6, 'apagar comentario nao pode deslocar as linhas'


def test_a_varredura_de_acento_ignora_atributo_de_tag_multilinha():
    """
    Caso real: <textarea id="descricao" ... > aberto numa linha e fechado na
    seguinte. Varrendo linha a linha, o `descricao` do atributo passava por
    texto de tela e o teste acusava um identificador, que ninguem le.
    """
    fonte = (
        '<textarea id="descricao" name="descricao"\n'
        '          rows="5"></textarea>\n'
        '<p>A descricao do cargo</p>\n'
    )
    linhas = _texto_visivel(fonte).split('\n')

    assert 'descricao' not in linhas[0], 'atributo de tag nao e texto de tela'
    assert 'descricao' not in linhas[1], 'resto da tag multilinha idem'
    assert 'descricao' in linhas[2], 'paragrafo continua sendo varrido'


@pytest.mark.django_db
def test_todo_template_compila():
    """
    Compila cada template. Pega bloco desbalanceado, tag desconhecida e sintaxe
    invalida de filtro.

    Compilar em vez de contar ocorrencia de tag: a primeira versao deste teste
    contava `{% comment %}` contra `{% endcomment %}` e acusou um template que
    so tinha a string escrita DENTRO de um comentario, como documentacao. Contar
    texto nao entende contexto; o compilador entende.

    `manage.py check` NAO faz isso: template so e compilado quando alguem pede a
    pagina. Um erro de sintaxe atravessa a suite inteira e aparece pro usuario.
    """
    from django.template import TemplateSyntaxError
    from django.template.loader import get_template

    achados = []
    for caminho in _templates():
        # Nome relativo a raiz de templates, que e como o loader acha
        partes = caminho.as_posix().split('/templates/', 1)
        if len(partes) != 2:
            continue
        try:
            get_template(partes[1])
        except TemplateSyntaxError as erro:
            achados.append(f'  {_relativo(caminho)}: {erro}')
        except Exception:
            # Template que o loader nao acha por caminho (nome duplicado entre
            # apps, por exemplo) nao e problema de sintaxe.
            continue

    assert not achados, 'Template com erro de sintaxe:\n' + '\n'.join(achados)
