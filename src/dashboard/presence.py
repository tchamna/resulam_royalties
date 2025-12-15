from __future__ import annotations

import ipaddress
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from typing import Mapping, Tuple

_LOCK = threading.Lock()
_SESSIONS: dict[str, dict] = {}
_IP_COUNTRY_CACHE: dict[str, Tuple[str, float]] = {}

_DEFAULT_ACTIVE_WINDOW_SECONDS = 90
_CACHE_TTL_SECONDS = 24 * 60 * 60


def _is_private_or_loopback(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return bool(addr.is_private or addr.is_loopback or addr.is_link_local)


def get_client_ip(headers: Mapping[str, str], remote_addr: str | None) -> str:
    """
    Best-effort client IP extraction that supports common reverse-proxy headers.
    """
    xff = headers.get("X-Forwarded-For") or headers.get("X-FORWARDED-FOR")
    if xff:
        for part in xff.split(","):
            candidate = part.strip()
            if candidate:
                return candidate
    xrip = headers.get("X-Real-IP") or headers.get("X-REAL-IP")
    if xrip:
        return xrip.strip()
    return (remote_addr or "").strip() or "Unknown"


def _country_from_headers(headers: Mapping[str, str]) -> str | None:
    for key in (
        "CF-IPCountry",
        "CloudFront-Viewer-Country",
        "X-AppEngine-Country",
        "X-Country-Code",
        "X-Geo-Country",
        "X-Country",
    ):
        val = headers.get(key)
        if val:
            return val.strip()
    return None


def _fetch_country_from_ipapi(ip: str) -> str | None:
    # ipapi.co returns plain text.
    url = f"https://ipapi.co/{ip}/country_name/"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:  # nosec - user requested geo lookup
            country = resp.read().decode("utf-8", errors="replace").strip()
            if not country or country.lower() in {"undefined", "none", "null"}:
                return None
            return country
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def get_country(headers: Mapping[str, str], remote_addr: str | None) -> str:
    """
    Best-effort country resolution. Prefers proxy-provided headers, then caches a
    lightweight geo lookup for public IPs. Falls back to "Local" / "Unknown".
    """
    from_headers = _country_from_headers(headers)
    if from_headers:
        return from_headers

    ip = get_client_ip(headers, remote_addr)
    if ip == "Unknown":
        return "Unknown"
    if _is_private_or_loopback(ip):
        return "Local"

    now = time.time()
    with _LOCK:
        cached = _IP_COUNTRY_CACHE.get(ip)
        if cached and (now - cached[1]) < _CACHE_TTL_SECONDS:
            return cached[0]

    country = _fetch_country_from_ipapi(ip) or "Unknown"
    with _LOCK:
        _IP_COUNTRY_CACHE[ip] = (country, now)
    return country


def touch(session_id: str, ip: str, country: str) -> None:
    now = time.time()
    with _LOCK:
        _SESSIONS[session_id] = {"ip": ip, "country": country, "last_seen": now}


def active_summary(active_window_seconds: int = _DEFAULT_ACTIVE_WINDOW_SECONDS) -> tuple[int, Counter]:
    now = time.time()
    cutoff = now - max(5, int(active_window_seconds))

    with _LOCK:
        active = {sid: info for sid, info in _SESSIONS.items() if info.get("last_seen", 0) >= cutoff}

        # Opportunistic cleanup to keep memory bounded.
        cleanup_cutoff = now - max(60, int(active_window_seconds) * 10)
        for sid in list(_SESSIONS.keys()):
            if _SESSIONS[sid].get("last_seen", 0) < cleanup_cutoff:
                _SESSIONS.pop(sid, None)

    countries = Counter((info.get("country") or "Unknown") for info in active.values())
    return len(active), countries

