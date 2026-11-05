"""Prüft die Telegram-Einstellungen (Token, Chat-ID, Befehle) und schickt eine Testnachricht.

Gibt keine geheimen Werte aus (Token und Chat-ID bleiben verborgen).
Aufruf: python -m tools.telegram_check   (braucht TELEGRAM_TOKEN und TELEGRAM_CHAT_ID)
"""
from __future__ import annotations

import os
import sys

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def call(token: str, method: str, **payload):
    try:
        r = requests.post(API.format(token=token, method=method), json=payload, timeout=30)
        return r.status_code, r.json()
    except (requests.RequestException, ValueError) as exc:
        return 0, {"ok": False, "description": type(exc).__name__}


def main() -> int:
    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    print(f"Secret TELEGRAM_TOKEN gesetzt: {'ja' if token else 'NEIN'}"
          + (f" (Format {'ok' if ':' in token and token.split(':')[0].isdigit() else 'UNGEWÖHNLICH'})" if token else ""))
    print(f"Secret TELEGRAM_CHAT_ID gesetzt: {'ja' if chat_id else 'NEIN'}"
          + (f" (nur Ziffern: {'ja' if chat_id.lstrip('-').isdigit() else 'NEIN'})" if chat_id else ""))
    if not token:
        return 1

    status, me = call(token, "getMe")
    if not me.get("ok"):
        print(f"❌ Token ungültig: HTTP {status} {me.get('description')}")
        return 1
    print(f"✅ Token gehört zum Bot: @{me['result'].get('username')}")

    _, hook = call(token, "getWebhookInfo")
    info = hook.get("result", {})
    print(f"Webhook eingerichtet: {'JA (blockiert Befehle!)' if info.get('url') else 'nein (richtig)'}")
    print(f"Wartende Nachrichten an den Bot: {info.get('pending_update_count', '?')}")

    _, upd = call(token, "getUpdates", timeout=0)
    updates = upd.get("result", []) if upd.get("ok") else []
    print(f"Abrufbare Nachrichten an den Bot (letzte 24 h): {len(updates)}"
          + ("" if upd.get("ok") else f" – Fehler: {upd.get('description')}"))
    for u in updates[-10:]:
        msg = u.get("message") or u.get("edited_message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        same = str(chat.get("id")) == chat_id
        text = (msg.get("text") or "")
        shown = text.split()[0] if text.startswith("/") else ("(Text)" if text else "(kein Text)")
        print(f"  - {shown} | Chat-Typ: {chat.get('type')} | stimmt mit TELEGRAM_CHAT_ID überein: "
              f"{'ja' if same else 'NEIN'}")

    if chat_id:
        status, sent = call(token, "sendMessage", chat_id=chat_id,
                            text="🔧 Testnachricht vom Job-Alarm: Token und Chat-ID funktionieren.")
        if sent.get("ok"):
            chat = sent["result"].get("chat", {})
            print(f"✅ Testnachricht gesendet (Chat-Typ: {chat.get('type')})")
        else:
            print(f"❌ Testnachricht fehlgeschlagen: HTTP {status} {sent.get('description')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
