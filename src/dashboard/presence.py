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


def _normalize_ip_candidate(candidate: str) -> str | None:
    candidate = (candidate or "").strip().strip('"').strip("'")
    if not candidate:
        return None

    # Common formats:
    # - "1.2.3.4"
    # - "1.2.3.4:12345"
    # - "[2001:db8::1]:12345"
    if candidate.startswith("[") and "]" in candidate:
        host = candidate[1 : candidate.index("]")].strip()
        return host or None

    # If it looks like IPv4:port, strip the port.
    if candidate.count(":") == 1 and "." in candidate:
        host = candidate.split(":", 1)[0].strip()
        return host or None

    return candidate


def _validate_ip(ip: str | None) -> str | None:
    ip = _normalize_ip_candidate(ip or "")
    if not ip or ip.lower() == "unknown":
        return None
    try:
        ipaddress.ip_address(ip)
        return ip
    except ValueError:
        return None


def _extract_ip_from_forwarded_header(forwarded: str) -> str | None:
    """
    Parse RFC 7239 Forwarded header to extract the first `for=` IP (if present).

    Example:
      Forwarded: for=192.0.2.60;proto=https;by=203.0.113.43
      Forwarded: for=\"[2001:db8:cafe::17]:4711\";proto=http
    """
    if not forwarded:
        return None

    first_element = forwarded.split(",", 1)[0]
    for part in first_element.split(";"):
        part = part.strip()
        if part.lower().startswith("for="):
            raw = part[4:].strip()
            if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
                raw = raw[1:-1]
            if raw.lower() == "unknown":
                return None
            return _normalize_ip_candidate(raw)

    return None


def get_client_ip(headers: Mapping[str, str], remote_addr: str | None) -> str:
    """
    Best-effort client IP extraction that supports common reverse-proxy headers.
    """
    # Prefer CDN-provided "true client" headers when available (e.g., Cloudflare).
    for key in ("CF-Connecting-IP", "True-Client-IP", "X-Client-IP"):
        raw = headers.get(key)
        if raw:
            ip = _validate_ip(raw)
            if ip:
                return ip

    forwarded = headers.get("Forwarded")
    ip = _validate_ip(_extract_ip_from_forwarded_header(forwarded or ""))
    if ip:
        return ip

    xff = headers.get("X-Forwarded-For") or headers.get("X-FORWARDED-FOR")
    if xff:
        candidates: list[str] = []
        for part in xff.split(","):
            ip = _validate_ip(part)
            if ip:
                candidates.append(ip)

        # Prefer the first public IP (avoid proxy/internal IPs).
        for ip in candidates:
            if not _is_private_or_loopback(ip):
                return ip
        if candidates:
            return candidates[0]

    xrip = headers.get("X-Real-IP") or headers.get("X-REAL-IP")
    if xrip:
        ip = _validate_ip(xrip)
        if ip:
            return ip

    ip = _validate_ip(remote_addr or "")
    return ip or "Unknown"


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
    if from_headers and len(from_headers) > 2:
        return from_headers

    ip = get_client_ip(headers, remote_addr)
    if ip == "Unknown":
        return from_headers or "Unknown"
    if _is_private_or_loopback(ip):
        return "Local"

    now = time.time()
    with _LOCK:
        cached = _IP_COUNTRY_CACHE.get(ip)
        if cached and (now - cached[1]) < _CACHE_TTL_SECONDS:
            return cached[0]

    country = _fetch_country_from_ipapi(ip) or (from_headers or "Unknown")
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
