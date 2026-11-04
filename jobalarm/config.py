"""Lädt config.yaml und firmen.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or ROOT / "config.yaml")


def load_companies(path: Path | None = None) -> list[dict[str, Any]]:
    data = load_yaml(path or ROOT / "firmen.yaml")
    companies = []
    for entry in data.get("firmen") or []:
        if not isinstance(entry, dict) or not entry.get("system"):
            continue
        if entry.get("aktiv", True) is False:
            continue
        companies.append(entry)
    return companies
