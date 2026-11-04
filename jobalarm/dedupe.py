"""Duplikaterkennung über Quellen hinweg: gleiche Firma + ähnlicher Titel."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

LEGAL_FORMS = re.compile(
    r"\b(gmbh|mbh|ag|se|ug|kg|kgaa|ohg|gbr|e\.?\s?v|co|inc|ltd|llc|plc|corp|corporation|"
    r"company|haftungsbeschränkt|haftungsbeschraenkt|holding|group|gruppe|deutschland|germany)\b",
    re.I,
)
GENDER = re.compile(
    r"\(\s*(m|w|f|d|x|i|div|all genders?|alle geschlechter|gn|mwd|wmd|fmd|mfd|fmx|mfx)"
    r"(\s*[/|,]\s*(m|w|f|d|x|i|div))*\s*\)|\*\s*in\b|:in\b|/in\b|\bm/w/d\b|\bw/m/d\b|\bf/m/d\b"
    r"|\bm/f/d\b|\bf/m/x\b|\bm/f/x\b|\ball genders\b",
    re.I,
)
NON_WORD = re.compile(r"[^a-z0-9äöüß ]+")


def _ascii_fold(text: str) -> str:
    text = text.lower().replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize_company(name: str) -> str:
    text = _ascii_fold(name or "")
    text = text.replace("&", " ")
    text = LEGAL_FORMS.sub(" ", text)
    text = NON_WORD.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(title: str) -> str:
    text = GENDER.sub(" ", title or "")
    text = _ascii_fold(text)
    text = text.replace("–", " ").replace("-", " ")
    text = NON_WORD.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def fingerprint(company: str, title: str) -> str:
    return f"{normalize_company(company)}|{normalize_title(title)}"


def same_company(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    # "applimeda" vs "applimeda health" -> gleich
    return len(shorter) >= 4 and (longer.startswith(shorter + " ") or longer == shorter)


def similar_titles(a: str, b: str, threshold: float = 0.85) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 12 and shorter in longer:
        return True
    return SequenceMatcher(None, a, b).ratio() >= threshold


def is_duplicate(fp: str, known: list[str] | set[str]) -> str | None:
    """Gibt den passenden bekannten Fingerabdruck zurück oder None."""
    company, _, title = fp.partition("|")
    if fp in known:
        return fp
    for other in known:
        o_company, _, o_title = other.partition("|")
        if same_company(company, o_company) and similar_titles(title, o_title):
            return other
    return None
