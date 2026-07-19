"""Menu de cliente existente — definição ÚNICA compartilhada.

A exibição (onboarding) e a extração da opção escolhida (engine) precisam
concordar na NUMERAÇÃO. Como a opção de UPGRADE só aparece para clientes COM
serviço habilitado, a numeração é DINÂMICA: quando o upgrade é ocultado, as
opções seguintes são renumeradas (sem "buracos"). Este módulo é a fonte da
verdade para os dois lados — nunca duplicar a lista em outro lugar.
"""

# Ordem canônica. Cada opção: chave semântica (usada no dispatch do engine),
# emoji (código ##...## decodificado no WhatsApp/chatsim), rótulo, aliases de
# palavra (o número é atribuído dinamicamente) e se é condicional ao upgrade.
OPCOES = [
    {'opcao': 'novo_servico',  'emoji': '##1f680##', 'label': 'Contratar um novo serviço',
     'aliases': ['novo', 'contratar', 'novo serviço'], 'so_com_servico': False},
    {'opcao': 'upgrade_plano', 'emoji': '##1f4c8##', 'label': 'Fazer upgrade de plano',
     'aliases': ['upgrade', 'mudar plano'], 'so_com_servico': True},
    {'opcao': 'acompanhar_os', 'emoji': '##1f4cd##', 'label': 'Acompanhar status da instalação',
     'aliases': ['acompanhar', 'instalação', 'instalacao', 'status'], 'so_com_servico': False},
    {'opcao': 'atendimento',   'emoji': '##1f4f1##', 'label': 'Falar com Atendimento',
     'aliases': ['atendimento', 'falar', 'atendente'], 'so_com_servico': False},
    {'opcao': 'finalizar',     'emoji': '##1f44b##', 'label': 'Finalizar atendimento',
     'aliases': ['finalizar', 'tchau', 'obrigado', 'obrigada'], 'so_com_servico': False},
]


def opcoes_visiveis(tem_servico_habilitado: bool) -> list[dict]:
    """Opções na ordem canônica, ocultando upgrade se não há serviço ativo."""
    return [o for o in OPCOES if not o['so_com_servico'] or tem_servico_habilitado]


def _label_painel(opcao: dict) -> str:
    """Rótulo da opção — EDITÁVEL no painel Mensagens do Robô
    (chave menu_opcao_<opcao>). Fallback: label padrão do código.
    O texto editado também vale para a extração (aliases dinâmicos)."""
    try:
        from src.regras.mensagens_client import mensagens_client
        return mensagens_client.texto(f"menu_opcao_{opcao['opcao']}", opcao['label'])
    except Exception:  # noqa: BLE001
        return opcao['label']


def montar_menu_texto(tem_servico_habilitado: bool) -> str:
    """Bloco de opções numerado + a dica de resposta, já renumerado."""
    ops = opcoes_visiveis(tem_servico_habilitado)
    linhas = [f"*{i})* {o['emoji']} {_label_painel(o)}" for i, o in enumerate(ops, 1)]
    n = len(ops)
    nums = ', '.join(f'*{i}*' for i in range(1, n)) + f' ou *{n}*'
    dica = f'_##1f4cc## Responda apenas com o *número* da opção ({nums})._'
    return '\n'.join(linhas) + '\n\n' + dica


def opcoes_extracao(tem_servico_habilitado: bool) -> dict:
    """Mapa {opcao: [num, *aliases]} para o extractor `opcao` do engine.

    O número é atribuído conforme a posição EXIBIDA (mesma de montar_menu_texto),
    garantindo que '2' signifique a mesma coisa que o cliente vê.
    """
    ops = opcoes_visiveis(tem_servico_habilitado)
    # inclui o rótulo do painel como alias — botão da URA manda o texto exibido
    return {o['opcao']: [str(i)] + list(o['aliases']) + [_label_painel(o).lower()]
            for i, o in enumerate(ops, 1)}
