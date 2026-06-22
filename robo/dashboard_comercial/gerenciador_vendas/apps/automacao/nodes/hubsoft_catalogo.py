"""Nós HubSoft de catálogo (read-only, sem parâmetros): serviços, vencimentos,
modelos de contrato."""
from .base import registrar
from .hubsoft_base import HubsoftNode


@registrar
class HubsoftListarServicos(HubsoftNode):
    tipo = "hubsoft_listar_servicos"
    label = "HubSoft: listar serviços (planos)"
    icone = "bi-box-seam"
    saida_chave = "servicos"

    def _chamar(self, svc, config, contexto):
        return svc.listar_servicos()


@registrar
class HubsoftListarVencimentos(HubsoftNode):
    tipo = "hubsoft_listar_vencimentos"
    label = "HubSoft: listar vencimentos"
    icone = "bi-calendar-date"
    saida_chave = "vencimentos"

    def _chamar(self, svc, config, contexto):
        return svc.listar_vencimentos()


@registrar
class HubsoftListarModelosContrato(HubsoftNode):
    tipo = "hubsoft_listar_modelos_contrato"
    label = "HubSoft: listar modelos de contrato"
    icone = "bi-file-earmark-text"
    saida_chave = "modelos"

    def _chamar(self, svc, config, contexto):
        return svc.listar_modelos_contrato()
