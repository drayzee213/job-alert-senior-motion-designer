"""Telegram senden und Befehle (/status, /pause, /weiter) abholen.

Ohne eigenen Server: Befehle werden beim nächsten Lauf per getUpdates abgeholt
(Telegram hebt sie 24 Stunden auf).
"""
from __future__ import annotations

import time
from typing import Any

import requests

API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 4000  # Telegram-Grenze ist 4096 Zeichen


class Telegram:
    def __init__(self, token: str, chat_id: str, dry_run: bool = False):
        self.token = token
        self.chat_id = str(chat_id)
        self.dry_run = dry_run
        self.sent: list[str] = []

    def _call(self, method: str, payload: dict[str, Any], timeout: float = 30) -> dict[str, Any]:
        url = API.format(token=self.token, method=method)
        for attempt in range(4):
            try:
                resp = requests.post(url, json=payload, timeout=timeout)
            except requests.RequestException as exc:
                if attempt == 3:
                    raise RuntimeError(f"Telegram nicht erreichbar: {type(exc).__name__}") from None
                time.sleep(2 * (attempt + 1))
                continue
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if resp.status_code == 429:
                time.sleep(int((data.get("parameters") or {}).get("retry_after", 5)) + 1)
                continue
            if not data.get("ok"):
                # Fehlermeldung ohne Token ausgeben
                raise RuntimeError(f"Telegram {method}: HTTP {resp.status_code} {data.get('description', '')}")
            return data
        raise RuntimeError(f"Telegram {method}: zu viele Versuche")

    def send(self, html_text: str, preview: bool = False) -> None:
        for chunk in split_message(html_text):
            self.sent.append(chunk)
            if self.dry_run:
                print("---- [Trockenlauf] Telegram-Nachricht ----\n" + chunk + "\n")
                continue
            self._call("sendMessage", {
                "chat_id": self.chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": not preview},
            })
            time.sleep(1.1)  # Telegram erlaubt ca. 1 Nachricht/Sekunde pro Chat

    def get_commands(self, offset: int | None) -> tuple[list[str], int | None]:
        """Holt neue Befehle aus dem eigenen Chat. Gibt (Befehle, neuer Offset) zurück."""
        if self.dry_run:
            return [], offset
        payload: dict[str, Any] = {"timeout": 0, "allowed_updates": ["message"]}
        if offset:
            payload["offset"] = offset
        data = self._call("getUpdates", payload)
        commands, new_offset = [], offset
        for upd in data.get("result", []):
            new_offset = max(new_offset or 0, int(upd["update_id"]) + 1)
            msg = upd.get("message") or {}
            if str((msg.get("chat") or {}).get("id")) != self.chat_id:
                continue  # fremde Chats ignorieren
            text = (msg.get("text") or "").strip()
            if text.startswith("/"):
                commands.append(text.split()[0].split("@")[0].lower())
        return commands, new_offset


def split_message(text: str, limit: int = MAX_LEN) -> list[str]:
    """Lange Nachrichten an Absatzgrenzen teilen (HTML-Tags bleiben pro Absatz heil)."""
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            parts.append(current)
        while len(block) > limit:
            parts.append(block[:limit])
            block = block[limit:]
        current = block
    if current:
        parts.append(current)
    return parts
