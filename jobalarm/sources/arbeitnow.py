"""Arbeitnow – kostenlose Jobbörse mit offener Schnittstelle (Fokus Deutschland).

Doku: https://www.arbeitnow.com/blog/job-board-api
"""
from __future__ import annotations

import time
from typing import Any

from .. import http
from ..models import Job, SourceError
from ..scoring import plain_text

URL = "https://www.arbeitnow.com/api/job-board-api"


def parse(data: dict[str, Any]) -> list[Job]:
    out = []
    for j in data.get("data", []):
        slug = j.get("slug")
        if not slug:
            continue
        posted = j.get("created_at")
        if isinstance(posted, (int, float)):
            posted = time.strftime("%Y-%m-%d", time.gmtime(posted))
        out.append(Job(
            source="arbeitnow",
            source_id=str(slug),
            title=j.get("title", ""),
            company=j.get("company_name", ""),
            location=j.get("location", "") or "",
            url=j.get("url", ""),
            description=plain_text(j.get("description", "")),
            remote=True if j.get("remote") else None,
            posted=str(posted)[:10] if posted else None,
            source_label="Arbeitnow",
        ))
    return out


def fetch(cfg: dict[str, Any]) -> list[Job]:
    pages = int(cfg["quellen"]["arbeitnow"].get("seiten", 3))
    jobs: list[Job] = []
    for page in range(1, pages + 1):
        try:
            data = http.get(URL, params={"page": page}, what="Arbeitnow").json()
        except ValueError as exc:
            raise SourceError(f"Arbeitnow: keine gültige Antwort ({exc})") from exc
        batch = parse(data)
        jobs.extend(batch)
        if not batch or not (data.get("links") or {}).get("next"):
            break
        time.sleep(1)
    return jobs
