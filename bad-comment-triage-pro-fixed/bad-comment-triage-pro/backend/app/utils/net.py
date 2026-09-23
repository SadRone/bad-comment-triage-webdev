import ipaddress
import socket
from urllib.parse import urlparse


def is_safe_public_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
            return False
        hostname = parsed.hostname
        for info in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        return True
    except Exception:
        return False
