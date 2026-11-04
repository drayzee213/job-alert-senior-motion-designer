"""Indeed und LinkedIn über python-jobspy (Version 1.4.1, siehe requirements.txt).

Verwendete Parameter laut Doku/Quelltext von 1.4.1: site_name, search_term, location,
distance (Meilen), is_remote (nur Indeed – LinkedIn ignoriert es mit Warnung),
results_wanted, hours_old, country_indeed, description_format, verbose.
Fehler stehen in df.attrs["errors"] (z.B. {"linkedin": "... 429 ..."}).
"""
from __future__ import annotations

import math
import random
import time
from typing import Any

from ..models import Job, SourceError

LABELS = {"indeed": "Indeed", "linkedin": "LinkedIn"}


def _val(rec: dict[str, Any], key: str) -> Any:
    v = rec.get(key)
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        pass
    if hasattr(v, "value"):  # Enum
        v = v.value
    return v


def _salary(rec: dict[str, Any]) -> str | None:
    lo, hi = _val(rec, "min_amount"), _val(rec, "max_amount")
    if not lo and not hi:
        return None
    cur = _val(rec, "currency") or "EUR"
    cur = "€" if cur in ("EUR", "€") else cur
    interval = {"yearly": "Jahr", "monthly": "Monat", "weekly": "Woche", "daily": "Tag",
                "hourly": "Stunde"}.get(str(_val(rec, "interval") or ""), "")

    def fmt(x: Any) -> str:
        return f"{int(float(x)):,}".replace(",", ".")

    amount = f"{fmt(lo)}–{fmt(hi)}" if lo and hi and lo != hi else fmt(lo or hi)
    return f"{amount} {cur}" + (f" / {interval}" if interval else "")


def record_to_job(rec: dict[str, Any], site: str) -> Job | None:
    jid = _val(rec, "id")
    url = _val(rec, "job_url")
    title = _val(rec, "title")
    if not jid or not url or not title:
        return None
    posted = _val(rec, "date_posted")
    return Job(
        source=site,
        source_id=str(jid),
        title=str(title),
        company=str(_val(rec, "company") or ""),
        location=str(_val(rec, "location") or ""),
        url=str(url),
        description=str(_val(rec, "description") or ""),
        remote=bool(_val(rec, "is_remote")) if _val(rec, "is_remote") is not None else None,
        posted=str(posted)[:10] if posted else None,
        salary=_salary(rec),
        source_label=LABELS.get(site, site),
    )


def fetch(cfg: dict[str, Any]) -> dict[str, list[Job] | SourceError]:
    """Gibt pro Seite (indeed/linkedin) eine Liste oder – wenn keine einzige Abfrage
    dieser Seite geklappt hat – einen SourceError zurück."""
    from jobspy import scrape_jobs  # erst hier laden (dauert etwas)

    src = cfg["quellen"]["jobspy"]
    pause = src.get("pause_sekunden", [15, 40])
    jobs: dict[str, list[Job]] = {}
    errors: dict[str, str] = {}
    blocked: set[str] = set()
    succeeded: set[str] = set()
    seen: set[str] = set()
    first = True
    for query in src.get("abfragen", []):
        site = query["seite"]
        if site in blocked:
            continue  # Seite blockiert -> in diesem Lauf nicht weiter anfragen
        if not first:
            time.sleep(random.uniform(pause[0], pause[1]))
        first = False
        kwargs: dict[str, Any] = dict(
            site_name=[site],
            search_term=query["begriff"],
            results_wanted=int(src.get("ergebnisse_pro_abfrage", 15)),
            hours_old=int(src.get("stunden_alt", 72)),
            description_format="markdown",
            verbose=0,
        )
        if query.get("ort"):
            kwargs["location"] = query["ort"]
            kwargs["distance"] = int(query.get("umkreis_meilen", 25))
        if site == "indeed":
            kwargs["country_indeed"] = "germany"
            if query.get("nur_remote"):
                kwargs["is_remote"] = True
        label = LABELS.get(site, site)
        try:
            df = scrape_jobs(**kwargs)
        except Exception as exc:  # jobspy wirft sehr unterschiedliche Fehler
            errors[site] = f"{label}: {type(exc).__name__}: {exc}"[:300]
            blocked.add(site)
            continue
        err = (getattr(df, "attrs", {}) or {}).get("errors", {}).get(site)
        if err:
            errors[site] = f"{label}: {err}"[:300]
            if df.empty or "429" in str(err) or "block" in str(err).lower():
                blocked.add(site)
        bucket = jobs.setdefault(site, [])
        for rec in df.to_dict("records"):
            job = record_to_job(rec, site)
            if job and job.uid not in seen:
                seen.add(job.uid)
                bucket.append(job)
        if not err:
            succeeded.add(site)
    results: dict[str, list[Job] | SourceError] = {}
    for query in src.get("abfragen", []):
        site = query["seite"]
        if site in results:
            continue
        if site in succeeded or jobs.get(site) or site not in errors:
            results[site] = jobs.get(site, [])
        else:
            results[site] = SourceError(errors[site])
    return results
