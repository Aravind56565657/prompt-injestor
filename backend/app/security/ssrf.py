import ipaddress
import re
import socket

import httpx

from app.core.config import get_settings

settings = get_settings()

_IPV4_REGEX = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")

METADATA_ENDPOINTS = (
    "169.254.169.254",
    "metadata.google.internal",
    "metadata",
    "100.100.100.200",
)


class SSRFError(Exception):
    pass


def resolve_hostname(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise SSRFError(f"Could not resolve host '{host}': {exc}") from exc
    ips: list[str] = []
    for info in infos:
        ip = info[4][0]
        if ip not in ips:
            ips.append(ip)
    return ips


def is_private_or_blocked(ip: str) -> bool:
    if not settings.ssrf_block_private:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def validate_url(url: str, *, mode: str = "strict") -> None:
    """Reject dangerous URLs.

    Cloud metadata endpoints are ALWAYS blocked. Private/loopback/reserved hosts
    are blocked in production, but allowed in dev/test when
    SSRF_ALLOW_LOCALHOST_DEV=true (needed to scan local mock targets).
    """
    if url.lower().startswith(("file:", "ftp:", "gopher:", "dict:", "ldap:")):
        raise SSRFError("Unsupported URL scheme")

    is_loose = settings.ssrf_allow_localhost_dev and settings.environment in (
        "development",
        "test",
    )

    parsed = httpx.URL(url)
    host = parsed.host or ""
    if not host:
        raise SSRFError("URL has no host")

    # Cloud metadata endpoints are ALWAYS blocked, even in dev/test.
    if host in METADATA_ENDPOINTS or host == "169.254.169.254":
        raise SSRFError("Cloud metadata endpoints are blocked")

    if is_loose:
        return

    # Literal IP or hostname resolution
    ips: list[str] = []
    literal = _IPV4_REGEX.match(host)
    if literal:
        ips.append(host)
    else:
        ips = resolve_hostname(host)

    for ip in ips:
        if is_private_or_blocked(ip):
            raise SSRFError(f"Blocked destination {ip} (private/loopback/reserved)")

    # Reject redirected-to metadata / private hosts
    if "169.254.169.254" in url or "metadata.google.internal" in url:
        raise SSRFError("Blocked cloud metadata host in URL")


def is_safe_redirect_url(url: str) -> bool:
    try:
        validate_url(url)
        return True
    except SSRFError:
        return False