"""
Guardas de segurança compartilhadas pelos nós que falam com a rede.

- `validar_url_ssrf`: bloqueia esquema fora de http/https e destinos que resolvem
  pra IP interno (loopback, privado, link-local/metadata, reservado). Cobre
  IPv4, IPv6 e IPv4-mapped-IPv6.
- `mascarar_headers`: troca valores de headers sensíveis por '***' antes de
  qualquer print/log/persistência.
"""
import ipaddress
import socket
from urllib.parse import urlsplit


ESQUEMAS_PERMITIDOS = {'http', 'https'}
HEADERS_SENSIVEIS = {'authorization', 'cookie', 'set-cookie', 'proxy-authorization'}


class DestinoBloqueado(Exception):
    """Destino reprovado pelo guard SSRF."""


def validar_url_ssrf(url):
    """Valida esquema e resolve o host, rejeitando IP interno.

    Levanta DestinoBloqueado se reprovado. Devolve a lista de IPs resolvidos.
    """
    partes = urlsplit(url or '')
    esquema = (partes.scheme or '').lower()
    if esquema not in ESQUEMAS_PERMITIDOS:
        raise DestinoBloqueado(f"esquema '{esquema or '?'}' não permitido (use http/https)")

    host = partes.hostname
    if not host:
        raise DestinoBloqueado('URL sem host')

    ips = _resolver_ips(host)
    if not ips:
        raise DestinoBloqueado(f"host '{host}' não resolveu")

    for ip in ips:
        if _ip_interno(ip):
            raise DestinoBloqueado(f"host '{host}' resolve p/ IP interno ({ip})")
    return ips


def _resolver_ips(host):
    try:
        infos = socket.getaddrinfo(host, None)  # AF_INET + AF_INET6
    except socket.gaierror:
        return []
    return [sockaddr[0] for *_, sockaddr in infos]


def _ip_interno(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # não parseou: bloqueia por precaução
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # ::ffff:169.254.169.254 → 169.254.169.254
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def mascarar_headers(headers):
    """Cópia dos headers com valores sensíveis trocados por '***'."""
    if not headers:
        return {}
    return {
        k: ('***' if str(k).lower() in HEADERS_SENSIVEIS else v)
        for k, v in dict(headers).items()
    }
