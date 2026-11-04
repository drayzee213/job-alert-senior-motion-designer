"""Prüft vor dem Senden, ob eine Anzeige noch online ist."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

import requests

from . import http
from .models import Job

DEAD_PHRASES = [
    "nicht mehr verfügbar", "nicht mehr verfuegbar", "nicht mehr aktiv", "nicht mehr online",
    "ist leider nicht mehr", "nicht mehr ausgeschrieben", "bereits besetzt", "wurde besetzt",
    "stelle ist vergeben", "anzeige ist abgelaufen", "stellenanzeige ist abgelaufen",
    "stellenangebot ist abgelaufen", "existiert nicht mehr",
    "no longer available", "no longer accepting applications", "no longer open",
    "position has been filled", "this job has expired", "job has expired", "posting has expired",
    "this job is no longer", "this position is no longer", "job is closed", "this job is closed",
    "job not found", "position is closed", "listing has expired",
    "bewerbungen werden nicht mehr angenommen",
]
SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")

OK, DEAD, UNKNOWN = "ok", "dead", "unknown"


def visible_text(html_text: str) -> str:
    text = SCRIPT_RE.sub(" ", html_text[:600_000])
    text = TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).lower()


def page_says_dead(html_text: str) -> str | None:
    text = visible_text(html_text)
    for phrase in DEAD_PHRASES:
        if phrase in text:
            return phrase
    return None


def _linkedin_id(url: str) -> str | None:
    m = re.search(r"/jobs/view/(?:[^/]*-)?(\d{6,})", url)
    return m.group(1) if m else None


def check(job: Job) -> tuple[str, str]:
    """Gibt (Status, Begründung) zurück. Status: ok, dead, unknown.

    unknown = Seite blockt automatische Abrufe (z.B. Indeed/LinkedIn 403/429/999). Dann
    verlassen wir uns darauf, dass die Anzeige gerade eben noch im Suchergebnis stand.
    """
    url = job.url
    if not url or not url.startswith("http"):
        return DEAD, "kein Link"

    if job.source == "arbeitsagentur" and "arbeitsagentur.de" in url:
        from .sources import arbeitsagentur
        alive = arbeitsagentur.is_alive(job)
        if alive is False:
            return DEAD, "bei der Arbeitsagentur gelöscht"
        return (OK, "Details abrufbar") if alive else (UNKNOWN, "Prüfung nicht möglich")

    if job.source == "linkedin":
        jid = _linkedin_id(url) or job.source_id.removeprefix("li-")
        if jid and jid.isdigit():
            url_to_check = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}"
        else:
            url_to_check = url
    else:
        url_to_check = url

    try:
        resp = http.session().get(url_to_check, timeout=20, allow_redirects=True,
                                  headers={"User-Agent": http.BROWSER_UA,
                                           "Accept": "text/html,application/xhtml+xml,*/*"})
    except requests.RequestException as exc:
        return UNKNOWN, f"nicht erreichbar ({type(exc).__name__})"

    if resp.status_code in (404, 410):
        return DEAD, f"HTTP {resp.status_code}"
    if resp.status_code in (401, 403, 429, 999) or resp.status_code >= 500:
        return UNKNOWN, f"HTTP {resp.status_code} (Seite blockt automatische Prüfung)"
    if resp.status_code >= 400:
        return DEAD, f"HTTP {resp.status_code}"

    final = resp.url or url_to_check
    if "error=true" in final or "/404" in urlsplit(final).path:
        return DEAD, "Weiterleitung auf Fehlerseite"
    # Firmen-Bewerbungssysteme leiten abgelaufene Stellen oft auf die Übersicht um
    if ":" in job.source and job.source_id and job.source_id not in final and final.rstrip("/") != url.rstrip("/"):
        if job.source_id not in resp.text[:300_000]:
            return DEAD, "Weiterleitung auf Übersichtsseite"
    phrase = page_says_dead(resp.text)
    if phrase:
        return DEAD, f"Seite meldet „{phrase}“"
    return OK, f"HTTP {resp.status_code}"
