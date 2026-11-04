"""Speichert, welche Anzeigen schon bekannt/gemeldet sind (Dateien im Ordner state/)."""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .config import ROOT

STATE_DIR = Path(os.environ.get("JOBALARM_STATE_DIR", ROOT / "state"))
FORGET_AFTER_DAYS = 45  # Anzeigen, die so lange in keiner Quelle mehr auftauchen, vergessen


def _read(path: Path, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)


class State:
    """seen.json: {uid: {"fp": Fingerabdruck, "first": Datum, "last": Datum, "r": Ergebnis}}"""

    def __init__(self, state_dir: Path | None = None):
        self.dir = Path(state_dir or STATE_DIR)
        self.seen_path = self.dir / "seen.json"
        self.status_path = self.dir / "status.json"
        seen = _read(self.seen_path, None)
        self.initialized = seen is not None
        self.seen: dict[str, dict[str, str]] = (seen or {}).get("jobs", {})
        self.status: dict[str, Any] = _read(self.status_path, {})
        self.status.setdefault("sources", {})
        self.status.setdefault("digest", [])
        self.status.setdefault("today", {})
        self.status.setdefault("paused", False)

    # ---- bekannte Anzeigen
    def is_known(self, uid: str) -> bool:
        return uid in self.seen

    def touch(self, uid: str, today: str) -> None:
        entry = self.seen.get(uid)
        if entry and entry.get("last") != today:
            entry["last"] = today

    def remember(self, uid: str, fp: str, result: str, today: str) -> None:
        self.seen[uid] = {"fp": fp, "first": today, "last": today, "r": result}

    def fingerprints(self) -> set[str]:
        return {e["fp"] for e in self.seen.values() if e.get("fp")}

    def notified_fingerprints(self) -> set[str]:
        """Fingerabdrücke von Anzeigen, die schon gemeldet oder still als gesehen markiert wurden."""
        return {e["fp"] for e in self.seen.values() if e.get("fp") and e.get("r") != "nein"}

    def prune(self, today: str) -> int:
        limit = (date.fromisoformat(today) - timedelta(days=FORGET_AFTER_DAYS)).isoformat()
        old = [uid for uid, e in self.seen.items() if (e.get("last") or e.get("first", "")) < limit]
        for uid in old:
            del self.seen[uid]
        return len(old)

    # ---- Tageszähler
    def count_today(self, today: str, key: str, n: int = 1) -> None:
        t = self.status["today"]
        if t.get("date") != today:
            t.clear()
            t["date"] = today
        t[key] = t.get(key, 0) + n

    def reset_today_if_needed(self, today: str) -> None:
        if self.status["today"].get("date") != today:
            self.status["today"] = {"date": today}

    def save(self) -> None:
        _write(self.seen_path, {"version": 1, "jobs": self.seen})
        _write(self.status_path, self.status)
