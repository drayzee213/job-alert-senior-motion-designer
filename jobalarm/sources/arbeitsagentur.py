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
    refnr = _first(item, "refnr", "referenznummer")
    if not refnr:
        return None
    title = _first(item, "titel", "stellenangebotsTitel", "stellentitel", "beruf") or ""
    company = _first(item, "arbeitgeber", "arbeitgeberName", "firma") or ""
    if isinstance(company, dict):
        company = company.get("name") or ""
    place = _first(item, "arbeitsort", "stellenlokation")
    if not place and isinstance(item.get("arbeitsorte"), list) and item["arbeitsorte"]:
        place = item["arbeitsorte"][0]
    location = ""
    if isinstance(place, dict):
        location = place.get("ort") or place.get("region") or ""
        adr = place.get("adresse")
        if not location and isinstance(adr, dict):
            location = adr.get("ort") or ""
    elif isinstance(place, str):
        location = place
    posted = _first(item, "aktuelleVeroeffentlichungsdatum", "veroeffentlichungsdatum",
                    "ersteVeroeffentlichungsdatum", "modifikationsTimestamp")
    url = _first(item, "externeUrl") or f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
    return Job(
        source="arbeitsagentur",
        source_id=str(refnr),
        title=str(title),
        company=str(company),
        location=str(location) + (" (Homeoffice möglich)" if homeoffice else ""),
        url=str(url),
        remote=True if homeoffice else None,
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
    src = cfg["quellen"]["arbeitsagentur"]
    search = cfg["suche"]
    days = int(src.get("tage_zurueck", 7))
    jobs: dict[str, Job] = {}
    errors = []
    calls = 0
    variants = [{"wo": search.get("ort", "Berlin"), "umkreis": search.get("umkreis_km", 40)}]
    if src.get("homeoffice_bundesweit", True):
        variants.append({"arbeitszeit": "ho"})
    for term in search.get("begriffe", []):
        for variant in variants:
            params = {"was": term, "angebotsart": 1, "veroeffentlichtseit": days,
                      "size": 50, "page": 1, "pav": "false", **variant}
            try:
                resp = http.get(SEARCH_URL, params=params, headers=HEADERS, what="Arbeitsagentur")
                data = resp.json()
            except (SourceError, ValueError) as exc:
                errors.append(str(exc))
                calls += 1
                if calls >= 2 and len(errors) == calls:
                    raise SourceError(errors[0])  # Schnittstelle offenbar gestört -> abbrechen
                continue
            calls += 1
            time.sleep(0.5)
            for item in _items(data):
                job = parse_item(item, homeoffice=variant.get("arbeitszeit") == "ho")
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
