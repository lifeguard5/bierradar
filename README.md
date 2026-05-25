# 🍺 Bierradar

Eine kleine Web-App, die zeigt, in welchem Getränke- oder Lebensmittelmarkt
gerade ein bestimmtes Bier im Angebot ist. Im Veltins-Look, mobil-optimiert,
läuft kostenlos über GitHub Pages.

Beobachtete Biere: **Veltins**, **Erdinger Weißbier**, **Mönchshof Hell**,
**Hasseröder**.

---

## Wie es funktioniert

1. Ein Skript (`scraper/scrape.py`) versucht **einmal täglich automatisch**
   (per GitHub Actions), die Angebote der konfigurierten Märkte auszulesen.
2. Es filtert nach den gesuchten Biersorten und schreibt die Treffer in
   `data/angebote.json`.
3. Die Web-App (`index.html`) zeigt diese Angebote schön aufbereitet an.

> **Wichtig – bitte einmal lesen:**
> Große Handelsketten wie REWE und EDEKA sichern ihre Seiten gegen
> automatische Zugriffe ab. In Tests haben **alle drei Beispiel-Märkte den
> Zugriff blockiert** (Fehler „403"). Das automatische Auslesen funktioniert
> daher **nicht zuverlässig** – es kann bei manchen Märkten klappen, bei
> anderen nicht. Deshalb gibt es das **manuelle Nachtragen** (siehe unten).
> Das ist kein Notbehelf, sondern der verlässliche Weg, die App aktuell zu
> halten.

---

## Einrichtung (einmalig, ca. 5 Minuten)

1. **GitHub-Konto** anlegen (falls noch nicht vorhanden) auf github.com.
2. Ein **neues Repository** anlegen, z. B. `bierradar`. Es kann ruhig
   öffentlich sein.
3. Alle Dateien aus diesem Ordner ins Repository hochladen
   (per Drag & Drop auf der GitHub-Webseite reicht völlig).
4. Im Repository auf **Settings → Pages** gehen.
   Unter „Build and deployment" → „Source" **Deploy from a branch** wählen,
   Branch **main**, Ordner **/ (root)**, speichern.
5. Nach ein, zwei Minuten ist die App erreichbar unter:
   `https://DEIN-BENUTZERNAME.github.io/bierradar/`
6. Den **GitHub-Actions-Scraper** aktivieren: Reiter **Actions** öffnen,
   die Workflows einmal bestätigen („I understand my workflows, go ahead
   and enable them"). Ab dann läuft der Scraper täglich automatisch.

Diesen Link kannst du an deine Freunde schicken. Auf dem Handy kann man die
Seite über „Zum Startbildschirm hinzufügen" wie eine echte App ablegen.

---

## Märkte hinzufügen oder ändern

Bearbeite die Datei **`data/markets.json`**. Pro Markt ein Eintrag:

```json
{
  "id": "edeka-musterstadt",
  "name": "EDEKA Musterstadt",
  "ort": "Musterstadt, Hauptstr. 1",
  "typ": "edeka",
  "url": "https://www.edeka.de/maerkte/...",
  "aktiv": true
}
```

- `id` – eindeutiges Kürzel, frei wählbar (keine Leerzeichen).
- `typ` – `rewe`, `edeka`, `koenner` (automatischer Versuch) oder
  `manuell` (nur Handpflege).
- Bitte nur Märkte im Umkreis von **ca. 20 km um Breuna** eintragen.

Nach dem Speichern auf GitHub läuft der Scraper automatisch neu.

---

## Angebote von Hand eintragen  ⭐ wichtigster Teil

Da das automatische Auslesen oft blockiert wird, trägst du gefundene
Bierangebote am besten selbst ein. Das geht in der Datei
**`data/manuell.json`**. Pro Angebot ein Eintrag:

```json
{
  "markt_id": "rewe-breuna",
  "bier_id": "veltins",
  "titel": "Veltins Pilsener 20x0,5l",
  "preis": "13,99",
  "gueltig_bis": "2026-05-31"
}
```

- `markt_id` – muss zu einer `id` aus `markets.json` passen.
- `bier_id` – `veltins`, `erdinger`, `moenchshof` oder `hasseroeder`
  (siehe `data/biere.json`).
- `gueltig_bis` – Datum im Format `JJJJ-MM-TT`. Nach diesem Tag verschwindet
  das Angebot **automatisch** aus der App.

So geht's am schnellsten direkt auf github.com:
Datei `data/manuell.json` öffnen → Stift-Symbol (bearbeiten) → Eintrag
ergänzen → unten „Commit changes". Fertig – die App aktualisiert sich von
selbst.

---

## Biersorten ändern

Die beobachteten Biere stehen in **`data/biere.json`**. Dort können weitere
Sorten ergänzt oder die Erkennungs-Stichwörter (`aliase`) erweitert werden.

---

## Wenn der automatische Scraper bei einem Markt klappt

Falls ein Markt doch automatisch lesbar ist, aber kein Bier erkannt wird,
liegt es meist an der Erkennung. Dann in `scraper/scrape.py` die jeweilige
`parse_*`-Funktion bzw. die Stichwörter in `biere.json` anpassen. Die
Stellen sind im Code kommentiert.

---

## Projektaufbau

```
bierradar/
├── index.html              Die App-Seite
├── manifest.json           Damit die App aufs Handy gelegt werden kann
├── assets/
│   ├── style.css           Design (Veltins-Look)
│   ├── app.js              App-Logik
│   └── favicon.svg         Symbol
├── data/
│   ├── markets.json        ➜ Märkte hier eintragen
│   ├── biere.json          ➜ Biersorten
│   ├── manuell.json        ➜ Angebote von Hand eintragen
│   └── angebote.json       (automatisch erzeugt – nicht bearbeiten)
├── scraper/
│   ├── scrape.py           Das Auslese-Skript
│   └── requirements.txt
└── .github/workflows/
    └── scrape.yml          Der tägliche Automatik-Lauf
```

---

*Bierradar ist ein privates Projekt. Keine offizielle Seite einer Brauerei
oder eines Marktes. Angaben ohne Gewähr.*
