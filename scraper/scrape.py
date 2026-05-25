#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bierradar Scraper  –  Datenquelle: marktguru.de
================================================
Statt die schwer zugaenglichen Einzel-Webseiten von REWE, EDEKA & Co.
auszulesen, nutzt dieser Scraper das Prospekt-Portal marktguru.de.
marktguru sammelt die Angebote praktisch aller deutschen Supermaerkte
und stellt eine Suche pro Postleitzahl bereit.

Vorgehen:
  1. API-Schluessel automatisch von der marktguru-Webseite holen.
  2. Fuer jedes gesuchte Bier und jede konfigurierte Postleitzahl
     die marktguru-Angebotssuche abfragen.
  3. Treffer einsammeln, Duplikate entfernen, nach data/angebote.json
     schreiben.

Wird automatisch per GitHub Actions ausgefuehrt
(siehe .github/workflows/scrape.yml).

WARTUNG:
  - Sollte marktguru die Schluessel-Einbindung aendern, muss
    `hole_api_schluessel()` angepasst werden. Die Stelle ist markiert.
  - Schlaegt eine einzelne Abfrage fehl, laeuft der Rest trotzdem weiter.
"""

import json
import re
import sys
import os
import time
from datetime import datetime, timezone, timedelta

import requests

# --- Pfade -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
BIERE_FILE = os.path.join(DATA_DIR, "biere.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "angebote.json")

TZ = timezone(timedelta(hours=2))   # deutsche Sommerzeit (vereinfacht)
TIMEOUT = 25
PAUSE = 0.6                          # kurze Pause zwischen Abfragen (hoeflich)

MARKTGURU_BASIS = "https://www.marktguru.de"
MARKTGURU_API = "https://api.marktguru.de/api/v1/offers/search"

# Browser-aehnliche Header
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-DE,de;q=0.9",
}


# --- Hilfsfunktionen ---------------------------------------------------
def lade_json(pfad):
    with open(pfad, "r", encoding="utf-8") as f:
        return json.load(f)


# --- API-Schluessel beschaffen ----------------------------------------
def hole_api_schluessel():
    """
    marktguru bindet zwei Schluessel (x-clientkey, x-apikey) in seine
    Webseite ein. Wir laden eine Seite und ziehen die Schluessel per
    Mustersuche heraus.

    ANPASSEN, falls marktguru die Einbindung aendert.
    Gibt (clientkey, apikey) zurueck oder wirft eine Exception.
    """
    # Die Schluessel stecken in den ausgelieferten JavaScript-Dateien.
    # Wir holen zuerst die Startseite und sammeln daraus die JS-Dateien.
    start = requests.get(MARKTGURU_BASIS, headers=HEADERS, timeout=TIMEOUT)
    start.raise_for_status()

    js_dateien = re.findall(r'src="([^"]+\.js)"', start.text)
    # auch absolute Pfade beruecksichtigen
    kandidaten = []
    for j in js_dateien:
        if j.startswith("http"):
            kandidaten.append(j)
        elif j.startswith("/"):
            kandidaten.append(MARKTGURU_BASIS + j)

    # Schluesselmuster: Base64-aehnliche Zeichenketten, die auf "=" enden
    muster_client = re.compile(r'["\']?x-?clientkey["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.I)
    muster_api = re.compile(r'["\']?x-?apikey["\']?\s*[:=]\s*["\']([^"\']+)["\']', re.I)

    # zuerst die Startseite selbst pruefen
    quellen = [start.text]

    # dann die JS-Dateien (die ersten paar reichen meist)
    for url in kandidaten[:12]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.ok:
                quellen.append(r.text)
        except Exception:
            pass

    clientkey = apikey = None
    for text in quellen:
        if not clientkey:
            m = muster_client.search(text)
            if m:
                clientkey = m.group(1)
        if not apikey:
            m = muster_api.search(text)
            if m:
                apikey = m.group(1)
        if clientkey and apikey:
            break

    if not (clientkey and apikey):
        raise RuntimeError(
            "marktguru-API-Schluessel nicht gefunden. "
            "Vermutlich hat marktguru die Webseite umgebaut - "
            "hole_api_schluessel() in scrape.py muss angepasst werden."
        )
    return clientkey, apikey


# --- marktguru abfragen -----------------------------------------------
def suche_angebote(suchbegriff, plz, clientkey, apikey):
    """Fragt die marktguru-Angebotssuche fuer einen Begriff + PLZ ab."""
    params = {
        "as": "web",
        "limit": 80,
        "offset": 0,
        "q": suchbegriff,
        "zipCode": plz,
    }
    kopf = dict(HEADERS)
    kopf["x-clientkey"] = clientkey
    kopf["x-apikey"] = apikey

    r = requests.get(MARKTGURU_API, params=params, headers=kopf, timeout=TIMEOUT)
    r.raise_for_status()
    daten = r.json()
    return daten.get("results", [])


def passt_zum_bier(angebot, bier):
    """Prueft, ob ein marktguru-Angebot wirklich zum gesuchten Bier gehoert."""
    felder = []
    for schluessel in ("title", "description", "brand"):
        wert = angebot.get(schluessel)
        if isinstance(wert, str):
            felder.append(wert)
        elif isinstance(wert, dict):
            felder.append(str(wert.get("name", "")))
    text = " ".join(felder).lower()
    return any(alias in text for alias in bier["aliase"])


def baue_angebot(angebot, bier, plz_ort):
    """Formt einen marktguru-Treffer in unser einheitliches Format um."""
    # Haendlername steht je nach Antwort unter advertisers[0].name
    haendler = "Markt unbekannt"
    werber = angebot.get("advertisers")
    if isinstance(werber, list) and werber:
        haendler = werber[0].get("name", haendler)
    elif isinstance(angebot.get("advertiser"), dict):
        haendler = angebot["advertiser"].get("name", haendler)

    preis = angebot.get("price")
    if isinstance(preis, (int, float)):
        preis = ("%.2f" % preis).replace(".", ",")
    elif not isinstance(preis, str):
        preis = None

    titel = angebot.get("description") or angebot.get("title") or bier["name"]

    # Gueltigkeit
    gueltig_bis = angebot.get("validityEndDate") or angebot.get("validTo")

    return {
        "bier_id": bier["id"],
        "bier_name": bier["name"],
        "markt_name": haendler,
        "markt_ort": plz_ort,
        "titel": str(titel).strip(),
        "preis": preis,
        "gueltig_bis": gueltig_bis,
        "quelle": "marktguru",
    }


# --- Hauptlauf ---------------------------------------------------------
def main():
    print("=== Bierradar Scraper (marktguru) ===")
    config = lade_json(CONFIG_FILE)
    biere = lade_json(BIERE_FILE)["biere"]
    plz_liste = config["postleitzahlen"]

    fehler_global = []

    # 1) API-Schluessel holen
    try:
        clientkey, apikey = hole_api_schluessel()
        print("API-Schluessel erfolgreich geholt.")
    except Exception as e:
        print(f"FEHLER beim Holen der Schluessel: {e}", file=sys.stderr)
        # Ergebnis mit Fehlerhinweis schreiben, App zeigt dann eine Meldung
        schreibe_ergebnis([], [str(e)])
        sys.exit(1)

    # 2) Fuer jedes Bier und jede PLZ abfragen
    alle_angebote = []
    for bier in biere:
        print(f"\n-> {bier['name']}")
        for begriff in bier["suchbegriffe"]:
            for plz_eintrag in plz_liste:
                plz = plz_eintrag["plz"]
                ort = plz_eintrag["ort"]
                try:
                    treffer = suche_angebote(begriff, plz, clientkey, apikey)
                    passend = [t for t in treffer if passt_zum_bier(t, bier)]
                    for t in passend:
                        alle_angebote.append(baue_angebot(t, bier, ort))
                    print(f"   '{begriff}' @ {plz} ({ort}): "
                          f"{len(passend)} passende von {len(treffer)}")
                except Exception as e:
                    msg = f"{begriff}@{plz}: {e}"
                    print(f"   FEHLER {msg}")
                    fehler_global.append(msg)
                time.sleep(PAUSE)

    # 3) Duplikate entfernen (gleiches Bier + Markt + Titel)
    eindeutig = {}
    for a in alle_angebote:
        key = (a["bier_id"], a["markt_name"], a["titel"])
        if key not in eindeutig:
            eindeutig[key] = a
    ergebnis_liste = list(eindeutig.values())

    schreibe_ergebnis(ergebnis_liste, fehler_global)
    print(f"\n=== Fertig: {len(ergebnis_liste)} Angebote geschrieben ===")


def schreibe_ergebnis(angebote, fehler):
    ergebnis = {
        "_hinweis": "Automatisch erzeugt vom Bierradar-Scraper. Quelle: marktguru.de. Nicht von Hand bearbeiten.",
        "stand": datetime.now(TZ).isoformat(),
        "quelle": "marktguru.de",
        "fehler": fehler,
        "angebote": angebote,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(ergebnis, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"Schwerer Fehler: {e}", file=sys.stderr)
        sys.exit(1)
