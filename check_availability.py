#!/usr/bin/env python3
"""
Nagoldtalsperre Hauptsperre – Verfügbarkeits-Tracker
=====================================================
Prüft regelmäßig, ob auf der ForstBW-Webshop-Seite ein Platz
für die Hauptsperre frei geworden ist, und schickt eine
Telegram-Nachricht bei jedem Check.
"""

import os
import re
import sys
import requests

# ─── Konfiguration (über GitHub Secrets / Environment Variables) ───
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# URL der Seite
URL = "https://webshop.forstbw.de/Angeln/Angeln-an-der-Nagoldtalsperre/"


def fetch_page() -> str:
    """Holt den HTML-Inhalt der ForstBW-Seite."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(URL, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_hauptsperre_slots(html: str) -> tuple[int, int] | None:
    """
    Liest maxAnzahlData (max. Plätze) und anzahlVerkauftData (verkauft)
    für die Hauptsperre aus dem HTML.

    HTML-Struktur auf der Seite:
        <a ... onclick="setSessionStoragePrice('...', 'Fischereischein - Hauptsperre')">
            ...
            <div class="maxAnzahlData" style="display: none;">100</div>
            <div class="anzahlVerkauftData" style="display: none;">100</div>
            ...
        </a>

    Gibt zurück: (verkauft, maximum) oder None bei Fehler.
    """
    # Strategie 1: Suche gezielt den Hauptsperre-Block
    block_match = re.search(
        r"Fischereischein\s*-\s*Hauptsperre.*?maxAnzahlData.*?>(\d+)<.*?anzahlVerkauftData.*?>(\d+)<",
        html, re.DOTALL | re.IGNORECASE
    )
    if block_match:
        maximum = int(block_match.group(1))
        sold = int(block_match.group(2))
        return sold, maximum

    # Strategie 2: Fallback – erste Instanz der CSS-Klassen
    max_match = re.search(r'class="maxAnzahlData"[^>]*>(\d+)<', html)
    sold_match = re.search(r'class="anzahlVerkauftData"[^>]*>(\d+)<', html)
    if max_match and sold_match:
        maximum = int(max_match.group(1))
        sold = int(sold_match.group(1))
        return sold, maximum

    return None


def send_telegram(message: str) -> bool:
    """Sendet eine Nachricht über den Telegram-Bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Telegram nicht konfiguriert. Nachricht nur auf Konsole:")
        print(message)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            print("✅ Telegram-Nachricht gesendet!")
            return True
        else:
            print(f"❌ Telegram-Fehler: {resp.status_code} – {resp.text}")
            return False
    except requests.RequestException as e:
        print(f"❌ Telegram-Verbindungsfehler: {e}")
        return False


def main():
    print("🎣 Prüfe Nagoldtalsperre Hauptsperre...")
    print(f"   URL: {URL}")

    # Seite abrufen
    try:
        html = fetch_page()
    except requests.RequestException as e:
        print(f"❌ Fehler beim Abruf der Seite: {e}")
        send_telegram(
            "⚠️ <b>Nagoldtalsperre Tracker</b>\n\n"
            f"Fehler beim Abruf der Seite:\n{e}\n\n"
            f"Bitte manuell prüfen: {URL}"
        )
        sys.exit(1)

    # Plätze auslesen
    slots = parse_hauptsperre_slots(html)

    if slots is None:
        msg = (
            "Konnte die Platzzahl nicht auslesen.\n"
            "Möglicherweise hat sich die Seitenstruktur geändert.\n"
            f"Bitte manuell prüfen: {URL}"
        )
        print(f"⚠️ {msg}")
        send_telegram(f"⚠️ <b>Nagoldtalsperre Tracker</b>\n\n{msg}")
        sys.exit(1)

    sold, maximum = slots
    free = maximum - sold
    print(f"   Verkauft: {sold} / Max: {maximum} → Frei: {free}")

    if sold < maximum:
        # PLATZ FREI!
        msg = (
            f"🎣🎉 <b>PLATZ FREI an der Nagoldtalsperre Hauptsperre!</b>\n\n"
            f"Verkauft: <b>{sold}/{maximum}</b> → "
            f"<b>{free} Platz/Plätze frei!</b>\n\n"
            f"👉 Jetzt schnell Antrag stellen:\n"
            f"{URL}"
        )
        send_telegram(msg)
        print(f"🎉 {free} Platz/Plätze frei!")
    else:
        # Alle 6 Stunden eine Status-Nachricht senden (UTC 0, 6, 12, 18 Uhr)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if now.hour % 6 == 0 and now.minute < 15:
            msg = (
                f"✅ <b>Tracker läuft</b>\n\n"
                f"Hauptsperre: <b>{sold}/{maximum}</b> belegt.\n"
                f"Du wirst sofort benachrichtigt, sobald ein Platz frei wird."
            )
            send_telegram(msg)
        print(f"😴 Noch voll belegt ({sold}/{maximum}).")

    sys.exit(0)


if __name__ == "__main__":
    main()
