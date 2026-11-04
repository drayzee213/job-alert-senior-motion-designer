"""Optionale KI-Bewertung mit Claude (standardmäßig AUS).

Wird nur benutzt, wenn in config.yaml ki_bewertung.aktiv: true steht UND das
GitHub-Secret ANTHROPIC_API_KEY gesetzt ist. Bei jedem Fehler gilt die Regel-Bewertung.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from .models import Job

PROFILE = """Kandidat: Motion Designer aus Berlin, ca. 10 Jahre Erfahrung.
Stärken: Character Animation, After Effects, Rive, Lottie, etwas UX/UI und Figma.
Sucht: Festanstellung (Senior/erfahren), Berlin oder remote in Deutschland.
Passend: Motion Designer für Apps/Produkte/UI, Rive Animator/Designer, Lottie, Character
Animator für Apps oder Games, Product/UX/UI Designer mit Motion- oder Gamification-Schwerpunkt.
Nicht passend: reiner Videoschnitt/Cutter, Social-Media-Content-Fließband, Praktikum,
Werkstudent, Junior, Freelance-Plattformen, Jobs außerhalb Deutschlands ohne Remote-Option."""

INSTRUCTION = """Bewerte, wie gut diese Stellenanzeige zum Kandidaten passt.
Antworte ausschließlich mit JSON in genau dieser Form:
{"kategorie": "sofort" | "vielleicht" | "nein", "punkte": 0-100, "grund": "ein kurzer deutscher Satz"}
"sofort" = klar passend, "vielleicht" = teilweise passend, "nein" = unpassend."""


def enabled(cfg: dict[str, Any]) -> bool:
    return bool((cfg.get("ki_bewertung") or {}).get("aktiv")) and bool(os.environ.get("ANTHROPIC_API_KEY"))


def review(jobs: list[Job], cfg: dict[str, Any]) -> int:
    """Bewertet bis zu max_pro_lauf Anzeigen neu. Gibt die Anzahl erfolgreicher Bewertungen zurück."""
    if not enabled(cfg):
        return 0
    try:
        import anthropic
    except ImportError:
        print("KI-Bewertung: Paket 'anthropic' fehlt – nutze Regel-Bewertung.")
        return 0
    kcfg = cfg["ki_bewertung"]
    model = kcfg.get("modell", "claude-opus-5-5")
    client = anthropic.Anthropic()
    done = 0
    candidates = [j for j in jobs if j.score >= int(kcfg.get("ab_punkten", 20))]
    for job in candidates[: int(kcfg.get("max_pro_lauf", 10))]:
        text = (f"Titel: {job.title}\nFirma: {job.company}\nOrt: {job.location}\n"
                f"Remote: {job.remote}\nBeschreibung:\n{job.description[:6000]}")
        try:
            response = client.messages.create(
                model=model,
                max_tokens=2000,
                output_config={"effort": "low"},
                system=PROFILE,
                messages=[{"role": "user", "content": f"{INSTRUCTION}\n\n{text}"}],
            )
        except anthropic.APIError as exc:
            print(f"KI-Bewertung fehlgeschlagen ({type(exc).__name__}) – Regel-Bewertung bleibt.")
            break
        if response.stop_reason == "refusal":
            continue
        answer = "".join(b.text for b in response.content if b.type == "text")
        m = re.search(r"\{.*\}", answer, re.S)
        if not m:
            continue
        try:
            data = json.loads(m.group(0))
        except ValueError:
            continue
        cat = data.get("kategorie")
        if cat in ("sofort", "vielleicht", "nein"):
            job.category = cat
            job.ai_note = f"KI: {data.get('grund', '').strip()}"
            done += 1
    return done
