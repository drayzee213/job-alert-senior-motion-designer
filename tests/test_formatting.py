from jobalarm.config import load_config
from jobalarm.formatting import format_digest, format_job, format_status, format_warning
from jobalarm.models import Job
from jobalarm.scoring import score_job
from jobalarm.telegram import split_message

CFG = load_config()


def sample(**kw):
    data = dict(source="arbeitsagentur", source_id="1", title="Senior Motion Designer – Character Animation & Rive",
                company="Applimeda GmbH", location="Remote", remote=True,
                url="https://example.com/job?id=1&x=<2>", posted="2026-11-03",
                salary="60.000–75.000 € / Jahr", source_label="Arbeitsagentur")
    data.update(kw)
    return score_job(Job(**data), CFG)


def test_nachricht_enthaelt_alle_felder():
    msg = format_job(sample())
    assert "<b>Senior Motion Designer – Character Animation &amp; Rive</b>" in msg
    assert "🏢 Applimeda GmbH" in msg
    assert "📍 Remote" in msg
    assert "💶 60.000–75.000 € / Jahr" in msg
    assert "📅 03.11.2026 · Arbeitsagentur" in msg
    assert "💡 " in msg and "Rive" in msg
    assert '<a href="https://example.com/job?id=1&amp;x=&lt;2&gt;">Zur Anzeige</a>' in msg


def test_nachricht_ohne_gehalt_und_datum():
    msg = format_job(sample(salary=None, posted=None))
    assert "💶" not in msg
    assert "📅 unbekannt" in msg


def test_nachricht_ist_kurz_genug_fuers_handy():
    msg = format_job(sample())
    assert len(msg) < 700
    assert len(msg.splitlines()) <= 9


def test_sammelnachricht_nummeriert():
    jobs = [sample(source_id=str(i), title=f"Motion Designer {i}") for i in range(3)]
    msg = format_digest(jobs)
    assert "3 Anzeigen" in msg
    assert "1. <b>Motion Designer 0</b>" in msg and "3. <b>Motion Designer 2</b>" in msg


def test_lange_sammelnachricht_wird_geteilt():
    jobs = [sample(source_id=str(i), title=f"Motion Designer {i} " + "x" * 200) for i in range(40)]
    parts = split_message(format_digest(jobs))
    assert len(parts) > 1
    assert all(len(p) <= 4000 for p in parts)
    # Kein Eintrag wird mitten im Link zerschnitten
    assert all(p.count("<a ") == p.count("</a>") for p in parts)


def test_warnung_und_status():
    assert "Arbeitsagentur" in format_warning("Arbeitsagentur", "HTTP 503", 3)
    status = {"paused": False, "today": {"sofort": 2, "vielleicht": 1}, "seen_count": 10,
              "sources": {"Indeed": {"fails": 0, "last_count": 5},
                          "LinkedIn": {"fails": 4},
                          "Firma A": {"fails": 0}, "Firma B": {"fails": 1}}}
    text = format_status(status, "04.11.2026 12:17 Uhr")
    assert "2 sofort" in text
    assert "❌ LinkedIn" in text
    assert "Firmen-Karriereseiten: 1 von 2 ok" in text
