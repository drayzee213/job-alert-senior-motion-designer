"""Telegram-Nachrichten (HTML-Format, handyfreundlich)."""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Any

from .models import Job
from .scoring import reason_sentence


def _date_de(iso: str | None) -> str:
    if not iso:
        return "unbekannt"
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return escape(iso)
    return d.strftime("%d.%m.%Y")


def format_job(job: Job) -> str:
    lines = [f"🎯 <b>{escape(job.title)}</b>"]
    lines.append(f"🏢 {escape(job.company or 'Firma unbekannt')}")
    lines.append(f"📍 {escape(job.location_label or job.location or 'Ort nicht angegeben')}")
    if job.salary:
        lines.append(f"💶 {escape(job.salary)}")
    lines.append(f"📅 {_date_de(job.posted)} · {escape(job.source_label or job.source)}")
    reason = reason_sentence(job)
    if reason:
        lines.append(f"💡 {escape(reason)}")
    lines.append(f"⭐ Relevanz: {job.score} Punkte")
    lines.append(f'🔗 <a href="{escape(job.url, quote=True)}">Zur Anzeige</a>')
    return "\n".join(lines)


def format_digest(jobs: list[Job]) -> str:
    head = f"🌙 <b>Vielleicht interessant – {len(jobs)} Anzeige{'n' if len(jobs) != 1 else ''}</b>"
    blocks = [head]
    for i, job in enumerate(jobs, 1):
        reason = reason_sentence(job)
        block = (
            f"{i}. <b>{escape(job.title)}</b>\n"
            f"   {escape(job.company or '?')} · {escape(job.location_label or job.location or '?')}\n"
        )
        if job.salary:
            block += f"   💶 {escape(job.salary)}\n"
        if reason:
            block += f"   💡 {escape(reason)}\n"
        block += f'   <a href="{escape(job.url, quote=True)}">Zur Anzeige</a> · {escape(job.source_label or job.source)} · {job.score} P.'
        blocks.append(block)
    return "\n\n".join(blocks)


def format_warning(source: str, error: str, fails: int) -> str:
    return (
        f"⚠️ <b>Quelle gestört: {escape(source)}</b>\n"
        f"Die letzten {fails} Abrufe sind fehlgeschlagen.\n"
        f"Letzter Fehler: <code>{escape(error[:300])}</code>\n"
        "Der Bot läuft mit den anderen Quellen weiter. Du bekommst eine Nachricht, "
        "sobald es wieder klappt."
    )


def format_recovered(source: str) -> str:
    return f"✅ <b>{escape(source)}</b> funktioniert wieder."


def format_status(status: dict[str, Any], now_text: str) -> str:
    today = status.get("today", {})
    lines = ["📊 <b>Status Job-Alarm</b>"]
    lines.append("⏸ <b>Pausiert</b> – mit /weiter wieder einschalten" if status.get("paused")
                 else "▶️ Aktiv")
    lines.append(f"🕒 Letzter Lauf: {escape(status.get('last_run_text') or now_text)}")
    lines.append(f"🎯 Heute gesendet: {today.get('sofort', 0)} sofort, "
                 f"{today.get('vielleicht', 0)} vielleicht (Sammelnachricht)")
    pending = len(status.get("digest", []))
    if pending:
        lines.append(f"📥 Für die Sammelnachricht vorgemerkt: {pending}")
    lines.append(f"📚 Bekannte Anzeigen: {status.get('seen_count', 0)}")
    lines.append("")
    lines.append("<b>Quellen</b>")
    sources = status.get("sources") or {}
    companies = {k: v for k, v in sources.items() if k.startswith("Firma ")}
    for name, info in sorted(sources.items()):
        if name in companies:
            continue
        lines.append(_source_line(name, info))
    if companies:
        broken = {k: v for k, v in companies.items() if v.get("fails", 0)}
        lines.append(f"{'✅' if not broken else '⚠️'} Firmen-Karriereseiten: "
                     f"{len(companies) - len(broken)} von {len(companies)} ok")
        for name, info in sorted(broken.items()):
            lines.append("   " + _source_line(name.removeprefix("Firma "), info))
    return "\n".join(lines)


def _source_line(name: str, info: dict[str, Any]) -> str:
    fails = int(info.get("fails", 0))
    if fails == 0:
        return f"✅ {escape(name)}: {info.get('last_count', 0)} Anzeigen"
    icon = "⚠️" if fails < 3 else "❌"
    return f"{icon} {escape(name)}: {fails}× fehlgeschlagen"


HELP_TEXT = (
    "🤖 <b>Job-Alarm – Befehle</b>\n"
    "/status – letzter Lauf, Treffer heute, Quellen\n"
    "/pause – keine Meldungen mehr, bis du /weiter schickst\n"
    "/weiter – wieder einschalten\n\n"
    "Hinweis: Der Bot liest Befehle nur bei seinem nächsten Lauf (ca. alle 30 Minuten "
    "zwischen 7 und 22 Uhr). Die Antwort kann also etwas dauern."
)
