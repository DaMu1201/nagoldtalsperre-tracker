#!/usr/bin/env python3
"""
Nagoldtalsperre – Verfügbarkeits-Tracker (Haupt- & Vorsperre)
==============================================================
Prüft regelmäßig, ob auf der ForstBW-Webshop-Seite ein Platz
für Haupt- oder Vorsperre frei geworden ist, und schickt eine
Telegram-Nachricht, sobald das der Fall ist.
Alle 6 Stunden kommt eine kurze Status-Summary.
"""

import os
import re
import sys
import requests
from datetime import datetime, timezone

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


def parse_sperre(html: str, name: str) -> tuple[int, int] | None:
    """
    Liest maxAnzahlData und anzahlVerkauftData für eine Sperre aus.

    Args:
        html: Der gesamte HTML-Code der Seite
        name: "Hauptsperre" oder "Vorsperre"

    HTML-Struktur:
        <a ... onclick="setSessionStoragePrice('...', 'Fischereischein - Hauptsperre')">
            ...
            <div class="maxAnzahlData" style="display: none;">100</div>
            <div class="anzahlVerkauftData" style="display: none;">100</div>
            ...
        </a>

    Gibt zurück: (verkauft, maximum) oder None bei Fehler.
    """
    pattern = (
        r"Fischereischein\s*-\s*" + re.escape(name)
        + r".*?maxAnzahlData.*?>(\d+)<.*?anzahlVerkauftData.*?>(\d+)<"
    )
    match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    if match:
        maximum = int(match.group(1))
        sold = int(match.group(2))
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
    print("🎣 Prüfe Nagoldtalsperre (Haupt- & Vorsperre)...")
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

    # Beide Sperren auslesen
    hauptsperre = parse_sperre(html, "Hauptsperre")
    vorsperre = parse_sperre(html, "Vorsperre")

    if hauptsperre is None and vorsperre is None:
        msg = (
            "Konnte keine Platzzahlen auslesen.\n"
            "Möglicherweise hat sich die Seitenstruktur geändert.\n"
            f"Bitte manuell prüfen: {URL}"
        )
        print(f"⚠️ {msg}")
        send_telegram(f"⚠️ <b>Nagoldtalsperre Tracker</b>\n\n{msg}")
        sys.exit(1)

    # Ergebnisse ausgeben
    alerts = []

    if hauptsperre:
        h_sold, h_max = hauptsperre
        h_free = h_max - h_sold
        print(f"   Hauptsperre: Verkauft {h_sold} / Max {h_max} → Frei: {h_free}")
        if h_sold < h_max:
            alerts.append(
                f"🎣 <b>Hauptsperre:</b> {h_sold}/{h_max} belegt → "
                f"<b>{h_free} Platz/Plätze frei!</b>"
            )
    else:
        print("   ⚠️ Hauptsperre: Konnte nicht ausgelesen werden")

    if vorsperre:
        v_sold, v_max = vorsperre
        v_free = v_max - v_sold
        print(f"   Vorsperre:   Verkauft {v_sold} / Max {v_max} → Frei: {v_free}")
        if v_sold < v_max:
            alerts.append(
                f"🎣 <b>Vorsperre:</b> {v_sold}/{v_max} belegt → "
                f"<b>{v_free} Platz/Plätze frei!</b>"
            )
    else:
        print("   ⚠️ Vorsperre: Konnte nicht ausgelesen werden")

    # Alarm senden wenn irgendwo ein Platz frei ist
    if alerts:
        msg = (
            "🎉 <b>PLATZ FREI an der Nagoldtalsperre!</b>\n\n"
            + "\n".join(alerts)
            + f"\n\n👉 Jetzt schnell Antrag stellen:\n{URL}"
        )
        send_telegram(msg)
        print("🎉 Alarm gesendet!")
    else:
        # Alle 6 Stunden Status-Summary (UTC 0, 6, 12, 18 Uhr)
        now = datetime.now(timezone.utc)
        if now.hour % 6 == 0 and now.minute < 15:
            h_info = f"{h_sold}/{h_max}" if hauptsperre else "?"
            v_info = f"{v_sold}/{v_max}" if vorsperre else "?"
            msg = (
                f"✅ <b>Tracker läuft</b>\n\n"
                f"Hauptsperre: <b>{h_info}</b> belegt\n"
                f"Vorsperre: <b>{v_info}</b> belegt\n\n"
                f"Du wirst sofort benachrichtigt, sobald ein Platz frei wird."
            )
            send_telegram(msg)
        print("😴 Alles belegt. Nächster Check beim nächsten Run.")

    sys.exit(0)


if __name__ == "__main__":
    main()
