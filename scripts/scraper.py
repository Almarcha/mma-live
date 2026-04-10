#!/usr/bin/env python3
"""
MMA Live - Automatización de eventos UFC
=========================================
Scrapea UFC.com y genera events.json actualizado.
Ejecutar manualmente o programar con GitHub Actions / cron.

Instalación:
    pip install requests beautifulsoup4 lxml

Uso:
    python scraper.py

Salida:
    public/events.json  (leído automáticamente por la app)
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
UFC_EVENTS_URL = "https://www.ufc.com/events"
OUTPUT_PATH    = Path(__file__).parent.parent / "public" / "events.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 12; Pixel 6) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/112.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}
REQUEST_TIMEOUT = 15
SLEEP_BETWEEN_REQUESTS = 2  # segundos, para no sobrecargar


# ─────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────
def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def clean(text: str) -> str:
    return " ".join(text.split()) if text else ""


# ─────────────────────────────────────────
# SCRAPING UFC.COM
# ─────────────────────────────────────────
def fetch_ufc_events():
    url = "https://d29dxerjsp82wz.cloudfront.net/api/v3/events"

    resp = requests.get(url, headers=HEADERS)
    data = resp.json()

    events = []

    for e in data.get("events", []):
        event_type = classify_event(e.get("name", ""))

        events.append({
            "name": e.get("name"),
            "date": e.get("date"),
            "date_iso": e.get("date"),
            "location": e.get("location", "Por confirmar"),
            "type": event_type["type"],
            "pill": event_type["pill"],
            "pillText": event_type["pillText"],
            "main": e.get("headline", ""),
            "url": f"https://www.ufc.com/event/{e.get('slug')}",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })

    return events


def parse_event_card(card) -> dict | None:
    # Nombre
    name_el = card.find(['h2', 'h3'])
    name = clean(name_el.get_text()) if name_el else ""
    if not name:
        return None

    # Fecha
    time_el = card.find('time')
    date_str = clean(time_el.get_text()) if time_el else ""
    date_iso = time_el.get("datetime", "") if time_el else ""

    # Localización
    location = "Por confirmar"
    loc_el = card.find(string=re.compile(r','))
    if loc_el:
        location = clean(loc_el)

    # Fighters
    fighters = card.find_all(string=re.compile(r'vs|VS'))
    main = clean(fighters[0]) if fighters else ""

    # URL
    link = card.find('a', href=True)
    url = "https://d29dxerjsp82wz.cloudfront.net/api/v3/events"

    event_type = classify_event(name)

    return {
        "name": name,
        "date": date_str,
        "date_iso": date_iso,
        "location": location,
        "type": event_type["type"],
        "pill": event_type["pill"],
        "pillText": event_type["pillText"],
        "main": main,
        "url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def classify_event(name: str) -> dict:
    """Clasifica el evento por tipo basado en el nombre."""
    name_lower = name.lower()
    if re.search(r'\bufc\s+\d{3}\b', name_lower):
        return {"type": "numbered", "pill": "pill-numbered", "pillText": "Numerado"}
    elif "fight night" in name_lower:
        return {"type": "fight-night", "pill": "pill-fn", "pillText": "Fight Night"}
    elif any(w in name_lower for w in ["championship", "title", "freedom", "special"]):
        return {"type": "special", "pill": "pill-special", "pillText": "Especial"}
    else:
        return {"type": "fight-night", "pill": "pill-fn", "pillText": "Fight Night"}


# ─────────────────────────────────────────
# FALLBACK: datos hardcodeados actualizados
# ─────────────────────────────────────────
FALLBACK_EVENTS = [
    {
        "name": "UFC Fight Night 271",
        "subtitle": "Adesanya vs Pyfer",
        "date": "28 Mar 2026",
        "date_iso": "2026-03-29T01:00:00Z",
        "location": "Seattle, WA",
        "type": "fight-night",
        "pill": "pill-fn",
        "pillText": "Fight Night",
        "main": "🥊 Israel Adesanya (24-5) vs Joe Pyfer (15-3)",
        "url": "https://www.ufc.com/event/ufc-fight-night-march-28-2026",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "name": "UFC Fight Night",
        "subtitle": "Moicano vs Duncan",
        "date": "4 Abr 2026",
        "date_iso": "2026-04-05T01:00:00Z",
        "location": "Las Vegas, NV · APEX",
        "type": "fight-night",
        "pill": "pill-fn",
        "pillText": "Fight Night",
        "main": "🥊 Renato Moicano vs Roosevelt Duncan",
        "url": "https://www.ufc.com/events",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "name": "UFC 327",
        "subtitle": "Procházka vs Ulberg",
        "date": "Abr 2026",
        "date_iso": "",
        "location": "Por confirmar",
        "type": "numbered",
        "pill": "pill-numbered",
        "pillText": "Numerado",
        "main": "🏆 Jiří Procházka vs Carlos Ulberg · Semipesado",
        "url": "https://www.ufc.com/events",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "name": "UFC 328",
        "subtitle": "Chimaev vs Strickland",
        "date": "May 2026",
        "date_iso": "",
        "location": "Por confirmar",
        "type": "numbered",
        "pill": "pill-numbered",
        "pillText": "Numerado",
        "main": "🏆 Khamzat Chimaev vs Sean Strickland · MW",
        "url": "https://www.ufc.com/events",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "name": "UFC Freedom 250",
        "subtitle": "Topuria vs Gaethje",
        "date": "14 Jun 2026",
        "date_iso": "2026-06-14T23:00:00Z",
        "location": "The White House, Washington D.C.",
        "type": "special",
        "pill": "pill-special",
        "pillText": "Especial",
        "main": "🏆 Ilia Topuria vs Justin Gaethje · Título Ligero",
        "url": "https://www.ufc.com/events",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    },
]


# ─────────────────────────────────────────
# GUARDAR JSON
# ─────────────────────────────────────────
def save_events(events: list[dict]):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source":     "ufc.com scraper",
        "count":      len(events),
        "events":     events,
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log(f"✅ Guardado en {OUTPUT_PATH} ({len(events)} eventos)")


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    log("=" * 50)
    log("MMA Live · Scraper de eventos UFC")
    log("=" * 50)

    events = fetch_ufc_events()

    if not events:
        log("⚠️  Scraping falló o devolvió 0 eventos. Usando fallback.")
        events = FALLBACK_EVENTS
    else:
        log(f"✔  {len(events)} eventos obtenidos del scraping")

    save_events(events)
    log("Listo.")


if __name__ == "__main__":
    main()
