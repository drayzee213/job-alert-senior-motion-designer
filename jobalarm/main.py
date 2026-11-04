"""Ein Lauf des Job-Alarms: Befehle lesen, Quellen abfragen, bewerten, melden, speichern."""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from . import ai, formatting, linkcheck
from .config import load_companies, load_config
from .dedupe import fingerprint, is_duplicate
from .models import Job, SourceError
from .scoring import score_job
from .sources import arbeitnow, arbeitsagentur, ats, jobspy_source
from .state import State
from .telegram import Telegram

TZ = ZoneInfo("Europe/Berlin")
MAX_ENRICH = 25


def _hm(text: str) -> tuple[int, int]:
    h, m = text.split(":")
    return int(h), int(m)


def in_window(now: datetime, cfg: dict[str, Any]) -> bool:
    n = cfg.get("benachrichtigung", {})
    start, end = _hm(n.get("aktiv_von", "07:00")), _hm(n.get("aktiv_bis", "22:30"))
    return start <= (now.hour, now.minute) <= end


def collect(cfg: dict[str, Any], state: State, now: datetime, force: bool,
            log: list[str]) -> tuple[list[Job], dict[str, str | None], dict[str, int]]:
    """Fragt alle aktiven Quellen ab. Gibt (Anzeigen, Fehler je Quelle, Anzahl je Quelle) zurück."""
    q = cfg["quellen"]
    jobs: list[Job] = []
    errors: dict[str, str | None] = {}
    counts: dict[str, int] = {}

    def run(name: str, fn) -> None:
        t0 = time.time()
        try:
            result = fn()
        except SourceError as exc:
            errors[name] = str(exc)
            log.append(f"❌ {exc}")
            return
        except Exception as exc:  # nichts darf den ganzen Lauf abbrechen
            errors[name] = f"{type(exc).__name__}: {exc}"[:300]
            log.append(f"❌ {name}: {errors[name]}")
            return
        errors[name] = None
        counts[name] = len(result)
        for job in result:
            job.feed = name
        jobs.extend(result)
        log.append(f"✅ {name}: {len(result)} Anzeigen ({time.time() - t0:.1f}s)")

    if q.get("arbeitsagentur", {}).get("aktiv"):
        run("Arbeitsagentur", lambda: arbeitsagentur.fetch(cfg))
    if q.get("arbeitnow", {}).get("aktiv"):
        run("Arbeitnow", lambda: arbeitnow.fetch(cfg))
    if q.get("firmen", {}).get("aktiv"):
        for company in load_companies():
            run(f"Firma {company.get('name')}", lambda c=company: ats.fetch_company(c))
            time.sleep(0.3)

    js = q.get("jobspy", {})
    if js.get("aktiv"):
        last = state.status.get("last_jobspy_run")
        due = force or not last or (
            now - datetime.fromisoformat(last) >= timedelta(minutes=int(js.get("alle_minuten", 120)) - 5))
        if due:
            t0 = time.time()
            try:
                results = jobspy_source.fetch(cfg)
            except Exception as exc:  # z.B. Importfehler
                results = {s: SourceError(f"jobspy: {type(exc).__name__}: {exc}"[:300])
                           for s in {a["seite"] for a in js.get("abfragen", [])}}
            state.status["last_jobspy_run"] = now.isoformat(timespec="minutes")
            for site, res in results.items():
                name = jobspy_source.LABELS.get(site, site)
                if isinstance(res, SourceError):
                    errors[name] = str(res)
                    log.append(f"❌ {res}")
                else:
                    errors[name] = None
                    counts[name] = len(res)
                    for job in res:
                        job.feed = name
                    jobs.extend(res)
                    log.append(f"✅ {name}: {len(res)} Anzeigen")
            log.append(f"   (Indeed/LinkedIn zusammen {time.time() - t0:.0f}s)")
        else:
            log.append("⏭ Indeed/LinkedIn: diesmal ausgelassen (nur alle "
                       f"{js.get('alle_minuten', 120)} Minuten)")
    return jobs, errors, counts


def update_source_health(state: State, errors: dict[str, str | None], counts: dict[str, int],
                         cfg: dict[str, Any], tg: Telegram, now: datetime) -> None:
    limit = int(cfg.get("benachrichtigung", {}).get("warnung_nach_fehlern", 3))
    for name, err in errors.items():
        info = state.status["sources"].setdefault(name, {"fails": 0})
        if err is None:
            if info.get("alerted"):
                _safe_send(tg, formatting.format_recovered(name))
            info.update({"fails": 0, "alerted": False, "last_ok": now.isoformat(timespec="minutes"),
                         "last_count": counts.get(name, 0), "last_error": None})
        else:
            info["fails"] = int(info.get("fails", 0)) + 1
            info["last_error"] = err[:300]
            if info["fails"] >= limit and not info.get("alerted"):
                _safe_send(tg, formatting.format_warning(name, err, info["fails"]))
                info["alerted"] = True
    # Quellen, die es nicht mehr gibt (z.B. Firma gelöscht), aus dem Status entfernen
    active_companies = {f"Firma {c.get('name')}" for c in load_companies()}
    for name in list(state.status["sources"]):
        if name.startswith("Firma ") and name not in active_companies:
            del state.status["sources"][name]


def _safe_send(tg: Telegram, text: str) -> bool:
    try:
        tg.send(text)
        return True
    except RuntimeError as exc:
        print(f"Senden fehlgeschlagen: {exc}", file=sys.stderr)
        return False


def is_recent(job: Job, today: str, days: int) -> bool:
    if not job.posted:
        return False
    limit = (datetime.fromisoformat(today) - timedelta(days=days)).date().isoformat()
    return job.posted[:10] >= limit


def run(args: argparse.Namespace) -> int:
    cfg = load_config()
    now = datetime.now(TZ)
    today = now.date().isoformat()
    log: list[str] = []
    state = State()
    first_run = not state.initialized

    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not args.dry_run and (not token or not chat_id):
        print("FEHLER: Die GitHub-Secrets TELEGRAM_TOKEN und/oder TELEGRAM_CHAT_ID fehlen. "
              "Siehe README, Schritt 4.", file=sys.stderr)
        return 2
    tg = Telegram(token, chat_id, dry_run=args.dry_run)

    if not args.force and not in_window(now, cfg):
        print(f"{now:%H:%M} Uhr – außerhalb der Zeit {cfg['benachrichtigung']['aktiv_von']}–"
              f"{cfg['benachrichtigung']['aktiv_bis']}, nichts zu tun.")
        return 0

    # ---- 1) Telegram-Befehle
    want_status = False
    try:
        commands, offset = tg.get_commands(state.status.get("tg_offset"))
        state.status["tg_offset"] = offset
    except RuntimeError as exc:
        commands = []
        log.append(f"⚠️ Telegram-Befehle nicht lesbar: {exc}")
    for cmd in commands:
        if cmd == "/pause":
            state.status["paused"] = True
            _safe_send(tg, "⏸ <b>Pausiert.</b> Ich melde mich nicht mehr, bis du /weiter schickst.")
        elif cmd in ("/weiter", "/resume", "/fortsetzen"):
            state.status["paused"] = False
            _safe_send(tg, "▶️ <b>Läuft wieder.</b> Neue Anzeigen kommen ab dem nächsten Lauf.")
        elif cmd == "/status":
            want_status = True
        elif cmd in ("/start", "/hilfe", "/help"):
            _safe_send(tg, formatting.HELP_TEXT)
    if commands:
        log.append(f"📨 Befehle: {' '.join(commands)}")

    if state.status.get("paused"):
        log.append("⏸ Pausiert – keine Abfragen.")
        finish(state, tg, args, now, log, want_status, {})
        return 0

    # ---- 2) Quellen abfragen
    jobs, errors, counts = collect(cfg, state, now, args.force, log)
    update_source_health(state, errors, counts, cfg, tg, now)

    # ---- 3) Neue Anzeigen bewerten
    new_jobs: list[Job] = []
    resend: list[Job] = []
    resend_uids: set[str] = set()
    seen_uids: set[str] = set()
    for job in jobs:
        if job.uid in seen_uids:
            continue
        seen_uids.add(job.uid)
        if state.is_known(job.uid):
            state.touch(job.uid, today)
            if args.recent_days and state.seen[job.uid].get("r") == "still":
                resend.append(score_job(job, cfg))
                resend_uids.add(job.uid)
            continue
        new_jobs.append(score_job(job, cfg))

    enriched = 0
    for job in new_jobs:
        if (job.source == "arbeitsagentur" and job.score > 0 and enriched < MAX_ENRICH
                and cfg["quellen"]["arbeitsagentur"].get("details_laden", True)):
            arbeitsagentur.enrich(job)
            score_job(job, cfg)
            enriched += 1
            time.sleep(0.3)
    if ai.enabled(cfg):
        n = ai.review([j for j in new_jobs if j.score > 0], cfg)
        log.append(f"🤖 KI-Bewertung: {n} Anzeigen geprüft")

    # ---- 4) Duplikate entfernen und einsortieren
    seeded = set(state.status.get("seeded_feeds", []))
    known_fps = state.notified_fingerprints()
    candidates = sorted([j for j in new_jobs + resend if j.category in ("sofort", "vielleicht")],
                        key=lambda j: j.score, reverse=True)
    to_send: list[Job] = []
    to_digest: list[Job] = []
    silent = 0
    for job in candidates:
        fp = fingerprint(job.company, job.title)
        is_resend = job.uid in resend_uids
        if not is_resend and is_duplicate(fp, known_fps):
            state.remember(job.uid, fp, "dup", today)
            continue
        known_fps.add(fp)
        # Neue Quelle (erster Lauf, neue Firma, Quelle bisher immer gestört): Bestand still merken
        source_is_new = job.feed not in seeded
        wanted = (not source_is_new and not is_resend) or (
            args.recent_days and is_recent(job, today, args.recent_days))
        if not wanted:
            state.remember(job.uid, fp, "still", today)
            silent += 1
            continue
        (to_send if job.category == "sofort" else to_digest).append(job)
    # irrelevante, aber thematisch nahe Anzeigen merken (spart erneutes Nachladen)
    for job in new_jobs:
        if job.category == "nein" and job.score > 0 and not state.is_known(job.uid):
            state.remember(job.uid, fingerprint(job.company, job.title), "nein", today)

    # ---- 5) Senden
    limit = int(cfg["benachrichtigung"].get("max_sofort_pro_lauf", 10))
    sent_now = 0
    for job in to_send:
        fp = fingerprint(job.company, job.title)
        if sent_now >= limit:
            to_digest.append(job)
            continue
        status, why = linkcheck.check(job)
        if status == linkcheck.DEAD:
            state.remember(job.uid, fp, "tot", today)
            log.append(f"🪦 Toter Link übersprungen: {job.title} ({why})")
            continue
        if _safe_send(tg, formatting.format_job(job)):
            state.remember(job.uid, fp, "sofort", today)
            state.count_today(today, "sofort")
            sent_now += 1
            log.append(f"📤 Sofort: {job.title} – {job.company} ({job.score} P., Link: {why})")
    for job in to_digest:
        state.remember(job.uid, fingerprint(job.company, job.title), "vielleicht", today)
        state.status["digest"].append(job.to_dict())
        log.append(f"📥 Vielleicht: {job.title} – {job.company} ({job.score} P.)")

    digest_at = _hm(cfg["benachrichtigung"].get("sammelnachricht_ab", "20:00"))
    digest_due = (now.hour, now.minute) >= digest_at and state.status.get("digest_date") != today
    if state.status["digest"] and (digest_due or args.recent_days):
        send_digest(state, tg, today, log)

    newly_seeded = sorted(name for name, err in errors.items() if err is None and name not in seeded)
    state.status["seeded_feeds"] = sorted(seeded | set(newly_seeded))
    if first_run:
        state.status["initialized_at"] = now.isoformat(timespec="minutes")
        failed = sorted(name for name, err in errors.items() if err)
        msg = ("✅ <b>Job-Alarm ist eingerichtet.</b>\n"
               f"{silent} passende Anzeigen, die schon online waren, habe ich still als bekannt "
               "gespeichert. Ab jetzt melde ich nur noch neue.")
        if args.recent_days:
            msg += f"\nPassende Anzeigen der letzten {args.recent_days} Tage habe ich dir geschickt."
        if failed:
            msg += ("\n\n⚠️ Diesmal nicht erreichbar: " + ", ".join(failed) +
                    ". Deren Bestand speichere ich still, sobald sie antworten.")
        _safe_send(tg, msg + "\n\n" + formatting.HELP_TEXT)
    elif newly_seeded and silent:
        log.append(f"🌱 Neue Quellen still übernommen: {', '.join(newly_seeded)} ({silent} Anzeigen)")

    log.append(f"Neu: {len(new_jobs)} · sofort gesendet: {sent_now} · vielleicht: {len(to_digest)}"
               f" · still gespeichert: {silent}")
    finish(state, tg, args, now, log, want_status, counts)
    return 0


def send_digest(state: State, tg: Telegram, today: str, log: list[str]) -> None:
    alive = []
    for data in state.status["digest"]:
        job = Job.from_dict(data)
        status, why = linkcheck.check(job)
        if status == linkcheck.DEAD:
            log.append(f"🪦 Sammelnachricht: toter Link entfernt: {job.title} ({why})")
            continue
        alive.append(job)
    if alive and _safe_send(tg, formatting.format_digest(alive)):
        state.count_today(today, "vielleicht", len(alive))
        log.append(f"🌙 Sammelnachricht mit {len(alive)} Anzeigen gesendet")
    state.status["digest"] = []
    state.status["digest_date"] = today


def finish(state: State, tg: Telegram, args: argparse.Namespace, now: datetime, log: list[str],
           want_status: bool, counts: dict[str, int]) -> None:
    today = now.date().isoformat()
    state.reset_today_if_needed(today)
    pruned = state.prune(today)
    if pruned:
        log.append(f"🧹 {pruned} alte Einträge vergessen")
    run_text = now.strftime("%d.%m.%Y %H:%M Uhr")
    # Nur einmal am Tag ändern, damit nicht jeder Lauf einen Commit erzeugt
    # (ein Commit pro Tag hält das Repo aktiv -> GitHub schaltet den Zeitplan nicht ab).
    state.status["heartbeat"] = today
    state.status["seen_count"] = len(state.seen)
    if want_status:
        _safe_send(tg, formatting.format_status({**state.status, "last_run_text": run_text}, run_text))
    if args.dry_run:
        log.append("🧪 Trockenlauf: nichts gespeichert, nichts gesendet.")
    else:
        state.save()
    report = "\n".join(log)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Job-Alarm Lauf " + run_text + "\n\n")
            fh.write("\n".join(f"- {line}" for line in log) + "\n")
            if tg.dry_run and tg.sent:
                fh.write("\n### Nachrichten (Trockenlauf, nicht gesendet)\n\n")
                for msg in tg.sent:
                    fh.write("```\n" + msg + "\n```\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Job-Alarm: neue Stellenanzeigen per Telegram")
    p.add_argument("--dry-run", action="store_true", help="nichts senden, nichts speichern")
    p.add_argument("--force", action="store_true", help="Zeitfenster ignorieren (für manuelle Läufe)")
    p.add_argument("--recent-days", type=int, default=0,
                   help="passende Anzeigen der letzten N Tage einmal schicken")
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
