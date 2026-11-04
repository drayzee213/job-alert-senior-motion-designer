"""Jobbörse der Bundesagentur für Arbeit (offene Schnittstelle, kein Konto nötig).

Doku: https://github.com/bundesAPI/jobsuche-api
"""
from __future__ import annotations

import base64
import time
from typing import Any

from .. import http
from ..models import Job, SourceError
from ..scoring import plain_text

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
SEARCH_URL = f"{BASE}/pc/v6/jobs"
DETAIL_URL = f"{BASE}/pc/v4/jobdetails/{{code}}"
HEADERS = {"X-API-Key": "jobboerse-jobsuche", "Accept": "application/json"}
LABEL = "Arbeitsagentur"


def _first(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = d.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def parse_item(item: dict[str, Any], homeoffice: bool = False) -> Job | None:
    """Liest einen Eintrag der Suche. v6 (Stand 11/2026) nutzt u. a. referenznummer,
    stellenangebotsTitel, firma, stellenlokationen, homeofficemoeglich,
    datumErsteVeroeffentlichung, externeURL. Ältere Feldnamen (v4) gehen auch."""
    refnr = _first(item, "referenznummer", "refnr")
    if not refnr:
        return None
    title = _first(item, "stellenangebotsTitel", "titel", "stellentitel", "beruf", "hauptberuf") or ""
    company = _first(item, "firma", "arbeitgeber", "arbeitgeberName") or ""
    if isinstance(company, dict):
        company = company.get("name") or ""
    places = []
    for loc in item.get("stellenlokationen") or item.get("arbeitsorte") or []:
        if isinstance(loc, dict):
            adr = loc.get("adresse") if isinstance(loc.get("adresse"), dict) else loc
            ort = adr.get("ort") or adr.get("region") or ""
            if ort and ort not in places:
                places.append(str(ort))
    place = item.get("arbeitsort")
    if not places and isinstance(place, dict) and place.get("ort"):
        places.append(str(place["ort"]))
    location = ", ".join(places[:3]) + (" u. a." if len(places) > 3 else "")
    if not location:
        location = "Deutschland"
    ho = homeoffice or bool(item.get("homeofficemoeglich"))
    if ho:
        location += " (Homeoffice möglich)"
    zeitraum = item.get("veroeffentlichungszeitraum") or {}
    posted = _first(item, "datumErsteVeroeffentlichung", "aktuelleVeroeffentlichungsdatum",
                    "veroeffentlichungsdatum") or (zeitraum.get("von") if isinstance(zeitraum, dict) else None)
    url = _first(item, "externeURL", "externeUrl") or f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
    title = str(title)
    if item.get("vertragsdauer") == "BEFRISTET" and "befrist" not in title.lower():
        title += " [befristet]"
    return Job(
        source="arbeitsagentur",
        source_id=str(refnr),
        title=title,
        company=str(company),
        location=location,
        url=str(url),
        posted=str(posted)[:10] if posted else None,
        source_label=LABEL,
    )


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("ergebnisliste", "stellenangebote", "ergebnisse", "jobs", "stellen"):
        val = data.get(key)
        if isinstance(val, list):
            return val
    return []


def fetch(cfg: dict[str, Any]) -> list[Job]:
    """Eine bundesweite Abfrage pro Suchbegriff (Berlin ist darin enthalten; ob der Ort
    passt, entscheidet die Bewertung)."""
    src = cfg["quellen"]["arbeitsagentur"]
    days = int(src.get("tage_zurueck", 7))
    jobs: dict[str, Job] = {}
    errors = []
    calls = 0
    for term in cfg["suche"].get("begriffe", []):
        params = {"was": term, "angebotsart": 1, "veroeffentlichtseit": days,
                  "size": 100, "page": 1, "pav": "false"}
        try:
            data = http.get(SEARCH_URL, params=params, headers=HEADERS, what="Arbeitsagentur").json()
        except (SourceError, ValueError) as exc:
            errors.append(str(exc))
            calls += 1
            if calls >= 2 and len(errors) == calls:
                raise SourceError(errors[0])  # Schnittstelle offenbar gestört -> abbrechen
            continue
        calls += 1
        time.sleep(0.5)
        for item in _items(data):
            job = parse_item(item)
            if job and job.uid not in jobs:
                jobs[job.uid] = job
    if errors and len(errors) == calls:
        raise SourceError(errors[0])
    return list(jobs.values())


def enrich(job: Job) -> None:
    """Beschreibung nachladen (nur für neue, interessante Anzeigen)."""
    code = base64.b64encode(job.source_id.encode()).decode()
    try:
        resp = http.get(DETAIL_URL.format(code=code), headers=HEADERS, retries=1,
                        what="Arbeitsagentur-Details")
        data = resp.json()
    except (SourceError, ValueError):
        return
    desc = _first(data, "stellenangebotsBeschreibung", "stellenbeschreibung", "beschreibung")
    if desc:
        job.description = plain_text(str(desc))
    if not job.company:
        job.company = _first(data, "arbeitgeber", "firma") or ""
    salary = _first(data, "verguetung", "gehalt")
    if salary and isinstance(salary, str):
        job.salary = salary
    if not job.remote and _first(data, "arbeitszeitHeimarbeitTelearbeit", "homeofficeMoeglich"):
        job.remote = True


def is_alive(job: Job) -> bool | None:
    """True = noch online, False = gelöscht, None = unklar."""
    code = base64.b64encode(job.source_id.encode()).decode()
    try:
        resp = http.request("GET", DETAIL_URL.format(code=code), headers=HEADERS, retries=1,
                            what="Arbeitsagentur-Details", ok_404=True)
    except SourceError:
        return None
    if resp.status_code == 404:
        return False
    return True
