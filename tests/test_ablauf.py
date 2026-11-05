"""Testet einen kompletten Lauf ohne Internet (Quellen, Linkprüfung und Telegram sind ersetzt)."""
import pytest

from jobalarm import linkcheck, main, state as state_mod
from jobalarm.models import Job

SENT: list[str] = []
FAILING: dict[str, str] = {}


class FakeTelegram:
    def __init__(self, token, chat_id, dry_run=False):
        self.dry_run = dry_run
        self.sent = SENT
        self.commands: list[str] = []

    def send(self, text, preview=False):
        SENT.append(text)

    def get_commands(self, offset):
        cmds, FakeTelegram.pending = list(FakeTelegram.pending), []
        return cmds, (offset or 0) + len(cmds)


FakeTelegram.pending = []


def job(i, title, company="Firma GmbH", source="arbeitsagentur", location="Berlin", posted="2026-11-03",
        description=""):
    return Job(source=source, source_id=str(i), title=title, company=company, location=location,
               url=f"https://example.com/{source}/{i}", posted=posted, source_label=source,
               description=description)


@pytest.fixture
def env(tmp_path, monkeypatch):
    SENT.clear()
    FAILING.clear()
    FakeTelegram.pending = []
    monkeypatch.setattr(state_mod, "STATE_DIR", tmp_path)
    monkeypatch.setattr(main, "Telegram", FakeTelegram)
    monkeypatch.setenv("TELEGRAM_TOKEN", "x")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setattr(main.time, "sleep", lambda s: None)
    monkeypatch.setattr(main.arbeitsagentur, "enrich", lambda j: None)
    dead: set[str] = set()
    monkeypatch.setattr(linkcheck, "check", lambda j: ("dead", "404") if j.url in dead else ("ok", "200"))
    feed: list[Job] = []

    def fake_collect(cfg, state, now, force, log):
        names = {}
        for j in feed:
            j.feed = j.feed or "Arbeitsagentur"
            names[j.feed] = names.get(j.feed, 0) + 1
        errors = {name: None for name in names} or {"Arbeitsagentur": None}
        errors.update(FAILING)
        return [j for j in feed if j.feed not in FAILING], errors, names

    monkeypatch.setattr(main, "collect", fake_collect)
    return feed, dead


def run(*args):
    return main.main(["--force", *args])


def job_messages():
    return [m for m in SENT if m.startswith("🎯")]


def test_erster_lauf_still_dann_nur_neue(env):
    feed, _ = env
    feed.append(job(1, "Senior Motion Designer (m/w/d)"))
    assert run() == 0
    assert job_messages() == []
    assert any("eingerichtet" in m for m in SENT)

    SENT.clear()
    feed.append(job(2, "Senior Rive Animator (m/w/d)", company="Neue Firma"))
    run()
    msgs = job_messages()
    assert len(msgs) == 1 and "Senior Rive Animator" in msgs[0]

    SENT.clear()
    run()  # nichts Neues -> nichts senden
    assert job_messages() == []


def test_erster_lauf_mit_option_letzte_7_tage(env):
    feed, _ = env
    feed.append(job(1, "Senior Motion Designer", posted="2026-11-03"))
    feed.append(job(2, "Senior Rive Designer", company="Alt GmbH", posted="2020-01-01"))
    # Datum relativ zu heute setzen, damit der Test nicht veraltet
    from datetime import date, timedelta
    feed[0].posted = (date.today() - timedelta(days=2)).isoformat()
    run("--recent-days", "7")
    msgs = job_messages()
    assert len(msgs) == 1 and "Senior Motion Designer" in msgs[0]


def test_duplikat_aus_zweiter_quelle_wird_nicht_gemeldet(env):
    feed, _ = env
    run()  # Erster Lauf (leer)
    SENT.clear()
    feed.append(job(1, "Senior Motion Designer (m/w/d)", company="Applimeda GmbH"))
    feed.append(job("in-9", "Senior Motion Designer", company="Applimeda", source="indeed"))
    run()
    assert len(job_messages()) == 1
    SENT.clear()
    feed.append(job("li-5", "Senior Motion Designer – Rive", company="Applimeda", source="linkedin"))
    run()
    assert job_messages() == []


def test_toter_link_wird_nicht_gesendet(env):
    feed, dead = env
    run()
    SENT.clear()
    j = job(1, "Senior Motion Designer")
    dead.add(j.url)
    feed.append(j)
    run()
    assert job_messages() == []


def test_vielleicht_kommt_in_die_sammelnachricht(env, monkeypatch):
    feed, _ = env
    real_hm = main._hm
    # Sammelzeit "20:00" tagsüber noch nicht erreicht (unabhängig von der echten Uhrzeit)
    monkeypatch.setattr(main, "_hm", lambda text: (24, 0) if text == "20:00" else real_hm(text))
    run()
    SENT.clear()
    feed.append(job(1, "Motion Designer (m/w/d)", location="München",
                    description="Wir arbeiten mit Rive und After Effects."))
    run()
    assert job_messages() == []
    st = state_mod.State()
    assert len(st.status["digest"]) == 1
    # Abends wird gesammelt verschickt
    monkeypatch.setattr(main, "_hm", lambda text: (0, 0) if text == "20:00" else real_hm(text))
    run()
    assert any(m.startswith("🌙") and "Motion Designer" in m for m in SENT)
    assert state_mod.State().status["digest"] == []


def test_pause_und_weiter(env):
    feed, _ = env
    run()
    SENT.clear()
    FakeTelegram.pending = ["/pause"]
    feed.append(job(1, "Senior Motion Designer"))
    run()
    st = state_mod.State()
    assert st.status["paused"] is True
    assert job_messages() == []  # während der Pause nichts melden
    SENT.clear()
    FakeTelegram.pending = ["/weiter", "/status"]
    run()
    assert any("Läuft wieder" in m for m in SENT)
    assert any("Status Job-Alarm" in m for m in SENT)
    assert len(job_messages()) == 1


def test_neue_firma_wird_still_uebernommen(env):
    feed, _ = env
    run()
    SENT.clear()
    old = job(1, "Senior Motion Designer", company="Neu AG", source="greenhouse:neu")
    old.feed = "Firma Neu AG"
    feed.append(old)
    run()  # Firma zum ersten Mal dabei -> Bestand still
    assert job_messages() == []
    fresh = job(2, "Senior Rive Animator", company="Neu AG", source="greenhouse:neu")
    fresh.feed = "Firma Neu AG"
    feed.append(fresh)
    run()
    assert len(job_messages()) == 1


def test_gestoerte_quelle_beim_ersten_lauf_flutet_spaeter_nicht(env):
    feed, _ = env
    FAILING["Indeed"] = "HTTP 429"
    j = job("in-1", "Senior Motion Designer", company="Alt GmbH", source="indeed")
    j.feed = "Indeed"
    feed.append(j)
    run()
    assert any("nicht erreichbar: Indeed" in m for m in SENT)
    SENT.clear()
    FAILING.clear()
    run()  # Indeed antwortet jetzt -> alte Anzeige still übernehmen
    assert job_messages() == []


def test_mindestabstand_verhindert_doppelte_abfrage(env, monkeypatch):
    feed, _ = env
    run()
    calls = []
    real = main.collect
    monkeypatch.setattr(main, "collect", lambda *a, **k: calls.append(1) or real(*a, **k))
    FakeTelegram.pending = ["/status"]
    main.main(["--force", "--min-abstand", "20"])
    assert calls == []  # gerade erst abgefragt -> nur Befehle
    assert any("Status Job-Alarm" in m for m in SENT)


def test_alle_zeigt_bekannte_und_neue_nach_relevanz(env):
    feed, dead = env
    feed.append(job(1, "Motion Designer (m/w/d)", company="Alt A"))          # Berlin, ~60 P.
    feed.append(job(2, "Character Animator", company="Alt B", location="Hamburg"))  # vielleicht
    feed.append(job(3, "Senior Backend Engineer", company="Egal"))           # unpassend
    run()  # erster Lauf: alles still
    assert job_messages() == []
    SENT.clear()
    feed.append(job(4, "Senior Motion Designer – Rive", company="Neu C"))   # neu, stärkster Treffer
    tot = job(5, "Senior Lottie Animator", company="Weg D")
    dead.add(tot.url)
    feed.append(tot)
    FakeTelegram.pending = ["/alle"]
    run()
    lists = [m for m in SENT if m.startswith("📋")]
    assert len(lists) == 1
    text = lists[0]
    assert text.index("Senior Motion Designer – Rive") < text.index("Motion Designer (m/w/d)") < text.index("Character Animator")
    assert "🆕 <b>Senior Motion Designer – Rive" in text
    assert "Backend" not in text and "Lottie" not in text
    assert job_messages() == []  # neue Stelle nicht zusätzlich einzeln
    SENT.clear()
    run()  # danach wird die schon gelistete Stelle nicht noch einmal als neu gemeldet
    assert job_messages() == []


def test_alle_ohne_treffer(env):
    feed, _ = env
    feed.append(job(1, "Senior Backend Engineer"))
    run()
    SENT.clear()
    run("--uebersicht")
    assert any(m.startswith("📋") and "keine passende Stelle" in m for m in SENT)
