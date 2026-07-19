"""Executor de `acoes_pos_etapa` definidas no YAML do fluxo.

Cada ação é dispatch'ada para o método correspondente do cliente Django.
Roda em background (chamado por _disparar_sync no validador).

Exemplo de YAML:
    acoes_pos_etapa:
      - tipo: atualizar_status
        valor: aguardando_assinatura
      - tipo: adicionar_tags
        tags: [Comercial]
      - tipo: registrar_historico
        status: fluxo_inicializado
"""
from __future__ import annotations

import logging
from typing import Any

from src.integracoes import robovendas

logger = logging.getLogger(__name__)


def executar_acoes(
    telefone: str,
    lead_id: int | None,
    acoes: list[dict[str, Any]],
    contexto: dict[str, Any] | None = None,
):
    """Executa cada acao da lista. Falha de uma não impede as outras."""
    if not acoes:
        return
    contexto = contexto or {}

    for acao in acoes:
        tipo = acao.get('tipo', '')
        try:
            if tipo == 'atualizar_status':
                if lead_id:
                    robovendas.atualizar_status(
                        lead_id,
                        status_api=acao.get('valor', ''),
                        observacoes=acao.get('observacoes', ''),
                    )

            elif tipo == 'adicionar_tags':
                if lead_id:
                    robovendas.atualizar_tags(
                        lead_id,
                        tags_add=acao.get('tags', []),
                        tags_remove=acao.get('tags_remove', []),
                    )

            elif tipo == 'registrar_historico':
                robovendas.registrar_historico(
                    telefone=telefone,
                    lead_id=lead_id,
                    status=acao.get('status', ''),
                    observacoes=acao.get('observacoes', ''),
                    nome_contato=contexto.get('nome', ''),
                )

            elif tipo == 'registrar_imagem':
                if lead_id and contexto.get('url_imagem'):
                    robovendas.registrar_imagem(
                        lead_id,
                        link_url=contexto['url_imagem'],
                        descricao=acao.get('descricao', 'documento'),
                    )

            else:
                logger.warning(f'Ação desconhecida: {tipo}')

        except Exception as e:
            logger.exception(f'Falha ao executar ação {tipo}: {e}')
