"""Gerenciamento de contexto/histórico de conversa por telefone.

Implementação simples em memória. Para produção, trocar por Redis.
"""
import time
from collections import defaultdict
from threading import Lock


class GerenciadorConversa:
    def __init__(self, ttl_segundos: int = 3600):
        self._dados: dict[str, dict] = {}
        self._lock = Lock()
        self._ttl = ttl_segundos

    def _expirar(self):
        agora = time.time()
        expirados = [k for k, v in self._dados.items() if agora - v.get('atualizado', 0) > self._ttl]
        for k in expirados:
            self._dados.pop(k, None)

    def obter(self, telefone: str) -> dict:
        with self._lock:
            self._expirar()
            if telefone not in self._dados:
                self._dados[telefone] = {
                    'historico': [],          # [{role, content, ts}]
                    'dados_extraidos': {},    # nome, cpf, cep, etc
                    'etapa_atual': '',
                    'tentativas': defaultdict(int),
                    'criado': time.time(),
                    'atualizado': time.time(),
                }
            return self._dados[telefone]

    def adicionar_msg(self, telefone: str, role: str, content: str):
        ctx = self.obter(telefone)
        ctx['historico'].append({'role': role, 'content': content, 'ts': time.time()})
        # Manter apenas as últimas 20 mensagens
        ctx['historico'] = ctx['historico'][-20:]
        ctx['atualizado'] = time.time()

    def salvar_dado(self, telefone: str, chave: str, valor):
        ctx = self.obter(telefone)
        ctx['dados_extraidos'][chave] = valor
        ctx['atualizado'] = time.time()

    def incrementar_tentativa(self, telefone: str, etapa: str) -> int:
        ctx = self.obter(telefone)
        ctx['tentativas'][etapa] += 1
        ctx['atualizado'] = time.time()
        return ctx['tentativas'][etapa]

    def resetar_tentativas(self, telefone: str, etapa: str):
        ctx = self.obter(telefone)
        ctx['tentativas'][etapa] = 0

    def definir_etapa(self, telefone: str, etapa: str):
        ctx = self.obter(telefone)
        ctx['etapa_atual'] = etapa
        ctx['atualizado'] = time.time()


gerenciador = GerenciadorConversa()
