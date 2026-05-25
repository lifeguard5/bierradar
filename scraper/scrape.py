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

# marktguru-API-Schluessel.
# marktguru ist eine Webseite ohne Login - diese Schluessel sind keine
# Geheimnisse, sondern oeffentliche Webseiten-Zugangsdaten, die die Seite
# selbst beim Laden an jeden Besucher mitgibt. Sie sind seit Jahren stabil.
# Sollte marktguru sie doch einmal aendern, versucht der Scraper als
# Rueckfallebene, neue Schluessel automatisch von der Webseite zu holen
# (siehe hole_api_schluessel).
MG_CLIENTKEY = "WU/RH+PMGDi+gkZer3WbMelt6zcYHSTytNB7VpTia90="
MG_APIKEY = "8Kk+pmbf7TgJ9nVj2cXeA7P5zBGv8iuutVVMRfOfvNE="

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
def teste_schluessel(clientkey, apikey):
    """Prueft mit einer kleinen Testabfrage, ob ein Schlusselpaar funktioniert."""
    try:
        kopf = dict(HEADERS)
        kopf["x-clientkey"] = clientkey
        kopf["x-apikey"] = apikey
        r = requests.get(
            MARKTGURU_API,
            params={"as": "web", "limit": 1, "offset": 0,
                    "q": "Bier", "zipCode": "34479"},
            headers=kopf, timeout=TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def lese_schluessel_von_webseite():
    """
    Rueckfallebene: Versucht, die API-Schluessel direkt aus der
    marktguru-Webseite und ihren JavaScript-Dateien zu lesen.
    Gibt (clientkey, apikey) zurueck oder (None, None).
    """
    try:
        start = requests.get(MARKTGURU_BASIS, headers=HEADERS, timeout=TIMEOUT)
        start.raise_for_status()
    except Exception:
        return None, None

    js_dateien = re.findall(r'src="([^"]+\.js)"', start.text)
    kandidaten = []
    for j in js_dateien:
        if j.startswith("http"):
            kandidaten.append(j)
        elif j.startswith("/"):
            kandidaten.append(MARKTGURU_BASIS + j)

    # Schluessel sind Base64-aehnliche Zeichenketten, die auf "=" enden.
    # Mehrere Muster, um verschiedene Schreibweisen abzudecken.
    muster_client = re.compile(
        r'(?:x-?clientkey|clientKey)["\']?\s*[:=]\s*["\']([A-Za-z0-9+/]{20,}=*)["\']', re.I)
    muster_api = re.compile(
        r'(?:x-?apikey|apiKey)["\']?\s*[:=]\s*["\']([A-Za-z0-9+/]{20,}=*)["\']', re.I)

    quellen = [start.text]
    for url in kandidaten[:15]:
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
    return clientkey, apikey


def hole_api_schluessel():
    """
    Liefert ein funktionierendes (clientkey, apikey)-Paar fuer die
    marktguru-API.

    Vorgehen:
      1. Die fest hinterlegten Schluessel testen (Normalfall, da stabil).
      2. Falls die nicht mehr funktionieren: aktuelle Schluessel von der
         marktguru-Webseite auslesen und ebenfalls testen.

    Wirft eine Exception, wenn beide Wege scheitern.
    """
    # 1) Feste Schluessel - der uebliche Fall
    if teste_schluessel(MG_CLIENTKEY, MG_APIKEY):
        print("API-Schluessel: feste Schluessel funktionieren.")
        return MG_CLIENTKEY, MG_APIKEY

    print("Feste Schluessel funktionieren nicht - versuche, "
          "aktuelle von der Webseite zu lesen ...")

    # 2) Rueckfallebene: von der Webseite lesen
    clientkey, apikey = lese_schluessel_von_webseite()
    if clientkey and apikey and teste_schluessel(clientkey, apikey):
        print("API-Schluessel: frisch von der Webseite geholt.")
        return clientkey, apikey

    raise RuntimeError(
        "Keine funktionierenden marktguru-API-Schluessel gefunden. "
        "marktguru hat moeglicherweise die API geaendert - "
        "die Schluessel MG_CLIENTKEY / MG_APIKEY in scrape.py "
        "muessen aktualisiert werden."
    )


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


def analysiere_gebinde(titel, preis_str):
    """
    Versucht aus dem Angebotstitel die Gebindegroesse zu erkennen
    (z.B. '20 x 0,5 l') und daraus die Gesamtmenge in Litern sowie
    den Preis pro Liter zu berechnen.

    Erkennt gaengige Schreibweisen:
      '20 x 0,5 l', '20x0,5l', '24 x 0,33', '6x0,33 l',
      '0,5 l', '5 l Fass'

    Gibt ein dict zurueck mit:
      anzahl, einzelgroesse_l, gesamt_l, gebinde_typ, preis_pro_liter
    Felder, die sich nicht ermitteln lassen, sind None.
    """
    ergebnis = {
        "anzahl": None,
        "einzelgroesse_l": None,
        "gesamt_l": None,
        "gebinde_typ": None,
        "preis_pro_liter": None,
    }
    if not titel:
        return ergebnis

    t = titel.lower().replace(",", ".")

    # Muster 1: "20 x 0.5 l" / "24x0.33" / "6 x 0.33l"
    m = re.search(r"(\d{1,2})\s*[x\u00d7]\s*(\d[.,]?\d*)\s*l?", t)
    if m:
        ergebnis["anzahl"] = int(m.group(1))
        ergebnis["einzelgroesse_l"] = float(m.group(2))
    else:
        # Muster 2: nur Einzelgroesse "0.5 l" / "5 l"
        m2 = re.search(r"(\d[.,]?\d*)\s*l\b", t)
        if m2:
            ergebnis["anzahl"] = 1
            ergebnis["einzelgroesse_l"] = float(m2.group(1))

    # Gesamtmenge
    if ergebnis["anzahl"] and ergebnis["einzelgroesse_l"]:
        ergebnis["gesamt_l"] = round(
            ergebnis["anzahl"] * ergebnis["einzelgroesse_l"], 3)

    # Gebinde-Typ aus Stichwoertern bzw. Anzahl ableiten
    if "fass" in t or "partyfass" in t:
        ergebnis["gebinde_typ"] = "Fass"
    elif "dose" in t or "dosen" in t:
        ergebnis["gebinde_typ"] = "Dose"
    elif "sixpack" in t or "six-pack" in t:
        ergebnis["gebinde_typ"] = "Sixpack"
    elif ergebnis["anzahl"]:
        if ergebnis["anzahl"] >= 12:
            ergebnis["gebinde_typ"] = "Kasten"
        elif ergebnis["anzahl"] == 6:
            ergebnis["gebinde_typ"] = "Sixpack"
        elif ergebnis["anzahl"] == 1:
            ergebnis["gebinde_typ"] = "Einzelflasche"
        else:
            ergebnis["gebinde_typ"] = "Mehrpack"
    elif "kasten" in t or "kiste" in t:
        ergebnis["gebinde_typ"] = "Kasten"

    # Preis pro Liter
    if ergebnis["gesamt_l"] and preis_str:
        try:
            preis = float(str(preis_str).replace(",", "."))
            if ergebnis["gesamt_l"] > 0:
                ppl = preis / ergebnis["gesamt_l"]
                ergebnis["preis_pro_liter"] = ("%.2f" % ppl).replace(".", ",")
        except ValueError:
            pass

    return ergebnis


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
    titel = str(titel).strip()

    # Gueltigkeit
    gueltig_bis = angebot.get("validityEndDate") or angebot.get("validTo")

    # Gebinde aus dem Titel analysieren (Anzahl, Groesse, Typ, Literpreis)
    gebinde = analysiere_gebinde(titel, preis)

    return {
        "bier_id": bier["id"],
        "bier_name": bier["name"],
        "markt_name": haendler,
        "markt_ort": plz_ort,
        "titel": titel,
        "preis": preis,
        "gueltig_bis": gueltig_bis,
        "gebinde_typ": gebinde["gebinde_typ"],
        "anzahl": gebinde["anzahl"],
        "einzelgroesse_l": gebinde["einzelgroesse_l"],
        "gesamt_l": gebinde["gesamt_l"],
        "preis_pro_liter": gebinde["preis_pro_liter"],
        "quelle": "marktguru",
    }


def ist_kasten(angebot):
    """
    Prueft, ob ein Angebot ein Kasten ist - nur diese interessieren uns.

    Ein Angebot gilt als Kasten, wenn:
      - der erkannte Gebinde-Typ 'Kasten' ist, ODER
      - es ein Mehrgebinde mit mindestens 10 Flaschen ist
        (faengt Kaesten ab, bei denen das Wort 'Kasten' im Titel fehlt,
         z.B. 'Veltins 24 x 0,33 l').

    Ausdruecklich NICHT als Kasten zaehlen: Sixpacks, Dosen,
    Einzelflaschen und Faesser.
    """
    typ = angebot.get("gebinde_typ")
    anzahl = angebot.get("anzahl")

    # eindeutige Nicht-Kaesten direkt aussortieren
    if typ in ("Dose", "Fass", "Sixpack", "Einzelflasche"):
        return False

    if typ == "Kasten":
        return True

    # kein klarer Typ, aber viele Flaschen -> ist praktisch ein Kasten
    if isinstance(anzahl, int) and anzahl >= 10:
        return True

    return False


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
    except Exception as e:
        print(f"FEHLER beim Holen der Schluessel: {e}", file=sys.stderr)
        # Bisherige Angebote NICHT loeschen - nur den Fehler vermerken,
        # damit die App weiterhin die letzten bekannten Angebote zeigt.
        behalte_bei_fehler(str(e))
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
                    # Nur Kaesten behalten - Sixpacks, Dosen und
                    # Einzelflaschen interessieren uns nicht.
                    kaesten = 0
                    for t in passend:
                        angebot = baue_angebot(t, bier, ort)
                        if ist_kasten(angebot):
                            alle_angebote.append(angebot)
                            kaesten += 1
                    print(f"   '{begriff}' @ {plz} ({ort}): "
                          f"{kaesten} Kaesten von {len(passend)} passenden "
                          f"({len(treffer)} Treffer)")
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


def behalte_bei_fehler(fehlertext):
    """
    Wird aufgerufen, wenn der Scraper keine neuen Daten holen konnte.
    Behaelt die zuletzt bekannten Angebote bei und vermerkt nur den
    Fehler - so bleibt die App nutzbar statt komplett leer zu sein.
    """
    try:
        alt = lade_json(OUTPUT_FILE)
        alte_angebote = alt.get("angebote", [])
    except Exception:
        alte_angebote = []
    schreibe_ergebnis(alte_angebote, [fehlertext])
    print(f"Hinweis: {len(alte_angebote)} bisherige Angebote beibehalten.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"Schwerer Fehler: {e}", file=sys.stderr)
        sys.exit(1)
