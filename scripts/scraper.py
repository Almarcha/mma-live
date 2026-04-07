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
def fetch_ufc_events() -> list[dict]:
    """Scrapea la página de eventos de UFC.com y devuelve lista de eventos."""
    log(f"Fetching {UFC_EVENTS_URL} ...")
    try:
        resp = requests.get(UFC_EVENTS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log(f"ERROR al descargar UFC.com: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    events = []

    # UFC.com usa divs con clase 'c-card-event--result'
    cards = soup.select("li.c-card-event--result, div[class*='event-card']")
    log(f"Encontrados {len(cards)} eventos en la página")

    for card in cards:
        try:
            event = parse_event_card(card)
            if event:
                events.append(event)
        except Exception as e:
            log(f"  SKIP: error parseando card: {e}")
            continue

    return events


def parse_event_card(card) -> dict | None:
    """Extrae datos de un evento individual."""
    # Nombre del evento
    name_el = card.select_one(
        ".c-card-event--result__headline, "
        "h3.c-card-event--result__headline, "
        "[class*='event-card__title'], "
        "h2, h3"
    )
    name = clean(name_el.get_text()) if name_el else ""
    if not name:
        return None

    # Fecha
    date_el = card.select_one(
        ".c-card-event--result__date, "
        "[class*='event-date'], "
        "time"
    )
    date_str = ""
    date_iso = ""
    if date_el:
        date_str = clean(date_el.get_text())
        # Intentar leer atributo datetime de <time>
        date_iso = date_el.get("datetime", "")

    # Localización
    loc_el = card.select_one(
        ".c-card-event--result__location, "
        "[class*='event-location']"
    )
    location = clean(loc_el.get_text()) if loc_el else "Por confirmar"

    # Main event fighters
    fighters = card.select(
        ".c-card-event--result__athlete-name, "
        "[class*='athlete-name'], "
        "[class*='fighter-name']"
    )
    fighter_names = [clean(f.get_text()) for f in fighters if clean(f.get_text())]

    # Tipo de evento
    event_type = classify_event(name)

    # URL del evento
    link_el = card.select_one("a[href]")
    url = ""
    if link_el:
        href = link_el.get("href", "")
        url = f"https://www.ufc.com{href}" if href.startswith("/") else href

    return {
        "name":        name,
        "date":        date_str,
        "date_iso":    date_iso,
        "location":    location,
        "fighters":    fighter_names,
        "type":        event_type["type"],
        "pill":        event_type["pill"],
        "pillText":    event_type["pillText"],
        "url":         url,
        "scraped_at":  datetime.now(timezone.utc).isoformat(),
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
