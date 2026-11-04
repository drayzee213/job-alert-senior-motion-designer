"""Öffentliche Stellen-Schnittstellen der Bewerbungssysteme (ATS) einzelner Firmen.

Unterstützt: greenhouse, lever, ashby, personio, recruitee, smartrecruiters, workable,
join, workday, teamtailor, bamboohr. Eintrag in firmen.yaml z.B.:
    - name: Duolingo
      system: greenhouse
      kennung: duolingo
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from .. import http
from ..models import Job, SourceError
from ..scoring import plain_text


def _iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):  # Millisekunden oder Sekunden
        ts = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
    return str(value)[:10]


def _job(company: dict[str, Any], system: str, jid: Any, title: str, **kw: Any) -> Job:
    return Job(
        source=f"{system}:{company['kennung']}",
        source_id=str(jid),
        title=(title or "").strip(),
        company=company.get("name") or company["kennung"],
        source_label=f"Karriereseite {company.get('name') or company['kennung']} ({system.title()})",
        **kw,
    )


# ---------------------------------------------------------------- Greenhouse
def greenhouse(c: dict[str, Any]) -> list[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{c['kennung']}/jobs"
    data = http.get(url, params={"content": "true"}, what=f"Greenhouse {c['kennung']}").json()
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name") or ""
        offices = ", ".join(o.get("name", "") for o in j.get("offices") or [] if o.get("name"))
        out.append(_job(c, "greenhouse", j["id"], j.get("title", ""),
                        location=loc or offices, url=j.get("absolute_url", ""),
                        description=plain_text(j.get("content") or ""),
                        posted=_iso(j.get("first_published") or j.get("updated_at"))))
    return out


# ---------------------------------------------------------------- Lever
def lever(c: dict[str, Any]) -> list[Job]:
    host = "api.eu.lever.co" if c.get("region") == "eu" else "api.lever.co"
    data = http.get(f"https://{host}/v0/postings/{c['kennung']}", params={"mode": "json"},
                    what=f"Lever {c['kennung']}").json()
    if not isinstance(data, list):
        raise SourceError(f"Lever {c['kennung']}: unerwartete Antwort")
    out = []
    for j in data:
        cats = j.get("categories") or {}
        locs = cats.get("allLocations") or [cats.get("location") or ""]
        workplace = (j.get("workplaceType") or "").lower()
        salary = None
        sr = j.get("salaryRange") or {}
        if sr.get("min") or sr.get("max"):
            salary = f"{sr.get('min', '')}–{sr.get('max', '')} {sr.get('currency', '')}".strip()
        out.append(_job(c, "lever", j["id"], j.get("text", ""),
                        location=", ".join(x for x in locs if x),
                        url=j.get("hostedUrl", ""),
                        description=j.get("descriptionPlain") or plain_text(j.get("description", "")),
                        remote=True if workplace == "remote" else None,
                        posted=_iso(j.get("createdAt")), salary=salary))
    return out


# ---------------------------------------------------------------- Ashby
def ashby(c: dict[str, Any]) -> list[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{c['kennung']}"
    data = http.get(url, params={"includeCompensation": "true"}, what=f"Ashby {c['kennung']}").json()
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""]
        locs += [s.get("location", "") for s in j.get("secondaryLocations") or [] if isinstance(s, dict)]
        comp = j.get("compensation") or {}
        out.append(_job(c, "ashby", j.get("id"), j.get("title", ""),
                        location=", ".join(x for x in locs if x),
                        url=j.get("jobUrl") or j.get("applyUrl") or "",
                        description=j.get("descriptionPlain") or plain_text(j.get("descriptionHtml", "")),
                        remote=True if j.get("isRemote") or (j.get("workplaceType") or "").lower() == "remote" else None,
                        posted=_iso(j.get("publishedAt")),
                        salary=comp.get("compensationTierSummary") or comp.get("scrapeableCompensationSalarySummary")))
    return out


# ---------------------------------------------------------------- Personio
def personio(c: dict[str, Any]) -> list[Job]:
    slug = c["kennung"]
    domains = [c["domain"]] if c.get("domain") else ["jobs.personio.de", "jobs.personio.com"]
    last_err: Exception | None = None
    for domain in domains:
        base = f"https://{slug}.{domain}"
        try:
            resp = http.get(f"{base}/xml", params={"language": c.get("sprache", "de")},
                            what=f"Personio {slug}")
            return parse_personio(resp.content, c, base)
        except (SourceError, ET.ParseError) as exc:
            last_err = exc
    raise SourceError(f"Personio {slug}: {last_err}")


def parse_personio(content: bytes, c: dict[str, Any], base: str) -> list[Job]:
    root = ET.fromstring(content)
    out = []
    for pos in root.iter("position"):
        def t(tag: str) -> str:
            el = pos.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""
        jid = t("id")
        if not jid:
            continue
        offices = [t("office")] + [(o.text or "").strip() for o in pos.findall("additionalOffices/office")]
        desc_parts = []
        for jd in pos.findall("jobDescriptions/jobDescription"):
            desc_parts.append((jd.findtext("name") or "") + " " + (jd.findtext("value") or ""))
        out.append(_job(c, "personio", jid, t("name"),
                        location=", ".join(o for o in offices if o),
                        url=f"{base}/job/{jid}",
                        description=plain_text(" ".join(desc_parts)),
                        posted=_iso(t("createdAt"))))
    return out


# ---------------------------------------------------------------- Recruitee
def recruitee(c: dict[str, Any]) -> list[Job]:
    data = http.get(f"https://{c['kennung']}.recruitee.com/api/offers/",
                    what=f"Recruitee {c['kennung']}").json()
    out = []
    for j in data.get("offers", []):
        if j.get("status") and j["status"] != "published":
            continue
        loc = j.get("location") or ", ".join(x for x in [j.get("city"), j.get("country")] if x)
        out.append(_job(c, "recruitee", j.get("id"), j.get("title", ""),
                        location=loc or "", url=j.get("careers_url") or j.get("careers_apply_url") or "",
                        description=plain_text((j.get("description") or "") + " " + (j.get("requirements") or "")),
                        remote=True if j.get("remote") else None,
                        posted=_iso(j.get("published_at") or j.get("created_at"))))
    return out


# ---------------------------------------------------------------- SmartRecruiters
def smartrecruiters(c: dict[str, Any]) -> list[Job]:
    out, offset = [], 0
    while True:
        data = http.get(f"https://api.smartrecruiters.com/v1/companies/{c['kennung']}/postings",
                        params={"limit": 100, "offset": offset},
                        what=f"SmartRecruiters {c['kennung']}").json()
        content = data.get("content", [])
        for j in content:
            loc = j.get("location") or {}
            out.append(_job(c, "smartrecruiters", j.get("id"), j.get("name", ""),
                            location=loc.get("fullLocation") or ", ".join(
                                x for x in [loc.get("city"), loc.get("country")] if x),
                            url=f"https://jobs.smartrecruiters.com/{c['kennung']}/{j.get('id')}",
                            remote=True if loc.get("remote") else None,
                            posted=_iso(j.get("releasedDate"))))
        offset += len(content)
        if not content or offset >= int(data.get("totalFound", 0)) or offset >= 1000:
            break
    return out


# ---------------------------------------------------------------- Workable
def workable(c: dict[str, Any]) -> list[Job]:
    data = http.get(f"https://apply.workable.com/api/v1/widget/accounts/{c['kennung']}",
                    params={"details": "true"}, what=f"Workable {c['kennung']}").json()
    out = []
    for j in data.get("jobs", []):
        loc = ", ".join(x for x in [j.get("city"), j.get("country")] if x)
        out.append(_job(c, "workable", j.get("shortcode") or j.get("id"), j.get("title", ""),
                        location=loc, url=j.get("url") or j.get("shortlink") or "",
                        description=plain_text(j.get("description") or ""),
                        remote=True if j.get("telecommuting") else None,
                        posted=_iso(j.get("published_on") or j.get("created_at"))))
    return out


# ---------------------------------------------------------------- JOIN
NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def join(c: dict[str, Any]) -> list[Job]:
    """JOIN hat keine dokumentierte Schnittstelle; wir lesen die Firmenseite
    join.com/companies/<kennung> und die darin eingebetteten Daten (__NEXT_DATA__)."""
    resp = http.get(f"https://join.com/companies/{c['kennung']}",
                    headers={"User-Agent": http.BROWSER_UA}, what=f"JOIN {c['kennung']}")
    m = NEXT_DATA_RE.search(resp.text)
    if not m:
        raise SourceError(f"JOIN {c['kennung']}: Seitenstruktur unbekannt")
    return parse_join(json.loads(m.group(1)), c)


def parse_join(data: Any, c: dict[str, Any]) -> list[Job]:
    found: dict[str, Job] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            title = node.get("title")
            jid = node.get("idParam") or node.get("id")
            if isinstance(title, str) and jid and ("idParam" in node or "workplaceType" in node
                                                   or "employmentType" in node):
                city = node.get("city")
                if isinstance(city, dict):
                    city = city.get("cityName") or city.get("name")
                id_param = str(node.get("idParam") or jid)
                remote = str(node.get("workplaceType") or "").upper() == "REMOTE"
                found.setdefault(id_param, _job(
                    c, "join", id_param, title,
                    location=str(city or ""),
                    url=f"https://join.com/companies/{c['kennung']}/{id_param}",
                    remote=True if remote else None,
                    posted=_iso(node.get("createdAt") or node.get("publishedAt"))))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return list(found.values())


# ---------------------------------------------------------------- Workday
def workday(c: dict[str, Any]) -> list[Job]:
    """Benötigt in firmen.yaml: host (z.B. firma.wd3.myworkdayjobs.com), kennung (Tenant),
    seite (Site-Name aus der URL) und optional suchtext (Liste)."""
    host, tenant, site = c["host"], c["kennung"], c["seite"]
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    out: dict[str, Job] = {}
    for text in c.get("suchtext") or ["motion", "animation", "designer"]:
        data = http.request("POST", url, json={"appliedFacets": {}, "limit": 20, "offset": 0,
                                               "searchText": text},
                            headers={"Content-Type": "application/json", "Accept": "application/json"},
                            what=f"Workday {tenant}").json()
        for j in data.get("jobPostings", []):
            path = j.get("externalPath") or ""
            jid = (j.get("bulletFields") or [path])[0]
            out.setdefault(str(jid), _job(c, "workday", jid, j.get("title", ""),
                                          location=j.get("locationsText") or "",
                                          url=f"https://{host}/{site}{path}"))
    return list(out.values())


# ---------------------------------------------------------------- Teamtailor
def teamtailor(c: dict[str, Any]) -> list[Job]:
    """Öffentlicher RSS-Feed https://<kennung>.teamtailor.com/jobs.rss"""
    resp = http.get(f"https://{c['kennung']}.teamtailor.com/jobs.rss", what=f"Teamtailor {c['kennung']}")
    try:
        return parse_teamtailor(resp.content, c)
    except ET.ParseError as exc:
        raise SourceError(f"Teamtailor {c['kennung']}: kein gültiger Feed ({exc})") from exc


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse_teamtailor(content: bytes, c: dict[str, Any]) -> list[Job]:
    root = ET.fromstring(content)
    out = []
    for item in root.iter("item"):
        fields: dict[str, str] = {}
        cities: list[str] = []
        for child in item:
            name = _local(child.tag)
            if name in ("locations", "location"):
                for el in child.iter():
                    if _local(el.tag) == "city" and (el.text or "").strip():
                        city = el.text.strip()
                        if city not in cities:
                            cities.append(city)
            elif (child.text or "").strip():
                fields.setdefault(name, child.text.strip())
        posted = None
        if fields.get("pubdate"):
            try:
                posted = parsedate_to_datetime(fields["pubdate"]).date().isoformat()
            except (TypeError, ValueError):
                posted = None
        remote_status = fields.get("remotestatus", "").lower()
        link = fields.get("link", "")
        out.append(_job(c, "teamtailor", fields.get("guid") or link, fields.get("title", ""),
                        location=", ".join(cities) or ("Remote" if remote_status == "fully" else ""),
                        url=link, description=plain_text(fields.get("description", "")),
                        remote=True if remote_status in ("fully", "remote") else None,
                        posted=posted))
    return out


# ---------------------------------------------------------------- BambooHR
def bamboohr(c: dict[str, Any]) -> list[Job]:
    data = http.get(f"https://{c['kennung']}.bamboohr.com/careers/list",
                    headers={"Accept": "application/json"}, what=f"BambooHR {c['kennung']}").json()
    out = []
    for j in data.get("result", []):
        loc = j.get("atsLocation") or j.get("location") or {}
        parts = [loc.get("city"), loc.get("state") or loc.get("province"), loc.get("country")]
        remote = j.get("isRemote") or str(j.get("locationType", "")) == "1"
        out.append(_job(c, "bamboohr", j.get("id"), j.get("jobOpeningName", ""),
                        location=", ".join(str(p) for p in parts if p),
                        url=f"https://{c['kennung']}.bamboohr.com/careers/{j.get('id')}",
                        remote=True if remote else None))
    return out


PROVIDERS: dict[str, Callable[[dict[str, Any]], list[Job]]] = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "personio": personio,
    "recruitee": recruitee,
    "smartrecruiters": smartrecruiters,
    "workable": workable,
    "join": join,
    "workday": workday,
    "teamtailor": teamtailor,
    "bamboohr": bamboohr,
}


def fetch_company(c: dict[str, Any]) -> list[Job]:
    system = str(c.get("system", "")).lower()
    if system not in PROVIDERS:
        raise SourceError(f"{c.get('name')}: unbekanntes System „{system}“")
    try:
        return PROVIDERS[system](c)
    except SourceError:
        raise
    except Exception as exc:  # unerwartetes Format
        raise SourceError(f"{c.get('name')}: {type(exc).__name__}: {exc}"[:300]) from exc
