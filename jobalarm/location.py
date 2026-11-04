"""Einordnung des Arbeitsorts: Berlin, Remote in DE, andere Stadt, Ausland."""
from __future__ import annotations

import re

REMOTE_RE = re.compile(
    r"remote|home ?office|homeoffice|telearbeit|heim[- ]?arbeit|anywhere|ortsunabh|"
    r"mobiles arbeiten|mobile work|work from home|\bwfh\b|distributed|fully remote|100 ?% remote",
    re.I,
)
BERLIN_RE = re.compile(r"\bberlin\b", re.I)
GERMANY_RE = re.compile(
    r"germany|deutschland|\bdeu\b|\bde\b|bundesweit|\bdach\b|"
    r"europe|europa|\beu\b|\bemea\b|\bcet\b|\bcest\b|worldwide|weltweit|global|anywhere",
    re.I,
)
GERMAN_CITIES = [
    "hamburg", "münchen", "muenchen", "munich", "köln", "koeln", "cologne", "frankfurt",
    "stuttgart", "düsseldorf", "duesseldorf", "dusseldorf", "leipzig", "dresden", "hannover",
    "hanover", "nürnberg", "nuremberg", "bremen", "potsdam", "karlsruhe", "mannheim", "bonn",
    "münster", "essen", "dortmund", "duisburg", "bochum", "wuppertal", "bielefeld", "augsburg",
    "wiesbaden", "mainz", "aachen", "kiel", "lübeck", "freiburg", "heidelberg", "darmstadt",
    "regensburg", "würzburg", "erlangen", "ulm", "rostock", "magdeburg", "erfurt", "jena",
    "halle", "kassel", "braunschweig", "osnabrück", "oldenburg", "saarbrücken", "paderborn",
    "ingolstadt", "wolfsburg", "göttingen", "bamberg", "konstanz", "gütersloh", "walldorf",
    "unterföhring", "ismaning", "garching", "eschborn", "teltow", "kleinmachnow",
]
GERMAN_CITY_RE = re.compile(r"\b(" + "|".join(GERMAN_CITIES) + r")\b", re.I)
# Eindeutige Hinweise auf Orte außerhalb Deutschlands (ohne Anspruch auf Vollständigkeit)
FOREIGN_RE = re.compile(
    r"\b(usa|u\.s\.|united states|us only|\bus\b|canada|uk|united kingdom|england|london|"
    r"ireland|dublin|france|paris|spain|españa|madrid|barcelona|portugal|lisbon|lisboa|"
    r"netherlands|amsterdam|belgium|brussels|austria|österreich|wien|vienna|switzerland|"
    r"schweiz|zürich|zurich|poland|polska|warsaw|krakow|kraków|czech|prague|praha|"
    r"italy|italia|milan|rome|sweden|stockholm|denmark|copenhagen|norway|oslo|finland|"
    r"helsinki|estonia|tallinn|latvia|lithuania|romania|bucharest|hungary|budapest|greece|"
    r"turkey|istanbul|israel|tel aviv|india|bangalore|bengaluru|singapore|japan|tokyo|"
    r"china|shanghai|australia|sydney|brazil|são paulo|mexico|argentina|ukraine|kyiv|"
    r"serbia|belgrade|croatia|bulgaria|cyprus|malta|dubai|uae|new york|san francisco|"
    r"california|los angeles|seattle|austin|boston|chicago|pittsburgh|toronto|vancouver|"
    r"montreal|latam|apac|americas|north america)\b",
    re.I,
)
# "Remote" mit klarer Einschränkung auf eine andere Region
FOREIGN_REMOTE_RE = re.compile(
    r"remote\s*[-–(,:]?\s*(us|usa|u\.s\.|united states|canada|uk|united kingdom|india|latam|"
    r"americas|north america|apac|brazil|spain|poland|portugal|france|netherlands)\b",
    re.I,
)


def _remote_label(loc: str) -> str:
    if not loc:
        return "Remote"
    return loc if REMOTE_RE.search(loc) else f"Remote ({loc})"


def classify_location(location: str, remote_flag: bool | None = None, title: str = "",
                      description: str = "") -> tuple[str, str]:
    """Gibt (Kategorie, lesbares Label) zurück.

    Kategorien: berlin, remote_de, remote_unklar, anderer_ort_de, ausland, unbekannt
    """
    loc = (location or "").strip()
    text = f"{loc} {title}"
    remote = bool(remote_flag) or bool(REMOTE_RE.search(text))
    berlin = bool(BERLIN_RE.search(loc))
    german = bool(GERMANY_RE.search(loc) or GERMAN_CITY_RE.search(loc))
    foreign = bool(FOREIGN_RE.search(loc))
    foreign_remote = bool(FOREIGN_REMOTE_RE.search(text))

    if berlin:
        return "berlin", ("Berlin (auch Remote)" if remote else "Berlin") if loc else "Berlin"
    if remote and not foreign_remote and (german or not foreign):
        if german:
            return "remote_de", _remote_label(loc)
        return "remote_unklar", _remote_label(loc) if loc and not REMOTE_RE.fullmatch(loc) \
            else "Remote (Region nicht angegeben)"
    if remote and foreign and german:
        return "remote_unklar", _remote_label(loc)
    if german:
        if REMOTE_RE.search(description or ""):
            return "remote_unklar", f"{loc} (Remote evtl. möglich)"
        return "anderer_ort_de", loc
    if foreign or foreign_remote:
        return "ausland", loc or "Ausland"
    if not loc:
        return "unbekannt", "Ort nicht angegeben"
    return "unbekannt", loc
