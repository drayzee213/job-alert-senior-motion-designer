"""Hilfswerkzeug: einzelne Quellen und Firmen genauer untersuchen (Ausgabe: tools/untersuchung.md).

Aufruf: python -m tools.untersuchen
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jobalarm import http  # noqa: E402
from jobalarm.sources import arbeitsagentur  # noqa: E402

OUT: list[str] = []


def out(s: str = "") -> None:
    print(s, flush=True)
    OUT.append(s)


def ba() -> None:
    out("## Arbeitsagentur v6\n")
    for params in (
        {"was": "Motion Designer", "wo": "Berlin", "umkreis": 50, "veroeffentlichtseit": 30, "size": 5},
        {"was": "Motion Designer", "veroeffentlichtseit": 30, "size": 5},
        {"was": "Motion Designer", "arbeitszeit": "ho", "veroeffentlichtseit": 30, "size": 5},
        {"was": "Rive", "veroeffentlichtseit": 60, "size": 5},
        {"was": "Animation", "wo": "Berlin", "umkreis": 50, "veroeffentlichtseit": 30, "size": 5},
        {"arbeitgeber": "Applimeda GmbH", "size": 5},
        {"was": "Applimeda", "size": 5},
    ):
        r = requests.get(arbeitsagentur.SEARCH_URL, params={"angebotsart": 1, "page": 1, **params},
                         headers=arbeitsagentur.HEADERS, timeout=30)
        data = r.json()
        items = arbeitsagentur._items(data)
        out(f"- `{params}` → HTTP {r.status_code}, maxErgebnisse={data.get('maxErgebnisse')}, {len(items)} Einträge")
        for it in items[:3]:
            job = arbeitsagentur.parse_item(it)
            out(f"  - geparst: {job.title if job else None} | {job.company if job else ''} | "
                f"{job.location if job else ''} | {job.posted if job else ''} | {job.url if job else ''}")
        if items:
            out("  - Rohdaten 1. Eintrag: `" + json.dumps(items[0], ensure_ascii=False)[:1500] + "`")
        time.sleep(1)
    # Details
    r = requests.get(arbeitsagentur.SEARCH_URL, params={"was": "Designer", "wo": "Berlin", "size": 1},
                     headers=arbeitsagentur.HEADERS, timeout=30)
    items = arbeitsagentur._items(r.json())
    if items:
        job = arbeitsagentur.parse_item(items[0])
        import base64
        code = base64.b64encode(job.source_id.encode()).decode()
        for url in (arbeitsagentur.DETAIL_URL.format(code=code),
                    f"{arbeitsagentur.BASE}/pc/v3/jobdetails/{code}",
                    f"{arbeitsagentur.BASE}/pc/v2/jobdetails/{code}"):
            d = requests.get(url, headers=arbeitsagentur.HEADERS, timeout=30)
            keys = sorted(d.json().keys()) if d.headers.get("content-type", "").startswith("application/json") else d.text[:200]
            out(f"- Details {url.split('/pc/')[1][:20]}…: HTTP {d.status_code}, Felder: `{keys}`")
        page = requests.get(job.url, headers={"User-Agent": http.BROWSER_UA}, timeout=30)
        out(f"- Öffentliche Seite {job.url}: HTTP {page.status_code}, {len(page.text)} Zeichen")


def indeed_linkedin() -> None:
    from jobspy import scrape_jobs
    out("\n## Indeed / LinkedIn Varianten\n")
    tests = [
        ("indeed", '"motion designer" OR "motion design" OR rive OR lottie OR "character animator"', "Berlin", False),
        ("indeed", "motion designer", "Berlin", False),
        ("indeed", "motion design", "", True),
        ("indeed", "rive animator", "", False),
        ("linkedin", "Applimeda", "Germany", False),
        ("linkedin", '"motion designer" OR rive OR lottie OR "character animator"', "Germany", False),
    ]
    for site, term, loc, remote in tests:
        kw = dict(site_name=[site], search_term=term, results_wanted=10, hours_old=24 * 14, verbose=0)
        if loc:
            kw["location"] = loc
        if site == "indeed":
            kw["country_indeed"] = "germany"
            if remote:
                kw["is_remote"] = True
        t0 = time.time()
        try:
            df = scrape_jobs(**kw)
            out(f"- {site} `{term}` ort={loc!r} remote={remote}: {len(df)} in {time.time()-t0:.0f}s, "
                f"Fehler={df.attrs.get('errors')}")
            for rec in df.to_dict("records")[:5]:
                out(f"  - {rec.get('title')} | {rec.get('company')} | {rec.get('location')} | {rec.get('date_posted')} | {rec.get('is_remote')}")
        except Exception as exc:
            out(f"- {site} `{term}`: ❌ {type(exc).__name__}: {exc}")
        time.sleep(15)


ATS_HINT = re.compile(
    r"https?://[^\s\"'<>]*(greenhouse|lever\.co|ashbyhq|personio|recruitee|smartrecruiters|workable|join\.com|"
    r"myworkdayjobs|softgarden|teamtailor|pinpointhq|bamboohr|breezy|onlyfy|prescreen|dvinci|rexx|workwise|"
    r"jobs\.gem|rippling|factorial|kenjo|hrworks|comeet|jobvite|icims|successfactors|recruiting|bewerbung|"
    r"career|karriere|jobs)[^\s\"'<>]*", re.I)

EXTRA_ENDPOINTS = [
    ("pinpoint", "https://{s}.pinpointhq.com/postings.json"),
    ("teamtailor", "https://{s}.teamtailor.com/jobs.rss"),
    ("bamboohr", "https://{s}.bamboohr.com/careers/list"),
    ("breezy", "https://{s}.breezy.hr/json"),
    ("gem", "https://api.gem.com/job_board/v0/{s}/job_posts/"),
    ("rippling", "https://api.rippling.com/platform/api/ats/v1/board/{s}/jobs"),
    ("softgarden", "https://{s}.softgarden.io/de/vacancies"),
    ("personio.com", "https://{s}.jobs.personio.com/xml"),
    ("lever-eu", "https://api.eu.lever.co/v0/postings/{s}?mode=json"),
    ("greenhouse-eu", "https://boards-api.eu.greenhouse.io/v1/boards/{s}/jobs"),
]

DEEP = {
    "Applimeda": (["https://www.applimeda.de", "https://applimeda.de", "https://www.applimeda.com"], ["applimeda", "applimedagmbh"]),
    "Blinkist": (["https://www.blinkist.com/en/careers", "https://www.blinkist.com/careers"], ["blinkist", "go1"]),
    "Clue": (["https://helloclue.com/careers", "https://helloclue.com/jobs"], ["clue", "biowink", "helloclue"]),
    "Freeletics": (["https://www.freeletics.com/en/corporate/jobs/", "https://www.freeletics.com/en/jobs/"], ["freeletics"]),
    "komoot": (["https://www.komoot.com/jobs", "https://www.komoot.com/careers"], ["komoot"]),
    "InnoGames": (["https://www.innogames.com/career/", "https://www.innogames.com/jobs/"], ["innogames", "innogamesgmbh"]),
    "Goodgame Studios": (["https://www.goodgamestudios.com/career/", "https://www.goodgamestudios.com/jobs/"], ["goodgamestudios", "goodgame"]),
    "Yager": (["https://www.yager.de/jobs/", "https://www.yager.de/careers/", "https://yager.de"], ["yager", "yagerdevelopment", "yager-development"]),
    "Ableton": (["https://www.ableton.com/en/jobs/"], ["ableton"]),
    "Ecosia": (["https://jobs.ecosia.org", "https://www.ecosia.org/jobs", "https://ecosia.org/careers"], ["ecosia"]),
    "Native Instruments": (["https://www.native-instruments.com/en/careers/"], ["nativeinstruments", "native-instruments", "soundwide"]),
    "Rive": (["https://rive.app/careers", "https://rive.app/jobs"], ["rive", "rive-app", "riveapp"]),
    "Selfapy": (["https://www.selfapy.com/karriere", "https://www.selfapy.de/karriere"], ["selfapy"]),
    "Fastic": (["https://fastic.com/careers/", "https://fastic.com/jobs"], ["fastic"]),
    "Klang Games": (["https://klang-games.com/jobs", "https://www.klang-games.com/careers"], ["klanggames", "klang-games", "klang"]),
    "Taxfix": (["https://taxfix.de/en/careers/", "https://taxfix.com/careers/"], ["taxfix"]),
    "Mimi Hearing": (["https://mimi.io/careers", "https://mimi.io/jobs"], ["mimi", "mimihearing", "mimi-hearing-technologies"]),
    "7Mind": (["https://www.7mind.de/karriere", "https://www.7mind.de/jobs"], ["7mind"]),
    "Daedalic": (["https://www.daedalic.com/jobs", "https://www.daedalic.com/career"], ["daedalic"]),
    "Bytro Labs": (["https://www.bytro.com/jobs", "https://www.bytro.com/careers"], ["bytro", "bytrolabs"]),
    "Sdui": (["https://sdui.de/karriere/", "https://sdui.de/jobs/"], ["sdui"]),
    "Scalable Capital": (["https://de.scalable.capital/karriere", "https://scalable.capital/careers"], ["scalablecapital", "scalable"]),
    "Kaia Health": (["https://kaiahealth.com/careers/", "https://kaiahealth.de/karriere/"], ["kaiahealth", "kaia-health"]),
    "Quizlet": (["https://quizlet.com/jobs"], ["quizlet"]),
}


def deep_company(name: str, pages: list[str], slugs: list[str]) -> None:
    out(f"\n### {name}")
    hints: set[str] = set()
    for url in pages:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": http.BROWSER_UA})
        except requests.RequestException as exc:
            out(f"- {url}: ❌ {type(exc).__name__}")
            continue
        out(f"- {url}: HTTP {r.status_code} → {r.url} ({len(r.text)} Zeichen)")
        if r.status_code >= 400:
            continue
        host = urlsplit(r.url).netloc
        for m in ATS_HINT.finditer(r.text):
            u = m.group(0).rstrip(").,;")
            if urlsplit(u).netloc != host or re.search(r"job|karriere|career", u, re.I):
                hints.add(u[:160])
        for m in re.finditer(r'href="([^"]*(?:job|karriere|career|stellen)[^"]*)"', r.text, re.I):
            hints.add(urljoin(r.url, m.group(1))[:160])
    for h in sorted(hints)[:25]:
        out(f"  - {h}")
    for slug in slugs:
        for system, tmpl in EXTRA_ENDPOINTS:
            u = tmpl.format(s=slug)
            try:
                r = requests.get(u, timeout=12, headers={"User-Agent": http.BROWSER_UA}, allow_redirects=False)
            except requests.RequestException:
                continue
            if r.status_code == 200 and len(r.text) > 50:
                out(f"  - ✅ {system}:{slug} → {u} HTTP 200, {len(r.text)} Zeichen: `{r.text[:200]!r}`")


def main() -> int:
    out(f"# Untersuchung – {time.strftime('%d.%m.%Y %H:%M UTC', time.gmtime())}\n")
    ba()
    indeed_linkedin()
    out("\n## Firmen genauer untersuchen")
    for name, (pages, slugs) in DEEP.items():
        try:
            deep_company(name, pages, slugs)
        except Exception as exc:
            out(f"- ❌ {name}: {type(exc).__name__}: {exc}")
    (ROOT / "tools" / "untersuchung.md").write_text("\n".join(OUT) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
