"""Prüft alle Quellen und findet heraus, welches Bewerbungssystem Firmen nutzen.

Aufruf:  python -m tools.check_sources [--kandidaten] [--jobspy]
Ergebnis: tools/pruefbericht.md (und Ausgabe im Log / in der Actions-Zusammenfassung)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jobalarm import http, linkcheck  # noqa: E402
from jobalarm.config import load_companies, load_config  # noqa: E402
from jobalarm.location import classify_location  # noqa: E402
from jobalarm.models import SourceError  # noqa: E402
from jobalarm.sources import arbeitnow, arbeitsagentur, ats  # noqa: E402

FINGERPRINTS = [
    ("greenhouse", r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)"),
    ("greenhouse", r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)"),
    ("greenhouse", r"greenhouse\.io/embed/job_board(?:/js)?\?for=([A-Za-z0-9_-]+)"),
    ("lever-eu", r"jobs\.eu\.lever\.co/([A-Za-z0-9_.-]+)"),
    ("lever", r"jobs\.lever\.co/([A-Za-z0-9_.-]+)"),
    ("teamtailor", r"([A-Za-z0-9-]+)\.teamtailor\.com"),
    ("bamboohr", r"([A-Za-z0-9-]+)\.bamboohr\.com"),
    ("ashby", r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)"),
    ("personio", r"([A-Za-z0-9-]+)\.jobs\.personio\.(?:de|com)"),
    ("recruitee", r"([A-Za-z0-9-]+)\.recruitee\.com"),
    ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)"),
    ("workable", r"apply\.workable\.com/([A-Za-z0-9_-]+)"),
    ("join", r"join\.com/companies/([A-Za-z0-9_-]+)"),
    ("workday", r"([A-Za-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)"),
]
OTHER_ATS = {
    "softgarden": r"softgarden\.(?:io|de)", "onlyfy/prescreen":
    r"onlyfy\.jobs|prescreen\.io", "d.vinci": r"dvinci|d-vinci", "rexx": r"rexx-systems|rexx-recruitment",
    "workwise": r"workwise\.io", "hrworks": r"hrworks",
    "jobvite": r"jobvite\.com", "icims": r"icims\.com", "successfactors": r"successfactors|sapsf",
    "breezy": r"breezy\.hr", "pinpoint": r"pinpointhq\.com", "comeet": r"comeet\.(?:co|com)",
    "gem": r"jobs\.gem\.com", "rippling": r"ats\.rippling\.com", "factorial": r"factorialhr",
    "kenjo": r"kenjo\.io", "zoho": r"zohorecruit", "greenhouse-like(generic)": r"gh_jid",
}
SKIP_SLUGS = {"embed", "js", "api", "v1", "jobs", "job_board", "www", "de", "en", "careers", "cdn",
              "static", "assets", "app", "boards"}
GUESS_SYSTEMS = ["greenhouse", "lever", "ashby", "personio", "recruitee", "workable", "join",
                 "smartrecruiters", "teamtailor"]

REPORT: list[str] = []


def out(line: str = "") -> None:
    print(line, flush=True)
    REPORT.append(line)


def fetch_page(url: str) -> str:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": http.BROWSER_UA}, allow_redirects=True)
        return r.text[:2_000_000] if r.status_code < 400 else ""
    except requests.RequestException:
        return ""


def detect(html: str) -> tuple[list[tuple[str, str, dict]], list[str]]:
    found: list[tuple[str, str, dict]] = []
    for system, pattern in FINGERPRINTS:
        for m in re.finditer(pattern, html):
            if system == "lever-eu":
                system, slug, extra = "lever", m.group(1), {"region": "eu"}
                if slug.lower() in SKIP_SLUGS or (system, slug, extra) in found:
                    continue
                found.append((system, slug, extra))
                continue
            if system == "workday":
                extra = {"host": f"{m.group(1)}.{m.group(2)}.myworkdayjobs.com", "seite": m.group(3)}
                slug = m.group(1)
            else:
                slug, extra = m.group(1), {}
            if slug.lower() in SKIP_SLUGS:
                continue
            item = (system, slug, extra)
            if item not in found:
                found.append(item)
    others = [name for name, pat in OTHER_ATS.items() if re.search(pat, html, re.I)]
    return found[:6], others


def try_feed(name: str, system: str, slug: str, extra: dict) -> dict | None:
    company = {"name": name, "system": system, "kennung": slug, **extra}
    try:
        jobs = ats.fetch_company(company)
    except SourceError as exc:
        return {"ok": False, "system": system, "kennung": slug, "fehler": str(exc)[:120]}
    de = [j for j in jobs if classify_location(j.location, j.remote, j.title)[0]
          in ("berlin", "remote_de", "anderer_ort_de", "remote_unklar")]
    return {"ok": True, "system": system, "kennung": slug, "anzahl": len(jobs), "de": len(de),
            "beispiele": [f"{j.title} [{j.location}]" for j in jobs[:3]], **extra}


def probe_company(cand: dict) -> dict:
    name = cand["name"]
    detected: list[tuple[str, str, dict]] = []
    others: set[str] = set()
    for url in cand.get("seiten", []):
        html = fetch_page(url)
        if html:
            d, o = detect(html)
            detected += [x for x in d if x not in detected]
            others.update(o)
    results = []
    for system, slug, extra in detected:
        res = try_feed(name, system, slug, extra)
        if res:
            res["erkannt"] = True
            results.append(res)
    if not any(r["ok"] and r["anzahl"] > 0 for r in results):
        for slug in cand.get("kennungen", []):
            for system in GUESS_SYSTEMS:
                res = try_feed(name, system, slug, {})
                if res and res["ok"] and res["anzahl"] > 0:
                    res["erkannt"] = False
                    results.append(res)
            if any(r["ok"] and r["anzahl"] > 0 for r in results):
                break
    good = [r for r in results if r["ok"] and r["anzahl"] > 0]
    good.sort(key=lambda r: (not r.get("erkannt"), -r["anzahl"]))
    return {"name": name, "treffer": good, "andere_systeme": sorted(others),
            "fehler": [r for r in results if not r["ok"]][:3]}


def check_core(cfg: dict, with_jobspy: bool) -> None:
    out("## Hauptquellen\n")
    # Arbeitsagentur
    params = {"was": "Motion Designer", "wo": "Berlin", "umkreis": 50, "angebotsart": 1,
              "veroeffentlichtseit": 30, "size": 10, "page": 1}
    try:
        r = requests.get(arbeitsagentur.SEARCH_URL, params=params, headers=arbeitsagentur.HEADERS, timeout=30)
        out(f"- Arbeitsagentur v6 Suche: HTTP {r.status_code}")
        data = r.json()
        out(f"  - Schlüssel der Antwort: `{sorted(data.keys())}`")
        items = arbeitsagentur._items(data)
        out(f"  - Anzahl Stellen: {len(items)}, maxErgebnisse: {data.get('maxErgebnisse')}")
        if items:
            out(f"  - Felder einer Stelle: `{sorted(items[0].keys())}`")
            out("  - Beispiel (gekürzt): `" + json.dumps(items[0], ensure_ascii=False)[:700] + "`")
            job = arbeitsagentur.parse_item(items[0])
            if job:
                out(f"  - Geparst: {job.title} | {job.company} | {job.location} | {job.posted} | {job.url}")
                arbeitsagentur.enrich(job)
                out(f"  - Details nachgeladen: Beschreibung {len(job.description)} Zeichen")
                out(f"  - Linkprüfung: {linkcheck.check(job)}")
        r2 = requests.get(arbeitsagentur.SEARCH_URL, params={**params, "wo": None, "umkreis": None,
                                                             "arbeitszeit": "ho"},
                          headers=arbeitsagentur.HEADERS, timeout=30)
        out(f"- Arbeitsagentur Homeoffice (arbeitszeit=ho): HTTP {r2.status_code}, "
            f"{len(arbeitsagentur._items(r2.json()))} Stellen")
        jobs = arbeitsagentur.fetch(cfg)
        out(f"- Arbeitsagentur kompletter Abruf mit config.yaml: {len(jobs)} Stellen")
        for j in jobs[:8]:
            out(f"  - {j.title} | {j.company} | {j.location} | {j.posted}")
    except Exception as exc:
        out(f"- ❌ Arbeitsagentur: {type(exc).__name__}: {exc}")

    try:
        jobs = arbeitnow.fetch(cfg)
        out(f"- Arbeitnow: {len(jobs)} Stellen, z. B. " + "; ".join(j.title for j in jobs[:3]))
    except Exception as exc:
        out(f"- ❌ Arbeitnow: {type(exc).__name__}: {exc}")

    try:
        r = requests.get("https://api.telegram.org/bot0:invalid/getMe", timeout=15)
        out(f"- Telegram-API erreichbar: HTTP {r.status_code} (401/404 ist hier richtig)")
    except Exception as exc:
        out(f"- ❌ Telegram-API: {exc}")

    if with_jobspy:
        from jobspy import scrape_jobs
        import jobspy
        out(f"- python-jobspy Version: {getattr(jobspy, '__version__', 'unbekannt')}")
        for site, loc in (("indeed", "Berlin"), ("linkedin", "Berlin, Germany")):
            t0 = time.time()
            try:
                kw = dict(site_name=[site], search_term='"motion designer" OR rive OR lottie',
                          location=loc, results_wanted=5, hours_old=168, verbose=0)
                if site == "indeed":
                    kw["country_indeed"] = "germany"
                df = scrape_jobs(**kw)
                out(f"- {site}: {len(df)} Stellen in {time.time() - t0:.0f}s, Fehler: {df.attrs.get('errors')}, "
                    f"Warnungen: {df.attrs.get('warnings')}")
                from jobalarm.sources.jobspy_source import record_to_job
                for rec in df.to_dict("records")[:3]:
                    job = record_to_job(rec, site)
                    if job:
                        out(f"  - {job.title} | {job.company} | {job.location} | {job.posted} | {job.salary}")
                        out(f"    Linkprüfung: {linkcheck.check(job)}")
            except Exception as exc:
                out(f"- ❌ {site}: {type(exc).__name__}: {exc}")
            time.sleep(20)


def check_watchlist() -> None:
    out("\n## Firmen aus firmen.yaml\n")
    out("| Firma | System | Anzeigen gesamt | davon DE/Remote | Status |")
    out("|---|---|---|---|---|")
    for c in load_companies():
        try:
            jobs = ats.fetch_company(c)
            de = [j for j in jobs if classify_location(j.location, j.remote, j.title)[0]
                  in ("berlin", "remote_de", "anderer_ort_de", "remote_unklar")]
            out(f"| {c['name']} | {c['system']}:{c['kennung']} | {len(jobs)} | {len(de)} | ✅ |")
        except SourceError as exc:
            out(f"| {c['name']} | {c['system']}:{c['kennung']} | – | – | ❌ {str(exc)[:80]} |")


def check_candidates() -> None:
    cands = yaml.safe_load(open(ROOT / "tools" / "firmen_kandidaten.yaml", encoding="utf-8"))["kandidaten"]
    out("\n## Kandidaten-Firmen (automatische Erkennung)\n")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(probe_company, cands))
    out("| Firma | gefunden | Anzeigen | DE | Beispiele | andere Systeme auf der Seite |")
    out("|---|---|---|---|---|---|")
    for res in results:
        if res["treffer"]:
            t = res["treffer"][0]
            how = "erkannt" if t.get("erkannt") else "geraten"
            extra = f" host={t['host']} seite={t['seite']}" if t.get("host") else ""
            out(f"| {res['name']} | {t['system']}:{t['kennung']}{extra} ({how}) | {t['anzahl']} | {t['de']} | "
                f"{'; '.join(t['beispiele'])[:150]} | {', '.join(res['andere_systeme'])} |")
        else:
            out(f"| {res['name']} | – | – | – | – | {', '.join(res['andere_systeme'])} |")
    (ROOT / "tools" / "kandidaten_ergebnis.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--kandidaten", action="store_true", help="Kandidaten-Firmen automatisch prüfen")
    p.add_argument("--jobspy", action="store_true", help="auch Indeed/LinkedIn testen")
    args = p.parse_args()
    cfg = load_config()
    out(f"# Prüfbericht Quellen – {time.strftime('%d.%m.%Y %H:%M UTC', time.gmtime())}\n")
    check_core(cfg, args.jobspy)
    check_watchlist()
    if args.kandidaten:
        check_candidates()
    report = "\n".join(REPORT) + "\n"
    (ROOT / "tools" / "pruefbericht.md").write_text(report, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
