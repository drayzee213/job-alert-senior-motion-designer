"""Gemeinsames Datenmodell für alle Quellen."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Job:
    source: str  # z.B. "arbeitsagentur", "indeed", "greenhouse:duolingo"
    source_id: str  # stabile ID innerhalb der Quelle
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str = ""
    remote: bool | None = None
    posted: str | None = None  # ISO-Datum (YYYY-MM-DD), falls bekannt
    salary: str | None = None
    source_label: str = ""  # lesbarer Quellenname für die Nachricht
    feed: str = ""  # Name der Abfrage im Status (z.B. "Arbeitsagentur", "Firma Duolingo")
    # Ergebnis der Bewertung (wird von scoring.py gesetzt)
    score: int = 0
    category: str = ""  # "sofort", "vielleicht", "nein"
    reasons: list[str] = field(default_factory=list)
    location_label: str = ""
    ai_note: str = ""

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.source_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


class SourceError(Exception):
    """Eine Quelle hat nicht geantwortet, blockiert oder Unsinn geliefert."""
