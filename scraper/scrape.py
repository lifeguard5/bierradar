#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bierradar Scraper
=================
Liest die Angebote der in data/markets.json konfigurierten Maerkte aus,
filtert nach den in data/biere.json definierten Biersorten und schreibt
das Ergebnis nach data/angebote.json.

Wird automatisch per GitHub Actions ausgefuehrt (siehe .github/workflows/scrape.yml).

WICHTIG / WARTUNG:
- Supermarkt-Webseiten aendern regelmaessig ihre Struktur. Wenn ein Markt
  ploetzlich keine Treffer mehr liefert, muss die jeweilige parse_*-Funktion
  angepasst werden. Die Stellen sind unten klar markiert.
- Schlaegt ein Markt fehl, bricht das Skript NICHT ab - die uebrigen Maerkte
  werden trotzdem verarbeitet. Fehler werden protokolliert.
"""

import json
import re
import sys
import os
from datetime import datetime, timezone, timedelta

import requests

# --- Pfade -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MARKETS_FILE = os.path.join(DATA_DIR, "markets.json")
BIERE_FILE = os.path.join(DATA_DIR, "biere.json")
MANUELL_FILE = os.path.join(DATA_DIR, "manuell.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "angebote.json")

# Deutsche Zeitzone (MESZ/MEZ - vereinfacht auf +2h)
TZ = timezone(timedelta(hours=2))

# Browser-aehnliche Header, damit die Seiten nicht sofort blocken.
# Hinweis: Grosse Handelsketten sichern ihre Seiten teils gegen Bots ab -
# ein 403 ist daher nicht ungewoehnlich. Dann den Markt manuell pflegen.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    "Cache-Control": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

TIMEOUT = 25
RETRIES = 2


# --- Hilfsfunktionen ---------------------------------------------------
def lade_json(pfad):
    with open(pfad, "r", encoding="utf-8") as f:
        return json.load(f)


def hole_seite(url):
    """Laedt eine URL mit kurzen Wiederholungen. Wirft bei Endfehler eine Exception."""
    import time
    letzter_fehler = None
    for versuch in range(RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            letzter_fehler = e
            if versuch < RETRIES:
                time.sleep(2)
    raise letzter_fehler


def finde_biere(text, biere):
    """
    Durchsucht einen Text nach den konfigurierten Bieren.
    Gibt eine Liste der gefundenen Bier-Objekte zurueck.
    """
    text_klein = text.lower()
    treffer = []
    for bier in biere:
        for alias in bier["aliase"]:
            if alias.lower() in text_klein:
                treffer.append(bier)
                break
    return treffer


def extrahiere_preis(text):
    """Versucht, einen Preis (z.B. 12,99) aus einem Textstueck zu ziehen."""
    m = re.search(r"(\d{1,3}[.,]\d{2})\s*(?:€|EUR)?", text)
    if m:
        return m.group(1).replace(".", ",")
    return None


# --- Parser pro Markt-Typ ---------------------------------------------
# Jeder Parser bekommt (markt, biere) und gibt eine Liste von Angeboten zurueck.
# Ein Angebot ist ein dict:
#   { "markt_id", "markt_name", "markt_ort", "markt_url",
#     "bier_id", "bier_name", "titel", "preis", "quelle" }

def parse_rewe(markt, biere):
    """
    REWE liefert Angebote ueber eine interne JSON-Schnittstelle aus.
    Wir versuchen zunaechst die Angebotsseite direkt, dann ein Text-Match.
    ANPASSEN falls REWE die Struktur aendert.
    """
    angebote = []
    html = hole_seite(markt["url"])

    # REWE bettet Angebotsdaten teils als JSON im HTML ein.
    # Strategie: gesamten Seitentext nach Bier-Stichwoertern absuchen
    # und den umgebenden Textausschnitt als Titel verwenden.
    treffer_bloecke = _suche_textbloecke(html, biere)
    for bier, block in treffer_bloecke:
        angebote.append(_baue_angebot(markt, bier, block, "auto"))
    return angebote


def parse_edeka(markt, biere):
    """
    EDEKA-Marktseiten laden Prospekte oft per JavaScript nach.
    Wir versuchen den statischen HTML-Inhalt - klappt das nicht,
    bleibt der Markt leer und sollte manuell gepflegt werden.
    ANPASSEN falls EDEKA die Struktur aendert.
    """
    angebote = []
    html = hole_seite(markt["url"])
    treffer_bloecke = _suche_textbloecke(html, biere)
    for bier, block in treffer_bloecke:
        angebote.append(_baue_angebot(markt, bier, block, "auto"))
    return angebote


def parse_koenner(markt, biere):
    """
    Getraenke Koenner Marktseite mit ?tab=angebote.
    ANPASSEN falls die Struktur sich aendert.
    """
    angebote = []
    html = hole_seite(markt["url"])
    treffer_bloecke = _suche_textbloecke(html, biere)
    for bier, block in treffer_bloecke:
        angebote.append(_baue_angebot(markt, bier, block, "auto"))
    return angebote


def _suche_textbloecke(html, biere):
    """
    Generische Erkennung: entfernt HTML-Tags, sucht Bier-Stichwoerter und
    schneidet den umliegenden Text als 'Angebotstitel' aus.
    Robuster Allrounder, der bei den meisten Marktseiten funktioniert.
    """
    # HTML-Tags grob entfernen, Whitespace normalisieren
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text_klein = text.lower()

    ergebnisse = []
    gesehen = set()
    for bier in biere:
        for alias in bier["aliase"]:
            idx = text_klein.find(alias.lower())
            if idx == -1:
                continue
            # Textausschnitt rund um den Treffer (fuer Titel + Preis)
            start = max(0, idx - 40)
            ende = min(len(text), idx + 80)
            block = text[start:ende].strip()
            schluessel = (bier["id"],)
            if schluessel in gesehen:
                break
            gesehen.add(schluessel)
            ergebnisse.append((bier, block))
            break
    return ergebnisse


def _baue_angebot(markt, bier, textblock, quelle):
    return {
        "markt_id": markt["id"],
        "markt_name": markt["name"],
        "markt_ort": markt.get("ort", ""),
        "markt_url": markt["url"],
        "bier_id": bier["id"],
        "bier_name": bier["name"],
        "titel": textblock if textblock else bier["name"],
        "preis": extrahiere_preis(textblock),
        "quelle": quelle,
    }


PARSER = {
    "rewe": parse_rewe,
    "edeka": parse_edeka,
    "koenner": parse_koenner,
}


# --- Manuelle Angebote -------------------------------------------------
def lade_manuelle_angebote(maerkte, biere):
    """Liest data/manuell.json und baut daraus Angebots-Eintraege."""
    angebote = []
    try:
        manuell = lade_json(MANUELL_FILE)
    except Exception as e:
        print(f"  Hinweis: manuell.json nicht lesbar ({e})")
        return angebote

    markt_index = {m["id"]: m for m in maerkte}
    bier_index = {b["id"]: b for b in biere}

    heute = datetime.now(TZ).date()
    for eintrag in manuell.get("angebote", []):
        markt = markt_index.get(eintrag.get("markt_id"))
        bier = bier_index.get(eintrag.get("bier_id"))
        if not markt or not bier:
            continue
        # Abgelaufene manuelle Angebote ueberspringen
        gueltig_bis = eintrag.get("gueltig_bis")
        if gueltig_bis:
            try:
                if datetime.strptime(gueltig_bis, "%Y-%m-%d").date() < heute:
                    continue
            except ValueError:
                pass
        angebote.append({
            "markt_id": markt["id"],
            "markt_name": markt["name"],
            "markt_ort": markt.get("ort", ""),
            "markt_url": markt["url"],
            "bier_id": bier["id"],
            "bier_name": bier["name"],
            "titel": eintrag.get("titel", bier["name"]),
            "preis": eintrag.get("preis"),
            "quelle": "manuell",
        })
    return angebote


# --- Hauptlauf ---------------------------------------------------------
def main():
    print("=== Bierradar Scraper ===")
    markets_cfg = lade_json(MARKETS_FILE)
    biere_cfg = lade_json(BIERE_FILE)
    maerkte = markets_cfg["maerkte"]
    biere = biere_cfg["biere"]

    alle_angebote = []
    markt_status = []

    for markt in maerkte:
        if not markt.get("aktiv", True):
            continue
        name = markt["name"]
        typ = markt.get("typ", "manuell")
        print(f"\n-> {name} ({typ})")

        if typ == "manuell" or typ not in PARSER:
            markt_status.append({"markt_id": markt["id"], "name": name,
                                 "status": "manuell", "treffer": 0})
            continue

        try:
            gefunden = PARSER[typ](markt, biere)
            alle_angebote.extend(gefunden)
            print(f"   {len(gefunden)} Bier-Treffer")
            markt_status.append({"markt_id": markt["id"], "name": name,
                                 "status": "ok", "treffer": len(gefunden)})
        except Exception as e:
            print(f"   FEHLER: {e}")
            markt_status.append({"markt_id": markt["id"], "name": name,
                                 "status": "fehler", "treffer": 0,
                                 "fehlermeldung": str(e)[:200]})

    # Manuelle Angebote ergaenzen
    manuelle = lade_manuelle_angebote(maerkte, biere)
    if manuelle:
        print(f"\n-> {len(manuelle)} manuelle Angebote ergaenzt")
        alle_angebote.extend(manuelle)

    # Duplikate entfernen (gleicher Markt + gleiches Bier + gleiche Quelle)
    eindeutig = {}
    for a in alle_angebote:
        key = (a["markt_id"], a["bier_id"], a["quelle"])
        if key not in eindeutig:
            eindeutig[key] = a
    alle_angebote = list(eindeutig.values())

    ergebnis = {
        "_hinweis": "Automatisch erzeugt vom Bierradar-Scraper. Nicht von Hand bearbeiten.",
        "stand": datetime.now(TZ).isoformat(),
        "markt_status": markt_status,
        "angebote": alle_angebote,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(ergebnis, f, ensure_ascii=False, indent=2)

    print(f"\n=== Fertig: {len(alle_angebote)} Angebote geschrieben ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Schwerer Fehler: {e}", file=sys.stderr)
        sys.exit(1)
