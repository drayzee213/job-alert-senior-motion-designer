"""Gemeinsame HTTP-Hilfen mit Zeitlimit, Wiederholung und höflichem User-Agent."""
from __future__ import annotations

import time

import requests

from .models import SourceError

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)
API_UA = "job-alarm-bot/1.0 (+private job alert; low frequency)"

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": API_UA, "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"})
    return _session


def get(url: str, *, params=None, headers=None, timeout: float = 25, retries: int = 2,
        what: str = "") -> requests.Response:
    """GET mit kurzer Wiederholung bei Netzwerkfehlern/5xx. Wirft SourceError."""
    return request("GET", url, params=params, headers=headers, timeout=timeout,
                   retries=retries, what=what)


def request(method: str, url: str, *, params=None, headers=None, json=None, timeout: float = 25,
            retries: int = 2, what: str = "", ok_404: bool = False) -> requests.Response:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = session().request(method, url, params=params, headers=headers, json=json,
                                     timeout=timeout)
        except requests.RequestException as exc:  # Netzwerkfehler
            last = exc
        else:
            if resp.status_code == 429:
                raise SourceError(f"{what or url}: HTTP 429 (zu viele Anfragen / blockiert)")
            if resp.status_code == 404 and ok_404:
                return resp
            if resp.status_code >= 500:
                last = SourceError(f"{what or url}: HTTP {resp.status_code}")
            elif resp.status_code >= 400:
                raise SourceError(f"{what or url}: HTTP {resp.status_code}")
            else:
                return resp
        if attempt < retries:
            time.sleep(2 * (attempt + 1))
    if isinstance(last, requests.RequestException):
        detail = "Zeitüberschreitung" if isinstance(last, requests.Timeout) else \
            f"keine Verbindung ({type(last).__name__})"
        raise SourceError(f"{what or url}: {detail}")
    raise SourceError(f"{what or url}: {last}")
