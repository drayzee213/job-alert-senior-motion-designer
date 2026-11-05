"""Nachvollziehbares Punktesystem für die Relevanz einer Anzeige."""
from __future__ import annotations

import html
import re
from functools import lru_cache
from typing import Any

from .location import FOREIGN_RE, HYBRID_RE, classify_location
from .models import Job

TAG_RE = re.compile(r"<[^>]+>")


def plain_text(text: str) -> str:
    """HTML grob entfernen (für Beschreibungen aus den Feeds)."""
    if not text:
        return ""
    text = html.unescape(text)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)  # manche Feeds sind doppelt escaped
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=512)
def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.I)


def score_job(job: Job, cfg: dict[str, Any]) -> Job:
    """Setzt job.score, job.category, job.reasons, job.location_label."""
    rules = cfg["bewertung"]
    title = job.title or ""
    desc = plain_text(job.description)
    reasons: list[str] = []
    score = 0

    # 1) Ausschlüsse
    for pat in rules.get("ausschluss_titel", []):
        m = _rx(pat).search(title)
        if m:
            job.score, job.category = -999, "nein"
            job.reasons = [f"ausgeschlossen: „{m.group(0)}“ im Titel"]
            job.location_label = job.location
            return job
    for pat in rules.get("ausschluss_beschreibung", []):
        m = _rx(pat).search(desc)
        if m:
            job.score, job.category = -999, "nein"
            job.reasons = [f"ausgeschlossen: „{m.group(0)}“ im Text"]
            job.location_label = job.location
            return job

    # 2) Titel
    title_labels = []
    strong_title = False
    for rule in rules.get("titel", []):
        if _rx(rule["muster"]).search(title):
            score += int(rule["punkte"])
            title_labels.append(rule["label"])
            strong_title = strong_title or not rule.get("schwach")
    title_labels = _dedupe_labels(title_labels)
    if title_labels:
        reasons.append(", ".join(title_labels) + " im Titel")

    # 3) Beschreibung (gedeckelt)
    desc_cfg = rules.get("beschreibung", {})
    desc_points, desc_labels, motion_in_desc, specific_in_desc = 0, [], False, False
    for rule in desc_cfg.get("regeln", []):
        if desc and _rx(rule["muster"]).search(desc):
            desc_points += int(rule["punkte"])
            motion_in_desc = motion_in_desc or bool(rule.get("motion"))
            specific_in_desc = specific_in_desc or bool(rule.get("spezifisch"))
            if rule["label"] not in title_labels:
                desc_labels.append(rule["label"])
    desc_points = min(desc_points, int(desc_cfg.get("max_punkte", 40)))
    score += desc_points
    if desc_labels:
        reasons.append(", ".join(desc_labels) + " in der Beschreibung")

    # 4) Seniorität
    senior = rules.get("senior", {})
    if senior and _rx(senior["muster"]).search(title):
        score += int(senior.get("punkte", 10))
        reasons.append("Senior-Level")

    # 5) Abzüge
    for rule in rules.get("abzug_titel", []):
        if _rx(rule["muster"]).search(title):
            score += int(rule["punkte"])

    # 6) Ort
    loc_points = rules.get("ort", {})
    kind, label = classify_location(job.location, job.remote, title, desc)
    if (job.source == "arbeitsagentur" and job.location and kind in ("unbekannt", "ausland")
            and not FOREIGN_RE.search(job.location) and not label.startswith("Deutschland")):
        kind = "anderer_ort_de"  # Arbeitsagentur-Stellen ohne Auslandsbezug liegen in Deutschland
    job.location_label = label
    score += int(loc_points.get(kind, 0))
    if kind == "berlin":
        reasons.append("in Berlin" if re.search(r"(?i)\bberlin\b", job.location or "Berlin")
                       else "Berliner Umland")
    elif kind == "remote_de":
        reasons.append("Remote")
    elif kind == "remote_unklar":
        reasons.append("Homeoffice teilweise möglich" if HYBRID_RE.search(label)
                       else "Remote möglich (Region prüfen)")
    elif kind == "remote_im_text":
        reasons.append("nicht Berlin – nur passend, falls wirklich Remote (bitte prüfen)")
    elif kind in ("anderer_ort_de", "hybrid_anderer_ort"):
        reasons.append(f"vor Ort in {job.location}")
    elif kind == "ausland":
        reasons.append("Ausland")

    # Ohne starken Fachbegriff im Titel braucht es einen Motion-Bezug im Anzeigentext
    # (z. B. "Product Designer" nur mit Rive/Lottie/Animation/Gamification ...)
    if not strong_title and not motion_in_desc:
        score = min(score, 0)
    # Ganz ohne Fachbegriff im Titel (z. B. "Customer Success Manager") nur bei sehr
    # eindeutigen Stichworten im Text (Rive, Lottie, Character Animation, Maskottchen)
    if not title_labels and not specific_in_desc:
        score = min(score, 0)

    job.score = score
    job.reasons = reasons
    if score >= int(rules.get("sofort_ab", 60)):
        job.category = "sofort"
    elif score >= int(rules.get("vielleicht_ab", 30)):
        job.category = "vielleicht"
    else:
        job.category = "nein"
    return job


def _dedupe_labels(labels: list[str]) -> list[str]:
    """'Motion' ist überflüssig, wenn 'Motion Design' schon da ist usw."""
    out = []
    for lab in labels:
        if any(lab != other and lab.lower() in other.lower() for other in labels):
            continue
        out.append(lab)
    return out


def reason_sentence(job: Job) -> str:
    if job.ai_note:
        return job.ai_note
    if not job.reasons:
        return ""
    return "; ".join(job.reasons) + "."
