#!/usr/bin/env python3
"""
Nagoldtalsperre Hauptsperre – Verfügbarkeits-Tracker
=====================================================
Prüft alle 15 Minuten, ob auf der ForstBW-Webshop-Seite ein Platz
für die Hauptsperre frei geworden ist, und schickt dir eine
Telegram-Nachricht, sobald das der Fall ist.
"""

import os
import re
import sys
import requests

# ─── Konfiguration (über GitHub Secrets / Environment Variables) ───
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# URL der Antragstellungs-Seite
URL = "https://webshop.forstbw.de/Angeln/Angeln-an-der-Nagoldtalsperre/"

# Maximale Plätze Hauptsperre
MAX_SLOTS = 100


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
    Versucht aus dem HTML die aktuelle/maximale Platzzahl
    für die Hauptsperre zu extrahieren.

    Die Seite zeigt die Daten in einem Kartenformat:
        Hauptsperre
        [01.03.
        <aktuell>
        <max>
        Jahreskarte
        140,00€

    Wir suchen nach dem Muster rund um 'Hauptsperre'.
    """
    # Strategie 1: Suche nach dem Pattern im HTML-Text
    # Die Zahlen stehen typischerweise als separate Elemente
    # in der Nähe von "Hauptsperre"
    
    # Normalisiere HTML – entferne Tags für leichteres Parsen
    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"\s+", " ", text)
    
    # Suche nach "Hauptsperre" gefolgt von zwei Zahlen
    pattern = r"Hauptsperre.*?(\d{1,3})\s+(\d{1,3})\s+Jahreskarte"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if match:
        current = int(match.group(1))
        maximum = int(match.group(2))
        return current, maximum

    # Strategie 2: Suche einfach nach zwei aufeinanderfolgenden
    # Zahlen die typisch für "belegt/max" sind
    pattern2 = r"Hauptsperre.*?(\d{1,3})[^\d]+(\d{1,3})"
    match2 = re.search(pattern2, text, re.DOTALL | re.IGNORECASE)
    
    if match2:
        current = int(match2.group(1))
        maximum = int(match2.group(2))
        return current, maximum

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
    resp = requests.post(url, json=payload, timeout=15)
    if resp.status_code == 200:
        print("✅ Telegram-Nachricht gesendet!")
        return True
    else:
        print(f"❌ Telegram-Fehler: {resp.status_code} – {resp.text}")
        return False


def main():
    print(f"🎣 Prüfe Nagoldtalsperre Hauptsperre...")
    print(f"   URL: {URL}")

    try:
        html = fetch_page()
    except requests.RequestException as e:
        print(f"❌ Fehler beim Abruf der Seite: {e}")
        sys.exit(1)

    slots = parse_hauptsperre_slots(html)

    if slots is None:
        msg = (
            "⚠️ Konnte die Platzzahl nicht auslesen.\n"
            "Möglicherweise hat sich die Seitenstruktur geändert.\n"
            "Bitte manuell prüfen: " + URL
        )
        print(msg)
        send_telegram(f"⚠️ <b>Nagoldtalsperre Tracker</b>\n\n{msg}")
        sys.exit(1)

    current, maximum = slots
    print(f"   Belegte Plätze: {current}/{maximum}")

    if current < maximum:
        free = maximum - current
        msg = (
            f"🎣🎉 <b>PLATZ FREI an der Nagoldtalsperre Hauptsperre!</b>\n\n"
            f"Aktuell: <b>{current}/{maximum}</b> belegt → "
            f"<b>{free} Platz/Plätze frei!</b>\n\n"
            f"👉 Jetzt schnell Antrag stellen:\n"
            f"{URL}"
        )
        send_telegram(msg)
        print(f"🎉 {free} Platz/Plätze frei!")
    else:
        print(f"😴 Noch voll belegt ({current}/{maximum}). Nächster Check in 15 Min.")
        send_telegram(
            f"✅ <b>Tracker funktioniert!</b>\n\nHauptsperre: <b>{current}/{maximum}</b> belegt.\nDu wirst benachrichtigt, sobald ein Platz frei wird."
        )

    # Immer mit Exit-Code 0, damit GitHub Actions nicht fehlschlägt
    sys.exit(0)


if __name__ == "__main__":
    main()
