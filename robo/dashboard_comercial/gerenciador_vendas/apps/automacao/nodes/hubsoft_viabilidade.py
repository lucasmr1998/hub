"""Nós HubSoft de viabilidade técnica (read-only): por endereço ou coordenadas."""
from .base import registrar
from .hubsoft_base import HubsoftNode, _txt, _int, _faltando


@registrar
class HubsoftViabilidadeEndereco(HubsoftNode):
    tipo = "hubsoft_viabilidade_endereco"
    label = "HubSoft: viabilidade por endereço"
    icone = "bi-geo"
    saida_chave = "viabilidade"

    def campos_config(self) -> list:
        return [
            {'nome': 'endereco', 'label': 'Endereço', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.rua}}'},
            {'nome': 'numero', 'label': 'Número', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.numero_residencia}}'},
            {'nome': 'bairro', 'label': 'Bairro', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.bairro}}'},
            {'nome': 'cidade', 'label': 'Cidade', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.cidade}}'},
            {'nome': 'estado', 'label': 'Estado (UF)', 'tipo': 'texto', 'obrigatorio': True,
             'placeholder': '{{lead.estado}}'},
            {'nome': 'raio', 'label': 'Raio (m)', 'tipo': 'numero', 'placeholder': '250'},
            {'nome': 'detalhar_portas', 'label': 'Detalhar portas', 'tipo': 'booleano'},
        ]

    def validar_config(self, config) -> list:
        return _faltando(config, ('endereco', 'numero', 'bairro', 'cidade', 'estado'))

    def _chamar(self, svc, config, contexto):
        return svc.consultar_viabilidade_endereco(
            endereco=_txt(contexto, config, 'endereco'),
            numero=_txt(contexto, config, 'numero'),
            bairro=_txt(contexto, config, 'bairro'),
            cidade=_txt(contexto, config, 'cidade'),
            estado=_txt(contexto, config, 'estado'),
            raio=_int(contexto.resolver(config.get('raio', '')), 250),
            detalhar_portas=bool(config.get('detalhar_portas', True)),
        )


@registrar
class HubsoftViabilidadeCoords(HubsoftNode):
    tipo = "hubsoft_viabilidade_coords"
    label = "HubSoft: viabilidade por coordenadas"
    icone = "bi-pin-map"
    saida_chave = "viabilidade"

    def campos_config(self) -> list:
        return [
            {'nome': 'latitude', 'label': 'Latitude', 'tipo': 'texto', 'obrigatorio': True},
            {'nome': 'longitude', 'label': 'Longitude', 'tipo': 'texto', 'obrigatorio': True},
            {'nome': 'raio', 'label': 'Raio (m)', 'tipo': 'numero', 'placeholder': '250'},
            {'nome': 'detalhar_portas', 'label': 'Detalhar portas', 'tipo': 'booleano'},
        ]

    def validar_config(self, config) -> list:
        return _faltando(config, ('latitude', 'longitude'))

    def _chamar(self, svc, config, contexto):
        return svc.consultar_viabilidade_coords(
            latitude=float(_txt(contexto, config, 'latitude') or 0),
            longitude=float(_txt(contexto, config, 'longitude') or 0),
            raio=_int(contexto.resolver(config.get('raio', '')), 250),
            detalhar_portas=bool(config.get('detalhar_portas', True)),
        )
