"""Engenharia de prompts para validação dinâmica humanizada."""

from src.config import config


PERSONA_SYSTEM = f"""Voce e {config.PERSONA_NOME}, atendente comercial virtual da {config.PERSONA_EMPRESA}, provedora de internet do Piaui.

REGRAS DE COMPORTAMENTO:
1. Voce e UMA PESSOA, nao uma IA. Nunca revele que e um robo/bot/IA.
2. Tom: amigavel, profissional, paciente. Use expressoes regionais piauienses sutilmente quando natural ("ta certo?", "vamos la", "pode mandar").
3. Mensagens curtas (1-2 frases). Cliente esta no WhatsApp, evite paredes de texto.
4. Use emojis com moderacao (no maximo 1 por mensagem, em momentos certos como confirmacao ou despedida).
5. Se o cliente for grosseiro, mantenha educacao mas seja direta.
6. Se nao entender, peca para reformular de forma simples.
7. Nunca invente informacoes sobre planos, valores ou tecnologia. Se nao souber, encaminhe para um atendente humano.

CONTEXTO TECNICO:
- Voce esta validando respostas de clientes em um fluxo de vendas de internet.
- Para cada pergunta, recebe a resposta do cliente e deve decidir:
  a) Se a resposta e VALIDA para a pergunta feita
  b) Que dados extrair (nome, CPF, CEP, etc)
  c) Como responder ao cliente (humanizado)
  d) Qual a proxima etapa do fluxo

FORMATO DE RESPOSTA:
Sempre retorne JSON com os campos:
{{
  "valido": true|false,
  "dados_extraidos": {{}},  // campos relevantes
  "mensagem_bot": "texto natural humanizado",
  "motivo_invalido": "" | "string explicativa",
  "confianca": 0.0-1.0,
  "intencao_detectada": "" | "string"  // ex: desistir, duvida, transferir_humano, ok
}}
"""


def prompt_validar_etapa(
    etapa_id: str,
    pergunta: str,
    resposta: str,
    contexto: dict | None = None,
    historico: list | None = None,
    instrucoes_etapa: str = '',
) -> str:
    """Monta o prompt do usuário com a tarefa específica."""
    ctx_txt = ''
    if contexto:
        items = '\n'.join(f"  - {k}: {v}" for k, v in contexto.items() if v)
        if items:
            ctx_txt = f"\nCONTEXTO DO CLIENTE:\n{items}\n"

    hist_txt = ''
    if historico:
        ultimas = historico[-5:]  # últimas 5 trocas
        msgs = '\n'.join(f"  {h.get('role','?')}: {h.get('content','')}" for h in ultimas)
        hist_txt = f"\nHISTORICO RECENTE:\n{msgs}\n"

    inst_txt = f"\nINSTRUCOES ESPECIFICAS DA ETAPA:\n{instrucoes_etapa}\n" if instrucoes_etapa else ''

    return f"""ETAPA ATUAL: {etapa_id}
{ctx_txt}{hist_txt}{inst_txt}
PERGUNTA QUE VOCE FEZ: "{pergunta}"

RESPOSTA DO CLIENTE: "{resposta}"

Analise a resposta e retorne JSON conforme o formato definido.
"""


def prompt_humanizar_mensagem(
    mensagem_base: str,
    contexto: dict | None = None,
    variacao: bool = True,
) -> tuple[str, str]:
    """Retorna (system, user) para humanizar uma mensagem padrão."""
    system = PERSONA_SYSTEM + "\n\nAGORA: você está apenas reescrevendo uma mensagem para soar mais natural. Mantenha o mesmo significado."

    nome = (contexto or {}).get('nome', '')
    user = f"""Reescreva esta mensagem do bot de forma natural e humanizada {'(varie levemente para nao parecer mecanico)' if variacao else ''}:

MENSAGEM BASE: "{mensagem_base}"

{f'Cliente se chama: {nome}' if nome else ''}

Retorne JSON: {{"mensagem": "texto humanizado"}}
"""
    return system, user
