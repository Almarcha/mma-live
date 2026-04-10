"""
UFC Upcoming Events Scraper
============================
Extrae todos los eventos futuros de https://www.ufc.com/events
y descarta los que sean anteriores a la fecha de hoy.

Dependencias:
    pip install requests beautifulsoup4
"""

import re
import json
from datetime import date, datetime
import requests
from bs4 import BeautifulSoup

URL = "https://www.ufc.com/events"
TODAY = date.today()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Abreviaturas de mes que usa UFC en sus tarjetas
MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_ufc_date(raw: str) -> date | None:
    """
    Parsea strings del tipo:
      'Sat, Apr 11 / 9:00 PM EDT / Main Card'
    Devuelve un objeto date o None si falla.
    """
    m = re.search(r"\w+,\s+(\w+)\s+(\d{1,2})", raw)
    if not m:
        return None

    month_str = m.group(1).lower()[:3]
    day = int(m.group(2))
    month = MONTH_ABBR.get(month_str)
    if not month:
        return None

    # El año no aparece en la tarjeta — lo inferimos comparando con hoy
    year = TODAY.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        return None

    # Si la fecha resultante ya pasó, probamos el año siguiente
    if candidate < TODAY:
        try:
            candidate = date(year + 1, month, day)
        except ValueError:
            return None

    return candidate


def scrape_upcoming_events() -> list[dict]:
    print(f"[*] Descargando {URL} ...")
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    events = []

    # Cada evento aparece como <h3><a href="/event/...">Nombre</a></h3>
    # La fecha está en el siguiente <a> con el mismo href que tiene el texto de la hora
    for h3 in soup.find_all("h3"):
        link = h3.find("a", href=re.compile(r"/event/"))
        if not link:
            continue

        name = link.get_text(strip=True)
        event_url = "https://www.ufc.com" + link["href"]

        # Buscar la fecha en los elementos cercanos
        date_text = ""
        parent = h3.find_parent()
        if parent:
            for a in parent.find_all("a", href=link["href"]):
                t = a.get_text(strip=True)
                if re.search(r"\w+,\s+\w+\s+\d{1,2}\s*/", t):
                    date_text = t
                    break

        # Fallback: buscar en siblings del h3
        if not date_text:
            for sibling in h3.find_next_siblings():
                text = sibling.get_text(" ", strip=True)
                if re.search(r"\w+,\s+\w+\s+\d{1,2}\s*/", text):
                    date_text = text
                    break
                if sibling.name == "h3":
                    break

        event_date = parse_ufc_date(date_text) if date_text else None

        # Descartar eventos pasados
        if event_date and event_date < TODAY:
            continue

        # Ubicación: buscar <h5> (venue) y el texto de ciudad que le sigue
        location = "–"
        if parent:
            venue_el = parent.find("h5")
            if venue_el:
                city_parts = []
                for sib in venue_el.find_next_siblings():
                    t = sib.get_text(strip=True)
                    if t and not re.search(
                        r"How to Watch|Tickets|Watch On|Prelims|Main Card|EDT|EST|PDT|PST",
                        t
                    ):
                        city_parts.append(t)
                    if len(city_parts) >= 2:
                        break
                location = venue_el.get_text(strip=True)
                if city_parts:
                    location += " — " + ", ".join(city_parts)

        events.append({
            "name": name,
            "date": event_date.isoformat() if event_date else (date_text or "Fecha desconocida"),
            "location": location,
            "url": event_url,
        })

    # Eliminar duplicados por URL
    seen = set()
    unique = []
    for ev in events:
        if ev["url"] not in seen:
            seen.add(ev["url"])
            unique.append(ev)

    # Ordenar por fecha
    unique.sort(key=lambda e: e["date"])
    return unique


def main():
    print(f"{'=' * 55}")
    print(f"  UFC Events Scraper — Eventos a partir de {TODAY}")
    print(f"{'=' * 55}\n")

    upcoming = scrape_upcoming_events()

    if not upcoming:
        print("No se encontraron eventos futuros.")
        return

    print(f"✅ {len(upcoming)} eventos futuros encontrados:\n")
    for i, ev in enumerate(upcoming, 1):
        print(f"  {i:02d}. {ev['name']}")
        print(f"      📅 {ev['date']}")
        print(f"      📍 {ev['location']}")
        print(f"      🔗 {ev['url']}")
        print()

    output_file = "public/events.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(upcoming, f, ensure_ascii=False, indent=2)

    print(f"💾 Resultados guardados en '{output_file}'")


if __name__ == "__main__":
    main()
